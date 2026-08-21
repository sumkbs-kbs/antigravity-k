from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from antigravity_k.finetune.active_artifact import (
    ActiveArtifactError,
    ActiveArtifactState,
    ActiveArtifactStatus,
    ArtifactPromotionContract,
    promote_artifact,
    read_active_artifact,
    rollback_active_artifact,
    validate_active_artifact_output,
)
from antigravity_k.finetune.artifact_lifecycle import (
    FusedArtifactResult,
    FusedArtifactStatus,
)


def _artifact(output_path: Path, recipe_sha256: str = "b" * 64) -> FusedArtifactResult:
    return FusedArtifactResult(
        status=FusedArtifactStatus.SUCCESS,
        return_code=0,
        base_model="/models/base",
        base_revision="sha256:base-revision",
        adapter_path=Path("adapter"),
        output_path=output_path,
        dataset_sha256="a" * 64,
        recipe_sha256=recipe_sha256,
        environment={"python": "3.13"},
        evaluation_sha256="c" * 64,
        iterations=2,
        stdout="",
        stderr="",
    )


def _write_artifact(root: Path, name: str, recipe_sha256: str = "b" * 64) -> Path:
    output_path = root / name
    output_path.mkdir(parents=True)
    _ = (output_path / "artifact_manifest.json").write_text(
        _artifact(output_path, recipe_sha256).model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def test_promotion_writes_validated_active_pointer_atomically(tmp_path: Path) -> None:
    artifact_path = _write_artifact(tmp_path, "candidate")
    state_path = tmp_path / "active.json"

    promoted = promote_artifact(
        artifact_path,
        state_path=state_path,
        contract=ArtifactPromotionContract(
            recipe_sha256="b" * 64,
            evaluation_sha256="c" * 64,
        ),
    )
    saved = read_active_artifact(state_path)

    assert promoted == saved
    assert promoted.status is ActiveArtifactStatus.ACTIVE
    assert promoted.base_model == "/models/base"
    assert promoted.output_path == artifact_path
    assert promoted.previous_output_path is None
    assert list(state_path.parent.glob(f".{state_path.name}.*")) == []


def test_promotion_rejects_missing_manifest_without_state_change(tmp_path: Path) -> None:
    state_path = tmp_path / "active.json"

    with pytest.raises(ActiveArtifactError, match="Artifact manifest is required"):
        _ = promote_artifact(
            tmp_path / "missing",
            state_path=state_path,
            contract=ArtifactPromotionContract(
                recipe_sha256="b" * 64,
                evaluation_sha256="c" * 64,
            ),
        )

    assert not state_path.exists()


def test_promotion_rejects_provenance_mismatch(tmp_path: Path) -> None:
    artifact_path = _write_artifact(tmp_path, "candidate")

    with pytest.raises(ActiveArtifactError, match="recipe provenance"):
        _ = promote_artifact(
            artifact_path,
            state_path=tmp_path / "active.json",
            contract=ArtifactPromotionContract(
                recipe_sha256="d" * 64,
                evaluation_sha256="c" * 64,
            ),
        )


def test_promotion_rejects_failed_artifact_and_maintains_previous_pointer(
    tmp_path: Path,
) -> None:
    previous = _write_artifact(tmp_path, "previous", "d" * 64)
    state_path = tmp_path / "active.json"
    original = promote_artifact(
        previous,
        state_path=state_path,
        contract=ArtifactPromotionContract(
            recipe_sha256="d" * 64,
            evaluation_sha256="c" * 64,
        ),
    )
    candidate = _write_artifact(tmp_path, "candidate")
    candidate_manifest = candidate / "artifact_manifest.json"
    failed = _artifact(candidate).model_dump(mode="json")
    failed["status"] = FusedArtifactStatus.FAILED.value
    _ = candidate_manifest.write_text(
        FusedArtifactResult.model_validate(failed).model_dump_json(indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ActiveArtifactError, match="Successful artifact"):
        _ = promote_artifact(
            candidate,
            state_path=state_path,
            contract=ArtifactPromotionContract(
                recipe_sha256="b" * 64,
                evaluation_sha256="c" * 64,
            ),
        )

    assert read_active_artifact(state_path) == original


def test_promotion_and_rollback_preserve_previous_candidate(tmp_path: Path) -> None:
    first = _write_artifact(tmp_path, "first", "d" * 64)
    second = _write_artifact(tmp_path, "second")
    state_path = tmp_path / "active.json"
    _ = promote_artifact(
        first,
        state_path=state_path,
        contract=ArtifactPromotionContract(
            recipe_sha256="d" * 64,
            evaluation_sha256="c" * 64,
        ),
    )
    promoted = promote_artifact(
        second,
        state_path=state_path,
        contract=ArtifactPromotionContract(
            recipe_sha256="b" * 64,
            evaluation_sha256="c" * 64,
        ),
    )

    rolled_back = rollback_active_artifact(state_path)

    assert promoted.previous_output_path == first
    assert rolled_back.status is ActiveArtifactStatus.ACTIVE
    assert rolled_back.output_path == first
    assert rolled_back.previous_output_path is None
    assert read_active_artifact(state_path) == rolled_back


def test_rollback_rejects_initial_active_pointer(tmp_path: Path) -> None:
    artifact_path = _write_artifact(tmp_path, "candidate")
    state_path = tmp_path / "active.json"
    _ = promote_artifact(
        artifact_path,
        state_path=state_path,
        contract=ArtifactPromotionContract(
            recipe_sha256="b" * 64,
            evaluation_sha256="c" * 64,
        ),
    )

    with pytest.raises(ActiveArtifactError, match="No previous artifact"):
        _ = rollback_active_artifact(state_path)


def test_read_active_artifact_rejects_tampered_pointer(tmp_path: Path) -> None:
    state_path = tmp_path / "active.json"
    _ = state_path.write_text('{"status": "active"}', encoding="utf-8")

    with pytest.raises(ActiveArtifactError, match="Invalid active artifact state"):
        _ = read_active_artifact(state_path)


def test_read_active_artifact_rejects_directory_state_path_without_detail(tmp_path: Path) -> None:
    # Given: a directory is supplied where the active JSON state file is required.
    state_path = tmp_path / "active-state"
    state_path.mkdir()

    # When: the active state boundary is read.
    with pytest.raises(ActiveArtifactError, match="Active artifact state is unavailable"):
        _ = read_active_artifact(state_path)


def test_validated_active_artifact_output_rejects_symlink(tmp_path: Path) -> None:
    # Given: a valid fused artifact is addressed through a directory symlink.
    artifact_path = _write_artifact(tmp_path, "candidate")
    symlink_path = tmp_path / "candidate-link"
    symlink_path.symlink_to(artifact_path, target_is_directory=True)
    state = ActiveArtifactState(
        status=ActiveArtifactStatus.ACTIVE,
        base_model="/models/base",
        base_revision="sha256:base-revision",
        output_path=symlink_path,
        recipe_sha256="b" * 64,
        evaluation_sha256="c" * 64,
        promotion_revision=1,
    )

    # When: the active output is validated.
    with pytest.raises(ActiveArtifactError, match="Active artifact output is unavailable"):
        _ = validate_active_artifact_output(state)


def test_concurrent_promotions_produce_one_exact_winner(tmp_path: Path) -> None:
    first = _write_artifact(tmp_path, "first", "d" * 64)
    second = _write_artifact(tmp_path, "second")
    state_path = tmp_path / "active.json"
    contracts = {
        first: ArtifactPromotionContract(
            recipe_sha256="d" * 64,
            evaluation_sha256="c" * 64,
        ),
        second: ArtifactPromotionContract(
            recipe_sha256="b" * 64,
            evaluation_sha256="c" * 64,
        ),
    }

    with ThreadPoolExecutor(max_workers=2) as executor:

        def promote(artifact: Path) -> ActiveArtifactState:
            return promote_artifact(
                artifact,
                state_path=state_path,
                contract=contracts[artifact],
            )

        promotions = list(
            executor.map(
                promote,
                (first, second),
            ),
        )
    saved = read_active_artifact(state_path)

    assert saved in promotions
    assert {item.output_path for item in promotions} == {first, second}
    assert {item.promotion_revision for item in promotions} == {1, 2}
    assert saved.previous_output_path in {first, second} - {saved.output_path}


def test_promote_cli_and_rollback_cli_use_real_entrypoint(tmp_path: Path) -> None:
    artifact_path = _write_artifact(tmp_path, "candidate")
    state_path = tmp_path / "active.json"
    command = [
        sys.executable,
        "-m",
        "antigravity_k.finetune.trainer",
        "promote",
        "--artifact",
        str(artifact_path),
        "--state",
        str(state_path),
        "--recipe-sha256",
        "b" * 64,
        "--evaluation-sha256",
        "c" * 64,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": "src"},
    )
    saved = ActiveArtifactState.model_validate_json(result.stdout)

    assert result.returncode == 0
    assert saved.output_path == artifact_path
    assert read_active_artifact(state_path) == saved

    rollback = subprocess.run(
        [
            sys.executable,
            "-m",
            "antigravity_k.finetune.trainer",
            "rollback",
            "--state",
            str(state_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"PYTHONPATH": "src"},
    )

    assert rollback.returncode == 2
    assert b"No previous artifact" in rollback.stderr.encode("utf-8")
