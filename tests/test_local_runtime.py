from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from antigravity_k.engine.local_runtime import LocalRuntimeSupervisor
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile
from antigravity_k.engine.provider_adapters.transformers_provider import TransformersProvider


def test_llama_runtime_reuses_an_available_server() -> None:
    profile = SimpleNamespace(
        name="qwen.gguf",
        repo="/models/qwen.gguf",
        provider="llama.cpp",
        api_base="http://127.0.0.1:8080/v1",
    )
    supervisor = LocalRuntimeSupervisor()

    with patch("antigravity_k.engine.local_runtime.safe_urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value = MagicMock()
        assert supervisor.ensure_available(profile) == profile.api_base

    urlopen.assert_called_once()


def test_llama_runtime_starts_server_when_endpoint_is_down() -> None:
    profile = SimpleNamespace(
        name="qwen.gguf",
        repo="/models/qwen.gguf",
        provider="llama.cpp",
        api_base="http://127.0.0.1:8080/v1",
    )
    process = MagicMock()
    process.poll.return_value = None
    with (
        patch("antigravity_k.engine.local_runtime.safe_urlopen", side_effect=OSError("offline")),
        patch("antigravity_k.engine.local_runtime.shutil.which", return_value="/opt/homebrew/bin/llama-server"),
        patch("antigravity_k.engine.local_runtime.subprocess.Popen", return_value=process) as popen,
        patch("antigravity_k.engine.local_runtime.time.sleep"),
    ):
        supervisor = LocalRuntimeSupervisor()
        with patch.object(supervisor, "_wait_until_available", return_value=True):
            assert supervisor.ensure_available(profile) == profile.api_base

    assert popen.call_args.args[0][:7] == [
        "/opt/homebrew/bin/llama-server",
        "-m",
        "/models/qwen.gguf",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
    ]


def test_llama_runtime_reports_installation_reason_when_server_binary_is_missing() -> None:
    profile = SimpleNamespace(
        name="qwen.gguf",
        repo="/models/qwen.gguf",
        provider="llama.cpp",
        api_base="http://127.0.0.1:8080/v1",
    )
    supervisor = LocalRuntimeSupervisor()

    with (
        patch("antigravity_k.engine.local_runtime.safe_urlopen", side_effect=OSError("offline")),
        patch.object(LocalRuntimeSupervisor, "_resolve_binary", return_value=""),
    ):
        try:
            supervisor.ensure_available(profile)
        except RuntimeError as exc:
            assert "llama-server" in str(exc)
            assert "AGK_LLAMA_SERVER_BIN" in str(exc)
        else:
            raise AssertionError("missing llama-server should be reported")


def test_transformers_provider_generates_only_new_tokens() -> None:
    class Tokenizer:
        def __call__(self, prompt: str, return_tensors: str) -> dict[str, object]:
            assert prompt == "hello"
            assert return_tensors == "pt"
            return {"input_ids": [[10, 11]]}

        def decode(self, tokens: object, skip_special_tokens: bool) -> str:
            assert tokens == [20, 21]
            assert skip_special_tokens is True
            return "world"

    class Model:
        def generate(self, **kwargs: object) -> list[list[int]]:
            assert kwargs["max_new_tokens"] == 12
            return [[10, 11, 20, 21]]

    loaded = SimpleNamespace(model=Model(), tokenizer=Tokenizer())

    assert TransformersProvider().generate(loaded, "hello", max_tokens=12) == "world"


def test_transformers_provider_enables_cache_for_verified_native_plan() -> None:
    class Tokenizer:
        def __call__(self, prompt: str, return_tensors: str) -> dict[str, object]:
            return {"input_ids": [[10, 11]]}

        def decode(self, tokens: object, skip_special_tokens: bool) -> str:
            return "world"

    class Model:
        def generate(self, **kwargs: object) -> list[list[int]]:
            assert kwargs["use_cache"] is True
            return [[10, 11, 20, 21]]

    loaded = SimpleNamespace(model=Model(), tokenizer=Tokenizer())
    plan = {"native_attention_enabled": True}

    assert TransformersProvider().generate(loaded, "hello", execution_plan=plan) == "world"


def test_transformers_provider_uses_quantized_cache_only_when_backend_is_available() -> None:
    class Tokenizer:
        def __call__(self, prompt: str, return_tensors: str) -> dict[str, object]:
            return {"input_ids": [[10, 11]]}

        def decode(self, tokens: object, skip_special_tokens: bool) -> str:
            return "world"

    class GenerationConfig:
        cache_implementation = None

    class Model:
        generation_config = GenerationConfig()

        def generate(self, **kwargs: object) -> list[list[int]]:
            assert kwargs["cache_implementation"] == "quantized"
            return [[10, 11, 20, 21]]

    loaded = SimpleNamespace(model=Model(), tokenizer=Tokenizer())
    plan = {"native_attention_enabled": True, "kv_cache_compression_enabled": True}

    with patch(
        "importlib.util.find_spec",
        return_value=object(),
    ):
        result = TransformersProvider().generate(loaded, "hello", execution_plan=plan)

    assert result == "world"


def test_transformers_provider_keeps_default_cache_when_quantized_backend_is_missing() -> None:
    class Tokenizer:
        def __call__(self, prompt: str, return_tensors: str) -> dict[str, object]:
            return {"input_ids": [[10, 11]]}

        def decode(self, tokens: object, skip_special_tokens: bool) -> str:
            return "world"

    class GenerationConfig:
        cache_implementation = None

    class Model:
        generation_config = GenerationConfig()

        def generate(self, **kwargs: object) -> list[list[int]]:
            assert "cache_implementation" not in kwargs
            return [[10, 11, 20, 21]]

    loaded = SimpleNamespace(model=Model(), tokenizer=Tokenizer())
    plan = {"native_attention_enabled": True, "kv_cache_compression_enabled": True}

    with patch("importlib.util.find_spec", return_value=None):
        result = TransformersProvider().generate(loaded, "hello", execution_plan=plan)

    assert result == "world"


def test_model_manager_routes_transformers_profiles_to_direct_loader() -> None:
    manager = object.__new__(ModelManager)
    profile = SimpleNamespace(provider="transformers", repo="/models/qwen", name="qwen")

    with patch.object(ModelManager, "_load_transformers_model", return_value=("model", "tokenizer")) as loader:
        result = manager._load_mlx_model(cast(ModelProfile, cast(object, profile)))

    loader.assert_called_once_with(profile)
    assert result == ("model", "tokenizer")
