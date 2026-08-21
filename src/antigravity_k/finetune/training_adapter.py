from __future__ import annotations

import logging
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from antigravity_k.finetune.training_recipe import ResolvedTrainingRecipe

logger = logging.getLogger("agk.finetune")


class TrainingRunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class TrainingRunResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    status: TrainingRunStatus
    return_code: int
    dataset_sha256: str
    adapter_path: Path
    data_dir: Path
    iterations: int = Field(ge=1)
    stdout: str
    stderr: str
    base_model: str
    base_revision: str
    recipe_sha256: str
    environment: dict[str, str]
    evaluation_sha256: str
    resume_adapter_path: Path | None = None
    resume_source_sha256: str | None = None


def run_resolved_training(
    resolved: ResolvedTrainingRecipe,
    *,
    cwd: Path | None = None,
) -> TrainingRunResult:
    data_dir = resolved.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    _stage_file(resolved.train_path, data_dir / "train.jsonl")
    _stage_file(resolved.valid_path, data_dir / "valid.jsonl")
    resolved.adapter_path.mkdir(parents=True, exist_ok=True)
    command = resolved.command
    process = subprocess.run(
        command,
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    status = TrainingRunStatus.SUCCESS if process.returncode == 0 else TrainingRunStatus.FAILED
    result = TrainingRunResult(
        status=status,
        return_code=process.returncode,
        dataset_sha256=resolved.dataset_sha256,
        adapter_path=resolved.adapter_path,
        data_dir=data_dir,
        iterations=resolved.iterations,
        stdout=process.stdout,
        stderr=process.stderr,
        base_model=resolved.base_model,
        base_revision=resolved.base_revision,
        recipe_sha256=resolved.recipe_sha256,
        environment=resolved.environment,
        evaluation_sha256=resolved.evaluation_sha256,
        resume_adapter_path=resolved.resume_adapter_path,
        resume_source_sha256=resolved.resume_source_sha256,
    )
    _ = (resolved.adapter_path.parent / "training_result.json").write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "MLX 학습 종료: status=%s return_code=%s dataset=%s",
        status.value,
        process.returncode,
        resolved.dataset_sha256,
    )
    return result


def _stage_file(source: Path, destination: Path) -> None:
    _ = destination.write_bytes(source.read_bytes())
