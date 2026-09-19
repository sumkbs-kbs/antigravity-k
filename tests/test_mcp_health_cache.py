"""Tests for MCP server health cache + /api/mcp/health endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.engine.mcp_health_cache import (
    MCPHealthCache,
    load_configured_mcp_servers,
    mcp_health_cache,
    probe_configured_servers,
)


@pytest.fixture(autouse=True)
def _clear_health_cache() -> Iterator[None]:
    mcp_health_cache.clear()
    yield
    mcp_health_cache.clear()


class TestMCPHealthCache:
    def test_record_success_and_snapshot(self) -> None:
        cache = MCPHealthCache()
        cache.record_success(
            "fs",
            transport="stdio",
            tools=["read_file", "write_file"],
            latency_ms=12.5,
            source="test",
            command="npx",
        )
        rows = cache.snapshot()
        assert len(rows) == 1
        assert rows[0]["name"] == "fs"
        assert rows[0]["status"] == "healthy"
        assert rows[0]["tool_count"] == 2
        assert rows[0]["initialized"] is True
        assert rows[0]["latency_ms"] == 12.5

    def test_record_failure_and_blocked(self) -> None:
        cache = MCPHealthCache()
        cache.record_failure("bad", "boom", transport="http")
        cache.record_blocked("blocked", "no auth", transport="http")
        by_name = {row["name"]: row for row in cache.snapshot()}
        assert by_name["bad"]["status"] == "error"
        assert by_name["bad"]["error"] == "boom"
        assert by_name["blocked"]["status"] == "blocked"

    def test_merge_with_configured_prefers_cache(self) -> None:
        cache = MCPHealthCache()
        cache.record_success("a", tools=["t1"])
        merged = cache.merge_with_configured(
            [
                {"name": "a", "transport": "stdio", "command": "cmd-a", "source": "cfg"},
                {"name": "b", "transport": "stdio", "command": "cmd-b", "source": "cfg"},
            ]
        )
        by_name = {row["name"]: row for row in merged}
        assert by_name["a"]["status"] == "healthy"
        assert by_name["a"]["tool_count"] == 1
        assert by_name["b"]["status"] == "configured"
        assert by_name["b"]["command"] == "cmd-b"

    def test_summary_counts(self) -> None:
        cache = MCPHealthCache()
        cache.record_success("ok")
        cache.record_failure("err", "x")
        summary = cache.summary()
        assert summary["total"] == 2
        assert summary["healthy"] == 1
        assert summary["error"] == 1


def test_load_configured_mcp_servers_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local-fs": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                    },
                    "remote": {
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer x"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGK_MCP_CONFIG", str(cfg))
    servers, source = load_configured_mcp_servers()
    assert source == str(cfg)
    names = {s["name"] for s in servers}
    assert names == {"local-fs", "remote"}
    by_name = {s["name"]: s for s in servers}
    assert by_name["local-fs"]["transport"] == "stdio"
    assert by_name["remote"]["transport"] == "http"


@pytest.mark.asyncio
async def test_probe_records_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"demo": {"command": "echo", "args": []}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGK_MCP_CONFIG", str(cfg))

    mock_session = MagicMock()
    tool = MagicMock()
    tool.name = "ping"
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[tool]))

    class _FakeManager:
        async def connect_server(self, *args: object, **kwargs: object) -> MagicMock:
            return mock_session

        async def cleanup(self) -> None:
            return None

    with (
        patch(
            "antigravity_k.tools.mcp_session_manager.MCPSessionManager",
            _FakeManager,
        ),
        patch(
            "antigravity_k.engine.mcp_capability.MCPCapabilityAdvisor.audit_config",
            return_value=MagicMock(findings=[]),
        ),
    ):
        rows = await probe_configured_servers(cache=mcp_health_cache)

    assert len(rows) == 1
    assert rows[0]["status"] == "healthy"
    assert rows[0]["tools"] == ["ping"]
    assert mcp_health_cache.get("demo") is not None


def test_api_mcp_health_get(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"alpha": {"command": "npx", "args": ["x"]}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGK_MCP_CONFIG", str(cfg))
    mcp_health_cache.record_success("alpha", tools=["t"], latency_ms=3.0)

    client = TestClient(app)
    response = client.get("/api/mcp/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["summary"]["healthy"] >= 1
    assert any(s["name"] == "alpha" and s["status"] == "healthy" for s in data["servers"])


def test_api_mcp_health_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"beta": {"command": "npx", "args": []}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGK_MCP_CONFIG", str(cfg))

    async def _fake_probe(**_kwargs: Any) -> list[dict[str, object]]:
        mcp_health_cache.record_success("beta", tools=["z"])
        return mcp_health_cache.snapshot()

    with patch(
        "antigravity_k.engine.mcp_health_cache.probe_configured_servers",
        new=_fake_probe,
    ):
        client = TestClient(app)
        response = client.post("/api/mcp/health/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert any(s["name"] == "beta" and s["status"] == "healthy" for s in data["servers"])
