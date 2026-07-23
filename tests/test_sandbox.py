"""SandboxRunner 단위 테스트 (작업 A).

seatbelt 프로파일 생성, 비활성 폴백, 타임아웃, Docker 감지를 검증합니다.
"""

import platform

import pytest

from antigravity_k.engine.sandbox import SandboxResult, SandboxRunner


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


class TestSeatbeltProfile:
    """macOS seatbelt 프로파일 생성 검증 (플랫폼 무관)."""

    def test_profile_contains_project_root(self):
        runner = SandboxRunner(project_root="/custom/project", enabled=True)
        profile = runner._build_seatbelt_profile()
        assert "/custom/project" in profile

    def test_profile_contains_network_policy(self):
        runner = SandboxRunner(project_root="/tmp", enabled=True, network="none")
        profile = runner._build_seatbelt_profile()
        # network none이면 차단 정책 포함
        assert "network" in profile.lower() or "deny" in profile.lower()

    def test_profile_allows_tmp(self):
        runner = SandboxRunner(project_root="/tmp/proj", enabled=True)
        profile = runner._build_seatbelt_profile()
        assert "/tmp" in profile

    def test_profile_allows_cache(self):
        runner = SandboxRunner(project_root="/tmp/proj", enabled=True)
        profile = runner._build_seatbelt_profile()
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
        result = SandboxRunner._is_docker_available()
        assert isinstance(result, bool)
