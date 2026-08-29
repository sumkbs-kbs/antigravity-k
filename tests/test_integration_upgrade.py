"""시스템 통합 업그레이드 테스트.
================================
이전 세션(tiptap-vuetify 패턴)에서 만든 모듈들이
실제 핵심 시스템(AppConfig, BaseAgent, SkillsRegistry)에
올바르게 통합되었는지 검증합니다.

검증 대상:
  A) AppConfig — I18nConfig, max_tool_risk 추가
  C) BaseAgent — I18n 기반 다국어 추론 지시문
  D) SkillsRegistry — validate_skill_tools() 연동
  E) ComputerUseTool — 메타데이터 적용 확인
  (B) TeamManager 섹션은 모듈 삭제(2026-08-25 삭제 감사 A티어)로 제거됨
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from antigravity_k.config import AppConfig, I18nConfig
from antigravity_k.i18n import set_locale
from antigravity_k.tools.base_tool import RenderIn, RiskLevel, ToolCategory
from antigravity_k.tools.tool_registry import ToolRegistry

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

    def test_local_qwen_is_runtime_default(self, monkeypatch):
        for name in (
            "AGK_CONFIG_FILE",
            "AGK_PROVIDER",
            "AGK_API_ENGINE",
            "AGK_MODEL_API_ENGINE",
            "AGK_MAIN_MODEL",
        ):
            monkeypatch.delenv(name, raising=False)

        cfg = AppConfig()

        assert cfg.model.main_model == "qwen3.8"
        assert cfg.model.code_model == "qwen3.8"
        assert cfg.model.vision_model == "qwen3.8"
        assert cfg.model.api_engine == "ollama"
        assert cfg.model.api_base == "http://localhost:11434/v1"

    def test_lm_studio_engine_uses_its_token_environment_variable(self, monkeypatch):
        monkeypatch.setenv("AGK_PROVIDER", "lmstudio")
        monkeypatch.setenv("LM_STUDIO_API_KEY", "test-lmstudio-token")

        cfg = AppConfig()

        assert cfg.model.api_engine == "lmstudio"
        assert cfg.model.api_base == "http://localhost:1234/v1"
        assert cfg.model.api_key == "test-lmstudio-token"

    def test_max_tool_risk_exists(self):
        """SecurityConfig에 max_tool_risk가 추가되었는지 확인."""
        cfg = AppConfig()
        assert hasattr(cfg.security, "max_tool_risk")
        assert cfg.security.max_tool_risk == "high"

    def test_yaml_config_is_loaded(self, tmp_path, monkeypatch):
        """AppConfig가 config.yaml 값을 실제 런타임에 반영하는지 확인."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "security:\n  access_pin: '2468'\nserver:\n  port: 9812\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("AGK_CONFIG_FILE", str(config_file))
        monkeypatch.delenv("AGK_SEC_ACCESS_PIN", raising=False)
        monkeypatch.delenv("AGK_SERVER_PORT", raising=False)

        cfg = AppConfig()

        assert cfg.security.access_pin == "2468"
        assert cfg.server.port == 9812

    def test_environment_overrides_yaml_config(self, tmp_path, monkeypatch):
        """환경변수가 config.yaml보다 높은 우선순위를 갖는지 확인."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("security:\n  access_pin: '2468'\n", encoding="utf-8")
        monkeypatch.setenv("AGK_CONFIG_FILE", str(config_file))
        monkeypatch.setenv("AGK_SEC_ACCESS_PIN", "env-pin")

        cfg = AppConfig()

        assert cfg.security.access_pin == "env-pin"

    def test_summary_includes_new_fields(self):
        """summary()에 새 필드들이 포함되는지 확인."""
        cfg = AppConfig()
        summary = cfg.summary()
        assert "도구 위험 한도" in summary
        assert "언어" in summary


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
        assert "한국어로만 답변하세요" in prompt or "출력 품질 규약" in prompt

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
        from antigravity_k.agents.skills_registry import SkillProfile, SkillsRegistry

        registry = SkillsRegistry.__new__(SkillsRegistry)
        registry.profiles = {}
        setattr(registry, "skills_dir", None)
        setattr(registry, "scanner", None)

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
        from antigravity_k.agents.skills_registry import SkillProfile, SkillsRegistry

        registry = SkillsRegistry.__new__(SkillsRegistry)
        registry.profiles = {}
        setattr(registry, "skills_dir", None)
        setattr(registry, "scanner", None)

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
        from antigravity_k.tools.computer_use import ComputerUseTool
        from antigravity_k.tools.system_tools import ReadFileTool, RunBashCommandTool

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
        from antigravity_k.tools.computer_use import ComputerUseTool
        from antigravity_k.tools.system_tools import ReadFileTool

        reg.install_many(ReadFileTool)
        reg.install(ComputerUseTool, force_stub=True)

        all_tools = reg.filter_by_risk(RiskLevel.CRITICAL)
        assert len(all_tools) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
