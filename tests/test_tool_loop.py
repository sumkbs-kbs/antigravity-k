from antigravity_k.engine.tool_call_parser import EventType, ToolCallParser


def test_parse_tool_calls_valid():
    text = """
    Here is my thought.
    <action_call>
    <tool_call>
    {
      "name": "run_bash",
      "arguments": {"command": "ls -l"}
    }
    </tool_call>
    </action_call>
    """
    parser = ToolCallParser()
    events = parser.feed(text)
    events.extend(parser.flush())

    calls = [e for e in events if e.type == EventType.TOOL_CALL_COMPLETE]
    assert len(calls) == 1
    assert calls[0].tool_call.name == "run_bash"
    assert calls[0].tool_call.arguments["command"] == "ls -l"


def test_parse_tool_calls_empty():
    text = "Just thinking out loud, no tools needed."
    parser = ToolCallParser()
    events = parser.feed(text)
    events.extend(parser.flush())

    calls = [e for e in events if e.type == EventType.TOOL_CALL_COMPLETE]
    assert len(calls) == 0


def test_parse_tool_calls_malformed():
    text = """
    <action_call>
    <tool_call>
    {
      "name": "run_bash",
      "arguments": "not valid json"
    }
    </tool_call>
    </action_call>
    """
    parser = ToolCallParser()
    events = parser.feed(text)
    events.extend(parser.flush())

    calls = [e for e in events if e.type == EventType.TOOL_CALL_COMPLETE]
    assert len(calls) == 1
    assert calls[0].tool_call.arguments == "not valid json"
