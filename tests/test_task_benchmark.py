import json
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.benchmark_harness import (
    BenchmarkHarness,
    TaskBenchmarkReport,
    TaskOutcome,
    TaskThresholds,
)
from antigravity_k.engine.task_runner import BackgroundTaskRunner


def test_task_outcome_tracks_tool_accuracy_and_execution_cost():
    outcome = TaskOutcome(
        case_id="task-001",
        target="qwen3.6:latest",
        success=True,
        completion_reason="done",
        expected_tools=("read_file", "write_file"),
        used_tools=("read_file", "read_file"),
        retry_count=1,
        latency_ms=1200.0,
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.02,
    )

    assert outcome.tool_recall == 0.5
    assert outcome.tool_precision == 1.0
    assert outcome.tool_accuracy == 0.5
    assert outcome.retry_count == 1


def test_task_benchmark_report_aggregates_success_retries_latency_tokens_and_cost():
    report = TaskBenchmarkReport(
        outcomes=[
            TaskOutcome(
                case_id="task-001",
                target="local",
                success=True,
                completion_reason="done",
                expected_tools=("read_file",),
                used_tools=("read_file",),
                retry_count=0,
                latency_ms=100.0,
                tokens_in=100,
                tokens_out=40,
                cost_usd=0.0,
            ),
            TaskOutcome(
                case_id="task-002",
                target="local",
                success=False,
                completion_reason="timeout",
                expected_tools=("read_file",),
                used_tools=(),
                retry_count=2,
                latency_ms=300.0,
                tokens_in=200,
                tokens_out=80,
                cost_usd=0.01,
            ),
        ],
    )

    assert report.task_success_rate == 0.5
    assert report.tool_accuracy == 0.5
    assert report.retry_rate == 0.5
    assert report.avg_latency_ms == 200.0
    assert report.total_tokens == 420
    assert report.total_cost_usd == 0.01
    assert report.to_dict()["task_success_rate"] == 0.5


def test_task_benchmark_report_recovery_success_rate_is_retry_then_succeed_fraction():
    # Given: two tasks needed a retry — one recovered, one did not. A third needed none.
    report = TaskBenchmarkReport(
        outcomes=[
            TaskOutcome("a", "local", True, "done", retry_count=2, latency_ms=100.0),
            TaskOutcome("b", "local", False, "failed", retry_count=3, latency_ms=200.0),
            TaskOutcome("c", "local", True, "done", retry_count=0, latency_ms=50.0),
        ],
    )

    # When / Then: recovery rate is the fraction of retried tasks that ultimately
    # succeeded (1 of 2), distinct from overall success rate and raw retry rate.
    assert report.recovery_success_rate == 0.5
    assert report.to_dict()["recovery_success_rate"] == 0.5


def test_harness_persists_and_reloads_task_outcomes(tmp_path):
    manager = MagicMock()
    manager._registry._raw = {}
    db_path = tmp_path / "benchmark.json"
    outcome = TaskOutcome(
        case_id="task-001",
        target="local",
        success=True,
        completion_reason="done",
    )

    harness = BenchmarkHarness(manager, db_path=db_path)
    harness.record_task_outcome(outcome)
    restored = BenchmarkHarness(manager, db_path=db_path)

    assert restored.task_report().outcomes == [outcome]
    assert restored.task_report().task_success_rate == 1.0


def test_task_comparison_table_exposes_operational_metrics(tmp_path):
    manager = MagicMock()
    manager._registry._raw = {}
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")
    harness.record_task_outcome(
        TaskOutcome(
            case_id="task-001",
            target="local",
            success=True,
            completion_reason="done",
            retry_count=1,
            latency_ms=120.0,
            tokens_in=10,
            tokens_out=20,
            cost_usd=0.03,
        ),
    )

    table = harness.task_comparison_table()

    assert "Task Benchmark" in table
    assert "성공률" in table
    assert "재시도율" in table
    assert "비용" in table


def test_harness_binds_to_task_runner_outcome_sink(tmp_path):
    manager = MagicMock()
    manager._registry._raw = {}
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    assert harness.bind_task_runner(runner) is runner
    assert runner.outcome_recorder is not None
    runner.outcome_recorder(
        TaskOutcome(
            case_id="task-001",
            target="local",
            success=True,
            completion_reason="done",
        ),
    )

    assert harness.task_report().task_success_rate == 1.0


def test_harness_binds_to_tool_loop_outcome_sink(tmp_path):
    manager = MagicMock()
    manager._registry._raw = {}
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")
    tool_loop = MagicMock()

    assert harness.bind_tool_loop(tool_loop) is tool_loop
    tool_loop.outcome_recorder(
        TaskOutcome(
            case_id="loop-001",
            target="local",
            success=True,
            completion_reason="done",
        ),
    )

    assert harness.task_report().task_success_rate == 1.0


def test_harness_calibrates_only_explicit_benchmark_outcomes(tmp_path):
    updates = []
    manager = MagicMock()
    manager._registry._raw = {}
    harness = BenchmarkHarness(
        manager,
        db_path=tmp_path / "benchmark.json",
        task_calibration_updater=lambda model, metrics: updates.append((model, metrics)),
    )

    harness.record_task_outcome(
        TaskOutcome(
            case_id="task-ad-hoc",
            target="qwen3.6:latest",
            success=False,
            completion_reason="cancelled",
            calibration_eligible=False,
        ),
    )

    assert updates[-1] == ("qwen3.6:latest", None)

    harness.record_task_outcome(
        TaskOutcome(
            case_id="sim-001",
            target="qwen3.6:latest",
            success=True,
            completion_reason="done",
            calibration_eligible=True,
        ),
    )

    model_name, metrics = updates[-1]
    assert model_name == "qwen3.6:latest"
    assert metrics is not None
    assert metrics.outcome_count == 1
    assert metrics.task_success_rate == 1.0


def test_task_report_thresholds_pass_and_expose_failures():
    report = TaskBenchmarkReport(
        outcomes=[
            TaskOutcome(
                case_id="task-001",
                target="local",
                success=True,
                completion_reason="done",
                expected_tools=("read_file",),
                used_tools=("read_file",),
                latency_ms=100.0,
            ),
        ],
    )
    thresholds = TaskThresholds(
        min_success_rate=1.0,
        min_tool_accuracy=1.0,
        max_retry_rate=0.0,
        max_avg_latency_ms=200.0,
        max_total_cost_usd=0.1,
    )

    assert report.check_thresholds(thresholds) == ()
    assert TaskBenchmarkReport().check_thresholds(thresholds) == ("no_outcomes",)


def test_harness_exports_model_scoped_task_calibration_artifact(tmp_path):
    manager = MagicMock()
    manager._registry._raw = {}
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")
    harness.record_task_outcome(
        TaskOutcome(
            case_id="task-001",
            target="qwen3.6:latest",
            success=True,
            completion_reason="done",
            expected_tools=("read_file",),
            used_tools=("read_file",),
            latency_ms=120.0,
            cost_usd=0.01,
            calibration_eligible=True,
        ),
    )
    artifact_path = tmp_path / "qwen-task-calibration.json"

    result_path = harness.export_task_calibration_artifact("qwen3.6:latest", artifact_path)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["model"] == "qwen3.6:latest"
    assert payload["task_benchmark"]["outcome_count"] == 1
    assert payload["task_benchmark"]["task_success_rate"] == 1.0
    assert payload["task_benchmark"]["tool_accuracy"] == 1.0
    assert payload["task_benchmark"]["retry_rate"] == 0.0


def test_harness_rejects_task_calibration_export_without_target_outcomes(tmp_path):
    manager = MagicMock()
    manager._registry._raw = {}
    harness = BenchmarkHarness(manager, db_path=tmp_path / "benchmark.json")

    with pytest.raises(ValueError, match="task outcomes"):
        harness.export_task_calibration_artifact("qwen3.6:latest", tmp_path / "missing.json")
