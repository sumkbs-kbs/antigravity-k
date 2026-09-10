"""Unit tests for UnifiedAgent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from antigravity_k.engine.unified_agent import (
    UnifiedAgent,
    _extract_code,
    _strip_think,
)


def test_strip_think_removes_think_blocks() -> None:
    raw = "<think>Let me ponder...</think>Here is the answer."
    assert _strip_think(raw) == "Here is the answer."

    open_think = "Prefix text.<think>Unfinished thinking..."
    assert _strip_think(open_think) == "Prefix text."


def test_extract_code_handles_fenced_and_raw() -> None:
    fenced = "Here is solution:\n```python\ndef add(a, b):\n    return a + b\n```"
    assert _extract_code(fenced) == "def add(a, b):\n    return a + b"

    raw_def = "Sure:\ndef sub(a, b):\n    return a - b"
    assert _extract_code(raw_def) == "def sub(a, b):\n    return a - b"

    class_code = "class Stack:\n    pass"
    assert _extract_code(class_code) == "class Stack:\n    pass"


def test_classify_rules() -> None:
    agent = UnifiedAgent(lambda **kw: "answer", "dummy-model", headroom=False)

    assert agent._classify("Fix the off-by-one bug in binary search") == "code"
    assert agent._classify("Implement a thread-safe cache") == "code"
    assert agent._classify("Where is the database connection pool defined?") == "explore"
    assert agent._classify("What is the latest version of FastAPI in 2026?") == "web"


def test_classify_fallback_to_llm() -> None:
    mock_gen = MagicMock(return_value="explore")
    agent = UnifiedAgent(mock_gen, "dummy-model", headroom=False)

    action = agent._classify("Tell me the structure of the system")
    assert action == "explore"


def test_run_answer_flow() -> None:
    mock_gen = MagicMock(return_value="Python is an interpreted language.")
    agent = UnifiedAgent(mock_gen, "dummy-model", headroom=False)

    outcome = agent.run("What is Python?")
    assert outcome.answer == "Python is an interpreted language."
    assert len(outcome.steps) == 1
    assert outcome.steps[0].action == "answer"


def test_run_explore_flow() -> None:
    mock_gen = MagicMock(return_value="Found in src/core/config.py")
    agent = UnifiedAgent(mock_gen, "dummy-model", headroom=False)

    with patch.object(agent, "_graphify_context", return_value="file: src/core/config.py: [Config]"):
        outcome = agent.run("Where is the config class defined?")

    assert outcome.used_graphify is True
    assert "src/core/config.py" in outcome.answer
    assert outcome.steps[0].action == "explore+graphify"


def test_run_web_flow() -> None:
    mock_gen = MagicMock(return_value="Version 2.0 released in 2026.")
    agent = UnifiedAgent(mock_gen, "dummy-model", headroom=False)

    with patch("antigravity_k.engine.unified_agent.web_search", return_value=[]):
        outcome = agent.run("What is the latest release today?")

    assert outcome.steps[0].action == "web+ssak-search"
    assert "Version 2.0" in outcome.answer


def test_run_code_without_test() -> None:
    mock_gen = MagicMock(return_value="```python\ndef square(x):\n    return x * x\n```")
    agent = UnifiedAgent(mock_gen, "dummy-model", headroom=False)

    with patch.object(agent, "_graphify_context", return_value=""):
        outcome = agent.run("Write a function to square a number")
    assert outcome.passed is True
    assert "def square(x):" in outcome.answer


def test_run_code_with_test_repair_loop() -> None:
    attempt_responses = [
        "```python\ndef mul(a, b):\n    return a + b\n```",
        "```python\ndef mul(a, b):\n    return a * b\n```",
    ]
    gen_idx = 0

    def fake_gen(**kwargs: object) -> str:
        nonlocal gen_idx
        res = attempt_responses[min(gen_idx, len(attempt_responses) - 1)]
        gen_idx += 1
        return res

    agent = UnifiedAgent(fake_gen, "dummy-model", headroom=False)
    test_code = "from solution import mul\n\ndef test_mul():\n    assert mul(2, 3) == 6\n"

    with patch.object(agent, "_graphify_context", return_value=""):
        outcome = agent.run("Implement mul function", test_code=test_code, max_repairs=2)
    assert outcome.passed is True
    assert "def mul(a, b):" in outcome.answer


def test_probe_diversity_detects_variation() -> None:
    responses = [
        "```python\ndef solve(): return 1\n```",
        "```python\ndef solve(): return 2\n```",
    ]
    gen_idx = 0

    def fake_gen(**kwargs: object) -> str:
        nonlocal gen_idx
        res = responses[gen_idx % len(responses)]
        gen_idx += 1
        return res

    agent = UnifiedAgent(fake_gen, "dummy-model", headroom=False)
    assert agent._probe_diversity("some task", "") is True


def test_probe_diversity_detects_convergence() -> None:
    same_code = "```python\ndef solve(): return 1\n```"
    agent = UnifiedAgent(lambda **kw: same_code, "dummy-model", headroom=False)
    assert agent._probe_diversity("some task", "") is False
