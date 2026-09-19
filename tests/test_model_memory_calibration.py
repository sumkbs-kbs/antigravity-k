from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from antigravity_k.engine.model_memory_calibration import (
    MemoryMeasurement,
    MemoryMeasurementOutcome,
    ModelMemoryArtifactError,
    ModelMemoryCalibrationArtifact,
    load_model_memory_budget,
)


def _measurement(
    context_tokens: int,
    kv_cache_bytes: int,
    outcome: MemoryMeasurementOutcome,
) -> MemoryMeasurement:
    return MemoryMeasurement(
        context_tokens=context_tokens,
        kv_cache_bytes=kv_cache_bytes,
        peak_memory_bytes=kv_cache_bytes * 4,
        outcome=outcome,
    )


def test_calibration_applies_headroom_to_highest_successful_measurement() -> None:
    artifact = ModelMemoryCalibrationArtifact(
        artifact_type="model_memory_calibration",
        schema_version=1,
        model="qwen3.6:latest",
        backend="ollama",
        source_sha256="a" * 64,
        headroom_ratio=Decimal("0.2"),
        measurements=(
            _measurement(16_000, 1_000_000, MemoryMeasurementOutcome.SUCCESS),
            _measurement(32_000, 2_000_000, MemoryMeasurementOutcome.SUCCESS),
            _measurement(48_000, 3_000_000, MemoryMeasurementOutcome.OOM),
        ),
    )

    budget = artifact.safe_budget()

    assert budget.context_token_limit == 25_600
    assert budget.kv_cache_byte_limit == 1_600_000


def test_calibration_rejects_oom_below_a_successful_context() -> None:
    with pytest.raises(ValidationError):
        _ = ModelMemoryCalibrationArtifact(
            artifact_type="model_memory_calibration",
            schema_version=1,
            model="qwen3.6:latest",
            backend="ollama",
            source_sha256="a" * 64,
            headroom_ratio=Decimal("0.2"),
            measurements=(
                _measurement(16_000, 1_000_000, MemoryMeasurementOutcome.OOM),
                _measurement(32_000, 2_000_000, MemoryMeasurementOutcome.SUCCESS),
            ),
        )


def test_loader_reports_the_exact_missing_artifact_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(ModelMemoryArtifactError) as captured:
        _ = load_model_memory_budget((missing_path,), "qwen3.6:latest")

    assert captured.value.path == missing_path


def test_loader_uses_the_most_conservative_budget_across_artifacts(tmp_path: Path) -> None:
    paths: list[Path] = []
    for index, headroom in enumerate((Decimal("0.2"), Decimal("0.5"))):
        artifact = ModelMemoryCalibrationArtifact(
            artifact_type="model_memory_calibration",
            schema_version=1,
            model="qwen3.6:latest",
            backend="ollama",
            source_sha256=f"{index + 1:x}" * 64,
            headroom_ratio=headroom,
            measurements=(
                _measurement(32_000, 2_000_000, MemoryMeasurementOutcome.SUCCESS),
                _measurement(48_000, 3_000_000, MemoryMeasurementOutcome.OOM),
            ),
        )
        path = tmp_path / f"measurement-{index}.json"
        _ = path.write_text(artifact.model_dump_json(), encoding="utf-8")
        paths.append(path)

    budget = load_model_memory_budget(tuple(paths), "qwen3.6:latest")

    assert budget is not None
    assert budget.context_token_limit == 16_000
    assert budget.kv_cache_byte_limit == 1_000_000
