from collections.abc import Mapping
from types import SimpleNamespace
from typing import cast

from scripts.run_local_model_benchmark import (
    _build_grounding_prompt,
    _extract_grounding_answer,
    _summarize_grounding_runs,
    _summarize_repeats,
)


def _result(case_id: str, score: float, grade: str, revision_count: int = 0):
    return SimpleNamespace(
        case_id=case_id,
        benchmark_score=score,
        quality_score=score,
        quality_grade=grade,
        quality_revision_count=revision_count,
        error="",
        verified=False,
    )


def _mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value)


def test_summarize_repeats_counts_verified_code_result_as_excellent():
    # Given: a verified_code case whose code executed correctly (verified=True, score 1.0)
    # but whose prose grade is only "retry" because the answer was code-only.
    reports = [
        SimpleNamespace(
            results=[
                _result("verf-001", 1.0, "excellent"),
                SimpleNamespace(
                    case_id="verf-002",
                    benchmark_score=1.0,
                    quality_score=0.45,
                    quality_grade="retry",
                    quality_revision_count=2,
                    error="",
                    verified=True,
                ),
            ],
        ),
    ]

    # When: the stability summary aggregates the run.
    summary = _mapping(_summarize_repeats(reports))

    # Then: the verified result counts as excellent for routing purposes — execution is the
    # ground truth for verified_code, so a terse-but-correct answer should not drag the
    # model's all-excellent rate below its real functional capability.
    assert summary["all_excellent_run_rate"] == 1.0
    assert summary["excellent_rate"] == 1.0


def test_summarize_repeats_reports_variance_and_case_stability():
    reports = [
        SimpleNamespace(results=[_result("alg-001", 1.0, "excellent"), _result("srch-002", 0.7, "good", 1)]),
        SimpleNamespace(results=[_result("alg-001", 0.5, "retry", 2), _result("srch-002", 1.0, "excellent")]),
    ]

    summary = _mapping(_summarize_repeats(reports))

    assert summary["repeat_count"] == 2
    assert summary["result_count"] == 4
    stddev = summary["benchmark_score_stddev"]
    assert isinstance(stddev, (int, float))
    assert stddev > 0
    assert summary["all_excellent_run_rate"] == 0
    by_case = _mapping(summary["by_case"])
    assert _mapping(by_case["alg-001"])["min_benchmark_score"] == 0.5
    assert _mapping(by_case["srch-002"])["excellent_rate"] == 0.5


def test_build_grounding_prompt_includes_question_and_bounded_evidence():
    source = SimpleNamespace(
        source_id="python-docs",
        title="Python release notes",
        text="Python 3.13 was released in 2024.",
        url="https://docs.python.org/3/",
    )
    case = SimpleNamespace(question="When was Python 3.13 released?", sources=(source,))

    prompt = _build_grounding_prompt(case)

    assert "When was Python 3.13 released?" in prompt
    assert "[citation:python-docs]" in prompt
    assert "[untrusted_web_content]" in prompt
    assert "Return JSON only" in prompt


def test_extract_grounding_answer_unwraps_structured_response():
    assert _extract_grounding_answer('{"answer":"Python 3.13 was released in 2024."}') == (
        "Python 3.13 was released in 2024."
    )
    assert _extract_grounding_answer("plain answer") == "plain answer"


def test_summarize_grounding_runs_reports_case_pass_rate():
    runs = [
        [SimpleNamespace(case_id="grounded", passed=True), SimpleNamespace(case_id="conflict", passed=True)],
        [SimpleNamespace(case_id="grounded", passed=True), SimpleNamespace(case_id="conflict", passed=False)],
    ]

    summary = _mapping(_summarize_grounding_runs(runs))

    assert summary["pass_rate"] == 0.75
    assert summary["all_pass_run_rate"] == 0.5
    by_case = _mapping(summary["by_case"])
    assert _mapping(by_case["conflict"])["pass_rate"] == 0.5
