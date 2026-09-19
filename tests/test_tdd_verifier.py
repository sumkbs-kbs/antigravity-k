"""Unit tests for TDDVerifier."""

from typing import Callable, cast

from antigravity_k.engine import tdd_verifier

_parse_pytest_output = cast(
    Callable[[str, bool], tdd_verifier.TDDExecutionResult],
    getattr(tdd_verifier.TDDVerifier, "_parse_pytest_output"),
)


def test_parse_clean_pytest_output():
    raw = "tests/test_main.py .. [100%]\n2 passed in 0.12s"
    res = _parse_pytest_output(raw, True)
    assert res.passed is True
    feedback = res.format_tdd_feedback()
    assert "TDD Verified" in feedback


def test_parse_failing_pytest_output():
    raw = """
FAILED tests/test_math.py::test_division - ZeroDivisionError: division by zero
1 failed, 1 passed in 0.20s
"""
    res = _parse_pytest_output(raw, False)
    assert res.passed is False
    assert len(res.failure_details) >= 1
    feedback = res.format_tdd_feedback()
    assert "TDD Test Failures" in feedback
    assert "test_division" in feedback
