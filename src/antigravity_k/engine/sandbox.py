"""Ssak-Ai: 명령 실행 샌드박스 (P2-1).

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
import math
import os
import platform
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from antigravity_k.engine.limited_process_runner import LimitedProcessRunner

logger = logging.getLogger("antigravity_k.sandbox")


def _user_tree_denied_root() -> str | None:
    """Return the directory whose subtree should be unreadable in restricted mode.

    On a multi-user layout this is the parent of HOME (e.g. ``/Users``) so other
    accounts are covered as well; otherwise HOME itself.
    """
    home = os.path.expanduser("~")
    if not home or home == "/":
        return None
    parent = os.path.dirname(home.rstrip("/"))
    if parent and parent not in ("", "/"):
        return parent
    return home


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


def run_sandboxed_argv(
    args: list[str],
    *,
    cwd: str,
    timeout: float,
    env: Mapping[str, str] | None = None,
    max_output_bytes: int = 1_000_000,
    extra_read_paths: Sequence[str] = (),
) -> SandboxResult:
    """Execute model-generated code through the mandatory OS sandbox.

    This boundary deliberately has no raw-process fallback. A verifier must fail
    closed when seatbelt/Docker is unavailable instead of executing generated code
    with the parent process privileges.

    Read access is restricted to the working directory, the Python interpreter
    runtime that must execute the code, explicit ``extra_read_paths`` and the
    system runtime locations in ``_RESTRICTED_SYSTEM_READ_PATHS``. The parent's
    ``os.environ`` is never inherited: ``env=None`` falls back to a minimal
    environment so caller secrets cannot leak into generated-code processes.
    """
    if not args:
        return SandboxResult(
            success=False,
            return_code=-1,
            sandboxed=True,
            error="Sandbox execution requires a non-empty argv.",
        )

    workspace = os.path.realpath(os.path.abspath(cwd))
    effective_timeout = max(1, math.ceil(timeout))
    read_paths = [workspace, *_python_runtime_read_paths(), *extra_read_paths]
    effective_env: dict[str, str] = dict(env) if env is not None else _minimal_child_env(workspace)
    runner = SandboxRunner(
        project_root=workspace,
        enabled=True,
        network="none",
        timeout=effective_timeout,
        max_output_bytes=max_output_bytes,
        restrict_reads=True,
        read_allow_paths=read_paths,
    )
    return runner.execute(
        shlex.join(args),
        timeout=effective_timeout,
        env=effective_env,
        cwd=workspace,
    )


def _python_runtime_read_paths() -> list[str]:
    """Return interpreter locations a sandboxed Python needs to boot.

    conda/venv interpreters live under the user HOME, so only these exact
    prefixes are allow-listed instead of the whole HOME directory.
    Seatbelt matches canonical (realpath) locations, and venv interpreters are
    frequently symlinks into a manager store (uv/conda), so both the symlink
    location and its resolved target tree must be allow-listed.
    """
    exe_real = os.path.realpath(os.path.abspath(sys.executable))
    paths = {
        sys.prefix,
        sys.base_prefix,
        os.path.realpath(sys.prefix),
        os.path.realpath(sys.base_prefix),
        os.path.dirname(os.path.abspath(sys.executable)),
        os.path.dirname(exe_real),
        os.path.dirname(os.path.dirname(exe_real)),
    }
    return sorted(p for p in paths if p)


def _minimal_child_env(workspace: str) -> dict[str, str]:
    """Default child environment when the caller does not supply one.

    No os.environ inheritance: only what a bare Python process needs. The
    interpreter's own bin directory stays first on PATH so callers that spawn
    ``python3``/``pytest`` by name keep resolving to the project environment.
    """
    home = os.path.join(workspace, ".sandbox-home")
    tmpdir = os.path.join(workspace, ".sandbox-tmp")
    os.makedirs(home, exist_ok=True)
    os.makedirs(tmpdir, exist_ok=True)
    interpreter_bin = os.path.dirname(os.path.abspath(sys.executable))
    return {
        "PATH": f"{interpreter_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": home,
        "TMPDIR": tmpdir,
        "PYTHONDONTWRITEBYTECODE": "1",
    }


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
        restrict_reads: bool = False,
        read_allow_paths: Sequence[str] = (),
    ):
        """Initialize the SandboxRunner.

        Args:
            project_root: 쓰기 허용할 프로젝트 루트 디렉토리
            enabled: 샌드박스 활성화 여부
            network: 네트워크 모드 (none/proxy/all)
            timeout: 기본 타임아웃 (초)
            restrict_reads: True면 읽기를 명시적 허용 경로로 제한한다.
                False(기본)는 기존 호출자 호환을 위해 전체 읽기를 허용한다.
            read_allow_paths: restrict_reads=True일 때 추가로 읽기를 허용할 경로.

        """
        self.project_root: str = os.path.realpath(os.path.abspath(project_root))
        self.enabled: bool = enabled
        self.network: str = network
        self.timeout: int = timeout
        self.max_output_bytes: int = max(1, max_output_bytes)
        self.max_memory_mb: int = max(128, max_memory_mb)
        self.max_processes: int = max(1, max_processes)
        self.restrict_reads: bool = restrict_reads
        self.read_allow_paths: tuple[str, ...] = tuple(
            os.path.realpath(os.path.abspath(p)) for p in read_allow_paths if p
        )
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
                self._limited_command(command, timeout, process_limit=self._macos_process_limit()),
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

    def build_seatbelt_profile(self) -> str:
        """Return the seatbelt profile used by long-lived sandbox clients."""
        return self._build_seatbelt_profile()

    def _build_seatbelt_profile(self) -> str:
        """macOS seatbelt 샌드박스 프로파일을 생성합니다.

        정책:
          - 프로젝트 디렉토리: 읽기/쓰기 허용
          - 시스템 경로(/usr, /bin, /lib): 읽기 전용
          - /tmp, /var/tmp: 읽기/쓰기 (빌드 산출물)
          - 네트워크: config에 따라 차단 또는 허용
          - fork/exec: 허용 (명령 실행 필요)
          - restrict_reads=True면 읽기를 시스템 런타임과 명시적 허용
            경로로 제한해 사용자 비밀 파일 접근을 차단한다.
        """
        root = self.project_root
        allow_net = self.network != "none"

        # (deny default)가 네트워크도 포함해 전부 차단하므로, 허용 모드에서는
        # 명시적 allow가 없으면 실상 항상 차단된다
        network_policy = "(allow network*)\n;; network allowed" if allow_net else "(deny network*)\n;; network blocked"

        if self.restrict_reads:
            # 실험적으로 검증된 macOS 26 동작: subpath 기반 좁은 read allow는
            # 인터프리터 로딩 단계에서 SIGABRT를 유발한다. 대신 전체 읽기 허용
            # 뒤에 사용자 트리/공유 임시 디렉토리 deny를 두고, 필요한 경로만
            # 다시 허용한다. seatbelt는 같은 구체성에서 나중에 오는 규칙을
            # 우선 적용하므로 deny 이후의 allow가 재허용으로 동작한다.
            denied_roots = []
            user_tree = _user_tree_denied_root()
            if user_tree:
                denied_roots.append(user_tree)
            # 다른 프로세스의 임시 파일(시크릿 포함 가능) 격리
            denied_roots.extend(["/tmp", "/private/tmp", "/var/tmp", "/private/var/tmp"])
            read_rules = ["(allow file-read*)"]
            for denied in denied_roots:
                read_rules.append(f'(deny file-read* (subpath "{denied}"))')
            # 재허용: 작업 디렉토리/런타임/호출자 지정 경로가 차단 트리
            # 안에 있더라도 정확히 그 prefix만 다시 연다.
            for p in dict.fromkeys([root, *self.read_allow_paths]):
                read_rules.append(f'(allow file-read* (literal "{p}"))')
                read_rules.append(f'(allow file-read* (subpath "{p}"))')
            read_section = "\n".join(read_rules)
            # restrict 모드: 쓰기도 root만. /tmp, /var/folders 전체 쓰기 허용 제거.
            write_section = f'(allow file-write* (subpath "{root}"))\n(allow file-write* (literal "/dev/null"))'
        else:
            read_section = "(allow file-read*)"
            cache_section = f'(allow file-write* (subpath "{os.path.expanduser("~/.cache")}"))'
            write_section = f""";; 프로젝트 디렉토리 쓰기 허용
(allow file-write* (subpath "{root}"))
;; 임시 디렉토리 (빌드 산출물)
(allow file-write* (subpath "/tmp"))
(allow file-write* (subpath "/var/tmp"))
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/private/var/folders"))
(allow file-write* (literal "/dev/null"))
;; 사용자 캐시 (pip, npm 등)
{cache_section}"""

        return f"""(version 1)
(deny default)
(allow process-fork)
(allow process-exec)
(allow signal (target self))
(allow sysctl-read)
{read_section}
{write_section}
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
                canonical_cwd = os.path.realpath(os.path.abspath(cwd))
                relative_cwd = os.path.relpath(canonical_cwd, self.project_root)
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

    def _macos_process_limit(self) -> int:
        try:
            result = subprocess.run(
                ["ps", "-u", str(os.getuid()), "-o", "pid="],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            current = len([line for line in result.stdout.splitlines() if line.strip()])
            return max(self.max_processes, current + self.max_processes)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return self.max_processes

    def _limited_command(self, command: str, timeout: int, process_limit: int | None = None) -> str:
        limit = process_limit or self.max_processes
        return (
            f"ulimit -t {max(1, timeout)} 2>/dev/null; "
            f"ulimit -u {limit} 2>/dev/null; "
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
        result = LimitedProcessRunner(self.max_output_bytes).run(
            args,
            shell=shell,
            timeout=timeout,
            env=env,
            cwd=cwd or self.project_root,
        )
        return result.return_code, result.stdout, result.stderr, result.output_truncated

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
