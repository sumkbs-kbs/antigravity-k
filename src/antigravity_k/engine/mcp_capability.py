"""MCP capability and safety advisor.

This module keeps MCP adoption inside Antigravity-K evidence-driven: it can
inspect MCP server configuration, map it to the latest protocol capabilities,
and produce a concrete upgrade plan before any external server is connected.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class MCPFinding:
    """A single MCP capability radar finding (feature, status, recommendation)."""

    server: str
    severity: str
    code: str
    message: str
    recommendation: str


@dataclass(frozen=True)
class MCPCapability:
    """Describes a supported or recommended MCP capability."""

    name: str
    why_it_matters: str
    antigravity_action: str
    priority: str
    evidence_url: str


@dataclass(frozen=True)
class MCPAuditReport:
    """Aggregated audit report for an MCP server configuration."""

    source: str
    servers_total: int
    servers_ready: int
    findings: list[MCPFinding] = field(default_factory=list)
    capabilities: list[MCPCapability] = field(default_factory=list)

    @property
    def blocking_count(self) -> int:
        """Blocking Count.

        Returns:
            int: The int result.

        """
        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def warning_count(self) -> int:
        """Warning Count.

        Returns:
            int: The int result.

        """
        return sum(1 for finding in self.findings if finding.severity == "warning")


class MCPCapabilityAdvisor:
    """Audit MCP configs and render latest-technology upgrade guidance."""

    def latest_capabilities(self) -> list[MCPCapability]:
        """Latest Capabilities.

        Returns:
            list[MCPCapability]: The list[mcpcapability] result.

        """
        return [
            MCPCapability(
                name="Streamable HTTP transport",
                why_it_matters=(
                    "The latest MCP transport model replaces legacy HTTP+SSE and "
                    "supports POST/GET, streaming, resumability, and sessions."
                ),
                antigravity_action=(
                    "Support `type: http` / `transport: streamable-http` in "
                    "MCPSessionManager and prefer it for remote servers."
                ),
                priority="P0",
                evidence_url="https://modelcontextprotocol.io/specification/2025-11-25/basic/transports",
            ),
            MCPCapability(
                name="OAuth 2.1 authorization",
                why_it_matters=(
                    "Remote MCP servers should authenticate clients rather than depending on ambient API keys."
                ),
                antigravity_action=(
                    "Flag non-local HTTP MCP servers without Authorization headers or an auth profile before import."
                ),
                priority="P0",
                evidence_url="https://modelcontextprotocol.io/specification/2025-03-26/changelog",
            ),
            MCPCapability(
                name="Tool annotations",
                why_it_matters=(
                    "Annotations such as read-only or destructive help clients apply "
                    "permission gates and avoid accidental side effects."
                ),
                antigravity_action=("Map MCP annotations to BaseTool risk levels and dashboard metadata."),
                priority="P0",
                evidence_url="https://modelcontextprotocol.io/specification/2025-03-26/changelog",
            ),
            MCPCapability(
                name="JSON-RPC batching and completions",
                why_it_matters=(
                    "Batching reduces round trips; completions improve parameter entry and tool-call accuracy."
                ),
                antigravity_action=(
                    "Expose batching/completions as optional server capabilities in the MCP audit report."
                ),
                priority="P1",
                evidence_url="https://modelcontextprotocol.io/specification/2025-03-26/changelog",
            ),
            MCPCapability(
                name="HF MCPClient and Tiny Agents",
                why_it_matters=(
                    "Hugging Face now exposes MCPClient/Tiny Agent patterns for "
                    "connecting stdio, SSE, and HTTP MCP servers to tool-using agents."
                ),
                antigravity_action=(
                    "Keep MCP config compatible with `stdio`, `sse`, and `http` "
                    "server descriptors and surface a template command."
                ),
                priority="P1",
                evidence_url="https://huggingface.co/docs/huggingface_hub/package_reference/mcp",
            ),
            MCPCapability(
                name="Precomputed Relational Intelligence (GitNexus)",
                why_it_matters=(
                    "Graph-based AST parsers like GitNexus precompute dependency chains, "
                    "preventing LLMs from hallucinating blast radius or missing references."
                ),
                antigravity_action=(
                    "Expose GitNexus MCP tools (`impact`, `context`) to the orchestration "
                    "loop so the agent can safely explore dependencies before refactoring."
                ),
                priority="P1",
                evidence_url="https://github.com/abhigyanpatwari/GitNexus",
            ),
        ]

    def load_config(self, path: str | Path) -> Mapping[str, Any]:
        """Load config.

        Args:
            path (str | Path): str | Path path.

        Returns:
            Mapping[str, Any]: The mapping[str, any] result.

        """
        config_path = Path(path)
        if not config_path.exists():
            return {}
        return json.loads(config_path.read_text(encoding="utf-8"))

    def audit_config(
        self,
        config: Mapping[str, Any] | None,
        source: str = "inline",
    ) -> MCPAuditReport:
        """Audit Config.

        Args:
            config (Mapping[str, Any] | None): Mapping[str, Any] | None config.
            source (str): str source.

        Returns:
            MCPAuditReport: The mcpauditreport result.

        """
        config = config or {}
        servers = config.get("mcpServers", {})
        if not isinstance(servers, Mapping):
            return MCPAuditReport(
                source=source,
                servers_total=0,
                servers_ready=0,
                findings=[
                    MCPFinding(
                        "*",
                        "error",
                        "invalid_config",
                        "`mcpServers` must be an object.",
                        "Use a Claude/HF-compatible MCP config with `mcpServers`.",
                    ),
                ],
                capabilities=self.latest_capabilities(),
            )

        findings: list[MCPFinding] = []
        ready = 0
        for name, raw_server in servers.items():
            server = raw_server if isinstance(raw_server, Mapping) else {}
            server_findings = self._audit_server(str(name), server)
            findings.extend(server_findings)
            if not any(item.severity == "error" for item in server_findings):
                ready += 1

        if not servers:
            findings.append(
                MCPFinding(
                    "*",
                    "info",
                    "no_servers",
                    "No MCP servers are configured.",
                    "Use `/mcp template` to start with a guarded local/remote setup.",
                ),
            )

        return MCPAuditReport(
            source=source,
            servers_total=len(servers),
            servers_ready=ready,
            findings=findings,
            capabilities=self.latest_capabilities(),
        )

    def _audit_server(self, name: str, server: Mapping[str, Any]) -> list[MCPFinding]:
        findings: list[MCPFinding] = []
        transport = _transport_for(server)

        if transport not in {"stdio", "http", "streamable-http", "sse"}:
            findings.append(
                MCPFinding(
                    name,
                    "error",
                    "unknown_transport",
                    f"Unknown MCP transport `{transport}`.",
                    "Use `stdio`, `http`/`streamable-http`, or legacy `sse`.",
                ),
            )
            return findings

        if transport == "stdio":
            command = str(server.get("command", "")).strip()
            if not command:
                findings.append(
                    MCPFinding(
                        name,
                        "error",
                        "missing_command",
                        "stdio MCP server is missing `command`.",
                        "Set a fixed executable command and args.",
                    ),
                )
            args = [str(arg) for arg in server.get("args", []) or []]
            if _uses_unpinned_npx(command, args):
                findings.append(
                    MCPFinding(
                        name,
                        "warning",
                        "unpinned_npx_package",
                        "npx MCP server package is not pinned.",
                        "Pin package versions instead of using `@latest` or floating package names.",
                    ),
                )
        else:
            url = str(server.get("url", "") or server.get("endpoint", "")).strip()
            if not url:
                findings.append(
                    MCPFinding(
                        name,
                        "error",
                        "missing_url",
                        "Remote MCP server is missing `url`.",
                        "Set a single MCP endpoint URL such as `https://host/mcp`.",
                    ),
                )
            elif transport == "sse":
                findings.append(
                    MCPFinding(
                        name,
                        "warning",
                        "legacy_sse",
                        "SSE is supported for compatibility but is no longer the preferred transport.",
                        "Prefer Streamable HTTP (`type: http`) for new remote MCP servers.",
                    ),
                )

            if url and not _is_local_url(url) and not _has_auth(server):
                findings.append(
                    MCPFinding(
                        name,
                        "error",
                        "remote_without_auth",
                        "Remote MCP server has no auth profile or Authorization header.",
                        "Use OAuth/API auth metadata before enabling remote tool execution.",
                    ),
                )

        if not server.get("trust_level"):
            findings.append(
                MCPFinding(
                    name,
                    "warning",
                    "missing_trust_level",
                    "MCP server has no trust label.",
                    "Set `trust_level` to local, verified, partner, or experimental.",
                ),
            )

        if not server.get("timeout_ms") and not server.get("timeout"):
            findings.append(
                MCPFinding(
                    name,
                    "warning",
                    "missing_timeout",
                    "MCP server has no timeout.",
                    "Set `timeout_ms` to prevent hung tool calls.",
                ),
            )

        if not server.get("tool_annotations") and not server.get("annotations"):
            findings.append(
                MCPFinding(
                    name,
                    "info",
                    "missing_tool_annotations",
                    "No declared tool annotation policy was found.",
                    "Prefer MCP tools that provide read-only/destructive/open-world annotations.",
                ),
            )

        return findings

    def render_markdown(self, report: MCPAuditReport) -> str:
        """Render markdown.

        Args:
            report (MCPAuditReport): MCPAuditReport report.

        Returns:
            str: The str result.

        """
        lines = [
            "# MCP Upgrade Radar",
            "",
            f"**Source:** `{report.source}`",
            f"**Servers:** {report.servers_ready}/{report.servers_total} ready",
            f"**Findings:** errors={report.blocking_count}, warnings={report.warning_count}",
            "",
            "## Latest Capability Matrix",
            "",
            "| Capability | Why it matters | Antigravity-K action | Priority |",
            "| --- | --- | --- | --- |",
        ]
        for capability in report.capabilities:
            lines.append(
                "| "
                + " | ".join(
                    [
                        capability.name,
                        capability.why_it_matters,
                        capability.antigravity_action,
                        capability.priority,
                    ],
                )
                + " |",
            )

        lines.extend(["", "## Findings", ""])
        if not report.findings:
            lines.append("- No MCP config findings.")
        else:
            for finding in report.findings:
                lines.append(
                    f"- **{finding.severity.upper()} `{finding.code}`** "
                    f"({finding.server}): {finding.message} → {finding.recommendation}",
                )

        lines.extend(["", "## Evidence Sources", ""])
        for capability in report.capabilities:
            lines.append(f"- **{capability.name}:** {capability.evidence_url}")

        return "\n".join(lines)

    def render_template(self) -> str:
        """Render template.

        Returns:
            str: The str result.

        """
        template = {
            "mcpServers": {
                "playwright-local": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@playwright/mcp@latest"],
                    "trust_level": "local",
                    "timeout_ms": 30000,
                    "tool_annotations": "required",
                },
                "example-remote": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                    "headers": {"Authorization": "Bearer ${EXAMPLE_MCP_TOKEN}"},
                    "trust_level": "verified",
                    "timeout_ms": 30000,
                    "tool_annotations": "required",
                },
                "gitnexus": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "gitnexus@latest", "mcp"],
                    "trust_level": "local",
                    "timeout_ms": 60000,
                    "tool_annotations": "read-only",
                },
            },
        }
        return json.dumps(template, ensure_ascii=False, indent=2)


def _transport_for(server: Mapping[str, Any]) -> str:
    transport = str(server.get("transport") or server.get("type") or "").lower()
    if transport:
        if transport in {"streamable_http", "streamable-http"}:
            return "streamable-http"
        return transport
    if server.get("command"):
        return "stdio"
    if server.get("url") or server.get("endpoint"):
        return "http"
    return "unknown"


def _has_auth(server: Mapping[str, Any]) -> bool:
    if server.get("auth") or server.get("auth_profile"):
        return True
    headers = server.get("headers", {})
    if isinstance(headers, Mapping):
        return any(str(key).lower() == "authorization" for key in headers)
    return False


def _is_local_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _uses_unpinned_npx(command: str, args: list[str]) -> bool:
    if Path(command).name != "npx":
        return False
    joined = " ".join(args)
    if "@latest" in joined:
        return True
    package_args = [arg for arg in args if not arg.startswith("-")]
    for arg in package_args:
        if "/" in arg and not re.search(r"@[^/\s]+$", arg):
            return True
    return False
