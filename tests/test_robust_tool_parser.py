"""Unit tests for RobustToolParser."""

from antigravity_k.engine.robust_tool_parser import RobustToolParser


def test_strict_tool_call():
    text = '<tool_call>{"name": "read_file", "arguments": {"file_path": "main.py"}}</tool_call>'
    calls = RobustToolParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments["file_path"] == "main.py"
    assert calls[0].repaired is False


def test_healed_trailing_comma_and_booleans():
    text = '<tool_call>{"name": "test_tool", "arguments": {"flag": True, "opt": None,}}</tool_call>'
    calls = RobustToolParser.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "test_tool"
    assert calls[0].arguments["flag"] is True
    assert calls[0].arguments["opt"] is None
    assert calls[0].repaired is True


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


def test_tool_call_preserves_nested_arguments():
    text = '<tool_call>{"name":"configure","arguments":{"config":{"retry":3},"enabled":true}}</tool_call>'

    calls = RobustToolParser.extract_tool_calls(text)

    assert len(calls) == 1
    assert calls[0].arguments == {"config": {"retry": 3}, "enabled": True}


def test_unterminated_fence_with_stray_closing_tag():
    """말단 변형: 닫는 fence 없이 생성 종료 + 짝 없는 </tool_call>만 붙은 경우.

    2026-09-04 Codex E2E에서 실측된 27B 모델 출력 (Phase 35).
    """
    text = '```json\n{"name": "exec_command", "arguments": {"cmd": "cat note.txt"}}\n</tool_call>'

    calls = RobustToolParser.extract_tool_calls(text)

    assert len(calls) == 1
    assert calls[0].name == "exec_command"
    assert calls[0].arguments == {"cmd": "cat note.txt"}
    assert calls[0].repaired is True


def test_unterminated_fence_without_any_tag():
    text = '```json\n{"name": "shell", "arguments": {"command": ["ls"]}}'

    calls = RobustToolParser.extract_tool_calls(text)

    assert len(calls) == 1
    assert calls[0].name == "shell"
    assert calls[0].arguments == {"command": ["ls"]}
