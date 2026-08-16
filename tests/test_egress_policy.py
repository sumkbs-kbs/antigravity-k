from urllib.request import Request

import httpx
import pytest

from antigravity_k.tools.egress_policy import (
    EgressPolicyError,
    safe_urlopen,
    validate_egress_url,
    validate_httpx_request_async,
)


def test_validate_egress_url_allows_local_ollama():
    assert validate_egress_url("http://localhost:11434/api/tags") == "http://localhost:11434/api/tags"
    assert validate_egress_url("http://127.0.0.1:11434/api/tags") == "http://127.0.0.1:11434/api/tags"


def test_validate_egress_url_rejects_private_and_non_http_targets():
    with pytest.raises(EgressPolicyError):
        validate_egress_url("http://192.168.1.20:11434/api/tags")
    with pytest.raises(EgressPolicyError):
        validate_egress_url("file:///etc/passwd")
    with pytest.raises(EgressPolicyError):
        validate_egress_url("http://localhost:11434/api/tags", allow_local=False)


def test_validate_egress_url_rejects_public_hostname_with_private_dns(monkeypatch):
    monkeypatch.setattr(
        "antigravity_k.tools.egress_policy.resolve_public_http_url_sync",
        lambda url: None,
    )
    with pytest.raises(EgressPolicyError):
        validate_egress_url("https://provider.example/v1/chat/completions")


def test_safe_urlopen_validates_request_before_open(monkeypatch):
    request = Request("http://127.0.0.1:11434/api/tags")
    opened = []

    def fake_urlopen(target, *args, **kwargs):
        opened.append(target.full_url)
        return "response"

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert safe_urlopen(request, timeout=2) == "response"
    assert opened == [request.full_url]


@pytest.mark.asyncio
async def test_async_httpx_hook_is_awaitable_and_validates_request():
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks={"request": [validate_httpx_request_async]},
    ) as client:
        response = await client.get("http://localhost:11434/api/tags")

    assert response.status_code == 200
    assert seen == ["http://localhost:11434/api/tags"]
