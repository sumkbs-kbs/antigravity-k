"""Tests for the ide_server module."""

from unittest import mock

from antigravity_k.engine.ide_server import IDEServer


class TestIDEServerInit:
    def test_defaults(self):
        srv = IDEServer()
        assert srv.port == 8080
        assert srv.workspace_dir == "."
        assert srv.process is None

    def test_custom_params(self):
        srv = IDEServer(port=3000, workspace_dir="/workspace")
        assert srv.port == 3000
        assert srv.workspace_dir == "/workspace"
        assert srv.process is None


class TestIDEServerStart:
    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_start_success(self, mock_popen):
        mock_process = mock.MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        srv = IDEServer(port=9000, workspace_dir="/tmp")
        srv.start()

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "code-server" in cmd[0]
        assert "127.0.0.1:9000" in cmd
        assert "/tmp" in cmd

    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_start_already_running(self, mock_popen):
        mock_process = mock.MagicMock()
        mock_process.poll.return_value = None  # still running
        mock_popen.return_value = mock_process

        srv = IDEServer(port=8080)
        srv.process = mock_process  # already set

        srv.start()

        # Popen should NOT be called again
        assert mock_popen.call_count == 0

    @mock.patch(
        "antigravity_k.engine.ide_server.subprocess.Popen", side_effect=FileNotFoundError("code-server not found")
    )
    def test_start_file_not_found(self, mock_popen):
        srv = IDEServer(port=8080)
        srv.start()
        assert srv.process is None


class TestIDEServerStop:
    def test_stop_none(self):
        srv = IDEServer()
        srv.stop()  # should not raise

    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_stop_running(self, mock_popen):
        mock_process = mock.MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        srv = IDEServer(port=8080)
        srv.process = mock_process
        srv.stop()

        mock_process.terminate.assert_called_once()

    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_stop_timeout_then_kill(self, mock_popen):
        mock_process = mock.MagicMock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = __import__("subprocess").TimeoutExpired("cmd", 5)
        mock_popen.return_value = mock_process

        srv = IDEServer(port=8080)
        srv.process = mock_process
        srv.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()


class TestIDEServerIsRunning:
    def test_no_process(self):
        srv = IDEServer()
        assert srv.is_running() is False

    def test_process_running(self):
        mock_process = mock.MagicMock()
        mock_process.poll.return_value = None
        srv = IDEServer()
        srv.process = mock_process
        assert srv.is_running() is True

    def test_process_stopped(self):
        mock_process = mock.MagicMock()
        mock_process.poll.return_value = 0  # exit code = stopped
        srv = IDEServer()
        srv.process = mock_process
        assert srv.is_running() is False
