"""Run a reproducible paired comparison between a local and frontier model.

How to run:
    uv run python scripts/run_frontier_comparison.py
    uv run python scripts/run_frontier_comparison.py --frontier openai/gpt-4o-mini
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from antigravity_k.engine.benchmark_cases import BenchmarkCase, get_suite
from antigravity_k.engine.benchmark_harness import BenchmarkHarness, BenchmarkResult
from antigravity_k.engine.frontier_evidence import (
    FrontierEvidence,
    FrontierEvidencePolicy,
    FrontierHarnessConfig,
    FrontierObservation,
    build_frontier_evidence,
)
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.quality_gate import QualityGate


class UnknownBenchmarkCaseError(KeyError):
    def __init__(self, case_ids: tuple[str, ...]):
        self.case_ids: tuple[str, ...] = case_ids
        super().__init__(", ".join(case_ids))


class BenchmarkExecutionError(RuntimeError):
    def __init__(self, result: BenchmarkResult):
        self.case_id: str = result.case_id
        self.target: str = result.target
        self.detail: str = result.error or "empty benchmark output"
        super().__init__(f"{result.case_id} × {result.target}: {self.detail}")


@dataclass(frozen=True, slots=True)
class ScoreResult:
    score: float
    grade: str
    latency_ms: float


@dataclass(frozen=True, slots=True)
class ComparisonPlan:
    local_model: str
    frontier_model: str
    cases: tuple[BenchmarkCase, ...]
    harness: FrontierHarnessConfig


@dataclass(frozen=True, slots=True)
class ComparisonCliArgs:
    local_model: str
    frontier_model: str
    case_ids: tuple[str, ...]
    repetitions: int
    seed: int
    maximum_gap: float
    output: Path


class ScoreProvider(Protocol):
    def score(self, case_id: str, target: str) -> ScoreResult: ...


class HarnessScoreProvider:
    def __init__(self, manager: ModelManager):
        self._manager: ModelManager = manager

    def score(self, case_id: str, target: str) -> ScoreResult:
        harness = BenchmarkHarness(
            self._manager,
            quality_gate=QualityGate(max_retries=0),
            db_path=None,
        )
        output = harness.compare_amplification([case_id], target, modes=["revision_off"])
        result = output["by_case"][case_id]["revision_off"]
        return require_successful_score(result)


def require_successful_score(result: BenchmarkResult) -> ScoreResult:
    if result.error or "empty_output" in result.issues:
        raise BenchmarkExecutionError(result)
    return ScoreResult(
        score=result.benchmark_score,
        grade=result.quality_grade,
        latency_ms=result.latency_ms,
    )


def collect_observations(plan: ComparisonPlan, scorer: ScoreProvider) -> tuple[FrontierObservation, ...]:
    observations: list[FrontierObservation] = []
    for repetition in range(plan.harness.repetitions):
        for case_index, case in enumerate(plan.cases):
            local_first = (repetition + case_index + plan.harness.seed) % 2 == 0
            if local_first:
                local = scorer.score(case.id, plan.local_model)
                frontier = scorer.score(case.id, plan.frontier_model)
            else:
                frontier = scorer.score(case.id, plan.frontier_model)
                local = scorer.score(case.id, plan.local_model)
            observations.append(
                FrontierObservation(
                    case_id=case.id,
                    repetition=repetition,
                    local_score=local.score,
                    frontier_score=frontier.score,
                    local_latency_ms=local.latency_ms,
                    frontier_latency_ms=frontier.latency_ms,
                )
            )
            gap = frontier.score - local.score
            print(f"repeat={repetition + 1} case={case.id} local={local.score:.3f} frontier={frontier.score:.3f} gap={gap:+.3f}")
    return tuple(observations)


def _parse_args() -> ComparisonCliArgs:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--local", default="qwen3.8", help="local model registry identifier")
    _ = parser.add_argument("--frontier", default="openai/gpt-4o-mini", help="frontier model identifier")
    _ = parser.add_argument("--cases", nargs="*", default=(), help="exact benchmark case IDs")
    _ = parser.add_argument("--repeats", type=int, default=3)
    _ = parser.add_argument("--seed", type=int, default=0)
    _ = parser.add_argument("--maximum-gap", type=float, default=0.05)
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmarks/frontier-comparison.json"),
    )
    values = parser.parse_args()
    return ComparisonCliArgs(
        local_model=cast(str, values.local),
        frontier_model=cast(str, values.frontier),
        case_ids=tuple(cast(list[str], values.cases)),
        repetitions=cast(int, values.repeats),
        seed=cast(int, values.seed),
        maximum_gap=cast(float, values.maximum_gap),
        output=cast(Path, values.output),
    )


def _resolve_cases(case_ids: tuple[str, ...]) -> tuple[BenchmarkCase, ...]:
    cases_by_id = {case.id: case for case in get_suite("all")}
    selected_ids = case_ids or tuple(case.id for case in get_suite("frontier"))
    unknown = tuple(case_id for case_id in selected_ids if case_id not in cases_by_id)
    if unknown:
        raise UnknownBenchmarkCaseError(unknown)
    return tuple(cases_by_id[case_id] for case_id in selected_ids)


def write_evidence_artifact(evidence: FrontierEvidence, output: Path) -> str:
    body = f"{evidence.model_dump_json(indent=2)}\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_text(body, encoding="utf-8")
    _ = output.with_suffix(f"{output.suffix}.sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
    )
    return digest


def main() -> int:
    args = _parse_args()
    cases = _resolve_cases(args.case_ids)
    harness = FrontierHarnessConfig(repetitions=args.repetitions, seed=args.seed)
    plan = ComparisonPlan(
        local_model=args.local_model,
        frontier_model=args.frontier_model,
        cases=cases,
        harness=harness,
    )
    observations = collect_observations(plan, HarnessScoreProvider(ModelManager(ModelRegistry())))
    evidence = build_frontier_evidence(
        local_model=plan.local_model,
        frontier_model=plan.frontier_model,
        cases=plan.cases,
        harness=plan.harness,
        observations=observations,
        policy=FrontierEvidencePolicy(maximum_acceptable_gap=args.maximum_gap),
    )
    evidence_sha256 = write_evidence_artifact(evidence, args.output)
    verdict = "PASS" if evidence.local_reaches_frontier else "FAIL"
    print(
        f"{verdict}: mean_gap={evidence.mean_gap:+.3f}, one_sided_95_upper={evidence.confidence_upper_bound:+.3f}, observations={evidence.observation_count}"
    )
    print(f"evidence={args.output} sha256={evidence_sha256}")
    return 0 if evidence.local_reaches_frontier else 2


if __name__ == "__main__":
    raise SystemExit(main())
