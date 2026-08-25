"""테스트: 벤치마크 태스크 지표·임계값·보정 아티팩트.
=============================================
TaskOutcome/TaskBenchmarkReport의 순수 지표 계산과
BenchmarkHarness의 기록→조회→내보내기 흐름을 검증한다.
"""

import json
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.benchmark_harness import (
    BenchmarkHarness,
    TaskBenchmarkReport,
    TaskOutcome,
    TaskThresholds,
)


def _outcome(
    case_id: str = "case-1",
    target: str = "model-a",
    success: bool = True,
    expected: tuple[str, ...] = ("read_file",),
    used: tuple[str, ...] = ("read_file",),
    retry: int = 0,
    latency_ms: float = 100.0,
    tokens: int = 10,
    cost_usd: float = 0.01,
    calibration_eligible: bool = False,
) -> TaskOutcome:
    return TaskOutcome(
        case_id=case_id,
        target=target,
        success=success,
        completion_reason="done",
        expected_tools=expected,
        used_tools=used,
        retry_count=retry,
        latency_ms=latency_ms,
        tokens_in=tokens,
        tokens_out=tokens,
        cost_usd=cost_usd,
        calibration_eligible=calibration_eligible,
    )


# ─── TaskOutcome 지표 ─────────────────────────────────────────────


class TestTaskOutcomeMetrics:
    def test_full_overlap_scores_one(self):
        outcome = _outcome(expected=("a", "b"), used=("b", "a", "extra"))

        assert outcome.tool_recall == 1.0
        assert outcome.tool_precision == pytest.approx(2 / 3)
        assert outcome.tool_accuracy == outcome.tool_recall

    def test_empty_expected_used_nothing_scores_one(self):
        assert _outcome(expected=(), used=()).tool_recall == 1.0

    def test_empty_expected_but_used_scores_zero_recall(self):
        assert _outcome(expected=(), used=("a",)).tool_recall == 0.0

    def test_empty_used_with_expectations_scores_zero_precision(self):
        assert _outcome(expected=("a",), used=()).tool_precision == 0.0

    def test_negative_metrics_rejected(self):
        with pytest.raises(ValueError, match="retry_count"):
            _outcome(retry=-1)
        with pytest.raises(ValueError, match="non-negative"):
            TaskOutcome(
                case_id="c",
                target="m",
                success=True,
                completion_reason="done",
                latency_ms=-5.0,
            )


class TestTaskThresholds:
    def test_rate_out_of_bounds_rejected(self):
        with pytest.raises(ValueError, match="between 0 and 1"):
            TaskThresholds(min_success_rate=1.5)

    def test_negative_maximums_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            TaskThresholds(max_avg_latency_ms=-1)


# ─── TaskBenchmarkReport 집계 ─────────────────────────────────────


class TestTaskBenchmarkReport:
    def test_empty_report_returns_zeroes_and_no_outcomes_flag(self):
        report = TaskBenchmarkReport()

        assert report.task_success_rate == 0.0
        assert report.tool_accuracy == 0.0
        assert report.retry_rate == 0.0
        assert report.recovery_success_rate == 0.0
        assert report.avg_latency_ms == 0.0
        assert report.total_tokens == 0
        assert report.avg_cost_usd == 0.0
        assert report.error_count == 0
        assert report.check_thresholds(TaskThresholds()) == ("no_outcomes",)

    def test_aggregates_over_mixed_outcomes(self):
        good = _outcome("c1", latency_ms=100.0)
        retried_fail = _outcome("c2", success=False, retry=2, expected=("a", "b"), used=("a",), cost_usd=0.5)
        report = TaskBenchmarkReport(outcomes=[good, retried_fail])

        assert report.task_success_rate == pytest.approx(0.5)
        assert report.tool_accuracy == pytest.approx((1.0 + 0.5) / 2)
        assert report.retry_rate == pytest.approx(0.5)
        assert report.recovery_success_rate == 0.0
        assert report.avg_latency_ms == pytest.approx(100.0)
        assert report.total_tokens == 40
        assert report.total_cost_usd == pytest.approx(0.51)
        assert report.avg_cost_usd == pytest.approx(0.255)
        assert report.error_count == 1

    def test_recovery_success_rate_measures_rescued_tasks(self):
        rescued = _outcome("r1", success=True, retry=1)
        still_failing = _outcome("r2", success=False, retry=1)
        clean = _outcome("c1", success=True)

        report = TaskBenchmarkReport(outcomes=[rescued, still_failing, clean])

        assert report.recovery_success_rate == pytest.approx(0.5)

    def test_check_thresholds_reports_each_violation(self):
        thresholds = TaskThresholds(
            min_success_rate=0.9,
            min_tool_accuracy=0.9,
            max_retry_rate=0.1,
            max_avg_latency_ms=10.0,
            max_total_cost_usd=0.1,
        )
        weak = _outcome("w1", success=False, retry=3, latency_ms=500.0, cost_usd=0.4, used=("wrong_tool",))
        violations = TaskBenchmarkReport(outcomes=[weak]).check_thresholds(thresholds)

        assert set(violations) == {
            "success_rate",
            "tool_accuracy",
            "retry_rate",
            "avg_latency_ms",
            "total_cost_usd",
        }

    def test_check_thresholds_passing_report_has_no_failures(self):
        strong = _outcome("s1")
        assert TaskBenchmarkReport(outcomes=[strong]).check_thresholds(TaskThresholds()) == ()

    def test_to_dict_round_trips_outcomes(self):
        outcome = _outcome()
        payload = TaskBenchmarkReport(outcomes=[outcome]).to_dict()

        assert payload["outcomes"][0]["case_id"] == "case-1"
        assert payload["task_success_rate"] == 1.0


# ─── BenchmarkHarness 기록/보정/내보내기 ──────────────────────────


@pytest.fixture
def harness(tmp_path):
    captured: dict[str, object] = {}

    def update(model_name: str, metrics) -> None:
        captured[model_name] = metrics

    harness = BenchmarkHarness(
        model_manager=MagicMock(), db_path=tmp_path / "bench.db", task_calibration_updater=update
    )
    harness._captured = captured  # type: ignore[attr-defined]
    return harness


class TestHarnessTaskCalibration:
    def test_record_and_filtered_task_report(self, harness):
        harness.record_task_outcome(_outcome("c1", target="model-a"))
        harness.record_task_outcome(_outcome("c2", target="model-b", success=False))

        full = harness.task_report()
        only_b = harness.task_report(target="model-b")

        assert len(full.outcomes) == 2
        assert len(only_b.outcomes) == 1
        assert only_b.outcomes[0].success is False

    def test_calibration_updater_receives_metrics_for_eligible_outcomes(self, harness, tmp_path):
        eligible = _outcome("e1", calibration_eligible=True)
        ineligible = _outcome("n1", calibration_eligible=False)
        harness.record_task_outcome(eligible)
        harness.record_task_outcome(ineligible)

        metrics = harness._captured["model-a"]
        assert metrics is not None
        assert metrics.outcome_count == 1
        assert metrics.task_success_rate == 1.0

    def test_export_artifact_writes_metrics_json(self, harness, tmp_path):
        harness.record_task_outcome(_outcome("e1", calibration_eligible=True))

        destination = harness.export_task_calibration_artifact("model-a", path=tmp_path / "artifact.json")

        artifact = json.loads(destination.read_text(encoding="utf-8"))
        assert artifact["artifact_type"] == "task_benchmark"
        assert artifact["task_benchmark"]["outcome_count"] == 1

    def test_export_without_outcomes_raises_value_error(self, harness, tmp_path):
        with pytest.raises(ValueError, match="No task outcomes"):
            harness.export_task_calibration_artifact("ghost", path=tmp_path / "x.json")

    def test_comparison_table_mentions_header_when_empty(self, harness):
        table = harness.task_comparison_table()

        assert "Task Benchmark" in table or "결과가 없습니다" in table
