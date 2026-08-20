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
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import BinaryIO

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
    output_truncated: bool = False
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
        max_output_bytes: int = 1_000_000,
        max_memory_mb: int = 2_048,
        max_processes: int = 64,
    ):
        """Initialize the SandboxRunner.

        Args:
            project_root: 쓰기 허용할 프로젝트 루트 디렉토리
            enabled: 샌드박스 활성화 여부
            network: 네트워크 모드 (none/proxy/all)
            timeout: 기본 타임아웃 (초)

        """
        self.project_root: str = os.path.abspath(project_root)
        self.enabled: bool = enabled
        self.network: str = network
        self.timeout: int = timeout
        self.max_output_bytes: int = max(1, max_output_bytes)
        self.max_memory_mb: int = max(128, max_memory_mb)
        self.max_processes: int = max(1, max_processes)
        self._platform: str = platform.system()

    def execute(
        self,
        command: str,
        timeout: int | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
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
            return self._execute_raw(command, effective_timeout, env, cwd)

        # 플랫폼별 샌드박스
        if self._platform == "Darwin":
            return self._execute_macos_sandbox(command, effective_timeout, env, cwd)
        elif self._is_docker_available():
            return self._execute_docker(command, effective_timeout, env, cwd)
        else:
            logger.warning(
                "샌드박스를 사용할 수 없는 환경(%s) — 실행을 차단",
                self._platform,
            )
            return SandboxResult(
                success=False,
                return_code=-1,
                sandboxed=True,
                error=f"Sandbox is unavailable on {self._platform}; raw execution is disabled.",
            )

    def _execute_macos_sandbox(
        self,
        command: str,
        timeout: int,
        env: Mapping[str, str] | None,
        cwd: str | None,
    ) -> SandboxResult:
        """macOS sandbox-exec(seatbelt)로 명령을 격리 실행."""
        profile_path = None
        try:
            profile = self._build_seatbelt_profile()
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False, encoding="utf-8") as f:
                _ = f.write(profile)
                profile_path = f.name

            # sandbox-exec -f <profile> sh -c "<command>"
            # sh -c로 래핑하여 셸 메타문자와 파이프를 올바르게 처리
            sandbox_cmd = [
                "sandbox-exec",
                "-f",
                profile_path,
                "sh",
                "-c",
                self._limited_command(command, timeout),
            ]

            return_code, stdout, stderr, output_truncated = self._run_limited_process(
                sandbox_cmd,
                shell=False,
                timeout=timeout,
                env=env,
                cwd=cwd,
            )

            return SandboxResult(
                success=return_code == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                output_truncated=output_truncated,
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
            logger.warning("sandbox-exec를 찾을 수 없음 — 실행을 차단")
            return SandboxResult(
                success=False,
                return_code=-1,
                sandboxed=True,
                error="sandbox-exec is unavailable; raw execution is disabled.",
            )
        except (OSError, ValueError) as e:
            logger.warning("macOS 샌드박스 실행 실패: %s", e)
            return SandboxResult(
                success=False,
                return_code=-1,
                sandboxed=True,
                error=f"macOS sandbox execution failed: {e}",
            )
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

        # (deny default)가 네트워크도 포함해 전부 차단하므로, 허용 모드에서는
        # 명시적 allow가 없으면 실제로는 항상 차단된다
        network_policy = "(allow network*)\n;; network allowed" if allow_net else "(deny network*)\n;; network blocked"

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
        env: Mapping[str, str] | None,
        cwd: str | None,
    ) -> SandboxResult:
        """Docker 컨테이너 내부에서 명령을 실행합니다."""
        network_flag = "--network=none" if self.network == "none" else ""
        working_dir = "/workspace"
        if cwd:
            try:
                relative_cwd = os.path.relpath(cwd, self.project_root)
            except ValueError:
                relative_cwd = ".."
            if relative_cwd == ".." or relative_cwd.startswith(f"..{os.sep}"):
                return SandboxResult(
                    success=False,
                    return_code=-1,
                    sandboxed=True,
                    error="Working directory must remain inside the project root.",
                )
            if relative_cwd != ".":
                working_dir = f"/workspace/{relative_cwd.replace(os.sep, '/')}"
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            f"--memory={self.max_memory_mb}m",
            f"--memory-swap={self.max_memory_mb}m",
            f"--pids-limit={self.max_processes}",
            "-v",
            f"{self.project_root}:/workspace",
            "-w",
            working_dir,
        ]
        if network_flag:
            docker_cmd.append(network_flag)
        docker_cmd.extend(["python:3.12-slim", "sh", "-c", self._limited_command(command, timeout)])

        try:
            return_code, stdout, stderr, output_truncated = self._run_limited_process(
                docker_cmd,
                shell=False,
                timeout=timeout,
                env=env,
                cwd=None,
            )
            return SandboxResult(
                success=return_code == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                output_truncated=output_truncated,
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
            logger.warning("Docker를 찾을 수 없음 — 실행을 차단")
            return SandboxResult(
                success=False,
                return_code=-1,
                sandboxed=True,
                error="Docker is unavailable; raw execution is disabled.",
            )

    def _execute_raw(
        self,
        command: str,
        timeout: int,
        env: Mapping[str, str] | None,
        cwd: str | None,
    ) -> SandboxResult:
        """일반 subprocess 실행 (샌드박스 미적용 폴백)."""
        try:
            return_code, stdout, stderr, output_truncated = self._run_limited_process(
                self._limited_command(command, timeout),
                shell=True,
                timeout=timeout,
                env=env,
                cwd=cwd,
            )
            return SandboxResult(
                success=return_code == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                output_truncated=output_truncated,
                sandboxed=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                timed_out=True,
                error=f"명령 타임아웃 ({timeout}초)",
            )
        except (OSError, ValueError) as e:
            return SandboxResult(success=False, error=str(e))

    def _limited_command(self, command: str, timeout: int) -> str:
        return (
            f"ulimit -t {max(1, timeout)} 2>/dev/null; "
            f"ulimit -u {self.max_processes} 2>/dev/null; "
            f"ulimit -v {self.max_memory_mb * 1024} 2>/dev/null; "
            f"exec sh -c {self._shell_quote(command)}"
        )

    @staticmethod
    def _shell_quote(command: str) -> str:
        return "'" + command.replace("'", "'\\''") + "'"

    def _bounded_streams(self, stdout: str | None, stderr: str | None) -> tuple[str, str, bool]:
        bounded_stdout, stdout_truncated = self._bound_output(stdout or "")
        bounded_stderr, stderr_truncated = self._bound_output(stderr or "")
        return bounded_stdout, bounded_stderr, stdout_truncated or stderr_truncated

    def _bound_output(self, output: str) -> tuple[str, bool]:
        raw = output.encode("utf-8", errors="replace")
        if len(raw) <= self.max_output_bytes:
            return output, False
        bounded = raw[: self.max_output_bytes].decode("utf-8", errors="ignore")
        return bounded, True

    def _run_limited_process(
        self,
        args: list[str] | str,
        *,
        shell: bool,
        timeout: int,
        env: Mapping[str, str] | None,
        cwd: str | None,
    ) -> tuple[int, str, str, bool]:
        process = subprocess.Popen(
            args,
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=dict(env) if env is not None else os.environ.copy(),
            cwd=cwd or self.project_root,
        )
        stdout_buffer = bytearray()
        stderr_buffer = bytearray()
        truncated = [False, False]

        def drain(stream: BinaryIO | None, buffer: bytearray, index: int) -> None:
            if stream is None:
                return
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    return
                remaining = self.max_output_bytes - len(buffer)
                if remaining > 0:
                    buffer.extend(chunk[:remaining])
                if len(chunk) > max(remaining, 0):
                    truncated[index] = True

        threads = [
            threading.Thread(target=drain, args=(process.stdout, stdout_buffer, 0), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr_buffer, 1), daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        try:
            _ = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            _ = process.wait()
        finally:
            for thread in threads:
                thread.join(timeout=1)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        stdout = bytes(stdout_buffer).decode("utf-8", errors="replace")
        stderr = bytes(stderr_buffer).decode("utf-8", errors="replace")
        if timed_out:
            raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr)
        return process.returncode or 0, stdout, stderr, any(truncated)

    @staticmethod
    def _is_docker_available() -> bool:
        """Docker 사용 가능 여부."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
