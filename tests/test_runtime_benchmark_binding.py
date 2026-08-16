from unittest.mock import MagicMock

from antigravity_k.api import dependencies
from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.task_runner import BackgroundTaskRunner


class _Orchestrator:
    vault_engine = None

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


def test_canonical_runtime_records_background_task_outcomes_for_calibration(tmp_path, monkeypatch):
    from antigravity_k.engine import task_runner

    manager = MagicMock()
    manager._registry._raw = {}
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
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    report = harness.task_report("qwen3.6:latest")
    assert len(report.outcomes) == 1
    assert report.task_success_rate == 1.0
    assert report.tool_accuracy == 1.0


def test_canonical_runtime_records_direct_task_outcomes_for_calibration(tmp_path, monkeypatch):
    from antigravity_k.engine import task_runner

    manager = MagicMock()
    manager._registry._raw = {}
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


def test_canonical_runtime_syncs_task_metrics_to_the_model_router(tmp_path, monkeypatch):
    from antigravity_k.engine import task_runner

    manager = MagicMock()
    manager._registry._raw = {}
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    harnesses: list[BenchmarkHarness] = []

    def create_harness(manager, task_calibration_updater):
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
    thread = runner._tasks[task_id]._thread
    assert thread is not None
    thread.join(timeout=2)

    assert len(harnesses) == 1
    manager.router.set_task_calibration.assert_called_once()
    model_name, metrics = manager.router.set_task_calibration.call_args.args
    assert model_name == "qwen3.6:latest"
    assert metrics.outcome_count == 1
    assert metrics.task_success_rate == 1.0
    assert metrics.tool_accuracy == 1.0
