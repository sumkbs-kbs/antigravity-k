import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.api import dependencies
from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.model_calibration import TaskBenchmarkMetrics
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.task_runner import BackgroundTask, BackgroundTaskRunner


class _Orchestrator:
    vault_engine: object = None

    def _get_model_for_role(self, role: str) -> str:
        assert role == "default"
        return "qwen3.6:latest"

    def get_model_for_role(self, role: str) -> str:
        return self._get_model_for_role(role)

    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ):
        assert messages[0]["role"] == "user"
        assert target_model == "qwen3.6:latest"
        assert max_steps == 15
        assert ephemeral_message is None
        return iter(['<tool_call>{"name":"read_file","arguments":{"file_path":"README.md"}}</tool_call>done'])


class _CalibrationMock(Protocol):
    def assert_called_once(self) -> None: ...

    @property
    def call_args(self) -> object: ...


class _RouterMock(Protocol):
    set_task_calibration: _CalibrationMock


def test_canonical_runtime_records_background_task_outcomes_for_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from antigravity_k.engine import task_runner

    manager = cast(ModelManager, MagicMock())
    registry = cast(object, getattr(manager, "_registry"))
    setattr(registry, "_raw", {})
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    monkeypatch.setattr(dependencies, "_agent_runtime", None)
    monkeypatch.setattr(dependencies, "_benchmark_harness", harness, raising=False)
    monkeypatch.setattr(dependencies, "get_orchestrator", _Orchestrator)
    monkeypatch.setattr(task_runner, "get_task_runner", lambda: runner)

    task_id = dependencies.get_agent_runtime().submit_task(
        "inspect README",
        context={"expected_tools": ["read_file"]},
    )
    tasks = cast(dict[str, BackgroundTask], getattr(runner, "_tasks"))
    thread = cast(threading.Thread | None, getattr(tasks[task_id], "_thread"))
    assert thread is not None
    thread.join(timeout=2)

    report = harness.task_report("qwen3.6:latest")
    assert len(report.outcomes) == 1
    assert report.task_success_rate == 1.0
    assert report.tool_accuracy == 1.0


def test_canonical_runtime_records_direct_task_outcomes_for_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from antigravity_k.engine import task_runner

    manager = cast(ModelManager, MagicMock())
    registry = cast(object, getattr(manager, "_registry"))
    setattr(registry, "_raw", {})
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    monkeypatch.setattr(dependencies, "_agent_runtime", None)
    monkeypatch.setattr(dependencies, "_benchmark_harness", harness, raising=False)
    monkeypatch.setattr(dependencies, "get_orchestrator", _Orchestrator)
    monkeypatch.setattr(task_runner, "get_task_runner", lambda: runner)

    tracked = dependencies.get_agent_runtime().start_stream(
        [{"role": "user", "content": "inspect README"}],
    )

    assert tracked.task_id is not None
    assert list(tracked.chunks)
    report = harness.task_report("qwen3.6:latest")
    assert len(report.outcomes) == 1
    assert report.outcomes[0].case_id == tracked.task_id
    assert report.task_success_rate == 1.0


def test_canonical_runtime_syncs_task_metrics_to_the_model_router(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from antigravity_k.engine import task_runner

    manager = cast(ModelManager, MagicMock())
    registry = cast(object, getattr(manager, "_registry"))
    setattr(registry, "_raw", {})
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    harnesses: list[BenchmarkHarness] = []

    def create_harness(
        manager: ModelManager,
        task_calibration_updater: Callable[[str, TaskBenchmarkMetrics | None], None] | None,
    ) -> BenchmarkHarness:
        harness = BenchmarkHarness(
            manager,
            db_path=tmp_path / "benchmark.json",
            task_calibration_updater=task_calibration_updater,
        )
        harnesses.append(harness)
        return harness

    monkeypatch.setattr(dependencies, "_agent_runtime", None)
    monkeypatch.setattr(dependencies, "_benchmark_harness", None)
    monkeypatch.setattr(dependencies, "BenchmarkHarness", create_harness)
    monkeypatch.setattr(dependencies, "get_model_manager", lambda: manager)
    monkeypatch.setattr(dependencies, "get_orchestrator", _Orchestrator)
    monkeypatch.setattr(task_runner, "get_task_runner", lambda: runner)

    task_id = dependencies.get_agent_runtime().submit_task(
        "inspect README",
        context={"benchmark_case_id": "tool-001", "expected_tools": ["read_file"]},
    )
    tasks = cast(dict[str, BackgroundTask], getattr(runner, "_tasks"))
    thread = cast(threading.Thread | None, getattr(tasks[task_id], "_thread"))
    assert thread is not None
    thread.join(timeout=2)

    assert len(harnesses) == 1
    router = cast(_RouterMock, cast(object, manager.router))
    router.set_task_calibration.assert_called_once()
    call_args = router.set_task_calibration.call_args
    assert call_args is not None
    call_values = cast(tuple[object, ...], getattr(call_args, "args"))
    model_name = cast(str, call_values[0])
    metrics = cast(TaskBenchmarkMetrics, call_values[1])
    assert model_name == "qwen3.6:latest"
    assert metrics.outcome_count == 1
    assert metrics.task_success_rate == 1.0
    assert metrics.tool_accuracy == 1.0
