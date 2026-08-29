"""테스트: 프로토콜 변환기.
======================
ProtocolTranslator의 OpenAI/Anthropic ↔ 내부 형식 상호 변환 기능 테스트.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.protocol_translator import APIFormat, ProtocolTranslator


@pytest.fixture
def t() -> ProtocolTranslator:
    return ProtocolTranslator()


class TestProtocolTranslator:
    # ─── 포맷 감지 ───────────────────────────────────────────────────

    def test_detect_format_openai(self, t: ProtocolTranslator):
        openai_req = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
        assert t.detect_format(openai_req) == APIFormat.OPENAI

    def test_detect_format_anthropic(self, t: ProtocolTranslator):
        anthropic_req = {"anthropic_version": "2023-06-01", "messages": []}
        assert t.detect_format(anthropic_req) == APIFormat.ANTHROPIC

    def test_detect_format_internal(self, t: ProtocolTranslator):
        internal_req = {"prompt": "Hello", "model": "local"}
        assert t.detect_format(internal_req) == APIFormat.INTERNAL

    def test_detect_format_fallback(self, t: ProtocolTranslator):
        """알 수 없는 포맷은 기본 OpenAI로 처리."""
        unknown = {"unknown": "data"}
        assert t.detect_format(unknown) == APIFormat.OPENAI

    # ─── 요청 변환: OpenAI → 내부 ───────────────────────────────────

    def test_translate_request_openai_to_internal(self, t: ProtocolTranslator):
        openai_req = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a bot"},
                {"role": "user", "content": "Hello"},
            ],
            "temperature": 0.5,
        }

        internal = t.translate_request(openai_req, APIFormat.OPENAI, APIFormat.INTERNAL)
        assert internal["system"] == "You are a bot"
        assert len(internal["messages"]) == 1
        assert internal["messages"][0]["role"] == "user"
        assert internal["temperature"] == 0.5
        assert internal["model"] == "gpt-4"

    # ─── 요청 변환: Anthropic → 내부 ────────────────────────────────

    def test_translate_request_anthropic_to_internal(self, t: ProtocolTranslator):
        anthropic_req = {
            "model": "claude-3-opus",
            "system": "You are a bot",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        internal = t.translate_request(anthropic_req, APIFormat.ANTHROPIC, APIFormat.INTERNAL)
        assert internal["system"] == "You are a bot"
        assert len(internal["messages"]) == 1
        assert internal["messages"][0]["role"] == "user"
        assert internal["model"] == "claude-3-opus"

    # ─── 요청 변환: 내부 → OpenAI ───────────────────────────────────

    def test_translate_request_internal_to_openai(self, t: ProtocolTranslator):
        internal_req = {
            "model": "local-model",
            "system": "You are a bot",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.8,
        }

        openai = t.translate_request(internal_req, APIFormat.INTERNAL, APIFormat.OPENAI)
        assert openai["model"] == "local-model"
        assert len(openai["messages"]) == 2
        assert openai["messages"][0]["role"] == "system"
        assert openai["messages"][1]["role"] == "user"
        assert openai["temperature"] == 0.8

    # ─── 요청 변환: 내부 → OpenAI (stop 포함) ──────────────────────

    def test_internal_to_openai_request_with_stop(self, t: ProtocolTranslator):
        internal_req = {
            "model": "local-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stop": ["\n", "END"],
        }
        openai = t.translate_request(internal_req, APIFormat.INTERNAL, APIFormat.OPENAI)
        assert openai["stop"] == ["\n", "END"]

    # ─── 요청 변환: 내부 → Anthropic ────────────────────────────────

    def test_internal_to_anthropic_request(self, t: ProtocolTranslator):
        internal_req = {
            "model": "local-model",
            "system": "Be helpful",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.3,
            "stop": ["STOP"],
            "stream": True,
        }
        anthropic = t.translate_request(internal_req, APIFormat.INTERNAL, APIFormat.ANTHROPIC)
        assert anthropic["model"] == "local-model"
        assert anthropic["system"] == "Be helpful"
        assert anthropic["temperature"] == 0.3
        assert anthropic["stop_sequences"] == ["STOP"]
        assert anthropic["stream"] is True

    # ─── 요청 변환: 동일 포맷 ───────────────────────────────────────

    def test_translate_request_same_format(self, t: ProtocolTranslator):
        req = {"prompt": "test"}
        res = t.translate_request(req, APIFormat.INTERNAL, APIFormat.INTERNAL)
        assert res == req
        assert res is not req  # Should be a copy

    # ─── 응답 변환: 내부 → OpenAI ───────────────────────────────────

    def test_translate_response_internal_to_openai(self, t: ProtocolTranslator):
        internal_resp = {
            "content": "Hi there",
            "model": "local-model",
            "finish_reason": "stop",
            "tokens_in": 10,
            "tokens_out": 20,
        }

        openai = t.translate_response(internal_resp, APIFormat.OPENAI, APIFormat.INTERNAL)
        assert "choices" in openai
        assert openai["choices"][0]["message"]["content"] == "Hi there"
        assert openai["usage"]["total_tokens"] == 30

    # ─── 응답 변환: 내부 → Anthropic ────────────────────────────────

    def test_translate_response_internal_to_anthropic(self, t: ProtocolTranslator):
        internal_resp = {
            "content": "Hi there",
            "model": "local-model",
            "finish_reason": "stop",
            "tokens_in": 10,
            "tokens_out": 20,
        }

        anthropic = t.translate_response(internal_resp, APIFormat.ANTHROPIC, APIFormat.INTERNAL)
        assert anthropic["type"] == "message"
        assert anthropic["content"][0]["text"] == "Hi there"
        assert anthropic["usage"]["input_tokens"] == 10
        assert anthropic["usage"]["output_tokens"] == 20

    # ─── 응답 변환: OpenAI → 내부 ───────────────────────────────────

    def test_translate_response_openai_to_internal(self, t: ProtocolTranslator):
        openai_resp = {
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello back"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10},
        }
        internal = t.translate_response(openai_resp, APIFormat.INTERNAL, APIFormat.OPENAI)
        assert internal["content"] == "Hello back"
        assert internal["model"] == "gpt-4"
        assert internal["tokens_in"] == 5
        assert internal["tokens_out"] == 10

    def test_translate_response_openai_to_internal_empty_choices(self, t: ProtocolTranslator):
        """choices가 빈 배열일 때 기본값 처리."""
        openai_resp = {"model": "gpt-4", "choices": [], "usage": {}}
        internal = t.translate_response(openai_resp, APIFormat.INTERNAL, APIFormat.OPENAI)
        assert internal["content"] == ""
        assert internal["finish_reason"] == "stop"

    # ─── 응답 변환: Anthropic → 내부 ────────────────────────────────

    def test_translate_response_anthropic_to_internal(self, t: ProtocolTranslator):
        anthropic_resp = {
            "model": "claude-3",
            "content": [{"type": "text", "text": "Hello back"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }
        internal = t.translate_response(anthropic_resp, APIFormat.INTERNAL, APIFormat.ANTHROPIC)
        assert internal["content"] == "Hello back"
        assert internal["model"] == "claude-3"
        assert internal["finish_reason"] == "end_turn"
        assert internal["tokens_in"] == 5
        assert internal["tokens_out"] == 10

    def test_translate_response_anthropic_to_internal_multiple_blocks(self, t: ProtocolTranslator):
        """여러 content 블록 처리."""
        anthropic_resp = {
            "content": [
                {"type": "text", "text": "Part 1. "},
                {"type": "text", "text": "Part 2."},
            ],
            "usage": {},
        }
        internal = t.translate_response(anthropic_resp, APIFormat.INTERNAL, APIFormat.ANTHROPIC)
        assert internal["content"] == "Part 1. Part 2."

    # ─── 응답 변환: 동일 포맷 ───────────────────────────────────────

    def test_translate_response_same_format(self, t: ProtocolTranslator):
        resp = {"content": "test"}
        res = t.translate_response(resp, APIFormat.INTERNAL, APIFormat.INTERNAL)
        assert res == resp
        assert res is not resp  # Should be a copy

    # ─── _extract_content 유틸 ──────────────────────────────────────

    def test_extract_content_string(self, t: ProtocolTranslator):
        assert t._extract_content("hello") == "hello"

    def test_extract_content_list_text_only(self, t: ProtocolTranslator):
        content = [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]
        assert t._extract_content(content) == "Hello\nWorld"

    def test_extract_content_multimodal_preserves_list(self, t: ProtocolTranslator):
        """멀티모달 컨텐츠(image_url 등)는 리스트 그대로 보존."""
        content = [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ]
        result = t._extract_content(content)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_extract_content_none(self, t: ProtocolTranslator):
        assert t._extract_content(None) == ""

    def test_extract_content_empty_string(self, t: ProtocolTranslator):
        assert t._extract_content("") == ""

    def test_extract_content_empty_list(self, t: ProtocolTranslator):
        assert t._extract_content([]) == ""

    def test_extract_content_no_text_key(self, t: ProtocolTranslator):
        """type='text'이지만 text 키가 없는 경우."""
        content = [{"type": "text"}]
        assert t._extract_content(content) == ""

    # ─── 라우팅 메서드 직접 테스트 ───────────────────────────────────

    def test_to_internal_request_openai(self, t: ProtocolTranslator):
        result = t._to_internal_request({"messages": [{"role": "user", "content": "Hi"}]}, APIFormat.OPENAI)
        assert "messages" in result

    def test_to_internal_request_anthropic(self, t: ProtocolTranslator):
        result = t._to_internal_request({"messages": [{"role": "user", "content": "Hi"}]}, APIFormat.ANTHROPIC)
        assert "messages" in result

    def test_to_internal_request_unknown(self, t: ProtocolTranslator):
        result = t._to_internal_request({"foo": "bar"}, APIFormat.INTERNAL)
        assert result == {"foo": "bar"}

    def test_from_internal_request_openai(self, t: ProtocolTranslator):
        result = t._from_internal_request({"messages": [{"role": "user", "content": "Hi"}]}, APIFormat.OPENAI)
        assert "model" in result

    def test_from_internal_request_anthropic(self, t: ProtocolTranslator):
        result = t._from_internal_request({"messages": [{"role": "user", "content": "Hi"}]}, APIFormat.ANTHROPIC)
        assert "model" in result

    def test_from_internal_request_unknown(self, t: ProtocolTranslator):
        result = t._from_internal_request({"foo": "bar"}, APIFormat.INTERNAL)
        assert result == {"foo": "bar"}

    def test_to_internal_response_openai(self, t: ProtocolTranslator):
        result = t._to_internal_response(
            {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}], "usage": {}},
            APIFormat.OPENAI,
        )
        assert result["content"] == "hi"

    def test_to_internal_response_anthropic(self, t: ProtocolTranslator):
        result = t._to_internal_response(
            {"content": [{"type": "text", "text": "hi"}], "usage": {}},
            APIFormat.ANTHROPIC,
        )
        assert result["content"] == "hi"

    def test_to_internal_response_unknown(self, t: ProtocolTranslator):
        result = t._to_internal_response({"foo": "bar"}, APIFormat.INTERNAL)
        assert result == {"foo": "bar"}

    def test_from_internal_response_openai(self, t: ProtocolTranslator):
        result = t._from_internal_response({"content": "hi"}, APIFormat.OPENAI)
        assert "choices" in result

    def test_from_internal_response_anthropic(self, t: ProtocolTranslator):
        result = t._from_internal_response({"content": "hi"}, APIFormat.ANTHROPIC)
        assert result["type"] == "message"

    def test_from_internal_response_unknown(self, t: ProtocolTranslator):
        result = t._from_internal_response({"foo": "bar"}, APIFormat.INTERNAL)
        assert result == {"foo": "bar"}

    # ─── 에지 케이스 ────────────────────────────────────────────────

    def test_openai_request_no_system(self, t: ProtocolTranslator):
        """system 메시지가 없으면 빈 문자열."""
        req = {"messages": [{"role": "user", "content": "Hello"}]}
        internal = t.translate_request(req, APIFormat.OPENAI, APIFormat.INTERNAL)
        assert internal["system"] == ""

    def test_openai_request_empty_messages(self, t: ProtocolTranslator):
        """messages가 빈 배열."""
        req = {"messages": []}
        internal = t.translate_request(req, APIFormat.OPENAI, APIFormat.INTERNAL)
        assert internal["messages"] == []
        assert internal["system"] == ""

    def test_anthropic_request_no_system(self, t: ProtocolTranslator):
        """Anthropic 요청에 system 필드가 없으면 빈 문자열."""
        req = {"messages": [{"role": "user", "content": "Hi"}]}
        internal = t.translate_request(req, APIFormat.ANTHROPIC, APIFormat.INTERNAL)
        assert internal["system"] == ""

    def test_anthropic_request_empty_messages(self, t: ProtocolTranslator):
        req = {"messages": []}
        internal = t.translate_request(req, APIFormat.ANTHROPIC, APIFormat.INTERNAL)
        assert internal["messages"] == []

    def test_internal_to_anthropic_request_no_system(self, t: ProtocolTranslator):
        """system이 없으면 결과에 포함되지 않음."""
        req = {"messages": [{"role": "user", "content": "Hi"}]}
        anthropic = t.translate_request(req, APIFormat.INTERNAL, APIFormat.ANTHROPIC)
        assert "system" not in anthropic

    def test_internal_to_anthropic_request_no_temp_stop(self, t: ProtocolTranslator):
        """temperature/stop/stream이 없으면 결과에 포함되지 않음."""
        req = {"messages": [{"role": "user", "content": "Hi"}]}
        anthropic = t.translate_request(req, APIFormat.INTERNAL, APIFormat.ANTHROPIC)
        assert "temperature" not in anthropic
        assert "stop_sequences" not in anthropic
        assert "stream" not in anthropic

    def test_internal_to_openai_request_no_stop(self, t: ProtocolTranslator):
        """stop이 없으면 결과에 포함되지 않음."""
        req = {"messages": [{"role": "user", "content": "Hi"}]}
        openai = t.translate_request(req, APIFormat.INTERNAL, APIFormat.OPENAI)
        assert "stop" not in openai
