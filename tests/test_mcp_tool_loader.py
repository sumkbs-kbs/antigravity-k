"""Tests for MCP Tool Loader (mcp_tool_loader.py)."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from typing import cast
from unittest import mock

import pytest
from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
    TextResourceContents,
)

import antigravity_k.tools.mcp_tool_loader as _loader
from antigravity_k.engine.tool_executor import result_indicates_failure
from antigravity_k.engine.tool_policy import (
    ToolPolicy,
    reset_tool_policy,
    set_tool_policy,
)
from antigravity_k.tools.base_tool import RiskLevel
from antigravity_k.tools.mcp_tool_loader import (
    MCPServerRegistry,
    MCPTool,
)
from antigravity_k.tools.mcp_tool_result import MCPToolOutcome


def _annotations_to_dict(value: object) -> dict[str, object]:
    function = cast(Callable[..., object], getattr(_loader, "_annotations_to_dict"))
    return cast(dict[str, object], function(value))


def _risk_from_annotations(value: object) -> RiskLevel:
    function = cast(Callable[..., object], getattr(_loader, "_risk_from_annotations"))
    return cast(RiskLevel, function(value))


def _server_policy(value: object) -> dict[str, object]:
    function = cast(Callable[..., object], getattr(_loader, "_server_policy"))
    return cast(dict[str, object], function(value))


def _string_dict(value: object) -> dict[str, str]:
    function = cast(Callable[..., object], getattr(_loader, "_string_dict"))
    return cast(dict[str, str], function(value))


def _timeout_seconds(value: object, *, default: float, keys: tuple[str, str] | None = None) -> float:
    function = cast(Callable[..., object], getattr(_loader, "_timeout_seconds"))
    if keys is None:
        return cast(float, function(value, default=default))
    return cast(float, function(value, default=default, keys=keys))


def _transport_for(value: object) -> str:
    function = cast(Callable[..., object], getattr(_loader, "_transport_for"))
    return cast(str, function(value))


def _skill_servers() -> dict[str, dict[str, object]]:
    return cast(dict[str, dict[str, object]], getattr(MCPServerRegistry, "_skill_servers"))


def _schema_problem(value: object) -> str | None:
    function = cast(Callable[..., object], getattr(_loader, "_schema_problem"))
    return cast(str | None, function(value))


class _ModelDumpAnnotation:
    def model_dump(self, *, exclude_none: bool) -> dict[str, object]:
        return {"readOnlyHint": True} if exclude_none else {}


class _DictAnnotation:
    def dict(self, *, exclude_none: bool) -> dict[str, object]:
        del exclude_none
        return {"destructiveHint": True}


class _WarningLogger:
    def __init__(self) -> None:
        self.warning_calls: list[tuple[object, ...]] = []

    def warning(self, *args: object, **kwargs: object) -> None:
        del kwargs
        self.warning_calls.append(args)

    def info(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


# ─── Helper functions (pure) ─────────────────────────────────────────


class TestTransportFor:
    """_transport_for determines MCP transport type from config."""

    def test_stdio_when_command_present(self):
        assert _transport_for({"command": "npx"}) == "stdio"

    def test_http_when_url_present(self):
        assert _transport_for({"url": "http://localhost:8080"}) == "http"

    def test_endpoint_also_http(self):
        assert _transport_for({"endpoint": "http://localhost"}) == "http"

    def test_explicit_transport_http(self):
        assert _transport_for({"transport": "http"}) == "http"

    def test_explicit_transport_sse(self):
        assert _transport_for({"transport": "sse"}) == "sse"

    def test_streamable_http_normalized(self):
        result = _transport_for({"transport": "streamable_http"})
        assert result == "streamable-http"

    def test_streamable_http_dash(self):
        result = _transport_for({"transport": "streamable-http"})
        assert result == "streamable-http"

    def test_type_alias(self):
        assert _transport_for({"type": "sse"}) == "sse"

    def test_unknown_returns_unknown(self):
        assert _transport_for({}) == "unknown"


class TestAnnotationsToDict:
    """_annotations_to_dict normalizes annotation objects to dict."""

    def test_none_returns_empty(self):
        assert _annotations_to_dict(None) == {}

    def test_pydantic_model_dump(self):
        mock_model = _ModelDumpAnnotation()
        result = _annotations_to_dict(mock_model)
        assert result == {"readOnlyHint": True}

    def test_dict_method(self):
        mock_obj = _DictAnnotation()
        result = _annotations_to_dict(mock_obj)
        assert result == {"destructiveHint": True}

    def test_mapping_input(self):
        result = _annotations_to_dict({"key": "value"})
        assert result == {"key": "value"}

    def test_other_returns_empty(self):
        result = _annotations_to_dict(42)
        assert result == {}


class TestRiskFromAnnotations:
    """_risk_from_annotations maps annotation hints to RiskLevel."""

    def test_destructive_is_high(self):
        assert _risk_from_annotations({"destructiveHint": True}) == RiskLevel.HIGH

    def test_open_world_is_medium(self):
        assert _risk_from_annotations({"openWorldHint": True}) == RiskLevel.MEDIUM

    def test_read_only_is_safe(self):
        assert _risk_from_annotations({"readOnlyHint": True}) == RiskLevel.SAFE

    def test_default_is_medium(self):
        assert _risk_from_annotations({}) == RiskLevel.MEDIUM


class TestTimeoutSeconds:
    """_timeout_seconds extracts timeout from config with fallback."""

    def test_primary_key(self):
        assert _timeout_seconds({"timeout": 60}, default=30) == 60.0

    def test_millis_key(self):
        assert _timeout_seconds({"timeout_ms": 5000}, default=30) == 5.0

    def test_default_when_missing(self):
        assert _timeout_seconds({}, default=30) == 30.0

    def test_custom_keys(self):
        result = _timeout_seconds(
            {"sse_read_timeout": 120},
            default=30,
            keys=("sse_read_timeout", "sse_read_timeout_ms"),
        )
        assert result == 120.0

    def test_custom_millis_keys(self):
        result = _timeout_seconds(
            {"sse_read_timeout_ms": 300000},
            default=30,
            keys=("sse_read_timeout", "sse_read_timeout_ms"),
        )
        assert result == 300.0


class TestStringDict:
    """_string_dict converts raw values to dict[str, str]."""

    def test_mapping_converts_keys_and_values(self):
        result = _string_dict({"key": 123, "nested": None})
        assert result == {"key": "123", "nested": "None"}

    def test_none_returns_empty(self):
        assert _string_dict(None) == {}

    def test_non_mapping_returns_empty(self):
        assert _string_dict("not a dict") == {}


class TestServerPolicy:
    """_server_policy extracts policy dict from server config."""

    def test_default_trust_level(self):
        policy = _server_policy({})
        assert policy["trust_level"] == "experimental"
        assert policy["authenticated"] is False

    def test_custom_trust_level(self):
        policy = _server_policy({"trust_level": "full"})
        assert policy["trust_level"] == "full"

    def test_auth_flag(self):
        policy = _server_policy({"auth": "bearer"})
        assert policy["authenticated"] is True

    def test_auth_profile_flag(self):
        policy = _server_policy({"auth_profile": "github"})
        assert policy["authenticated"] is True

    def test_authorization_header(self):
        policy = _server_policy({"headers": {"Authorization": "Bearer xyz"}})
        assert policy["authenticated"] is True

    def test_timeout_extracted(self):
        policy = _server_policy({"timeout": 30})
        assert policy["timeout_ms"] == 30

    def test_timeout_ms_preferred(self):
        policy = _server_policy({"timeout_ms": 15000, "timeout": 30})
        assert policy["timeout_ms"] == 15000


# ─── MCPServerRegistry ──────────────────────────────────────────────


class TestMCPServerRegistryBase:
    """Core catalog access."""

    def test_get_all_returns_catalog(self):
        registry = MCPServerRegistry()
        all_servers = registry.get_all()
        assert "filesystem" in all_servers
        assert "github" in all_servers
        assert len(all_servers) >= 9

    def test_get_by_category_returns_filtered(self):
        registry = MCPServerRegistry()
        search = registry.get_by_category("search")
        assert "brave-search" in search
        assert "filesystem" not in search

    def test_get_recommended_returns_list(self):
        registry = MCPServerRegistry()
        recommended = registry.get_recommended()
        assert "filesystem" in recommended
        assert "fetch" in recommended
        assert isinstance(recommended, list)


class TestMCPServerRegistrySkillIntegration:
    """Skill MCP server registration (Phase 1 D11)."""

    def setup_method(self):
        """Ensure clean _skill_servers state before each test."""
        _skill_servers().clear()

    def teardown_method(self):
        """Clean up _skill_servers after each test."""
        _skill_servers().clear()

    def test_register_skill_mcp(self):
        registry = MCPServerRegistry()
        mcp_config = {
            "serverId": "my-skill-server",
            "command": "python",
            "args": ["-m", "my_skill"],
        }
        result = registry.register_skill_mcp("my-skill", mcp_config)
        assert result is True
        assert "my-skill-server" in _skill_servers()

    def test_get_skill_mcp_servers_returns_registered(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("test-skill", {"serverId": "ts1", "command": "echo"})
        servers = registry.get_skill_mcp_servers()
        assert "ts1" in servers
        assert servers["ts1"]["skill_name"] == "test-skill"

    def test_get_skill_mcp_servers_filtered_by_name(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("skill-a", {"serverId": "sa1", "command": "echo"})
        _ = registry.register_skill_mcp("skill-b", {"serverId": "sb1", "command": "echo"})
        filtered = registry.get_skill_mcp_servers("skill-a")
        assert "sa1" in filtered
        assert "sb1" not in filtered

    def test_unregister_skill_mcp_removes_servers(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("my-skill", {"serverId": "ms1", "command": "echo"})
        _ = registry.register_skill_mcp("my-skill", {"serverId": "ms2", "command": "echo"})
        result = registry.unregister_skill_mcp("my-skill")
        assert result is True
        assert registry.get_skill_mcp_servers("my-skill") == {}

    def test_unregister_nonexistent_skill(self):
        registry = MCPServerRegistry()
        result = registry.unregister_skill_mcp("nonexistent")
        assert result is False

    def test_register_duplicate_server_id_skips(self):
        registry = MCPServerRegistry()
        result = registry.register_skill_mcp("skill", {"serverId": "filesystem", "command": "echo"})
        assert result is False  # Already in CATALOG

    def test_list_skills_with_mcp(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("skill-a", {"serverId": "sa1", "command": "echo"})
        _ = registry.register_skill_mcp("skill-b", {"serverId": "sb1", "command": "echo"})
        skills = registry.list_skills_with_mcp()
        skill_names = [s["skill"] for s in skills]
        assert "skill-a" in skill_names
        assert "skill-b" in skill_names

    def test_get_all_includes_skill_servers(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("s1", {"serverId": "custom-srv", "command": "echo"})
        all_servers = registry.get_all()
        assert "custom-srv" in all_servers

    def test_get_by_category_includes_skill_servers(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("s1", {"serverId": "custom-srv", "command": "echo"})
        # register_skill_mcp always sets category="skill"
        skill_servers = registry.get_by_category("skill")
        assert "custom-srv" in skill_servers

    def test_skill_server_isolation_between_instances(self):
        # _skill_servers is a class variable shared across instances
        registry1 = MCPServerRegistry()
        registry2 = MCPServerRegistry()
        _ = registry1.register_skill_mcp("skill", {"serverId": "shared-srv", "command": "echo"})
        assert "shared-srv" in _skill_servers()
        assert registry2.get_skill_mcp_servers("skill")["shared-srv"]["skill_name"] == "skill"
        # Clean up
        _skill_servers().clear()

    def test_catalog_summary_includes_skills(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("skill-x", {"serverId": "sx1", "command": "echo"})
        summary = registry.get_catalog_summary()
        assert "sx1" in summary
        assert "skill: skill-x" in summary
        _skill_servers().clear()


class TestMCPServerRegistryGenerateConfig:
    """Config file generation."""

    def test_generate_config_creates_file(self):
        registry = MCPServerRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = registry.generate_config(tmp_path, server_ids=["filesystem", "fetch"])
            assert result == tmp_path
            assert os.path.exists(tmp_path)
            with open(tmp_path, encoding="utf-8") as f:
                data = cast(dict[str, object], json.load(f))
            servers = cast(dict[str, object], data["mcpServers"])
            assert "mcpServers" in data
            assert "filesystem" in servers
            assert "fetch" in servers
        finally:
            os.unlink(tmp_path)

    def test_generate_config_defaults_to_recommended(self):
        registry = MCPServerRegistry()
        with mock.patch.object(registry, "get_recommended", return_value=["filesystem"]):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                _ = registry.generate_config(tmp_path)
                with open(tmp_path, encoding="utf-8") as f:
                    data = cast(dict[str, object], json.load(f))
                servers = cast(dict[str, object], data["mcpServers"])
                assert "filesystem" in servers
            finally:
                os.unlink(tmp_path)

    def test_generate_config_unknown_server_warns(self):
        registry = MCPServerRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            logger_double = _WarningLogger()
            with mock.patch("antigravity_k.tools.mcp_tool_loader.logger", new=logger_double):
                _ = registry.generate_config(tmp_path, server_ids=["nonexistent"])
                assert len(logger_double.warning_calls) == 1
        finally:
            os.unlink(tmp_path)

    def test_generate_config_with_skills(self):
        registry = MCPServerRegistry()
        _ = registry.register_skill_mcp("skill-z", {"serverId": "zs1", "command": "echo"})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _ = registry.generate_config_with_skills(tmp_path)
            with open(tmp_path, encoding="utf-8") as f:
                data = cast(dict[str, object], json.load(f))
            servers = cast(dict[str, object], data["mcpServers"])
            assert "zs1" in servers
        finally:
            os.unlink(tmp_path)
            _skill_servers().clear()


# ─── MCPTool ────────────────────────────────────────────────────────


class TestMCPTool:
    """MCPTool properties and metadata."""

    def test_properties(self):
        tool = MCPTool(
            name="test-tool",
            description="A test tool",
            schema={"type": "object"},
            mcp_client=mock.MagicMock(),
            server_name="test-server",
            transport="stdio",
            annotations={"readOnlyHint": True},
            server_policy={"trust_level": "full", "authenticated": True},
        )
        assert tool.name == "test-tool"
        assert tool.description == "A test tool"
        assert tool.parameters_schema == {"type": "object"}
        assert tool.risk_level == RiskLevel.SAFE

    def test_to_metadata_includes_mcp_info(self):
        tool = MCPTool(
            name="meta-tool",
            description="",
            schema={},
            mcp_client=mock.MagicMock(),
            server_name="server-x",
            transport="sse",
            annotations={"readOnlyHint": True},
            server_policy={"trust_level": "full", "authenticated": True, "timeout_ms": 5000},
        )
        metadata = tool.to_metadata()
        mcp_metadata = cast(dict[str, object], metadata["mcp"])
        assert "mcp" in metadata
        assert mcp_metadata["server"] == "server-x"
        assert mcp_metadata["transport"] == "sse"
        assert mcp_metadata["remote"] is True
        assert mcp_metadata["authenticated"] is True
        assert mcp_metadata["timeout_ms"] == 5000
        assert mcp_metadata["trust_level"] == "full"

    def test_default_risk_level(self):
        tool = MCPTool(
            name="default-risk",
            description="",
            schema={},
            mcp_client=mock.MagicMock(),
            server_name="srv",
        )
        # No annotations → default is MEDIUM
        assert tool.risk_level == RiskLevel.MEDIUM

    def test_tags_include_server_and_transport(self):
        tool = MCPTool(
            name="tagged",
            description="",
            schema={},
            mcp_client=mock.MagicMock(),
            server_name="my-server",
            transport="stdio",
        )
        assert "mcp" in tool.tags
        assert "my-server" in tool.tags
        assert "stdio" in tool.tags

    def test_high_risk_for_destructive(self):
        tool = MCPTool(
            name="destructive",
            description="",
            schema={},
            mcp_client=mock.MagicMock(),
            server_name="srv",
            annotations={"destructiveHint": True},
        )
        assert tool.risk_level == RiskLevel.HIGH


class TestSchemaProblem:
    """inputSchema 계약 판정 — 위반은 조용히 넘기지 않는다."""

    def test_empty_schema_is_accepted(self):
        # 인자 없는 도구는 `{}` 로 오는 것이 정상이다(과잉 거절 금지).
        assert _schema_problem({}) is None

    def test_object_schema_is_accepted(self):
        assert _schema_problem({"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}) is None

    def test_missing_schema_is_a_problem(self):
        assert _schema_problem(None) is not None

    def test_non_mapping_schema_is_a_problem(self):
        assert _schema_problem(["not", "a", "mapping"]) is not None

    def test_non_object_type_is_a_problem(self):
        problem = _schema_problem({"type": "string"})
        assert problem is not None and "object" in problem

    def test_non_list_required_is_a_problem(self):
        assert _schema_problem({"type": "object", "required": "q"}) is not None

    def test_non_string_required_entries_are_a_problem(self):
        assert _schema_problem({"type": "object", "required": [1, 2]}) is not None

    def test_non_mapping_properties_is_a_problem(self):
        assert _schema_problem({"type": "object", "properties": ["q"]}) is not None


class TestMCPToolTypedOutcome:
    """MCPTool.execute 는 CallToolResult 의 구조·오류를 typed 결과로 보존한다."""

    @pytest.fixture
    def loop(self) -> Iterator[asyncio.AbstractEventLoop]:
        owned = asyncio.new_event_loop()
        yield owned
        owned.close()

    def _tool(self, result: object, loop: asyncio.AbstractEventLoop, **kwargs: object) -> MCPTool:
        client = mock.MagicMock()
        client.call_tool = mock.AsyncMock(return_value=result)
        return MCPTool(
            name="ssak_search",
            description="",
            schema={"type": "object"},
            mcp_client=client,
            server_name="ssak",
            transport="stdio",
            session_loop=loop,
            **kwargs,
        )

    def test_plain_text_is_returned_verbatim(self, loop: asyncio.AbstractEventLoop):
        result = CallToolResult(content=[TextContent(type="text", text="hello")], isError=False)
        outcome = self._tool(result, loop).execute(query="x")

        assert isinstance(outcome, MCPToolOutcome)
        assert str(outcome) == "hello"
        assert outcome.is_error is False
        assert outcome.error_code is None
        assert outcome.partial is False
        assert result_indicates_failure(outcome) is False

    def test_is_error_is_typed_and_marked_in_text(self, loop: asyncio.AbstractEventLoop):
        payload = {"error": {"code": "INVALID_TOOL_ARGS", "detail": "bad arg"}}
        result = CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload))],
            isError=True,
        )
        outcome = self._tool(result, loop).execute(query=1)

        assert outcome.is_error is True
        assert outcome.error_code == "INVALID_TOOL_ARGS"
        assert result_indicates_failure(outcome) is True
        text = str(outcome)
        assert text.startswith("Error:")
        assert '"code": "INVALID_TOOL_ARGS"' in text  # 원문 보존(개행·들여쓰기 무관)
        # 문자열로 뭉개는 경로(레거시 분류)도 실패로 남는다 — 이중 안전장치.
        assert result_indicates_failure(text) is True

    def test_typed_flag_wins_even_without_error_marker(self, loop: asyncio.AbstractEventLoop):
        # 서버가 오류 마커 없는 본문에 isError 만 실은 경우에도 성공으로 새지 않는다.
        outcome = MCPToolOutcome("payload arrived fine", is_error=True, error_code="BOOM")
        assert result_indicates_failure(outcome) is True
        assert result_indicates_failure("payload arrived fine") is False

    def test_structured_content_is_preserved(self, loop: asyncio.AbstractEventLoop):
        result = CallToolResult(
            content=[TextContent(type="text", text="summary")],
            structuredContent={"status": "partial", "partial": True, "items": [1, 2]},
            isError=False,
        )
        outcome = self._tool(result, loop).execute()

        assert outcome.structured_content == {"status": "partial", "partial": True, "items": [1, 2]}
        assert outcome.partial is True
        text = str(outcome)
        assert text.startswith("summary")
        assert "[structuredContent]" in text
        assert '"items"' in text
        assert outcome.metadata()["partial"] is True

    def test_media_blocks_are_preserved(self, loop: asyncio.AbstractEventLoop):
        result = CallToolResult(
            content=[
                TextContent(type="text", text="bundle"),
                ImageContent(type="image", data="QUJD", mimeType="image/png"),
                EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(uri="fixture://n.txt", mimeType="text/plain", text="note body"),
                ),
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(uri="fixture://b.bin", mimeType="application/pdf", blob="AAEC"),
                ),
                ResourceLink(type="resource_link", name="linked", uri="fixture://l.txt", mimeType="text/plain"),
            ],
            isError=False,
        )
        outcome = self._tool(result, loop).execute()

        kinds = [block["type"] for block in outcome.blocks]
        assert kinds == ["text", "image", "resource", "resource", "resource_link"]
        assert outcome.blocks[1]["data"] == "QUJD"
        assert outcome.blocks[1]["mimeType"] == "image/png"
        assert outcome.blocks[2]["text"] == "note body"
        assert outcome.blocks[3]["blob"] == "AAEC"
        assert outcome.blocks[4]["uri"] == "fixture://l.txt"
        text = str(outcome)
        assert "bundle" in text
        assert "note body" in text
        assert "fixture://l.txt" in text  # AnyUrl 이 str 판정에서 사라지지 않는다
        assert "[image: image/png" in text

    def test_empty_content_falls_back_to_structured_dump(self, loop: asyncio.AbstractEventLoop):
        # 종전에는 content 가 비면 결과 객체(pydantic repr)를 그대로 돌려줬다.
        result = CallToolResult(content=[], isError=False)
        outcome = self._tool(result, loop).execute()

        assert isinstance(outcome, MCPToolOutcome)
        assert "content" in str(outcome)
        assert "CallToolResult" not in str(outcome)

    def test_transport_failure_becomes_typed_error(self, loop: asyncio.AbstractEventLoop):
        client = mock.MagicMock()
        client.call_tool = mock.AsyncMock(side_effect=RuntimeError("broken pipe"))
        tool = MCPTool(
            name="ssak_search",
            description="",
            schema={},
            mcp_client=client,
            server_name="ssak",
            transport="stdio",
            session_loop=loop,
        )
        outcome = tool.execute(query="x")

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "TRANSPORT_ERROR"
        assert result_indicates_failure(outcome) is True
        assert "broken pipe" in str(outcome)

    def test_running_session_loop_is_refused_instead_of_hanging(self):
        class _RunningLoop:
            def is_running(self) -> bool:
                return True

        client = mock.MagicMock()
        client.call_tool = mock.AsyncMock()
        tool = MCPTool(
            name="ssak_search",
            description="",
            schema={},
            mcp_client=client,
            server_name="ssak",
            transport="stdio",
            session_loop=cast(asyncio.AbstractEventLoop, _RunningLoop()),
        )
        outcome = tool.execute(query="x")

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "CALL_LOOP_UNAVAILABLE"
        assert client.call_tool.await_count == 0, "멈출 루프에 호출을 던졌다"

    def test_request_policy_denial_blocks_before_the_server_call(self, loop: asyncio.AbstractEventLoop):
        result = CallToolResult(content=[TextContent(type="text", text="ok")], isError=False)
        tool = self._tool(result, loop)
        client = tool._mcp_client

        token = set_tool_policy(ToolPolicy(allowed_mcp_servers=frozenset({"other"})))
        try:
            outcome = tool.execute(query="x")
        finally:
            reset_tool_policy(token)

        assert isinstance(outcome, MCPToolOutcome)
        assert outcome.is_error is True
        assert outcome.error_code == "POLICY_DENIED"
        assert "[BLOCKED]" in str(outcome)
        assert client.call_tool.await_count == 0, "허용되지 않은 서버로 호출이 나갔다"

    def test_denied_tool_toggle_blocks_before_the_server_call(self, loop: asyncio.AbstractEventLoop):
        result = CallToolResult(content=[TextContent(type="text", text="ok")], isError=False)
        tool = self._tool(result, loop)

        token = set_tool_policy(ToolPolicy(denied_tools=frozenset({"ssak_search"})))
        try:
            outcome = tool.execute(query="x")
        finally:
            reset_tool_policy(token)

        assert outcome.is_error is True
        assert outcome.error_code == "POLICY_DENIED"
        assert tool._mcp_client.call_tool.await_count == 0

    def test_loader_records_schema_violations_and_skips_those_tools(self):
        """스키마 위반 도구는 등록하지 않고 이유를 남긴다(SDK 가 막지 못하는 경로)."""
        good = mock.MagicMock()
        good.name = "good"
        good.description = "ok"
        good.inputSchema = {"type": "object", "properties": {}}
        good.annotations = None
        bad = mock.MagicMock()
        bad.name = "no_schema"
        bad.description = "missing inputSchema"
        bad.inputSchema = None
        bad.input_schema = None
        bad.annotations = None
        listed = mock.MagicMock()
        listed.tools = [good, bad]

        session = mock.MagicMock()
        session.list_tools = mock.AsyncMock(return_value=listed)

        loader = _loader.MCPToolLoader(config_path=None, include_system_tools=False, load_skill_servers=False)
        loader.session_manager.connect_server = mock.AsyncMock(return_value=session)

        asyncio.run(loader._connect_and_load_servers({"srv": {"command": "x"}}, "test"))

        assert [tool.name for tool in loader.tools] == ["good"]
        assert loader.schema_errors == [{"server": "srv", "tool": "no_schema", "reason": "inputSchema 가 없다"}]
