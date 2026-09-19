"""Phase 5 엔진 단위 테스트: Anthropic tool-use 브리지.

벤치마킹 출처: unsloth (로컬 모델 + Claude Code/MCP tool calling).
로컬 모델의 <tool_call> 텍스트 출력과 Anthropic tool_use 블록 간 변환을 검증한다.
"""

from __future__ import annotations

import json

from antigravity_k.engine.anthropic_tool_bridge import (
    build_content_blocks,
    build_tool_choice_directive,
    extract_tool_use_blocks,
    flatten_message_content,
    resolve_stop_reason,
    serialize_tools_for_prompt,
)


def test_serialize_tools_for_prompt_contains_catalog() -> None:
    tools = [
        {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "input_schema": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    ]
    catalog = serialize_tools_for_prompt(tools)
    assert "get_weather" in catalog
    assert "Get current weather" in catalog
    assert "```json" in catalog  # 코드펜스 형식 (crash-safe, <tool_call> 리터럴 금지)
    assert "<tool_call>" not in catalog  # llama.cpp 런너 세그폴트 유발 토큰
    assert '"city"' in catalog


def test_serialize_tools_empty_returns_empty() -> None:
    assert serialize_tools_for_prompt([]) == ""


def test_tool_choice_any_directive() -> None:
    assert "MUST" in build_tool_choice_directive({"type": "any"})


def test_tool_choice_named_tool_directive() -> None:
    directive = build_tool_choice_directive({"type": "tool", "name": "get_weather"})
    assert "get_weather" in directive


def test_tool_choice_auto_is_noop() -> None:
    assert build_tool_choice_directive("auto") == ""
    assert build_tool_choice_directive(None) == ""


def test_extract_clean_tool_call() -> None:
    text = '도구를 사용하겠습니다.\n<tool_call>\n{"name": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>'
    blocks = extract_tool_use_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].name == "read_file"
    assert json.loads(blocks[0].input_json) == {"path": "a.py"}
    assert blocks[0].tool_use_id.startswith("toolu_")
    assert not blocks[0].repaired


def test_extract_repaired_tool_call() -> None:
    """27B 모델의 흔한 오류(Python bool, trailing comma)가 수리되는지."""
    text = '<tool_call>\n{"name": "run", "arguments": {"path": "x.py", "watch": True,}}\n</tool_call>'
    blocks = extract_tool_use_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].repaired
    assert json.loads(blocks[0].input_json)["watch"] is True


def test_extract_multiple_tool_calls() -> None:
    text = (
        '<tool_call>{"name": "a", "arguments": {"x": 1}}</tool_call>\n'
        '<tool_call>{"name": "b", "arguments": {"y": 2}}</tool_call>'
    )
    blocks = extract_tool_use_blocks(text)
    assert [b.name for b in blocks] == ["a", "b"]
    assert len({b.tool_use_id for b in blocks}) == 2  # 고유 ID


def test_no_tool_call_returns_empty() -> None:
    assert extract_tool_use_blocks("일반 텍스트 응답입니다.") == []


def test_extract_backtick_json_tool_call() -> None:
    """카탈로그가 안내하는 코드펜스 형식 — qwen3 런너 crash-safe 대체 형식."""
    text = '도구를 사용하겠습니다.\n```json\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
    blocks = extract_tool_use_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].name == "read_file"
    assert json.loads(blocks[0].input_json) == {"path": "a.py"}


def test_build_content_blocks_text_plus_tool_use() -> None:
    text = '설명입니다.\n<tool_call>{"name": "t", "arguments": {"k": "v"}}</tool_call>'
    tool_blocks = extract_tool_use_blocks(text)
    blocks = build_content_blocks(text, tool_blocks)
    assert blocks[0]["type"] == "text"
    assert "설명입니다." in blocks[0]["text"]
    assert "<tool_call>" not in blocks[0]["text"]  # 태그 제거
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["name"] == "t"


def test_build_content_blocks_backtick_format_stripped() -> None:
    """코드펜스 도구 호출도 text 블록에서 제거되고 tool_use로 변환된다."""
    text = '설명입니다.\n```json\n{"name": "t", "arguments": {"k": "v"}}\n```'
    tool_blocks = extract_tool_use_blocks(text)
    blocks = build_content_blocks(text, tool_blocks)
    assert blocks[0]["type"] == "text"
    assert "```" not in blocks[0]["text"]
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["input"] == {"k": "v"}


def test_strip_preserves_plain_json_fences() -> None:
    """도구 호출이 아닌 일반 json 코드펜스는 text 블록에 보존된다."""
    text = '설정 예시입니다.\n```json\n{"server": "localhost", "port": 8080}\n```'
    blocks = build_content_blocks(text, [])
    assert len(blocks) == 1
    assert "port" in str(blocks[0]["text"])


def test_build_content_blocks_tool_only_strips_text_block() -> None:
    text = '<tool_call>{"name": "t", "arguments": {}}</tool_call>'
    blocks = build_content_blocks(text, extract_tool_use_blocks(text))
    assert [b["type"] for b in blocks] == ["tool_use"]


def test_resolve_stop_reason_tool_use_wins() -> None:
    blocks = extract_tool_use_blocks('<tool_call>{"name": "t", "arguments": {}}</tool_call>')
    assert resolve_stop_reason("...", blocks, max_tokens_hit=True) == "tool_use"


def test_resolve_stop_reason_end_turn() -> None:
    assert resolve_stop_reason("일반 응답", [], max_tokens_hit=False) == "end_turn"


def test_flatten_tool_result_roundtrip() -> None:
    """tool_use(assistant) + tool_result(user) 히스토리가 텍스트로 유지되는지."""
    assistant_content = [
        {"type": "text", "text": "파일을 확인하겠습니다."},
        {"type": "tool_use", "id": "toolu_123", "name": "read_file", "input": {"path": "x.py"}},
    ]
    user_content = [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_123",
            "content": [{"type": "text", "text": "print('hello')"}],
        },
    ]
    assistant_text = flatten_message_content(assistant_content)
    assert "read_file" in assistant_text
    assert "```json" in assistant_text  # 모델이 자기 출력 형식으로 인식 (crash-safe)
    assert "toolu_123" not in assistant_text  # 내부 ID는 노출하지 않음

    user_text = flatten_message_content(user_content)
    assert "Function result for tool_use_id=toolu_123" in user_text
    assert "print('hello')" in user_text
