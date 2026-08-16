from pathlib import Path

from antigravity_k.tools.claim_grounding_benchmark import (
    ClaimGroundingCase,
    evaluate_live_grounding_case,
    load_claim_grounding_cases,
    run_claim_grounding_benchmark,
)
from antigravity_k.tools.search_quality_evaluator import CitationSource


def test_claim_grounding_fixture_covers_support_unknown_and_conflict_contracts():
    cases = load_claim_grounding_cases(Path("tests/fixtures/claim_grounding_cases.json"))
    results = run_claim_grounding_benchmark(cases)

    assert len(results) == 4
    assert all(result.passed for result in results)
    assert results[1].report.unknown_citation_count == 1
    assert results[2].report.unacknowledged_conflict_count == 1
    assert results[3].report.unacknowledged_conflict_count == 0
    assert cases[0].question == "When was Python 3.13 released?"


def test_claim_grounding_response_override_fails_on_unknown_citation():
    cases = load_claim_grounding_cases(Path("tests/fixtures/claim_grounding_cases.json"))
    results = run_claim_grounding_benchmark(
        cases,
        {"grounded-release": "The release date is unknown. [citation:missing]"},
    )

    first = results[0]
    assert first.passed is False
    assert first.report.unknown_citation_count == 1


def test_live_grounding_requires_supported_citations_and_sources():
    source = CitationSource(
        source_id="python-docs",
        title="Python release notes",
        text="Python 3.13 was released in 2024.",
    )
    case = ClaimGroundingCase(
        case_id="live",
        response="",
        sources=(source,),
        question="When was Python 3.13 released?",
    )

    passed = evaluate_live_grounding_case(case, "Python 3.13 was released in 2024. [citation:python-docs]")
    failed = evaluate_live_grounding_case(case, "Python 3.13 was released in 2024. [citation:missing]")

    assert passed.passed is True
    assert failed.passed is False
    assert "unknown_citations" in failed.failures
