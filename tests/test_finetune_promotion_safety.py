from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from antigravity_k.finetune.active_artifact import read_active_artifact
from antigravity_k.finetune.artifact_lifecycle import FusedArtifactResult, FusedArtifactStatus
from antigravity_k.finetune.evaluation_gate import PromotionDecision


def _write_artifact(root: Path, name: str, recipe_sha256: str) -> Path:
    output_path = root / name
    output_path.mkdir()
    artifact = FusedArtifactResult(
        status=FusedArtifactStatus.SUCCESS,
        return_code=0,
        base_model="/models/base",
        base_revision="sha256:base-revision",
        adapter_path=Path("adapter"),
        output_path=output_path,
        dataset_sha256="a" * 64,
        recipe_sha256=recipe_sha256,
        environment={"python": "3.13", "backend": "mlx"},
        evaluation_sha256="c" * 64,
        iterations=2,
        stdout="",
        stderr="",
    )
    _ = (output_path / "artifact_manifest.json").write_text(
        artifact.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _write_decision(root: Path, name: str, recipe_sha256: str, *, eligible: bool = True) -> Path:
    path = root / f"{name}.decision.json"
    categories = ("long_horizon", "verified_code", "tool_recovery", "korean_reasoning")
    payload = {
        "schema_version": 3,
        "artifact_type": "promotion_decision",
        "model": "active-local",
        "evaluated_model": "/models/base",
        "model_revision": "sha256:base-revision",
        "recipe_sha256": recipe_sha256,
        "evaluation_pair_sha256": "c" * 64,
        "evaluation_sha256": "e" * 64,
        "dataset_sha256": "a" * 64,
        "policy": {
            "schema_version": 1,
            "approved_dataset_sha256": "a" * 64,
            "required_categories": list(categories),
            "minimum_category_score": 0.5,
            "maximum_category_regression": 0.0,
            "minimum_overall_improvement": 0.01,
            "minimum_case_count": 4,
        },
        "categories": [
            {
                "category": category,
                "case_ids": [f"{category}-case"],
                "base_score": 0.5 if eligible else 1.0,
                "tuned_score": 1.0 if eligible else 0.0,
                "delta": 0.5 if eligible else -1.0,
                "passed": eligible,
            }
            for category in categories
        ],
        "missing_categories": [],
        "base_score": 0.5 if eligible else 1.0,
        "tuned_score": 1.0 if eligible else 0.0,
        "delta": 0.5 if eligible else -1.0,
        "statistical_evidence": {
            "confidence_level": 0.95,
            "observation_count": 4,
            "paired_deltas": [0.5 if eligible else -1.0] * 4,
            "mean_delta": 0.5 if eligible else -1.0,
            "standard_error": 0.0,
            "confidence_lower_bound": 0.5 if eligible else -1.0,
            "confidence_upper_bound": 0.5 if eligible else -1.0,
        },
        "eligible": eligible,
        "reasons": [] if eligible else ["category regression: long_horizon"],
        "results": [
            {
                "case_id": category,
                "quality_score": 1.0 if eligible else 0.0,
                "benchmark_score": 1.0 if eligible else 0.0,
                "quality_grade": "excellent" if eligible else "fail",
                "error": "" if eligible else "category regression: long_horizon",
            }
            for category in categories
        ],
    }
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_fake_mlx(root: Path) -> Path:
    module_root = root / "fake-runtime"
    module_root.mkdir()
    _ = (module_root / "mlx_lm.py").write_text(
        "\n".join(
            (
                "from pathlib import Path",
                "import os",
                "",
                "def load(*, path_or_hf_repo, revision=None, adapter_path=None):",
                "    marker = os.environ.get('AGK_PROBE_MARKER')",
                "    if marker:",
                "        Path(marker).write_text(path_or_hf_repo, encoding='utf-8')",
                "    return object(), object()",
                "",
                "def generate(model, tokenizer, *, prompt, max_tokens, sampler):",
                "    return '' if os.environ.get('AGK_PROBE_FAIL') == '1' else 'probe-ok'",
                "",
            ),
        ),
        encoding="utf-8",
    )
    return module_root


def _promote_command(artifact: Path, state: Path, decision: Path, recipe_sha256: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "antigravity_k.finetune.trainer",
        "promote",
        "--artifact",
        str(artifact),
        "--state",
        str(state),
        "--decision",
        str(decision),
        "--recipe-sha256",
        recipe_sha256,
        "--evaluation-sha256",
        "c" * 64,
    ]


def test_cli_probe_failure_restores_previous_active_artifact(tmp_path: Path) -> None:
    runtime = _write_fake_mlx(tmp_path)
    state_path = tmp_path / "active.json"
    first_recipe = "b" * 64
    second_recipe = "d" * 64
    first = _write_artifact(tmp_path, "first", first_recipe)
    second = _write_artifact(tmp_path, "second", second_recipe)
    environment = os.environ | {"PYTHONPATH": f"{runtime}:src"}

    first_result = subprocess.run(
        _promote_command(first, state_path, _write_decision(tmp_path, "first", first_recipe), first_recipe),
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    previous = read_active_artifact(state_path)
    failed_result = subprocess.run(
        _promote_command(second, state_path, _write_decision(tmp_path, "second", second_recipe), second_recipe),
        capture_output=True,
        text=True,
        check=False,
        env=environment | {"AGK_PROBE_FAIL": "1"},
    )

    assert first_result.returncode == 0, first_result.stderr
    assert json.loads(first_result.stdout)["status"] == "active"
    assert failed_result.returncode == 4, failed_result.stderr
    assert json.loads(failed_result.stdout)["status"] == "rolled_back"
    assert read_active_artifact(state_path) == previous
    assert previous.output_path == first


def test_cli_ineligible_decision_is_rejected_before_runtime_probe(tmp_path: Path) -> None:
    runtime = _write_fake_mlx(tmp_path)
    marker = tmp_path / "probe.marker"
    recipe_sha256 = "b" * 64
    artifact = _write_artifact(tmp_path, "candidate", recipe_sha256)
    decision = _write_decision(tmp_path, "candidate", recipe_sha256, eligible=False)

    result = subprocess.run(
        _promote_command(artifact, tmp_path / "active.json", decision, recipe_sha256),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ
        | {
            "PYTHONPATH": f"{runtime}:src",
            "AGK_PROBE_MARKER": str(marker),
        },
    )

    assert result.returncode == 2
    assert "not eligible" in result.stderr
    assert not marker.exists()


def test_cli_initial_probe_failure_leaves_no_active_pointer(tmp_path: Path) -> None:
    runtime = _write_fake_mlx(tmp_path)
    recipe_sha256 = "b" * 64
    artifact = _write_artifact(tmp_path, "candidate", recipe_sha256)
    decision = _write_decision(tmp_path, "candidate", recipe_sha256)
    state_path = tmp_path / "active.json"

    result = subprocess.run(
        _promote_command(artifact, state_path, decision, recipe_sha256),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": f"{runtime}:src", "AGK_PROBE_FAIL": "1"},
    )

    assert result.returncode == 4
    assert json.loads(result.stdout)["active"] is None
    assert not state_path.exists()


def test_cli_stale_decision_provenance_is_rejected_before_probe(tmp_path: Path) -> None:
    runtime = _write_fake_mlx(tmp_path)
    marker = tmp_path / "probe.marker"
    recipe_sha256 = "b" * 64
    artifact = _write_artifact(tmp_path, "candidate", recipe_sha256)
    decision = _write_decision(tmp_path, "candidate", recipe_sha256)
    stale = PromotionDecision.model_validate_json(decision.read_text(encoding="utf-8")).model_copy(
        update={"evaluation_pair_sha256": "d" * 64},
    )
    _ = decision.write_text(stale.model_dump_json(), encoding="utf-8")

    result = subprocess.run(
        _promote_command(artifact, tmp_path / "active.json", decision, recipe_sha256),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ
        | {
            "PYTHONPATH": f"{runtime}:src",
            "AGK_PROBE_MARKER": str(marker),
        },
    )

    assert result.returncode == 2
    assert "evaluation provenance" in result.stderr
    assert not marker.exists()


def test_cli_internally_inconsistent_eligible_decision_is_rejected(tmp_path: Path) -> None:
    runtime = _write_fake_mlx(tmp_path)
    marker = tmp_path / "probe.marker"
    recipe_sha256 = "b" * 64
    artifact = _write_artifact(tmp_path, "candidate", recipe_sha256)
    decision = _write_decision(tmp_path, "candidate", recipe_sha256)
    parsed = PromotionDecision.model_validate_json(decision.read_text(encoding="utf-8"))
    tampered = parsed.model_copy(
        update={
            "categories": (
                parsed.categories[0].model_copy(update={"passed": False}),
                *parsed.categories[1:],
            ),
        },
    )
    _ = decision.write_text(tampered.model_dump_json(), encoding="utf-8")

    result = subprocess.run(
        _promote_command(artifact, tmp_path / "active.json", decision, recipe_sha256),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ
        | {
            "PYTHONPATH": f"{runtime}:src",
            "AGK_PROBE_MARKER": str(marker),
        },
    )

    assert result.returncode == 2
    assert "Invalid promotion decision" in result.stderr
    assert not marker.exists()
