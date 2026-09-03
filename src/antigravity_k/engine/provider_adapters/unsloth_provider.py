from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, override
from urllib.parse import urlsplit, urlunsplit

from .inference_providers import LMStudioProvider, LoadedModelArg

type ProviderConfigValue = str | int | float | bool | None


class UnslothProfile(Protocol):
    api_base: str
    api_key_env: str


class LoadedUnslothModel(Protocol):
    profile: UnslothProfile


@dataclass(frozen=True, slots=True)
class UnslothEndpointError(ValueError):
    endpoint: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"Unsloth endpoint {self.reason}: {self.endpoint or '<not configured>'}"


def normalize_unsloth_api_base(base_url: str) -> str:
    endpoint = base_url.strip()
    if not endpoint:
        raise UnslothEndpointError(endpoint=endpoint, reason="is not configured")

    try:
        parsed = urlsplit(endpoint)
    except ValueError as exc:
        raise UnslothEndpointError(endpoint=endpoint, reason="is malformed") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnslothEndpointError(endpoint=endpoint, reason="must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise UnslothEndpointError(endpoint=endpoint, reason="must not contain credentials, query, or fragment")
    if parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"}:
        raise UnslothEndpointError(endpoint=endpoint, reason="must use a loopback host")

    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def resolve_unsloth_settings(
    profile: UnslothProfile,
    provider_config: Mapping[str, ProviderConfigValue],
) -> tuple[str, str]:
    configured_base = provider_config.get("base_url", "")
    config_base_url = configured_base if isinstance(configured_base, str) else ""
    base_url = profile.api_base or config_base_url or os.environ.get("UNSLOTH_API_BASE", "") or "http://127.0.0.1:8080/v1"

    configured_key_env = provider_config.get("api_key_env", "")
    config_key_env = configured_key_env if isinstance(configured_key_env, str) else ""
    key_env = profile.api_key_env or config_key_env or "UNSLOTH_API_KEY"
    return normalize_unsloth_api_base(base_url), os.environ.get(key_env, "")


class UnslothProvider(LMStudioProvider):
    forwards_native_tools: bool = False

    @override
    def _resolve_endpoint(self, loaded: LoadedModelArg) -> tuple[str, str]:
        return resolve_unsloth_settings(loaded.profile, self._provider_config())

    @staticmethod
    def _provider_config() -> Mapping[str, ProviderConfigValue]:
        try:
            from antigravity_k.engine.model_registry import ModelRegistry

            return ModelRegistry().get_provider_config("unsloth")
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            return {}
