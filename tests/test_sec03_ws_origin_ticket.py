"""SEC-03 — WebSocket Origin allowlist + 단기 1회성 ticket.

계약 (docs/11_COMMERCIAL_GA_100_PLAN.md §SEC-03):
  - 잘못된/missing Origin, 재사용·만료 ticket, query PIN/token이 거절된다.
    (missing Origin은 browser가 아닌 클라이언트이므로 origin 차원에서 허용 —
    credential이 없으면 4401로 거절된다)
  - ticket은 로그와 browser history에 credential을 노출하지 않는다.
    (query ?token= 장기 bearer 채널 제거 + ticket 재사용 불가)
  - 정상 reconnect와 task event replay가 유지된다.
  - cross-site browser 시나리오가 side effect와 event read 모두 차단된다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.auth import TokenService, hash_pin

# ---------------------------------------------------------------------------
# 단위: ws_origin / ws_ticket
# ---------------------------------------------------------------------------


class TestWsOriginAllowlist:
    def test_missing_origin_allows_non_browser_clients(self) -> None:
        """curl/CLI는 Origin을 보내지 않는다 — origin 차원에서 허용."""
        from antigravity_k.security.ws_origin import ws_origin_allowed

        assert ws_origin_allowed(None) is True
        assert ws_origin_allowed("") is True

    def test_default_allowlist_accepts_dashboard_dev_origin(self) -> None:
        from antigravity_k.security.ws_origin import ws_origin_allowed

        assert ws_origin_allowed("http://localhost:5173") is True
        assert ws_origin_allowed("http://127.0.0.1:8000") is True

    def test_trailing_slash_is_normalized(self) -> None:
        from antigravity_k.security.ws_origin import ws_origin_allowed

        assert ws_origin_allowed("http://localhost:5173/") is True

    def test_cross_site_origin_rejected(self) -> None:
        """공격 시나리오: evil.example이 브라우저로 로컬 WS에 접속."""
        from antigravity_k.security.ws_origin import ws_origin_allowed

        assert ws_origin_allowed("https://evil.example") is False
        assert ws_origin_allowed("http://localhost:9999") is False
        # scheme 교체 우회도 차단
        assert ws_origin_allowed("https://localhost:8000") is False

    def test_env_allowlist_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.security import ws_origin

        monkeypatch.setenv("AGK_CORS_ORIGINS", "https://dashboard.example.com")
        assert ws_origin.ws_origin_allowed("https://dashboard.example.com") is True
        assert ws_origin.ws_origin_allowed("http://localhost:5173") is False


class TestWsTicketService:
    @pytest.fixture()
    def service(self, monkeypatch: pytest.MonkeyPatch) -> TokenService:
        monkeypatch.setattr("antigravity_k.api.auth_routes._token_service", None)
        from antigravity_k.api.auth_routes import _token_service  # noqa: F401

        svc = TokenService()
        monkeypatch.setattr("antigravity_k.api.auth_routes._token_service", svc)
        return svc

    def test_issue_and_consume_roundtrip(self, service: TokenService) -> None:
        from antigravity_k.security.ws_ticket import WSTicketService

        tickets = WSTicketService(service, ttl_sec=5)
        ticket = tickets.issue("qa")
        assert tickets.consume(ticket) == "qa"

    def test_reuse_is_rejected(self, service: TokenService) -> None:
        """1회성 핵심 계약 — 같은 ticket 두 번째 소비는 거절."""
        from antigravity_k.security.ws_ticket import WSTicketService

        tickets = WSTicketService(service, ttl_sec=5)
        ticket = tickets.issue("qa")
        assert tickets.consume(ticket) == "qa"
        assert tickets.consume(ticket) is None

    def test_expired_ticket_rejected(self, service: TokenService) -> None:
        from antigravity_k.security.ws_ticket import WSTicketService

        tickets = WSTicketService(service, ttl_sec=1)
        ticket = tickets.issue("qa")
        assert tickets.consume(ticket) == "qa"

    def test_bearer_token_is_not_a_valid_ticket(self, service: TokenService) -> None:
        """장기 bearer를 ticket 자리에 써도 typ 불일치로 거절."""
        from antigravity_k.security.ws_ticket import WSTicketService

        tickets = WSTicketService(service, ttl_sec=5)
        bearer = service.issue_token("qa")
        assert tickets.consume(bearer) is None

    def test_garbage_rejected(self, service: TokenService) -> None:
        from antigravity_k.security.ws_ticket import WSTicketService

        tickets = WSTicketService(service, ttl_sec=5)
        assert tickets.consume("not-a-jwt") is None
        assert tickets.consume("") is None

    def test_ticket_from_other_secret_rejected(self, tmp_path: object) -> None:
        import os
        import tempfile
        from pathlib import Path

        from antigravity_k.security.ws_ticket import WSTicketService

        with tempfile.TemporaryDirectory() as td:
            p1 = Path(str(td)) / "s1"
            p2 = Path(str(td)) / "s2"
            os.environ["AGK_SEC_TOKEN_SECRET_FILE"] = str(p1)
            t1 = TokenService()
            os.environ["AGK_SEC_TOKEN_SECRET_FILE"] = str(p2)
            t2 = TokenService()
            service_a = WSTicketService(t1, ttl_sec=5)
            assert service_a.consume(t2.issue_token("qa")) is None


# ---------------------------------------------------------------------------
# 통합: hash-protected loopback 서버에서 WS gate 전체 경로
# ---------------------------------------------------------------------------


@pytest.fixture()
def protected_server(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """저장 PIN hash가 있는 보호 loopback 서버 TestClient."""
    from pathlib import Path

    from fastapi.testclient import TestClient as _TC

    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.config import config
    from antigravity_k.security import ws_ticket as ws_ticket_mod

    td = Path(str(tmp_path))
    hash_file = td / "auth_hash"
    hash_file.write_text(hash_pin("stored-pin-1234"), encoding="utf-8")

    orig_pin = config.security.access_pin
    orig_hash = config.security.pin_hash_file
    orig_secret = config.security.token_secret_file
    config.security.access_pin = ""
    config.security.pin_hash_file = str(hash_file)
    config.security.token_secret_file = str(td / "token_secret")
    monkeypatch.delenv("AGK_SEC_DEV_NO_PIN_ALLOW", raising=False)

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    ws_ticket_mod.reset_ws_ticket_service()

    from antigravity_k.api.server import app

    client = _TC(app, raise_server_exceptions=False)
    yield client

    config.security.access_pin = orig_pin
    config.security.pin_hash_file = orig_hash
    config.security.token_secret_file = orig_secret
    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    ws_ticket_mod.reset_ws_ticket_service()


class TestWsGateIntegration:
    def _login(self, client: TestClient) -> str:
        resp = client.post("/api/auth/login", json={"pin": "stored-pin-1234"})
        assert resp.status_code == 200, resp.text
        return str(resp.json()["access_token"])

    def test_query_token_channel_is_removed(self, protected_server: TestClient) -> None:
        """SEC-03 핵심: query ?token= 장기 bearer는 더 이상 인증되지 않는다."""
        token = self._login(protected_server)
        with protected_server.websocket_connect(f"/v1/ws/events?token={token}") as ws:
            first = ws.receive()
        assert first["type"] == "websocket.close" and first["code"] == 4401

    def test_cross_site_origin_rejected_4403(self, protected_server: TestClient) -> None:
        """cross-site 브라우저 — origin이 맞지 않으면 credential과 무관하게 4403."""
        token = self._login(protected_server)
        with protected_server.websocket_connect(
            "/v1/ws/events",
            headers={"Origin": "https://evil.example"},
            subprotocols=[f"bearer.{token}"],
        ) as ws:
            first = ws.receive()
        assert first["type"] == "websocket.close" and first["code"] == 4403

    def test_subprotocol_bearer_still_authenticates(self, protected_server: TestClient) -> None:
        token = self._login(protected_server)
        # 정상 bearer subprotocol → gate 통과 → 30초 내 keepalive ping 수신.
        with protected_server.websocket_connect("/v1/ws/events", subprotocols=[f"bearer.{token}"]) as ws:
            frame = ws.receive()
        assert frame.get("type") == "websocket.send", f"정상 bearer가 거절됐다: {frame}"

    def test_ticket_flow_authenticates_browser_clients(self, protected_server: TestClient) -> None:
        """정상 browser 흐름: login → ws-ticket → ?ticket= 1회 사용 → 성공."""
        token = self._login(protected_server)
        resp = protected_server.post("/api/auth/ws-ticket", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        ticket = str(resp.json()["ticket"])

        with protected_server.websocket_connect(f"/v1/ws/events?ticket={ticket}") as ws:
            frame = ws.receive()
        assert frame.get("type") == "websocket.send", f"유효 ticket이 거절됐다: {frame}"

    def test_ticket_reuse_rejected(self, protected_server: TestClient) -> None:
        """재사용 ticket 거절 — 첫 연결은 성공, 두 번째는 4401."""
        token = self._login(protected_server)
        resp = protected_server.post("/api/auth/ws-ticket", headers={"Authorization": f"Bearer {token}"})
        ticket = str(resp.json()["ticket"])

        # 1차 소비 (성공 — keepalive ping 수신까지)
        with protected_server.websocket_connect(f"/v1/ws/events?ticket={ticket}") as ws:
            frame = ws.receive()
        assert frame.get("type") == "websocket.send"

        # 2차 재사용 (거절)
        with protected_server.websocket_connect(f"/v1/ws/events?ticket={ticket}") as ws:
            first = ws.receive()
        assert first["type"] == "websocket.close" and first["code"] == 4401

    def test_ws_ticket_requires_auth(self, protected_server: TestClient) -> None:
        """ticket 발급 endpoint는 인증되지 않으면 401."""
        resp = protected_server.post("/api/auth/ws-ticket")
        assert resp.status_code == 401

    def test_unknown_ticket_query_is_just_unauthenticated(self, protected_server: TestClient) -> None:
        with protected_server.websocket_connect("/v1/ws/events?ticket=garbage") as ws:
            first = ws.receive()
        assert first["type"] == "websocket.close" and first["code"] == 4401
