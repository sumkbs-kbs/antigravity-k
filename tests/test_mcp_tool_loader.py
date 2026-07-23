"""Tests for MCP Tool Loader (mcp_tool_loader.py)."""

from __future__ import annotations

import json
import os
import tempfile
from unittest import mock

from antigravity_k.tools.base_tool import RiskLevel
from antigravity_k.tools.mcp_tool_loader import (
    MCPServerRegistry,
    MCPTool,
    _annotations_to_dict,
    _risk_from_annotations,
    _server_policy,
    _string_dict,
    _timeout_seconds,
    _transport_for,
)

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
        mock_model = mock.Mock()
        mock_model.model_dump.return_value = {"readOnlyHint": True}
        result = _annotations_to_dict(mock_model)
        assert result == {"readOnlyHint": True}
        mock_model.model_dump.assert_called_once_with(exclude_none=True)

    def test_dict_method(self):
        mock_obj = mock.Mock()
        mock_obj.dict.return_value = {"destructiveHint": True}
        # Ensure it doesn't have model_dump
        del mock_obj.model_dump
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
        MCPServerRegistry._skill_servers.clear()

    def teardown_method(self):
        """Clean up _skill_servers after each test."""
        MCPServerRegistry._skill_servers.clear()

    def test_register_skill_mcp(self):
        registry = MCPServerRegistry()
        mcp_config = {
            "serverId": "my-skill-server",
            "command": "python",
            "args": ["-m", "my_skill"],
        }
        result = registry.register_skill_mcp("my-skill", mcp_config)
        assert result is True
        assert "my-skill-server" in registry._skill_servers

    def test_get_skill_mcp_servers_returns_registered(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("test-skill", {"serverId": "ts1", "command": "echo"})
        servers = registry.get_skill_mcp_servers()
        assert "ts1" in servers
        assert servers["ts1"]["skill_name"] == "test-skill"

    def test_get_skill_mcp_servers_filtered_by_name(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("skill-a", {"serverId": "sa1", "command": "echo"})
        registry.register_skill_mcp("skill-b", {"serverId": "sb1", "command": "echo"})
        filtered = registry.get_skill_mcp_servers("skill-a")
        assert "sa1" in filtered
        assert "sb1" not in filtered

    def test_unregister_skill_mcp_removes_servers(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("my-skill", {"serverId": "ms1", "command": "echo"})
        registry.register_skill_mcp("my-skill", {"serverId": "ms2", "command": "echo"})
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
        registry.register_skill_mcp("skill-a", {"serverId": "sa1", "command": "echo"})
        registry.register_skill_mcp("skill-b", {"serverId": "sb1", "command": "echo"})
        skills = registry.list_skills_with_mcp()
        skill_names = [s["skill"] for s in skills]
        assert "skill-a" in skill_names
        assert "skill-b" in skill_names

    def test_get_all_includes_skill_servers(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("s1", {"serverId": "custom-srv", "command": "echo"})
        all_servers = registry.get_all()
        assert "custom-srv" in all_servers

    def test_get_by_category_includes_skill_servers(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("s1", {"serverId": "custom-srv", "command": "echo"})
        # register_skill_mcp always sets category="skill"
        skill_servers = registry.get_by_category("skill")
        assert "custom-srv" in skill_servers

    def test_skill_server_isolation_between_instances(self):
        # _skill_servers is a class variable shared across instances
        registry1 = MCPServerRegistry()
        registry2 = MCPServerRegistry()
        registry1.register_skill_mcp("skill", {"serverId": "shared-srv", "command": "echo"})
        assert "shared-srv" in registry2._skill_servers
        # Clean up
        MCPServerRegistry._skill_servers.clear()

    def test_catalog_summary_includes_skills(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("skill-x", {"serverId": "sx1", "command": "echo"})
        summary = registry.get_catalog_summary()
        assert "sx1" in summary
        assert "skill: skill-x" in summary
        MCPServerRegistry._skill_servers.clear()


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
                data = json.load(f)
            assert "mcpServers" in data
            assert "filesystem" in data["mcpServers"]
            assert "fetch" in data["mcpServers"]
        finally:
            os.unlink(tmp_path)

    def test_generate_config_defaults_to_recommended(self):
        registry = MCPServerRegistry()
        with mock.patch.object(registry, "get_recommended", return_value=["filesystem"]):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                registry.generate_config(tmp_path)
                with open(tmp_path, encoding="utf-8") as f:
                    data = json.load(f)
                assert "filesystem" in data["mcpServers"]
            finally:
                os.unlink(tmp_path)

    def test_generate_config_unknown_server_warns(self):
        registry = MCPServerRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with mock.patch("antigravity_k.tools.mcp_tool_loader.logger") as mock_log:
                registry.generate_config(tmp_path, server_ids=["nonexistent"])
                mock_log.warning.assert_called_once()
        finally:
            os.unlink(tmp_path)

    def test_generate_config_with_skills(self):
        registry = MCPServerRegistry()
        registry.register_skill_mcp("skill-z", {"serverId": "zs1", "command": "echo"})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            registry.generate_config_with_skills(tmp_path)
            with open(tmp_path, encoding="utf-8") as f:
                data = json.load(f)
            assert "zs1" in data["mcpServers"]
        finally:
            os.unlink(tmp_path)
            MCPServerRegistry._skill_servers.clear()


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
        assert "mcp" in metadata
        assert metadata["mcp"]["server"] == "server-x"
        assert metadata["mcp"]["transport"] == "sse"
        assert metadata["mcp"]["remote"] is True
        assert metadata["mcp"]["authenticated"] is True
        assert metadata["mcp"]["timeout_ms"] == 5000
        assert metadata["mcp"]["trust_level"] == "full"

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
