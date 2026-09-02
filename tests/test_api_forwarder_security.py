from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest
from starlette.requests import Request

from antigravity_k.api.startup_security import StartupSecurityError


def _load_forwarder():
    path = Path(__file__).parents[1] / "scripts" / "api_forwarder.py"
    spec = importlib.util.spec_from_file_location("agk_api_forwarder", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load api_forwarder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_non_loopback_forwarder_requires_strong_credential(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_forwarder()
    monkeypatch.delenv("AGK_SEC_ACCESS_PIN", raising=False)
    monkeypatch.setenv("AGK_SEC_PIN_HASH_FILE", str(tmp_path / "missing-hash"))

    with pytest.raises(StartupSecurityError):
        module.validate_forwarder_startup("0.0.0.0")


def test_loopback_forwarder_allows_local_bootstrap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_forwarder()
    monkeypatch.delenv("AGK_SEC_ACCESS_PIN", raising=False)
    monkeypatch.setenv("AGK_SEC_PIN_HASH_FILE", str(tmp_path / "missing-hash"))

    module.validate_forwarder_startup("127.0.0.1")


def _request_with_pin(pin: str | None) -> Request:
    headers = [] if pin is None else [(b"x-access-pin", pin.encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/models",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 1234),
            "scheme": "http",
            "root_path": "",
            "http_version": "1.1",
        },
    )


def test_public_forwarder_requires_pin_on_http_and_accepts_valid_pin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_forwarder()
    monkeypatch.setenv("AGK_SEC_ACCESS_PIN", "strong-forwarder-pin")
    monkeypatch.setenv("AGK_SEC_PIN_HASH_FILE", str(tmp_path / "auth-hash"))
    module.validate_forwarder_startup("0.0.0.0")

    assert module._forwarder_request_authenticated(_request_with_pin(None)) is False
    assert module._forwarder_request_authenticated(_request_with_pin("wrong-pin")) is False
    assert module._forwarder_request_authenticated(_request_with_pin("strong-forwarder-pin")) is True
    assert module._forwarder_pin_authenticated("strong-forwarder-pin") is True

    async def call_next(_request: Request):
        return module.JSONResponse(status_code=204)

    response = asyncio.run(module.verify_forwarder_access(_request_with_pin(None), call_next))
    assert response.status_code == 401
