"""Mcp Tool Loader module."""

import asyncio
import json
import logging
import os
from collections.abc import Mapping
from typing import Any

from mcp.client.session import ClientSession

from antigravity_k.engine.mcp_capability import MCPCapabilityAdvisor

from .base_tool import BaseTool, RiskLevel, ToolCategory
from .mcp_session_manager import MCPSessionManager
from .system_tools import ReadFileTool, ReplaceFileContentTool, RunBashCommandTool

logger = logging.getLogger(__name__)


class MCPTool(BaseTool):
    """MCP(Model Context Protocol) 리소스를 래핑하는 도구.

    실제 MCP 서버의 엔드포인트나 리소스를 호출하여 결과를 반환합니다.
    """

    def __init__(
        self,
        name: str,
        description: str,
        schema: dict[str, Any],
        mcp_client: ClientSession,
        server_name: str = "",
        transport: str = "stdio",
        annotations: Mapping[str, Any] | None = None,
        server_policy: Mapping[str, Any] | None = None,
    ):
        """Initialize the MCPTool.

        Args:
            name (str): str name.
            description (str): str description.
            schema (dict[str, Any]): dict[str, Any] schema.
            mcp_client (ClientSession): ClientSession mcp client.
            server_name (str): str server name.
            transport (str): str transport.
            annotations (Mapping[str, Any] | None): Mapping[str, Any] | None annotations.
            server_policy (Mapping[str, Any] | None): Mapping[str, Any] | None server policy.

        """
        self._name = name
        self._description = description
        self._schema = schema
        self._mcp_client = mcp_client
        self._server_name = server_name
        self._transport = transport
        self._annotations = dict(annotations or {})
        self._server_policy = dict(server_policy or {})
        self.category = ToolCategory.DATA
        self.risk_level = _risk_from_annotations(self._annotations)
        self.icon = "🔌"
        self.tags = [tag for tag in ["mcp", server_name, transport] if tag]

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        logger.info("Executing MCP Tool '%s' with args: %s", self._name, kwargs)

        # Async MCP call wrapped synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(self._mcp_client.call_tool(self._name, arguments=kwargs))

        # Format the CallToolResult
        # The result might contain .content which is a list of blocks
        if hasattr(result, "content") and result.content:
            outputs = []
            for block in result.content:
                if block.type == "text":
                    outputs.append(block.text)
                else:
                    outputs.append(str(block))
            return "\n".join(outputs)

        return result

    def to_metadata(self) -> dict[str, Any]:
        """To Metadata.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        metadata = super().to_metadata()
        metadata["mcp"] = {
            "server": self._server_name,
            "transport": self._transport,
            "annotations": self._annotations,
            "trust_level": self._server_policy.get("trust_level", "experimental"),
            "remote": self._transport in {"http", "streamable-http", "sse"},
            "authenticated": bool(self._server_policy.get("authenticated")),
            "timeout_ms": self._server_policy.get("timeout_ms"),
        }
        return metadata


class MCPToolLoader:
    """설정된 MCP 서버들로부터 도구 목록을 가져와서 BaseTool 객체 리스트로 변환하는 로더.

    Phase 1 D11: MCPServerRegistry를 통해 스킬이 등록한 MCP 서버도 로드.
    """

    def __init__(
        self,
        config_path: str | None = ".mcp.json",
        include_system_tools: bool = True,
        load_skill_servers: bool = True,
        project_root: str | None = None,
    ):
        """Initialize the MCPToolLoader.

        Args:
            config_path (str | None): str | None config path.
            include_system_tools (bool): bool include system tools.
            load_skill_servers (bool): Phase 1 D11 — 스킬이 등록한 MCP 서버도 로드할지 여부.
            project_root (str | None): Phase 1 D11 — 프로젝트 루트 (스킬 메타데이터 스캔용).

        """
        self.config_path = config_path
        self.include_system_tools = include_system_tools
        self.load_skill_servers = load_skill_servers
        self.project_root = project_root or os.getcwd()
        self.tools: list[BaseTool] = []
        self.session_manager = MCPSessionManager()

    def load_tools(self) -> list[BaseTool]:
        """MCP 서버와 통신하여 사용 가능한 도구 목록을 조회하고 로드합니다.

        동기 방식으로 호출되며, 내부는 asyncio.run으로 비동기 초기화를 래핑합니다.
        Phase 1 D11: MCPServerRegistry의 스킬 등록 서버를 추가로 로드합니다.
        """
        logger.info("Loading tools from MCP servers...")

        # 시스템(Local) 도구 등록
        if self.include_system_tools:
            self.tools.extend([ReadFileTool(), ReplaceFileContentTool(), RunBashCommandTool()])

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Phase 1 D11: 표준 .mcp.json에서 서버 로드
        if self.config_path and os.path.exists(self.config_path):
            loop.run_until_complete(self._load_mcp_servers(self.config_path))
        else:
            logger.warning(
                "MCP config not found at %s. Skipping dynamic MCP servers.",
                self.config_path,
            )

        # Phase 1 D11: 스킬이 등록한 MCP 서버 로드
        if self.load_skill_servers:
            loop.run_until_complete(self._load_skill_mcp_servers())

        return self.tools

    async def _load_mcp_servers(self, config_path: str):
        with open(config_path, encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)

        mcp_servers = config.get("mcpServers", {})
        await self._connect_and_load_servers(mcp_servers, config_path)

    async def _load_skill_mcp_servers(self):
        """Phase 1 D11: MCPServerRegistry에서 스킬 등록 MCP 서버를 로드합니다."""
        try:
            registry = MCPServerRegistry()
            skill_servers = registry.get_skill_mcp_servers()

            if not skill_servers:
                return

            logger.info(
                "[MCPToolLoader] Loading %s skill-registered MCP servers...",
                len(skill_servers),
            )

            # 스킬 등록 서버를 .mcp.json 형식의 dict로 변환
            mcp_servers: dict[str, dict[str, Any]] = {}
            for sid, cfg in skill_servers.items():
                server_config: dict[str, Any] = {
                    "command": cfg.get("command", ""),
                    "args": list(cfg.get("args", [])),
                }
                if cfg.get("env"):
                    server_config["env"] = dict(cfg["env"])
                mcp_servers[sid] = server_config

            await self._connect_and_load_servers(mcp_servers, "skill-registry")

        except ImportError:
            logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
        except Exception:
            logger.exception("[MCPToolLoader] Failed to load skill MCP servers")

    async def _connect_and_load_servers(
        self,
        mcp_servers: dict[str, dict[str, Any]],
        source: str,
    ):
        """MCP 서버 목록을 연결하고 도구를 로드합니다.

        Phase 1 D11: _load_mcp_servers와 _load_skill_mcp_servers에서 공통 사용.

        Args:
            mcp_servers: 서버 이름 → 설정 매핑
            source: 로그용 출처 식별자 (파일 경로 또는 "skill-registry")
        """
        advisor = MCPCapabilityAdvisor()
        audit = advisor.audit_config({"mcpServers": mcp_servers}, source=source)
        blocked_servers = {finding.server for finding in audit.findings if finding.severity == "error"}

        for finding in audit.findings:
            log_message = f"MCP audit [{finding.severity}] {finding.server}: {finding.message} {finding.recommendation}"
            if finding.severity == "error":
                logger.error(log_message)
            elif finding.severity == "warning":
                logger.warning(log_message)
            else:
                logger.info(log_message)

        for server_name, server_config in mcp_servers.items():
            if server_name in blocked_servers:
                logger.error("Skipping MCP server '%s' due to audit errors.", server_name)
                continue

            try:
                transport = _transport_for(server_config)
                session = await self._connect_server(server_name, server_config, transport)

                # Fetch available tools
                tools_response = await session.list_tools()

                for tool in tools_response.tools:
                    annotations = _annotations_to_dict(getattr(tool, "annotations", None))
                    mcp_tool = MCPTool(
                        name=tool.name,
                        description=tool.description or "",
                        schema=getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", {}) or {},
                        mcp_client=session,
                        server_name=server_name,
                        transport=transport,
                        annotations=annotations,
                        server_policy=_server_policy(server_config),
                    )
                    self.tools.append(mcp_tool)
                    logger.info("Registered MCP tool: %s from %s", tool.name, server_name)

            except Exception:
                logger.exception("Error loading tools from '%s'", server_name)

    async def _connect_server(
        self,
        server_name: str,
        server_config: Mapping[str, Any],
        transport: str,
    ) -> ClientSession:
        if transport == "stdio":
            command = str(server_config.get("command", "")).strip()
            args = [str(arg) for arg in server_config.get("args", []) or []]
            env = server_config.get("env", None)
            return await self.session_manager.connect_server(server_name, command, args, env)

        headers = _string_dict(server_config.get("headers", {}))
        url = str(server_config.get("url") or server_config.get("endpoint") or "")
        timeout = _timeout_seconds(server_config, default=30)
        sse_read_timeout = _timeout_seconds(
            server_config,
            default=300,
            keys=("sse_read_timeout", "sse_read_timeout_ms"),
        )

        if transport in {"http", "streamable-http"}:
            return await self.session_manager.connect_streamable_http(
                server_name,
                url,
                headers=headers or None,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            )

        if transport == "sse":
            return await self.session_manager.connect_sse(
                server_name,
                url,
                headers=headers or None,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            )

        raise ValueError(f"Unsupported MCP transport: {transport}")


def _transport_for(server: Mapping[str, Any]) -> str:
    transport = str(server.get("transport") or server.get("type") or "").lower()
    if transport in {"streamable_http", "streamable-http"}:
        return "streamable-http"
    if transport:
        return transport
    if server.get("command"):
        return "stdio"
    if server.get("url") or server.get("endpoint"):
        return "http"
    return "unknown"


def _annotations_to_dict(annotations: Any) -> dict[str, Any]:
    if annotations is None:
        return {}
    if hasattr(annotations, "model_dump"):
        return annotations.model_dump(exclude_none=True)
    if hasattr(annotations, "dict"):
        return annotations.dict(exclude_none=True)
    if isinstance(annotations, Mapping):
        return dict(annotations)
    return {}


def _risk_from_annotations(annotations: Mapping[str, Any]) -> RiskLevel:
    if annotations.get("destructiveHint"):
        return RiskLevel.HIGH
    if annotations.get("openWorldHint"):
        return RiskLevel.MEDIUM
    if annotations.get("readOnlyHint"):
        return RiskLevel.SAFE
    return RiskLevel.MEDIUM


def _timeout_seconds(
    config: Mapping[str, Any],
    default: float,
    keys: tuple[str, str] = ("timeout", "timeout_ms"),
) -> float:
    primary, millis = keys
    if primary in config:
        return float(config[primary])
    if millis in config:
        return float(config[millis]) / 1000
    return default


def _string_dict(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _server_policy(config: Mapping[str, Any]) -> dict[str, Any]:
    headers = config.get("headers", {})
    authenticated = bool(config.get("auth") or config.get("auth_profile"))
    if isinstance(headers, Mapping):
        authenticated = authenticated or any(str(key).lower() == "authorization" for key in headers)
    return {
        "trust_level": config.get("trust_level", "experimental"),
        "authenticated": authenticated,
        "timeout_ms": config.get("timeout_ms") or config.get("timeout"),
    }


# ─── MCP 서버 레지스트리 (커뮤니티 무료 서버 카탈로그) ─────────────


class MCPServerRegistry:
    """MCP 에코시스템의 무료 커뮤니티 서버 카탈로그.

    추천 서버 목록을 관리하고, .mcp.json 설정 파일 자동 생성을 지원합니다.
    MCP가 Linux Foundation (Agentic AI Foundation)의 표준 프로토콜이 되면서
    1,000+ 서버가 에코시스템에 존재합니다.

    사용법:
        registry = MCPServerRegistry()
        recommended = registry.get_recommended()
        registry.generate_config(".mcp.json", ["filesystem", "github", "brave-search"])
    """

    # 검증된 무료 MCP 서버 카탈로그
    CATALOG = {
        "filesystem": {
            "name": "Filesystem",
            "description": "로컬 파일시스템 읽기/쓰기/검색",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            "category": "core",
            "free": True,
        },
        "github": {
            "name": "GitHub",
            "description": "GitHub API — 이슈, PR, 코드 검색",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
            "category": "dev",
            "free": True,
        },
        "brave-search": {
            "name": "Brave Search",
            "description": "Brave 웹 검색 API",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": ""},
            "category": "search",
            "free": True,  # 무료 티어 2,000회/월
        },
        "sqlite": {
            "name": "SQLite",
            "description": "SQLite 데이터베이스 쿼리",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sqlite"],
            "category": "data",
            "free": True,
        },
        "puppeteer": {
            "name": "Puppeteer",
            "description": "브라우저 자동화 (스크린샷, 네비게이션)",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
            "category": "browser",
            "free": True,
        },
        "memory": {
            "name": "Memory",
            "description": "Knowledge Graph 기반 영속 메모리",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "category": "memory",
            "free": True,
        },
        "fetch": {
            "name": "Fetch",
            "description": "URL 콘텐츠 가져오기 (마크다운 변환)",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fetch"],
            "category": "web",
            "free": True,
        },
        "sequential-thinking": {
            "name": "Sequential Thinking",
            "description": "구조화된 단계별 사고 (CoT 강화)",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            "category": "reasoning",
            "free": True,
        },
        "gitnexus": {
            "name": "GitNexus",
            "description": "코드베이스 Knowledge Graph 및 파급 효과(Blast Radius) 분석",
            "command": "npx",
            "args": ["-y", "gitnexus@latest", "mcp"],
            "category": "dev",
            "free": True,
        },
    }

    # Phase 1 D11: 스킬이 등록한 MCP 서버 저장소 (클래스 레벨 — 모든 인스턴스 공유)
    _skill_servers: dict[str, dict[str, Any]] = {}

    def get_all(self) -> dict[str, dict]:
        """전체 카탈로그를 반환합니다. (카탈로그 + 스킬 등록 서버 병합)"""
        merged = self.CATALOG.copy()
        for sid, config in self._skill_servers.items():
            merged[sid] = config
        return merged

    def get_by_category(self, category: str) -> dict[str, dict]:
        """카테고리별 서버를 반환합니다. (스킬 등록 서버 포함)"""
        result = {k: v for k, v in self.CATALOG.items() if v.get("category") == category}
        result.update({k: v for k, v in self._skill_servers.items() if v.get("category") == category})
        return result

    def get_recommended(self) -> list[str]:
        """에이전트 기능 강화에 추천하는 서버 목록을 반환합니다."""
        return ["filesystem", "fetch", "memory", "sequential-thinking", "gitnexus"]

    # ─── Phase 1 D11: Skill-MCP 연동 API ────────────────────────────

    def register_skill_mcp(self, skill_name: str, mcp_config: dict[str, Any]) -> bool:
        """스킬의 MCP 서버를 레지스트리에 등록합니다.

        SkillInstaller가 스킬 설치 시 호출하여, 해당 스킬이 제공하는 MCP 서버를
        MCPServerRegistry에 등록합니다. 이후 MCPToolLoader가 이 서버에서 도구를 로드할 수 있습니다.

        Args:
            skill_name: 스킬 이름 (예: "code-review")
            mcp_config: MCP 서버 설정 (command, args, env 등)

        Returns:
            등록 성공 여부
        """
        server_id = mcp_config.get("serverId", f"skill-{skill_name}")
        if server_id in self.CATALOG:
            logger.warning(
                "[MCPRegistry] Server '%s' already exists in catalog — skill '%s' registration skipped",
                server_id,
                skill_name,
            )
            return False

        # skill server config 저장
        self._skill_servers[server_id] = {
            "name": mcp_config.get("name", skill_name),
            "description": mcp_config.get("description", f"MCP server from skill '{skill_name}'"),
            "command": mcp_config.get("command", ""),
            "args": list(mcp_config.get("args", [])),
            "env": dict(mcp_config.get("env", {})),
            "category": "skill",
            "free": True,
            "skill_name": skill_name,
            "source": "skill",
        }

        logger.info(
            "[MCPRegistry] Skill MCP server registered: %s (skill=%s)",
            server_id,
            skill_name,
        )
        return True

    def unregister_skill_mcp(self, skill_name: str) -> bool:
        """스킬 제거 시 연결된 MCP 서버 등록을 해제합니다.

        Args:
            skill_name: 스킬 이름

        Returns:
            해제 성공 여부
        """
        removed = False
        for sid in list(self._skill_servers.keys()):
            if self._skill_servers[sid].get("skill_name") == skill_name:
                del self._skill_servers[sid]
                logger.info(
                    "[MCPRegistry] Skill MCP server unregistered: %s (skill=%s)",
                    sid,
                    skill_name,
                )
                removed = True
        if not removed:
            logger.debug("[MCPRegistry] No MCP servers found for skill '%s'", skill_name)
        return removed

    def get_skill_mcp_servers(self, skill_name: str | None = None) -> dict[str, dict]:
        """스킬이 등록한 MCP 서버 목록을 반환합니다.

        Args:
            skill_name: 특정 스킬 이름 (None이면 모든 스킬 서버)

        Returns:
            server_id → config 매핑
        """
        if skill_name:
            return {sid: cfg for sid, cfg in self._skill_servers.items() if cfg.get("skill_name") == skill_name}
        return dict(self._skill_servers)

    def list_skills_with_mcp(self) -> list[dict[str, Any]]:
        """MCP 서버를 등록한 스킬 목록을 반환합니다.

        Returns:
            스킬 이름 + MCP 서버 ID 목록
        """
        result: dict[str, list[str]] = {}
        for sid, cfg in self._skill_servers.items():
            skill_name = cfg.get("skill_name", "")
            if skill_name:
                result.setdefault(skill_name, []).append(sid)
        return [{"skill": skill, "servers": servers} for skill, servers in sorted(result.items())]

    def generate_config(self, output_path: str, server_ids: list[str] | None = None) -> str:
        """.mcp.json 설정 파일을 자동 생성합니다.

        Phase 1 D11: 스킬 등록 서버도 포함할 수 있습니다.

        Args:
            output_path: 출력 경로 (예: ".mcp.json")
            server_ids: 포함할 서버 ID 목록 (None이면 추천 목록)

        Returns:
            생성된 파일 경로

        """
        if server_ids is None:
            server_ids = self.get_recommended()

        config: dict[str, Any] = {"mcpServers": {}}
        all_servers = self.get_all()

        for sid in server_ids:
            if sid not in all_servers:
                logger.warning("Unknown MCP server: %s", sid)
                continue

            entry = all_servers[sid]
            server_config = {
                "command": entry["command"],
                "args": entry["args"],
            }
            if "env" in entry:
                server_config["env"] = entry["env"]

            config["mcpServers"][sid] = server_config

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info(
            "[MCPRegistry] 설정 생성: %s (%s개 서버, %s개 스킬 서버)",
            output_path,
            len(config["mcpServers"]),
            len(self._skill_servers),
        )
        return output_path

    def generate_config_with_skills(self, output_path: str, server_ids: list[str] | None = None) -> str:
        """.mcp.json 설정 파일을 생성합니다. (스킬 등록 서버 포함)

        Phase 1 D11: 추천 서버 + 스킬이 등록한 MCP 서버를 모두 포함한 설정 생성.

        Args:
            output_path: 출력 경로 (예: ".mcp.json")
            server_ids: 포함할 추가 서버 ID 목록 (None이면 추천 목록)

        Returns:
            생성된 파일 경로

        """
        if server_ids is None:
            server_ids = self.get_recommended()

        # 추천 서버 + 스킬 등록 서버 ID 모두 포함
        skill_server_ids = list(self._skill_servers.keys())
        all_ids = list(dict.fromkeys(server_ids + skill_server_ids))  # 중복 제거, 순서 유지

        return self.generate_config(output_path, all_ids)

    def get_catalog_summary(self) -> str:
        """카탈로그 요약을 사람이 읽기 쉬운 형식으로 반환합니다. (스킬 서버 포함)"""
        lines = ["📦 MCP 서버 카탈로그 (무료)", ""]
        by_category: dict[str, list] = {}

        all_servers = self.get_all()
        for sid, info in all_servers.items():
            cat = info.get("category", "other")
            by_category.setdefault(str(cat), []).append((sid, info))

        for cat, servers in sorted(by_category.items()):
            lines.append(f"  [{cat}]")
            for sid, info in servers:
                skill_tag = f" (skill: {info.get('skill_name', '')})" if info.get("source") == "skill" else ""
                lines.append(f"    - {sid}: {info['description']}{skill_tag}")

        return "\n".join(lines)
