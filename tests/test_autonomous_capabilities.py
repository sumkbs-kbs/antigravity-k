from antigravity_k.engine.capability_policy import AutonomousCapabilityPolicy
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.tools.base_tool import BaseTool, RiskLevel, ToolCategory
from antigravity_k.tools.permission_gate import Permission
from antigravity_k.tools.tool_registry import ToolRegistry


class DummyTool(BaseTool):
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.CRITICAL

    @property
    def name(self):
        return "desktop_control"

    @property
    def description(self):
        return "Control the local desktop"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        return "controlled"


def test_capability_policy_prompts_for_critical_pc_control():
    policy = AutonomousCapabilityPolicy()
    decision = policy.decide_tool(DummyTool(), objective="화면을 직접 조작해서 테스트")

    assert decision.decision == "prompt"
    assert decision.risk_level == "critical"


def test_tool_registry_applies_autonomous_policy_before_execution():
    registry = ToolRegistry()
    registry.install(DummyTool())

    permission, result = registry.execute_with_permission("desktop_control", {}, objective="본 PC를 조작해서 테스트")

    assert permission == Permission.PROMPT
    assert "Critical PC capabilities" in result


def test_skill_loader_autonomously_activates_relevant_safe_skill(tmp_path):
    skill_dir = tmp_path / ".agent" / "skills" / "browser-qa"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: Browser QA
description: DOM browser testing and UI quality validation
tags: [browser, qa, dom]
risk_level: safe
trust_level: local
---
Use DOM inspection, screenshots, and browser self-test loops for UI QA.
""",
        encoding="utf-8",
    )

    loader = SkillLoader(project_root=str(tmp_path), include_global=False)
    activated = loader.auto_match("DOM 브라우저 테스트와 UI QA를 진행해줘")

    assert "browser-qa" in activated
    assert "browser-qa" in loader.active_skills


def test_skill_loader_does_not_auto_activate_critical_skill(tmp_path):
    skill_dir = tmp_path / ".agent" / "skills" / "system-reset"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: System Reset
description: reset, delete, and reconfigure the local system
tags: [system, reset]
risk_level: critical
trust_level: local
---
Reset system settings and delete generated files.
""",
        encoding="utf-8",
    )

    loader = SkillLoader(project_root=str(tmp_path), include_global=False)
    activated = loader.auto_match("system reset 작업을 진행해줘")

    assert "system-reset" not in activated
    assert loader.get_last_decisions()[0].decision == "prompt"


def test_capabilities_slash_command_reports_tool_and_skill_decisions(tmp_path):
    skill_dir = tmp_path / ".agent" / "skills" / "browser-qa"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: Browser QA
description: DOM browser testing
risk_level: safe
trust_level: local
---
Inspect DOM and test browser flows.
""",
        encoding="utf-8",
    )
    registry = ToolRegistry(project_root=str(tmp_path))
    registry.install(DummyTool())
    loader = SkillLoader(project_root=str(tmp_path), include_global=False)
    slash = SlashCommandRegistry(tool_registry=registry, skill_loader=loader)

    result = slash.execute("/capabilities DOM browser testing")

    assert "Autonomous Capability Manifest" in result
    assert "desktop_control" in result
    assert "browser-qa" in result
