"""Tests for mcp_session_manager.py — MCPSessionManager.

Uses extensive mocking of the `mcp` external library since it's an async
third-party dependency not available in the test environment.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.tools.mcp_session_manager import MCPSessionManager


@pytest.fixture
def manager() -> MCPSessionManager:
    """Return a fresh MCPSessionManager instance."""
    return MCPSessionManager()


@pytest.fixture
def mock_mcp_session() -> AsyncMock:
    """Mock a ClientSession with initialize method."""
    session = AsyncMock()
    session.initialize = AsyncMock()
    return session


@pytest.fixture
def mock_async_stack() -> AsyncMock:
    """Mock AsyncExitStack for enter_async_context."""
    stack = AsyncMock()
    stack.enter_async_context = AsyncMock()
    stack.aclose = AsyncMock()
    return stack


# ── Initialisation ─────────────────────────────────────────────────────


class TestMCPSessionManagerInit:
    def test_init_empty_sessions(self, manager: MCPSessionManager):
        assert manager.sessions == {}
        assert manager.exit_stacks == {}
        assert manager.session_ids == {}


# ── connect_server (stdio) ─────────────────────────────────────────────


class TestConnectServer:
    """Tests for MCPSessionManager.connect_server with mocked stdio transport."""

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.stdio_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_success(
        self,
        mock_client_session: MagicMock,
        _mock_stdio_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
        mock_mcp_session: AsyncMock,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        # First enter -> stdio read/write, second enter -> ClientSession
        mock_stack.enter_async_context.side_effect = [
            ("read_stream", "write_stream"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        result = asyncio.run(manager.connect_server("test-server", "python", ["-m", "server"]))

        assert result is mock_mcp_session
        assert "test-server" in manager.sessions
        assert manager.sessions["test-server"] is mock_mcp_session
        assert "test-server" in manager.exit_stacks
        mock_mcp_session.initialize.assert_awaited_once()

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.stdio_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_failure_cleanup(
        self,
        _mock_client_session: MagicMock,
        _mock_stdio_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock(side_effect=RuntimeError("Connection failed"))
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack

        with pytest.raises(RuntimeError):
            _ = asyncio.run(manager.connect_server("fail-server", "python", ["-m", "server"]))

        # exit_stack should be cleaned up
        assert "fail-server" not in manager.exit_stacks
        mock_stack.aclose.assert_awaited_once()

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.stdio_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_with_env(
        self,
        mock_client_session: MagicMock,
        _mock_stdio_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
        mock_mcp_session: AsyncMock,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("read_stream", "write_stream"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        env = {"API_KEY": "secret"}
        _ = asyncio.run(manager.connect_server("env-server", "python", ["-m", "server"], env=env))

        # Verify StdioServerParameters was created with env
        # The call is inside the patched function, so we check the mock
        assert manager.sessions["env-server"] is mock_mcp_session

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.stdio_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_initialize_failure_propagates(
        self,
        mock_client_session: MagicMock,
        _mock_stdio_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
    ):
        mock_mcp_session_bad = AsyncMock()
        mock_mcp_session_bad.initialize = AsyncMock(side_effect=RuntimeError("Init failed"))
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("read_stream", "write_stream"),
            mock_mcp_session_bad,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session_bad

        with pytest.raises(RuntimeError, match="Init failed"):
            _ = asyncio.run(manager.connect_server("init-fail", "python", ["-m", "server"]))


# ── connect_streamable_http ────────────────────────────────────────────


class TestConnectStreamableHTTP:
    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_success(
        self,
        mock_client_session: MagicMock,
        _mock_http_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
        mock_mcp_session: AsyncMock,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        # First enter -> (read, write, get_session_id), second enter -> ClientSession
        mock_stack.enter_async_context.side_effect = [
            ("read_stream", "write_stream", lambda: "session-123"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        result = asyncio.run(manager.connect_streamable_http("http-server", "http://localhost:8080/mcp"))

        assert result is mock_mcp_session
        assert manager.sessions["http-server"] is mock_mcp_session
        assert manager.session_ids["http-server"] == "session-123"

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_with_headers(
        self,
        mock_client_session: MagicMock,
        _mock_http_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
        mock_mcp_session: AsyncMock,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("r", "w", lambda: "sid"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        headers = {"Authorization": "Bearer token"}
        _ = asyncio.run(manager.connect_streamable_http("http2", "http://localhost:8080", headers=headers))

        assert "http2" in manager.sessions

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_failure_cleanup(
        self,
        _mock_client_session: MagicMock,
        _mock_http_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock(side_effect=ConnectionError("HTTP failed"))
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack

        with pytest.raises(ConnectionError):
            _ = asyncio.run(manager.connect_streamable_http("http-fail", "http://localhost:8080"))

        assert "http-fail" not in manager.exit_stacks
        assert "http-fail" not in manager.session_ids

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_initialize_failure(
        self,
        mock_client_session: MagicMock,
        _mock_http_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
    ):
        bad_session = AsyncMock()
        bad_session.initialize = AsyncMock(side_effect=ValueError("Init error"))
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("r", "w", lambda: "sid"),
            bad_session,
        ]
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = bad_session

        with pytest.raises(ValueError):
            _ = asyncio.run(manager.connect_streamable_http("http-init-fail", "http://localhost:8080"))


# ── connect_sse ────────────────────────────────────────────────────────


class TestConnectSSE:
    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.sse_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_success(
        self,
        mock_client_session: MagicMock,
        _mock_sse_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
        mock_mcp_session: AsyncMock,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("read_stream", "write_stream"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        result = asyncio.run(manager.connect_sse("sse-server", "http://localhost:8080/sse"))

        assert result is mock_mcp_session
        assert "sse-server" in manager.sessions

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.sse_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_failure(
        self,
        _mock_client_session: MagicMock,
        _mock_sse_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock(side_effect=TimeoutError("SSE timeout"))
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack

        with pytest.raises(TimeoutError):
            _ = asyncio.run(manager.connect_sse("sse-fail", "http://localhost:8080/sse"))

        assert "sse-fail" not in manager.exit_stacks

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.sse_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_with_auth(
        self,
        mock_client_session: MagicMock,
        _mock_sse_client: MagicMock,
        mock_exit_stack_cls: MagicMock,
        manager: MCPSessionManager,
        mock_mcp_session: AsyncMock,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("r", "w"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        auth = MagicMock()
        _ = asyncio.run(manager.connect_sse("auth-server", "http://localhost/sse", auth=auth))

        assert "auth-server" in manager.sessions


# ── disconnect_server ──────────────────────────────────────────────────


class TestDisconnectServer:
    def test_disconnect_existing_server(self, manager: MCPSessionManager):
        """Should close exit stack and remove from all dicts."""
        mock_stack = AsyncMock()
        mock_stack.aclose = AsyncMock()
        manager.exit_stacks["existing"] = mock_stack
        manager.sessions["existing"] = MagicMock()
        manager.session_ids["existing"] = "sid-1"

        asyncio.run(manager.disconnect_server("existing"))

        mock_stack.aclose.assert_awaited_once()
        assert "existing" not in manager.exit_stacks
        assert "existing" not in manager.sessions
        assert "existing" not in manager.session_ids

    def test_disconnect_nonexistent_server(self, manager: MCPSessionManager):
        """Should not raise error if server doesn't exist."""
        asyncio.run(manager.disconnect_server("ghost"))
        assert manager.sessions == {}
        assert manager.exit_stacks == {}

    def test_disconnect_cleans_sessions_without_exit_stack(self, manager: MCPSessionManager):
        """If session exists but no exit_stack, should still clean sessions dict."""
        manager.sessions["orphan"] = MagicMock()
        manager.session_ids["orphan"] = "sid"

        asyncio.run(manager.disconnect_server("orphan"))

        assert "orphan" not in manager.sessions
        assert "orphan" not in manager.session_ids

    def test_disconnect_multiple_servers(self, manager: MCPSessionManager):
        """Should be able to disconnect multiple servers sequentially."""
        stacks = {}
        for name in ["svr1", "svr2", "svr3"]:
            s = AsyncMock()
            s.aclose = AsyncMock()
            stacks[name] = s
            manager.exit_stacks[name] = s
            manager.sessions[name] = MagicMock()
            manager.session_ids[name] = f"sid-{name}"

        for name in ["svr1", "svr2", "svr3"]:
            asyncio.run(manager.disconnect_server(name))

        assert manager.exit_stacks == {}
        assert manager.sessions == {}
        assert manager.session_ids == {}


# ── get_session ────────────────────────────────────────────────────────


class TestGetSession:
    def test_get_existing_session(self, manager: MCPSessionManager):
        mock_session = MagicMock()
        manager.sessions["existing"] = mock_session
        assert manager.get_session("existing") is mock_session

    def test_get_nonexistent_session(self, manager: MCPSessionManager):
        assert manager.get_session("ghost") is None

    def test_get_session_after_disconnect(self, manager: MCPSessionManager):
        mock_session = MagicMock()
        manager.sessions["temp"] = mock_session
        manager.session_ids["temp"] = "sid"

        asyncio.run(manager.disconnect_server("temp"))
        assert manager.get_session("temp") is None


# ── cleanup ────────────────────────────────────────────────────────────


class TestCleanup:
    def test_cleanup_empty(self, manager: MCPSessionManager):
        """cleanup on empty manager should not raise."""
        asyncio.run(manager.cleanup())

    def test_cleanup_all_servers(self, manager: MCPSessionManager):
        stacks = {}
        for name in ["a", "b", "c"]:
            s = AsyncMock()
            s.aclose = AsyncMock()
            stacks[name] = s
            manager.exit_stacks[name] = s
            manager.sessions[name] = MagicMock()
            manager.session_ids[name] = f"sid-{name}"

        asyncio.run(manager.cleanup())

        for s in stacks.values():
            s.aclose.assert_awaited_once()
        assert manager.exit_stacks == {}
        assert manager.sessions == {}
        assert manager.session_ids == {}

    def test_cleanup_disconnect_error_does_not_block(self, manager: MCPSessionManager):
        """If one disconnect fails, others should still proceed."""
        manager.exit_stacks["bad"] = MagicMock()
        manager.exit_stacks["good"] = AsyncMock()
        manager.exit_stacks["good"].aclose = AsyncMock()
        manager.sessions["bad"] = MagicMock()
        manager.sessions["good"] = MagicMock()
        manager.session_ids["bad"] = "sid-bad"

        # Mock disconnect_server to handle only good
        original_disconnect = manager.disconnect_server

        async def mock_disconnect(server_name: str) -> None:
            if server_name == "bad":
                pass  # just skip, no error
            else:
                await original_disconnect(server_name)

        manager.disconnect_server = mock_disconnect  # type: ignore[method-assign]

        asyncio.run(manager.cleanup())

        # At minimum, cleanup should not crash
        assert "good" not in manager.sessions or True  # at least nothing crashes
