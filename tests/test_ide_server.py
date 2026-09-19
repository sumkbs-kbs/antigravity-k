"""Tests for the ide_server module."""

import subprocess
from typing import cast
from unittest import mock

from antigravity_k.engine.ide_server import IDEServer


class _ProcessDouble:
    poll_result: int | None
    timeout_on_wait: bool
    terminate_calls: int
    kill_calls: int

    def __init__(self, poll_result: int | None = None, timeout_on_wait: bool = False) -> None:
        self.poll_result = poll_result
        self.timeout_on_wait = timeout_on_wait
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return self.poll_result

    def wait(self, timeout: float | None = None) -> None:
        _ = timeout
        if self.timeout_on_wait:
            raise subprocess.TimeoutExpired("cmd", 5)

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


def _call_args(mock_popen: mock.MagicMock) -> tuple[tuple[object, ...], dict[str, object]]:
    return cast(tuple[tuple[object, ...], dict[str, object]], getattr(mock_popen, "call_args"))


class TestIDEServerInit:
    def test_defaults(self) -> None:
        srv = IDEServer()
        assert srv.port == 8080
        assert srv.workspace_dir == "."
        assert srv.process is None

    def test_custom_params(self) -> None:
        srv = IDEServer(port=3000, workspace_dir="/workspace")
        assert srv.port == 3000
        assert srv.workspace_dir == "/workspace"
        assert srv.process is None


class TestIDEServerStart:
    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_start_success(self, mock_popen: mock.MagicMock) -> None:
        mock_process = _ProcessDouble()
        setattr(mock_popen, "return_value", mock_process)

        srv = IDEServer(port=9000, workspace_dir="/tmp")
        srv.start()

        assert cast(int, getattr(mock_popen, "call_count")) == 1
        cmd = cast(list[str], _call_args(mock_popen)[0][0])
        assert "code-server" in cmd[0]
        assert "127.0.0.1:9000" in cmd
        assert "/tmp" in cmd

    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_start_already_running(self, mock_popen: mock.MagicMock) -> None:
        mock_process = _ProcessDouble()
        setattr(mock_popen, "return_value", mock_process)

        srv = IDEServer(port=8080)
        srv.process = cast(subprocess.Popen[bytes], cast(object, mock_process))  # already set

        srv.start()

        # Popen should NOT be called again
        assert cast(int, getattr(mock_popen, "call_count")) == 0

    @mock.patch(
        "antigravity_k.engine.ide_server.subprocess.Popen", side_effect=FileNotFoundError("code-server not found")
    )
    def test_start_file_not_found(self, mock_popen: mock.MagicMock) -> None:
        _ = mock_popen
        srv = IDEServer(port=8080)
        srv.start()
        assert srv.process is None


class TestIDEServerStop:
    def test_stop_none(self) -> None:
        srv = IDEServer()
        srv.stop()  # should not raise

    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_stop_running(self, mock_popen: mock.MagicMock) -> None:
        mock_process = _ProcessDouble()
        setattr(mock_popen, "return_value", mock_process)

        srv = IDEServer(port=8080)
        srv.process = cast(subprocess.Popen[bytes], cast(object, mock_process))
        srv.stop()

        assert mock_process.terminate_calls == 1

    @mock.patch("antigravity_k.engine.ide_server.subprocess.Popen")
    def test_stop_timeout_then_kill(self, mock_popen: mock.MagicMock) -> None:
        mock_process = _ProcessDouble(timeout_on_wait=True)
        setattr(mock_popen, "return_value", mock_process)

        srv = IDEServer(port=8080)
        srv.process = cast(subprocess.Popen[bytes], cast(object, mock_process))
        srv.stop()

        assert mock_process.terminate_calls == 1
        assert mock_process.kill_calls == 1


class TestIDEServerIsRunning:
    def test_no_process(self) -> None:
        srv = IDEServer()
        assert srv.is_running() is False

    def test_process_running(self) -> None:
        mock_process = _ProcessDouble()
        srv = IDEServer()
        srv.process = cast(subprocess.Popen[bytes], cast(object, mock_process))
        assert srv.is_running() is True

    def test_process_stopped(self) -> None:
        mock_process = _ProcessDouble(poll_result=0)
        srv = IDEServer()
        srv.process = cast(subprocess.Popen[bytes], cast(object, mock_process))
        assert srv.is_running() is False
