from antigravity_k.engine.mcp_capability import MCPCapabilityAdvisor
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.tools.base_tool import RiskLevel
from antigravity_k.tools.mcp_tool_loader import MCPTool


def test_mcp_audit_blocks_remote_http_without_auth():
    advisor = MCPCapabilityAdvisor()
    report = advisor.audit_config(
        {
            "mcpServers": {
                "remote": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                    "trust_level": "verified",
                    "timeout_ms": 30000,
                    "tool_annotations": "required",
                }
            }
        }
    )

    assert report.blocking_count == 1
    assert any(finding.code == "remote_without_auth" for finding in report.findings)


def test_mcp_audit_accepts_guarded_local_stdio_config():
    advisor = MCPCapabilityAdvisor()
    report = advisor.audit_config(
        {
            "mcpServers": {
                "filesystem": {
                    "type": "stdio",
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem@1.0.0",
                        ".",
                    ],
                    "trust_level": "local",
                    "timeout_ms": 30000,
                    "tool_annotations": "required",
                }
            }
        }
    )

    assert report.servers_ready == 1
    assert report.blocking_count == 0
    assert not any(finding.code == "unpinned_npx_package" for finding in report.findings)


def test_mcp_template_contains_transport_trust_and_timeout():
    template = MCPCapabilityAdvisor().render_template()

    assert '"type": "http"' in template
    assert '"trust_level": "verified"' in template
    assert '"timeout_ms": 30000' in template
    assert '"tool_annotations": "required"' in template


def test_mcp_slash_command_and_completion():
    registry = SlashCommandRegistry()

    assert registry.is_command("/mcp")
    assert "/mcp" in registry.get_completions("/mc")

    result = registry.execute("/mcp")

    assert "MCP Upgrade Radar" in result
    assert "Streamable HTTP transport" in result
    assert "Tool annotations" in result


def test_mcp_tool_annotations_drive_risk_metadata():
    read_only = MCPTool(
        name="safe_read",
        description="Read only MCP tool",
        schema={"type": "object"},
        mcp_client=object(),
        server_name="local",
        transport="stdio",
        annotations={"readOnlyHint": True},
    )
    destructive = MCPTool(
        name="danger_write",
        description="Destructive MCP tool",
        schema={"type": "object"},
        mcp_client=object(),
        server_name="remote",
        transport="http",
        annotations={"destructiveHint": True},
        server_policy={"trust_level": "verified", "authenticated": True},
    )

    assert read_only.risk_level == RiskLevel.SAFE
    assert destructive.risk_level == RiskLevel.HIGH
    assert read_only.to_metadata()["mcp"]["server"] == "local"
    assert destructive.to_metadata()["mcp"]["authenticated"] is True
