import hashlib
from pathlib import Path

import pytest

from antigravity_k.engine.benchmark_cases import BenchmarkCase
from antigravity_k.engine.benchmark_harness import BenchmarkResult
from antigravity_k.engine.frontier_evidence import (
    FrontierEvidencePolicy,
    FrontierHarnessConfig,
    FrontierObservation,
    build_frontier_evidence,
)
from scripts.run_frontier_comparison import (
    BenchmarkExecutionError,
    ComparisonPlan,
    ScoreResult,
    collect_observations,
    require_successful_score,
    write_evidence_artifact,
)


class RecordingScorer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def score(self, case_id: str, target: str) -> ScoreResult:
        self.calls.append((case_id, target))
        score = 0.8 if target == "local" else 0.82
        return ScoreResult(score=score, grade="excellent", latency_ms=10.0)


def test_collect_observations_pairs_every_case_and_repetition_and_balances_model_order() -> None:
    cases = (
        BenchmarkCase(id="case-1", category="simple", prompt="one", difficulty=1),
        BenchmarkCase(id="case-2", category="simple", prompt="two", difficulty=1),
    )
    plan = ComparisonPlan(
        local_model="local",
        frontier_model="frontier",
        cases=cases,
        harness=FrontierHarnessConfig(repetitions=2, seed=0),
    )
    scorer = RecordingScorer()

    observations = collect_observations(plan, scorer)

    assert [(item.case_id, item.repetition) for item in observations] == [
        ("case-1", 0),
        ("case-2", 0),
        ("case-1", 1),
        ("case-2", 1),
    ]
    assert scorer.calls[:2] == [("case-1", "local"), ("case-1", "frontier")]
    assert scorer.calls[-2:] == [("case-2", "local"), ("case-2", "frontier")]


@pytest.mark.parametrize(("error", "issues"), [("model not registered", []), ("", ["empty_output"])])
def test_require_successful_score_rejects_benchmark_execution_failures(error: str, issues: list[str]) -> None:
    result = BenchmarkResult(
        case_id="case-1",
        target="qwen3.8",
        quality_score=0.0,
        quality_grade="fail",
        latency_ms=1.0,
        tokens_in=1,
        tokens_out=0,
        output_preview="",
        timestamp=0.0,
        issues=issues,
        error=error,
    )

    with pytest.raises(BenchmarkExecutionError, match="case-1"):
        require_successful_score(result)


def test_write_evidence_artifact_companion_matches_written_bytes(tmp_path: Path) -> None:
    case = BenchmarkCase(id="case-1", category="simple", prompt="one", difficulty=1)
    observation = FrontierObservation(
        case_id=case.id,
        repetition=0,
        local_score=0.8,
        frontier_score=0.8,
        local_latency_ms=10,
        frontier_latency_ms=10,
    )
    evidence = build_frontier_evidence(
        local_model="local",
        frontier_model="frontier",
        cases=(case,),
        harness=FrontierHarnessConfig(repetitions=1),
        observations=(observation,),
        policy=FrontierEvidencePolicy(minimum_observations=2),
    )
    output = tmp_path / "evidence.json"

    digest = write_evidence_artifact(evidence, output)

    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    assert output.with_suffix(".json.sha256").read_text() == f"{digest}  evidence.json\n"
