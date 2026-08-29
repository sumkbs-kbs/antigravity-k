from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from antigravity_k.engine.local_model_discovery import (
    DiscoveredLocalModel,
    LocalModelDiscovery,
)
from antigravity_k.engine.model_policy import ModelRoutingPolicy
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.provider_adapters.inference_providers import LMStudioProvider, get_inference_provider
from antigravity_k.engine.provider_capabilities import LocalProviderCapabilityProbe, ProviderConfigRegistry


def _response(payload: object) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def test_ollama_catalog_normalizes_runtime_metadata() -> None:
    discovery = LocalModelDiscovery(model_dirs=())
    payload = {
        "models": [
            {
                "name": "qwen3.8:latest",
                "model": "qwen3.8:latest",
                "size": 17_000_000_000,
                "details": {
                    "parameter_size": "27.0B",
                    "quantization_level": "Q4_K_M",
                    "family": "qwen2",
                },
            },
            {
                "name": "nomic-embed-text:latest",
                "size": 274_000_000,
                "details": {"family": "bert"},
            },
        ],
    }

    with patch(
        "antigravity_k.engine.local_model_discovery.safe_urlopen",
        return_value=_response(payload),
    ):
        models = discovery.discover()

    assert [model.name for model in models] == ["qwen3.8:latest", "nomic-embed-text:latest"]
    assert models[0].provider == "ollama"
    assert models[0].parameter_count_b == 27.0
    assert models[0].estimated_memory_gb > 15
    assert models[0].quantization == "Q4_K_M"
    assert models[0].role == "reasoning"
    assert models[1].role == "embedding"


def test_openai_compatible_catalog_supports_lmstudio_and_llamacpp() -> None:
    discovery = LocalModelDiscovery(
        model_dirs=(),
        openai_endpoints=(
            ("lmstudio", "http://127.0.0.1:1234/v1"),
            ("llama.cpp", "http://127.0.0.1:8080/v1"),
        ),
    )
    payloads = [
        {"data": [{"id": "lmstudio-community/Qwen2.5-Coder-14B", "context_length": 32768}]},
        {"data": [{"id": "llama-3.2-vision:11b", "owned_by": "llama.cpp"}]},
    ]

    with patch(
        "antigravity_k.engine.local_model_discovery.safe_urlopen",
        side_effect=[_response({}), _response(payloads[0]), _response(payloads[1])],
    ):
        models = discovery.discover()

    assert [(model.provider, model.name) for model in models] == [
        ("lmstudio", "lmstudio-community/Qwen2.5-Coder-14B"),
        ("llama.cpp", "llama-3.2-vision:11b"),
    ]
    assert models[0].role == "coding"
    assert models[0].context_length == 32768
    assert models[1].role == "vision"


def test_unsloth_server_catalog_is_auto_detected() -> None:
    discovery = LocalModelDiscovery(
        model_dirs=(),
        openai_endpoints=(("unsloth", "http://127.0.0.1:18000/v1"),),
    )
    payload = {
        "data": [
            {
                "id": "unsloth/Qwen3.8-27B",
                "backend": "transformers",
                "device": "mps",
                "quantization": "4bit",
                "context_length": 32768,
                "capabilities": ["completion"],
            },
        ],
    }

    with patch(
        "antigravity_k.engine.local_model_discovery.safe_urlopen",
        return_value=_response(payload),
    ):
        models = discovery.discover()

    assert len(models) == 1
    assert models[0].provider == "unsloth"
    assert models[0].name == "unsloth/Qwen3.8-27B"
    assert models[0].quantization == "4bit"
    assert models[0].context_length == 32768


def test_unsloth_environment_endpoint_is_included(monkeypatch) -> None:
    monkeypatch.setenv("UNSLOTH_API_BASE", "http://127.0.0.1:18000/v1")

    assert ("unsloth", "http://127.0.0.1:18000/v1") in LocalModelDiscovery._configured_openai_endpoints()


def test_unsloth_adapter_directory_is_auto_detected(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "Qwen3.8-27B-unsloth-lora"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"0" * 1024)

    models = LocalModelDiscovery(model_dirs=(tmp_path,), disable_network=True).discover()

    assert len(models) == 1
    assert models[0].provider == "unsloth"
    assert models[0].repo == str(adapter_dir)
    assert models[0].role == "reasoning"


def test_transformers_config_and_weights_are_auto_detected(tmp_path: Path) -> None:
    model_dir = tmp_path / "Qwen3.8-27B-Transformers"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        '{"model_type":"qwen2","num_parameters":27000000000,"max_position_embeddings":32768,'
        '"quantization_config":{"bits":4}}',
        encoding="utf-8",
    )
    (model_dir / "model.safetensors").write_bytes(b"0" * 2048)

    models = LocalModelDiscovery(model_dirs=(tmp_path,), disable_network=True).discover()

    assert len(models) == 1
    assert models[0].provider == "transformers"
    assert models[0].parameter_count_b == 27.0
    assert models[0].context_length == 32768
    assert models[0].quantization == "4bit"


def test_optional_local_server_endpoints_are_auto_configured(monkeypatch) -> None:
    monkeypatch.setenv("AGK_VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("AGK_TGI_API_BASE", "http://127.0.0.1:3000/v1")
    monkeypatch.setenv("AGK_KOBOLDCPP_API_BASE", "http://127.0.0.1:5001/v1")
    monkeypatch.setenv("AGK_TEXTGEN_WEBUI_API_BASE", "http://127.0.0.1:5000/v1")

    endpoints = LocalModelDiscovery._configured_openai_endpoints()

    assert {provider for provider, _ in endpoints} >= {"vllm", "tgi", "koboldcpp", "text-generation-webui"}


def test_optional_local_servers_use_openai_compatible_adapter() -> None:
    for provider in ("vllm", "tgi", "koboldcpp", "text-generation-webui"):
        loaded = SimpleNamespace(
            profile=SimpleNamespace(
                name="local-model",
                repo="local-model",
                provider=provider,
                api_base="http://127.0.0.1:9000/v1",
            ),
        )

        assert isinstance(get_inference_provider(loaded), LMStudioProvider)


def test_filesystem_catalog_finds_gguf_and_mlx_directories(tmp_path: Path) -> None:
    gguf = tmp_path / "Qwen3.8-27B-Instruct-Q4_K_M.gguf"
    gguf.write_bytes(b"0" * 1024)
    mlx_dir = tmp_path / "Qwen3.8-27B-4bit-mlx"
    mlx_dir.mkdir()
    (mlx_dir / "config.json").write_text("{}", encoding="utf-8")
    (mlx_dir / "mlx_model.safetensors").write_bytes(b"0" * 2048)

    models = LocalModelDiscovery(model_dirs=(tmp_path,), disable_network=True).discover()

    assert {model.provider for model in models} == {"llama.cpp", "mlx"}
    gguf_model = next(model for model in models if model.provider == "llama.cpp")
    assert gguf_model.quantization == "Q4_K_M"
    assert gguf_model.parameter_count_b == 27.0
    assert gguf_model.role == "reasoning"


def test_unreachable_runtime_is_fail_soft() -> None:
    discovery = LocalModelDiscovery(model_dirs=(), disable_network=False)

    with patch(
        "antigravity_k.engine.local_model_discovery.safe_urlopen",
        side_effect=OSError("connection refused"),
    ):
        assert discovery.discover() == ()


def test_registry_merges_discovered_models_without_overwriting_configured_profiles() -> None:
    registry = ModelRegistry()
    configured = registry.get_model("qwen3.8")
    assert configured is not None

    discovered = (
        DiscoveredLocalModel(
            name="qwen3.8:latest",
            repo="qwen3.8:latest",
            provider="ollama",
            api_base="http://127.0.0.1:11434",
            role="reasoning",
            parameter_count_b=27.0,
            estimated_memory_gb=17.0,
            context_length=32768,
            quantization="Q4_K_M",
            capabilities=("completion", "tools"),
            source="ollama",
        ),
        DiscoveredLocalModel(
            name="new-coder:7b",
            repo="new-coder:7b",
            provider="ollama",
            api_base="http://127.0.0.1:11434",
            role="coding",
            parameter_count_b=7.0,
            estimated_memory_gb=5.0,
            context_length=8192,
            quantization="Q4_K_M",
            capabilities=(),
            source="ollama",
        ),
    )

    added = registry.merge_discovered_models(discovered)

    assert [profile.name for profile in added] == ["new-coder:7b"]
    assert registry.get_model("qwen3.8") is configured
    assert registry.get_model("qwen3.8:latest") is configured
    assert registry.get_model("new-coder:7b") is not None


def test_registry_refresh_delegates_to_discovery() -> None:
    registry = ModelRegistry()
    discovery = MagicMock()
    discovery.discover.return_value = ()

    assert registry.refresh_local_models(discovery=discovery) == ()
    discovery.discover.assert_called_once_with()


def test_llamacpp_profile_uses_openai_compatible_inference_adapter() -> None:
    loaded = SimpleNamespace(
        profile=SimpleNamespace(
            name="Qwen3.8-27B-Q4_K_M.gguf",
            repo="/models/Qwen3.8-27B-Q4_K_M.gguf",
            provider="llama.cpp",
            api_base="http://127.0.0.1:8080/v1",
        ),
    )

    assert isinstance(get_inference_provider(loaded), LMStudioProvider)


def test_llamacpp_capability_probe_uses_its_openai_models_endpoint() -> None:
    profile = ModelProfile(
        name="qwen3.8:latest",
        repo="qwen3.8:latest",
        role="reasoning",
        provider="llama.cpp",
        api_base="http://127.0.0.1:8080/v1",
    )
    registry = cast(ProviderConfigRegistry, cast(object, SimpleNamespace(get_provider_config=lambda _: {})))
    probe = LocalProviderCapabilityProbe(registry)

    with patch(
        "antigravity_k.engine.provider_capabilities.safe_urlopen",
        return_value=_response({"data": [{"id": "qwen3.8:latest", "capabilities": ["tools"]}]}),
    ) as urlopen:
        capability = probe.observe(profile)

    assert urlopen.call_args.args[0].full_url == "http://127.0.0.1:8080/v1/models"
    assert capability["runtime_status"] == "available"
    assert capability["native_tool_calling"] == "supported"


def test_small_local_models_can_be_explicitly_enabled_without_changing_quality_default() -> None:
    profile = ModelRegistry().get_model("llava:latest")
    assert profile is None
    policy = ModelRoutingPolicy(enabled=True, min_local_parameter_count_b=20.0)
    assert policy.allow_small_local_models is False

    enabled = ModelRoutingPolicy(
        enabled=True,
        min_local_parameter_count_b=20.0,
        allow_small_local_models=True,
    )
    discovered = DiscoveredLocalModel(
        name="llava:latest",
        repo="llava:latest",
        provider="ollama",
        api_base="http://127.0.0.1:11434",
        role="vision",
        parameter_count_b=7.0,
    )
    model = ModelRegistry()
    model.merge_discovered_models((discovered,))
    selected = model.get_model("llava:latest")
    assert selected is not None
    assert policy.decide(selected).allowed is False
    assert enabled.decide(selected).allowed is True
