import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from antigravity_k.engine.provider_adapters.inference_providers import (
    LMStudioProvider,
    OllamaProvider,
    get_inference_provider,
)
from antigravity_k.engine.tool_call_parser import EventType, ToolCallParser


def _loaded_model(context_length: int = 262_144):
    return SimpleNamespace(profile=SimpleNamespace(name="qwen3.6:latest", context_length=context_length))


def _loaded_lmstudio_model():
    return SimpleNamespace(
        profile=SimpleNamespace(
            name="lmstudio/qwen3.6",
            repo="qwen3.6:latest",
            provider="lmstudio",
            api_base="http://127.0.0.1:1234/v1",
            api_key_env="LM_STUDIO_API_KEY",
        ),
    )


def _loaded_unsloth_model():
    return SimpleNamespace(
        profile=SimpleNamespace(
            name="unsloth/qwen3.6",
            repo="qwen3.6:latest",
            provider="unsloth",
            api_base="http://127.0.0.1:18000/v1",
            api_key_env="UNSLOTH_API_KEY",
        ),
    )


def test_ollama_native_tools_are_sent_and_emitted_as_tool_call():
    response = MagicMock()
    response.__iter__.return_value = iter(
        [
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "read_file",
                                    "arguments": {"file_path": "README.md"},
                                },
                            },
                        ],
                    },
                    "done": False,
                },
            ).encode()
            + b"\n",
            json.dumps({"done": True}).encode() + b"\n",
        ],
    )
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    provider = OllamaProvider()

    with patch.object(provider, "_resolve_endpoint", return_value=("http://localhost:11434/v1", "ollama")):
        with patch(
            "antigravity_k.engine.provider_adapters.inference_providers.urllib.request.urlopen",
            return_value=request_context,
        ) as urlopen:
            chunks = list(
                provider.stream_generate(
                    _loaded_model(),
                    "read README",
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "description": "Read a file",
                                "parameters": {"type": "object", "properties": {}},
                            },
                        },
                    ],
                ),
            )

    request = json.loads(urlopen.call_args.args[0].data.decode())
    assert request["tools"][0]["function"]["name"] == "read_file"
    output = "".join(chunks)
    parser = ToolCallParser()
    events = parser.feed(output) + parser.flush()
    calls = [
        event.tool_call
        for event in events
        if event.type == EventType.TOOL_CALL_COMPLETE and event.tool_call is not None
    ]
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"file_path": "README.md"}


def test_ollama_single_native_tool_json_content_is_synthesized_as_a_tool_call():
    # Given: Qwen returns exactly one required tool's arguments as fenced JSON content.
    response = MagicMock()
    response.__iter__.return_value = iter(
        [
            json.dumps(
                {
                    "message": {"role": "assistant", "content": '```json\n{"file_path": "config.yaml"}\n```'},
                    "done": True,
                },
            ).encode()
            + b"\n",
        ],
    )
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    provider = OllamaProvider()

    # When: the adapter streams the native tool response.
    with (
        patch.object(provider, "_resolve_endpoint", return_value=("http://localhost:11434/v1", "ollama")),
        patch(
            "antigravity_k.engine.provider_adapters.inference_providers.urllib.request.urlopen",
            return_value=request_context,
        ),
    ):
        output = "".join(
            provider.stream_generate(
                _loaded_model(),
                "read config",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "parameters": {
                                "type": "object",
                                "properties": {"file_path": {"type": "string"}},
                                "required": ["file_path"],
                            },
                        },
                    },
                ],
            ),
        )

    # Then: the tool loop receives a parseable call with the returned arguments.
    parser = ToolCallParser()
    events = parser.feed(output) + parser.flush()
    calls = [
        event.tool_call
        for event in events
        if event.type == EventType.TOOL_CALL_COMPLETE and event.tool_call is not None
    ]
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"file_path": "config.yaml"}


def test_qwen_non_stream_generation_uses_native_no_think_endpoint():
    response = MagicMock()
    response.read.return_value = json.dumps(
        {"message": {"content": "Python 3.13 was released in 2024.", "thinking": "private plan"}},
    ).encode()
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    provider = OllamaProvider()

    with (
        patch.object(provider, "_resolve_endpoint", return_value=("http://localhost:11434/v1", "ollama")),
        patch(
            "antigravity_k.engine.provider_adapters.inference_providers.safe_urlopen",
            return_value=request_context,
        ) as urlopen,
    ):
        result = provider.generate(_loaded_model(), "When was Python 3.13 released?", max_tokens=120)

    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode())
    assert request.full_url == "http://localhost:11434/api/chat"
    assert payload["think"] is False
    assert result == "Python 3.13 was released in 2024."


def test_qwen_native_stream_uses_the_profile_context_budget():
    response = MagicMock()
    response.__iter__.return_value = iter([json.dumps({"done": True}).encode() + b"\n"])
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    provider = OllamaProvider()

    with (
        patch.object(provider, "_resolve_endpoint", return_value=("http://localhost:11434/v1", "ollama")),
        patch(
            "antigravity_k.engine.provider_adapters.inference_providers.safe_urlopen",
            return_value=request_context,
        ) as urlopen,
    ):
        list(provider.stream_generate(_loaded_model(context_length=16_384), "Hello"))

    payload = json.loads(urlopen.call_args.args[0].data.decode())
    assert payload["options"]["num_ctx"] == 12_288
    assert payload["options"]["repeat_penalty"] == 1.0


def test_lmstudio_provider_uses_its_openai_compatible_endpoint(monkeypatch):
    response = MagicMock()
    response.__iter__.return_value = iter(
        [b'data: {"choices":[{"delta":{"content":"LM Studio OK"}}]}\n', b"data: [DONE]\n"],
    )
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    monkeypatch.setenv("LM_STUDIO_API_KEY", "test-token")
    provider = LMStudioProvider()

    with patch(
        "antigravity_k.engine.provider_adapters.inference_providers.safe_urlopen",
        return_value=request_context,
    ) as urlopen:
        output = "".join(provider.stream_generate(_loaded_lmstudio_model(), "Hello"))

    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode())
    assert request.full_url == "http://127.0.0.1:1234/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-token"
    assert payload["model"] == "qwen3.6:latest"
    assert output == "LM Studio OK"


def test_lmstudio_provider_allows_a_local_server_without_an_api_token(monkeypatch):
    response = MagicMock()
    response.__iter__.return_value = iter(
        [b'data: {"choices":[{"delta":{"content":"LM Studio OK"}}]}\n', b"data: [DONE]\n"],
    )
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    monkeypatch.delenv("LM_STUDIO_API_KEY", raising=False)
    provider = LMStudioProvider()

    with patch(
        "antigravity_k.engine.provider_adapters.inference_providers.safe_urlopen",
        return_value=request_context,
    ) as urlopen:
        output = "".join(provider.stream_generate(_loaded_lmstudio_model(), "Hello"))

    request = urlopen.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:1234/v1/chat/completions"
    assert request.get_header("Authorization") is None
    assert output == "LM Studio OK"


def test_lmstudio_profile_selects_the_local_openai_provider():
    assert isinstance(get_inference_provider(_loaded_lmstudio_model()), LMStudioProvider)


def test_unsloth_profile_selects_read_only_local_provider(monkeypatch):
    # Given
    response = MagicMock()
    response.__iter__.return_value = iter(
        [b'data: {"choices":[{"delta":{"content":"Unsloth OK"}}]}\n', b"data: [DONE]\n"],
    )
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    monkeypatch.setenv("UNSLOTH_API_KEY", "scoped-test-token")

    # When
    provider = get_inference_provider(_loaded_unsloth_model())
    with patch(
        "antigravity_k.engine.provider_adapters.inference_providers.safe_urlopen",
        return_value=request_context,
    ) as urlopen:
        output = "".join(
            provider.stream_generate(
                _loaded_unsloth_model(),
                "Hello",
                tools=[{"type": "function", "function": {"name": "run_python"}}],
            ),
        )

    # Then
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode())
    assert type(provider).__name__ == "UnslothProvider"
    assert request.full_url == "http://127.0.0.1:18000/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer scoped-test-token"
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert output == "Unsloth OK"


def test_ollama_native_tool_rejection_falls_back_to_xml_prompt():
    response = MagicMock()
    response.__iter__.return_value = iter(
        [
            json.dumps(
                {
                    "message": {"content": '<tool_call>{"name":"read_file","arguments":{}}</tool_call>'},
                    "done": True,
                },
            ).encode()
            + b"\n",
        ],
    )
    request_context = MagicMock()
    request_context.__enter__.return_value = response
    request_context.__exit__.return_value = False
    provider = OllamaProvider()

    with patch.object(provider, "_resolve_endpoint", return_value=("http://localhost:11434/v1", "ollama")):
        with patch(
            "antigravity_k.engine.provider_adapters.inference_providers.urllib.request.urlopen",
            side_effect=[RuntimeError("tools are not supported"), request_context],
        ) as urlopen:
            chunks = list(
                provider.stream_generate(
                    _loaded_model(),
                    "read README",
                    tools=[{"type": "function", "function": {"name": "read_file"}}],
                ),
            )

    assert len(urlopen.call_args_list) == 2
    first_request = json.loads(urlopen.call_args_list[0].args[0].data.decode())
    fallback_request = json.loads(urlopen.call_args_list[1].args[0].data.decode())
    assert "tools" in first_request
    assert "tools" not in fallback_request
    assert "<tool_call>" in "".join(chunks)
