"""Phase 35 테스트: OpenAI Responses API passthrough (/v1/responses).

Codex CLI 0.150+ 는 wire_api="chat" 없이 Responses API만 호출한다
(openai/codex#7782). function_call / function_call_output 왕복과 SSE 이벤트를 검증한다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api import dependencies as api_dependencies
from antigravity_k.api.server import app
from antigravity_k.engine.openai_responses_bridge import (
    build_responses_response,
    build_tool_prompt,
    responses_input_to_internal,
    responses_stream_events,
    validate_responses_tools,
)


class _FakeManager:
    def __init__(self, response: str = "로컬 모델 응답입니다.") -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(self, *, prompt: str, target: str, **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "target": target, **kwargs})
        return self.response


@pytest.fixture()
def client() -> Any:
    fake = _FakeManager()
    app.dependency_overrides[api_dependencies.get_model_manager] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.pop(api_dependencies.get_model_manager, None)


@pytest.fixture()
def tool_calling_client() -> Any:
    fake = _FakeManager(
        response='<tool_call>\n{"name": "shell", "arguments": {"command": ["ls"]}}\n</tool_call>',
    )
    app.dependency_overrides[api_dependencies.get_model_manager] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.pop(api_dependencies.get_model_manager, None)


def _responses_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "name": "shell",
        "description": "Run a shell command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "array"}}},
    }


def _base_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": "qwen3.8:latest",
        "instructions": "You are a coding agent.",
        "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "파일 보여줘"}]}],
        "tools": [_responses_tool()],
        "stream": False,
    }
    body.update(overrides)
    return body


# ─── 1. 단위: tools 검증 ─────────────────────────────────────────────


def test_validate_responses_tools_flat_format() -> None:
    tools, error = validate_responses_tools([_responses_tool()])
    assert error is None
    assert tools == [
        {
            "name": "shell",
            "description": "Run a shell command.",
            "input_schema": {"type": "object", "properties": {"command": {"type": "array"}}},
        }
    ]


def test_validate_responses_tools_skips_builtin_tools() -> None:
    tools, error = validate_responses_tools([{"type": "web_search"}, _responses_tool()])
    assert error is None
    assert [t["name"] for t in tools] == ["shell"]


def test_validate_responses_tools_rejects_missing_name() -> None:
    tools, error = validate_responses_tools([{"type": "function"}])
    assert tools == []
    assert error is not None


# ─── 2. 단위: input 변환 ─────────────────────────────────────────────


def test_string_input_becomes_single_user_message() -> None:
    system_text, internal = responses_input_to_internal("안녕", "You are helpful.")
    assert system_text == "You are helpful."
    assert internal == [{"role": "user", "content": "안녕"}]


def test_function_call_output_becomes_function_result() -> None:
    items = [
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "ls 실행해줘"}]},
        {"type": "function_call", "call_id": "call_x1", "name": "shell", "arguments": '{"command": ["ls"]}'},
        {
            "type": "function_call_output",
            "call_id": "call_x1",
            "output": '{"output": "README.md\\nsrc", "metadata": {}}',
        },
        {"type": "reasoning", "summary": []},
    ]
    system_text, internal = responses_input_to_internal(items, "sys")
    assert system_text == "sys"
    assert internal[0] == {"role": "user", "content": "ls 실행해줘"}
    assert '"name": "shell"' in internal[1]["content"]
    assert "Function result for tool_use_id=call_x1" in internal[2]["content"]
    assert "README.md" in internal[2]["content"]
    assert len(internal) == 3  # reasoning은 스킵


def test_plain_output_string_unwrapped_verbatim() -> None:
    _, internal = responses_input_to_internal(
        [{"type": "function_call_output", "call_id": "c1", "output": "plain text result"}]
    )
    assert "plain text result" in internal[0]["content"]


# ─── 3. 단위: 프롬프트/응답 ──────────────────────────────────────────


def test_build_tool_prompt_includes_catalog() -> None:
    prompt = build_tool_prompt(
        "sys",
        [{"name": "shell", "description": "d", "input_schema": {}}],
        "auto",
        [{"role": "user", "content": "hi"}],
    )
    assert prompt.startswith("System: sys")
    assert "# Tool Use" in prompt
    assert "User: hi" in prompt


def test_build_responses_response_with_function_call() -> None:
    res = build_responses_response(
        "m",
        '<tool_call>\n{"name": "shell", "arguments": {"command": ["ls"]}}\n</tool_call>',
        responses_extract_blocks(),
    )
    assert res["object"] == "response"
    assert res["status"] == "completed"
    kinds = [item["type"] for item in res["output"]]
    assert "function_call" in kinds
    call = next(i for i in res["output"] if i["type"] == "function_call")
    assert call["name"] == "shell"
    assert json.loads(call["arguments"]) == {"command": ["ls"]}
    assert res["usage"]["total_tokens"] > 0


def responses_extract_blocks() -> list[Any]:
    from antigravity_k.engine.anthropic_tool_bridge import extract_tool_use_blocks

    return extract_tool_use_blocks('<tool_call>\n{"name": "shell", "arguments": {"command": ["ls"]}}\n</tool_call>')


def test_build_responses_response_text_only() -> None:
    res = build_responses_response("m", "그냥 텍스트", [])
    assert [i["type"] for i in res["output"]] == ["message"]
    assert res["output"][0]["content"][0]["text"] == "그냥 텍스트"


# ─── 4. 단위: SSE 이벤트 ─────────────────────────────────────────────


def test_stream_events_sequence_with_function_call() -> None:
    frames = responses_stream_events("m", "생각...", responses_extract_blocks())
    types = [f.split("event: ")[1].split("\n")[0] for f in frames]
    assert types[0] == "response.created"
    assert "response.output_item.added" in types
    assert "response.function_call_arguments.delta" in types
    assert "response.function_call_arguments.done" in types
    assert types[-1] == "response.completed"
    # completed의 output에 function_call 포함
    completed = json.loads(frames[-1].split("data: ")[1])
    assert any(i["type"] == "function_call" for i in completed["response"]["output"])
    assert completed["response"]["status"] == "completed"


def test_stream_events_text_only() -> None:
    frames = responses_stream_events("m", "텍스트 응답", [])
    joined = "".join(frames)
    assert "response.output_text.delta" in joined
    assert "function_call" not in joined
    types = [f.split("event: ")[1].split("\n")[0] for f in frames]
    assert types[-1] == "response.completed"


# ─── 5. 엔드포인트 ───────────────────────────────────────────────────


def test_endpoint_non_stream_function_call(tool_calling_client: Any) -> None:
    test_client, fake = tool_calling_client
    res = test_client.post("/v1/responses", json=_base_body())
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["object"] == "response"
    call = next(i for i in data["output"] if i["type"] == "function_call")
    assert call["name"] == "shell"
    assert json.loads(call["arguments"]) == {"command": ["ls"]}
    assert "instructions" in fake.calls[0]["prompt"] or "System:" in fake.calls[0]["prompt"]


def test_endpoint_function_call_output_roundtrip(tool_calling_client: Any) -> None:
    test_client, fake = tool_calling_client
    body = _base_body(
        input=[
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "ls"}]},
            {"type": "function_call", "call_id": "call_9", "name": "shell", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call_9", "output": "README.md"},
        ]
    )
    res = test_client.post("/v1/responses", json=body)
    assert res.status_code == 200, res.text
    prompt = fake.calls[0]["prompt"]
    assert "Function result for tool_use_id=call_9" in prompt
    assert "README.md" in prompt


def test_endpoint_streaming_completed_event(tool_calling_client: Any) -> None:
    test_client, _ = tool_calling_client
    res = test_client.post("/v1/responses", json=_base_body(stream=True))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    assert "event: response.created" in res.text
    assert "event: response.completed" in res.text
    assert '"function_call"' in res.text


def test_endpoint_missing_model_rejected(client: Any) -> None:
    test_client, _ = client
    body = _base_body()
    body.pop("model")
    res = test_client.post("/v1/responses", json=body)
    assert res.status_code == 400


def test_endpoint_invalid_tools_rejected(client: Any) -> None:
    test_client, _ = client
    res = test_client.post("/v1/responses", json=_base_body(tools="bad"))
    assert res.status_code == 400
