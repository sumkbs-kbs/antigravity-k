from __future__ import annotations

from enum import StrEnum
from importlib import import_module
from pathlib import Path
from typing import ClassVar, Protocol, final

from pydantic import BaseModel, ConfigDict, Field

from antigravity_k.finetune.evaluation_backends import MlxModule
from antigravity_k.finetune.evaluation_mlx_sampler import make_mlx_sampler


class RuntimeProbeStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class PromotionProbeTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    output_path: Path
    model_name: str = Field(min_length=1)


class RuntimeProbeResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    status: RuntimeProbeStatus
    backend: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class RuntimeProbe(Protocol):
    def __call__(self, target: PromotionProbeTarget) -> RuntimeProbeResult: ...


@final
class MlxFusedArtifactProbe:
    def __call__(self, target: PromotionProbeTarget) -> RuntimeProbeResult:
        try:
            module = import_module("mlx_lm")
            if not isinstance(module, MlxModule):
                return _failed(target, "MLX runtime API is incompatible.")
            loaded = module.load(path_or_hf_repo=str(target.output_path))
            output = module.generate(
                model=loaded[0],
                tokenizer=loaded[1],
                prompt="Return OK.",
                max_tokens=1,
                sampler=make_mlx_sampler(0.0),
            )
        except (ImportError, IndexError, OSError, RuntimeError, TypeError, ValueError) as error:
            return _failed(target, f"MLX runtime probe failed: {type(error).__name__}")
        if not output:
            return _failed(target, "MLX runtime probe returned no content.")
        return RuntimeProbeResult(
            status=RuntimeProbeStatus.PASSED,
            backend="mlx",
            model_name=target.model_name,
            detail="Fused artifact loaded and generated one token.",
        )


def _failed(target: PromotionProbeTarget, detail: str) -> RuntimeProbeResult:
    return RuntimeProbeResult(
        status=RuntimeProbeStatus.FAILED,
        backend="mlx",
        model_name=target.model_name,
        detail=detail,
    )
