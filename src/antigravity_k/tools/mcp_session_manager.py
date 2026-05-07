from contextlib import AsyncExitStack
import logging
from typing import Any, Dict, Optional

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class MCPSessionManager:
    """
    Manages MCP sessions with external plugins/servers.
    Handles the asynchronous lifecycle of MCP servers running over stdio,
    Streamable HTTP, and legacy SSE transports.
    """

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stacks: Dict[str, AsyncExitStack] = {}
        self.session_ids: Dict[str, Optional[str]] = {}

    async def connect_server(
        self,
        server_name: str,
        command: str,
        args: list[str],
        env: Optional[Dict[str, str]] = None,
    ) -> ClientSession:
        """
        Connects to an MCP server over stdio.
        """
        logger.info(
            f"Connecting to MCP server '{server_name}' using command: {command} {' '.join(args)}"
        )

        stack = AsyncExitStack()
        self.exit_stacks[server_name] = stack

        server_params = StdioServerParameters(command=command, args=args, env=env)

        try:
            # Connect to the stdio server
            read, write = await stack.enter_async_context(stdio_client(server_params))

            # Create and initialize the session
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            self.sessions[server_name] = session
            logger.info(
                f"Successfully connected and initialized MCP server '{server_name}'"
            )
            return session

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{server_name}': {e}")
            await stack.aclose()
            if server_name in self.exit_stacks:
                del self.exit_stacks[server_name]
            raise

    async def connect_streamable_http(
        self,
        server_name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30,
        sse_read_timeout: float = 300,
        auth: Optional[Any] = None,
    ) -> ClientSession:
        """
        Connects to an MCP server using the current Streamable HTTP transport.
        """
        logger.info(
            f"Connecting to MCP server '{server_name}' over Streamable HTTP: {url}"
        )

        stack = AsyncExitStack()
        self.exit_stacks[server_name] = stack

        try:
            read, write, get_session_id = await stack.enter_async_context(
                streamablehttp_client(
                    url,
                    headers=headers,
                    timeout=timeout,
                    sse_read_timeout=sse_read_timeout,
                    auth=auth,
                )
            )

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            self.sessions[server_name] = session
            self.session_ids[server_name] = get_session_id()
            logger.info(
                f"Successfully connected and initialized MCP server '{server_name}' "
                "over Streamable HTTP"
            )
            return session

        except Exception as e:
            logger.error(
                f"Failed to connect to MCP server '{server_name}' over Streamable HTTP: {e}"
            )
            await stack.aclose()
            if server_name in self.exit_stacks:
                del self.exit_stacks[server_name]
            if server_name in self.session_ids:
                del self.session_ids[server_name]
            raise

    async def connect_sse(
        self,
        server_name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5,
        sse_read_timeout: float = 300,
        auth: Optional[Any] = None,
    ) -> ClientSession:
        """
        Connects to an MCP server using the legacy HTTP+SSE transport.
        Prefer connect_streamable_http for new remote servers.
        """
        logger.info(f"Connecting to MCP server '{server_name}' over legacy SSE: {url}")

        stack = AsyncExitStack()
        self.exit_stacks[server_name] = stack

        try:
            read, write = await stack.enter_async_context(
                sse_client(
                    url,
                    headers=headers,
                    timeout=timeout,
                    sse_read_timeout=sse_read_timeout,
                    auth=auth,
                )
            )

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            self.sessions[server_name] = session
            logger.info(
                f"Successfully connected and initialized MCP server '{server_name}' over SSE"
            )
            return session

        except Exception as e:
            logger.error(
                f"Failed to connect to MCP server '{server_name}' over SSE: {e}"
            )
            await stack.aclose()
            if server_name in self.exit_stacks:
                del self.exit_stacks[server_name]
            raise

    async def disconnect_server(self, server_name: str):
        """
        Disconnects from an MCP server and cleans up resources.
        """
        if server_name in self.exit_stacks:
            logger.info(f"Disconnecting MCP server '{server_name}'")
            await self.exit_stacks[server_name].aclose()
            del self.exit_stacks[server_name]

        if server_name in self.sessions:
            del self.sessions[server_name]

        if server_name in self.session_ids:
            del self.session_ids[server_name]

    def get_session(self, server_name: str) -> Optional[ClientSession]:
        return self.sessions.get(server_name)

    async def cleanup(self):
        """
        Disconnects all active MCP servers.
        """
        servers = list(self.exit_stacks.keys())
        for server in servers:
            await self.disconnect_server(server)
