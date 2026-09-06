"""WS-02: file/shell/Git/search tools use canonical project root."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from antigravity_k.api.contracts.execution_context import RequestExecutionContext
from antigravity_k.api.project_binding import (
    reset_bound_request_execution_context,
    set_bound_request_execution_context,
)
from antigravity_k.tools.file_tools import GrepSearchTool, WriteFileTool
from antigravity_k.tools.git_tools import GitStatusTool
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.system_tools import ReadFileTool, RunBashCommandTool
from antigravity_k.tools.tool_contracts import Permission
from antigravity_k.tools.tool_path import (
    ToolPathError,
    disable_path_audit_capture,
    enable_path_audit_capture,
    get_path_audit_events,
    resolve_tool_path,
    rewrite_tool_args,
)
from antigravity_k.tools.tool_registry import ToolRegistry


def _bind_project(tmp_path: Path, name: str = "proj") -> Path:
    root = (tmp_path / name).resolve()
    root.mkdir(parents=True, exist_ok=True)
    ctx = RequestExecutionContext(
        request_id="req-ws02",
        task_id="task-ws02",
        project_id="proj-ws02",
        canonical_project_root=str(root),
        conversation_id="conv-ws02",
        conversation_revision=0,
        actor_subject="tester",
        session_id="sess-ws02",
        model_id="test-model",
    )
    set_bound_request_execution_context(ctx)
    return root


@pytest.fixture(autouse=True)
def _clear_binding():
    reset_bound_request_execution_context()
    disable_path_audit_capture()
    yield
    reset_bound_request_execution_context()
    disable_path_audit_capture()


def test_resolve_relative_joins_project_root_not_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = tmp_path / "server"
    project = tmp_path / "project"
    server.mkdir()
    project.mkdir()
    (server / "probe.txt").write_text("SERVER", encoding="utf-8")
    (project / "probe.txt").write_text("PROJECT", encoding="utf-8")
    monkeypatch.chdir(server)

    resolved = resolve_tool_path("probe.txt", str(project))
    assert resolved == str((project / "probe.txt").resolve())
    assert Path(resolved).read_text(encoding="utf-8") == "PROJECT"


def test_reject_dotdot_symlink_and_mixed_separator_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET", encoding="utf-8")
    (project / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ToolPathError):
        resolve_tool_path("../outside/secret.txt", str(project))

    with pytest.raises(ToolPathError):
        resolve_tool_path("link/secret.txt", str(project))

    with pytest.raises(ToolPathError):
        resolve_tool_path(r"..\outside\secret.txt", str(project))

    with pytest.raises(ToolPathError):
        resolve_tool_path(str(outside / "secret.txt"), str(project))


def test_permission_gate_inspected_path_matches_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = tmp_path / "server"
    project = tmp_path / "project"
    server.mkdir()
    project.mkdir()
    (project / "a.txt").write_text("ok", encoding="utf-8")
    monkeypatch.chdir(server)

    _bind_project(tmp_path, "project")
    gate = PermissionGate(project_root=str(server), mode="auto-pilot")
    resolved = gate.resolve_for_tool("a.txt")
    assert resolved == str((project / "a.txt").resolve())
    assert gate._check_path("a.txt", "read_file") == Permission.ALLOW
    assert gate._check_path("../secret", "read_file") == Permission.DENY
    assert gate._check_path(str(server / "x"), "write_file") == Permission.DENY


def test_registry_read_uses_project_not_server_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = tmp_path / "server"
    project = tmp_path / "project"
    server.mkdir()
    project.mkdir()
    (server / "probe.txt").write_text("SERVER_ROOT", encoding="utf-8")
    (project / "probe.txt").write_text("PROJECT_ROOT", encoding="utf-8")
    monkeypatch.chdir(server)

    root = _bind_project(tmp_path, "project")
    enable_path_audit_capture()
    registry = ToolRegistry(project_root=str(server))
    registry.install(ReadFileTool())

    perm, result = registry.execute_with_permission("read_file", {"file_path": "probe.txt"})
    assert perm == Permission.ALLOW
    assert "PROJECT_ROOT" in result
    assert "SERVER_ROOT" not in result

    events = get_path_audit_events()
    assert events
    assert all(e["inspected_path"] == e["executed_path"] for e in events)
    assert all(e["executed_path"].startswith(str(root)) for e in events)


def test_registry_write_and_search_under_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = tmp_path / "server"
    project = tmp_path / "project"
    server.mkdir()
    project.mkdir()
    monkeypatch.chdir(server)
    _bind_project(tmp_path, "project")

    registry = ToolRegistry(project_root=str(server))
    registry.install(WriteFileTool())
    registry.install(GrepSearchTool())

    perm, result = registry.execute_with_permission(
        "write_file",
        {"file_path": "notes.txt", "content": "canonical-marker"},
    )
    assert perm == Permission.ALLOW
    assert (project / "notes.txt").read_text(encoding="utf-8") == "canonical-marker"
    assert not (server / "notes.txt").exists()

    perm, grep_out = registry.execute_with_permission(
        "grep_search",
        {"query": "canonical-marker", "path": "."},
    )
    assert perm == Permission.ALLOW
    assert "canonical-marker" in grep_out


def test_shell_and_git_use_explicit_project_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = tmp_path / "server"
    project = tmp_path / "project"
    server.mkdir()
    project.mkdir()
    (server / "marker.txt").write_text("SERVER", encoding="utf-8")
    (project / "marker.txt").write_text("PROJECT", encoding="utf-8")
    monkeypatch.chdir(server)
    _bind_project(tmp_path, "project")

    # init git in project
    import subprocess

    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "ws02@test"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "ws02"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "add", "marker.txt"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project, check=True, capture_output=True)

    registry = ToolRegistry(project_root=str(server))
    bash = RunBashCommandTool()
    registry.install(bash)
    registry.install(GitStatusTool())

    perm, out = registry.execute_with_permission("run_bash_command", {"command": "pwd"})
    assert perm == Permission.ALLOW
    assert os.path.realpath(project) == os.path.realpath(out.splitlines()[0].strip()) or os.path.realpath(project) in {
        os.path.realpath(p) for p in out.replace("/private", "").split()
    }

    perm, out = registry.execute_with_permission("run_bash_command", {"command": "cat marker.txt"})
    assert perm == Permission.ALLOW
    assert "PROJECT" in out
    assert "SERVER" not in out

    perm, status = registry.execute_with_permission("git_status", {})
    assert perm == Permission.ALLOW
    assert "not a git repository" not in status.lower()


def test_rewrite_correlates_inspected_and_executed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "f.txt").write_text("x", encoding="utf-8")
    enable_path_audit_capture()
    rewritten, resolutions = rewrite_tool_args("read_file", {"file_path": "f.txt"}, str(project))
    assert resolutions
    assert resolutions[0].correlated
    assert rewritten["file_path"] == resolutions[0].executed_path
    events = get_path_audit_events()
    assert events[0]["inspected_path"] == events[0]["executed_path"]


def test_direct_read_without_registry_still_cwd_sensitive_documented(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct tool.execute bypasses registry rewrite; runtime must use registry (WS-02)."""
    server = tmp_path / "server"
    project = tmp_path / "project"
    server.mkdir()
    project.mkdir()
    (server / "probe.txt").write_text("SERVER", encoding="utf-8")
    (project / "probe.txt").write_text("PROJECT", encoding="utf-8")
    monkeypatch.chdir(server)
    # Without rewrite, ambient cwd wins — proving why registry rewrite is required.
    assert "SERVER" in ReadFileTool().execute(file_path="probe.txt")
