"""SandboxRunner 단위 테스트 (작업 A).

seatbelt 프로파일 생성, 비활성 폴백, 타임아웃, Docker 감지를 검증합니다.
"""

import os
import platform
import shlex
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from antigravity_k.engine.sandbox import SandboxResult, SandboxRunner, run_sandboxed_argv


class TestSandboxResult:
    """SandboxResult 데이터클래스 검증."""

    def test_defaults(self):
        result = SandboxResult(success=True)
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.return_code == 0
        assert not result.timed_out
        assert not result.sandboxed

    def test_sandboxed_flag(self):
        result = SandboxResult(success=True, sandboxed=True)
        assert result.sandboxed


class TestSandboxDisabled:
    """샌드박스 비활성화 시 raw subprocess 폴백."""

    def test_disabled_uses_raw(self):
        runner = SandboxRunner(project_root="/tmp", enabled=False)
        result = runner.execute("echo test_disabled")
        assert result.success
        assert not result.sandboxed  # raw이므로 sandboxed=False
        assert "test_disabled" in result.stdout

    def test_disabled_returns_output(self):
        runner = SandboxRunner(project_root="/tmp", enabled=False)
        result = runner.execute("printf 'hello world'")
        assert "hello world" in result.stdout

    def test_output_quota_truncates_stdout(self):
        runner = SandboxRunner(project_root="/tmp", enabled=False, max_output_bytes=8)
        result = runner.execute("printf '1234567890'")
        assert result.output_truncated
        assert len(result.stdout.encode()) <= 8


class TestModelCodeBoundary:
    def test_forces_sandbox_and_network_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: dict[str, object] = {}

        class FakeRunner:
            def __init__(self, **kwargs: object) -> None:
                calls.update(kwargs)

            def execute(self, command: str, **kwargs: object) -> SandboxResult:
                calls["command"] = command
                calls["execute"] = kwargs
                return SandboxResult(success=True, sandboxed=True)

        monkeypatch.setattr("antigravity_k.engine.sandbox.SandboxRunner", FakeRunner)

        result = run_sandboxed_argv(["python3", "-c", "print(1)"], cwd=str(tmp_path), timeout=0.2)

        assert result.sandboxed is True
        assert calls["enabled"] is True
        assert calls["network"] == "none"
        execute_kwargs = cast(dict[str, object], calls["execute"])
        assert execute_kwargs["timeout"] == 1

    def test_empty_argv_fails_closed(self, tmp_path: Path) -> None:
        result = run_sandboxed_argv([], cwd=str(tmp_path), timeout=1)

        assert result.success is False
        assert result.sandboxed is True
        assert "non-empty argv" in result.error


class TestSeatbeltProfile:
    """macOS seatbelt 프로파일 생성 검증 (플랫폼 무관)."""

    def test_profile_contains_project_root(self):
        runner = SandboxRunner(project_root="/custom/project", enabled=True)
        build_profile = cast(Callable[[], str], getattr(runner, "_build_seatbelt_profile"))
        profile = build_profile()
        assert "/custom/project" in profile

    def test_profile_contains_network_policy(self):
        runner = SandboxRunner(project_root="/tmp", enabled=True, network="none")
        build_profile = cast(Callable[[], str], getattr(runner, "_build_seatbelt_profile"))
        profile = build_profile()
        # network none이면 차단 정책 포함
        assert "network" in profile.lower() or "deny" in profile.lower()

    def test_profile_allows_tmp(self):
        runner = SandboxRunner(project_root="/tmp/proj", enabled=True)
        build_profile = cast(Callable[[], str], getattr(runner, "_build_seatbelt_profile"))
        profile = build_profile()
        assert "/tmp" in profile

    def test_profile_allows_cache(self):
        runner = SandboxRunner(project_root="/tmp/proj", enabled=True)
        build_profile = cast(Callable[[], str], getattr(runner, "_build_seatbelt_profile"))
        profile = build_profile()
        assert ".cache" in profile


class TestTimeout:
    """타임아웃 동작 검증."""

    def test_timeout_returns_timed_out(self):
        runner = SandboxRunner(project_root="/tmp", enabled=False, timeout=1)
        result = runner.execute("sleep 10")
        assert result.timed_out
        assert not result.success

    def test_custom_timeout_override(self):
        runner = SandboxRunner(project_root="/tmp", enabled=False, timeout=60)
        result = runner.execute("sleep 10", timeout=1)
        assert result.timed_out

    @pytest.mark.skipif(os.name != "posix", reason="POSIX process-group behavior")
    def test_timeout_terminates_background_descendant(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "descendant.pid"
        child_code = (
            "import pathlib, subprocess, sys, time; "
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
            "pathlib.Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8'); "
            "time.sleep(60)"
        )
        command = " ".join(
            (
                shlex.quote(sys.executable),
                "-c",
                shlex.quote(child_code),
                shlex.quote(str(pid_file)),
            )
        )
        runner = SandboxRunner(
            project_root=str(tmp_path),
            enabled=False,
            timeout=1,
            max_processes=10_000,
        )

        try:
            result = runner.execute(command)
            assert result.timed_out
            descendant_pid = int(pid_file.read_text(encoding="utf-8"))
            with pytest.raises(ProcessLookupError):
                os.kill(descendant_pid, 0)
        finally:
            if pid_file.exists():
                descendant_pid = int(pid_file.read_text(encoding="utf-8"))
                try:
                    os.kill(descendant_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS 전용")
class TestMacOSSandboxExecution:
    """macOS sandbox-exec 실제 실행 (macOS에서만)."""

    def test_sandboxed_echo(self):
        import shutil

        if not shutil.which("sandbox-exec"):
            pytest.skip("sandbox-exec 없음")
        runner = SandboxRunner(project_root="/tmp", enabled=True, network="none")
        result = runner.execute("echo sandbox_ok")
        assert result.success
        assert result.sandboxed
        assert "sandbox_ok" in result.stdout


class TestDockerDetection:
    """Docker 가용성 감지."""

    def test_is_docker_available_returns_bool(self):
        is_docker_available = cast(Callable[[], bool], getattr(SandboxRunner, "_is_docker_available"))
        result = is_docker_available()
        assert isinstance(result, bool)


def test_enabled_sandbox_fails_closed_when_backend_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = SandboxRunner(project_root="/tmp", enabled=True)
    setattr(runner, "_platform", "Linux")
    monkeypatch.setattr(SandboxRunner, "_is_docker_available", staticmethod(lambda: False))

    result = runner.execute("echo should_not_run")

    assert not result.success
    assert result.sandboxed
    assert "raw execution is disabled" in result.error
