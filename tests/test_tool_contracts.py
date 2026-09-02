from __future__ import annotations

from pathlib import Path
from typing import override

from antigravity_k.tools.base_tool import BaseTool, RiskLevel, ToolCategory
from antigravity_k.tools.tool_contracts import Permission
from antigravity_k.tools.tool_registry import ToolRegistry


class _WriteTool(BaseTool):
    category: ToolCategory = ToolCategory.FILE_IO
    risk_level: RiskLevel = RiskLevel.LOW

    @property
    @override
    def name(self) -> str:
        return "write_file"

    @property
    @override
    def description(self) -> str:
        return "Write a project file."

    @property
    @override
    def parameters_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    @override
    def execute(self, **kwargs: object) -> str:
        return "written"


class _ShellTool(BaseTool):
    category: ToolCategory = ToolCategory.CODE_EXEC
    risk_level: RiskLevel = RiskLevel.HIGH

    @property
    @override
    def name(self) -> str:
        return "run_bash_command"

    @property
    @override
    def description(self) -> str:
        return "Run a shell command."

    @property
    @override
    def parameters_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {"command": {"type": "string"}}}

    @override
    def execute(self, **kwargs: object) -> str:
        return "ran"


def test_registry_authorize_returns_spec_and_allow_decision_for_project_write(tmp_path: Path) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    _ = registry.install(_WriteTool())

    decision = registry.authorize("write_file", {"path": str(tmp_path / "note.txt")})

    assert decision.permission is Permission.ALLOW
    assert decision.spec.name == "write_file"
    assert decision.spec.risk_level == "low"


def test_registry_authorize_returns_permission_gate_denial_for_dangerous_shell_command(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    _ = registry.install(_ShellTool())

    decision = registry.authorize("run_bash_command", {"command": "rm -rf /"})

    assert decision.permission is Permission.DENY
    assert decision.source == "permission_gate"


def test_registry_authorize_tool_evaluates_unregistered_descriptor(tmp_path: Path) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    tool = _WriteTool()

    decision = registry.authorize_tool(tool, {"path": str(tmp_path / "note.txt")})

    assert decision.permission is Permission.ALLOW
    assert decision.spec.name == "write_file"
    assert registry.get("write_file") is None
