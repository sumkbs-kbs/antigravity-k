from __future__ import annotations

import importlib.util
import json
import os
import time
import urllib.request
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, NotRequired, Protocol, TypedDict
from urllib.error import HTTPError, URLError

from antigravity_k.tools.egress_policy import EgressPolicyError, safe_urlopen

if TYPE_CHECKING:
    from .model_registry import ModelProfile


NativeToolCalling = Literal["supported", "unsupported", "unknown"]
RuntimeStatus = Literal["available", "unavailable", "not_required"]


class ProviderCapability(TypedDict):
    model: str
    provider: str
    is_local: bool
    native_tool_calling: NativeToolCalling
    runtime_status: RuntimeStatus
    source: str
    detail: str
    reported_capabilities: list[str]
    reported_model_count: int
    reported_model_ids: NotRequired[list[str]]


class ProviderConfigRegistry(Protocol):
    def get_provider_config(self, provider: str) -> Mapping[str, object]: ...


def remediation_hint(profile: ModelProfile, capability: ProviderCapability) -> str:
    """Return the next operator action for an unavailable local provider."""
    if capability["runtime_status"] != "unavailable":
        return ""

    detail = capability["detail"]
    match profile.backend.casefold():
        case "ollama":
            if "404" in detail:
                return f"ollama pull {profile.repo}"
            return "ollama serve"
        case "lmstudio" | "lm_studio":
            if "401" in detail or "403" in detail:
                return "LM Studio 토큰을 .env의 LM_STUDIO_API_KEY에 추가"
            loaded_ids = capability.get("reported_model_ids", [])
            if loaded_ids:
                loaded_id = loaded_ids[0]
                return (
                    f"LM Studio에서 {loaded_id}를 로드하거나 " f"config.yaml의 {profile.name} repo를 같은 식별자로 변경"
                )
            if "not loaded" in detail or "no loaded models" in detail:
                return "LM Studio에서 모델을 로드한 뒤 다시 진단"
            return "LM Studio Local Server를 127.0.0.1:1234/v1에서 시작"
        case "mlx":
            return "uv sync --extra mlx"
        case _:
            return ""


class LocalProviderCapabilityProbe:
    _CACHE_TTL_SECONDS = 60.0

    def __init__(self, registry: ProviderConfigRegistry) -> None:
        self._registry = registry
        self._cache: dict[str, ProviderCapability] = {}
        self._observed_at: dict[str, float] = {}

    def observe(self, profile: ModelProfile, *, refresh: bool = False) -> ProviderCapability:
        now = time.monotonic()
        cached = self._cache.get(profile.name)
        observed_at = self._observed_at.get(profile.name, 0.0)
        if cached is not None and not refresh and now - observed_at < self._CACHE_TTL_SECONDS:
            return cached

        provider = profile.backend.casefold()
        match provider:
            case "ollama":
                capability = self._probe_ollama(profile)
            case "lmstudio" | "lm_studio":
                capability = self._probe_lmstudio(profile)
            case "mlx":
                capability = self._probe_mlx(profile)
            case _:
                capability = self._static_unknown(profile)

        self._cache[profile.name] = capability
        self._observed_at[profile.name] = now
        return capability

    def clear(self) -> None:
        self._cache.clear()
        self._observed_at.clear()

    def _probe_ollama(self, profile: ModelProfile) -> ProviderCapability:
        base_url, api_key = self._endpoint(profile, "http://localhost:11434")
        request = urllib.request.Request(
            f"{self._native_base(base_url)}/api/show",
            data=json.dumps({"name": profile.name}).encode("utf-8"),
            headers=self._headers(api_key),
        )
        try:
            payload = self._request_json(request)
        except (EgressPolicyError, HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            return self._unavailable(profile, "ollama:/api/show", exc)

        raw_capabilities = payload.get("capabilities", [])
        capabilities = (
            [item.casefold() for item in raw_capabilities if isinstance(item, str)]
            if isinstance(raw_capabilities, list)
            else []
        )
        native_tools: NativeToolCalling = "unknown"
        if capabilities:
            native_tools = "supported" if "tools" in capabilities else "unsupported"
        return self._capability(
            profile,
            native_tools,
            "available",
            "ollama:/api/show",
            "Ollama model metadata reported its capability list.",
            capabilities,
        )

    def _probe_lmstudio(self, profile: ModelProfile) -> ProviderCapability:
        base_url, api_key = self._endpoint(profile, "http://127.0.0.1:1234/v1")
        api_base = base_url.rstrip("/")
        if not api_base.endswith("/v1"):
            api_base = f"{api_base}/v1"
        request = urllib.request.Request(f"{api_base}/models", headers=self._headers(api_key))
        try:
            payload = self._request_json(request)
        except (EgressPolicyError, HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            return self._unavailable(profile, "lmstudio:/v1/models", exc)

        entries = payload.get("data", [])
        models = [entry for entry in entries if isinstance(entry, Mapping)] if isinstance(entries, list) else []
        loaded_ids: list[str] = []
        for entry in models:
            model_id = entry.get("id")
            if isinstance(model_id, str):
                loaded_ids.append(model_id)
        identifiers = {profile.name, profile.repo}
        matched = next(
            (entry for entry in models if isinstance(entry.get("id"), str) and entry["id"] in identifiers),
            None,
        )
        if matched is None:
            detail = (
                "LM Studio server has no loaded models."
                if not loaded_ids
                else "LM Studio server reachable; configured model identifiers are not loaded."
            )
            return self._capability(
                profile,
                "unknown",
                "unavailable",
                "lmstudio:/v1/models",
                detail,
                [],
                reported_model_count=len(models),
                reported_model_ids=loaded_ids[:5],
            )
        capabilities = self._reported_tool_capabilities(matched)
        native_tools: NativeToolCalling = "unknown"
        if capabilities:
            native_tools = "supported" if "tools" in capabilities else "unsupported"
        return self._capability(
            profile,
            native_tools,
            "available",
            "lmstudio:/v1/models",
            "LM Studio model discovery does not guarantee tool calling when it omits capability metadata.",
            capabilities,
            reported_model_count=len(models),
            reported_model_ids=loaded_ids[:5],
        )

    def _probe_mlx(self, profile: ModelProfile) -> ProviderCapability:
        installed = importlib.util.find_spec("mlx_lm") is not None
        runtime_status: RuntimeStatus = "available" if installed else "unavailable"
        detail = (
            "The direct MLX provider does not pass a native tool schema to mlx_lm."
            if installed
            else "mlx_lm is not installed for the direct MLX provider."
        )
        return self._capability(
            profile,
            "unsupported",
            runtime_status,
            "mlx_lm:direct",
            detail,
        )

    def _static_unknown(self, profile: ModelProfile) -> ProviderCapability:
        return self._capability(
            profile,
            "unknown",
            "not_required",
            "provider:static",
            "This provider does not expose a local native-tool capability probe.",
        )

    def _endpoint(self, profile: ModelProfile, default_base_url: str) -> tuple[str, str]:
        provider_config = self._registry.get_provider_config(profile.backend)
        configured_base_url = provider_config.get("base_url", "") if isinstance(provider_config, Mapping) else ""
        base_url = profile.api_base or configured_base_url or default_base_url
        configured_key_env = provider_config.get("api_key_env", "") if isinstance(provider_config, Mapping) else ""
        key_env = profile.api_key_env or configured_key_env
        api_key = os.environ.get(key_env, "") if isinstance(key_env, str) and key_env else ""
        if not api_key and profile.backend.casefold() == "ollama":
            api_key = os.environ.get("OLLAMA_API_KEY", "") or "ollama"
        return str(base_url).rstrip("/"), api_key

    @staticmethod
    def _native_base(base_url: str) -> str:
        if base_url.endswith("/v1"):
            return base_url[:-3]
        return base_url

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _request_json(request: urllib.request.Request) -> dict[str, object]:
        with safe_urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _reported_tool_capabilities(entry: Mapping[str, object] | None) -> list[str]:
        if entry is None:
            return []
        raw_capabilities = entry.get("capabilities", [])
        capabilities = (
            [item.casefold() for item in raw_capabilities if isinstance(item, str)]
            if isinstance(raw_capabilities, list)
            else []
        )
        supports_tools = entry.get("supports_tools")
        if supports_tools is True:
            capabilities.append("tools")
        return capabilities

    @staticmethod
    def _capability(
        profile: ModelProfile,
        native_tool_calling: NativeToolCalling,
        runtime_status: RuntimeStatus,
        source: str,
        detail: str,
        reported_capabilities: list[str] | None = None,
        reported_model_count: int = 0,
        reported_model_ids: list[str] | None = None,
    ) -> ProviderCapability:
        return {
            "model": profile.name,
            "provider": profile.backend,
            "is_local": profile.is_local,
            "native_tool_calling": native_tool_calling,
            "runtime_status": runtime_status,
            "source": source,
            "detail": detail,
            "reported_capabilities": reported_capabilities or [],
            "reported_model_count": reported_model_count,
            "reported_model_ids": reported_model_ids or [],
        }

    def _unavailable(self, profile: ModelProfile, source: str, exc: BaseException) -> ProviderCapability:
        return self._capability(
            profile,
            "unknown",
            "unavailable",
            source,
            f"{type(exc).__name__}: {exc}",
        )
