import json
from collections.abc import Mapping
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelRouter
from antigravity_k.engine.provider_capabilities import (
    LocalProviderCapabilityProbe,
    ProviderCapability,
    RuntimeStatus,
    remediation_hint,
)

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]


class _Registry:
    def __init__(self, providers: dict[str, dict[str, str]] | None = None) -> None:
        self._providers = providers or {}

    def get_provider_config(self, provider: str) -> dict[str, str]:
        return self._providers.get(provider, {})


def _response(payload: Mapping[str, JsonValue]) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    return context


def test_ollama_probe_reports_model_native_tools():
    profile = ModelProfile(
        name="qwen3.6:latest",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="ollama",
    )
    probe = LocalProviderCapabilityProbe(_Registry({"ollama": {"base_url": "http://localhost:11434"}}))

    with patch(
        "antigravity_k.engine.provider_capabilities.safe_urlopen",
        return_value=_response({"capabilities": ["completion", "tools"]}),
    ) as urlopen:
        capability = probe.observe(profile)

    request = urlopen.call_args.args[0]
    assert request.full_url == "http://localhost:11434/api/show"
    assert json.loads(request.data.decode("utf-8")) == {"name": "qwen3.6:latest"}
    assert capability["native_tool_calling"] == "supported"
    assert capability["runtime_status"] == "available"
    assert capability["reported_capabilities"] == ["completion", "tools"]


def test_lmstudio_probe_reports_explicit_model_tool_metadata():
    profile = ModelProfile(
        name="local-qwen",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="lmstudio",
        api_base="http://127.0.0.1:1234/v1",
    )
    probe = LocalProviderCapabilityProbe(_Registry())

    with patch(
        "antigravity_k.engine.provider_capabilities.safe_urlopen",
        return_value=_response({"data": [{"id": "local-qwen", "capabilities": ["tools"]}]}),
    ) as urlopen:
        capability = probe.observe(profile)

    assert urlopen.call_args.args[0].full_url == "http://127.0.0.1:1234/v1/models"
    assert capability["native_tool_calling"] == "supported"
    assert capability["runtime_status"] == "available"
    assert capability["reported_model_count"] == 1


def test_lmstudio_probe_marks_configured_model_unavailable_on_identifier_mismatch():
    profile = ModelProfile(
        name="lmstudio/qwen",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="lmstudio",
    )
    probe = LocalProviderCapabilityProbe(_Registry())

    with patch(
        "antigravity_k.engine.provider_capabilities.safe_urlopen",
        return_value=_response({"data": [{"id": "qwen/qwen3-30b-a3b-instruct"}]}),
    ):
        capability = probe.observe(profile)

    assert capability["runtime_status"] == "unavailable"
    assert capability["reported_model_count"] == 1
    assert capability.get("reported_model_ids") == ["qwen/qwen3-30b-a3b-instruct"]


def test_lmstudio_probe_marks_unavailable_when_no_model_is_loaded():
    profile = ModelProfile(
        name="lmstudio/qwen",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="lmstudio",
    )
    probe = LocalProviderCapabilityProbe(_Registry())

    with patch(
        "antigravity_k.engine.provider_capabilities.safe_urlopen",
        return_value=_response({"data": []}),
    ):
        capability = probe.observe(profile)

    assert capability["runtime_status"] == "unavailable"
    assert capability.get("reported_model_ids") == []


def test_unsloth_probe_is_optional_when_endpoint_is_not_configured(monkeypatch):
    # Given
    monkeypatch.delenv("UNSLOTH_API_BASE", raising=False)
    profile = ModelProfile(name="unsloth/qwen", repo="qwen3.6:latest", role="reasoning", provider="unsloth")
    probe = LocalProviderCapabilityProbe(_Registry())

    # When
    with patch("antigravity_k.engine.provider_capabilities.safe_urlopen") as urlopen:
        capability = probe.observe(profile)

    # Then
    urlopen.assert_not_called()
    assert capability["runtime_status"] == "unavailable"
    assert capability["native_tool_calling"] == "unsupported"
    assert "not configured" in capability["detail"]


def test_unsloth_probe_reports_configured_server_failure():
    # Given
    profile = ModelProfile(
        name="unsloth/qwen",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="unsloth",
        api_base="http://127.0.0.1:18000/v1",
    )
    probe = LocalProviderCapabilityProbe(_Registry())

    # When
    with patch("antigravity_k.engine.provider_capabilities.safe_urlopen", side_effect=URLError("connection refused")):
        capability = probe.observe(profile)

    # Then
    assert capability["runtime_status"] == "unavailable"
    assert capability["native_tool_calling"] == "unsupported"
    assert "connection refused" in capability["detail"]


def test_unsloth_probe_rejects_non_loopback_endpoint_without_request():
    # Given
    profile = ModelProfile(
        name="unsloth/qwen",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="unsloth",
        api_base="https://models.example.com/v1",
    )
    probe = LocalProviderCapabilityProbe(_Registry())

    # When
    with patch("antigravity_k.engine.provider_capabilities.safe_urlopen") as urlopen:
        capability = probe.observe(profile)

    # Then
    urlopen.assert_not_called()
    assert capability["runtime_status"] == "unavailable"
    assert "loopback" in capability["detail"]


def test_unsloth_probe_reports_runtime_metadata_and_disables_server_tools():
    # Given
    profile = ModelProfile(
        name="unsloth/qwen",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="unsloth",
        api_base="http://127.0.0.1:18000/v1",
    )
    probe = LocalProviderCapabilityProbe(_Registry())
    payload: dict[str, JsonValue] = {
        "data": [
            {
                "id": "qwen3.6:latest",
                "backend": "mlx",
                "device": "mps",
                "quantization": "Q4_K_M",
                "context_length": 32768,
                "capabilities": ["tools"],
            },
        ],
    }

    # When
    with patch(
        "antigravity_k.engine.provider_capabilities.safe_urlopen",
        return_value=_response(payload),
    ) as urlopen:
        capability = probe.observe(profile)

    # Then
    assert urlopen.call_args.args[0].full_url == "http://127.0.0.1:18000/v1/models"
    assert capability["runtime_status"] == "available"
    assert capability["native_tool_calling"] == "unsupported"
    assert capability.get("reported_backend") == "mlx"
    assert capability.get("reported_device") == "mps"
    assert capability.get("reported_quantization") == "Q4_K_M"
    assert capability.get("reported_context_length") == 32768
    assert "disabled" in capability["detail"]


def test_mlx_probe_marks_native_tools_unsupported():
    profile = ModelProfile(name="mlx-qwen", repo="mlx-community/qwen", role="reasoning", provider="mlx")
    capability = LocalProviderCapabilityProbe(_Registry()).observe(profile)

    assert capability["native_tool_calling"] == "unsupported"
    assert capability["source"] == "mlx_lm:direct"


def _capability_for(
    profile: ModelProfile,
    status: RuntimeStatus,
    detail: str,
) -> ProviderCapability:
    return {
        "model": profile.name,
        "provider": profile.backend,
        "is_local": True,
        "native_tool_calling": "unknown",
        "runtime_status": status,
        "source": "test",
        "detail": detail,
        "reported_capabilities": [],
        "reported_model_count": 0,
    }


def test_remediation_hint_for_ollama_server_down():
    profile = ModelProfile(name="qwen3.6:latest", repo="qwen3.6:latest", role="reasoning", provider="ollama")
    capability = _capability_for(profile, "unavailable", "URLError: connection refused")

    assert remediation_hint(profile, capability) == "ollama serve"


def test_remediation_hint_for_missing_ollama_model():
    profile = ModelProfile(name="qwen3.6:latest", repo="qwen3.6:latest", role="reasoning", provider="ollama")
    capability = _capability_for(profile, "unavailable", "HTTPError: HTTP Error 404")

    assert remediation_hint(profile, capability) == "ollama pull qwen3.6:latest"


def test_remediation_hint_for_lmstudio_token_failure():
    profile = ModelProfile(name="lmstudio/qwen", repo="qwen", role="reasoning", provider="lmstudio")
    capability = _capability_for(profile, "unavailable", "HTTPError: HTTP Error 401")

    assert remediation_hint(profile, capability) == "LM Studio 토큰을 .env의 LM_STUDIO_API_KEY에 추가"


def test_remediation_hint_suggests_loaded_lmstudio_identifier():
    profile = ModelProfile(name="lmstudio/qwen", repo="qwen3.6:latest", role="reasoning", provider="lmstudio")
    capability = _capability_for(
        profile,
        "unavailable",
        "LM Studio server reachable; configured model identifiers are not loaded.",
    )
    capability["reported_model_ids"] = ["qwen/qwen3-30b-a3b-instruct", "other-model"]

    assert (
        remediation_hint(profile, capability)
        == "LM Studio에서 qwen/qwen3-30b-a3b-instruct를 로드하거나 config.yaml의 lmstudio/qwen repo를 같은 식별자로 변경"
    )


def test_remediation_hint_for_lmstudio_without_loaded_models():
    profile = ModelProfile(name="lmstudio/qwen", repo="qwen3.6:latest", role="reasoning", provider="lmstudio")
    capability = _capability_for(profile, "unavailable", "LM Studio server has no loaded models.")
    capability["reported_model_ids"] = []

    assert remediation_hint(profile, capability) == "LM Studio에서 모델을 로드한 뒤 다시 진단"


def test_remediation_hint_for_missing_mlx_runtime():
    profile = ModelProfile(name="mlx-qwen", repo="mlx-community/qwen", role="reasoning", provider="mlx")
    capability = _capability_for(profile, "unavailable", "mlx_lm is not installed")

    assert remediation_hint(profile, capability) == "uv sync --extra mlx"


def test_remediation_hint_is_empty_when_available():
    profile = ModelProfile(name="qwen3.6:latest", repo="qwen3.6:latest", role="reasoning", provider="ollama")
    capability = _capability_for(profile, "available", "ready")

    assert remediation_hint(profile, capability) == ""


def test_manager_status_exposes_capabilities_to_router():
    profile = ModelProfile(name="qwen3.6:latest", repo="qwen3.6:latest", role="reasoning", provider="ollama")
    registry = MagicMock(spec=ModelRegistry)
    registry._raw = {}
    registry.memory_config = SimpleNamespace(max_loaded_gb=100.0, unload_cooldown_sec=60.0, auto_unload=False)
    registry.list_models.return_value = [profile]
    router = ModelRouter(registry)
    manager = ModelManager(registry=registry, router=router)
    manager._capability_probe.observe = MagicMock(
        return_value={
            "model": profile.name,
            "provider": "ollama",
            "is_local": True,
            "native_tool_calling": "supported",
            "runtime_status": "available",
            "source": "ollama:/api/show",
            "detail": "test",
            "reported_capabilities": ["tools"],
            "reported_model_count": 0,
        },
    )

    status = manager.status()

    assert status["provider_capabilities"][profile.name]["native_tool_calling"] == "supported"
    assert status["routing"]["provider_capabilities"][profile.name]["runtime_status"] == "available"
