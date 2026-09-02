"""SandboxRunner 격리 보장 검증 스위트 (P0).

기존 test_sandbox.py가 프로파일 "포함"만 검증한 것에 더해, 격리의
"부정" 보장(deny default, 네트워크 차단, 쓰기 화이트리스트, cwd 제한)을
검증합니다. macOS에서는 실제 sandbox-exec로 쓰기/네트워크 동작을 실증합니다.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import socket
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from antigravity_k.engine.sandbox import SandboxResult, SandboxRunner


def _writable_subpaths(profile: str) -> set[str]:
    return set(
        re.findall(r'\(allow file-write\* \(subpath "([^"]+)"\)\)', profile),
    )


def _call_private(target: object, name: str, *args: object) -> object:
    method = cast(Callable[..., object], cast(object, getattr(target, name)))
    return method(*args)


def _profile(runner: SandboxRunner) -> str:
    return cast(str, _call_private(runner, "_build_seatbelt_profile"))


class TestProfileBasePolicy:
    def test_profile_has_deny_default(self):
        runner = SandboxRunner(project_root="/custom/proj", enabled=True)
        profile = _profile(runner)
        assert "(deny default)" in profile

    def test_profile_allows_reads(self):
        runner = SandboxRunner(project_root="/custom/proj", enabled=True)
        profile = _profile(runner)
        assert "(allow file-read*)" in profile

    def test_profile_allows_process_operations(self):
        runner = SandboxRunner(project_root="/custom/proj", enabled=True)
        profile = _profile(runner)
        assert "(allow process-fork)" in profile
        assert "(allow process-exec)" in profile


class TestNetworkPolicy:
    def test_network_none_denies_network(self):
        runner = SandboxRunner(project_root="/tmp", enabled=True, network="none")
        profile = _profile(runner)
        assert "(deny network*)" in profile

    def test_network_all_allows_network(self):
        runner = SandboxRunner(project_root="/tmp", enabled=True, network="all")
        profile = _profile(runner)
        assert "(allow network*)" in profile
        assert "(deny network*)" not in profile

    def test_network_none_does_not_deny_file_writes(self):
        runner = SandboxRunner(project_root="/tmp", enabled=True, network="none")
        profile = _profile(runner)
        assert "(deny file-write*)" not in profile


class TestWriteWhitelist:
    def test_writable_subpaths_are_exactly_the_whitelist(self, tmp_path: Path):
        runner = SandboxRunner(project_root=str(tmp_path), enabled=True)
        profile = _profile(runner)
        expected = {
            str(tmp_path),
            "/tmp",
            "/var/tmp",
            "/private/tmp",
            "/private/var/folders",
            os.path.expanduser("~/.cache"),
        }
        assert _writable_subpaths(profile) == expected

    def test_home_other_than_cache_is_not_writable(self):
        runner = SandboxRunner(project_root="/custom/proj", enabled=True)
        profile = _profile(runner)
        home = os.path.expanduser("~")
        assert "/.ssh" not in profile
        assert home not in _writable_subpaths(profile)

    def test_system_paths_are_not_writable(self):
        runner = SandboxRunner(project_root="/custom/proj", enabled=True)
        profile = _profile(runner)
        assert _writable_subpaths(profile).isdisjoint({"/etc", "/usr", "/bin", "/Library"})


class TestProcessLimits:
    def test_limited_command_sets_ulimits(self):
        runner = SandboxRunner(project_root="/tmp", enabled=True, max_processes=32, max_memory_mb=512)
        cmd = cast(str, _call_private(runner, "_limited_command", "echo hi", 60))
        assert "ulimit -t 60" in cmd
        assert "ulimit -u 32" in cmd
        assert "ulimit -v 524288" in cmd

    def test_shell_quote_preserves_single_quotes(self):
        cmd = cast(str, _call_private(SandboxRunner, "_shell_quote", "echo 'a b'"))
        assert cmd == "'echo '\\''a b'\\'''"


class TestDockerCwdConfinement:
    def test_cwd_outside_project_root_is_denied(self):
        runner = SandboxRunner(project_root="/tmp/proj", enabled=True)
        result = cast(SandboxResult, _call_private(runner, "_execute_docker", "pwd", 60, None, "/etc"))
        assert not result.success
        assert "Working directory must remain inside the project root" in result.error

    def test_cwd_inside_project_root_is_accepted(self):
        runner = SandboxRunner(project_root="/tmp/proj", enabled=True)
        def fake_run_limited_process(*_args: object, **_kwargs: object) -> tuple[int, str, str, bool]:
            return 0, "ok", "", False

        setattr(runner, "_run_limited_process", fake_run_limited_process)
        result = cast(SandboxResult, _call_private(runner, "_execute_docker", "pwd", 60, None, "/tmp/proj/sub"))
        assert result.success


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS 전용")
class TestMacOSIsolation:
    @pytest.fixture(autouse=True)
    def _require_sandbox_exec(self):
        if not shutil.which("sandbox-exec"):
            pytest.skip("sandbox-exec 없음")

    def test_write_to_project_root_succeeds_with_network_none(self, tmp_path: Path):
        runner = SandboxRunner(project_root=str(tmp_path), enabled=True, network="none")
        result = runner.execute("echo hello > out.txt && cat out.txt")
        assert result.success, result.stderr
        assert "hello" in result.stdout
        assert (tmp_path / "out.txt").exists()

    def test_write_to_system_path_is_denied(self, tmp_path: Path):
        runner = SandboxRunner(project_root=str(tmp_path), enabled=True, network="none")
        result = runner.execute("touch /etc/agk_sandbox_probe 2>&1")
        assert not result.success
        assert not result.stdout.strip().endswith("0")

    def test_network_access_is_denied_when_network_none(self, tmp_path: Path):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = cast(tuple[str, int], cast(object, listener.getsockname()))[1]
        runner = SandboxRunner(project_root=str(tmp_path), enabled=True, network="none")
        result = runner.execute(
            f"python3 -c \"import socket; socket.create_connection(('127.0.0.1', {port}), timeout=2)\" 2>&1",
        )
        assert not result.success
        assert result.sandboxed
        listener.close()

    def test_network_all_allows_localhost_connection(self, tmp_path: Path):
        import threading

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = cast(tuple[str, int], cast(object, listener.getsockname()))[1]

        def accept_one():
            conn, _ = cast(tuple[socket.socket, object], cast(object, listener.accept()))
            conn.close()

        thread = threading.Thread(target=accept_one, daemon=True)
        thread.start()
        runner = SandboxRunner(project_root=str(tmp_path), enabled=True, network="all")
        result = runner.execute(
            f"python3 -c \"import socket; s=socket.create_connection(('127.0.0.1', {port}), timeout=3); s.close(); print('CONNECTED')\"",
        )
        thread.join(timeout=3)
        listener.close()
        assert result.success, result.stderr
        assert "CONNECTED" in result.stdout

    def test_read_from_project_root_succeeds(self, tmp_path: Path):
        _ = (tmp_path / "data.txt").write_text("sandbox_read_ok", encoding="utf-8")
        runner = SandboxRunner(project_root=str(tmp_path), enabled=True, network="none")
        result = runner.execute("cat data.txt")
        assert result.success
        assert "sandbox_read_ok" in result.stdout
