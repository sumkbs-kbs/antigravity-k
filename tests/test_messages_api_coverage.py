"""Phase 58: messages_api 커버리지 보강 — 예외/검증/스트리밍 분기.

Phase 25(anthropic_tool_bridge·disclosure 100%)에 이은 두 번째 커버리티 패스.
응답 어댑터의 검증 실패·생성 실패·스트리밍 예외·빈 청크 폴백 경로를 잠근다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api import dependencies as api_dependencies
from antigravity_k.api.routes import messages_api
from antigravity_k.api.server import app


class _FakeManager:
    def __init__(self, response: str = "로컬 모델 응답입니다.", chunks: list[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response
        self.chunks = chunks if chunks is not None else [response]
        self.fail = False

    def generate(self, *, prompt: str, target: str, **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "target": target, **kwargs})
        if self.fail:
            raise RuntimeError("mlx inference boom")
        return self.response

    def stream_generate(self, *, prompt: str, target: str, **kwargs: Any) -> list[str]:
        self.calls.append({"prompt": prompt, "target": target, **kwargs})
        if self.fail:
            raise RuntimeError("mlx stream boom")
        return list(self.chunks)


def _install(fake: _FakeManager) -> None:
    app.dependency_overrides[api_dependencies.get_model_manager] = lambda: fake


def _uninstall() -> None:
    app.dependency_overrides.pop(api_dependencies.get_model_manager, None)


@pytest.fixture()
def client() -> Any:
    fake = _FakeManager()
    _install(fake)
    yield TestClient(app), fake
    _uninstall()


def _base_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": "qwen3.8",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": "안녕하세요"}],
    }
    body.update(overrides)
    return body


# ── 단위: 어댑터 헬퍼 ─────────────────────────────────────────────


class TestAdapterHelpers:
    def test_system_as_block_list(self) -> None:
        system = [{"type": "text", "text": "규칙 1"}, {"type": "text", "text": "규칙 2"}, "문자열은 무시"]
        assert messages_api._extract_system_text(system) == "규칙 1\n규칙 2"  # noqa: SLF001

    def test_system_none_and_string(self) -> None:
        assert messages_api._extract_system_text(None) == ""  # noqa: SLF001
        assert messages_api._extract_system_text("문자열 시스템") == "문자열 시스템"  # noqa: SLF001

    def test_effective_system_appends_directive(self) -> None:
        """tool_choice 지시문이 시스템 프롬프트에 결합된다."""
        system = messages_api._build_effective_system(  # noqa: SLF001
            "기본 시스템",
            [{"name": "read_file", "description": "파일 읽기", "input_schema": {"type": "object"}}],
            {"type": "any"},
        )
        assert "기본 시스템" in system
        assert "read_file" in system

    def test_effective_system_empty_without_tools(self) -> None:
        assert messages_api._build_effective_system("", [], None) == ""  # noqa: SLF001

    def test_system_unknown_type_is_empty(self) -> None:
        assert messages_api._extract_system_text(12345) == ""  # noqa: SLF001

    def test_flatten_skips_non_mapping_and_bad_roles(self) -> None:
        raw = [
            "not a mapping",
            {"role": "system", "content": "차단되는 역할"},
            {"role": "user", "content": "정상"},
        ]
        flat = messages_api._flatten_messages(raw)  # noqa: SLF001
        assert flat == [{"role": "user", "content": "정상"}]

    def test_flatten_non_sequence_is_empty(self) -> None:
        assert messages_api._flatten_messages(3.14) == []  # noqa: SLF001

    def test_tools_must_be_array(self) -> None:
        tools, err = messages_api._validate_tools({"name": "x"})  # noqa: SLF001
        assert tools == []
        assert err == "tools: must be an array"

    def test_each_tool_must_be_object(self) -> None:
        tools, err = messages_api._validate_tools(["name"])  # noqa: SLF001
        assert tools == []
        assert err == "tools: each tool must be an object"

    def test_token_estimate_empty_is_zero(self) -> None:
        assert messages_api._count_tokens_estimate("") == 0  # noqa: SLF001

    def test_split_chunks_covers_all_text(self) -> None:
        text = "x" * 600
        pieces = messages_api._split_chunks(text, size=256)  # noqa: SLF001
        assert "".join(pieces) == text
        assert len(pieces) == 3


# ── 요청 검증 엔드포인트 분기 ─────────────────────────────────────


class TestRequestValidation:
    def test_non_object_body(self, client: Any) -> None:
        test_client, _ = client
        res = test_client.post("/v1/messages", content=b'["array"]', headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["message"] == "Request body must be a JSON object"

    def test_invalid_json_body(self, client: Any) -> None:
        test_client, _ = client
        res = test_client.post("/v1/messages", content=b"{broken", headers={"content-type": "application/json"})
        assert res.status_code == 400
        assert res.json()["error"]["message"] == "Invalid JSON body"

    def test_tools_rejected_when_not_array(self, client: Any) -> None:
        test_client, _ = client
        res = test_client.post("/v1/messages", json=_base_body(tools={"name": "x"}))
        assert res.status_code == 400
        assert res.json()["error"]["message"] == "tools: must be an array"

    def test_tools_rejected_when_element_not_object(self, client: Any) -> None:
        test_client, _ = client
        res = test_client.post("/v1/messages", json=_base_body(tools=["x"]))
        assert res.status_code == 400
        assert res.json()["error"]["message"] == "tools: each tool must be an object"


# ── 생성 실패 경로 ───────────────────────────────────────────────


class TestGenerationFailures:
    def test_non_streaming_generate_failure_returns_529(self, client: Any) -> None:
        test_client, fake = client
        fake.fail = True
        res = test_client.post("/v1/messages", json=_base_body())
        assert res.status_code == 529
        assert "Model generation failed" in res.json()["error"]["message"]

    def test_streaming_generator_failure_becomes_text_block(self, client: Any) -> None:
        test_client, fake = client
        fake.fail = True
        with test_client.stream("POST", "/v1/messages", json=_base_body(stream=True)) as res:
            assert res.status_code == 200
            events = [json.loads(line[6:]) for line in res.iter_lines() if line.startswith("data: ")]
        types = [e["type"] for e in events]
        assert "content_block_start" in types
        error_deltas = [e for e in events if e["type"] == "content_block_delta" and e["delta"]["type"] == "text_delta"]
        assert any("mlx stream boom" in d["delta"]["text"] for d in error_deltas)
        stop = [e for e in events if e["type"] == "message_delta"][0]
        assert stop["delta"]["stop_reason"] == "end_turn"


# ── 스트리밍 폴백/복원 경로 ───────────────────────────────────────────


class TestStreamingReconstruction:
    def test_all_empty_chunks_emit_no_text_block(self, client: Any) -> None:
        """전 청크가 빈 값이면 text 블록 자체가 생략된다 (build_content_blocks 계약)."""
        test_client, fake = client
        fake.chunks = ["", ""]
        with test_client.stream("POST", "/v1/messages", json=_base_body(stream=True)) as res:
            events = [json.loads(line[6:]) for line in res.iter_lines() if line.startswith("data: ")]
        starts = [e for e in events if e["type"] == "content_block_start"]
        assert starts == []  # 빈 텍스트 → text 블록 생략, tool_use도 없음
        stop = [e for e in events if e["type"] == "message_delta"][0]
        assert stop["delta"]["stop_reason"] == "end_turn"

    def test_tool_call_in_stream_renders_tool_use_block(self, client: Any) -> None:
        """완성 텍스트에 tool_call이 있으면 tool_use 블록 + input_json_delta로 전송."""
        test_client, fake = client
        fake.chunks = ['<tool_call>\n{"name": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>']
        with test_client.stream("POST", "/v1/messages", json=_base_body(stream=True)) as res:
            events = [json.loads(line[6:]) for line in res.iter_lines() if line.startswith("data: ")]
        types = [e["type"] for e in events]
        starts = [e for e in events if e["type"] == "content_block_start"]
        tool_starts = [e for e in starts if e["content_block"]["type"] == "tool_use"]
        assert tool_starts, "tool_use content_block_start 이벤트 필요"
        assert tool_starts[0]["content_block"]["name"] == "read_file"
        json_deltas = [e for e in events if e.get("delta", {}).get("type") == "input_json_delta"]
        assert json_deltas and json.loads(json_deltas[0]["delta"]["partial_json"]) == {"path": "a.py"}
        stop = [e for e in events if e["type"] == "message_delta"][0]
        assert stop["delta"]["stop_reason"] == "tool_use"

    def test_stream_async_wrapper_yields_all_chunks(self) -> None:
        """stream_generate_async가 동기 제너레이터를 전부 비동기로 전달한다."""
        import asyncio

        class _IterManager:
            def stream_generate(self, *, prompt: str, target: str, **kwargs: Any) -> Any:
                return iter(["a", "b", "c"])

        async def run() -> list[str]:
            got: list[str] = []
            async for chunk in messages_api.stream_generate_async(_IterManager(), "p", "m"):
                got.append(chunk)
            return got

        assert asyncio.run(run()) == ["a", "b", "c"]
