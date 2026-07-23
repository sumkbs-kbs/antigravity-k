"""Tests for the OpenAI adapter."""

import json

from antigravity_k.engine.provider_adapters.openai_adapter import OpenAIAdapter


class TestTranslateRequest:
    def setup_method(self):
        self.adapter = OpenAIAdapter()

    def test_basic_text_message(self):
        payload = {
            "model": "claude-3",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = self.adapter.translate_request(payload)
        assert result["model"] == "claude-3"
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == "Hello"
        assert result["temperature"] == 0.7

    def test_with_system_string(self):
        payload = {
            "model": "claude-3",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        result = self.adapter.translate_request(payload)
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are helpful"

    def test_with_system_list(self):
        payload = {
            "model": "claude-3",
            "system": [{"type": "text", "text": "System prompt here"}],
            "messages": [{"role": "user", "content": "Hi"}],
        }
        result = self.adapter.translate_request(payload)
        assert result["messages"][0]["role"] == "system"
        assert "System prompt here" in result["messages"][0]["content"]

    def test_with_content_list(self):
        payload = {
            "model": "claude-3",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]}
            ],
        }
        result = self.adapter.translate_request(payload)
        assert result["messages"][0]["content"] == "HelloWorld"

    def test_with_tools(self):
        payload = {
            "model": "claude-3",
            "messages": [{"role": "user", "content": "Use a tool"}],
            "tools": [{"name": "test_tool", "description": "A test", "input_schema": {"type": "object"}}],
        }
        result = self.adapter.translate_request(payload)
        assert "tools" in result
        assert result["tools"][0]["type"] == "function"
        assert result["tools"][0]["function"]["name"] == "test_tool"

    def test_custom_temperature(self):
        payload = {
            "model": "claude-3",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.2,
        }
        result = self.adapter.translate_request(payload)
        assert result["temperature"] == 0.2

    def test_no_messages(self):
        payload = {"model": "claude-3"}
        result = self.adapter.translate_request(payload)
        assert result["messages"] == []


class TestTranslateResponse:
    def setup_method(self):
        self.adapter = OpenAIAdapter()

    def test_no_choices(self):
        resp = {"id": "err", "error": "fail"}
        result = self.adapter.translate_response(resp)
        assert result == resp

    def test_basic_text(self):
        resp = {
            "id": "chatcmpl-123",
            "model": "gpt-4",
            "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
        }
        result = self.adapter.translate_response(resp)
        assert result["id"] == "chatcmpl-123"
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello!"

    def test_with_tool_calls(self):
        resp = {
            "id": "chatcmpl-456",
            "model": "gpt-4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Let me use a tool",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": json.dumps({"loc": "Seoul"})},
                            }
                        ],
                    },
                }
            ],
        }
        result = self.adapter.translate_response(resp)
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"
        assert result["content"][1]["name"] == "get_weather"
        assert result["content"][1]["input"]["loc"] == "Seoul"

    def test_empty_choices(self):
        resp = {"id": "x", "model": "y", "choices": []}
        result = self.adapter.translate_response(resp)
        assert result == resp


class TestTranslateStream:
    def setup_method(self):
        self.adapter = OpenAIAdapter()

    def test_returns_chunk_as_is(self):
        chunk = {"choices": [{"delta": {"content": "Hello"}}]}
        result = self.adapter.translate_stream(chunk)
        assert result == chunk
