"""
테스트: 프로토콜 변환기
======================
ProtocolTranslator의 OpenAI/Anthropic ↔ 내부 형식 상호 변환 기능 테스트.
"""
import pytest

from antigravity_k.engine.protocol_translator import (
    APIFormat,
    ProtocolTranslator,
)

@pytest.fixture
def translator():
    return ProtocolTranslator()

class TestProtocolTranslator:
    def test_detect_format(self, translator):
        openai_req = {"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]}
        assert translator.detect_format(openai_req) == APIFormat.OPENAI
        
        anthropic_req = {"anthropic_version": "2023-06-01", "messages": []}
        assert translator.detect_format(anthropic_req) == APIFormat.ANTHROPIC
        
        internal_req = {"prompt": "Hello", "model": "local"}
        assert translator.detect_format(internal_req) == APIFormat.INTERNAL

    def test_translate_request_openai_to_internal(self, translator):
        openai_req = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a bot"},
                {"role": "user", "content": "Hello"}
            ],
            "temperature": 0.5
        }
        
        internal = translator.translate_request(openai_req, APIFormat.OPENAI, APIFormat.INTERNAL)
        assert internal["system"] == "You are a bot"
        assert len(internal["messages"]) == 1
        assert internal["messages"][0]["role"] == "user"
        assert internal["temperature"] == 0.5
        assert internal["model"] == "gpt-4"

    def test_translate_request_anthropic_to_internal(self, translator):
        anthropic_req = {
            "model": "claude-3-opus",
            "system": "You are a bot",
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }
        
        internal = translator.translate_request(anthropic_req, APIFormat.ANTHROPIC, APIFormat.INTERNAL)
        assert internal["system"] == "You are a bot"
        assert len(internal["messages"]) == 1
        assert internal["messages"][0]["role"] == "user"
        assert internal["model"] == "claude-3-opus"

    def test_translate_request_internal_to_openai(self, translator):
        internal_req = {
            "model": "local-model",
            "system": "You are a bot",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.8
        }
        
        openai = translator.translate_request(internal_req, APIFormat.INTERNAL, APIFormat.OPENAI)
        assert openai["model"] == "local-model"
        assert len(openai["messages"]) == 2
        assert openai["messages"][0]["role"] == "system"
        assert openai["messages"][1]["role"] == "user"
        assert openai["temperature"] == 0.8

    def test_translate_response_internal_to_openai(self, translator):
        internal_resp = {
            "content": "Hi there",
            "model": "local-model",
            "finish_reason": "stop",
            "tokens_in": 10,
            "tokens_out": 20
        }
        
        openai = translator.translate_response(internal_resp, APIFormat.OPENAI, APIFormat.INTERNAL)
        assert "choices" in openai
        assert openai["choices"][0]["message"]["content"] == "Hi there"
        assert openai["usage"]["total_tokens"] == 30

    def test_translate_response_internal_to_anthropic(self, translator):
        internal_resp = {
            "content": "Hi there",
            "model": "local-model",
            "finish_reason": "stop",
            "tokens_in": 10,
            "tokens_out": 20
        }
        
        anthropic = translator.translate_response(internal_resp, APIFormat.ANTHROPIC, APIFormat.INTERNAL)
        assert anthropic["type"] == "message"
        assert anthropic["content"][0]["text"] == "Hi there"
        assert anthropic["usage"]["input_tokens"] == 10
        assert anthropic["usage"]["output_tokens"] == 20

    def test_translate_same_format(self, translator):
        req = {"prompt": "test"}
        res = translator.translate_request(req, APIFormat.INTERNAL, APIFormat.INTERNAL)
        assert res == req
        assert res is not req  # Should be a copy
