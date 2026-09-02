from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from antigravity_k.engine.model_calibration import (
    ModelQualityCalibrationConfig,
    ModelQualityCalibrationStore,
)
from antigravity_k.finetune.evaluation import (
    CandidateEvaluation,
    CandidateKind,
    EvaluationDataset,
    EvaluationError,
    EvaluationPair,
)
from antigravity_k.finetune.evaluation_gate import (
    EvaluationCategory,
    PromotionDecision,
    PromotionGatePolicy,
    build_promotion_decision,
    promotion_decision_sha256,
)

_decision_adapter: TypeAdapter[PromotionDecision] = TypeAdapter(PromotionDecision)


def _write_dataset(root: Path, categories: tuple[str, ...]) -> EvaluationDataset:
    path = root / "held_out_v1.jsonl"
    rows = [
        {
            "id": f"case-{index}",
            "category": category,
            "prompt": f"prompt-{index}",
            "expected_keywords": [f"answer-{index}"],
            "forbidden_for_training": True,
        }
        for index, category in enumerate(categories)
    ]
    _ = path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _ = path.with_suffix(".freeze.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset_path": path.name,
                "sha256": digest,
                "row_count": len(rows),
            },
        )
        + "\n",
        encoding="utf-8",
    )
    return EvaluationDataset(
        path=path,
        sha256=digest,
        case_ids=tuple(f"case-{index}" for index in range(len(categories))),
    )


def _pair(dataset: EvaluationDataset, *, base: tuple[float, ...], tuned: tuple[float, ...]) -> EvaluationPair:
    return EvaluationPair(
        dataset=dataset,
        base=CandidateEvaluation(
            kind=CandidateKind.BASE,
            model="/models/base",
            model_revision="sha256:base-revision",
            case_ids=dataset.case_ids,
            scores=base,
            environment={"python": "3.13", "backend": "mlx"},
        ),
        tuned=CandidateEvaluation(
            kind=CandidateKind.TUNED,
            model="/models/base",
            model_revision="sha256:base-revision",
            adapter_path=Path("adapter"),
            recipe_sha256="b" * 64,
            case_ids=dataset.case_ids,
            scores=tuned,
            environment={"python": "3.13", "backend": "mlx"},
        ),
    )


def _four_categories() -> tuple[str, ...]:
    return tuple(member.value for member in EvaluationCategory)


def _policy_for(dataset: EvaluationDataset) -> PromotionGatePolicy:
    return PromotionGatePolicy(approved_dataset_sha256=dataset.sha256)


def test_gate_marks_improved_four_category_pair_eligible(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, _four_categories())
    pair = _pair(
        dataset,
        base=(0.5, 0.5, 0.5, 0.5),
        tuned=(1.0, 0.75, 1.0, 1.0),
    )

    decision = build_promotion_decision(pair, policy=_policy_for(dataset))

    assert decision.eligible is True
    assert decision.missing_categories == ()
    assert tuple(result.category for result in decision.categories) == tuple(EvaluationCategory)
    assert decision.base_score == 0.5
    assert decision.tuned_score == 0.9375
    assert decision.statistical_evidence.observation_count == 4
    assert decision.statistical_evidence.confidence_lower_bound > 0.01
    assert decision.evaluation_sha256
    assert promotion_decision_sha256(decision)


def test_gate_rejects_evaluation_below_minimum_case_count(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, _four_categories())
    pair = _pair(dataset, base=(0.0, 0.0, 0.0, 0.0), tuned=(1.0, 1.0, 1.0, 1.0))
    policy = PromotionGatePolicy(approved_dataset_sha256=dataset.sha256, minimum_case_count=5)

    decision = build_promotion_decision(pair, policy=policy)

    assert decision.eligible is False
    assert "insufficient evaluation cases: 4 < 5" in decision.reasons


def test_gate_rejects_noisy_gain_without_positive_confidence_bound(tmp_path: Path) -> None:
    categories = tuple(category for category in _four_categories() for _ in range(2))
    dataset = _write_dataset(tmp_path, categories)
    base = (0.5,) * 8
    tuned = (1.0, 0.1) * 4
    policy = PromotionGatePolicy(approved_dataset_sha256=dataset.sha256, minimum_case_count=8)

    decision = build_promotion_decision(_pair(dataset, base=base, tuned=tuned), policy=policy)

    assert decision.delta == 0.05
    assert decision.statistical_evidence.confidence_lower_bound < policy.minimum_overall_improvement
    assert "paired improvement confidence lower bound below minimum" in decision.reasons


def test_gate_records_missing_required_category_without_mutating_frozen_data(tmp_path: Path) -> None:
    present = tuple(member.value for member in EvaluationCategory if member is not EvaluationCategory.LONG_HORIZON)
    dataset = _write_dataset(tmp_path, present)
    pair = _pair(
        dataset,
        base=(0.0, 0.0, 0.0),
        tuned=(1.0, 1.0, 1.0),
    )

    decision = build_promotion_decision(pair, policy=_policy_for(dataset))

    assert decision.eligible is False
    assert decision.missing_categories == (EvaluationCategory.LONG_HORIZON,)
    assert "missing required categories: long_horizon" in decision.reasons


def test_gate_blocks_category_regression_even_when_overall_score_improves(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, _four_categories())
    pair = _pair(
        dataset,
        base=(1.0, 0.0, 0.0, 0.0),
        tuned=(0.0, 1.0, 1.0, 1.0),
    )

    decision = build_promotion_decision(pair, policy=_policy_for(dataset))

    assert decision.eligible is False
    assert decision.categories[0].passed is False
    assert "category regression: long_horizon" in decision.reasons
    decision_path = tmp_path / "rejected-decision.json"
    _ = decision_path.write_text(decision.model_dump_json(), encoding="utf-8")
    calibration = ModelQualityCalibrationStore.from_config(
        ModelQualityCalibrationConfig(enabled=True, artifact_paths=(decision_path,)),
        tmp_path,
    )
    assert calibration.is_eligible(decision.model) is False


def test_gate_rejects_base_tuned_environment_mismatch(tmp_path: Path) -> None:
    pair = _pair(
        _write_dataset(tmp_path, _four_categories()),
        base=(0.0, 0.0, 0.0, 0.0),
        tuned=(1.0, 1.0, 1.0, 1.0),
    )
    pair = pair.model_copy(
        update={"tuned": pair.tuned.model_copy(update={"environment": {"python": "3.12", "backend": "mlx"}})},
    )

    with pytest.raises(EvaluationError, match="same environment"):
        _ = build_promotion_decision(pair)


def test_gate_rejects_dataset_without_freeze_manifest(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, _four_categories())
    dataset.path.with_suffix(".freeze.json").unlink()
    pair = _pair(dataset, base=(0.0, 0.0, 0.0, 0.0), tuned=(1.0, 1.0, 1.0, 1.0))

    with pytest.raises(EvaluationError, match="freeze manifest"):
        _ = build_promotion_decision(pair)


def test_gate_blocks_self_rehashed_but_unapproved_dataset(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, _four_categories())
    pair = _pair(dataset, base=(0.0, 0.0, 0.0, 0.0), tuned=(1.0, 1.0, 1.0, 1.0))

    decision = build_promotion_decision(pair)

    assert decision.eligible is False
    assert "dataset digest is not approved by promotion policy" in decision.reasons


def test_evaluation_result_hash_binds_observed_scores(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path, _four_categories())
    first = build_promotion_decision(
        _pair(dataset, base=(0.0, 0.0, 0.0, 0.0), tuned=(1.0, 1.0, 1.0, 1.0)),
        policy=_policy_for(dataset),
    )
    second = build_promotion_decision(
        _pair(dataset, base=(0.25, 0.0, 0.0, 0.0), tuned=(1.0, 1.0, 1.0, 1.0)),
        policy=_policy_for(dataset),
    )

    assert first.evaluation_sha256 != second.evaluation_sha256


def test_shipped_v2_covers_all_promotion_categories() -> None:
    dataset_path = Path("data/benchmarks/held_out_v2.jsonl")
    case_ids = tuple(json.loads(line)["id"] for line in dataset_path.read_text(encoding="utf-8").splitlines() if line)
    dataset = EvaluationDataset(
        path=dataset_path,
        sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        case_ids=case_ids,
    )

    decision = build_promotion_decision(
        _pair(dataset, base=(0.0, 0.0, 0.0, 0.0), tuned=(1.0, 1.0, 1.0, 1.0)),
    )

    assert decision.eligible is True
    assert decision.dataset_sha256 == "cf202bd9360381270525d9801dcbb4fa1a3f6ec6491ccf6bfd57776dbe2acbde"


def test_evaluation_gate_cli_writes_typed_decision(tmp_path: Path) -> None:
    dataset_path = Path("data/benchmarks/held_out_v2.jsonl")
    case_ids = tuple(json.loads(line)["id"] for line in dataset_path.read_text(encoding="utf-8").splitlines() if line)
    dataset = EvaluationDataset(
        path=dataset_path,
        sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        case_ids=case_ids,
    )
    pair = _pair(
        dataset,
        base=(0.0, 0.0, 0.0, 0.0),
        tuned=(1.0, 1.0, 1.0, 1.0),
    )
    evaluation_path = tmp_path / "evaluation.json"
    decision_path = tmp_path / "promotion_decision.json"
    _ = evaluation_path.write_text(pair.model_dump_json(indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "evaluate-gate",
            "--evaluation",
            str(evaluation_path),
            "--output",
            str(decision_path),
            "--routing-model-name",
            "active-local",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src"},
    )

    assert result.returncode == 0, result.stderr
    decision = _decision_adapter.validate_json(decision_path.read_text(encoding="utf-8"))
    assert decision.eligible is True
    assert decision.model == "active-local"
    assert tuple(result.case_id for result in decision.results) == _four_categories()
    assert _decision_adapter.validate_json(result.stdout) == decision
    calibration = ModelQualityCalibrationStore.from_config(
        ModelQualityCalibrationConfig(enabled=True, artifact_paths=(decision_path,)),
        tmp_path,
    )
    assert calibration.is_eligible("active-local") is True
    assert calibration.summaries()[0].case_count == 4
