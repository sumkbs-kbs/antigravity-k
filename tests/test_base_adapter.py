"""Tests for the base provider adapter."""

import pytest

from antigravity_k.engine.provider_adapters.base_adapter import BaseProviderAdapter


class TestBaseProviderAdapter:
    def test_cannot_instantiate(self):
        """Abstract class should not be instantiable directly."""
        with pytest.raises(TypeError):
            BaseProviderAdapter()

    def test_concrete_subclass(self):
        class ConcreteAdapter(BaseProviderAdapter):
            def translate_request(self, anthropic_payload):
                return {"messages": anthropic_payload.get("messages", [])}

            def translate_response(self, provider_response):
                return {"content": provider_response.get("choices", [{}])[0].get("message", {})}

            def translate_stream(self, provider_chunk):
                return {"delta": provider_chunk.get("delta", {})}

        adapter = ConcreteAdapter()
        assert isinstance(adapter, BaseProviderAdapter)

        # Test translate_request
        req = adapter.translate_request({"messages": [{"role": "user", "content": "hi"}]})
        assert req["messages"][0]["role"] == "user"

        # Test translate_response
        resp = adapter.translate_response({"choices": [{"message": {"content": "hello"}}]})
        assert resp["content"]["content"] == "hello"

        # Test translate_stream
        chunk = adapter.translate_stream({"delta": {"text": "hello"}})
        assert chunk["delta"]["text"] == "hello"
