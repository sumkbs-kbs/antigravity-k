from dataclasses import replace
from typing import TypedDict

from antigravity_k.engine.benchmark_cases import BenchmarkCase
from antigravity_k.engine.frontier_evidence import (
    FrontierEvidencePolicy,
    FrontierHarnessConfig,
    FrontierObservation,
    build_frontier_evidence,
    frontier_evidence_sha256,
)


def _case(case_id: str = "case-1") -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        category="architecture",
        prompt="Design a resilient worker.",
        difficulty=4,
        expected_keywords=("idempotency", "retry"),
    )


def _observation(index: int, gap: float = 0.02) -> FrontierObservation:
    local_score = 0.80 + (index % 2) * 0.01
    return FrontierObservation(
        case_id=f"case-{index % 2 + 1}",
        repetition=index // 2,
        local_score=local_score,
        frontier_score=local_score + gap,
        local_latency_ms=100 + index,
        frontier_latency_ms=120 + index,
    )


class _EvidenceInputs(TypedDict):
    local_model: str
    frontier_model: str
    harness: FrontierHarnessConfig
    observations: tuple[FrontierObservation, ...]


def test_frontier_evidence_accepts_local_model_when_confidence_upper_bound_is_within_gap() -> None:
    evidence = build_frontier_evidence(
        local_model="qwen3.8:27b",
        frontier_model="frontier/model@revision",
        cases=(_case("case-1"), _case("case-2")),
        harness=FrontierHarnessConfig(repetitions=3, seed=17),
        observations=tuple(_observation(index) for index in range(6)),
        policy=FrontierEvidencePolicy(minimum_observations=6, maximum_acceptable_gap=0.05),
    )

    assert evidence.schema_version == 2
    assert evidence.observation_count == 6
    assert evidence.mean_gap == 0.02
    assert evidence.confidence_upper_bound == 0.02
    assert evidence.local_reaches_frontier is True
    assert evidence.reasons == ()
    assert len(evidence.dataset_sha256) == 64
    assert len(evidence.harness_sha256) == 64


def test_frontier_evidence_rejects_insufficient_or_uncertain_evidence() -> None:
    evidence = build_frontier_evidence(
        local_model="qwen3.8:27b",
        frontier_model="frontier/model@revision",
        cases=(_case(),),
        harness=FrontierHarnessConfig(repetitions=2, seed=3),
        observations=(
            _observation(0, 0.08),
            _observation(1, 0.01).model_copy(update={"case_id": "case-1", "repetition": 1}),
        ),
        policy=FrontierEvidencePolicy(minimum_observations=6, maximum_acceptable_gap=0.05),
    )

    assert evidence.local_reaches_frontier is False
    assert "insufficient paired observations" in evidence.reasons
    assert "confidence upper bound exceeds acceptable frontier gap" in evidence.reasons


def test_frontier_evidence_fingerprints_case_content_and_serializes_deterministically() -> None:
    common: _EvidenceInputs = {
        "local_model": "qwen3.8:27b",
        "frontier_model": "frontier/model@revision",
        "harness": FrontierHarnessConfig(repetitions=3, seed=17),
        "observations": tuple(_observation(index) for index in range(6)),
    }
    original = build_frontier_evidence(cases=(_case("case-1"), _case("case-2")), **common)
    changed_case = replace(_case("case-2"), prompt="A changed held-out prompt.")
    changed = build_frontier_evidence(cases=(_case("case-1"), changed_case), **common)

    assert original.dataset_sha256 != changed.dataset_sha256
    assert frontier_evidence_sha256(original) == frontier_evidence_sha256(original)
    assert frontier_evidence_sha256(original) != frontier_evidence_sha256(changed)
