"""
시스템 통합 업그레이드 테스트
================================
이전 세션(tiptap-vuetify 패턴)에서 만든 모듈들이
실제 핵심 시스템(AppConfig, TeamManager, BaseAgent, SkillsRegistry)에
올바르게 통합되었는지 검증합니다.

검증 대상:
  A) AppConfig — I18nConfig, max_tool_risk 추가
  B) TeamManager — ToolRegistry/I18n 자동 초기화
  C) BaseAgent — I18n 기반 다국어 추론 지시문
  D) SkillsRegistry — validate_skill_tools() 연동
  E) ComputerUseTool — 메타데이터 적용 확인
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from antigravity_k.config import AppConfig, I18nConfig
from antigravity_k.tools.base_tool import ToolCategory, RenderIn, RiskLevel
from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.i18n import I18n, set_locale


# ═══════════════ A) AppConfig 통합 테스트 ═══════════════


class TestAppConfigIntegration:
    """config.py에 I18nConfig와 max_tool_risk가 올바르게 통합되었는지 검증."""

    def test_i18n_config_exists(self):
        """AppConfig에 i18n 속성이 존재하는지 확인."""
        cfg = AppConfig()
        assert hasattr(cfg, "i18n")
        assert isinstance(cfg.i18n, I18nConfig)

    def test_i18n_config_defaults(self):
        """I18nConfig 기본값이 올바른지 확인."""
        cfg = AppConfig()
        assert cfg.i18n.locale == "auto"
        assert cfg.i18n.fallback_locale == "en"

    def test_max_tool_risk_exists(self):
        """SecurityConfig에 max_tool_risk가 추가되었는지 확인."""
        cfg = AppConfig()
        assert hasattr(cfg.security, "max_tool_risk")
        assert cfg.security.max_tool_risk == "high"

    def test_summary_includes_new_fields(self):
        """summary()에 새 필드들이 포함되는지 확인."""
        cfg = AppConfig()
        summary = cfg.summary()
        assert "도구 위험 한도" in summary
        assert "언어" in summary


# ═══════════════ B) TeamManager ToolRegistry 통합 테스트 ═══════════════


class TestTeamManagerToolRegistry:
    """TeamManager가 ToolRegistry와 I18n을 올바르게 초기화하는지 검증."""

    def test_tool_registry_exists(self):
        """TeamManager에 tool_registry 속성이 존재하는지 확인."""
        # 직접 import 대신 모듈 로드 테스트
        from antigravity_k.agents.team_manager import TeamManager

        tm = TeamManager(model_manager=None)
        assert hasattr(tm, "tool_registry")
        assert isinstance(tm.tool_registry, ToolRegistry)

    def test_system_tools_auto_registered(self):
        """시스템 도구들이 자동으로 등록되었는지 확인."""
        from antigravity_k.agents.team_manager import TeamManager

        tm = TeamManager(model_manager=None)
        assert "read_file" in tm.tool_registry
        assert "replace_file_content" in tm.tool_registry
        assert "run_bash_command" in tm.tool_registry

    def test_i18n_exists(self):
        """TeamManager에 i18n 인스턴스가 존재하는지 확인."""
        from antigravity_k.agents.team_manager import TeamManager

        tm = TeamManager(model_manager=None)
        assert hasattr(tm, "i18n")
        assert isinstance(tm.i18n, I18n)

    def test_get_tools_for_role(self):
        """역할 기반 도구 필터링이 동작하는지 확인."""
        from antigravity_k.agents.team_manager import TeamManager

        tm = TeamManager(model_manager=None)
        tools = tm.get_tools_for_role("WORKER")
        # max_tool_risk=high이므로 CRITICAL 도구는 제외
        for tool in tools:
            assert tool.risk_level != RiskLevel.CRITICAL

    def test_tool_registry_summary(self):
        """ToolRegistry 요약이 올바르게 생성되는지 확인."""
        from antigravity_k.agents.team_manager import TeamManager

        tm = TeamManager(model_manager=None)
        summary = tm.tool_registry.summary()
        assert "tools installed" in summary


# ═══════════════ C) BaseAgent I18n 통합 테스트 ═══════════════


class TestBaseAgentI18n:
    """BaseAgent의 시스템 프롬프트가 I18n에 따라 변하는지 검증."""

    def test_korean_reasoning_prompt(self):
        """한국어 로케일에서 한국어 추론 지시문이 포함되는지 확인."""
        from antigravity_k.agents.base_agent import BaseAgent

        set_locale("ko")
        agent = BaseAgent(
            name="TestAgent",
            role="TEST",
            system_prompt="테스트 에이전트입니다.",
            model_id="test",
        )
        prompt = agent._build_system_prompt()
        assert "한국어로 답변하세요" in prompt

    def test_english_reasoning_prompt(self):
        """영어 로케일에서 영어 추론 지시문이 포함되는지 확인."""
        from antigravity_k.agents.base_agent import BaseAgent

        set_locale("en")
        agent = BaseAgent(
            name="TestAgent",
            role="TEST",
            system_prompt="You are a test agent.",
            model_id="test",
        )
        prompt = agent._build_system_prompt()
        assert "highly capable agent" in prompt

    def test_japanese_reasoning_prompt(self):
        """일본어 로케일에서 일본어 추론 지시문이 포함되는지 확인."""
        from antigravity_k.agents.base_agent import BaseAgent

        set_locale("ja")
        agent = BaseAgent(
            name="TestAgent",
            role="TEST",
            system_prompt="テストエージェントです。",
            model_id="test",
        )
        prompt = agent._build_system_prompt()
        assert "日本語で回答してください" in prompt

    def test_fallback_reasoning_prompt(self):
        """지원되지 않는 로케일에서 영어로 폴백하는지 확인."""
        from antigravity_k.agents.base_agent import BaseAgent

        set_locale("fr")  # 프랑스어 → 폴백 → en
        agent = BaseAgent(
            name="TestAgent",
            role="TEST",
            system_prompt="Agent de test.",
            model_id="test",
        )
        prompt = agent._build_system_prompt()
        assert "highly capable agent" in prompt
        # 원복
        set_locale("ko")


# ═══════════════ D) SkillsRegistry 연동 테스트 ═══════════════


class TestSkillsRegistryIntegration:
    """SkillsRegistry가 ToolRegistry 검증 및 I18n을 사용하는지 검증."""

    def test_validate_skill_tools_finds_missing(self):
        """존재하지 않는 도구를 참조하는 스킬을 감지하는지 확인."""
        from antigravity_k.agents.skills_registry import SkillsRegistry, SkillProfile

        registry = SkillsRegistry.__new__(SkillsRegistry)
        registry.profiles = {}
        registry.skills_dir = None
        registry.scanner = None

        # 가짜 프로필 추가
        registry.profiles["TEST_SKILL"] = SkillProfile(
            name="TEST_SKILL",
            description="Test",
            system_prompt="Test",
            tools=["read_file", "nonexistent_tool", "another_fake"],
        )

        tool_reg = ToolRegistry()
        from antigravity_k.tools.system_tools import ReadFileTool

        tool_reg.install(ReadFileTool)

        missing = registry.validate_skill_tools(tool_reg)
        assert "TEST_SKILL" in missing
        assert "nonexistent_tool" in missing["TEST_SKILL"]
        assert "another_fake" in missing["TEST_SKILL"]

    def test_validate_skill_tools_no_missing(self):
        """모든 도구가 존재하면 빈 딕셔너리를 반환하는지 확인."""
        from antigravity_k.agents.skills_registry import SkillsRegistry, SkillProfile

        registry = SkillsRegistry.__new__(SkillsRegistry)
        registry.profiles = {}
        registry.skills_dir = None
        registry.scanner = None

        registry.profiles["VALID_SKILL"] = SkillProfile(
            name="VALID_SKILL",
            description="Valid",
            system_prompt="Valid",
            tools=["read_file"],
        )

        tool_reg = ToolRegistry()
        from antigravity_k.tools.system_tools import ReadFileTool

        tool_reg.install(ReadFileTool)

        missing = registry.validate_skill_tools(tool_reg)
        assert len(missing) == 0


# ═══════════════ E) ComputerUseTool 메타데이터 테스트 ═══════════════


class TestComputerUseMetadata:
    """ComputerUseTool에 tiptap-vuetify 메타데이터가 올바르게 적용되었는지 검증."""

    def test_metadata_fields(self):
        """ComputerUseTool의 메타데이터가 올바르게 설정되었는지 확인."""
        from antigravity_k.tools.computer_use import ComputerUseTool

        tool = ComputerUseTool(force_stub=True)

        assert tool.category == ToolCategory.COMPUTER_USE
        assert tool.render_in == RenderIn.CONTEXTUAL
        assert tool.risk_level == RiskLevel.CRITICAL
        assert tool.icon == "🖥️"
        assert "desktop" in tool.tags

    def test_metadata_dict(self):
        """to_metadata()가 올바른 딕셔너리를 반환하는지 확인."""
        from antigravity_k.tools.computer_use import ComputerUseTool

        tool = ComputerUseTool(force_stub=True)
        meta = tool.to_metadata()

        assert meta["category"] == "computer_use"
        assert meta["risk_level"] == "critical"


# ═══════════════ F) 위험도 기반 필터링 E2E 테스트 ═══════════════


class TestRiskBasedFiltering:
    """위험도 기반 도구 필터링이 end-to-end로 동작하는지 검증."""

    def test_critical_tools_filtered_out_by_default(self):
        """기본 설정(max_risk=high)에서 CRITICAL 도구가 제외되는지 확인."""
        reg = ToolRegistry()
        from antigravity_k.tools.system_tools import ReadFileTool, RunBashCommandTool
        from antigravity_k.tools.computer_use import ComputerUseTool

        reg.install_many(ReadFileTool, RunBashCommandTool)
        reg.install(ComputerUseTool, force_stub=True)

        safe_tools = reg.filter_by_risk(RiskLevel.HIGH)
        tool_names = [t.name for t in safe_tools]
        assert "read_file" in tool_names
        assert "run_bash_command" in tool_names
        assert "computer_use" not in tool_names  # CRITICAL → 제외

    def test_all_tools_with_critical_risk(self):
        """max_risk=critical이면 모든 도구가 포함되는지 확인."""
        reg = ToolRegistry()
        from antigravity_k.tools.system_tools import ReadFileTool
        from antigravity_k.tools.computer_use import ComputerUseTool

        reg.install_many(ReadFileTool)
        reg.install(ComputerUseTool, force_stub=True)

        all_tools = reg.filter_by_risk(RiskLevel.CRITICAL)
        assert len(all_tools) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
