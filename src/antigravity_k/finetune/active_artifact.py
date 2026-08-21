from __future__ import annotations

import fcntl
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, final, override

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from antigravity_k.finetune.artifact_lifecycle import FusedArtifactResult, FusedArtifactStatus


@final
class ActiveArtifactError(ValueError):
    __slots__: ClassVar[tuple[str, ...]] = ("reason",)
    reason: str

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

    @override
    def __str__(self) -> str:
        return self.reason


class ActiveArtifactStatus(StrEnum):
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"


class ArtifactPromotionContract(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    recipe_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActiveArtifactState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    status: ActiveArtifactStatus
    base_model: str = Field(min_length=1)
    base_revision: str = Field(min_length=1)
    output_path: Path
    recipe_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    promotion_revision: int = Field(ge=1)
    previous_output_path: Path | None = None


_artifact_adapter: TypeAdapter[FusedArtifactResult] = TypeAdapter(FusedArtifactResult)
_state_adapter: TypeAdapter[ActiveArtifactState] = TypeAdapter(ActiveArtifactState)


def read_active_artifact(state_path: Path) -> ActiveArtifactState:
    try:
        state = _state_adapter.validate_json(state_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ActiveArtifactError(f"Invalid active artifact state at {state_path}: {error}") from error
    except FileNotFoundError as error:
        raise ActiveArtifactError(f"Active artifact state is required at {state_path}.") from error
    if state.status is not ActiveArtifactStatus.ACTIVE:
        raise ActiveArtifactError("Active artifact state must be active.")
    return state


def promote_artifact(
    artifact_path: Path,
    *,
    state_path: Path,
    contract: ArtifactPromotionContract,
) -> ActiveArtifactState:
    with _state_lock(state_path):
        previous = _read_optional_state(state_path)
        artifact = _load_artifact(artifact_path)
        _validate_artifact(artifact, artifact_path=artifact_path, contract=contract)
        state = ActiveArtifactState(
            status=ActiveArtifactStatus.ACTIVE,
            base_model=artifact.base_model,
            base_revision=artifact.base_revision,
            output_path=artifact_path,
            recipe_sha256=artifact.recipe_sha256,
            evaluation_sha256=artifact.evaluation_sha256,
            promotion_revision=1 if previous is None else previous.promotion_revision + 1,
            previous_output_path=None if previous is None else previous.output_path,
        )
        _write_state_atomic(state_path, state)
        return state


def rollback_active_artifact(state_path: Path) -> ActiveArtifactState:
    with _state_lock(state_path):
        current = read_active_artifact(state_path)
        if current.previous_output_path is None:
            raise ActiveArtifactError("No previous artifact is available for rollback.")
        previous_path = current.previous_output_path
        artifact = _load_artifact(previous_path)
        _validate_artifact(
            artifact,
            artifact_path=previous_path,
            contract=ArtifactPromotionContract(
                recipe_sha256=artifact.recipe_sha256,
                evaluation_sha256=artifact.evaluation_sha256,
            ),
        )
        state = ActiveArtifactState(
            status=ActiveArtifactStatus.ACTIVE,
            base_model=artifact.base_model,
            base_revision=artifact.base_revision,
            output_path=previous_path,
            recipe_sha256=artifact.recipe_sha256,
            evaluation_sha256=artifact.evaluation_sha256,
            promotion_revision=current.promotion_revision + 1,
        )
        _write_state_atomic(state_path, state)
        return state


def _read_optional_state(state_path: Path) -> ActiveArtifactState | None:
    if not state_path.exists():
        return None
    return read_active_artifact(state_path)


def _load_artifact(artifact_path: Path) -> FusedArtifactResult:
    manifest_path = artifact_path / "artifact_manifest.json"
    try:
        return _artifact_adapter.validate_json(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ActiveArtifactError(f"Artifact manifest is required at {manifest_path}.") from error
    except ValueError as error:
        raise ActiveArtifactError(f"Invalid artifact manifest at {manifest_path}: {error}") from error


def _validate_artifact(
    artifact: FusedArtifactResult,
    *,
    artifact_path: Path,
    contract: ArtifactPromotionContract,
) -> None:
    if artifact.status is not FusedArtifactStatus.SUCCESS:
        raise ActiveArtifactError("Successful artifact is required for promotion.")
    if artifact.output_path.resolve() != artifact_path.resolve():
        raise ActiveArtifactError("Artifact manifest output path does not match the promoted directory.")
    if artifact.recipe_sha256 != contract.recipe_sha256:
        raise ActiveArtifactError("Artifact recipe provenance does not match the promotion contract.")
    if artifact.evaluation_sha256 != contract.evaluation_sha256:
        raise ActiveArtifactError("Artifact evaluation provenance does not match the promotion contract.")


@contextmanager
def _state_lock(state_path: Path) -> Generator[None]:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state_path.with_suffix(f"{state_path.suffix}.lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _write_state_atomic(state_path: Path, state: ActiveArtifactState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=state_path.parent,
        prefix=f".{state_path.name}.",
        delete=False,
    ) as temporary:
        temporary_name = temporary.name
        _ = temporary.write(state.model_dump_json(indent=2) + "\n")
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        os.replace(temporary_name, state_path)
    except OSError:
        os.unlink(temporary_name)
        raise
