from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.system_tools import RunBashCommandTool
from antigravity_k.tools.tool_contracts import Permission
from antigravity_k.tools.tool_registry import ToolRegistry


def _approved_output(_command: str, _env: Mapping[str, str]) -> str:
    return "approved-output"


def _no_sandbox(_command: str, _env: Mapping[str, str]) -> None:
    return None


class _ProviderManager:
    @staticmethod
    def get_provider_env() -> dict[str, str]:
        return {}


def _provider_manager() -> _ProviderManager:
    return _ProviderManager()


def _execution_permit(tool: RunBashCommandTool) -> object:
    return cast(object, getattr(tool, "_execution_permit"))


def test_run_bash_tool_cannot_execute_directly():
    tool = RunBashCommandTool()

    result = tool.execute(command="echo should-not-run")

    assert result.startswith("[APPROVAL REQUIRED]")


def test_tool_registry_injects_execution_permit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = RunBashCommandTool()
    monkeypatch.setattr(tool, "_run_with_sandbox", _approved_output)
    registry = ToolRegistry(project_root=str(tmp_path))
    install = cast(Callable[[object], ToolRegistry], getattr(registry, "install"))
    _ = install(tool)

    permission, result = registry.execute_with_permission(
        "run_bash_command",
        {"command": "echo approved"},
        objective="run a local verification command",
    )

    assert permission is Permission.ALLOW
    assert result == "approved-output"


def test_permission_gate_rejects_sibling_prefix_and_symlink_escape(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    sibling = tmp_path / "project-sibling"
    sibling.mkdir()
    outside = tmp_path / "outside.txt"
    _ = outside.write_text("secret", encoding="utf-8")
    link = project_root / "linked.txt"
    link.symlink_to(outside)
    gate = PermissionGate(project_root=str(project_root), mode="auto-pilot")

    assert gate.check("write_file", {"path": str(sibling / "file.txt")}, risk_level="low") is Permission.DENY
    assert gate.check("write_file", {"path": str(link)}, risk_level="low") is Permission.DENY


def test_failed_command_surfaces_exit_code_so_model_can_detect_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a command that exits non-zero with a specific message on stderr.
    tool = RunBashCommandTool()
    monkeypatch.setattr(tool, "_run_with_sandbox", _no_sandbox)
    monkeypatch.setattr(tool, "_execution_permit", object(), raising=False)
    monkeypatch.setattr(
        "antigravity_k.tools.system_tools.get_provider_manager",
        _provider_manager,
        raising=False,
    )

    # When: the tool runs a failing command through the subprocess fallback.
    result = tool.execute(
        command="python3 -c 'import sys; sys.stderr.write(\"boom\"); sys.exit(3)'",
        _execution_permit=_execution_permit(tool),
    )

    # Then: the exit code is surfaced so the model can definitively detect failure and
    # trigger a correction — inferring failure only from stderr content is unreliable.
    assert "exit_code=3" in result
    assert "boom" in result


def test_successful_command_does_not_surface_exit_code_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a command that succeeds (exit 0).
    tool = RunBashCommandTool()
    monkeypatch.setattr(tool, "_run_with_sandbox", _no_sandbox)
    monkeypatch.setattr(tool, "_execution_permit", object(), raising=False)
    monkeypatch.setattr(
        "antigravity_k.tools.system_tools.get_provider_manager",
        _provider_manager,
        raising=False,
    )

    # When: the tool runs a succeeding command.
    result = tool.execute(command="python3 -c 'print(42)'", _execution_permit=_execution_permit(tool))

    # Then: success output is returned without a failure marker cluttering the context.
    assert "42" in result
    assert "exit_code" not in result
