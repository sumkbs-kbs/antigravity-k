from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter

from antigravity_k.engine.provider_adapters.unsloth_resource_broker import (
    SystemMemoryProbe,
    UnslothResourceBroker,
)
from antigravity_k.finetune.artifact_lifecycle import (
    ArtifactLifecycleError,
    FusedArtifactResult,
    FusedArtifactStatus,
    fuse_training_artifact,
)
from antigravity_k.finetune.training_adapter import TrainingRunResult, TrainingRunStatus
from antigravity_k.finetune.training_recipe import ResolvedTrainingRecipe


class FakeFuseLaunch(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    argv: tuple[str, ...]
    fuse: bool


_artifact_adapter: TypeAdapter[FusedArtifactResult] = TypeAdapter(FusedArtifactResult)
_launch_adapter: TypeAdapter[FakeFuseLaunch] = TypeAdapter(FakeFuseLaunch)


def _resolved(tmp_path: Path) -> ResolvedTrainingRecipe:
    return ResolvedTrainingRecipe(
        command=(sys.executable, "-m", "mlx_lm", "lora"),
        dataset_sha256="a" * 64,
        dataset_record_count=10,
        train_path=tmp_path / "train.jsonl",
        valid_path=tmp_path / "valid.jsonl",
        adapter_path=tmp_path / "run" / "adapters",
        data_dir=tmp_path / "run" / "data",
        iterations=6,
        base_model="/models/base",
        base_revision="sha256:base-revision",
        recipe_sha256="b" * 64,
        environment={"python": "3.13", "mlx_lm": "test"},
        evaluation_sha256="c" * 64,
    )


def _training_result(resolved: ResolvedTrainingRecipe) -> TrainingRunResult:
    return TrainingRunResult(
        status=TrainingRunStatus.SUCCESS,
        return_code=0,
        dataset_sha256=resolved.dataset_sha256,
        adapter_path=resolved.adapter_path,
        data_dir=resolved.data_dir,
        iterations=resolved.iterations,
        stdout="trained",
        stderr="",
        base_model=resolved.base_model,
        base_revision=resolved.base_revision,
        recipe_sha256=resolved.recipe_sha256,
        environment=resolved.environment,
        evaluation_sha256=resolved.evaluation_sha256,
    )


def _fake_fuse_package(root: Path) -> None:
    package = root / "mlx_lm"
    package.mkdir(parents=True, exist_ok=True)
    _ = (package / "__init__.py").write_text("", encoding="utf-8")
    _ = (package / "__main__.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from pathlib import Path",
                "",
                "argv = __import__('sys').argv",
                "payload = {'argv': argv, 'fuse': True}",
                "if argv[1:2] == ['fuse']:",
                "    del argv[1]",
                "Path(os.environ['FAKE_FUSE_MARKER']).write_text(json.dumps(payload), encoding='utf-8')",
                "print('fake fuse complete')",
            ],
        ),
        encoding="utf-8",
    )


def test_fuse_training_artifact_runs_command_and_writes_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "fuse-launch.json"
    _fake_fuse_package(fake_root)
    resolved = _resolved(tmp_path)
    result = _training_result(resolved)
    output_path = tmp_path / "fused"
    monkeypatch.setenv("PYTHONPATH", str(fake_root))
    monkeypatch.setenv("FAKE_FUSE_MARKER", str(marker))

    fused = fuse_training_artifact(result, output_path=output_path)

    assert fused.status is FusedArtifactStatus.SUCCESS
    assert fused.return_code == 0
    assert (output_path / "artifact_manifest.json").exists()
    saved = _artifact_adapter.validate_json((output_path / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert saved == fused
    assert fused.dataset_sha256 == result.dataset_sha256
    assert fused.recipe_sha256 == result.recipe_sha256
    assert fused.environment == result.environment
    assert fused.evaluation_sha256 == result.evaluation_sha256
    assert fused.base_revision == result.base_revision
    assert saved.base_revision == result.base_revision
    launch = _launch_adapter.validate_json(marker.read_text(encoding="utf-8"))
    assert launch.argv[launch.argv.index("--adapter-path") + 1] == str(result.adapter_path)
    assert launch.argv[launch.argv.index("--save-path") + 1] == str(output_path)


def test_fuse_training_artifact_rejects_failed_training(tmp_path: Path) -> None:
    resolved = _resolved(tmp_path)
    result = _training_result(resolved).model_copy(
        update={"status": TrainingRunStatus.FAILED, "return_code": 2},
    )

    with pytest.raises(ArtifactLifecycleError, match="Successful training run"):
        _ = fuse_training_artifact(result, output_path=tmp_path / "invalid")


def test_merge_cli_emits_typed_artifact_manifest(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "fuse-launch.json"
    _fake_fuse_package(fake_root)
    resolved = _resolved(tmp_path)
    training_result = _training_result(resolved)
    training_path = tmp_path / "training_result.json"
    resource_db = tmp_path / "resources.sqlite3"
    _ = training_path.write_text(training_result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    environment = os.environ | {
        "PYTHONPATH": f"{fake_root}{os.pathsep}src",
        "FAKE_FUSE_MARKER": str(marker),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "merge",
            "--run",
            str(training_path),
            "--output",
            str(tmp_path / "fused-cli"),
            "--estimated-peak-bytes",
            "100000",
            "--resource-db",
            str(resource_db),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    payload = _artifact_adapter.validate_json(result.stdout)
    assert result.returncode == 0
    assert payload.status is FusedArtifactStatus.SUCCESS
    assert (tmp_path / "fused-cli" / "artifact_manifest.json").exists()
    assert UnslothResourceBroker(resource_db, SystemMemoryProbe()).status().active_reservations == ()


def test_merge_cli_requires_resource_estimate_before_launch(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "fuse-launch.json"
    _fake_fuse_package(fake_root)
    resolved = _resolved(tmp_path)
    training_path = tmp_path / "training_result.json"
    _ = training_path.write_text(_training_result(resolved).model_dump_json(), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "merge",
            "--run",
            str(training_path),
            "--output",
            str(tmp_path / "fused-cli"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ
        | {
            "PYTHONPATH": f"{fake_root}{os.pathsep}src",
            "FAKE_FUSE_MARKER": str(marker),
        },
    )

    assert result.returncode == 2
    assert "--estimated-peak-bytes is required" in result.stderr
    assert not marker.exists()
    assert not (tmp_path / "fused-cli").exists()


def test_merge_cli_rejects_failed_training_run(tmp_path: Path) -> None:
    resolved = _resolved(tmp_path)
    training_result = _training_result(resolved).model_copy(
        update={"status": TrainingRunStatus.FAILED, "return_code": 2},
    )
    training_path = tmp_path / "training_result.json"
    _ = training_path.write_text(training_result.model_dump_json(indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "merge",
            "--run",
            str(training_path),
            "--output",
            str(tmp_path / "invalid-cli"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": "src"},
    )

    assert result.returncode == 2
    assert not (tmp_path / "invalid-cli").exists()
