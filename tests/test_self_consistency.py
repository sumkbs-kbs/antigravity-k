"""테스트: SelfConsistencyEngine 증폭 모듈.

단일 모델 N샘플링 → 유사도 클러스터링 → 다수결 선택이 정확히 동작하는지,
config 매핑이 올바른지, 실패 경로가 안전한지 검증한다.
"""

import pytest

from antigravity_k.engine.self_consistency import (
    ConsistencyTrace,
    SelfConsistencyEngine,
    config_to_engine_kwargs,
    jaccard,
    normalize_answer,
)


def _gen_factory(responses):
    """responses를 순차 반환하는 generate_fn. 호출 시 temperature를 기록한다."""
    state = {"i": 0, "temps": []}

    def gen(prompt, **kwargs):
        i = state["i"]
        state["i"] += 1
        state["temps"].append(kwargs.get("temperature"))
        return responses[min(i, len(responses) - 1)]

    return gen, state


CODE_FIB = "```python\ndef fib(n):\n    return n\n```"
CODE_OTHER = "```python\ndef other(x):\n    pass\n```"


class TestNormalize:
    def test_extracts_code_fence_body(self):
        # 코드 작업에서는 펜스 본문이 정답의 핵심 — 본문만 정규화 대상.
        n = normalize_answer("explanation\n```python\ndef f():\n    return 1\n```\nmore")
        assert "def f" in n
        assert "explanation" not in n

    def test_lowercase_and_punct_collapse(self):
        n1 = normalize_answer("Hello, World!")
        n2 = normalize_answer("hello world")
        assert n1 == n2

    def test_empty_safe(self):
        assert normalize_answer("") == ""


class TestJaccard:
    def test_identical_is_one(self):
        assert jaccard(frozenset("a b c".split()), frozenset("a b c".split())) == 1.0

    def test_disjoint_is_zero(self):
        assert jaccard(frozenset("a".split()), frozenset("b".split())) == 0.0

    def test_empty_both_is_one(self):
        assert jaccard(frozenset(), frozenset()) == 1.0


class TestSelection:
    def test_majority_cluster_wins(self):
        # 3개 동일코드 + 2개 다른코드 → 다수결이 동일코드.
        gen, _ = _gen_factory([CODE_FIB] * 3 + [CODE_OTHER] * 2)
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=5, similarity_threshold=0.4)
        trace = eng.run("write fib")
        assert "def fib" in trace.selected
        assert abs(trace.confidence - 0.6) < 0.01
        assert trace.cluster_sizes == [3, 2]

    def test_unanimous_gives_full_confidence(self):
        gen, _ = _gen_factory([CODE_FIB] * 5)
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=5, similarity_threshold=0.3)
        trace = eng.run("write fib")
        assert abs(trace.confidence - 1.0) < 0.01
        assert len(trace.cluster_sizes) == 1

    def test_tie_break_prefers_lower_temperature(self):
        # 동점 클러스터에서는 더 낮은 온도(결정론적) 샘플을 대표로 삼는다.
        gen, state = _gen_factory([CODE_FIB, CODE_OTHER, CODE_FIB, CODE_OTHER])
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=4, similarity_threshold=0.2)
        eng.run("q")
        # 온도는 단조증가하므로 첫 번째 샘플이 가장 낮음
        assert state["temps"] == sorted(state["temps"])


class TestDiversity:
    def test_temperature_varies_across_samples(self):
        gen, state = _gen_factory([CODE_FIB] * 5)
        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=5,
            base_temperature=0.7,
            temperature_spread=0.3,
        )
        eng.run("q")
        assert len(set(state["temps"])) == 5  # 모두 다른 온도
        assert min(state["temps"]) >= 0.0
        assert max(state["temps"]) <= 1.5

    def test_single_sample_is_skipped(self):
        # n_samples<=1은 self-consistency가 무의미하므로 샘플링 없이 스킵한다.
        gen, state = _gen_factory([CODE_FIB])
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=1)
        trace = eng.run("q")
        assert trace.skipped is True
        assert state["temps"] == []


class TestSafetyAndSkip:
    def test_no_generate_fn_skips(self):
        eng = SelfConsistencyEngine(generate_fn=None, n_samples=5)
        trace = eng.run("q")
        assert trace.skipped is True

    def test_n_samples_one_skips(self):
        eng = SelfConsistencyEngine(generate_fn=lambda p, **k: "x", n_samples=1)
        trace = eng.run("q")
        assert trace.skipped is True

    def test_all_empty_samples_skips(self):
        eng = SelfConsistencyEngine(generate_fn=lambda p, **k: "", n_samples=3)
        trace = eng.run("q")
        assert trace.skipped is True
        assert trace.skip_reason == "all samples empty"

    def test_partial_sample_failure_does_not_crash(self):
        # 일부 샘플 호출이 예외를 던져도 전체는 살아남는다.
        calls = {"i": 0}

        def gen(prompt, **kwargs):
            calls["i"] += 1
            if calls["i"] == 2:
                raise RuntimeError("transient")
            return CODE_FIB

        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=3, similarity_threshold=0.3)
        trace = eng.run("q")
        assert trace.skipped is False
        assert "def fib" in trace.selected


class TestConfigMapping:
    def test_full_config(self):
        kw = config_to_engine_kwargs(
            {
                "n_samples": 7,
                "base_temperature": 0.9,
                "temperature_spread": 0.25,
                "similarity_threshold": 0.6,
                "selection": "majority",
            }
        )
        assert kw == {
            "n_samples": 7,
            "base_temperature": 0.9,
            "temperature_spread": 0.25,
            "similarity_threshold": 0.6,
            "selection": "majority",
        }

    def test_complexity_threshold_mapped(self):
        kw = config_to_engine_kwargs({"complexity_threshold": 0.4})
        assert kw == {"complexity_threshold": 0.4}

    def test_none_values_skipped(self):
        kw = config_to_engine_kwargs({"n_samples": None, "base_temperature": 0.7})
        assert kw == {"base_temperature": 0.7}

    def test_invalid_values_ignored(self):
        kw = config_to_engine_kwargs({"n_samples": "not-a-number"})
        assert "n_samples" not in kw

    def test_non_dict_returns_empty(self):
        assert config_to_engine_kwargs(None) == {}
        assert config_to_engine_kwargs("string") == {}

    def test_kwargs_build_valid_engine(self):
        kw = config_to_engine_kwargs({"n_samples": 3, "base_temperature": 0.6})
        eng = SelfConsistencyEngine(generate_fn=lambda p, **k: "x", **kw)
        assert eng.n_samples == 3
        assert eng.base_temperature == 0.6


class TestTraceShape:
    def test_samples_assigned_cluster_ids(self):
        gen, _ = _gen_factory([CODE_FIB, CODE_OTHER, CODE_FIB])
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=3, similarity_threshold=0.2)
        trace = eng.run("q")
        assert all(s.cluster_id >= 0 for s in trace.samples)

    def test_latency_recorded(self):
        gen, _ = _gen_factory([CODE_FIB] * 3)
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=3, similarity_threshold=0.3)
        trace = eng.run("q")
        assert trace.latency_ms >= 0.0
        assert isinstance(trace, ConsistencyTrace)


class TestComplexityGating:
    """complexity_threshold로 단순 작업은 N샘플링을 스킵하는지 검증."""

    def test_simple_task_skipped_no_samples(self):
        # 단순 작업("안녕 도움 목록")은 복잡도 0.1로 게이트에서 스킵 — 0회 발화.
        calls = []

        def gen(prompt, **kwargs):
            calls.append(kwargs.get("temperature"))
            return CODE_FIB

        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=3, complexity_threshold=0.4)
        trace = eng.run("안녕하세요 도움 목록 보여줘")
        assert trace.skipped is True
        assert "complexity" in trace.skip_reason
        assert calls == []  # 샘플링 발화 없음

    def test_complex_task_fires_sampling(self):
        # 복잡 작업(아키텍처/동시성/캐시)은 게이트 통과 — N회 발화.
        calls = []

        def gen(prompt, **kwargs):
            calls.append(1)
            return CODE_FIB

        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=3,
            complexity_threshold=0.4,
            similarity_threshold=0.2,
        )
        trace = eng.run("분산 시스템 아키텍처 설계와 동시성 캐시 최적화")
        assert trace.skipped is False
        assert len(calls) == 3

    def test_no_threshold_always_fires(self):
        # complexity_threshold=None이면 게이트 없이 항상 N샘플링.
        calls = []

        def gen(prompt, **kwargs):
            calls.append(1)
            return CODE_FIB

        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=2, similarity_threshold=0.2)
        trace = eng.run("간단한 질문")
        assert trace.skipped is False
        assert len(calls) == 2

    def test_threshold_zero_fires_everything(self):
        # threshold=0.0이면 복잡도가 0이 아니면 모두 발화.
        calls = []

        def gen(prompt, **kwargs):
            calls.append(1)
            return CODE_FIB

        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=2,
            complexity_threshold=0.0,
            similarity_threshold=0.2,
        )
        trace = eng.run("아무 질문")
        assert trace.skipped is False


class TestSharedComplexityEstimator:
    """CoV와 self-consistency가 같은 estimate_complexity를 공유하는지 검증."""

    def test_cov_method_equals_module_function(self):
        from antigravity_k.engine.chain_of_verification import ChainOfVerification, estimate_complexity

        cov = ChainOfVerification()
        task = "복잡한 알고리즘 아키텍처 설계 최적화"
        assert cov.estimate_complexity(task) == estimate_complexity(task)

    def test_simple_indicators_low_complexity(self):
        from antigravity_k.engine.chain_of_verification import estimate_complexity

        # SIMPLE_INDICATORS 2개 이상 → 0.1
        assert estimate_complexity("hello hi 간단한 목록") == 0.1

    def test_complex_indicators_high_complexity(self):
        from antigravity_k.engine.chain_of_verification import estimate_complexity

        # 복잡 지표 다수 → 높은 점수
        score = estimate_complexity("분산 동시성 캐시 아키텍처 최적화 보안")
        assert score >= 0.5
        from antigravity_k.engine.chain_of_verification import estimate_complexity

        score = estimate_complexity("분산 동시성 캐시 아키텍처 최적화 보안")
        assert score >= 0.5


# ─── 일반화 (qwen 하드코딩 → config 기반) 회귀 ────────────────────


class TestGeneralizedSelfConsistencyPath:
    """self-consistency 경로가 qwen 하드코딩이 아닌 config 기반인지 검증.

    run_loop 직접 응답 경로에서, 모델명에 'qwen3'이 없어도
    amplification.self_consistency.enabled가 켜지면 generate_self_consistent가
    호출되어야 한다 (20B+ 모델 전반 지원).
    """

    @pytest.fixture
    def _orch_factory(self):
        """direct_response run_loop를 위한 최소 orch stub을 반환."""
        from unittest.mock import AsyncMock, MagicMock

        def make(config: dict, model_name: str = "deepseek-r1:70b"):
            orch = MagicMock()
            orch.config = config
            orch.project_root = "/tmp"
            orch._skill_prompts_cache = ""
            orch._last_agent_output = ""
            # 비-qwen 모델을 반환하도록 준비
            orch._prepare_agent_prompt.return_value = (
                model_name,
                "sys",
                "tool",
                "skill",
                "prompt",
                [{"role": "user", "content": "hi"}],
            )
            orch.manager = MagicMock()
            orch.manager._registry = MagicMock()
            orch.manager.router = MagicMock()
            orch.manager.router.get_combo.return_value = None
            orch.manager.is_loaded.return_value = True
            orch.manager.get_system_prompt.return_value = ""
            orch.manager.get_tool_prompt.return_value = ""
            orch._get_model_for_role.return_value = model_name
            ctx = MagicMock()
            ctx.tool_guardrail = MagicMock()
            ctx.tool_guardrail.reset = MagicMock()
            ctx.cognitive_loop = MagicMock()
            ctx.quality_gate = MagicMock()
            ctx.quality_gate.reset = MagicMock()
            ctx.tool_executor = MagicMock()
            ctx.tool_executor.execute_async = AsyncMock(return_value="ok")
            orch.ctx = ctx
            return orch

        return make

    def test_non_qwen_model_uses_self_consistency_when_enabled(self, _orch_factory):
        # config 켜짐 + 비-qwen 모델 → generate_self_consistent 호출.
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = _orch_factory(
            {"amplification": {"self_consistency": {"enabled": True}}},
            model_name="deepseek-r1:70b",
        )
        orch.manager.generate_self_consistent.return_value = "amplified"
        orch.manager.generate.return_value = "plain"

        list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        orch.manager.generate_self_consistent.assert_called_once()
        # 핵심: 직접 응답이 self-consistent 경로를 탔다 (revision 호출은 별개).

    def test_non_qwen_model_falls_back_when_disabled(self, _orch_factory):
        # config 꺼짐 + 비-qwen 모델 → 일반 generate (self-consistent 미호출).
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = _orch_factory(
            {"amplification": {"self_consistency": {"enabled": False}}},
            model_name="deepseek-r1:70b",
        )
        orch.manager.generate_self_consistent.return_value = "amplified"
        orch.manager.generate.return_value = "plain"

        list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        orch.manager.generate_self_consistent.assert_not_called()
        # 핵심: 비활성 시 self-consistent 경로를 타지 않는다.

    def test_qwen_model_still_works_when_enabled(self, _orch_factory):
        # qwen 모델 + config 켜짐 → 여전히 generate_self_consistent (회귀 방지).
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = _orch_factory(
            {"amplification": {"self_consistency": {"enabled": True}}},
            model_name="qwen3.6:latest",
        )
        orch.manager.generate_self_consistent.return_value = "amplified"
        orch.manager.generate.return_value = "plain"

        list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        orch.manager.generate_self_consistent.assert_called_once()
