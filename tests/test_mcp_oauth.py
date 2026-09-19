"""Tests for MCP OAuth 2.1 interactive flow (PKCE + token vault)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.engine import mcp_oauth as oauth
from antigravity_k.engine.mcp_oauth import (
    MCPOAuthError,
    OAuthTokenSet,
    PendingAuth,
    PendingAuthStore,
    canonical_resource_uri,
    complete_authorization,
    generate_pkce_pair,
    get_authorization_header,
    merge_oauth_headers,
    parse_www_authenticate,
    start_authorization,
)


@pytest.fixture(autouse=True)
def _isolate_oauth(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate encrypted token vault — secure_key binds paths at import time."""
    import antigravity_k.engine.secure_key as sk

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sk, "_VAULT_KEY_DIR", vault_dir)
    monkeypatch.setattr(sk, "_MASTER_KEY_FILE", vault_dir / "master.key")
    monkeypatch.setattr(sk, "_VAULT_DB", vault_dir / "keys.enc")
    monkeypatch.setenv("AGK_VAULT_DIR", str(vault_dir))
    oauth.pending_auth_store.clear()
    yield
    oauth.pending_auth_store.clear()


class TestPkceAndParsing:
    def test_generate_pkce_pair_s256(self) -> None:
        verifier, challenge = generate_pkce_pair()
        assert len(verifier) >= 43
        assert challenge
        assert "=" not in challenge
        # Recompute challenge
        import base64
        import hashlib

        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert challenge == expected

    def test_canonical_resource_uri(self) -> None:
        assert canonical_resource_uri("https://MCP.Example.com/mcp/") == "https://mcp.example.com/mcp"
        with pytest.raises(MCPOAuthError):
            canonical_resource_uri("not-a-url")

    def test_parse_www_authenticate(self) -> None:
        header = (
            'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource", '
            'scope="files:read"'
        )
        params = parse_www_authenticate(header)
        assert params["resource_metadata"] == "https://mcp.example.com/.well-known/oauth-protected-resource"
        assert params["scope"] == "files:read"


class TestTokenVault:
    def test_save_load_delete_tokens(self) -> None:
        tokens = OAuthTokenSet(
            access_token="access-xyz",
            refresh_token="refresh-xyz",
            expires_at=time.time() + 3600,
            resource="https://mcp.example.com/mcp",
            client_id="client-1",
            token_endpoint="https://auth.example.com/token",
        )
        assert oauth.save_token_set("remote", tokens)
        loaded = oauth.load_token_set("remote")
        assert loaded is not None
        assert loaded.access_token == "access-xyz"
        assert loaded.refresh_token == "refresh-xyz"
        assert oauth.has_stored_tokens("remote")
        assert oauth.delete_token_set("remote")
        assert oauth.load_token_set("remote") is None

    def test_merge_oauth_headers_prefers_existing(self) -> None:
        tokens = OAuthTokenSet(access_token="tok", token_type="Bearer")
        oauth.save_token_set("srv", tokens)
        merged = merge_oauth_headers("srv", {"Authorization": "Bearer manual"})
        assert merged["Authorization"] == "Bearer manual"
        merged2 = merge_oauth_headers("srv", {})
        assert merged2["Authorization"] == "Bearer tok"

    def test_get_authorization_header_refreshes_expired(self) -> None:
        tokens = OAuthTokenSet(
            access_token="old",
            refresh_token="rt",
            expires_at=time.time() - 10,
            client_id="cid",
            token_endpoint="https://auth.example.com/token",
            resource="https://mcp.example.com/mcp",
        )
        oauth.save_token_set("srv", tokens)

        def fake_post(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "access_token": "new-access",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "rt2",
            }
            return resp

        with patch.object(oauth, "_default_http_post_form", fake_post):
            # refresh_tokens uses http_post_form param; get_authorization_header calls refresh_tokens
            # which defaults to _default_http_post_form — patch that.
            header = get_authorization_header("srv")
        assert header == "Bearer new-access"
        assert oauth.load_token_set("srv") is not None
        assert oauth.load_token_set("srv").access_token == "new-access"  # type: ignore[union-attr]


def _mock_discovery_http(url: str, headers: dict[str, str] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    if "oauth-protected-resource" in url:
        resp.json.return_value = {
            "resource": "https://mcp.example.com/mcp",
            "authorization_servers": ["https://auth.example.com"],
            "scopes_supported": ["mcp:tools"],
        }
    elif "oauth-authorization-server" in url or "openid-configuration" in url:
        resp.json.return_value = {
            "issuer": "https://auth.example.com",
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "code_challenge_methods_supported": ["S256"],
            "registration_endpoint": "https://auth.example.com/register",
        }
    else:
        resp.status_code = 404
        resp.json.return_value = {}
    return resp


class TestInteractiveFlow:
    def test_start_and_complete_with_preregistered_client(self) -> None:
        store = PendingAuthStore()
        server_config = {
            "url": "https://mcp.example.com/mcp",
            "auth": {"type": "oauth", "client_id": "ssak-ai-client"},
        }

        start = start_authorization(
            "remote-mcp",
            server_config,
            redirect_uri="http://127.0.0.1:8400/api/mcp/oauth/callback",
            http_get=_mock_discovery_http,
            store=store,
        )
        assert start["ok"] is True
        assert "code_challenge" in start["authorization_url"]
        assert "resource=" in start["authorization_url"]
        assert start["state"]
        state = start["state"]

        def fake_token_post(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> MagicMock:
            assert data["grant_type"] == "authorization_code"
            assert data["code"] == "auth-code-1"
            assert data["code_verifier"]
            assert data["resource"] == "https://mcp.example.com/mcp"
            assert data["client_id"] == "ssak-ai-client"
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "token_type": "Bearer",
                "expires_in": 1200,
                "scope": "mcp:tools",
            }
            return resp

        result = complete_authorization(
            code="auth-code-1",
            state=state,
            http_post_form=fake_token_post,
            store=store,
        )
        assert result["ok"] is True
        assert result["server_name"] == "remote-mcp"
        assert oauth.has_stored_tokens("remote-mcp")
        header = get_authorization_header("remote-mcp")
        assert header == "Bearer access-1"

    def test_start_rejects_missing_pkce(self) -> None:
        def no_pkce(url: str, headers: dict[str, str] | None = None) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            if "oauth-protected-resource" in url:
                resp.json.return_value = {
                    "authorization_servers": ["https://auth.example.com"],
                }
            else:
                resp.json.return_value = {
                    "authorization_endpoint": "https://auth.example.com/authorize",
                    "token_endpoint": "https://auth.example.com/token",
                    # missing code_challenge_methods_supported
                }
            return resp

        with pytest.raises(MCPOAuthError, match="PKCE"):
            start_authorization(
                "x",
                {"url": "https://mcp.example.com/mcp", "auth": {"client_id": "c"}},
                redirect_uri="http://127.0.0.1:8400/api/mcp/oauth/callback",
                http_get=no_pkce,
            )

    def test_complete_rejects_unknown_state(self) -> None:
        with pytest.raises(MCPOAuthError, match="Unknown or expired"):
            complete_authorization(code="c", state="nope", store=PendingAuthStore())


class TestAPIEndpoints:
    def test_status_and_revoke_roundtrip(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / ".mcp.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "remote": {
                            "url": "https://mcp.example.com/mcp",
                            "auth": {"type": "oauth", "client_id": "c1"},
                        },
                        "local": {"command": "npx", "args": ["-y", "x"]},
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("AGK_MCP_CONFIG", str(cfg))
        oauth.save_token_set(
            "remote",
            OAuthTokenSet(access_token="a", resource="https://mcp.example.com/mcp"),
        )

        client = TestClient(app)
        status = client.get("/api/mcp/oauth/status")
        assert status.status_code == 200
        body = status.json()
        assert body["ok"] is True
        by_name = {s["name"]: s for s in body["servers"]}
        assert by_name["remote"]["supports_oauth"] is True
        assert by_name["remote"]["connected"] is True
        assert by_name["local"]["supports_oauth"] is False

        revoked = client.post("/api/mcp/oauth/revoke", json={"server_name": "remote"})
        assert revoked.status_code == 200
        assert revoked.json()["connected"] is False
        assert not oauth.has_stored_tokens("remote")

    def test_start_complete_api_mocked(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / ".mcp.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "remote": {
                            "url": "https://mcp.example.com/mcp",
                            "auth": {"type": "oauth", "client_id": "c1"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("AGK_MCP_CONFIG", str(cfg))

        client = TestClient(app)
        with (
            patch("antigravity_k.engine.mcp_oauth.discover_protected_resource_metadata") as prm,
            patch("antigravity_k.engine.mcp_oauth.discover_authorization_server_metadata") as asm,
        ):
            prm.return_value = {
                "authorization_servers": ["https://auth.example.com"],
                "scopes_supported": ["mcp:tools"],
            }
            asm.return_value = {
                "authorization_endpoint": "https://auth.example.com/authorize",
                "token_endpoint": "https://auth.example.com/token",
                "code_challenge_methods_supported": ["S256"],
            }
            started = client.post(
                "/api/mcp/oauth/start",
                json={"server_name": "remote", "redirect_uri": "http://127.0.0.1:8400/api/mcp/oauth/callback"},
            )
        assert started.status_code == 200
        data = started.json()
        assert data["ok"] is True
        state = data["state"]

        def fake_post(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "access_token": "api-access",
                "token_type": "Bearer",
                "expires_in": 600,
            }
            return resp

        with patch("antigravity_k.engine.mcp_oauth._default_http_post_form", fake_post):
            completed = client.post("/api/mcp/oauth/complete", json={"code": "abc", "state": state})
        assert completed.status_code == 200
        assert completed.json()["connected"] is True
        assert oauth.has_stored_tokens("remote")

        # Browser callback path returns HTML
        oauth.pending_auth_store.put(
            PendingAuth(
                state="cb-state",
                server_name="remote",
                resource="https://mcp.example.com/mcp",
                redirect_uri="http://127.0.0.1:8400/api/mcp/oauth/callback",
                client_id="c1",
                code_verifier="verifier",
                authorization_endpoint="https://auth.example.com/authorize",
                token_endpoint="https://auth.example.com/token",
                authorization_server="https://auth.example.com",
            )
        )
        with patch("antigravity_k.engine.mcp_oauth._default_http_post_form", fake_post):
            cb = client.get("/api/mcp/oauth/callback", params={"code": "z", "state": "cb-state"})
        assert cb.status_code == 200
        assert "MCP OAuth" in cb.text
