from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from antigravity_k.engine.provider_adapters.unsloth_resource_broker import (
    SystemMemoryProbe,
    UnslothResourceBroker,
)
from antigravity_k.finetune.dataset_contract import (
    DatasetConsent,
    DatasetLicense,
    DatasetSplitPolicy,
    DatasetSubjectRights,
    FinetuneDatasetContract,
    inspect_dataset,
    split_frozen_dataset,
)
from antigravity_k.finetune.training_adapter import (
    TrainingRunResult,
    TrainingRunStatus,
    run_resolved_training,
)
from antigravity_k.finetune.training_recipe import (
    TrainingRecipe,
    resolve_training_recipe,
)
from antigravity_k.finetune.training_runtime import FakeTrainingLaunch

_result_adapter: TypeAdapter[TrainingRunResult] = TypeAdapter(TrainingRunResult)
_launch_adapter: TypeAdapter[FakeTrainingLaunch] = TypeAdapter(FakeTrainingLaunch)


class FakeResumeLaunch(FakeTrainingLaunch):
    resume_adapter_file: Path


def _fake_mlx_package(root: Path, marker: Path) -> None:
    package = root / "mlx_lm"
    _ = package.mkdir(parents=True)
    _ = (package / "__init__.py").write_text("", encoding="utf-8")
    _ = (package / "__main__.py").write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from pathlib import Path",
                "",
                "if __import__('sys').argv[1:2] == ['lora']:",
                "    del __import__('sys').argv[1]",
                "",
                "argv = __import__('sys').argv",
                "data_index = argv.index('--data') + 1",
                "payload = {'argv': argv, 'data_dir': argv[data_index]}",
                "if '--resume-adapter-file' in argv:",
                "    payload['resume_adapter_file'] = argv[argv.index('--resume-adapter-file') + 1]",
                "marker = Path(os.environ['FAKE_MLX_MARKER'])",
                "marker.write_text(json.dumps(payload), encoding='utf-8')",
                "print('fake training complete')",
            ],
        ),
        encoding="utf-8",
    )
    assert marker.parent.exists()


def _recipe(tmp_path: Path) -> tuple[TrainingRecipe, Path, Path]:
    dataset_path = tmp_path / "prepared.jsonl"
    records = [{"instruction": f"question {index}", "output": f"answer {index}"} for index in range(10)]
    _ = dataset_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    contract = FinetuneDatasetContract(
        path=dataset_path,
        consent=DatasetConsent.EXPLICIT,
        subject_rights=DatasetSubjectRights.HONORED,
        license_id=DatasetLicense.MIT,
        split_policy=DatasetSplitPolicy(
            seed=42,
            train_ratio="90/10",
            manifest_path=dataset_path.with_name("split_manifest.json"),
        ),
    )
    _ = inspect_dataset(contract)
    split_paths = split_frozen_dataset(contract)
    recipe = TrainingRecipe(
        base_model="/models/base",
        base_revision="sha256:base-revision",
        output_dir=tmp_path / "run",
        dataset=contract,
        epochs=2,
        batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=Decimal("0.00001"),
        lora_rank=8,
        lora_alpha=16,
        save_every=2,
        seed=7,
    )
    return recipe, split_paths.train_path, split_paths.valid_path


def test_training_adapter_stages_mlx_data_and_runs_resolved_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "marker.json"
    _fake_mlx_package(fake_root, marker)
    recipe, train_path, valid_path = _recipe(tmp_path)
    resolved = resolve_training_recipe(recipe)
    monkeypatch.setenv("PYTHONPATH", str(fake_root))
    monkeypatch.setenv("FAKE_MLX_MARKER", str(marker))

    result = run_resolved_training(resolved)

    assert result.status is TrainingRunStatus.SUCCESS
    assert result.return_code == 0
    assert "fake training complete" in result.stdout
    assert result.base_revision == "sha256:base-revision"
    assert (resolved.data_dir / "train.jsonl").read_bytes() == train_path.read_bytes()
    assert (resolved.data_dir / "valid.jsonl").read_bytes() == valid_path.read_bytes()
    launched = _launch_adapter.validate_json(marker.read_text(encoding="utf-8"))
    assert launched.data_dir == resolved.data_dir
    saved = _result_adapter.validate_json((recipe.output_dir / "training_result.json").read_text(encoding="utf-8"))
    assert saved == result


def test_train_cli_runs_resolved_recipe_through_adapter(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "marker.json"
    _fake_mlx_package(fake_root, marker)
    recipe, _, _ = _recipe(tmp_path)
    resource_db = tmp_path / "resources.sqlite3"
    environment = os.environ | {
        "PYTHONPATH": f"{fake_root}{os.pathsep}src",
        "FAKE_MLX_MARKER": str(marker),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "train",
            "--model",
            "/models/base",
            "--base-revision",
            "sha256:base-revision",
            "--data",
            str(recipe.dataset.path),
            "--manifest",
            str(recipe.dataset.split_policy.manifest_path),
            "--output",
            str(recipe.output_dir),
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

    payload = _result_adapter.validate_json(result.stdout)
    assert result.returncode == 0
    assert payload.status is TrainingRunStatus.SUCCESS
    assert (recipe.output_dir / "training_result.json").exists()
    assert (recipe.output_dir / "data" / "train.jsonl").exists()
    assert (recipe.output_dir / "data" / "valid.jsonl").exists()
    assert UnslothResourceBroker(resource_db, SystemMemoryProbe()).status().active_reservations == ()


def test_train_cli_requires_resource_estimate_before_launch(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "marker.json"
    _fake_mlx_package(fake_root, marker)
    recipe, _, _ = _recipe(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "train",
            "--model",
            "/models/base",
            "--base-revision",
            "sha256:base-revision",
            "--data",
            str(recipe.dataset.path),
            "--manifest",
            str(recipe.dataset.split_policy.manifest_path),
            "--output",
            str(recipe.output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ
        | {
            "PYTHONPATH": f"{fake_root}{os.pathsep}src",
            "FAKE_MLX_MARKER": str(marker),
        },
    )

    assert result.returncode == 2
    assert "--estimated-peak-bytes is required" in result.stderr
    assert not marker.exists()


def test_training_adapter_runs_resume_command_and_records_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root = tmp_path / "fake"
    marker = tmp_path / "resume-marker.json"
    _fake_mlx_package(fake_root, marker)
    recipe, _, _ = _recipe(tmp_path)
    checkpoint = recipe.output_dir / "adapters" / "0000004_adapters.safetensors"
    checkpoint.parent.mkdir(parents=True)
    _ = checkpoint.write_bytes(b"checkpoint")
    monkeypatch.setenv("PYTHONPATH", str(fake_root))
    monkeypatch.setenv("FAKE_MLX_MARKER", str(marker))

    resolved = resolve_training_recipe(recipe, resume=True)
    result = run_resolved_training(resolved)

    launch = TypeAdapter(FakeResumeLaunch).validate_json(marker.read_text(encoding="utf-8"))
    assert result.resume_adapter_path == checkpoint
    assert result.resume_source_sha256 == hashlib.sha256(b"checkpoint").hexdigest()
    assert launch.resume_adapter_file == checkpoint


def test_train_cli_resume_rejects_missing_checkpoint(tmp_path: Path) -> None:
    recipe, _, _ = _recipe(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "train",
            "--model",
            "/models/base",
            "--base-revision",
            "sha256:base-revision",
            "--data",
            str(recipe.dataset.path),
            "--manifest",
            str(recipe.dataset.split_policy.manifest_path),
            "--output",
            str(recipe.output_dir),
            "--resume",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": "src"},
    )

    assert result.returncode == 2
    assert "Resumable checkpoint is required" in result.stderr
