"""Network access-info endpoint (personal mobile / LAN hints)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from antigravity_k.api.server import app


def test_network_access_info_shape() -> None:
    client = TestClient(app)
    resp = client.get("/api/network/access-info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mobile_bind_default"] is False
    assert isinstance(data["bind_host"], str)
    assert isinstance(data["port"], int)
    assert isinstance(data["is_loopback"], bool)
    assert isinstance(data["lan_ipv4"], list)
    assert isinstance(data["suggested_mobile_urls"], list)
    assert "agk serve --host" in data["restart_command_lan"]
    assert data["notes"]
