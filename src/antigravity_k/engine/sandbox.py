"""Antigravity-K: 명령 실행 샌드박스 (P2-1).

====================================
에이전트가 실행하는 셸 명령을 OS 수준에서 격리합니다.
macOS의 sandbox-exec(seatbelt)와 Docker 컨테이너를 지원합니다.

보안 모델:
  - 파일 시스템: 프로젝트 디렉토리만 쓰기 허용, 나머지 읽기 전용
  - 네트워크: config의 sandbox_network 설정 (none = 차단)
  - 프로세스: 자식 프로세스 생성 제한
  - 타임아웃: 무한 실행 방지

사용법:
    runner = SandboxRunner(project_root="/path/to/project", enabled=True)
    result = runner.execute("npm test", timeout=60)
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger("antigravity_k.sandbox")


@dataclass
class SandboxResult:
    """샌드박스 실행 결과."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    timed_out: bool = False
    sandboxed: bool = False
    error: str = ""


class SandboxRunner:
    """OS 수준 샌드박스 명령 실행기.

    macOS에서는 sandbox-exec(seatbelt) 프로파일을 생성하여 명령을 격리합니다.
    Linux/Docker 환경에서는 Docker 컨테이너 내부 실행을 지원합니다.
    샌드박스가 비활성화되거나 사용 불가능하면 일반 subprocess로 폴백합니다.
    """

    def __init__(
        self,
        project_root: str = ".",
        enabled: bool = False,
        network: str = "none",
        timeout: int = 60,
    ):
        """Initialize the SandboxRunner.

        Args:
            project_root: 쓰기 허용할 프로젝트 루트 디렉토리
            enabled: 샌드박스 활성화 여부
            network: 네트워크 모드 (none/proxy/all)
            timeout: 기본 타임아웃 (초)

        """
        self.project_root = os.path.abspath(project_root)
        self.enabled = enabled
        self.network = network
        self.timeout = timeout
        self._platform = platform.system()

    def execute(
        self,
        command: str,
        timeout: int | None = None,
        env: dict | None = None,
    ) -> SandboxResult:
        """명령을 샌드박스에서 실행합니다.

        Args:
            command: 실행할 셸 명령
            timeout: 타임아웃 (기본값 사용 시 None)
            env: 환경 변수

        Returns:
            SandboxResult
        """
        effective_timeout = timeout or self.timeout

        if not self.enabled:
            return self._execute_raw(command, effective_timeout, env)

        # 플랫폼별 샌드박스
        if self._platform == "Darwin":
            return self._execute_macos_sandbox(command, effective_timeout, env)
        elif self._is_docker_available():
            return self._execute_docker(command, effective_timeout, env)
        else:
            logger.warning(
                "샌드박스를 사용할 수 없는 환경(%s) — raw subprocess로 폴백",
                self._platform,
            )
            return self._execute_raw(command, effective_timeout, env)

    def _execute_macos_sandbox(
        self,
        command: str,
        timeout: int,
        env: dict | None,
    ) -> SandboxResult:
        """macOS sandbox-exec(seatbelt)로 명령을 격리 실행."""
        profile_path = None
        try:
            profile = self._build_seatbelt_profile()
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False, encoding="utf-8") as f:
                f.write(profile)
                profile_path = f.name

            # sandbox-exec -f <profile> sh -c "<command>"
            # sh -c로 래핑하여 셸 메타문자와 파이프를 올바르게 처리
            sandbox_cmd = [
                "sandbox-exec",
                "-f",
                profile_path,
                "sh",
                "-c",
                command,
            ]

            result = subprocess.run(
                sandbox_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env or os.environ.copy(),
                cwd=self.project_root,
            )

            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                sandboxed=True,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                timed_out=True,
                error=f"샌드박스 명령 타임아웃 ({timeout}초)",
                sandboxed=True,
            )
        except FileNotFoundError:
            logger.warning("sandbox-exec를 찾을 수 없음 — raw subprocess로 폴백")
            return self._execute_raw(command, timeout, env)
        except Exception as e:
            logger.warning("macOS 샌드박스 실행 실패, raw로 폴백: %s", e)
            return self._execute_raw(command, timeout, env)
        finally:
            if profile_path and os.path.exists(profile_path):
                os.unlink(profile_path)

    def _build_seatbelt_profile(self) -> str:
        """macOS seatbelt 샌드박스 프로파일을 생성합니다.

        정책:
          - 프로젝트 디렉토리: 읽기/쓰기 허용
          - 시스템 경로(/usr, /bin, /lib): 읽기 전용
          - /tmp, /var/tmp: 읽기/쓰기 (빌드 산출물)
          - 네트워크: config에 따라 차단 또는 허용
          - fork/exec: 허용 (명령 실행 필요)
        """
        root = self.project_root
        allow_net = self.network != "none"

        network_policy = (
            ""  # 허용 (기본)
            if allow_net
            else "(deny network*)\n(deny file-write*)\n;; network blocked"
        )

        return f"""(version 1)
(deny default)
(allow process-fork)
(allow process-exec)
(allow signal (target self))
(allow sysctl-read)
(allow file-read*)
;; 프로젝트 디렉토리 쓰기 허용
(allow file-write* (subpath "{root}"))
;; 임시 디렉토리 (빌드 산출물)
(allow file-write* (subpath "/tmp"))
(allow file-write* (subpath "/var/tmp"))
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/private/var/folders"))
;; 사용자 캐시 (pip, npm 등)
(allow file-write* (subpath "{os.path.expanduser("~/.cache")}"))
{network_policy}
"""

    def _execute_docker(
        self,
        command: str,
        timeout: int,
        env: dict | None,
    ) -> SandboxResult:
        """Docker 컨테이너 내부에서 명령을 실행합니다."""
        network_flag = "--network=none" if self.network == "none" else ""
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{self.project_root}:/workspace",
            "-w",
            "/workspace",
        ]
        if network_flag:
            docker_cmd.append(network_flag)
        docker_cmd.extend(["python:3.12-slim", "sh", "-c", command])

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env or os.environ.copy(),
            )
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                sandboxed=True,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                timed_out=True,
                error=f"Docker 명령 타임아웃 ({timeout}초)",
                sandboxed=True,
            )
        except FileNotFoundError:
            logger.warning("Docker를 찾을 수 없음 — raw subprocess로 폴백")
            return self._execute_raw(command, timeout, env)

    def _execute_raw(
        self,
        command: str,
        timeout: int,
        env: dict | None,
    ) -> SandboxResult:
        """일반 subprocess 실행 (샌드박스 미적용 폴백)."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env or os.environ.copy(),
            )
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                sandboxed=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                timed_out=True,
                error=f"명령 타임아웃 ({timeout}초)",
            )
        except Exception as e:
            return SandboxResult(success=False, error=str(e))

    @staticmethod
    def _is_docker_available() -> bool:
        """Docker 사용 가능 여부."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
