from __future__ import annotations

import json
from pathlib import Path

import yaml
from pytest import MonkeyPatch

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelRouter


def _write_runtime_config(path: Path, state_path: Path) -> None:
    payload = {
        "models": {
            "reasoning": [
                {"name": "base-model", "repo": "base-model", "role": "reasoning"},
            ],
        },
        "active_artifact": {
            "state_path": str(state_path),
            "model_name": "active-model",
            "role": "reasoning",
        },
    }
    _ = path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_active_pointer(path: Path, fused_path: Path) -> None:
    payload = {
        "status": "active",
        "base_model": "mlx-community/Qwen2.5-0.5B-4bit",
        "base_revision": "8b4323d7cf06a376179d6eb5358ed1c66902529a",
        "output_path": str(fused_path),
        "recipe_sha256": "b" * 64,
        "evaluation_sha256": "c" * 64,
        "promotion_revision": 1,
    }
    _ = path.write_text(json.dumps(payload), encoding="utf-8")


def test_promoted_active_artifact_routes_and_loads_its_fused_repo(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    # Given: a configured active artifact points at a promoted fused directory.
    config_path = tmp_path / "config.yaml"
    state_path = tmp_path / "active.json"
    fused_path = tmp_path / "promoted-fused"
    fused_path.mkdir()
    _write_active_pointer(state_path, fused_path)
    _write_runtime_config(config_path, state_path)
    registry = ModelRegistry(config_path=str(config_path))
    router = ModelRouter(registry)
    manager = ModelManager(registry, router=router)
    loaded_profiles: list[ModelProfile] = []

    def fake_mlx_loader(profile: ModelProfile) -> tuple[str, str]:
        loaded_profiles.append(profile)
        return "fused-model", "fused-tokenizer"

    monkeypatch.setattr(manager, "_load_mlx_model", fake_mlx_loader)

    # When: the active name is routed and loaded through the runtime services.
    routed_profile = router.route_single("active-model")
    loaded_model = manager.load("active-model")

    # Then: routing and the real manager load seam receive the fused MLX profile.
    assert routed_profile.provider == "mlx"
    assert routed_profile.repo == str(fused_path)
    assert loaded_profiles == [routed_profile]
    assert loaded_model.profile.repo == str(fused_path)
