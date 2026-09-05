from __future__ import annotations

from pathlib import Path
from typing import Callable, cast, override

from antigravity_k.engine.self_capability import (
    SelfCapabilityEngine,
    is_self_capability_request,
)
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.tools.base_tool import BaseTool, RiskLevel, ToolCategory
from antigravity_k.tools.tool_registry import ToolRegistry


def _install(registry: ToolRegistry, tool: BaseTool) -> None:
    installer = cast(Callable[[object], ToolRegistry], getattr(registry, "install"))
    _ = installer(tool)


class DummyWriteTool(BaseTool):
    category: ToolCategory = ToolCategory.FILE_IO
    risk_level: RiskLevel = RiskLevel.LOW

    @property
    @override
    def name(self) -> str:
        return "write_file"

    @property
    @override
    def description(self) -> str:
        return "Write a file in the current project"

    @property
    @override
    def parameters_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @override
    def execute(self, **_kwargs: object) -> str:
        return "ok"


class DummyDomTool(BaseTool):
    category: ToolCategory = ToolCategory.WEB
    risk_level: RiskLevel = RiskLevel.SAFE

    @property
    @override
    def name(self) -> str:
        return "fetch_dom"

    @property
    @override
    def description(self) -> str:
        return "Inspect browser DOM for QA"

    @property
    @override
    def parameters_schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @override
    def execute(self, **_kwargs: object) -> str:
        return "ok"


def test_self_capability_request_detection():
    assert is_self_capability_request("너를 소개하고 니가 할 수 있는 일을 알려줘")
    assert is_self_capability_request("what can you do?")
    assert not is_self_capability_request("GCD 함수를 작성해줘")
    assert not is_self_capability_request("/capabilities DOM browser testing")
    assert not is_self_capability_request("/goal DOM 기능을 테스트해줘")


def test_self_capability_report_uses_runtime_tools_and_skills(tmp_path: Path) -> None:
    skill_dir = tmp_path / ".agent" / "skills" / "browser-qa"
    skill_dir.mkdir(parents=True)
    _ = (skill_dir / "SKILL.md").write_text(
        """---
name: Browser QA
description: DOM browser testing
risk_level: safe
trust_level: local
---
Inspect DOM and console state.
""",
        encoding="utf-8",
    )
    registry = ToolRegistry(project_root=str(tmp_path))
    _install(registry, DummyWriteTool())
    _install(registry, DummyDomTool())
    loader = SkillLoader(project_root=str(tmp_path), include_global=False)

    snapshot = SelfCapabilityEngine().build(
        tool_registry=registry,
        skill_loader=loader,
        project_root=str(tmp_path),
        slash_commands=["self", "capabilities"],
    )
    rendered = SelfCapabilityEngine().render_markdown(snapshot)

    assert "등록 도구: `2`개" in rendered
    assert "등록 Skills: `1`개" in rendered
    assert "`fetch_dom`" in rendered
    assert "`write_file`" in rendered
    assert "`browser-qa`" in rendered
    assert "WiFi" not in rendered
    assert "볼륨" not in rendered


def test_self_slash_command_reports_runtime_capabilities(tmp_path: Path) -> None:
    registry = ToolRegistry(project_root=str(tmp_path))
    _install(registry, DummyDomTool())
    loader = SkillLoader(project_root=str(tmp_path), include_global=False)
    slash = SlashCommandRegistry(tool_registry=registry, skill_loader=loader)

    result = slash.execute("/self")

    assert "Ssak-Ai Self Capability Report" in result
    assert "등록 도구: `1`개" in result
    assert "`fetch_dom`" in result
    assert "/capabilities <목표>" in result
