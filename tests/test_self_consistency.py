"""테스트: SelfConsistencyEngine 증폭 모듈.

단일 모델 N샘플링 → 유사도 클러스터링 → 다수결 선택이 정확히 동작하는지,
config 매핑이 올바른지, 실패 경로가 안전한지 검증한다.
"""

from collections.abc import Callable, Iterator
from typing import TypedDict, cast, final

import pytest

from antigravity_k.engine.self_consistency import (
    ConsistencyTrace,
    SelfConsistencyEngine,
    config_to_engine_kwargs,
    jaccard,
    normalize_answer,
)


class _GenState(TypedDict):
    i: int
    temps: list[float]


class _EngineKwargs(TypedDict, total=False):
    n_samples: int
    base_temperature: float
    temperature_spread: float
    similarity_threshold: float
    complexity_threshold: float
    selection: str


@final
class _RouterDouble:
    def get_combo(self, _model: str) -> None:
        return None


@final
class _ManagerDouble:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.router = _RouterDouble()
        self._registry: object = object()
        self.self_consistent_calls = 0
        self.generate_calls = 0

    def get_system_prompt(self) -> str:
        return ""

    def get_tool_prompt(self) -> str:
        return ""

    def is_loaded(self, name: str) -> bool:
        return name == self.model_name

    def generate(self, prompt: str, target: str, **kwargs: object) -> str:
        _ = prompt, target, kwargs
        self.generate_calls += 1
        return "plain"

    def stream_generate(self, **kwargs: object) -> Iterator[str]:
        _ = kwargs
        return iter(())

    def generate_best_of_n(self, prompt: str, target: str, **kwargs: object) -> str:
        _ = prompt, target, kwargs
        return "best"

    def generate_self_consistent(self, prompt: str, target: str, **kwargs: object) -> str:
        _ = prompt, target, kwargs
        self.self_consistent_calls += 1
        return "amplified"

    def generate_decomposed(
        self,
        prompt: str,
        target: str,
        *,
        force: bool = False,
        **kwargs: object,
    ) -> str:
        _ = prompt, target, force, kwargs
        return "decomposed"


@final
class _ContextDouble:
    tool_guardrail = None
    cognitive_loop = None
    quality_gate = None
    tool_executor = None


@final
class _OrchestratorDouble:
    def __init__(self, config: dict[str, object], model_name: str) -> None:
        self.config = config
        self.project_root = "/tmp"
        self._skill_prompts_cache = ""
        self._last_agent_output = ""
        self.expected_tools: tuple[str, ...] = ()
        self.manager = _ManagerDouble(model_name)
        self.ctx = _ContextDouble()
        self.selected_model = self._get_model_for_role("SELF")

    def _get_model_for_role(self, _role: str) -> str:
        return self.manager.model_name


def _gen_factory(responses: list[str]) -> tuple[Callable[..., str], _GenState]:
    """responses를 순차 반환하는 generate_fn. 호출 시 temperature를 기록한다."""
    state: _GenState = {"i": 0, "temps": []}

    def gen(prompt: str, **kwargs: object) -> str:
        _ = prompt
        i = state["i"]
        state["i"] += 1
        temperature = kwargs.get("temperature")
        if isinstance(temperature, (int, float)):
            state["temps"].append(float(temperature))
        return responses[min(i, len(responses) - 1)]

    return gen, state


def _constant_generator(value: str) -> Callable[..., str]:
    def generate(_prompt: str, **_kwargs: object) -> str:
        return value

    return generate


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
        # 병렬+조기종료 환경에서 결정적으로 검증한다: 낮은 온도(결정론적
        # 샘플)는 FIB, 높은 온도는 OTHER를 반환하는 생성기.
        # n=5 → 첫 웨이브(과반=3, 온도 낮은 3개)가 모두 FIB → 과반 형성으로
        # 조기 종료하고 FIB가 선택된다.
        def gen(_prompt: str, **kwargs: object) -> str:
            temp = float(kwargs.get("temperature", 0.0))
            return CODE_FIB if temp < 0.72 else CODE_OTHER

        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=5,
            base_temperature=0.7,
            temperature_spread=0.3,
            similarity_threshold=0.4,
        )
        trace = eng.run("write fib")
        assert "def fib" in trace.selected
        assert trace.confidence == 1.0  # 조기 종료된 3샘플이 전원 일치
        assert len(trace.samples) == 3  # 나머지 2샘플은 생략

    def test_unanimous_gives_full_confidence(self):
        gen, _ = _gen_factory([CODE_FIB] * 5)
        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=5, similarity_threshold=0.3)
        trace = eng.run("write fib")
        assert abs(trace.confidence - 1.0) < 0.01
        assert len(trace.cluster_sizes) == 1

    def test_tie_break_prefers_lower_temperature(self):
        # 동점 클러스터에서는 첫 번째(더 낮은 온도 샘플을 포함한) 클러스터의
        # 최저 온도 구성원을 대표로 삼는다.
        def gen(_prompt: str, **kwargs: object) -> str:
            temp = float(kwargs.get("temperature", 0.0))
            return CODE_FIB if temp < 0.68 else CODE_OTHER

        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=4,
            base_temperature=0.7,
            temperature_spread=0.2,
            similarity_threshold=0.2,
        )
        # 온도: [0.567, 0.633, 0.7, 0.767] → FIB 2 : OTHER 2 동점
        trace = eng.run("q")
        assert "def fib" in trace.selected  # 동점 시 저온 클러스터가 이긴다

    def test_no_majority_collects_all_samples(self):
        # 과반이 형성되지 않으면 전체 N개를 수집한다 (정확한 클러스터 통계).
        calls = {"n": 0}

        def gen(_prompt: str, **kwargs: object) -> str:
            _ = kwargs
            calls["n"] += 1
            return f"unique answer {calls['n']}"

        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=5,
            similarity_threshold=0.8,
        )
        trace = eng.run("q")
        assert len(trace.samples) == 5
        assert calls["n"] == 5


class TestDiversity:
    def test_temperature_varies_across_samples(self):
        gen, state = _gen_factory([CODE_FIB] * 5)
        eng = SelfConsistencyEngine(
            generate_fn=gen,
            n_samples=5,
            base_temperature=0.7,
            temperature_spread=0.3,
        )
        _ = eng.run("q")
        # 샘플링된 모든 온도는 서로 다르다 (과반 조기 종료로 3개 이상)
        assert len(set(state["temps"])) >= 3
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
        eng = SelfConsistencyEngine(generate_fn=_constant_generator("x"), n_samples=1)
        trace = eng.run("q")
        assert trace.skipped is True

    def test_all_empty_samples_skips(self):
        eng = SelfConsistencyEngine(generate_fn=_constant_generator(""), n_samples=3)
        trace = eng.run("q")
        assert trace.skipped is True
        assert trace.skip_reason == "all samples empty"

    def test_partial_sample_failure_does_not_crash(self):
        # 일부 샘플 호출이 예외를 던져도 전체는 살아남는다.
        calls = {"i": 0}

        def gen(_prompt: str, **kwargs: object) -> str:
            _ = kwargs
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
        kw = cast(_EngineKwargs, cast(object, config_to_engine_kwargs({"n_samples": 3, "base_temperature": 0.6})))
        eng = SelfConsistencyEngine(generate_fn=_constant_generator("x"), **kw)
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
        calls: list[object] = []

        def gen(_prompt: str, **kwargs: object) -> str:
            calls.append(kwargs.get("temperature"))
            return CODE_FIB

        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=3, complexity_threshold=0.4)
        trace = eng.run("안녕하세요 도움 목록 보여줘")
        assert trace.skipped is True
        assert "complexity" in trace.skip_reason
        assert calls == []  # 샘플링 발화 없음

    def test_complex_task_fires_sampling(self):
        # 복잡 작업(아키텍처/동시성/캐시)은 게이트 통과 — 샘플링 발화.
        # 전원 동일 답변이므로 과반(n//2+1=2) 형성 후 조기 종료한다.
        calls: list[int] = []

        def gen(_prompt: str, **kwargs: object) -> str:
            _ = kwargs
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
        assert len(calls) >= 2  # 과반 웨이브는 실행됨
        assert trace.confidence == 1.0

    def test_no_threshold_always_fires(self):
        # complexity_threshold=None이면 게이트 없이 항상 N샘플링.
        calls: list[int] = []

        def gen(_prompt: str, **kwargs: object) -> str:
            _ = kwargs
            calls.append(1)
            return CODE_FIB

        eng = SelfConsistencyEngine(generate_fn=gen, n_samples=2, similarity_threshold=0.2)
        trace = eng.run("간단한 질문")
        assert trace.skipped is False
        assert len(calls) == 2

    def test_threshold_zero_fires_everything(self):
        # threshold=0.0이면 복잡도가 0이 아니면 모두 발화.
        calls: list[int] = []

        def gen(_prompt: str, **kwargs: object) -> str:
            _ = kwargs
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
    def _orch_factory(self) -> Callable[..., _OrchestratorDouble]:
        def make(config: dict[str, object], model_name: str = "deepseek-r1:70b") -> _OrchestratorDouble:
            return _OrchestratorDouble(config, model_name)

        return make

    def test_non_qwen_model_uses_self_consistency_when_enabled(
        self, _orch_factory: Callable[..., _OrchestratorDouble]
    ):
        # config 켜짐 + 비-qwen 모델 → generate_self_consistent 호출.
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = _orch_factory(
            {"amplification": {"self_consistency": {"enabled": True}}},
            model_name="deepseek-r1:70b",
        )
        _ = list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        assert orch.manager.self_consistent_calls == 1
        # 핵심: 직접 응답이 self-consistent 경로를 탔다 (revision 호출은 별개).

    def test_non_qwen_model_falls_back_when_disabled(
        self, _orch_factory: Callable[..., _OrchestratorDouble]
    ):
        # config 꺼짐 + 비-qwen 모델 → 일반 generate (self-consistent 미호출).
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = _orch_factory(
            {"amplification": {"self_consistency": {"enabled": False}}},
            model_name="deepseek-r1:70b",
        )
        _ = list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        assert orch.manager.self_consistent_calls == 0
        assert orch.manager.generate_calls == 1
        # 핵심: 비활성 시 self-consistent 경로를 타지 않는다.

    def test_qwen_model_still_works_when_enabled(
        self, _orch_factory: Callable[..., _OrchestratorDouble]
    ):
        # qwen 모델 + config 켜짐 → 여전히 generate_self_consistent (회귀 방지).
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = _orch_factory(
            {"amplification": {"self_consistency": {"enabled": True}}},
            model_name="qwen3.6:latest",
        )
        _ = list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        assert orch.manager.self_consistent_calls == 1
