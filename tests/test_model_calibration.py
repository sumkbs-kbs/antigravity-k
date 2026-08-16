import json
from pathlib import Path
from unittest.mock import MagicMock

from antigravity_k.engine.model_calibration import (
    ModelQualityCalibrationConfig,
    ModelQualityCalibrationStore,
    TaskBenchmarkMetrics,
)
from antigravity_k.engine.model_registry import ModelProfile
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy


def _write_benchmark_artifact(path: Path, model: str, scores: tuple[float, ...]) -> None:
    payload = {
        "model": model,
        "results": [
            {
                "case_id": f"case-{index}",
                "quality_score": score,
                "benchmark_score": score,
                "quality_grade": "excellent" if score >= 0.9 else "fail",
                "error": "",
            }
            for index, score in enumerate(scores, start=1)
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_calibration_rejects_measured_model_below_quality_threshold(tmp_path: Path) -> None:
    artifact_path = tmp_path / "underperforming.json"
    _write_benchmark_artifact(artifact_path, "underperforming-30b", (0.4, 0.5))
    config = ModelQualityCalibrationConfig(
        enabled=True,
        artifact_paths=(artifact_path,),
        min_mean_benchmark_score=0.8,
        min_min_benchmark_score=0.7,
        min_excellent_rate=0.8,
    )

    store = ModelQualityCalibrationStore.from_config(config, tmp_path)

    assert store.is_eligible("underperforming-30b") is False
    assert store.is_eligible("unmeasured-model") is True


def test_calibration_uses_repeat_minimum_instead_of_only_latest_result(tmp_path: Path) -> None:
    artifact_path = tmp_path / "unstable.json"
    artifact_path.write_text(
        json.dumps(
            {
                "model": "unstable-30b",
                "results": [
                    {
                        "case_id": "latest-success",
                        "quality_score": 1.0,
                        "benchmark_score": 1.0,
                        "quality_grade": "excellent",
                        "error": "",
                    }
                ],
                "stability": {
                    "repeat_count": 2,
                    "result_count": 4,
                    "mean_benchmark_score": 0.85,
                    "min_benchmark_score": 0.4,
                    "excellent_rate": 0.75,
                    "runs": [{"error_count": 0}, {"error_count": 0}],
                },
            }
        ),
        encoding="utf-8",
    )
    config = ModelQualityCalibrationConfig(enabled=True, artifact_paths=(artifact_path,))

    store = ModelQualityCalibrationStore.from_config(config, tmp_path)

    assert store.is_eligible("unstable-30b") is False
    assert store.summaries()[0].case_count == 4


def test_calibration_rejects_prior_repeat_error_when_latest_result_succeeds(tmp_path: Path) -> None:
    artifact_path = tmp_path / "prior-error.json"
    artifact_path.write_text(
        json.dumps(
            {
                "model": "flaky-30b",
                "results": [
                    {
                        "case_id": "latest-success",
                        "quality_score": 1.0,
                        "benchmark_score": 1.0,
                        "quality_grade": "excellent",
                        "error": "",
                    }
                ],
                "stability": {
                    "repeat_count": 2,
                    "result_count": 4,
                    "mean_benchmark_score": 0.95,
                    "min_benchmark_score": 0.9,
                    "excellent_rate": 1.0,
                    "runs": [{"error_count": 1}, {"error_count": 0}],
                },
            }
        ),
        encoding="utf-8",
    )
    config = ModelQualityCalibrationConfig(enabled=True, artifact_paths=(artifact_path,))

    store = ModelQualityCalibrationStore.from_config(config, tmp_path)

    assert store.is_eligible("flaky-30b") is False
    assert store.summaries()[0].error_count == 1


def test_calibration_rejects_incomplete_repeat_even_with_high_case_success_rate(tmp_path: Path) -> None:
    artifact_path = tmp_path / "partially-excellent.json"
    artifact_path.write_text(
        json.dumps(
            {
                "model": "partially-excellent-30b",
                "results": [
                    {
                        "case_id": "latest-success",
                        "quality_score": 1.0,
                        "benchmark_score": 1.0,
                        "quality_grade": "excellent",
                        "error": "",
                    }
                ],
                "stability": {
                    "repeat_count": 2,
                    "result_count": 10,
                    "mean_benchmark_score": 0.95,
                    "min_benchmark_score": 0.9,
                    "excellent_rate": 0.95,
                    "all_excellent_run_rate": 0.5,
                    "runs": [{"error_count": 0}, {"error_count": 0}],
                },
            }
        ),
        encoding="utf-8",
    )
    config = ModelQualityCalibrationConfig(
        enabled=True,
        artifact_paths=(artifact_path,),
        min_all_excellent_run_rate=0.8,
    )

    store = ModelQualityCalibrationStore.from_config(config, tmp_path)

    assert store.is_eligible("partially-excellent-30b") is False


def test_calibration_rejects_model_with_measured_task_quality_below_threshold(tmp_path: Path) -> None:
    artifact_path = tmp_path / "task-underperforming.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_type": "task_benchmark",
                "model": "task-underperforming-30b",
                "task_benchmark": {
                    "outcome_count": 4,
                    "task_success_rate": 0.5,
                    "tool_accuracy": 0.5,
                    "retry_rate": 0.75,
                    "avg_latency_ms": 1000.0,
                    "avg_cost_usd": 0.01,
                    "error_count": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    config = ModelQualityCalibrationConfig(
        enabled=True,
        artifact_paths=(artifact_path,),
        min_task_outcome_count=3,
        min_task_success_rate=0.8,
        min_task_tool_accuracy=0.8,
        max_task_retry_rate=0.5,
    )

    store = ModelQualityCalibrationStore.from_config(config, tmp_path)

    assert store.is_eligible("task-underperforming-30b") is False
    summary = store.summaries()[0]
    assert summary.task_outcome_count == 4
    assert summary.task_success_rate == 0.5


def test_router_status_exposes_operational_task_calibration_metrics(tmp_path: Path) -> None:
    artifact_path = tmp_path / "task-qwen.json"
    artifact_path.write_text(
        json.dumps(
            {
                "artifact_type": "task_benchmark",
                "model": "qwen3.6:latest",
                "task_benchmark": {
                    "outcome_count": 3,
                    "task_success_rate": 1.0,
                    "tool_accuracy": 1.0,
                    "retry_rate": 0.0,
                    "avg_latency_ms": 1000.0,
                    "avg_cost_usd": 0.01,
                    "error_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    registry = MagicMock()
    registry._config_path = str(tmp_path / "config.yaml")
    registry._raw = {
        "router": {
            "quality_calibration": {
                "enabled": True,
                "artifact_paths": ["task-qwen.json"],
                "min_task_outcome_count": 3,
            }
        }
    }
    qwen = ModelProfile(
        name="qwen3.6:latest",
        repo="qwen3.6:latest",
        role="reasoning",
        parameter_count_b=36.0,
    )
    registry.get_model.side_effect = lambda name: qwen if name == qwen.name else None
    registry.list_models.return_value = [qwen]

    status = ModelRouter(registry).status()

    assert status["quality_calibration"]["operational_metrics"] == [
        {
            "model": "qwen3.6:latest",
            "outcome_count": 3,
            "task_success_rate": 1.0,
            "tool_accuracy": 1.0,
            "retry_rate": 0.0,
        }
    ]


def test_router_prefers_quality_calibrated_qwen_when_first_model_fails_threshold(tmp_path: Path) -> None:
    _write_benchmark_artifact(tmp_path / "underperforming.json", "underperforming-30b", (0.4, 0.5))
    _write_benchmark_artifact(tmp_path / "qwen.json", "qwen3.6:latest", (0.95, 1.0))
    registry = MagicMock()
    registry._config_path = str(tmp_path / "config.yaml")
    registry._raw = {
        "router": {
            "quality_calibration": {
                "enabled": True,
                "artifact_paths": ["underperforming.json", "qwen.json"],
                "min_mean_benchmark_score": 0.8,
                "min_min_benchmark_score": 0.7,
                "min_excellent_rate": 0.8,
            }
        }
    }
    profiles = {
        "underperforming-30b": ModelProfile(
            name="underperforming-30b",
            repo="underperforming-30b",
            role="reasoning",
            parameter_count_b=30.0,
        ),
        "qwen3.6:latest": ModelProfile(
            name="qwen3.6:latest",
            repo="qwen3.6:latest",
            role="reasoning",
            parameter_count_b=36.0,
        ),
    }
    registry.get_model.side_effect = profiles.get
    registry.list_models.return_value = list(profiles.values())
    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="quality-first",
            models=["underperforming-30b", "qwen3.6:latest"],
            strategy=RouteStrategy.FALLBACK,
        )
    )

    selected = router.route("quality-first")

    assert selected.name == "qwen3.6:latest"
    assert router.status()["quality_calibration"]["eligible_models"] == ["qwen3.6:latest"]


def test_router_uses_observed_task_metrics_without_a_manual_calibration_export(tmp_path: Path) -> None:
    registry = MagicMock()
    registry._config_path = str(tmp_path / "config.yaml")
    registry._raw = {
        "router": {
            "quality_calibration": {
                "enabled": True,
                "min_task_outcome_count": 3,
                "min_task_success_rate": 0.8,
                "min_task_tool_accuracy": 0.8,
                "max_task_retry_rate": 0.5,
            }
        }
    }
    profiles = {
        "underperforming-30b": ModelProfile(
            name="underperforming-30b",
            repo="underperforming-30b",
            role="reasoning",
            parameter_count_b=30.0,
        ),
        "qwen3.6:latest": ModelProfile(
            name="qwen3.6:latest",
            repo="qwen3.6:latest",
            role="reasoning",
            parameter_count_b=36.0,
        ),
    }
    registry.get_model.side_effect = profiles.get
    registry.list_models.return_value = list(profiles.values())
    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="observed-quality-first",
            models=["underperforming-30b", "qwen3.6:latest"],
            strategy=RouteStrategy.FALLBACK,
        )
    )
    router.set_task_calibration(
        "underperforming-30b",
        TaskBenchmarkMetrics(
            outcome_count=3,
            task_success_rate=0.5,
            tool_accuracy=1.0,
            retry_rate=0.0,
            avg_latency_ms=100.0,
            avg_cost_usd=0.0,
            error_count=1,
        ),
    )
    router.set_task_calibration(
        "qwen3.6:latest",
        TaskBenchmarkMetrics(
            outcome_count=3,
            task_success_rate=1.0,
            tool_accuracy=1.0,
            retry_rate=0.0,
            avg_latency_ms=100.0,
            avg_cost_usd=0.0,
            error_count=0,
        ),
    )

    selected = router.route("observed-quality-first")

    assert selected.name == "qwen3.6:latest"
    assert router.status()["quality_calibration"]["operational_metrics"] == [
        {
            "model": "qwen3.6:latest",
            "outcome_count": 3,
            "task_success_rate": 1.0,
            "tool_accuracy": 1.0,
            "retry_rate": 0.0,
        },
        {
            "model": "underperforming-30b",
            "outcome_count": 3,
            "task_success_rate": 0.5,
            "tool_accuracy": 1.0,
            "retry_rate": 0.0,
        },
    ]


def test_router_keeps_qwen_routable_while_observed_task_metrics_warm_up(tmp_path: Path) -> None:
    registry = MagicMock()
    registry._config_path = str(tmp_path / "config.yaml")
    registry._raw = {
        "router": {
            "quality_calibration": {
                "enabled": True,
                "min_task_outcome_count": 3,
                "min_task_success_rate": 0.8,
                "min_task_tool_accuracy": 0.8,
                "max_task_retry_rate": 0.5,
            }
        }
    }
    qwen = ModelProfile(
        name="qwen3.6:latest",
        repo="qwen3.6:latest",
        role="reasoning",
        parameter_count_b=36.0,
    )
    registry.get_model.side_effect = lambda name: qwen if name == qwen.name else None
    registry.list_models.return_value = [qwen]
    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="qwen-observed-warmup",
            models=[qwen.name],
            strategy=RouteStrategy.FALLBACK,
        )
    )
    router.set_task_calibration(
        qwen.name,
        TaskBenchmarkMetrics(
            outcome_count=1,
            task_success_rate=1.0,
            tool_accuracy=1.0,
            retry_rate=0.0,
            avg_latency_ms=100.0,
            avg_cost_usd=0.0,
            error_count=0,
        ),
    )

    selected = router.route("qwen-observed-warmup")

    assert selected.name == qwen.name
    assert router.status()["quality_calibration"]["operational_metrics"][0]["outcome_count"] == 1
