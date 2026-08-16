from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.system_tools import RunBashCommandTool
from antigravity_k.tools.tool_registry import ToolRegistry


def test_run_bash_tool_cannot_execute_directly():
    tool = RunBashCommandTool()

    result = tool.execute(command="echo should-not-run")

    assert result.startswith("[APPROVAL REQUIRED]")


def test_tool_registry_injects_execution_permit(monkeypatch, tmp_path):
    tool = RunBashCommandTool()
    monkeypatch.setattr(tool, "_run_with_sandbox", lambda command, env: "approved-output")
    registry = ToolRegistry(project_root=str(tmp_path))
    registry.install(tool)

    permission, result = registry.execute_with_permission(
        "run_bash_command",
        {"command": "echo approved"},
        objective="run a local verification command",
    )

    assert permission is Permission.ALLOW
    assert result == "approved-output"


def test_permission_gate_rejects_sibling_prefix_and_symlink_escape(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    sibling = tmp_path / "project-sibling"
    sibling.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = project_root / "linked.txt"
    link.symlink_to(outside)
    gate = PermissionGate(project_root=str(project_root), mode="auto-pilot")

    assert gate.check("write_file", {"path": str(sibling / "file.txt")}, risk_level="low") is Permission.DENY
    assert gate.check("write_file", {"path": str(link)}, risk_level="low") is Permission.DENY


def test_failed_command_surfaces_exit_code_so_model_can_detect_failure(monkeypatch, tmp_path):
    # Given: a command that exits non-zero with a specific message on stderr.
    tool = RunBashCommandTool()
    monkeypatch.setattr(tool, "_run_with_sandbox", lambda command, env: None)
    monkeypatch.setattr(tool, "_execution_permit", object(), raising=False)
    monkeypatch.setattr(
        "antigravity_k.tools.system_tools.get_provider_manager",
        lambda: type("M", (), {"get_provider_env": staticmethod(lambda: {})})(),
        raising=False,
    )

    # When: the tool runs a failing command through the subprocess fallback.
    result = tool.execute(
        command="python3 -c 'import sys; sys.stderr.write(\"boom\"); sys.exit(3)'",
        _execution_permit=tool._execution_permit,
    )

    # Then: the exit code is surfaced so the model can definitively detect failure and
    # trigger a correction — inferring failure only from stderr content is unreliable.
    assert "exit_code=3" in result
    assert "boom" in result


def test_successful_command_does_not_surface_exit_code_marker(monkeypatch, tmp_path):
    # Given: a command that succeeds (exit 0).
    tool = RunBashCommandTool()
    monkeypatch.setattr(tool, "_run_with_sandbox", lambda command, env: None)
    monkeypatch.setattr(tool, "_execution_permit", object(), raising=False)
    monkeypatch.setattr(
        "antigravity_k.tools.system_tools.get_provider_manager",
        lambda: type("M", (), {"get_provider_env": staticmethod(lambda: {})})(),
        raising=False,
    )

    # When: the tool runs a succeeding command.
    result = tool.execute(command="python3 -c 'print(42)'", _execution_permit=tool._execution_permit)

    # Then: success output is returned without a failure marker cluttering the context.
    assert "42" in result
    assert "exit_code" not in result
