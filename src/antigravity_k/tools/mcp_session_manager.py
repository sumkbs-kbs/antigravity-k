import logging
from typing import Dict, Optional
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from contextlib import AsyncExitStack

logger = logging.getLogger(__name__)


class MCPSessionManager:
    """
    Manages MCP sessions with external plugins/servers.
    Handles the asynchronous lifecycle of MCP servers running over stdio.
    """

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stacks: Dict[str, AsyncExitStack] = {}

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

    def get_session(self, server_name: str) -> Optional[ClientSession]:
        return self.sessions.get(server_name)

    async def cleanup(self):
        """
        Disconnects all active MCP servers.
        """
        servers = list(self.exit_stacks.keys())
        for server in servers:
            await self.disconnect_server(server)
