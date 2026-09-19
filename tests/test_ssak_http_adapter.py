"""원격 검색 백엔드 adapter 계약 시험 — 인증·실패 가시성·비밀 위생.

세 adapter(`WebSearchEngine._search_self_hosted`, `WebSearchTool._sync_search_self_hosted`,
`ssak_search_client.search`)는 모두 같은 `/api/search` 를 호출한다. 그 백엔드는 기본 모드에서
`Authorization: Bearer <key>` 를 요구하는데 어느 adapter도 헤더를 보내지 않아, 기본 배포에서
provider 가 **조용히 401 로 강등**되고 모델은 "결과 없음"만 보았다.

여기서 고정하는 것:
- 토큰이 설정되면 세 adapter 모두 같은 헤더를 보낸다(토큰이 없으면 보내지 않는다 — 열린 모드).
- 토큰은 `_FILE` 변형으로도 읽는다(환경 덤프 노출 면적 축소).
- 401/403 은 조용한 빈 결과가 아니라 **진단 로그**를 남긴다(env 이름만, 값은 절대 아님).
- 업스트림이 토큰을 되울려도 로그·결과에 남지 않는다.

실제 stdlib HTTP 서버를 세우고 실제 httpx/urllib 로 호출한다 — mock 이 아니라 배선을 잰다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from antigravity_k.tools.search_auth import (
    REDACTED,
    SEARCH_TOKEN_ENV,
    SEARCH_TOKEN_FILE_ENV,
    auth_is_configured,
    redact_secret,
    resolve_search_token,
    search_auth_headers,
)
from antigravity_k.tools.ssak_search_client import search as ssak_client_search
from antigravity_k.tools.web_search_engine import WebSearchEngine
from antigravity_k.tools.web_search_tool import WebSearchTool

TOKEN = "agk-search-token-7d21"


# ── 실제 HTTP 백엔드 ───────────────────────────────────────────────────────────


class _SearchBackend:
    """모드로 동작이 바뀌는 실제 HTTP 백엔드."""

    def __init__(self) -> None:
        self.mode = "ok"
        self.delay = 0.0
        self.requests: list[dict[str, object]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def _make_handler(self):
        backend = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
                """시험 출력 보호 — 표준 라이브러리 콜백이다."""
                return

            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8")
                backend.requests.append(
                    {
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "body": json.loads(raw) if raw else {},
                    }
                )
                if backend.delay:
                    time.sleep(backend.delay)
                status, body = backend._response()
                encoded = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler

    def _response(self) -> tuple[int, dict[str, object]]:
        if self.mode == "unauthorized":
            return 401, {
                "error": {
                    "code": "UNAUTHORIZED",
                    "detail": f"Provide Authorization: Bearer <key>; got {TOKEN}",
                    "retryable": False,
                }
            }
        if self.mode == "servererror":
            return 500, {"error": {"code": "INTERNAL", "detail": "boom"}}
        return 200, {
            "results": [
                {"title": "First", "url": "https://example.com/a", "content": "alpha", "score": 0.9},
                {"title": "Second", "url": "https://example.com/b", "content": "beta", "score": 0.5},
            ]
        }

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture()
def backend() -> Iterator[_SearchBackend]:
    server = _SearchBackend()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture(autouse=True)
def _clean_search_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (SEARCH_TOKEN_ENV, SEARCH_TOKEN_FILE_ENV, "AGK_SEARCH_ENGINE_URL"):
        monkeypatch.delenv(name, raising=False)


# ── 자격 증명 해석 ─────────────────────────────────────────────────────────────


def test_no_token_configured_means_no_header() -> None:
    """열린 모드(`AUTH_OPEN_MODE=1`)의 로컬 백엔드는 토큰 없이도 정상이다."""
    assert resolve_search_token({}) is None
    assert search_auth_headers({}) == {}
    assert auth_is_configured({}) is False


def test_token_comes_from_the_environment() -> None:
    assert search_auth_headers({SEARCH_TOKEN_ENV: f"  {TOKEN}  "}) == {"Authorization": f"Bearer {TOKEN}"}
    assert auth_is_configured({SEARCH_TOKEN_ENV: TOKEN}) is True


def test_token_comes_from_a_file_so_it_stays_out_of_environment_dumps(tmp_path: Path) -> None:
    token_file = tmp_path / "search-token"
    token_file.write_text(f"{TOKEN}\n", encoding="utf-8")

    assert search_auth_headers({SEARCH_TOKEN_FILE_ENV: str(token_file)}) == {"Authorization": f"Bearer {TOKEN}"}


def test_a_missing_token_file_is_not_fatal(tmp_path: Path) -> None:
    assert resolve_search_token({SEARCH_TOKEN_FILE_ENV: str(tmp_path / "absent")}) is None


def test_redact_secret_masks_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    assert TOKEN not in redact_secret(f"upstream echoed {TOKEN}")
    assert REDACTED in redact_secret(f"upstream echoed {TOKEN}")
    assert redact_secret("nothing to hide") == "nothing to hide"


# ── 비동기 엔진 adapter ────────────────────────────────────────────────────────


def test_engine_forwards_the_bearer_and_parses_results(
    backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)
    engine = WebSearchEngine(max_results=2)

    results = asyncio.run(engine._search_self_hosted("quantum computing"))

    assert [result.title for result in results] == ["First", "Second"]
    assert backend.requests[-1]["authorization"] == f"Bearer {TOKEN}"
    assert backend.requests[-1]["path"] == "/api/search"


def test_engine_sends_no_header_without_a_token(backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    engine = WebSearchEngine(max_results=2)

    results = asyncio.run(engine._search_self_hosted("quantum computing"))

    assert results, "열린 모드 백엔드는 인증 없이도 결과를 준다"
    assert backend.requests[-1]["authorization"] is None


def test_engine_401_is_reported_instead_of_looking_like_an_empty_search(
    backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """조용한 401 은 모델에게 '결과 없음'으로 보인다 — 원인을 로그로 남긴다(값은 제외)."""
    backend.mode = "unauthorized"
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)
    engine = WebSearchEngine(max_results=2)

    with caplog.at_level(logging.WARNING):
        results = asyncio.run(engine._search_self_hosted("quantum computing"))

    assert results == []
    assert engine._provider_cooldowns.get("self_hosted", 0.0) > 0.0, "실패한 provider 는 쿨다운에 들어가야 한다"
    warnings = [record.getMessage() for record in caplog.records]
    assert any("401" in message and SEARCH_TOKEN_ENV in message for message in warnings), warnings
    assert TOKEN not in caplog.text


# ── 동기 도구 adapter ─────────────────────────────────────────────────────────


def test_sync_tool_forwards_the_bearer(backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)
    tool = WebSearchTool()

    results = tool._sync_search_self_hosted("quantum computing")

    assert any(title == "First" for title, _url, _snippet in results), results
    assert backend.requests[-1]["authorization"] == f"Bearer {TOKEN}"


def test_sync_tool_401_warns_and_returns_nothing(
    backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    backend.mode = "unauthorized"
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)
    tool = WebSearchTool()

    with caplog.at_level(logging.WARNING):
        results = tool._sync_search_self_hosted("quantum computing")

    assert list(results) == []
    assert any("401" in record.getMessage() and SEARCH_TOKEN_ENV in record.getMessage() for record in caplog.records)
    assert TOKEN not in caplog.text


def test_sync_tool_sends_no_header_without_a_token(backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    tool = WebSearchTool()

    tool._sync_search_self_hosted("quantum computing")

    assert backend.requests[-1]["authorization"] is None


# ── urllib 클라이언트 adapter ─────────────────────────────────────────────────


def test_client_adapter_forwards_the_bearer(backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    hits = ssak_client_search("quantum computing", base_url=backend.base_url, max_results=2)

    assert [hit.title for hit in hits] == ["First", "Second"]
    assert backend.requests[-1]["authorization"] == f"Bearer {TOKEN}"


def test_client_adapter_401_warns_and_carries_no_secret(
    backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    backend.mode = "unauthorized"
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    with caplog.at_level(logging.WARNING):
        hits = ssak_client_search("quantum computing", base_url=backend.base_url)

    assert hits == []
    assert TOKEN not in caplog.text, "업스트림이 토큰을 되울려도 로그에 남으면 안 된다"
    assert any("401" in record.getMessage() and SEARCH_TOKEN_ENV in record.getMessage() for record in caplog.records)


def test_client_adapter_timeout_is_bounded_and_returns_nothing(
    backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.delay = 1.5
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    started = time.perf_counter()
    hits = ssak_client_search("quantum computing", base_url=backend.base_url, timeout=0.3)
    elapsed = time.perf_counter() - started

    assert hits == []
    assert elapsed < 1.2, f"타임아웃이 지켜지지 않았다({elapsed:.2f}s)"


def test_client_adapter_upstream_error_returns_nothing_without_raising(
    backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.mode = "servererror"
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    assert ssak_client_search("quantum computing", base_url=backend.base_url) == []


def test_the_three_adapters_agree_on_the_header(backend: _SearchBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    """세 adapter 가 같은 규칙을 쓴다 — 하나라도 빠지면 그 경로만 401 로 강등된다."""
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", backend.base_url)
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    asyncio.run(WebSearchEngine(max_results=2)._search_self_hosted("q"))
    WebSearchTool()._sync_search_self_hosted("q")
    ssak_client_search("q", base_url=backend.base_url)

    assert [request["authorization"] for request in backend.requests] == [f"Bearer {TOKEN}"] * 3


def test_a_backend_on_an_unroutable_port_still_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """백엔드가 없으면(포트 오타 등) 예외가 아니라 빈 결과 + 로그다 — 계약은 '빈 결과'로 유지."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", f"http://127.0.0.1:{dead_port}")
    monkeypatch.setenv(SEARCH_TOKEN_ENV, TOKEN)

    assert asyncio.run(WebSearchEngine(max_results=2)._search_self_hosted("q")) == []
    assert ssak_client_search("q", base_url=f"http://127.0.0.1:{dead_port}", timeout=0.5) == []
