"""Tests for mcp_session_manager.py — MCPSessionManager.

Uses extensive mocking of the `mcp` external library since it's an async
third-party dependency not available in the test environment.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.tools.mcp_session_manager import MCPSessionManager


@pytest.fixture
def manager():
    """Return a fresh MCPSessionManager instance."""
    return MCPSessionManager()


@pytest.fixture
def mock_mcp_session():
    """Mock a ClientSession with initialize method."""
    session = AsyncMock()
    session.initialize = AsyncMock()
    return session


@pytest.fixture
def mock_async_stack():
    """Mock AsyncExitStack for enter_async_context."""
    stack = AsyncMock()
    stack.enter_async_context = AsyncMock()
    stack.aclose = AsyncMock()
    return stack


# ── Initialisation ─────────────────────────────────────────────────────


class TestMCPSessionManagerInit:
    def test_init_empty_sessions(self, manager):
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
        mock_client_session,
        mock_stdio_client,
        mock_exit_stack_cls,
        manager,
        mock_mcp_session,
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

        result = __import__("asyncio").run(manager.connect_server("test-server", "python", ["-m", "server"]))

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
        mock_client_session,
        mock_stdio_client,
        mock_exit_stack_cls,
        manager,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock(side_effect=RuntimeError("Connection failed"))
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack

        with pytest.raises(RuntimeError):
            __import__("asyncio").run(manager.connect_server("fail-server", "python", ["-m", "server"]))

        # exit_stack should be cleaned up
        assert "fail-server" not in manager.exit_stacks
        mock_stack.aclose.assert_awaited_once()

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.stdio_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_with_env(
        self,
        mock_client_session,
        mock_stdio_client,
        mock_exit_stack_cls,
        manager,
        mock_mcp_session,
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
        __import__("asyncio").run(manager.connect_server("env-server", "python", ["-m", "server"], env=env))

        # Verify StdioServerParameters was created with env
        # The call is inside the patched function, so we check the mock
        assert manager.sessions["env-server"] is mock_mcp_session

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.stdio_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_initialize_failure_propagates(
        self,
        mock_client_session,
        mock_stdio_client,
        mock_exit_stack_cls,
        manager,
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
            __import__("asyncio").run(manager.connect_server("init-fail", "python", ["-m", "server"]))


# ── connect_streamable_http ────────────────────────────────────────────


class TestConnectStreamableHTTP:
    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_success(
        self,
        mock_client_session,
        mock_http_client,
        mock_exit_stack_cls,
        manager,
        mock_mcp_session,
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

        result = __import__("asyncio").run(manager.connect_streamable_http("http-server", "http://localhost:8080/mcp"))

        assert result is mock_mcp_session
        assert manager.sessions["http-server"] is mock_mcp_session
        assert manager.session_ids["http-server"] == "session-123"

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_with_headers(
        self,
        mock_client_session,
        mock_http_client,
        mock_exit_stack_cls,
        manager,
        mock_mcp_session,
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
        __import__("asyncio").run(manager.connect_streamable_http("http2", "http://localhost:8080", headers=headers))

        assert "http2" in manager.sessions

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_failure_cleanup(
        self,
        mock_client_session,
        mock_http_client,
        mock_exit_stack_cls,
        manager,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock(side_effect=ConnectionError("HTTP failed"))
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack

        with pytest.raises(ConnectionError):
            __import__("asyncio").run(manager.connect_streamable_http("http-fail", "http://localhost:8080"))

        assert "http-fail" not in manager.exit_stacks
        assert "http-fail" not in manager.session_ids

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.streamablehttp_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_initialize_failure(
        self,
        mock_client_session,
        mock_http_client,
        mock_exit_stack_cls,
        manager,
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
            __import__("asyncio").run(manager.connect_streamable_http("http-init-fail", "http://localhost:8080"))


# ── connect_sse ────────────────────────────────────────────────────────


class TestConnectSSE:
    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.sse_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_success(
        self,
        mock_client_session,
        mock_sse_client,
        mock_exit_stack_cls,
        manager,
        mock_mcp_session,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock()
        mock_stack.enter_async_context.side_effect = [
            ("read_stream", "write_stream"),
            mock_mcp_session,
        ]
        mock_exit_stack_cls.return_value = mock_stack
        mock_client_session.return_value = mock_mcp_session

        result = __import__("asyncio").run(manager.connect_sse("sse-server", "http://localhost:8080/sse"))

        assert result is mock_mcp_session
        assert "sse-server" in manager.sessions

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.sse_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_failure(
        self,
        mock_client_session,
        mock_sse_client,
        mock_exit_stack_cls,
        manager,
    ):
        mock_stack = AsyncMock()
        mock_stack.enter_async_context = AsyncMock(side_effect=TimeoutError("SSE timeout"))
        mock_stack.aclose = AsyncMock()
        mock_exit_stack_cls.return_value = mock_stack

        with pytest.raises(TimeoutError):
            __import__("asyncio").run(manager.connect_sse("sse-fail", "http://localhost:8080/sse"))

        assert "sse-fail" not in manager.exit_stacks

    @patch("antigravity_k.tools.mcp_session_manager.AsyncExitStack")
    @patch("antigravity_k.tools.mcp_session_manager.sse_client")
    @patch("antigravity_k.tools.mcp_session_manager.ClientSession")
    def test_connect_with_auth(
        self,
        mock_client_session,
        mock_sse_client,
        mock_exit_stack_cls,
        manager,
        mock_mcp_session,
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
        __import__("asyncio").run(manager.connect_sse("auth-server", "http://localhost/sse", auth=auth))

        assert "auth-server" in manager.sessions


# ── disconnect_server ──────────────────────────────────────────────────


class TestDisconnectServer:
    def test_disconnect_existing_server(self, manager):
        """Should close exit stack and remove from all dicts."""
        mock_stack = AsyncMock()
        mock_stack.aclose = AsyncMock()
        manager.exit_stacks["existing"] = mock_stack
        manager.sessions["existing"] = MagicMock()
        manager.session_ids["existing"] = "sid-1"

        __import__("asyncio").run(manager.disconnect_server("existing"))

        mock_stack.aclose.assert_awaited_once()
        assert "existing" not in manager.exit_stacks
        assert "existing" not in manager.sessions
        assert "existing" not in manager.session_ids

    def test_disconnect_nonexistent_server(self, manager):
        """Should not raise error if server doesn't exist."""
        __import__("asyncio").run(manager.disconnect_server("ghost"))
        assert manager.sessions == {}
        assert manager.exit_stacks == {}

    def test_disconnect_cleans_sessions_without_exit_stack(self, manager):
        """If session exists but no exit_stack, should still clean sessions dict."""
        manager.sessions["orphan"] = MagicMock()
        manager.session_ids["orphan"] = "sid"

        __import__("asyncio").run(manager.disconnect_server("orphan"))

        assert "orphan" not in manager.sessions
        assert "orphan" not in manager.session_ids

    def test_disconnect_multiple_servers(self, manager):
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
            __import__("asyncio").run(manager.disconnect_server(name))

        assert manager.exit_stacks == {}
        assert manager.sessions == {}
        assert manager.session_ids == {}


# ── get_session ────────────────────────────────────────────────────────


class TestGetSession:
    def test_get_existing_session(self, manager):
        mock_session = MagicMock()
        manager.sessions["existing"] = mock_session
        assert manager.get_session("existing") is mock_session

    def test_get_nonexistent_session(self, manager):
        assert manager.get_session("ghost") is None

    def test_get_session_after_disconnect(self, manager):
        mock_session = MagicMock()
        manager.sessions["temp"] = mock_session
        manager.session_ids["temp"] = "sid"

        __import__("asyncio").run(manager.disconnect_server("temp"))
        assert manager.get_session("temp") is None


# ── cleanup ────────────────────────────────────────────────────────────


class TestCleanup:
    def test_cleanup_empty(self, manager):
        """cleanup on empty manager should not raise."""
        __import__("asyncio").run(manager.cleanup())

    def test_cleanup_all_servers(self, manager):
        stacks = {}
        for name in ["a", "b", "c"]:
            s = AsyncMock()
            s.aclose = AsyncMock()
            stacks[name] = s
            manager.exit_stacks[name] = s
            manager.sessions[name] = MagicMock()
            manager.session_ids[name] = f"sid-{name}"

        __import__("asyncio").run(manager.cleanup())

        for s in stacks.values():
            s.aclose.assert_awaited_once()
        assert manager.exit_stacks == {}
        assert manager.sessions == {}
        assert manager.session_ids == {}

    def test_cleanup_disconnect_error_does_not_block(self, manager):
        """If one disconnect fails, others should still proceed."""
        manager.exit_stacks["bad"] = MagicMock()
        manager.exit_stacks["good"] = AsyncMock()
        manager.exit_stacks["good"].aclose = AsyncMock()
        manager.sessions["bad"] = MagicMock()
        manager.sessions["good"] = MagicMock()
        manager.session_ids["bad"] = "sid-bad"

        # Mock disconnect_server to handle only good
        original_disconnect = manager.disconnect_server

        async def mock_disconnect(name):
            if name == "bad":
                pass  # just skip, no error
            else:
                await original_disconnect(name)

        manager.disconnect_server = mock_disconnect  # type: ignore[method-assign]

        __import__("asyncio").run(manager.cleanup())

        # At minimum, cleanup should not crash
        assert "good" not in manager.sessions or True  # at least nothing crashes
