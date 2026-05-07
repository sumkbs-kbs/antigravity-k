from antigravity_k.engine.codex_transfer import CodexTransferEngine
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.tools.tool_registry import ToolRegistry


def test_codex_transfer_manifest_contains_core_strengths():
    engine = CodexTransferEngine()
    report = engine.build(
        "제로 오류 정책으로 DOM 테스트와 출력 품질을 개선",
        connected_tools=45,
        known_skills=12,
    )

    rendered = engine.render_markdown(report)

    assert "Codex Capability Transfer Manifest" in rendered
    assert "Transfer Boundary" in rendered
    assert "Goal Contracting" in rendered
    assert "Evidence-First Exploration" in rendered
    assert "Autonomous Tool Judgment" in rendered
    assert "DOM-Grounded QA" in rendered
    assert "Zero-Error Completion" in rendered
    assert "Private model weights" in rendered
    assert "`45`" in rendered
    assert "`12`" in rendered


def test_codex_prompt_contract_is_concise_and_actionable():
    contract = CodexTransferEngine().render_prompt_contract()

    assert "Codex-Grade Operating Contract" in contract
    assert "Observe:" in contract
    assert "Verify:" in contract
    assert "Codex-Grade Completion Gates" in contract
    assert "console error or warning" in contract


def test_codex_slash_command_uses_connected_runtime(tmp_path):
    skill_dir = tmp_path / ".agent" / "skills" / "dom-qa"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: DOM QA
description: DOM testing and zero error browser validation
risk_level: safe
trust_level: local
---
Verify browser DOM, console logs, and command palette flows.
""",
        encoding="utf-8",
    )

    registry = ToolRegistry(project_root=str(tmp_path))
    registry.auto_discover("antigravity_k.tools")
    loader = SkillLoader(project_root=str(tmp_path), include_global=False)
    slash = SlashCommandRegistry(tool_registry=registry, skill_loader=loader)

    result = slash.execute("/codex DOM QA zero error upgrade")

    assert "Codex Capability Transfer Manifest" in result
    assert "Connected tools" in result
    assert "Known skills" in result
    assert "Zero-Error Completion Gates" in result
    assert "DOM-Grounded QA" in result
