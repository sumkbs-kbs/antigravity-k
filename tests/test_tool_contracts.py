from __future__ import annotations

from typing import Any

from antigravity_k.tools.base_tool import BaseTool, RiskLevel, ToolCategory
from antigravity_k.tools.permission_gate import Permission
from antigravity_k.tools.tool_registry import ToolRegistry


class _WriteTool(BaseTool):
    category = ToolCategory.FILE_IO
    risk_level = RiskLevel.LOW

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write a project file."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    def execute(self, **kwargs: Any) -> str:
        return "written"


class _ShellTool(BaseTool):
    category = ToolCategory.CODE_EXEC
    risk_level = RiskLevel.HIGH

    @property
    def name(self) -> str:
        return "run_bash_command"

    @property
    def description(self) -> str:
        return "Run a shell command."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"command": {"type": "string"}}}

    def execute(self, **kwargs: Any) -> str:
        return "ran"


def test_registry_authorize_returns_spec_and_allow_decision_for_project_write(tmp_path) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    registry.install(_WriteTool())

    decision = registry.authorize("write_file", {"path": str(tmp_path / "note.txt")})

    assert decision.permission is Permission.ALLOW
    assert decision.spec.name == "write_file"
    assert decision.spec.risk_level == "low"


def test_registry_authorize_returns_permission_gate_denial_for_dangerous_shell_command(tmp_path) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    registry.install(_ShellTool())

    decision = registry.authorize("run_bash_command", {"command": "rm -rf /"})

    assert decision.permission is Permission.DENY
    assert decision.source == "permission_gate"


def test_registry_authorize_tool_evaluates_unregistered_descriptor(tmp_path) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    tool = _WriteTool()

    decision = registry.authorize_tool(tool, {"path": str(tmp_path / "note.txt")})

    assert decision.permission is Permission.ALLOW
    assert decision.spec.name == "write_file"
    assert registry.get("write_file") is None
