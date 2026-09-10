from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from antigravity_k.engine.sandbox import run_sandboxed_argv
from antigravity_k.engine.unified_agent import UnifiedAgent


def sandbox_env(workspace: Path) -> dict[str, str]:
    return {
        "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(workspace / ".sandbox-home"),
        "TMPDIR": str(workspace / ".sandbox-tmp"),
    }


def main() -> None:
    secret_name = "FAKE_SECRET_RP01_MANUAL"
    previous_secret = os.environ.get(secret_name)
    os.environ[secret_name] = "synthetic-only"
    agent = UnifiedAgent(
        MagicMock(return_value="```python\ndef add(a, b):\n    return a + b\n```"),
        "manual-qa-model",
        headroom=False,
    )
    test_code = (
        "import os\n\n"
        "from solution import add\n\n"
        "def test_real_sandbox_contract():\n"
        f"    assert os.environ.get({secret_name!r}) is None\n"
        "    assert add(20, 22) == 42\n"
    )
    try:
        with patch.object(agent, "_graphify_context", return_value=""):
            outcome = agent._run_code("Write add", test_code, max_repairs=0)
        assert outcome.passed is True

        with tempfile.TemporaryDirectory(prefix="rp01-user-sentinel-", dir=Path.home()) as external_dir:
            sentinel = Path(external_dir) / "secret.txt"
            sentinel.write_text("SYNTHETIC-SENTINEL", encoding="utf-8")
            with tempfile.TemporaryDirectory(prefix="rp01-work-") as workspace_name:
                workspace = Path(workspace_name)
                probe = workspace / "probe.py"
                probe.write_text(
                    "from pathlib import Path\n"
                    f"sentinel = Path({str(sentinel)!r})\n"
                    "try:\n"
                    "    sentinel.read_text()\n"
                    "    print('READ_OK')\n"
                    "except OSError:\n"
                    "    print('READ_BLOCKED')\n"
                    "try:\n"
                    "    sentinel.write_text('ESCAPED')\n"
                    "    print('WRITE_OK')\n"
                    "except OSError:\n"
                    "    print('WRITE_BLOCKED')\n",
                    encoding="utf-8",
                )
                probe_result = run_sandboxed_argv(
                    [sys.executable, "-B", "probe.py"],
                    cwd=str(workspace),
                    timeout=10,
                    env=sandbox_env(workspace),
                )
                assert probe_result.success is True
                assert "READ_BLOCKED" in probe_result.stdout
                assert "WRITE_BLOCKED" in probe_result.stdout
                assert sentinel.read_text(encoding="utf-8") == "SYNTHETIC-SENTINEL"

                listener = socket.socket()
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                hits: list[bool] = []

                def accept_once() -> None:
                    try:
                        connection, _ = listener.accept()
                    except OSError:
                        return
                    hits.append(True)
                    connection.close()

                thread = threading.Thread(target=accept_once, daemon=True)
                thread.start()
                port = listener.getsockname()[1]
                network_result = run_sandboxed_argv(
                    [
                        sys.executable,
                        "-B",
                        "-c",
                        f"import socket; socket.create_connection(('127.0.0.1', {port}), timeout=1)",
                    ],
                    cwd=str(workspace),
                    timeout=10,
                    env=sandbox_env(workspace),
                )
                listener.close()
                thread.join(timeout=1)
                assert network_result.success is False
                assert hits == []

                quota_result = run_sandboxed_argv(
                    [sys.executable, "-B", "-c", "print('Q' * 10000)"],
                    cwd=str(workspace),
                    timeout=10,
                    env=sandbox_env(workspace),
                    max_output_bytes=512,
                )
                assert quota_result.output_truncated is True
                assert len(quota_result.stdout.encode()) <= 512

        print("RESULT agent_normal_passed=True")
        print("RESULT parent_secret_absent=True")
        print("RESULT external_read_blocked=True")
        print("RESULT external_write_blocked=True")
        print("RESULT loopback_egress_blocked=True")
        print("RESULT output_quota_enforced=True")
        print("RESULT synthetic_sentinel_cleanup=True")
    finally:
        if previous_secret is None:
            os.environ.pop(secret_name, None)
        else:
            os.environ[secret_name] = previous_secret


if __name__ == "__main__":
    main()
