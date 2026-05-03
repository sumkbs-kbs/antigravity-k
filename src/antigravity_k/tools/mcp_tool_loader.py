import logging
import json
import asyncio
import os
from typing import List, Dict, Any, Optional
from .base_tool import BaseTool
from .system_tools import ReadFileTool, ReplaceFileContentTool, RunBashCommandTool
from .mcp_session_manager import MCPSessionManager
from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)

class MCPTool(BaseTool):
    """
    MCP(Model Context Protocol) 리소스를 래핑하는 도구.
    실제 MCP 서버의 엔드포인트나 리소스를 호출하여 결과를 반환합니다.
    """
    def __init__(self, name: str, description: str, schema: Dict[str, Any], mcp_client: ClientSession):
        self._name = name
        self._description = description
        self._schema = schema
        self._mcp_client = mcp_client

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


class MCPToolLoader:
    """
    설정된 MCP 서버들로부터 도구 목록을 가져와서 BaseTool 객체 리스트로 변환하는 로더.
    """
    def __init__(self, config_path: Optional[str] = ".mcp.json"):
        self.config_path = config_path
        self.tools: List[BaseTool] = []
        self.session_manager = MCPSessionManager()
        
    def load_tools(self) -> List[BaseTool]:
        """
        MCP 서버와 통신하여 사용 가능한 도구 목록을 조회하고 로드합니다.
        동기 방식으로 호출되며, 내부는 asyncio.run으로 비동기 초기화를 래핑합니다.
        """
        logger.info("Loading tools from MCP servers...")
        
        # 시스템(Local) 도구 등록
        self.tools.extend([
            ReadFileTool(),
            ReplaceFileContentTool(),
            RunBashCommandTool()
        ])
        
        if not self.config_path or not os.path.exists(self.config_path):
            logger.warning(f"MCP config not found at {self.config_path}. Skipping dynamic MCP servers.")
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
        for server_name, server_config in mcp_servers.items():
            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", None)
            
            if not command:
                logger.error(f"MCP Server '{server_name}' is missing 'command'.")
                continue
                
            try:
                session = await self.session_manager.connect_server(server_name, command, args, env)
                
                # Fetch available tools
                tools_response = await session.list_tools()
                
                for tool in tools_response.tools:
                    mcp_tool = MCPTool(
                        name=tool.name,
                        description=tool.description or "",
                        schema=tool.inputSchema,
                        mcp_client=session
                    )
                    self.tools.append(mcp_tool)
                    logger.info(f"Registered MCP tool: {tool.name} from {server_name}")
                    
            except Exception as e:
                logger.error(f"Error loading tools from '{server_name}': {e}")
