import logging
import json
import asyncio
import os
from typing import List, Dict, Any, Mapping, Optional

from antigravity_k.engine.mcp_capability import MCPCapabilityAdvisor

from .base_tool import BaseTool, RiskLevel, ToolCategory
from .system_tools import ReadFileTool, ReplaceFileContentTool, RunBashCommandTool
from .mcp_session_manager import MCPSessionManager
from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)


class MCPTool(BaseTool):
    """
    MCP(Model Context Protocol) 리소스를 래핑하는 도구.
    실제 MCP 서버의 엔드포인트나 리소스를 호출하여 결과를 반환합니다.
    """

    def __init__(
        self,
        name: str,
        description: str,
        schema: Dict[str, Any],
        mcp_client: ClientSession,
        server_name: str = "",
        transport: str = "stdio",
        annotations: Optional[Mapping[str, Any]] = None,
        server_policy: Optional[Mapping[str, Any]] = None,
    ):
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
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def execute(self, **kwargs) -> Any:
        logger.info(f"Executing MCP Tool '{self._name}' with args: {kwargs}")

        # Async MCP call wrapped synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            self._mcp_client.call_tool(self._name, arguments=kwargs)
        )

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

    def to_metadata(self) -> Dict[str, Any]:
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
    """
    설정된 MCP 서버들로부터 도구 목록을 가져와서 BaseTool 객체 리스트로 변환하는 로더.
    """

    def __init__(
        self,
        config_path: Optional[str] = ".mcp.json",
        include_system_tools: bool = True,
    ):
        self.config_path = config_path
        self.include_system_tools = include_system_tools
        self.tools: List[BaseTool] = []
        self.session_manager = MCPSessionManager()

    def load_tools(self) -> List[BaseTool]:
        """
        MCP 서버와 통신하여 사용 가능한 도구 목록을 조회하고 로드합니다.
        동기 방식으로 호출되며, 내부는 asyncio.run으로 비동기 초기화를 래핑합니다.
        """
        logger.info("Loading tools from MCP servers...")

        # 시스템(Local) 도구 등록
        if self.include_system_tools:
            self.tools.extend(
                [ReadFileTool(), ReplaceFileContentTool(), RunBashCommandTool()]
            )

        if not self.config_path or not os.path.exists(self.config_path):
            logger.warning(
                f"MCP config not found at {self.config_path}. Skipping dynamic MCP servers."
            )
            return self.tools

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self._load_mcp_servers())

        return self.tools

    async def _load_mcp_servers(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        mcp_servers = config.get("mcpServers", {})
        advisor = MCPCapabilityAdvisor()
        audit = advisor.audit_config(
            {"mcpServers": mcp_servers}, source=self.config_path
        )
        blocked_servers = {
            finding.server for finding in audit.findings if finding.severity == "error"
        }

        for finding in audit.findings:
            log_message = (
                f"MCP audit [{finding.severity}] {finding.server}: "
                f"{finding.message} {finding.recommendation}"
            )
            if finding.severity == "error":
                logger.error(log_message)
            elif finding.severity == "warning":
                logger.warning(log_message)
            else:
                logger.info(log_message)

        for server_name, server_config in mcp_servers.items():
            if server_name in blocked_servers:
                logger.error(
                    f"Skipping MCP server '{server_name}' due to audit errors."
                )
                continue

            try:
                transport = _transport_for(server_config)
                session = await self._connect_server(
                    server_name, server_config, transport
                )

                # Fetch available tools
                tools_response = await session.list_tools()

                for tool in tools_response.tools:
                    annotations = _annotations_to_dict(
                        getattr(tool, "annotations", None)
                    )
                    mcp_tool = MCPTool(
                        name=tool.name,
                        description=tool.description or "",
                        schema=getattr(tool, "inputSchema", None)
                        or getattr(tool, "input_schema", {})
                        or {},
                        mcp_client=session,
                        server_name=server_name,
                        transport=transport,
                        annotations=annotations,
                        server_policy=_server_policy(server_config),
                    )
                    self.tools.append(mcp_tool)
                    logger.info(f"Registered MCP tool: {tool.name} from {server_name}")

            except Exception as e:
                logger.error(f"Error loading tools from '{server_name}': {e}")

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
            return await self.session_manager.connect_server(
                server_name, command, args, env
            )

        headers = _string_dict(server_config.get("headers", {}))
        url = str(server_config.get("url") or server_config.get("endpoint") or "")
        timeout = _timeout_seconds(server_config, default=30)
        sse_read_timeout = _timeout_seconds(
            server_config, default=300, keys=("sse_read_timeout", "sse_read_timeout_ms")
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


def _annotations_to_dict(annotations: Any) -> Dict[str, Any]:
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


def _string_dict(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _server_policy(config: Mapping[str, Any]) -> Dict[str, Any]:
    headers = config.get("headers", {})
    authenticated = bool(config.get("auth") or config.get("auth_profile"))
    if isinstance(headers, Mapping):
        authenticated = authenticated or any(
            str(key).lower() == "authorization" for key in headers
        )
    return {
        "trust_level": config.get("trust_level", "experimental"),
        "authenticated": authenticated,
        "timeout_ms": config.get("timeout_ms") or config.get("timeout"),
    }


# ─── MCP 서버 레지스트리 (커뮤니티 무료 서버 카탈로그) ─────────────


class MCPServerRegistry:
    """
    MCP 에코시스템의 무료 커뮤니티 서버 카탈로그.

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

    def get_all(self) -> Dict[str, Dict]:
        """전체 카탈로그를 반환합니다."""
        return self.CATALOG.copy()

    def get_by_category(self, category: str) -> Dict[str, Dict]:
        """카테고리별 서버를 반환합니다."""
        return {k: v for k, v in self.CATALOG.items() if v.get("category") == category}

    def get_recommended(self) -> List[str]:
        """에이전트 기능 강화에 추천하는 서버 목록을 반환합니다."""
        return ["filesystem", "fetch", "memory", "sequential-thinking", "gitnexus"]

    def generate_config(self, output_path: str, server_ids: List[str] = None) -> str:
        """
        .mcp.json 설정 파일을 자동 생성합니다.

        Args:
            output_path: 출력 경로 (예: ".mcp.json")
            server_ids: 포함할 서버 ID 목록 (None이면 추천 목록)

        Returns:
            생성된 파일 경로
        """
        if server_ids is None:
            server_ids = self.get_recommended()

        config = {"mcpServers": {}}

        for sid in server_ids:
            if sid not in self.CATALOG:
                logger.warning(f"Unknown MCP server: {sid}")
                continue

            entry = self.CATALOG[sid]
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
            f"[MCPRegistry] 설정 생성: {output_path} ({len(config['mcpServers'])}개 서버)"
        )
        return output_path

    def get_catalog_summary(self) -> str:
        """카탈로그 요약을 사람이 읽기 쉬운 형식으로 반환합니다."""
        lines = ["📦 MCP 서버 카탈로그 (무료)", ""]
        by_category = {}
        for sid, info in self.CATALOG.items():
            cat = info.get("category", "other")
            by_category.setdefault(cat, []).append((sid, info))

        for cat, servers in sorted(by_category.items()):
            lines.append(f"  [{cat}]")
            for sid, info in servers:
                lines.append(f"    - {sid}: {info['description']}")

        return "\n".join(lines)
