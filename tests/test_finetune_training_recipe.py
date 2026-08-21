from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from antigravity_k.finetune.dataset_contract import (
    DatasetConsent,
    DatasetLicense,
    DatasetSplitPolicy,
    DatasetSubjectRights,
    FinetuneDatasetContract,
    inspect_dataset,
)
from antigravity_k.finetune.training_recipe import (
    ResolvedTrainingRecipe,
    TrainingRecipe,
    TrainingRecipeError,
    resolve_training_recipe,
)

_resolved_adapter: TypeAdapter[ResolvedTrainingRecipe] = TypeAdapter(ResolvedTrainingRecipe)


def _dataset(tmp_path: Path) -> FinetuneDatasetContract:
    path = tmp_path / "prepared.jsonl"
    records = [{"instruction": f"question {index}", "output": f"answer {index}"} for index in range(10)]
    _ = path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return FinetuneDatasetContract(
        path=path,
        consent=DatasetConsent.EXPLICIT,
        subject_rights=DatasetSubjectRights.HONORED,
        license_id=DatasetLicense.MIT,
        split_policy=DatasetSplitPolicy(
            seed=42,
            train_ratio="90/10",
            manifest_path=path.with_name("split_manifest.json"),
        ),
    )


def _recipe(contract: FinetuneDatasetContract) -> TrainingRecipe:
    return TrainingRecipe(
        base_model="/models/base",
        base_revision="sha256:base-revision",
        output_dir=contract.path.parent / "run",
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


def test_training_recipe_resolves_dataset_and_command(tmp_path: Path) -> None:
    contract = _dataset(tmp_path)
    report = inspect_dataset(contract)

    resolved = resolve_training_recipe(_recipe(contract))

    assert resolved.dataset_sha256 == report.sha256
    assert resolved.dataset_record_count == report.record_count
    assert resolved.train_path == contract.path.with_name("prepared_train.jsonl")
    assert resolved.valid_path == contract.path.with_name("prepared_valid.jsonl")
    assert resolved.command[:3] == (sys.executable, "-m", "mlx_lm")
    assert resolved.command[3] == "lora"
    assert "--model" in resolved.command
    assert resolved.command[resolved.command.index("--model") + 1] == "/models/base"
    assert resolved.command[resolved.command.index("--adapter-path") + 1] == str(tmp_path / "run" / "adapters")
    assert resolved.data_dir == tmp_path / "run" / "data"
    assert resolved.command[resolved.command.index("--data") + 1] == str(tmp_path / "run" / "data")
    assert resolved.command[resolved.command.index("--iters") + 1] == "6"
    assert resolved.base_model == "/models/base"
    assert resolved.base_revision == "sha256:base-revision"
    assert len(resolved.recipe_sha256) == 64
    assert resolved.environment["python"] == sys.version.split()[0]
    assert len(resolved.evaluation_sha256) == 64


def test_training_recipe_rejects_mismatched_dataset_manifest(tmp_path: Path) -> None:
    contract = _dataset(tmp_path)
    _ = inspect_dataset(contract)
    changed = contract.model_copy(
        update={
            "path": contract.path.with_name("changed.jsonl"),
            "split_policy": contract.split_policy.model_copy(
                update={"seed": 8},
            ),
        },
    )
    _ = changed.path.write_text(contract.path.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(TrainingRecipeError, match="Frozen dataset manifest must remain unchanged."):
        _ = resolve_training_recipe(_recipe(changed))


def test_train_cli_dry_run_prints_resolved_recipe_without_adapters(tmp_path: Path) -> None:
    contract = _dataset(tmp_path)
    _ = inspect_dataset(contract)

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
            str(contract.path),
            "--manifest",
            str(contract.split_policy.manifest_path),
            "--output",
            str(tmp_path / "run"),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src"},
    )

    payload = _resolved_adapter.validate_json(result.stdout)
    assert result.returncode == 0
    assert payload.command[1:4] == ("-m", "mlx_lm", "lora")
    assert payload.dataset_sha256 is not None
    assert payload.base_revision == "sha256:base-revision"
    assert not (tmp_path / "run").exists()
