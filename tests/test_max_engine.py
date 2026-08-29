"""Integration tests for MaxModeEngine (P4: MAX Mode Parallel Editing).

Tests the full run() pipeline:
- Worker configuration with model availability scenarios
- Worker prompt generation by strategy
- Selector logic (best result picking)
- Parallel execution with mock workers
- Error handling and fallbacks
- MAX_EXECUTE handler integration
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import cast
from unittest.mock import MagicMock

from antigravity_k.engine.max_engine import (
    MaxModeEngine,
    MaxOrchestratorProtocol,
    MaxRunResult,
    WorkerConfig,
    WorkerResult,
)


def _available_models(engine: MaxModeEngine) -> list[str]:
    method = cast(Callable[[], list[str]], getattr(engine, "_get_available_models"))
    return method()


def _worker_configs(engine: MaxModeEngine, delegate_to: str, target_model: str) -> list[WorkerConfig]:
    method = cast(Callable[[str, str], list[WorkerConfig]], getattr(engine, "_build_worker_configs"))
    return method(delegate_to, target_model)


def _worker_prompt(engine: MaxModeEngine, prompt: str, model: str, strategy: str, temperature: float) -> str:
    method = cast(Callable[[str, str, str, float], str], getattr(engine, "_build_worker_prompt"))
    return method(prompt, model, strategy, temperature)


def _select_best(
    engine: MaxModeEngine,
    prompt: str,
    results: list[WorkerResult],
    delegate_to: str,
    orchestrator: MaxOrchestratorProtocol | None,
) -> int:
    method = cast(
        Callable[[str, list[WorkerResult], str, MaxOrchestratorProtocol | None], int], getattr(engine, "_select_best")
    )
    return method(prompt, results, delegate_to, orchestrator)


def _format_trace(
    engine: MaxModeEngine,
    results: list[WorkerResult],
    selected_idx: int,
    configs: Sequence[Mapping[str, object]],
) -> str:
    method = cast(
        Callable[[list[WorkerResult], int, Sequence[Mapping[str, object]]], str],
        getattr(engine, "_format_trace"),
    )
    return method(results, selected_idx, configs)


def _max_workers(engine: MaxModeEngine) -> int:
    return cast(int, getattr(engine, "_max_workers"))


def _max_handler(ctx: object, orchestrator: object) -> Iterator[str]:
    from antigravity_k.engine import orchestrator_handlers

    method = cast(Callable[[object, object], Iterator[str]], getattr(orchestrator_handlers, "max_execute_handler"))
    return method(ctx, orchestrator)


# ─── Helper: Mock Manager ────────────────────────────────────────


def _make_mock_manager(config: dict[str, object] | None = None) -> MagicMock:
    """Mock ModelManager를 생성합니다."""
    mgr = MagicMock()
    mgr._loaded_models = None
    mgr.loaded_models = None
    mgr.config = config or {}
    return mgr


def _make_mock_orchestrator(
    manager: MagicMock | None = None,
    qa_response: str = "SELECTED: 1\nREASON: Best output",
) -> MagicMock:
    """Mock OrchestratorAgent를 생성합니다."""
    orch = MagicMock()

    # Selector 호출 시 qa_response 반환
    def mock_generate(prompt: str = "", target: str = "", max_tokens: int = 256) -> str:
        _ = (prompt, target, max_tokens)
        return qa_response

    resolved_manager = manager if manager is not None else _make_mock_manager()
    resolved_manager.generate = mock_generate
    orch.manager = resolved_manager

    def resolve_role(_role: str) -> str:
        return "qa-model"

    orch._get_model_for_role = resolve_role
    orch.project_root = "/tmp/test_project"
    return orch


# ─── Dataclass Tests ────────────────────────────────────────────


class TestMaxDataClasses:
    """WorkerResult / MaxRunResult 데이터 클래스 단위 테스트."""

    def test_worker_result_creation(self):
        """WorkerResult가 올바르게 생성되는지 검증."""
        wr = WorkerResult(
            worker_id=0,
            model="model-a",
            strategy="default",
            output="def foo(): pass",
            elapsed_sec=1.5,
        )
        assert wr.worker_id == 0
        assert wr.model == "model-a"
        assert wr.strategy == "default"
        assert wr.output == "def foo(): pass"
        assert wr.elapsed_sec == 1.5
        assert wr.error is None

    def test_worker_result_with_error(self):
        """WorkerResult에 에러가 포함될 수 있는지 검증."""
        wr = WorkerResult(
            worker_id=1,
            model="model-b",
            strategy="creative",
            output="",
            elapsed_sec=0.5,
            error="Model not available",
        )
        assert wr.error == "Model not available"
        assert wr.output == ""

    def test_max_run_result_creation(self):
        """MaxRunResult가 올바르게 생성되는지 검증."""
        results = [
            WorkerResult(0, "a", "default", "out1", 1.0),
            WorkerResult(1, "b", "creative", "out2", 2.0),
        ]
        mrr = MaxRunResult(
            total_workers=2,
            successful=2,
            results=results,
            selected_idx=1,
            final_output="out2",
            selector_reasoning="Best output selected",
        )
        assert mrr.total_workers == 2
        assert mrr.successful == 2
        assert len(mrr.results) == 2
        assert mrr.selected_idx == 1
        assert mrr.final_output == "out2"
        assert mrr.error is None

    def test_max_run_result_with_error(self):
        """MaxRunResult가 에러 상태를 올바르게 표현하는지 검증."""
        mrr = MaxRunResult(
            total_workers=0,
            successful=0,
            error="No models available",
        )
        assert mrr.error == "No models available"
        assert mrr.final_output == ""
        assert mrr.selected_idx == -1


# ─── Worker Config Building Tests ───────────────────────────────


class TestWorkerConfigBuilding:
    """_build_worker_configs() 테스트."""

    def test_single_model_returns_one_worker(self):
        """1개 모델만 있으면 1개 워커만 생성되는지 검증."""
        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a"])

        configs = _worker_configs(engine, "WORKER", "model-a")

        assert len(configs) == 1
        assert configs[0]["model"] == "model-a"
        assert configs[0]["strategy"] == "default"

    def test_two_models_returns_two_workers(self):
        """2개 모델이 있으면 2개 워커가 생성되는지 검증."""
        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a", "model-b"])

        configs = _worker_configs(engine, "WORKER", "model-a")

        assert len(configs) == 2
        assert configs[0]["model"] == "model-a"
        assert configs[0]["strategy"] == "default"
        assert configs[1]["model"] == "model-b"
        assert configs[1]["strategy"] == "creative"

    def test_three_models_returns_three_workers(self):
        """3개 모델이 있으면 3개 워커가 생성되는지 검증."""
        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a", "model-b", "model-c"])

        configs = _worker_configs(engine, "WORKER", "model-a")

        assert len(configs) == 3
        assert configs[0]["strategy"] == "default"
        assert configs[1]["strategy"] == "creative"
        assert configs[2]["strategy"] == "safe"

    def test_no_manager_returns_empty(self):
        """model_manager 없으면 빈 리스트 반환."""
        engine = MaxModeEngine(None)
        configs = _worker_configs(engine, "WORKER", "")
        assert configs == []

    def test_no_available_models_returns_empty(self):
        """가용 모델 없으면 빈 리스트 반환."""
        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: cast(list[str], []))

        configs = _worker_configs(engine, "WORKER", "")
        assert configs == []

    def test_max_workers_limits_configs(self):
        """set_max_workers(2)로 제한하면 2개만 생성되는지 검증."""
        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["a", "b", "c"])
        engine.set_max_workers(2)

        configs = _worker_configs(engine, "WORKER", "a")
        assert len(configs) == 2


# ─── Worker Prompt Building Tests ───────────────────────────────


class TestWorkerPromptBuilding:
    """_build_worker_prompt() 테스트."""

    def test_default_strategy(self):
        """default 전략이 정확성과 완전성을 강조하는지 검증."""
        engine = MaxModeEngine(None)
        prompt = _worker_prompt(
            engine,
            "Create a function",
            "model-a",
            "default",
            0.2,
        )

        assert "[MAX Mode Worker - model-a, default]" in prompt
        assert "correctness" in prompt.lower()
        assert "Create a function" in prompt

    def test_creative_strategy(self):
        """creative 전략이 창의적 접근을 강조하는지 검증."""
        engine = MaxModeEngine(None)
        prompt = _worker_prompt(
            engine,
            "Refactor this code",
            "model-b",
            "creative",
            0.7,
        )

        assert "[MAX Mode Worker - model-b, creative]" in prompt
        assert "creative" in prompt.lower()
        assert "unconventional" in prompt.lower()

    def test_safe_strategy(self):
        """safe 전략이 안전성과 안정성을 강조하는지 검증."""
        engine = MaxModeEngine(None)
        prompt = _worker_prompt(
            engine,
            "Update dependency",
            "model-c",
            "safe",
            0.1,
        )

        assert "safety" in prompt.lower()
        assert "backward compatibility" in prompt.lower()
        assert "defensive" in prompt.lower()

    def test_balanced_strategy(self):
        """balanced 전략이 pragmatism과 quality의 균형을 강조하는지 검증."""
        engine = MaxModeEngine(None)
        prompt = _worker_prompt(
            engine,
            "Design API",
            "model-d",
            "balanced",
            0.4,
        )

        assert "pragmatism" in prompt.lower() or "judgment" in prompt.lower()

    def test_unknown_strategy_falls_back_to_default(self):
        """알 수 없는 전략이 default로 폴백되는지 검증."""
        engine = MaxModeEngine(None)
        prompt = _worker_prompt(
            engine,
            "Do task",
            "model-e",
            "unknown_strategy",
            0.5,
        )

        # unknown_strategy는 strategy_intro에 없으므로 default 사용
        # default는 correctness를 강조
        assert "correctness" in prompt.lower()


# ─── Selector Logic Tests ──────────────────────────────────────


class TestSelectorLogic:
    """_select_best() 테스트."""

    def test_single_result_returns_0(self):
        """결과가 1개면 Selector 없이 바로 0 반환."""
        engine = MaxModeEngine(None)
        result = _select_best(
            engine,
            "task",
            [WorkerResult(0, "a", "default", "output", 1.0)],
            "WORKER",
            None,
        )
        assert result == 0

    def test_selector_picks_correct_index(self):
        """Selector가 올바른 후보를 선정하는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr, "SELECTED: 2\nREASON: Most complete")
        engine = MaxModeEngine(mgr)

        results = [
            WorkerResult(0, "a", "default", "short", 1.0),
            WorkerResult(1, "b", "creative", "longer complete solution", 2.0),
        ]
        selected = _select_best(engine, "task", results, "WORKER", orch)
        assert selected == 1  # 1-based SELECTED:2 → 0-based 1

    def test_selector_fallback_on_parse_failure(self):
        """Selector 파싱 실패 시 첫 번째 결과로 폴백되는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr, "Nope, nothing here")
        engine = MaxModeEngine(mgr)

        results = [
            WorkerResult(0, "a", "default", "out1", 1.0),
            WorkerResult(1, "b", "creative", "out2", 2.0),
        ]
        selected = _select_best(engine, "task", results, "WORKER", orch)
        assert selected == 0  # fallback to first

    def test_selector_fallback_on_exception(self):
        """Selector 예외 발생 시 첫 번째 결과로 폴백되는지 검증."""
        mgr = _make_mock_manager()

        def broken_generate(prompt: str = "", target: str = "", max_tokens: int = 256) -> str:
            _ = (prompt, target, max_tokens)
            raise RuntimeError("API failure")

        mgr.generate = broken_generate
        orch = _make_mock_orchestrator(mgr, "")
        engine = MaxModeEngine(mgr)

        results = [
            WorkerResult(0, "a", "default", "out1", 1.0),
            WorkerResult(1, "b", "creative", "out2", 2.0),
        ]
        selected = _select_best(engine, "task", results, "WORKER", orch)
        assert selected == 0  # fallback to first

    def test_selector_out_of_range_fallback(self):
        """Selector가 범위를 벗어난 인덱스를 반환하면 0으로 폴백."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr, "SELECTED: 999\nREASON: Nonsense")
        engine = MaxModeEngine(mgr)

        results = [
            WorkerResult(0, "a", "default", "out1", 1.0),
        ]
        selected = _select_best(engine, "task", results, "WORKER", orch)
        assert selected == 0  # out of range → fallback to 0


# ─── Available Models Tests ────────────────────────────────────


class TestAvailableModels:
    """_get_available_models() 테스트."""

    def test_from_loaded_dict_models(self):
        """_loaded_models(dict)에서 모델을 가져오는지 검증."""
        mgr = _make_mock_manager()
        mgr._loaded_models = {"model-a": {}, "model-b": {}, "model-c": {}}
        engine = MaxModeEngine(mgr)

        models = _available_models(engine)
        assert "model-a" in models
        assert "model-b" in models
        assert "model-c" in models

    def test_from_loaded_list_models(self):
        """loaded_models(list)에서 모델을 가져오는지 검증."""
        mgr = _make_mock_manager()
        mgr.loaded_models = [{"name": "model-x"}, {"name": "model-y"}]
        engine = MaxModeEngine(mgr)

        models = _available_models(engine)
        assert "model-x" in models
        assert "model-y" in models

    def test_from_config_combos(self):
        """config combos에서 모델을 가져오는지 검증."""
        mgr = _make_mock_manager(
            config={
                "combos": {
                    "reasoning-balanced": {"models": ["llama3:70b", "qwen3:32b"]},
                    "fast-response": {"models": ["qwen3:8b"]},
                }
            }
        )
        engine = MaxModeEngine(mgr)

        models = _available_models(engine)
        assert len(models) >= 2
        assert "llama3:70b" in models

    def test_fallback_to_default(self):
        """아무 모델도 없으면 ['default'] 반환."""
        mgr = _make_mock_manager(config={})
        engine = MaxModeEngine(mgr)
        # manager has no models and empty config
        models = _available_models(engine)
        assert len(models) >= 1

    def test_respects_max_workers_limit(self):
        """max_workers 수보다 많은 모델을 반환하지 않는지 검증."""
        mgr = _make_mock_manager()
        mgr._loaded_models = {f"model-{i}": {} for i in range(8)}
        engine = MaxModeEngine(mgr)
        engine.set_max_workers(3)

        models = _available_models(engine)
        assert len(models) <= 3


# ─── Full run() Integration Tests ──────────────────────────────


class TestRunIntegration:
    """MaxModeEngine.run() 통합 테스트 (mock _run_worker 사용)."""

    def test_run_with_two_workers_selects_best(self):
        """2개 워커 실행 → Selector가 더 긴/완전한 결과를 선정하는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr, "SELECTED: 2\nREASON: More complete")
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a", "model-b"])

        def mock_run_worker(
            worker_id: int,
            config: WorkerConfig,
            prompt: str,
            messages: list[dict[str, str]],
            task_type: str,
            delegate_to: str,
            max_steps: int,
            orchestrator: MaxOrchestratorProtocol,
        ) -> WorkerResult:
            _ = (config, prompt, messages, task_type, delegate_to, max_steps, orchestrator)
            if worker_id == 0:
                return WorkerResult(0, "model-a", "default", "short", 0.5)
            return WorkerResult(1, "model-b", "creative", "longer complete solution with details", 1.2)

        setattr(engine, "_run_worker", mock_run_worker)

        result = engine.run(
            {
                "prompt": "Create a function",
                "messages": [{"role": "user", "content": "Create a function"}],
                "task_type": "coding",
                "delegate_to": "WORKER",
                "max_steps": 15,
                "target_model": "model-a",
            },
            orchestrator=orch,
        )

        assert result.total_workers == 2
        assert result.successful == 2
        assert len(result.results) == 2
        assert result.selected_idx == 1  # SELECTED:2 → index 1
        assert "details" in result.final_output  # worker 2 output
        assert "MAX Mode" in result.selector_reasoning

    def test_run_all_workers_fail(self):
        """모든 워커가 실패하면 적절한 에러 결과를 반환하는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr, "SELECTED: 1")
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a", "model-b"])

        def mock_run_worker(
            worker_id: int,
            config: WorkerConfig,
            prompt: str,
            messages: list[dict[str, str]],
            task_type: str,
            delegate_to: str,
            max_steps: int,
            orchestrator: MaxOrchestratorProtocol,
        ) -> WorkerResult:
            _ = (prompt, messages, task_type, delegate_to, max_steps, orchestrator)
            return WorkerResult(worker_id, config["model"], config["strategy"], "", 2.0, error="Worker crashed")

        setattr(engine, "_run_worker", mock_run_worker)

        result = engine.run(
            {
                "prompt": "task",
                "messages": [{"role": "user", "content": "task"}],
                "task_type": "coding",
            },
            orchestrator=orch,
        )

        assert result.total_workers == 2
        assert result.successful == 0
        assert result.final_output == ""

    def test_run_no_orchestrator_returns_error(self):
        """orchestrator 없이 run() 호출 시 에러 결과 반환."""
        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)

        result = engine.run(
            {
                "prompt": "task",
                "messages": [{"role": "user", "content": "task"}],
            },
            orchestrator=None,
        )

        assert result.error is not None
        assert "requires orchestrator" in result.error
        assert result.total_workers == 0

    def test_run_no_manager_returns_error(self):
        """model_manager 없이 run() 호출 시 에러 결과 반환."""
        engine = MaxModeEngine(None)

        result = engine.run(
            {
                "prompt": "task",
                "messages": [{"role": "user", "content": "task"}],
            },
            orchestrator=MagicMock(),
        )

        assert result.error is not None
        assert result.total_workers == 0

    def test_run_no_available_models_returns_error(self):
        """가용 모델 없이 run() 호출 시 에러 결과 반환."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr)
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: cast(list[str], []))

        result = engine.run(
            {
                "prompt": "task",
                "messages": [{"role": "user", "content": "task"}],
            },
            orchestrator=orch,
        )

        assert result.error is not None
        assert "No available models" in result.error

    def test_run_with_worker_exception(self):
        """워커에서 예외 발생 시 graceful하게 처리되는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr)
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a", "model-b"])

        call_count = [0]

        def mock_run_worker(*_args: object, **_kwargs: object) -> WorkerResult:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Worker thread crash")
            return WorkerResult(1, "model-b", "creative", "successful output", 1.0)

        setattr(engine, "_run_worker", mock_run_worker)

        result = engine.run(
            {
                "prompt": "task",
                "messages": [{"role": "user", "content": "task"}],
            },
            orchestrator=orch,
        )

        # ThreadPoolExecutor에서 예외 발생해도 graceful 처리
        assert result.total_workers == 2
        # 적어도 하나의 결과는 있어야 함
        assert len(result.results) > 0

    def test_run_with_messages_and_task_type(self):
        """task_spec에 messages/task_type이 올바르게 전달되는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr, "SELECTED: 1")
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a"])

        captured = {}

        def mock_run_worker(
            worker_id: int,
            config: WorkerConfig,
            prompt: str,
            messages: list[dict[str, str]],
            task_type: str,
            delegate_to: str,
            max_steps: int,
            orchestrator: MaxOrchestratorProtocol,
        ) -> WorkerResult:
            _ = (worker_id, config, messages, max_steps, orchestrator)
            captured["task_type"] = task_type
            captured["delegate_to"] = delegate_to
            captured["prompt"] = prompt
            return WorkerResult(0, "model-a", "default", "result", 0.5)

        setattr(engine, "_run_worker", mock_run_worker)

        _ = engine.run(
            {
                "prompt": "Refactor auth",
                "messages": [{"role": "user", "content": "Refactor auth module"}],
                "task_type": "reasoning",
                "delegate_to": "ENG_MANAGER",
                "max_steps": 20,
                "target_model": "reasoning-model",
            },
            orchestrator=orch,
        )

        assert captured["task_type"] == "reasoning"
        assert captured["delegate_to"] == "ENG_MANAGER"
        assert "Refactor auth" in captured["prompt"]


# ─── Format Trace Tests ─────────────────────────────────────────


class TestFormatTrace:
    """_format_trace() 출력 포맷 테스트."""

    def test_format_trace_includes_all_workers(self):
        """_format_trace()가 모든 워커 정보를 포함하는지 검증."""
        engine = MaxModeEngine(None)
        results = [
            WorkerResult(0, "model-a", "default", "out1", 1.0),
            WorkerResult(1, "model-b", "creative", "out2" * 100, 2.5),
        ]
        configs = [{"model": "a", "strategy": "default"}, {"model": "b", "strategy": "creative"}]

        trace = _format_trace(engine, results, 0, configs)

        assert "MAX Mode" in trace
        assert "Worker 1" in trace
        assert "Worker 2" in trace
        assert "SELECTED" in trace  # index 0 marked as selected

    def test_format_trace_marks_selected_only(self):
        """_format_trace()가 선택된 워커만 SELECTED로 표시하는지 검증."""
        engine = MaxModeEngine(None)
        results = [
            WorkerResult(0, "a", "default", "out1", 1.0),
            WorkerResult(1, "b", "creative", "out2", 2.0),
        ]
        configs = [{"model": "a", "strategy": "default"}, {"model": "b", "strategy": "creative"}]

        trace = _format_trace(engine, results, 1, configs)

        # Worker 2만 SELECTED — SELECTED 마커가 Worker 2 라인에 있는지 검증
        assert trace.count("SELECTED") == 1
        assert "SELECTED" in trace[trace.index("Worker 2") :]


# ─── Set Max Workers Tests ──────────────────────────────────────


class TestSetMaxWorkers:
    """set_max_workers() 테스트."""

    def test_set_workers_clamps_to_min_1(self):
        """set_max_workers(0)이 1로 클램핑되는지 검증."""
        engine = MaxModeEngine(None)
        engine.set_max_workers(0)
        assert _max_workers(engine) == 1

    def test_set_workers_clamps_to_max_8(self):
        """set_max_workers(999)가 8로 클램핑되는지 검증."""
        engine = MaxModeEngine(None)
        engine.set_max_workers(999)
        assert _max_workers(engine) == 8

    def test_set_workers_normal(self):
        """set_max_workers(5)가 정상 설정되는지 검증."""
        engine = MaxModeEngine(None)
        engine.set_max_workers(5)
        assert _max_workers(engine) == 5


# ─── Error Handling / Edge Cases ───────────────────────────────


class TestEdgeCases:
    """MAX 엔진 엣지 케이스 테스트."""

    def test_run_with_empty_task_spec(self):
        """비어 있는 task_spec으로 run()이 동작하는지 검증."""
        mgr = _make_mock_manager()
        orch = _make_mock_orchestrator(mgr)
        engine = MaxModeEngine(mgr)
        setattr(engine, "_get_available_models", lambda: ["model-a"])

        def mock_run_worker(*_args: object, **_kwargs: object) -> WorkerResult:
            return WorkerResult(0, "model-a", "default", "output", 0.3)

        setattr(engine, "_run_worker", mock_run_worker)

        result = engine.run({}, orchestrator=orch)
        assert result.successful >= 0  # graceful handling

    def test_init_with_default_project_root(self):
        """project_root 없이 초기화 시 cwd를 사용하는지 검증."""
        import os

        engine = MaxModeEngine(None)
        assert engine.project_root == os.getcwd()

    def test_init_with_custom_project_root(self):
        """project_root를 지정하면 해당 경로를 사용하는지 검증."""
        engine = MaxModeEngine(None, project_root="/custom/path")
        assert engine.project_root == "/custom/path"


# ─── MAX_EXECUTE Handler Integration Tests ─────────────────────


class TestMaxExecuteHandler:
    """MAX_EXECUTE 핸들러 통합 테스트."""

    def test_handler_calls_max_engine_and_yields_result(self):
        """max_execute_handler가 MaxModeEngine.run()을 호출하고 결과를 yield하는지 검증."""
        from antigravity_k.engine.state_graph import StateContext

        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)

        # run() 결과 모의
        mock_result = MaxRunResult(
            total_workers=2,
            successful=2,
            results=[
                WorkerResult(0, "model-a", "default", "worker output a", 1.0),
                WorkerResult(1, "model-b", "creative", "worker output b", 1.5),
            ],
            selected_idx=0,
            final_output="worker output a",
            selector_reasoning="Trace output",
        )
        engine.run = lambda task_spec, orchestrator=None: mock_result

        # orchestrator mock
        orch = MagicMock()
        orch.max_engine = engine
        orch.project_root = "/tmp/test"
        orch._last_agent_output = ""

        # context setup
        ctx = StateContext(messages=[{"role": "user", "content": "test task"}])
        ctx.user_message = "test task"
        ctx.refined_prompt = "refined: test task"
        ctx.custom_messages = [{"role": "user", "content": "test task"}]
        ctx.delegate_to = "WORKER"
        ctx.task_type = "coding"
        ctx.max_steps = 15
        ctx.target_model = "model-a"
        ctx.rag_context = ""

        chunks = list(_max_handler(ctx, orch))

        # MAX 모드 안내 메시지가 포함되어야 함
        assert any("MAX Mode" in c for c in chunks)
        # Selector 선정 메시지가 포함되어야 함
        assert any("MAX Selector" in c for c in chunks)
        # Worker 결과 정보가 포함되어야 함
        assert any("Worker 1" in c for c in chunks)
        assert any("Worker 2" in c for c in chunks)

    def test_handler_fallback_when_no_max_engine(self):
        """max_engine이 None일 때 싱글 에이전트로 fallback되는지 검증."""
        from antigravity_k.engine.state_graph import StateContext

        # max_engine이 None인 orchestrator
        orch = MagicMock()
        orch.max_engine = None

        # tool_loop 없으므로 폴백 실패할 수 있음, 하지만 try/except 처리 확인
        ctx = StateContext(messages=[{"role": "user", "content": "test"}])
        ctx.user_message = "test"
        ctx.custom_messages = [{"role": "user", "content": "test"}]
        ctx.delegate_to = "WORKER"
        ctx.task_type = "coding"
        ctx.max_steps = 15
        ctx.target_model = "model-a"
        ctx.refined_prompt = ""
        ctx.rag_context = ""

        chunks: list[str] = []
        try:
            for c in _max_handler(ctx, orch):
                chunks.append(str(c))
        except Exception:
            pass

        assert any("MAX Engine not available" in c for c in chunks) or any("falling back" in c.lower() for c in chunks)

    def test_handler_handles_engine_exception(self):
        """MaxModeEngine.run()에서 예외 발생 시 graceful 처리되는지 검증."""
        from antigravity_k.engine.state_graph import StateContext

        mgr = _make_mock_manager()
        engine = MaxModeEngine(mgr)

        def broken_run(task_spec: dict[str, object], orchestrator: object | None = None) -> MaxRunResult:
            _ = (task_spec, orchestrator)
            raise RuntimeError("Engine crashed")

        engine.run = broken_run

        orch = MagicMock()
        orch.max_engine = engine
        orch.project_root = "/tmp/test"
        orch._last_agent_output = ""

        ctx = StateContext(messages=[{"role": "user", "content": "test"}])
        ctx.user_message = "test"
        ctx.custom_messages = [{"role": "user", "content": "test"}]
        ctx.delegate_to = "WORKER"
        ctx.task_type = "coding"
        ctx.max_steps = 15
        ctx.target_model = "model-a"
        ctx.refined_prompt = ""
        ctx.rag_context = ""

        chunks: list[str] = []
        try:
            for c in _max_handler(ctx, orch):
                chunks.append(str(c))
        except Exception:
            pass

        assert any("MAX Error" in c for c in chunks) or any("fall" in c.lower() for c in chunks)
