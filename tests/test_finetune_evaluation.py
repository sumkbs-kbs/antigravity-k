from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from antigravity_k.finetune.artifact_lifecycle import fuse_training_artifact
from antigravity_k.finetune.evaluation import (
    CandidateEvaluation,
    CandidateKind,
    EvaluationCase,
    EvaluationDataset,
    EvaluationError,
    EvaluationPair,
    evaluate_candidates,
    evaluation_pair_sha256,
    load_evaluation_pair,
)
from antigravity_k.finetune.training_adapter import TrainingRunResult, TrainingRunStatus
from antigravity_k.finetune.training_recipe import ResolvedTrainingRecipe

_pair_adapter: TypeAdapter[EvaluationPair] = TypeAdapter(EvaluationPair)


def _write_freeze(path: Path, *, row_count: int) -> None:
    _ = path.with_suffix(".freeze.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset_path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "row_count": row_count,
            },
        )
        + "\n",
        encoding="utf-8",
    )


def _write_dataset(root: Path) -> EvaluationDataset:
    path = root / "held_out_v1.jsonl"
    rows = [
        {
            "id": "ko",
            "category": "korean_reasoning",
            "prompt": "summary",
            "expected_keywords": ["summary"],
            "forbidden_for_training": True,
        },
        {
            "id": "code",
            "category": "verified_code",
            "prompt": "code",
            "expected_output": "63",
            "expected_keywords": ["63"],
            "forbidden_for_training": True,
        },
    ]
    _ = path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    _write_freeze(path, row_count=len(rows))
    return EvaluationDataset(path=path, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), case_ids=("ko", "code"))


def _candidate(kind: CandidateKind, score: float) -> CandidateEvaluation:
    identity = Path("adapter") if kind is CandidateKind.TUNED else None
    return CandidateEvaluation(
        kind=kind,
        model="/models/base",
        model_revision="sha256:base-revision",
        adapter_path=identity,
        recipe_sha256="b" * 64 if kind is CandidateKind.TUNED else None,
        case_ids=("ko", "code"),
        scores=(score, score),
        environment={"python": "3.13"},
    )


def test_evaluation_pair_rejects_training_case(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)
    dataset_path = dataset.path
    payload = dataset.model_dump(mode="json")
    payload["case_ids"] = ("training", "ko")
    korean_case = dataset_path.read_text(encoding="utf-8").splitlines()[0]
    _ = dataset_path.write_text(
        '{"id":"training","prompt":"train","forbidden_for_training":false}\n' + korean_case + "\n",
        encoding="utf-8",
    )
    _write_freeze(dataset_path, row_count=2)
    changed = dataset.model_validate(
        payload
        | {
            "sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        },
    )
    pair = EvaluationPair(
        dataset=changed,
        base=_candidate(CandidateKind.BASE, 0.5).model_copy(update={"case_ids": changed.case_ids}),
        tuned=_candidate(CandidateKind.TUNED, 0.75).model_copy(update={"case_ids": changed.case_ids}),
    )

    with pytest.raises(EvaluationError, match="forbidden for training"):
        _ = evaluation_pair_sha256(pair)


def test_evaluation_pair_rejects_case_mismatch(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)
    base = _candidate(CandidateKind.BASE, 0.5).model_copy(update={"case_ids": ("ko",)})
    pair = EvaluationPair(
        dataset=dataset,
        base=base,
        tuned=_candidate(CandidateKind.TUNED, 0.75),
    )

    with pytest.raises(EvaluationError, match="same held-out cases"):
        _ = evaluation_pair_sha256(pair)


def test_evaluation_pair_hash_excludes_scores(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)
    first = EvaluationPair(
        dataset=dataset,
        base=_candidate(CandidateKind.BASE, 0.5),
        tuned=_candidate(CandidateKind.TUNED, 0.75),
    )
    second = EvaluationPair(
        dataset=dataset,
        base=_candidate(CandidateKind.BASE, 0.51),
        tuned=_candidate(CandidateKind.TUNED, 0.76),
    )

    assert evaluation_pair_sha256(first) == evaluation_pair_sha256(second)


def test_load_evaluation_pair_rejects_wrong_provenance(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)
    pair = EvaluationPair(
        dataset=dataset,
        base=_candidate(CandidateKind.BASE, 0.5),
        tuned=_candidate(
            CandidateKind.TUNED,
            0.75,
        ).model_copy(update={"model_revision": "sha256:other-revision"}),
    )
    path = tmp_path / "evaluation.json"
    _ = path.write_text(pair.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(EvaluationError, match="same base model revision"):
        _ = load_evaluation_pair(path, model="/models/base", model_revision="sha256:base-revision")


def test_fused_artifact_uses_evaluation_pair_hash(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)
    pair = EvaluationPair(
        dataset=dataset,
        base=_candidate(CandidateKind.BASE, 0.5),
        tuned=_candidate(CandidateKind.TUNED, 0.75),
    )
    path = tmp_path / "evaluation.json"
    _ = path.write_text(pair.model_dump_json(indent=2), encoding="utf-8")
    resolved = ResolvedTrainingRecipe(
        command=("python",),
        dataset_sha256="a" * 64,
        dataset_record_count=10,
        train_path=tmp_path / "train.jsonl",
        valid_path=tmp_path / "valid.jsonl",
        adapter_path=Path("adapter"),
        data_dir=tmp_path / "data",
        iterations=2,
        base_model="/models/base",
        base_revision="sha256:base-revision",
        recipe_sha256="b" * 64,
        environment={"python": "3.13"},
        evaluation_sha256="c" * 64,
    )
    training = TrainingRunResult(
        status=TrainingRunStatus.SUCCESS,
        return_code=0,
        dataset_sha256=resolved.dataset_sha256,
        adapter_path=resolved.adapter_path,
        data_dir=resolved.data_dir,
        iterations=resolved.iterations,
        stdout="",
        stderr="",
        base_model=resolved.base_model,
        base_revision=resolved.base_revision,
        recipe_sha256=resolved.recipe_sha256,
        environment=resolved.environment,
        evaluation_sha256=resolved.evaluation_sha256,
    )

    fused = fuse_training_artifact(
        training,
        output_path=tmp_path / "fused",
        evaluation_path=path,
    )

    assert fused.evaluation_sha256 == evaluation_pair_sha256(pair)


def test_merge_cli_rejects_recipe_mismatch(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)
    pair = EvaluationPair(
        dataset=dataset,
        base=_candidate(CandidateKind.BASE, 0.5),
        tuned=_candidate(CandidateKind.TUNED, 0.75).model_copy(update={"recipe_sha256": "d" * 64}),
    )
    path = tmp_path / "evaluation.json"
    _ = path.write_text(pair.model_dump_json(indent=2), encoding="utf-8")
    training = TrainingRunResult(
        status=TrainingRunStatus.SUCCESS,
        return_code=0,
        dataset_sha256="a" * 64,
        adapter_path=Path("adapter"),
        data_dir=tmp_path / "data",
        iterations=2,
        stdout="",
        stderr="",
        base_model="/models/base",
        base_revision="sha256:base-revision",
        recipe_sha256="b" * 64,
        environment={"python": "3.13"},
        evaluation_sha256="c" * 64,
    )
    training_path = tmp_path / "training_result.json"
    _ = training_path.write_text(training.model_dump_json(indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "merge",
            "--run",
            str(training_path),
            "--output",
            str(tmp_path / "fused"),
            "--evaluation",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src"},
    )

    assert result.returncode == 2


def test_evaluate_candidates_builds_typed_base_tuned_pair(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path)

    def inference(case: EvaluationCase, kind: CandidateKind) -> str:
        if kind is CandidateKind.BASE:
            return "wrong"
        return case.expected_output or " ".join(case.expected_keywords)

    pair = evaluate_candidates(
        dataset=dataset,
        model="/models/base",
        model_revision="sha256:base-revision",
        adapter_path=Path("adapter"),
        recipe_sha256="b" * 64,
        environment={"python": "3.13"},
        inference=inference,
    )

    assert pair.base.scores == (0.0, 0.0)
    assert pair.tuned.scores == (1.0, 1.0)
    assert evaluation_pair_sha256(pair)
