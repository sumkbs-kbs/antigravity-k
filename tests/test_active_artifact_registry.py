from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from pytest import LogCaptureFixture

from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.finetune.active_artifact import (
    ActiveArtifactError,
    ActiveArtifactState,
    ActiveArtifactStatus,
    read_active_artifact,
    validate_active_artifact_output,
)
from antigravity_k.finetune.artifact_lifecycle import FusedArtifactResult, FusedArtifactStatus


def _write_registry_config(path: Path, state_path: Path) -> None:
    payload = {
        "models": {"reasoning": [{"name": "base-model", "repo": "base-model", "role": "reasoning"}]},
        "defaults": {"reasoning": "active-model"},
        "active_artifact": {"state_path": str(state_path), "model_name": "active-model", "role": "reasoning"},
    }
    _ = path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_active_pointer(path: Path, output_path: Path) -> None:
    payload = {
        "status": "active",
        "base_model": "mlx-community/Qwen2.5-0.5B-4bit",
        "base_revision": "8b4323d7cf06a376179d6eb5358ed1c66902529a",
        "output_path": str(output_path),
        "recipe_sha256": "b" * 64,
        "evaluation_sha256": "c" * 64,
        "promotion_revision": 1,
    }
    _ = path.write_text(json.dumps(payload), encoding="utf-8")


def _write_fused_artifact(output_path: Path) -> None:
    output_path.mkdir()
    artifact = FusedArtifactResult(
        status=FusedArtifactStatus.SUCCESS,
        return_code=0,
        base_model="mlx-community/Qwen2.5-0.5B-4bit",
        base_revision="8b4323d7cf06a376179d6eb5358ed1c66902529a",
        adapter_path=output_path / "adapters",
        output_path=output_path,
        dataset_sha256="a" * 64,
        recipe_sha256="b" * 64,
        environment={"python": "3.13"},
        evaluation_sha256="c" * 64,
        iterations=1,
        stdout="",
        stderr="",
    )
    _ = (output_path / "artifact_manifest.json").write_text(artifact.model_dump_json(indent=2), encoding="utf-8")


def test_registry_exposes_valid_active_artifact_as_mlx_profile(tmp_path: Path) -> None:
    # Given: a configured active pointer identifies a valid fused artifact.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    artifact_path = tmp_path / "fused"
    _write_fused_artifact(artifact_path)
    _write_active_pointer(state_path, artifact_path)
    _write_registry_config(config_path, state_path)

    # When: the registry loads the active artifact.
    registry = ModelRegistry(config_path=str(config_path))
    profile = registry.get_model("active-model")

    # Then: the profile exposes the validated fused path through MLX.
    assert profile is not None
    assert profile.provider == "mlx"
    assert profile.repo == str(artifact_path)
    assert profile.role == "reasoning"
    assert registry.defaults.reasoning == "active-model"


def test_registry_keeps_base_catalog_when_active_artifact_output_is_missing(tmp_path: Path) -> None:
    # Given: an active JSON pointer references a fused output that no longer exists.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    _write_active_pointer(state_path, tmp_path / "missing-fused")
    _write_registry_config(config_path, state_path)

    # When: the registry loads the configured catalog.
    registry = ModelRegistry(config_path=str(config_path))

    # Then: it fails closed and leaves only the configured base model exposed.
    assert registry.get_model("active-model") is None
    assert registry.get_model("base-model") is not None


def test_registry_rejects_existing_directory_without_fused_manifest(tmp_path: Path) -> None:
    # Given: an active pointer targets an arbitrary existing directory.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    arbitrary_path = tmp_path / "arbitrary"
    arbitrary_path.mkdir()
    _write_active_pointer(state_path, arbitrary_path)
    _write_registry_config(config_path, state_path)

    # When: the registry loads the active pointer.
    registry = ModelRegistry(config_path=str(config_path))

    # Then: no active profile is exposed and the base catalog remains available.
    assert registry.get_model("active-model") is None
    assert registry.get_model("base-model") is not None


def test_registry_rejects_symlinked_fused_output(tmp_path: Path) -> None:
    # Given: an active pointer targets a symlink to an otherwise valid fused artifact.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    fused_path = tmp_path / "fused"
    output_symlink = tmp_path / "fused-link"
    _write_fused_artifact(fused_path)
    output_symlink.symlink_to(fused_path, target_is_directory=True)
    _write_active_pointer(state_path, output_symlink)
    _write_registry_config(config_path, state_path)

    # When: the registry loads the active pointer.
    registry = ModelRegistry(config_path=str(config_path))

    # Then: symlinked output cannot become the active MLX profile.
    assert registry.get_model("active-model") is None
    assert registry.get_model("base-model") is not None


def test_registry_redacts_malformed_pointer_metadata_from_warning(tmp_path: Path, caplog: LogCaptureFixture) -> None:
    # Given: malformed pointer data includes a secret-bearing rejected field.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    secret = "api-key-sentinel-must-not-log"
    _ = state_path.write_text(f'{{"status":"active","api_key":"{secret}"}}', encoding="utf-8")
    _write_registry_config(config_path, state_path)
    caplog.set_level(logging.WARNING, logger="antigravity_k.model_registry")

    # When: the registry rejects the malformed active pointer.
    registry = ModelRegistry(config_path=str(config_path))

    # Then: it retains the base catalog without logging rejected metadata.
    assert registry.get_model("active-model") is None
    assert registry.get_model("base-model") is not None
    assert secret not in caplog.text
    assert "Active artifact model is unavailable." in caplog.text


def test_registry_keeps_base_catalog_when_active_state_path_is_directory(tmp_path: Path) -> None:
    # Given: active configuration points to a directory rather than a state file.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active-state-directory"
    state_path.mkdir()
    _write_registry_config(config_path, state_path)

    # When: the registry initializes.
    registry = ModelRegistry(config_path=str(config_path))

    # Then: the invalid state path cannot abort catalog loading or expose an active profile.
    assert registry.get_model("active-model") is None
    assert registry.get_model("base-model") is not None


def test_registry_keeps_base_catalog_when_active_pointer_is_malformed(tmp_path: Path) -> None:
    # Given: the active pointer does not contain valid JSON state.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    _ = state_path.write_text("not-json", encoding="utf-8")
    _write_registry_config(config_path, state_path)

    # When: the registry loads the configured catalog.
    registry = ModelRegistry(config_path=str(config_path))

    # Then: malformed promotion state does not hide the configured base model.
    assert registry.get_model("active-model") is None
    assert registry.get_model("base-model") is not None


def test_read_active_artifact_rejects_directory_state_path_without_detail(tmp_path: Path) -> None:
    # Given: a directory is supplied where the active JSON state file is required.
    state_path = tmp_path / "active-state"
    state_path.mkdir()

    # When: the active state boundary is read.
    try:
        _ = read_active_artifact(state_path)
    except ActiveArtifactError as error:
        # Then: the error remains stable and does not expose filesystem details.
        assert str(error) == "Active artifact state is unavailable."
    else:
        raise AssertionError("directory state path must be rejected")


def test_validated_active_artifact_output_rejects_symlink(tmp_path: Path) -> None:
    # Given: a valid fused artifact is addressed through a directory symlink.
    artifact_path = tmp_path / "candidate"
    symlink_path = tmp_path / "candidate-link"
    _write_fused_artifact(artifact_path)
    symlink_path.symlink_to(artifact_path, target_is_directory=True)
    state = ActiveArtifactState(
        status=ActiveArtifactStatus.ACTIVE,
        base_model="mlx-community/Qwen2.5-0.5B-4bit",
        base_revision="8b4323d7cf06a376179d6eb5358ed1c66902529a",
        output_path=symlink_path,
        recipe_sha256="b" * 64,
        evaluation_sha256="c" * 64,
        promotion_revision=1,
    )

    # When: the active output is validated.
    try:
        _ = validate_active_artifact_output(state)
    except ActiveArtifactError as error:
        # Then: directory symlinks cannot become active artifact outputs.
        assert str(error) == "Active artifact output is unavailable."
    else:
        raise AssertionError("symlinked active output must be rejected")
