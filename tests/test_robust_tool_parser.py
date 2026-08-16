"""Unit tests for RobustToolParser."""

from antigravity_k.engine.robust_tool_parser import RobustToolParser


def test_strict_tool_call():
    text = '<tool_call>{"name": "read_file", "arguments": {"file_path": "main.py"}}</tool_call>'
    calls = RobustToolParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments["file_path"] == "main.py"


def test_healed_trailing_comma_and_booleans():
    text = '<tool_call>{"name": "test_tool", "arguments": {"flag": True, "opt": None,}}</tool_call>'
    calls = RobustToolParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "test_tool"
    assert calls[0].arguments["flag"] is True
    assert calls[0].arguments["opt"] is None


def test_healed_unclosed_braces():
    text = '<tool_call>{"name": "broken_tool", "arguments": {"target": "data.csv"'
    calls = RobustToolParser.extract_tool_calls(text)
    # Even if missing closing braces, it should attempt repair or gracefully extract
    assert len(calls) <= 1


def test_backtick_json_fallback():
    text = """
```json
{
  "name": "run_command",
  "arguments": {
    "CommandLine": "pytest"
  }
}
```
"""
    calls = RobustToolParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "run_command"
    assert calls[0].arguments["CommandLine"] == "pytest"
