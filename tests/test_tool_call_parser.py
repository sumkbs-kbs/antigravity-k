"""
tool_call_parser.py 단위 테스트
================================
- <thought> 내부의 <action_call> 텍스트가 도구 호출로 오인되지 않는지 확인
- 정상적인 도구 호출은 여전히 동작하는지 확인
- thought 뒤에 오는 진짜 도구 호출이 정상 감지되는지 확인
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from antigravity_k.engine.tool_call_parser import ToolCallParser, EventType


def test_normal_tool_call():
    """정상적인 도구 호출이 올바르게 파싱되는지"""
    parser = ToolCallParser()
    text = '<action_call>\n{"name": "web_search", "arguments": {"query": "test"}}\n</action_call>'
    events = parser.feed(text)
    events += parser.flush()

    types = [e.type for e in events]
    assert EventType.TOOL_CALL_START in types, f"TOOL_CALL_START missing: {types}"
    assert EventType.TOOL_CALL_COMPLETE in types, f"TOOL_CALL_COMPLETE missing: {types}"

    complete_event = [e for e in events if e.type == EventType.TOOL_CALL_COMPLETE][0]
    assert complete_event.tool_call.name == "web_search"
    assert complete_event.tool_call.arguments == {"query": "test"}
    print("✅ test_normal_tool_call PASSED")


def test_thought_blocks_ignored():
    """<thought> 내부의 <action_call> 텍스트가 도구 호출로 오인되지 않는지"""
    parser = ToolCallParser()
    text = (
        "<thought>\n"
        "Single <action_call>? Yes.\n"
        "No extra text after <action_call>? Yes.\n"
        "</thought>\n"
    )
    events = parser.feed(text)
    events += parser.flush()

    types = [e.type for e in events]
    assert (
        EventType.TOOL_CALL_START not in types
    ), f"False TOOL_CALL_START detected inside thought! {types}"
    assert (
        EventType.TOOL_CALL_ERROR not in types
    ), f"False TOOL_CALL_ERROR detected inside thought! {types}"
    # 모두 TEXT 이벤트여야 함
    assert all(
        e.type == EventType.TEXT for e in events
    ), f"Non-TEXT events found: {types}"
    print("✅ test_thought_blocks_ignored PASSED")


def test_thought_then_real_tool_call():
    """<thought> 블록 후에 오는 진짜 <action_call>이 정상 감지되는지"""
    parser = ToolCallParser()
    text = (
        "<thought>\n"
        "I will use web_search to find the weather. <action_call> should work.\n"
        "</thought>\n"
        "<action_call>\n"
        '{"name": "web_search", "arguments": {"query": "거제 날씨"}}\n'
        "</action_call>\n"
    )
    events = parser.feed(text)
    events += parser.flush()

    types = [e.type for e in events]
    assert (
        EventType.TOOL_CALL_START in types
    ), f"Real TOOL_CALL_START not detected: {types}"
    assert (
        EventType.TOOL_CALL_COMPLETE in types
    ), f"Real TOOL_CALL_COMPLETE not detected: {types}"
    # TOOL_CALL_ERROR는 없어야 함
    assert (
        EventType.TOOL_CALL_ERROR not in types
    ), f"Unexpected TOOL_CALL_ERROR: {types}"

    complete_event = [e for e in events if e.type == EventType.TOOL_CALL_COMPLETE][0]
    assert complete_event.tool_call.name == "web_search"
    assert complete_event.tool_call.arguments == {"query": "거제 날씨"}
    print("✅ test_thought_then_real_tool_call PASSED")


def test_streaming_chunks():
    """스트리밍 청크 단위로 들어와도 정상 동작하는지"""
    parser = ToolCallParser()
    chunks = [
        "<thou",
        "ght>\nI need <action_call> tag\n</thou",
        "ght>\n<action_",
        'call>\n{"name": "web_search", "argum',
        'ents": {"query": "test"}}\n</action_call>',
    ]

    all_events = []
    for chunk in chunks:
        all_events.extend(parser.feed(chunk))
    all_events.extend(parser.flush())

    types = [e.type for e in all_events]
    # thought 안의 <action_call>은 무시, 진짜만 감지
    complete_events = [e for e in all_events if e.type == EventType.TOOL_CALL_COMPLETE]
    assert (
        len(complete_events) == 1
    ), f"Expected exactly 1 TOOL_CALL_COMPLETE, got {len(complete_events)}: {types}"
    assert complete_events[0].tool_call.name == "web_search"
    assert (
        EventType.TOOL_CALL_ERROR not in types
    ), f"Unexpected TOOL_CALL_ERROR: {types}"
    print("✅ test_streaming_chunks PASSED")


def test_text_without_any_tags():
    """태그가 없는 순수 텍스트"""
    parser = ToolCallParser()
    events = parser.feed("Hello, this is plain text without any tags.")
    events += parser.flush()

    types = [e.type for e in events]
    assert all(
        e.type == EventType.TEXT for e in events
    ), f"Non-TEXT events found: {types}"
    full_text = "".join(e.data for e in events)
    assert "Hello, this is plain text without any tags." == full_text
    print("✅ test_text_without_any_tags PASSED")


def test_multiple_thought_blocks():
    """여러 개의 <thought> 블록이 있을 때"""
    parser = ToolCallParser()
    text = (
        "<thought>First thought with <action_call> mention</thought>\n"
        "Some visible text\n"
        "<thought>Second thought also mentions <action_call></thought>\n"
        "<action_call>\n"
        '{"name": "test_tool", "arguments": {}}\n'
        "</action_call>\n"
    )
    events = parser.feed(text)
    events += parser.flush()

    types = [e.type for e in events]
    complete_events = [e for e in events if e.type == EventType.TOOL_CALL_COMPLETE]
    assert (
        len(complete_events) == 1
    ), f"Expected 1 TOOL_CALL_COMPLETE, got {len(complete_events)}"
    assert complete_events[0].tool_call.name == "test_tool"
    assert EventType.TOOL_CALL_ERROR not in types, f"Unexpected errors: {types}"
    print("✅ test_multiple_thought_blocks PASSED")


if __name__ == "__main__":
    test_normal_tool_call()
    test_thought_blocks_ignored()
    test_thought_then_real_tool_call()
    test_streaming_chunks()
    test_text_without_any_tags()
    test_multiple_thought_blocks()
    print("\n🎉 All tests PASSED!")
