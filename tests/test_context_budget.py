from __future__ import annotations

import json
from pathlib import Path

from pydantic import JsonValue

from antigravity_k.engine.context_budget import context_budget_for_model
from antigravity_k.engine.orchestrator import OrchestratorAgent


def _config(*, context_length: int, configured_limit: int | None = None) -> dict[str, JsonValue]:
    router: dict[str, JsonValue] = {}
    if configured_limit is not None:
        router["context_token_limit"] = configured_limit
    return {
        "defaults": {"reasoning": "qwen3.6:latest"},
        "models": {
            "reasoning": [
                {
                    "name": "qwen3.6:latest",
                    "context_length": context_length,
                },
            ],
        },
        "router": router,
    }


def _write_memory_artifact(path: Path, *, model: str = "qwen3.6:latest") -> None:
    _ = path.write_text(
        json.dumps(
            {
                "artifact_type": "model_memory_calibration",
                "schema_version": 1,
                "model": model,
                "backend": "ollama",
                "source_sha256": "a" * 64,
                "headroom_ratio": 0.25,
                "measurements": [
                    {
                        "context_tokens": 16_000,
                        "kv_cache_bytes": 1_000_000,
                        "peak_memory_bytes": 8_000_000,
                        "outcome": "success",
                    },
                    {
                        "context_tokens": 32_000,
                        "kv_cache_bytes": 2_000_000,
                        "peak_memory_bytes": 10_000_000,
                        "outcome": "success",
                    },
                    {
                        "context_tokens": 48_000,
                        "kv_cache_bytes": 3_000_000,
                        "peak_memory_bytes": 12_000_000,
                        "outcome": "oom",
                    },
                ],
            },
        ),
        encoding="utf-8",
    )


def test_context_budget_expands_qwen_profile_without_using_its_full_window():
    budget = context_budget_for_model(_config(context_length=262_144), "qwen3.6:latest")

    assert budget.token_limit == 32_768
    assert budget.trajectory_max_messages == 128
    assert budget.trajectory_max_chars == 131_072


def test_context_budget_preserves_legacy_limit_for_an_unknown_model():
    budget = context_budget_for_model(_config(context_length=262_144), "unregistered-model")

    assert budget.token_limit == 8_000
    assert budget.trajectory_max_messages == 40
    assert budget.trajectory_max_chars == 80_000


def test_context_budget_never_exceeds_a_smaller_model_window():
    budget = context_budget_for_model(_config(context_length=16_384, configured_limit=100_000), "qwen3.6:latest")

    assert budget.token_limit == 12_288
    assert budget.trajectory_max_messages == 48
    assert budget.trajectory_max_chars == 80_000


def test_context_budget_honors_a_lower_explicit_operator_limit():
    budget = context_budget_for_model(_config(context_length=262_144, configured_limit=12_000), "qwen3.6:latest")

    assert budget.token_limit == 12_000
    assert budget.trajectory_max_messages == 46


def test_context_budget_applies_empirical_model_and_kv_limits(tmp_path: Path) -> None:
    artifact_path = tmp_path / "qwen-memory.json"
    _write_memory_artifact(artifact_path)
    config = _config(context_length=262_144)
    router = config["router"]
    assert isinstance(router, dict)
    router["memory_calibration_artifact_paths"] = [str(artifact_path)]

    budget = context_budget_for_model(config, "qwen3.6:latest")

    assert budget.token_limit == 24_000
    assert budget.kv_cache_byte_limit == 1_500_000


def test_orchestrator_uses_empirical_context_limit_for_target_model(tmp_path: Path) -> None:
    artifact_path = tmp_path / "qwen-memory.json"
    _write_memory_artifact(artifact_path)
    config = _config(context_length=262_144)
    router = config["router"]
    assert isinstance(router, dict)
    router["memory_calibration_artifact_paths"] = [str(artifact_path)]
    orchestrator = OrchestratorAgent(model_manager=_Manager(), project_root=str(tmp_path))
    orchestrator.config = config

    context_compressor = orchestrator.context_compressor_for("qwen3.6:latest")

    assert context_compressor is not None
    assert context_compressor.token_limit == 24_000


def test_context_budget_does_not_borrow_another_models_empirical_limit(tmp_path: Path) -> None:
    artifact_path = tmp_path / "qwen-memory.json"
    _write_memory_artifact(artifact_path)
    config = _config(context_length=262_144)
    router = config["router"]
    assert isinstance(router, dict)
    router["memory_calibration_artifact_paths"] = [str(artifact_path)]

    budget = context_budget_for_model(config, "different-model")

    assert budget.token_limit == 8_000
    assert budget.kv_cache_byte_limit is None


class _Manager:
    def generate(self, **_kwargs: JsonValue) -> str:
        return "summary"


def test_orchestrator_builds_target_aware_compressors(tmp_path: Path) -> None:
    orchestrator = OrchestratorAgent(model_manager=_Manager(), project_root=str(tmp_path))
    orchestrator.config = _config(context_length=262_144)

    context_compressor = orchestrator.context_compressor_for("qwen3.6:latest")
    trajectory_compressor = orchestrator.trajectory_compressor_for("qwen3.6:latest")

    assert context_compressor is not None
    assert context_compressor.token_limit == 32_768
    assert trajectory_compressor is not None
    assert trajectory_compressor.max_messages == 128
