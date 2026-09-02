from typing import Callable, cast

import pytest

from antigravity_k.engine.quality_gate import QualityGate


def _check_repetition(qg: QualityGate, output: str) -> tuple[float, list[str]]:
    check = cast(Callable[[str], tuple[float, list[str]]], getattr(qg, "_check_repetition"))
    return check(output)


def _check_artifact_format(qg: QualityGate, output: str) -> tuple[float, list[str]]:
    check = cast(Callable[[str], tuple[float, list[str]]], getattr(qg, "_check_artifact_format"))
    return check(output)


def _check_output_contract(
    qg: QualityGate,
    request: str,
    output: str,
    task_type: str,
) -> tuple[float, list[str]]:
    check = cast(
        Callable[[str, str, str], tuple[float, list[str]]],
        getattr(qg, "_check_output_contract"),
    )
    return check(request, output, task_type)


@pytest.fixture
def qg() -> QualityGate:
    return QualityGate()


def test_quality_gate_markdown_check(qg: QualityGate):
    # Valid markdown
    good_md = "Here is some text.\n```python\nprint('hello')\n```"
    result = qg.evaluate("CODE", "Make python", good_md)
    assert result.score > 0

    # Missing backticks closing
    bad_md = "Here is some text.\n```python\nprint('hello')"
    result_bad = qg.evaluate("CODE", "Make python", bad_md)
    assert result_bad.score < 1.0
    assert any("누락" in i for i in result_bad.issues)


def test_quality_gate_softened_penalty(qg: QualityGate):
    # Test that foreign language doesn't immediately fail but lowers score
    text = "Here is an answer in English with some tags. <thought> Thinking... </thought>"
    result = qg.evaluate("GENERAL", "test", text)
    # Should deduct some points but not fail immediately if threshold allows
    assert result.score < 1.0


def test_quality_gate_validates_python_syntax_for_code_alias(qg: QualityGate):
    result = qg.evaluate(
        "code",
        "Write a Python factorial function",
        "```python\ndeffactorial(n: int):\n    return n```",
    )

    assert any("구문오류" in issue for issue in result.issues)


def test_quality_gate_accepts_explicit_code_only_response(qg: QualityGate):
    result = qg.evaluate(
        "code",
        "Python factorial 함수를 작성하고 시간 복잡도를 포함해. 코드만 출력해.",
        "```python\ndef factorial(n: int) -> int:\n    if n < 0:\n        raise ValueError('n must be non-negative')\n    result = 1\n    for value in range(2, n + 1):\n        result *= value\n    return result\n\n# Time complexity: O(n)\n# Space complexity: O(1)\n```",
    )

    assert result.grade.value == "excellent"


def test_repetition_check_allows_common_code_example_boundary(qg: QualityGate):
    # Given: three distinct valid code alternatives share only output boilerplate.
    methods = [
        "def formula():\n    return 55",
        "def builtin():\n    return sum(range(1, 11))",
        "def loop():\n    total = 0\n    return total",
    ]
    output = "".join(
        f"### 방법 {index}\n```python\n{method}\nprint(result)  # 출력: 55\n```\n\n**복잡도 분석:**\n"
        for index, method in enumerate(methods, start=1)
    )

    # When: the repetition gate scans the response.
    score, issues = _check_repetition(qg, output)

    # Then: the shared fence boundary is not treated as a generation loop.
    assert score == 1.0
    assert not any("반복" in issue for issue in issues)


def test_artifact_check_does_not_treat_a_task_title_as_a_task_manifest(qg: QualityGate):
    # Given: a normal response labels its coding exercise with a singular Task title.
    output = "## Task: Fibonacci\n\n```python\ndef fibonacci(n: int) -> int:\n    return n\n```"

    # When: the artifact-format checker inspects the response.
    score, issues = _check_artifact_format(qg, output)

    # Then: no task-manifest checkbox penalty is applied.
    assert score == 1.0
    assert "Task.md 컨텍스트에서 체크박스 태스크(`- [ ]`) 없음" not in issues


def test_search_task_does_not_require_code_block_for_python_research(qg: QualityGate):
    # Given: a search task whose subject is a programming language.
    request = "Python 3.13의 실험적 JIT를 웹 검색으로 조사해"
    output = "- Python 3.13 release notes [citation:python-docs]"

    # When: the output contract evaluates the research response.
    score, issues = _check_output_contract(qg, request, output, "search")

    # Then: the subject keyword does not turn research into a code-output contract.
    assert score == 1.0
    assert "요청된 코드 블록 누락" not in issues
