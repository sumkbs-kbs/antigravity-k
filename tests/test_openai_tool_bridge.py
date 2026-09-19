"""Phase 35 테스트: OpenAI tools passthrough (/v1/chat/completions).

Codex 등 OpenAI 프로토콜 에이전트의 function calling을 로컬 모델 텍스트 프로토콜로
왕복 변환하는 openai_tool_bridge + chat.py passthrough 분기를 검증한다.
anthropic_tool_bridge (Phase 5)와 동일 단일 파서를 재사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api import dependencies as api_dependencies
from antigravity_k.api.project_binding import (
    DEFAULT_SESSION_ID,
    bind_session_active_project,
    get_session_project_bindings,
    reset_bound_request_execution_context,
)
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.openai_tool_bridge import (
    build_openai_response,
    build_tool_prompt,
    convert_tool_choice,
    effective_system,
    extract_blocks,
    openai_messages_to_internal,
    openai_stream_frames,
    tool_blocks_to_tool_calls,
    validate_openai_tools,
)
from antigravity_k.engine.project_registry import ProjectRegistry


class _FakeManager:
    """ModelManager 목 — generate만 흉내낸다."""

    def __init__(self, response: str = "로컬 모델 응답입니다.") -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(self, *, prompt: str, target: str, **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "target": target, **kwargs})
        return self.response


def _bind_default_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Register a temp project and bind DEFAULT_SESSION so chat tools path can proceed."""
    import antigravity_k.engine.project_registry as preg

    storage = tmp_path / "projects.json"
    monkeypatch.setattr(preg, "_DEFAULT_STORAGE_PATH", storage)
    monkeypatch.setattr(preg, "_global_registry", None)
    allow_root = tmp_path.resolve()
    monkeypatch.setattr(config.paths, "project_root", allow_root)
    monkeypatch.delenv("AGK_ALLOWED_ROOTS", raising=False)

    proj_dir = tmp_path / "tool_bridge_proj"
    proj_dir.mkdir()
    registry = ProjectRegistry(storage_path=storage)
    record = registry.add_project(name="ToolBridge", path=str(proj_dir))
    monkeypatch.setattr(preg, "_global_registry", registry)

    get_session_project_bindings().reset_all()
    reset_bound_request_execution_context()
    bind_session_active_project(DEFAULT_SESSION_ID, record.id)
    return record.id


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    _ = _bind_default_project(tmp_path, monkeypatch)
    fake = _FakeManager()
    app.dependency_overrides[api_dependencies.get_model_manager] = lambda: fake
    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client, fake
    app.dependency_overrides.pop(api_dependencies.get_model_manager, None)
    get_session_project_bindings().reset_all()
    reset_bound_request_execution_context()


@pytest.fixture()
def tool_calling_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    _ = _bind_default_project(tmp_path, monkeypatch)
    fake = _FakeManager(
        response='<tool_call>\n{"name": "shell", "arguments": {"command": ["ls"]}}\n</tool_call>',
    )
    app.dependency_overrides[api_dependencies.get_model_manager] = lambda: fake
    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client, fake
    app.dependency_overrides.pop(api_dependencies.get_model_manager, None)
    get_session_project_bindings().reset_all()
    reset_bound_request_execution_context()


def _openai_tool(name: str = "shell") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "Run a shell command.",
            "parameters": {"type": "object", "properties": {"command": {"type": "array"}}},
        },
    }


def _base_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": "qwen3.8:latest",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": "파일 목록 보여줘"}],
        "tools": [_openai_tool()],
    }
    body.update(overrides)
    return body


# ─── 1. 단위: validate_openai_tools ──────────────────────────────────


def test_validate_openai_tools_converts_function_format() -> None:
    tools, error = validate_openai_tools([_openai_tool()])
    assert error is None
    assert tools == [
        {
            "name": "shell",
            "description": "Run a shell command.",
            "input_schema": {"type": "object", "properties": {"command": {"type": "array"}}},
        }
    ]


def test_validate_openai_tools_rejects_non_array() -> None:
    tools, error = validate_openai_tools("not-an-array")
    assert tools == []
    assert error is not None and "array" in error


def test_validate_openai_tools_rejects_missing_name() -> None:
    tools, error = validate_openai_tools([{"type": "function", "function": {"description": "x"}}])
    assert tools == []
    assert error is not None and "name" in error


def test_validate_openai_tools_tolerates_direct_format() -> None:
    """function 래퍼 없는 직접 형식도 방어적으로 허용."""
    tools, error = validate_openai_tools([{"name": "ls", "parameters": {"type": "object"}}])
    assert error is None
    assert tools[0]["name"] == "ls"


# ─── 2. 단위: convert_tool_choice ────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("auto", "auto"),
        ("none", {"type": "none"}),
        ("required", {"type": "any"}),
        ({"type": "function", "function": {"name": "shell"}}, {"type": "tool", "name": "shell"}),
    ],
)
def test_convert_tool_choice(raw: Any, expected: Any) -> None:
    assert convert_tool_choice(raw) == expected


# ─── 3. 단위: 히스토리 변환 ───────────────────────────────────────────


def test_messages_to_internal_serializes_tool_calls() -> None:
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "파일 보여줘"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "shell", "arguments": '{"command": ["ls"]}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "README.md\nsrc"},
    ]
    system_text, internal = openai_messages_to_internal(messages)
    assert system_text == "You are helpful."
    assert internal[0] == {"role": "user", "content": "파일 보여줘"}
    fence = internal[1]["content"]
    assert "```json" in fence and '"name": "shell"' in fence
    result = internal[2]["content"]
    assert result.startswith("Function result for tool_use_id=call_1:")
    assert "README.md" in result


def test_messages_to_internal_flattens_content_parts() -> None:
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "부분1"}, {"type": "text", "text": "부분2"}],
        }
    ]
    _, internal = openai_messages_to_internal(messages)
    assert internal[0]["content"] == "부분1\n부분2"


def test_messages_to_internal_handles_broken_arguments_json() -> None:
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "shell", "arguments": "{oops"}}],
        }
    ]
    _, internal = openai_messages_to_internal(messages)
    assert '"arguments": {}' in internal[0]["content"]


# ─── 4. 단위: 프롬프트/응답 조립 ──────────────────────────────────────


def test_effective_system_includes_catalog_and_directive() -> None:
    system = effective_system("base", [{"name": "shell", "description": "d", "input_schema": {}}], {"type": "any"})
    assert "base" in system
    assert "# Tool Use" in system
    assert "You MUST use one of the available tools" in system


def test_build_tool_prompt_roles() -> None:
    prompt = build_tool_prompt(
        "sys",
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    )
    assert prompt.startswith("System: sys")
    assert "User: hi" in prompt and "Assistant: hello" in prompt
    assert prompt.rstrip().endswith("Assistant:")


def test_build_openai_response_without_tools() -> None:
    res = build_openai_response("m", "plain text", [])
    assert res["choices"][0]["finish_reason"] == "stop"
    assert res["choices"][0]["message"]["content"] == "plain text"
    assert "tool_calls" not in res["choices"][0]["message"]


def test_build_openai_response_with_tool_calls() -> None:
    blocks = extract_blocks('<tool_call>\n{"name": "shell", "arguments": {"command": ["ls"]}}\n</tool_call>')
    assert blocks, "파서가 tool_call 블록을 추출해야 한다"
    res = build_openai_response("m", '```json\n{"name": "shell"}\n```', blocks)
    choice = res["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    call = choice["message"]["tool_calls"][0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "shell"
    # arguments는 JSON 문자열 규약
    assert isinstance(call["function"]["arguments"], str)
    assert json.loads(call["function"]["arguments"]) == {"command": ["ls"]}


def test_tool_blocks_to_tool_calls_ids_preserved() -> None:
    blocks = extract_blocks('<tool_call>\n{"name": "a", "arguments": {}}\n</tool_call>')
    calls = tool_blocks_to_tool_calls(blocks)
    assert calls[0]["id"].startswith("toolu_")


# ─── 5. 단위: 스트리밍 프레임 ────────────────────────────────────────


def test_stream_frames_text_only() -> None:
    frames = openai_stream_frames("m", ["안녕", "하세요"], [])
    assert frames[0].startswith("data: ")
    assert '"role": "assistant"' in frames[0]
    assert any("안녕" in f for f in frames)
    assert any('"finish_reason": "stop"' in f for f in frames)
    assert frames[-1] == "data: [DONE]\n\n"


def test_stream_frames_with_tool_calls() -> None:
    blocks = extract_blocks('<tool_call>\n{"name": "shell", "arguments": {"command": ["ls"]}}\n</tool_call>')
    frames = openai_stream_frames("m", ["think..."], blocks)
    joined = "".join(frames)
    assert '"tool_calls"' in joined
    assert '"name": "shell"' in joined or '"name":"shell"' in joined
    assert '"finish_reason": "tool_calls"' in joined
    assert frames[-1] == "data: [DONE]\n\n"


# ─── 6. 엔드포인트: /v1/chat/completions passthrough ─────────────────


def test_endpoint_non_stream_tool_call(tool_calling_client: Any) -> None:
    test_client, fake = tool_calling_client
    res = test_client.post("/v1/chat/completions", json=_base_body())
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["object"] == "chat.completion"
    choice = data["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    call = choice["message"]["tool_calls"][0]
    assert call["function"]["name"] == "shell"
    assert json.loads(call["function"]["arguments"]) == {"command": ["ls"]}
    # 프롬프트에 도구 카탈로그가 주입됐는지
    assert "# Tool Use" in fake.calls[0]["prompt"]


def test_endpoint_tool_result_followup_roundtrip(tool_calling_client: Any) -> None:
    """2턴: tool 결과가 프롬프트에 Function result로 반영되는지."""
    test_client, fake = tool_calling_client
    body = _base_body(
        messages=[
            {"role": "user", "content": "파일 보여줘"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "toolu_abc",
                        "type": "function",
                        "function": {"name": "shell", "arguments": '{"command": ["ls"]}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "toolu_abc", "content": "README.md\nsrc"},
        ]
    )
    res = test_client.post("/v1/chat/completions", json=body)
    assert res.status_code == 200, res.text
    prompt = fake.calls[0]["prompt"]
    assert "Function result for tool_use_id=toolu_abc" in prompt
    assert "README.md" in prompt


def test_endpoint_streaming_tool_call(tool_calling_client: Any) -> None:
    test_client, _ = tool_calling_client
    res = test_client.post("/v1/chat/completions", json=_base_body(stream=True))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    text = res.text
    assert "data: [DONE]" in text
    assert '"tool_calls"' in text
    assert '"finish_reason": "tool_calls"' in text


def test_endpoint_plain_request_still_uses_orchestrator(client: Any) -> None:
    """tools 없는 요청은 기존 오케스트레이터 경로 그대로 (회귀 방지)."""
    test_client, fake = client
    res = test_client.post(
        "/v1/chat/completions",
        json={"model": "qwen3.8:latest", "messages": [{"role": "user", "content": "안녕"}]},
    )
    assert res.status_code == 200, res.text
    # 오케스트레이터 경로는 generate를 직접 호출하지 않을 수 있으므로 상태코드만 확인


def test_endpoint_invalid_tools_rejected(client: Any) -> None:
    test_client, _ = client
    res = test_client.post("/v1/chat/completions", json=_base_body(tools="bad"))
    assert res.status_code == 400


def test_endpoint_missing_model_rejected(tool_calling_client: Any) -> None:
    test_client, _ = tool_calling_client
    body = _base_body()
    body.pop("model")
    res = test_client.post("/v1/chat/completions", json=body)
    assert res.status_code == 400
