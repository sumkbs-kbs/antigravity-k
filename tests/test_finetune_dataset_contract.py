from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from antigravity_k.finetune.dataset_contract import (
    DatasetConsent,
    DatasetContractError,
    DatasetLicense,
    DatasetSplitManifest,
    DatasetSplitPolicy,
    DatasetSubjectRights,
    FinetuneDatasetContract,
    inspect_dataset,
    split_frozen_dataset,
)


def _dataset(tmp_path: Path) -> Path:
    path = tmp_path / "dataset.jsonl"
    records = [{"instruction": f"question {index}", "output": f"answer {index}"} for index in range(10)]
    _ = path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def _contract(path: Path, *, consent: DatasetConsent = DatasetConsent.EXPLICIT) -> FinetuneDatasetContract:
    return FinetuneDatasetContract(
        path=path,
        consent=consent,
        subject_rights=DatasetSubjectRights.HONORED,
        license_id=DatasetLicense.MIT,
        split_policy=DatasetSplitPolicy(
            seed=42,
            train_ratio="90/10",
            manifest_path=path.parent / "split_manifest.json",
        ),
    )


def test_dataset_contract_hashes_and_freezes_split(tmp_path: Path) -> None:
    path = _dataset(tmp_path)
    contract = _contract(path)

    report = inspect_dataset(contract)

    expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert report.sha256 == expected_hash
    assert report.record_count == 10
    assert report.train_record_count == 9
    assert report.valid_record_count == 1
    manifest = DatasetSplitManifest.model_validate_json(
        (path.parent / "split_manifest.json").read_text(encoding="utf-8"),
    )
    assert manifest.sha256 == expected_hash
    assert manifest.seed == 42
    assert manifest.train_indices == tuple(sorted(manifest.train_indices))
    assert manifest.valid_indices == (1,)


def test_dataset_contract_rejects_non_explicit_consent_or_unhonored_rights(tmp_path: Path) -> None:
    path = _dataset(tmp_path)

    with pytest.raises(DatasetContractError, match="explicit consent"):
        _ = inspect_dataset(
            _contract(path, consent=DatasetConsent.PUBLICLY_AVAILABLE),
        )


def test_dataset_split_writes_files_from_frozen_manifest(tmp_path: Path) -> None:
    path = _dataset(tmp_path)

    split_paths = split_frozen_dataset(_contract(path))

    manifest = DatasetSplitManifest.model_validate_json(
        (path.parent / "split_manifest.json").read_text(encoding="utf-8"),
    )
    records = path.read_text(encoding="utf-8").splitlines()
    assert split_paths.train_path.read_text(encoding="utf-8").splitlines() == [
        records[index] for index in manifest.train_indices
    ]
    assert split_paths.valid_path.read_text(encoding="utf-8").splitlines() == [
        records[index] for index in manifest.valid_indices
    ]


def test_prepare_cli_requires_dataset_contract_and_rejects_pii(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "prepared.jsonl"
    record = {"instruction": "email user@example.com", "output": "answer"}
    _ = input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "prepare",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--consent",
            "explicit",
            "--license",
            "MIT",
            "--subject-rights",
            "honored",
            "--split",
            "90/10",
            "--seed",
            "42",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src"},
    )

    assert result.returncode != 0
    assert "PII detected" in result.stderr
    assert output_path.exists()
    assert not output_path.with_name("split_manifest.json").exists()


def test_dataset_contract_detects_plain_email_pii(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    record = {"instruction": "email user@example.com", "output": "answer"}
    _ = path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="PII"):
        _ = inspect_dataset(_contract(path))


def test_dataset_contract_rejects_changed_dataset_after_freeze(tmp_path: Path) -> None:
    path = _dataset(tmp_path)
    _ = inspect_dataset(_contract(path))
    with path.open("a", encoding="utf-8") as stream:
        _stream = stream.write(json.dumps({"instruction": "new", "output": "new"}) + "\n")

    with pytest.raises(DatasetContractError, match="unchanged"):
        _ = inspect_dataset(_contract(path))


def test_dataset_contract_requires_both_train_and_valid_records(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    _ = path.write_text(json.dumps({"instruction": "one", "output": "one"}) + "\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="train and validation"):
        _ = inspect_dataset(_contract(path))
