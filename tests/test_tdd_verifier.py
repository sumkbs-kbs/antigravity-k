"""Unit tests for TDDVerifier."""

from antigravity_k.engine.tdd_verifier import TDDVerifier


def test_parse_clean_pytest_output():
    raw = "tests/test_main.py .. [100%]\n2 passed in 0.12s"
    res = TDDVerifier._parse_pytest_output(raw, is_zero_return=True)
    assert res.passed is True
    feedback = res.format_tdd_feedback()
    assert "TDD Verified" in feedback


def test_parse_failing_pytest_output():
    raw = """
FAILED tests/test_math.py::test_division - ZeroDivisionError: division by zero
1 failed, 1 passed in 0.20s
"""
    res = TDDVerifier._parse_pytest_output(raw, is_zero_return=False)
    assert res.passed is False
    assert len(res.failure_details) >= 1
    feedback = res.format_tdd_feedback()
    assert "TDD Test Failures" in feedback
    assert "test_division" in feedback
