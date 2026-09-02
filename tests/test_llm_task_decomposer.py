"""테스트: LlmTaskDecomposer 증폭 모듈.

복잡한 멀티스텝 작업을 LLM으로 단계 분해해 작은 모델의 추론 약점을 보완하는지,
단순 작업은 스킵하고 실패 경로는 안전한지 검증한다.
"""

from collections.abc import Callable
from typing import cast
from unittest.mock import MagicMock

from antigravity_k.engine import llm_task_decomposer as _decomposer_module
from antigravity_k.engine.llm_task_decomposer import (
    Decomposition,
    LlmTaskDecomposer,
    is_complex_task,
)

_extract_steps: Callable[[str], list[str]] = cast(
    Callable[[str], list[str]],
    getattr(_decomposer_module, "_extract_steps"),
)


def _mock_method(obj: object, name: str) -> MagicMock:
    return cast(MagicMock, getattr(obj, name))


def _replace_method(obj: object, name: str, mock: MagicMock) -> None:
    setattr(obj, name, mock)


class TestIsComplexTask:
    def test_simple_short_skipped(self):
        assert is_complex_task("안녕") is False

    def test_simple_code_skipped(self):
        # 단순 함수 작성은 분해 가치 없음.
        assert is_complex_task("파이보나치 함수를 작성해줘") is False

    def test_architecture_design_not_sequential(self):
        # 단일 산출물 아키텍처 설계는 분해 이득 없이 지연만 4배 늘어 제외.
        assert is_complex_task("이벤트 소싱 CQRS 패턴을 설계하세요") is False

    def test_complex_workflow_detected(self):
        assert is_complex_task("코드 마이그레이션 워크플로를 단계별로 설계하세요") is True

    def test_complex_pipeline_detected(self):
        assert is_complex_task("build a multi-stage deployment pipeline") is True

    def test_empty_safe(self):
        assert is_complex_task("") is False


class TestExtractSteps:
    def test_json_array(self):
        raw = '["단계1", "단계2", "단계3"]'
        assert _extract_steps(raw) == ["단계1", "단계2", "단계3"]

    def test_json_in_fence(self):
        raw = '```json\n["a", "b"]\n```'
        assert _extract_steps(raw) == ["a", "b"]

    def test_numbered_list(self):
        raw = "1. 분석\n2. 계획\n3. 실행"
        assert _extract_steps(raw) == ["분석", "계획", "실행"]

    def test_bulleted_list(self):
        raw = "- a\n- b\n- c"
        assert _extract_steps(raw) == ["a", "b", "c"]

    def test_empty_safe(self):
        assert _extract_steps("") == []

    def test_garbage_safe(self):
        # 단일 문장은 단계 아님.
        assert _extract_steps("그냥 설명만 있는 문장입니다.") == []


def _gen_factory(response: str) -> Callable[[str], str]:
    def gen(_prompt: str) -> str:
        return response

    return gen


class TestDecompose:
    def test_complex_task_decomposes(self):
        gen = _gen_factory('["분석", "계획", "실행", "검증"]')
        d = LlmTaskDecomposer(generate_fn=gen).decompose("멀티스텝 마이그레이션 워크플로 설계 과제")
        assert not d.skipped
        assert len(d.steps) == 4

    def test_simple_task_skipped(self):
        gen = _gen_factory('["x"]')
        d = LlmTaskDecomposer(generate_fn=gen).decompose("간단한 함수 작성")
        assert d.skipped
        assert "not complex" in d.skip_reason

    def test_no_generate_fn_skipped(self):
        d = LlmTaskDecomposer(generate_fn=None).decompose("복잡한 워크플로 설계 과제")
        assert d.skipped
        assert "generate_fn" in d.skip_reason

    def test_too_few_steps_skipped(self):
        # 복잡한 작업이지만 LLM이 단일 단계만 반환 → 스킵.
        gen = _gen_factory('["유일단계"]')
        d = LlmTaskDecomposer(generate_fn=gen).decompose("코드 마이그레이션 워크플로를 단계별로 설계")
        assert d.skipped
        assert "too few" in d.skip_reason

    def test_max_steps_caps(self):
        many = "[" + ", ".join(f'"단계{i}"' for i in range(20)) + "]"
        gen = _gen_factory(many)
        d = LlmTaskDecomposer(generate_fn=gen, max_steps=5).decompose(
            "코드 마이그레이션 워크플로를 단계별로 설계하세요"
        )
        assert not d.skipped
        assert len(d.steps) == 5

    def test_generate_error_skipped_safe(self):
        def boom(_p: str) -> str:
            raise RuntimeError("transient")

        d = LlmTaskDecomposer(generate_fn=boom).decompose("코드 마이그레이션 워크플로를 설계")
        assert d.skipped
        assert "generate error" in d.skip_reason

    def test_empty_response_skipped(self):
        gen = _gen_factory("")
        d = LlmTaskDecomposer(generate_fn=gen).decompose("코드 마이그레이션 워크플로를 설계하세요")
        assert d.skipped


class TestStepPrompt:
    def test_includes_context_and_step(self):
        gen = _gen_factory("[]")
        dec = LlmTaskDecomposer(generate_fn=gen)
        sp = dec.step_prompt("특정단계", "원본작업맥락")
        assert "원본작업맥락" in sp
        assert "특정단계" in sp

    def test_completed_results_flow_into_next_step(self):
        dec = LlmTaskDecomposer(generate_fn=_gen_factory("[]"))
        sp = dec.step_prompt("2단계", "원본", completed_results=["1단계 출력"])
        assert "1단계 출력" in sp
        assert "일관되게 이어서" in sp

    def test_first_step_has_no_prior_context(self):
        dec = LlmTaskDecomposer(generate_fn=_gen_factory("[]"))
        sp = dec.step_prompt("1단계", "원본", completed_results=None)
        assert "이전 단계 결과" not in sp

    def test_decomposition_dataclass_shape(self):
        d = Decomposition(original_task="x", steps=["a", "b"])
        assert d.original_task == "x"
        assert d.steps == ["a", "b"]
        assert d.skipped is False


class TestManagerIntegration:
    def _manager(self):
        from unittest.mock import MagicMock

        from antigravity_k.engine.model_manager import ModelManager
        from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
        from antigravity_k.engine.model_router import ModelRouter
        from antigravity_k.engine.usage_tracker import UsageTracker

        registry = MagicMock(spec=ModelRegistry)
        memory_config = _mock_method(registry, "memory_config")
        memory_config.max_loaded_gb = 1000
        memory_config.auto_unload = False
        profile = ModelProfile(
            name="qwen3.6:latest",
            repo="qwen/qwen3.6",
            role="reasoning",
            estimated_memory_gb=1,
        )
        def get_model(name: str):
            return profile if name == profile.name else None

        _mock_method(registry, "get_model").side_effect = get_model
        router = ModelRouter(registry)
        tracker = UsageTracker(db_path=None)
        manager = ModelManager(registry=registry, router=router, tracker=tracker)
        _replace_method(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
        return manager

    def test_generate_decomposed_runs_each_step(self):
        manager = self._manager()
        _replace_method(manager, "_task_decomposition_config", MagicMock(side_effect=lambda: {
            "enabled": True,
            "min_steps": 2,
            "max_steps": 6,
        }))
        _replace_method(manager, "_self_consistency_config", MagicMock(side_effect=lambda: {"enabled": False}))

        call_count = 0

        def fake(_loaded: object, prompt: str, **_kwargs: object) -> str:
            nonlocal call_count
            call_count += 1
            if "분해하세요" in prompt:
                return '["저장소 분석", "변경 계획 수립"]'
            if "[이번 단계]" in prompt:
                return "checkpoint/recovery 결과"
            return "plain"

        _replace_method(manager, "_do_generate", MagicMock(side_effect=fake))
        out = manager.generate_decomposed(
            "코드 마이그레이션 워크플로를 설계하세요",
            "qwen3.6:latest",
        )
        # 1회 분해 + 2회 단계 실행 = 3회 호출.
        assert _mock_method(manager, "_do_generate").call_count == 3
        assert "1단계" in out and "2단계" in out
        assert out.count("checkpoint/recovery 결과") == 2

    def test_disabled_falls_back_to_plain_generate(self):
        manager = self._manager()
        _replace_method(manager, "_task_decomposition_config", MagicMock(side_effect=lambda: {"enabled": False}))
        _replace_method(manager, "_self_consistency_config", MagicMock(side_effect=lambda: {"enabled": False}))
        _replace_method(manager, "_do_generate", MagicMock(return_value="plain"))
        out = manager.generate_decomposed(
            "코드 마이그레이션 워크플로를 설계하세요",
            "qwen3.6:latest",
        )
        assert out == "plain"
        assert _mock_method(manager, "_do_generate").call_count == 1

    def test_forced_escalation_ignores_initial_enabled_gate(self):
        manager = self._manager()
        _replace_method(manager, "_task_decomposition_config", MagicMock(side_effect=lambda: {"enabled": False}))
        _replace_method(manager, "_self_consistency_config", MagicMock(side_effect=lambda: {"enabled": False}))

        def fake(_loaded: object, prompt: str, **_kwargs: object) -> str:
            if "분해하세요" in prompt:
                return '["저장소 분석", "변경 계획 수립"]'
            return "단계 결과"

        _replace_method(manager, "_do_generate", MagicMock(side_effect=fake))
        out = manager.generate_decomposed(
            "코드 마이그레이션 워크플로를 설계하세요",
            "qwen3.6:latest",
            force=True,
        )
        assert "1단계" in out
        assert _mock_method(manager, "_do_generate").call_count == 3

    def test_simple_task_skips_decomposition_cost(self):
        manager = self._manager()
        _replace_method(manager, "_task_decomposition_config", MagicMock(side_effect=lambda: {
            "enabled": True,
            "min_steps": 2,
            "max_steps": 6,
        }))
        _replace_method(manager, "_self_consistency_config", MagicMock(side_effect=lambda: {"enabled": False}))
        _replace_method(manager, "_do_generate", MagicMock(return_value="plain"))
        out = manager.generate_decomposed("안녕", "qwen3.6:latest")
        assert out == "plain"
        # 단순 작업은 게이트에서 즉시 폴백해 1회 호출만 발생한다.
        assert _mock_method(manager, "_do_generate").call_count == 1

    def test_later_steps_receive_previous_outputs(self):
        manager = self._manager()
        _replace_method(manager, "_task_decomposition_config", MagicMock(side_effect=lambda: {
            "enabled": True,
            "min_steps": 2,
            "max_steps": 6,
        }))
        _replace_method(manager, "_self_consistency_config", MagicMock(side_effect=lambda: {"enabled": False}))

        call_count = 0

        def fake(_loaded: object, prompt: str, **_kwargs: object) -> str:
            nonlocal call_count
            call_count += 1
            if "분해하세요" in prompt:
                return '["Command 핸들러 정의", "Event Store 구현"]'
            if "[1단계 결과]" not in prompt and "[이번 단계] Event Store" in prompt:
                raise AssertionError("2단계 프롬프트에 1단계 결과가 없다")
            return "STEP_OUTPUT_" + str(call_count)

        _replace_method(manager, "_do_generate", MagicMock(side_effect=fake))
        out = manager.generate_decomposed(
            "이벤트 소싱 CQRS 파이프라인을 설계하세요",
            "qwen3.6:latest",
        )
        second_prompt = cast(str, _mock_method(manager, "_do_generate").call_args_list[2].args[1])
        assert "[1단계 결과]" in second_prompt
        assert "STEP_OUTPUT_2" in second_prompt
        assert "STEP_OUTPUT_3" in out


class TestToolLoopIntegration:
    def _orch(self, config: object, model_name: str = "deepseek-r1:70b") -> MagicMock:
        from unittest.mock import AsyncMock, MagicMock

        orch = MagicMock()
        setattr(orch, "config", config)
        setattr(orch, "project_root", "/tmp")
        setattr(orch, "_skill_prompts_cache", "")
        setattr(orch, "_last_agent_output", "")
        _mock_method(orch, "_prepare_agent_prompt").return_value = (
            model_name,
            "sys",
            "tool",
            "skill",
            "prompt",
            [{"role": "user", "content": "hi"}],
        )
        manager = MagicMock()
        setattr(orch, "manager", manager)
        setattr(manager, "_registry", MagicMock())
        router = MagicMock()
        setattr(manager, "router", router)
        _mock_method(router, "get_combo").return_value = None
        _mock_method(manager, "is_loaded").return_value = True
        _mock_method(manager, "get_system_prompt").return_value = ""
        _mock_method(manager, "get_tool_prompt").return_value = ""
        _mock_method(orch, "_get_model_for_role").return_value = model_name
        ctx = MagicMock()
        tool_guardrail = MagicMock()
        setattr(ctx, "tool_guardrail", tool_guardrail)
        setattr(tool_guardrail, "reset", MagicMock())
        setattr(ctx, "cognitive_loop", MagicMock())
        quality_gate = MagicMock()
        setattr(ctx, "quality_gate", quality_gate)
        setattr(quality_gate, "reset", MagicMock())
        tool_executor = MagicMock()
        setattr(ctx, "tool_executor", tool_executor)
        setattr(tool_executor, "execute_async", AsyncMock(return_value="ok"))
        setattr(orch, "ctx", ctx)
        return orch

    def test_direct_response_uses_decomposed_when_enabled(self):
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = self._orch({"amplification": {"task_decomposition": {"enabled": True}}})
        manager = _mock_method(orch, "manager")
        _mock_method(manager, "generate_decomposed").return_value = "분해 증폭 결과"
        _mock_method(manager, "generate").return_value = "plain"
        _ = list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        _mock_method(manager, "generate_decomposed").assert_called_once()

    def test_direct_response_falls_back_when_disabled(self):
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        orch = self._orch({"amplification": {"task_decomposition": {"enabled": False}}})
        manager = _mock_method(orch, "manager")
        _mock_method(manager, "generate").return_value = "plain"
        _ = list(
            ToolLoopEngine(orch).run_loop(
                [{"role": "user", "content": "답만"}],
                "SELF",
                "chat",
                max_steps=1,
                direct_response=True,
            )
        )
        _mock_method(manager, "generate_decomposed").assert_not_called()
        # 폴백 경로는 초기 생성 + 품질 리비전 재생성으로 2회까지 호출될 수 있다.
        assert _mock_method(manager, "generate").call_count >= 1
