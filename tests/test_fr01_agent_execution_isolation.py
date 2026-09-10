"""FR-01 regression: user/model code must execute only inside the OS sandbox.

Covers the UnifiedAgent pytest path (single + consistency) and the shared
``run_sandboxed_argv`` boundary:

- normal code passes, failing tests surface as failure
- no host-process fallback; missing sandbox backend fails closed before exec
- external sentinel read/write denied (user tree and shared /tmp)
- parent environment secrets are not inherited
- network egress denied, timeout kills the process group, output quota holds

macOS-specific cases are skipped when seatbelt is not the active backend.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.sandbox import run_sandboxed_argv
from antigravity_k.engine.unified_agent import UnifiedAgent

IS_MACOS = sys.platform == "darwin"

_GOOD_CODE = "def add(a, b):\n    return a + b\n"
_GOOD_TEST = "from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
_BAD_CODE = "def add(a, b):\n    return a - b\n"


def _agent() -> UnifiedAgent:
    return UnifiedAgent(MagicMock(return_value="```python\n" + _GOOD_CODE + "\n```"), "dummy-model", headroom=False)


def _sandbox_env(work: str) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": work, "TMPDIR": work}


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    home = tmp_path / ".sandbox-home"
    tmp = tmp_path / ".sandbox-tmp"
    home.mkdir()
    tmp.mkdir()
    return tmp_path


class TestAgentTestSuiteExecution:
    """UnifiedAgent._run_test_suite must go through run_sandboxed_argv."""

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_passing_solution_passes(self, workdir: Path) -> None:
        (workdir / "solution.py").write_text(_GOOD_CODE, encoding="utf-8")
        (workdir / "test_solution.py").write_text(_GOOD_TEST, encoding="utf-8")
        passed, feedback = _agent()._run_test_suite(workdir)
        assert passed is True
        assert "1 passed" in feedback

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_failing_solution_reports_failure(self, workdir: Path) -> None:
        (workdir / "solution.py").write_text(_BAD_CODE, encoding="utf-8")
        (workdir / "test_solution.py").write_text(_GOOD_TEST, encoding="utf-8")
        passed, feedback = _agent()._run_test_suite(workdir)
        assert passed is False
        assert "assert" in feedback

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_parent_secrets_not_inherited(self, workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FAKE_SECRET_FR01", "leak-me-if-you-can")
        (workdir / "solution.py").write_text(_GOOD_CODE, encoding="utf-8")
        (workdir / "test_solution.py").write_text(
            "import os\n\n"
            "def test_leak():\n"
            "    with open('secret_check.txt', 'w') as f:\n"
            "        f.write(os.environ.get('FAKE_SECRET_FR01', 'CLEAN'))\n"
            "    assert False\n",
            encoding="utf-8",
        )
        _agent()._run_test_suite(workdir)
        leaked = workdir / "secret_check.txt"
        assert not leaked.exists() or leaked.read_text(encoding="utf-8") == "CLEAN"

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_backend_unavailable_fails_closed_without_execution(self, tmp_path: Path) -> None:
        work = tmp_path / "work"
        work.mkdir()
        marker = work / "must-not-run.txt"
        # Simulate an environment where the seatbelt backend cannot be found.
        result = run_sandboxed_argv(
            [
                sys.executable,
                "-B",
                "-c",
                f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')",
            ],
            cwd=str(work),
            timeout=10,
            env={"PATH": "/nonexistent-bin", "HOME": str(work), "TMPDIR": str(work)},
        )
        assert result.success is False
        assert result.sandboxed is True
        assert result.stdout == ""
        assert "sandbox-exec is unavailable" in result.error
        assert not marker.exists()

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_single_path_uses_sandbox_and_reports(self) -> None:
        agent = _agent()
        with patch.object(agent, "_graphify_context", return_value=""):
            outcome = agent._run_code("Write add", _GOOD_TEST, max_repairs=0)
        assert outcome.passed is True

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_consistency_path_uses_sandbox_and_reports(self) -> None:
        agent = _agent()
        with patch.object(agent, "_graphify_context", return_value=""):
            outcome = agent._run_code("Write add", _GOOD_TEST, max_repairs=0, consistency_samples=2)
        assert outcome.passed is True


class TestSandboxBoundary:
    """run_sandboxed_argv file/env/network/process containment."""

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_external_sentinel_read_denied(self, workdir: Path) -> None:
        # Sentinel must live inside the user tree (denied root), not under the
        # pytest temp tree (/private/var/folders), which is outside the deny set.
        outside_dir = Path(tempfile.mkdtemp(prefix="fr01_outside_", dir=os.path.expanduser("~")))
        outside = outside_dir / "secret.txt"
        outside.write_text("TOP-SECRET-SENTINEL", encoding="utf-8")
        try:
            code = (
                "import os\n"
                "try:\n"
                f"    open({str(outside)!r}).read()\n"
                "    print('READ_OK')\n"
                "except Exception as e:\n"
                "    print('READ_BLOCKED', type(e).__name__)\n"
            )
            (workdir / "probe.py").write_text(code, encoding="utf-8")
            res = run_sandboxed_argv(
                [sys.executable, "-B", "probe.py"],
                cwd=str(workdir),
                timeout=20,
                env=_sandbox_env(str(workdir)),
            )
            assert res.success is True
            assert "READ_BLOCKED" in res.stdout
        finally:
            import shutil

            shutil.rmtree(outside_dir, ignore_errors=True)

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_external_write_denied(self, workdir: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
        outside = tmp_path_factory.mktemp("fr01_outside_w")
        target = outside / "escape.txt"
        code = (
            "try:\n"
            f"    open({str(target)!r}, 'w').write('ESCAPED')\n"
            "    print('WRITE_OK')\n"
            "except Exception as e:\n"
            "    print('WRITE_BLOCKED', type(e).__name__)\n"
        )
        (workdir / "probe.py").write_text(code, encoding="utf-8")
        run_sandboxed_argv(
            [sys.executable, "-B", "probe.py"],
            cwd=str(workdir),
            timeout=20,
            env=_sandbox_env(str(workdir)),
        )
        assert not target.exists()

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_shared_tmp_access_denied(self, workdir: Path) -> None:
        sentinel = Path("/tmp") / f"fr01_sentinel_{os.getpid()}.txt"
        sentinel.write_text("shared-secret", encoding="utf-8")
        try:
            code = (
                "import os\n"
                "results = []\n"
                f"p = {str(sentinel)!r}\n"
                "try:\n"
                "    open(p).read(); results.append('READ_OK')\n"
                "except Exception:\n"
                "    results.append('READ_BLOCKED')\n"
                "try:\n"
                "    open(p, 'a').write('x'); results.append('WRITE_OK')\n"
                "except Exception:\n"
                "    results.append('WRITE_BLOCKED')\n"
                "print('PROBE', results)\n"
            )
            (workdir / "probe.py").write_text(code, encoding="utf-8")
            res = run_sandboxed_argv(
                [sys.executable, "-B", "probe.py"],
                cwd=str(workdir),
                timeout=20,
                env=_sandbox_env(str(workdir)),
            )
            assert res.success is True
            assert res.stdout.strip().endswith("['READ_BLOCKED', 'WRITE_BLOCKED']")
        finally:
            sentinel.unlink(missing_ok=True)

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_loopback_egress_denied(self, workdir: Path) -> None:
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        hits: list[int] = []

        def acceptor() -> None:
            try:
                conn, _ = srv.accept()
                hits.append(1)
                conn.close()
            except OSError:
                pass

        threading.Thread(target=acceptor, daemon=True).start()
        code = f"import socket\nsocket.create_connection(('127.0.0.1', {port}), timeout=3)\nprint('CONNECTED')\n"
        (workdir / "probe.py").write_text(code, encoding="utf-8")
        res = run_sandboxed_argv(
            [sys.executable, "-B", "probe.py"],
            cwd=str(workdir),
            timeout=20,
            env=_sandbox_env(str(workdir)),
        )
        time.sleep(0.3)
        assert res.success is False
        assert hits == []
        srv.close()

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_timeout_kills_process_group(self, workdir: Path) -> None:
        marker = "import time;time.sleep(60)"
        code = (
            "import subprocess, sys, time\n"
            f"subprocess.Popen([sys.executable, '-c', {marker!r}])\n"
            "print('started', flush=True)\n"
            "time.sleep(60)\n"
        )
        (workdir / "probe.py").write_text(code, encoding="utf-8")
        res = run_sandboxed_argv(
            [sys.executable, "-B", "probe.py"],
            cwd=str(workdir),
            timeout=4,
            env=_sandbox_env(str(workdir)),
        )
        assert res.timed_out is True
        assert res.success is False
        time.sleep(1)
        leftover = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True, check=False)
        assert leftover.stdout.strip() == ""

    def test_output_quota_truncates(self, workdir: Path) -> None:
        code = "print('A' * 100_000)\n"
        (workdir / "probe.py").write_text(code, encoding="utf-8")
        res = run_sandboxed_argv(
            [sys.executable, "-B", "probe.py"],
            cwd=str(workdir),
            timeout=20,
            env=_sandbox_env(str(workdir)),
            max_output_bytes=2048,
        )
        assert len(res.stdout.encode()) <= 2048
        assert res.output_truncated is True
