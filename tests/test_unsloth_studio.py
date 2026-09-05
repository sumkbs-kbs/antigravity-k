from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, ListToolsResult, Tool
from pydantic import SecretStr, ValidationError

from antigravity_k.api.routes import unsloth_studio_api
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.provider_adapters.unsloth_studio import UnslothStudioService
from antigravity_k.engine.provider_adapters.unsloth_studio_contracts import (
    UNSLOTH_STUDIO_READ_TOOLS,
    UnslothStudioPermissionDenied,
    UnslothStudioSettings,
    UnslothStudioSnapshot,
    UnslothStudioToolResult,
    normalize_unsloth_mcp_url,
)
from antigravity_k.tools.base_tool import BaseTool, RiskLevel, ToolCategory
from antigravity_k.tools.mcp_session_manager import MCPSessionManager
from antigravity_k.tools.tool_contracts import Permission, PermissionDecision, ToolSpec
from antigravity_k.tools.tool_registry import ToolRegistry


class _CallRecord(Protocol):
    args: tuple[object, ...]
    kwargs: Mapping[str, object]


class _MockCall(Protocol):
    call_args: _CallRecord | None

    def assert_not_called(self) -> None:
        ...

    def assert_called_once(self) -> None:
        ...


class _AwaitMockCall(Protocol):
    await_args: _CallRecord
    await_args_list: Sequence[_CallRecord]

    def assert_not_called(self) -> None:
        ...

    def assert_awaited_once_with(self, *args: object, **kwargs: object) -> None:
        ...


class _ManagerMocks(Protocol):
    connect_streamable_http: _AwaitMockCall
    disconnect_server: _AwaitMockCall


class _RegistryMocks(Protocol):
    authorize_tool: _MockCall


class _AuthorizeMock(_MockCall, Protocol):
    return_value: PermissionDecision
    side_effect: Callable[[BaseTool, Mapping[str, object], str], PermissionDecision] | None


class _AuditMocks(Protocol):
    log_event: _MockCall


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


def _settings(token: str | None = "studio-secret") -> UnslothStudioSettings:
    return UnslothStudioSettings(
        endpoint="http://127.0.0.1:8888/mcp",
        token=SecretStr(token) if token is not None else None,
    )


def _tool(name: str) -> Tool:
    return Tool(name=name, description=name, inputSchema={"type": "object"})


def _allow_decision(tool_name: str) -> PermissionDecision:
    return PermissionDecision(
        spec=ToolSpec(name=tool_name, risk_level="safe"),
        permission=Permission.ALLOW,
        source="permission_gate",
        reason="Read-only tool allowed.",
    )


def test_normalize_unsloth_mcp_url_accepts_only_loopback_mcp_endpoint() -> None:
    assert normalize_unsloth_mcp_url("http://localhost:8888/mcp") == "http://localhost:8888/mcp/"
    assert normalize_unsloth_mcp_url("http://[::1]:8888/mcp/") == "http://[::1]:8888/mcp/"

    with pytest.raises(ValueError, match="loopback"):
        _ = normalize_unsloth_mcp_url("http://studio.example.com/mcp/")
    with pytest.raises(ValueError, match="credentials"):
        _ = normalize_unsloth_mcp_url("http://user:pass@127.0.0.1:8888/mcp/")
    with pytest.raises(ValueError, match="/mcp/"):
        _ = normalize_unsloth_mcp_url("http://127.0.0.1:8888/v1/")


def test_settings_reject_blank_token() -> None:
    with pytest.raises(ValidationError, match="token"):
        _ = UnslothStudioSettings(endpoint="http://127.0.0.1:8888/mcp/", token=SecretStr("   "))


@pytest.mark.asyncio
async def test_snapshot_is_optional_without_token_and_skips_connection() -> None:
    manager = MagicMock(spec=MCPSessionManager)
    registry = MagicMock(spec=ToolRegistry)
    service = UnslothStudioService(settings=_settings(token=None), manager=manager, registry=registry)

    snapshot = await service.snapshot()

    assert snapshot.configured is False
    assert snapshot.available is False
    assert snapshot.allowed_tools == UNSLOTH_STUDIO_READ_TOOLS
    cast(_ManagerMocks, manager).connect_streamable_http.assert_not_called()
    cast(_RegistryMocks, registry).authorize_tool.assert_not_called()


@pytest.mark.asyncio
async def test_snapshot_calls_only_allowlisted_read_tools_with_bearer_token() -> None:
    advertised_tools = [
        *[_tool(tool.value) for tool in UNSLOTH_STUDIO_READ_TOOLS],
        _tool("start_training"),
        _tool("stop_training"),
        _tool("export_gguf"),
    ]
    session = MagicMock(spec=ClientSession)
    session.list_tools = AsyncMock(return_value=ListToolsResult(tools=advertised_tools))
    session.call_tool = AsyncMock(
        side_effect=[
            CallToolResult(content=[], structuredContent={"tool": tool.value}, isError=False)
            for tool in UNSLOTH_STUDIO_READ_TOOLS
        ],
    )
    manager = MagicMock(spec=MCPSessionManager)
    manager.connect_streamable_http = AsyncMock(return_value=session)
    manager.disconnect_server = AsyncMock()
    registry = MagicMock(spec=ToolRegistry)
    authorize_mock = cast(_AuthorizeMock, registry.authorize_tool)
    authorize_mock.side_effect = lambda tool, args, objective="": _allow_decision(tool.name)
    service = UnslothStudioService(settings=_settings(), manager=manager, registry=registry)

    snapshot = await service.snapshot()

    assert snapshot.configured is True
    assert snapshot.available is True
    assert tuple(result.tool for result in snapshot.results) == UNSLOTH_STUDIO_READ_TOOLS
    assert all(result.ok for result in snapshot.results)
    call_tool_mock = cast(_AwaitMockCall, session.call_tool)
    assert [call.args[0] for call in call_tool_mock.await_args_list] == [
        tool.value for tool in UNSLOTH_STUDIO_READ_TOOLS
    ]
    connect_mock = cast(_AwaitMockCall, manager.connect_streamable_http)
    assert connect_mock.await_args.kwargs["headers"] == {
        "Authorization": "Bearer studio-secret",
    }
    cast(_ManagerMocks, manager).disconnect_server.assert_awaited_once_with("unsloth-studio")


@pytest.mark.asyncio
async def test_permission_denial_prevents_mcp_connection() -> None:
    manager = MagicMock(spec=MCPSessionManager)
    registry = MagicMock(spec=ToolRegistry)
    authorize_mock = cast(_AuthorizeMock, registry.authorize_tool)
    authorize_mock.return_value = PermissionDecision(
        spec=ToolSpec(name="studio_status", risk_level=RiskLevel.SAFE.value, category=ToolCategory.DATA.value),
        permission=Permission.DENY,
        source="permission_gate",
        reason="Policy denied the read.",
    )
    service = UnslothStudioService(settings=_settings(), manager=manager, registry=registry)

    with pytest.raises(UnslothStudioPermissionDenied, match="studio_status"):
        _ = await service.snapshot()

    cast(_ManagerMocks, manager).connect_streamable_http.assert_not_called()


def test_api_exposes_snapshot_without_secret_and_records_audit() -> None:
    service = MagicMock(spec=UnslothStudioService)
    service.snapshot = AsyncMock(
        return_value=UnslothStudioSnapshot(
            configured=True,
            available=True,
            endpoint="http://127.0.0.1:8888/mcp/",
            allowed_tools=UNSLOTH_STUDIO_READ_TOOLS,
            available_tools=UNSLOTH_STUDIO_READ_TOOLS,
            results=tuple(
                UnslothStudioToolResult(tool=tool, ok=True, data={"state": "idle"}, error=None)
                for tool in UNSLOTH_STUDIO_READ_TOOLS
            ),
            error=None,
        ),
    )
    audit = MagicMock()
    app.dependency_overrides[unsloth_studio_api.get_unsloth_studio_service] = lambda: service

    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(unsloth_studio_api, "get_audit_logger", lambda: audit)
            with TestClient(app) as client:
                response = client.get("/v1/integrations/unsloth/studio", headers=_auth_headers())
    finally:
        _ = app.dependency_overrides.pop(unsloth_studio_api.get_unsloth_studio_service, None)

    assert response.status_code == 200
    payload = cast(Mapping[str, object], response.json())
    assert payload["available"] is True
    assert "studio-secret" not in response.text
    log_event_mock = cast(_AuditMocks, audit).log_event
    log_event_mock.assert_called_once()
    call_args = log_event_mock.call_args
    assert call_args is not None
    assert isinstance(call_args.args[1], Mapping)
    assert "token" not in call_args.args[1]
