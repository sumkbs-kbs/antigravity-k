from __future__ import annotations

import urllib.request
from http.client import HTTPResponse
from typing import cast
from urllib.parse import urlsplit
from urllib.request import Request

import httpx

from .web_search_quality import (
    canonicalize_url,
    is_public_http_url,
    resolve_public_http_url_sync,
)

_LOCAL_HOSTS = frozenset({"localhost", "localhost.localdomain", "127.0.0.1", "::1"})


class EgressPolicyError(ValueError):
    pass


def _target_url(target: str | Request) -> str:
    return target.full_url if isinstance(target, Request) else target


def _is_local_host(hostname: str) -> bool:
    return hostname.casefold() in _LOCAL_HOSTS or hostname.casefold().endswith(".localhost")


def validate_egress_url(
    url: str,
    *,
    allow_local: bool = True,
    resolve_dns: bool = True,
) -> str:
    canonical = canonicalize_url(url)
    if not canonical:
        raise EgressPolicyError("egress URL must be an unauthenticated HTTP(S) URL")

    hostname = urlsplit(canonical).hostname or ""
    if _is_local_host(hostname):
        if allow_local:
            return canonical
        raise EgressPolicyError("local egress is disabled for this connector")

    if not is_public_http_url(canonical):
        raise EgressPolicyError(f"private or non-public egress blocked: {hostname}")
    if resolve_dns and resolve_public_http_url_sync(canonical) is None:
        raise EgressPolicyError(f"egress DNS resolution is not public: {hostname}")
    return canonical


def safe_urlopen(
    target: str | Request,
    allow_local: bool = True,
    timeout: float | None = None,
) -> HTTPResponse:
    _ = validate_egress_url(_target_url(target), allow_local=allow_local)
    if timeout is None:
        return cast(HTTPResponse, urllib.request.urlopen(target))
    return cast(HTTPResponse, urllib.request.urlopen(target, timeout=timeout))


def validate_httpx_request(request: httpx.Request) -> None:
    validate_egress_url(str(request.url))


async def validate_httpx_request_async(request: httpx.Request) -> None:
    validate_httpx_request(request)


def validate_public_httpx_request(request: httpx.Request) -> None:
    """Reject local/private destinations for untrusted outbound requests."""
    validate_egress_url(str(request.url), allow_local=False)


async def validate_public_httpx_request_async(request: httpx.Request) -> None:
    """Async event-hook variant of :func:`validate_public_httpx_request`."""
    validate_public_httpx_request(request)


__all__ = [
    "EgressPolicyError",
    "safe_urlopen",
    "validate_egress_url",
    "validate_httpx_request",
    "validate_httpx_request_async",
    "validate_public_httpx_request",
    "validate_public_httpx_request_async",
]
