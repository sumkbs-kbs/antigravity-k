import pytest

from antigravity_k.engine.quality_gate import QualityGate


@pytest.fixture
def qg():
    return QualityGate()


def test_quality_gate_markdown_check(qg):
    # Valid markdown
    good_md = "Here is some text.\n```python\nprint('hello')\n```"
    result = qg.evaluate("CODE", "Make python", good_md)
    assert result.score > 0

    # Missing backticks closing
    bad_md = "Here is some text.\n```python\nprint('hello')"
    result_bad = qg.evaluate("CODE", "Make python", bad_md)
    assert result_bad.score < 1.0
    assert any("누락" in i for i in result_bad.issues)


def test_quality_gate_softened_penalty(qg):
    # Test that foreign language doesn't immediately fail but lowers score
    text = "Here is an answer in English with some tags. <thought> Thinking... </thought>"
    result = qg.evaluate("GENERAL", "test", text)
    # Should deduct some points but not fail immediately if threshold allows
    assert result.score < 1.0
