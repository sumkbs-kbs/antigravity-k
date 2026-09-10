"""FR-02 regression: shell path expansion must not bypass the project boundary.

Covers the lexical layer (``assert_shell_command_paths_in_root`` /
PermissionGate) and the executing OS-sandbox boundary:

- ``$HOME`` / ``${HOME}`` / quoted expansions are detected after expandvars
- command substitution and backticks are denied outright
- symlink / traversal / absolute / glob escapes keep external sentinels intact
- child interpreters (python) cannot open external files
- legitimate in-root writes (including spaces) keep working
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.terminal_tools import PersistentTerminalManager
from antigravity_k.tools.tool_path import (
    ToolPathError,
    assert_shell_command_paths_in_root,
)

IS_MACOS = sys.platform == "darwin"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "local.txt").write_text("inside", encoding="utf-8")
    (root / "space dir").mkdir()
    return root


@pytest.fixture()
def sentinel(tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("OUTSIDE-SENTINEL", encoding="utf-8")
    return target


class TestLexicalBoundary:
    """assert_shell_command_paths_in_root + PermissionGate deny paths."""

    @pytest.mark.parametrize(
        "command",
        [
            "cat $HOME/secret.txt",
            "cat ${HOME}/secret.txt",
            'cat "$HOME/secret.txt"',
            "cat '${HOME}/secret.txt'",
            "cat /etc/passwd",
            "cat ../outside/secret.txt",
            "cat ~/secret.txt",
        ],
    )
    def test_expansion_and_escape_tokens_denied(self, project: Path, command: str) -> None:
        with pytest.raises(ToolPathError):
            assert_shell_command_paths_in_root(command, str(project))

    @pytest.mark.parametrize(
        "command",
        [
            "cat $(echo ../outside/secret.txt)",
            "cat `echo ../outside/secret.txt`",
            "echo $(cat /etc/passwd)",
        ],
    )
    def test_command_substitution_denied(self, project: Path, command: str) -> None:
        with pytest.raises(ToolPathError):
            assert_shell_command_paths_in_root(command, str(project))

    @pytest.mark.parametrize(
        "command",
        [
            "echo PWNED >/tmp/secret.txt",
            "echo PWNED >>/tmp/secret.txt",
            "echo PWNED 2>/tmp/secret.txt",
            "echo PWNED >$HOME/secret.txt",
            "echo PWNED >${HOME}/secret.txt",
            "cat</tmp/secret.txt",
        ],
    )
    def test_attached_redirection_escape_tokens_denied(self, project: Path, command: str) -> None:
        with pytest.raises(ToolPathError):
            assert_shell_command_paths_in_root(command, str(project))

    @pytest.mark.parametrize(
        "command",
        [
            "cat local.txt",
            "echo hi > out.txt",
            "echo hi >out.txt",
            "cat 'space dir/../local.txt'",
        ],
    )
    def test_in_root_commands_allowed(self, project: Path, command: str) -> None:
        assert_shell_command_paths_in_root(command, str(project))

    def test_gate_denies_home_expansion(self, project: Path) -> None:
        gate = PermissionGate(project_root=str(project), mode="auto-pilot")
        assert gate.check("run_bash_command", {"command": "cat $HOME/secret.txt"}, risk_level="high") is Permission.DENY

    def test_gate_denies_persistent_command_escape(self, project: Path) -> None:
        gate = PermissionGate(project_root=str(project), mode="auto-pilot")
        assert (
            gate.check("run_persistent_command", {"command": "cat ${HOME}/secret.txt"}, risk_level="high")
            is Permission.DENY
        )

    def test_gate_allows_in_root_persistent_command(self, project: Path) -> None:
        gate = PermissionGate(project_root=str(project), mode="auto-pilot")
        assert (
            gate.check("run_persistent_command", {"command": "echo hi > out.txt"}, risk_level="high")
            is Permission.ALLOW
        )


class TestExecutionBoundary:
    """Real seatbelt execution must keep external sentinels intact."""

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_home_expansion_write_blocked_in_sandbox(
        self, project: Path, sentinel: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SENTINEL_TARGET", str(sentinel))
        before = _digest(sentinel)
        manager = PersistentTerminalManager()
        term_id = manager.create_terminal(
            f"echo PWNED > $SENTINEL_TARGET && echo done > {project / 'flag.txt'}",
            str(project),
        )
        process = manager.terminals[term_id]
        _ = process.wait(timeout=20)
        _ = manager.get_output(term_id)
        assert _digest(sentinel) == before
        # /tmp-family writes are denied as well; the project root write may or
        # may not have happened before the denial — the sentinel is the contract.
        assert sentinel.read_text(encoding="utf-8") == "OUTSIDE-SENTINEL"

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_symlink_escape_write_blocked(self, project: Path, sentinel: Path) -> None:
        link = project / "escape_link.txt"
        try:
            link.symlink_to(sentinel)
        except OSError:
            pytest.skip("symlink creation unavailable")
        before = _digest(sentinel)
        manager = PersistentTerminalManager()
        term_id = manager.create_terminal(f"echo PWNED > {link}", str(project))
        process = manager.terminals[term_id]
        _ = process.wait(timeout=20)
        _ = manager.get_output(term_id)
        # sandbox write boundary resolves real paths; symlinked target stays intact
        assert _digest(sentinel) == before

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_glob_write_outside_blocked(self, project: Path, sentinel: Path) -> None:
        before = _digest(sentinel)
        manager = PersistentTerminalManager()
        term_id = manager.create_terminal(f"echo PWNED > {sentinel.parent / '*.txt'}", str(project))
        process = manager.terminals[term_id]
        _ = process.wait(timeout=20)
        _ = manager.get_output(term_id)
        assert _digest(sentinel) == before

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_child_python_cannot_open_external_file(self, project: Path, sentinel: Path) -> None:
        before = _digest(sentinel)
        code = (
            f"import pathlib\n"
            f"try:\n"
            f"    pathlib.Path({str(sentinel)!r}).write_text('PWNED')\n"
            f"    print('CHILD_WROTE')\n"
            f"except Exception:\n"
            f"    print('CHILD_BLOCKED')\n"
        )
        script = project / "attack.py"
        script.write_text(code, encoding="utf-8")
        manager = PersistentTerminalManager()
        term_id = manager.create_terminal(f"{sys.executable} -B {script}", str(project))
        process = manager.terminals[term_id]
        _ = process.wait(timeout=30)
        output = manager.get_output(term_id)
        assert "CHILD_BLOCKED" in output
        assert _digest(sentinel) == before

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_normal_in_root_write_succeeds(self, project: Path) -> None:
        manager = PersistentTerminalManager()
        target = project / "space dir" / "out file.txt"
        term_id = manager.create_terminal(f"echo ok > '{target}'", str(project))
        process = manager.terminals[term_id]
        _ = process.wait(timeout=20)
        _ = manager.get_output(term_id)
        assert target.exists()
        assert target.read_text(encoding="utf-8").strip() == "ok"

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_absolute_outside_write_blocked(self, project: Path, sentinel: Path) -> None:
        before = _digest(sentinel)
        manager = PersistentTerminalManager()
        term_id = manager.create_terminal(f"echo PWNED > {sentinel}", str(project))
        process = manager.terminals[term_id]
        _ = process.wait(timeout=20)
        _ = manager.get_output(term_id)
        assert _digest(sentinel) == before


class TestRequestScopedRoot:
    """Permission root and executing profile root must agree."""

    @pytest.mark.skipif(not IS_MACOS, reason="seatbelt backend required")
    def test_terminal_profile_pins_request_root(self, project: Path, sentinel: Path) -> None:
        from antigravity_k.tools.terminal_tools import build_sandbox_argv

        wrapped = build_sandbox_argv("echo hi", project_root=str(project))
        assert wrapped is not None
        argv, profile_path = wrapped
        try:
            profile = profile_path.read_text(encoding="utf-8")
            assert os.path.realpath(str(project)) in profile
        finally:
            profile_path.unlink(missing_ok=True)
        assert argv[0] == "sandbox-exec"
