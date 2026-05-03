"""
tiptap-vuetify 패턴 기반 업그레이드 통합 테스트
=================================================
테스트 대상:
  A) BaseTool 메타데이터 (ToolCategory/RenderIn/RiskLevel)
  B) ToolRegistry 자동 등록 패턴 (install/filter)
  C) I18n 에이전트 다국어 시스템
"""

import pytest
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from antigravity_k.tools.base_tool import (
    BaseTool, ToolCategory, RenderIn, RiskLevel
)
from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.i18n import I18n, t, get_i18n, set_locale


# ─────────────────── Mock Tools ───────────────────

class MockReadTool(BaseTool):
    category = ToolCategory.FILE_IO
    render_in = RenderIn.TOOLBAR
    risk_level = RiskLevel.SAFE
    icon = "📄"
    tags = ["file", "read"]

    @property
    def name(self):
        return "mock_read"

    @property
    def description(self):
        return "Mock read tool"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        return "read result"


class MockWriteTool(BaseTool):
    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "✏️"
    tags = ["file", "write"]

    @property
    def name(self):
        return "mock_write"

    @property
    def description(self):
        return "Mock write tool"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        return "write result"


class MockExecTool(BaseTool):
    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "⚡"
    tags = ["exec", "dangerous"]

    @property
    def name(self):
        return "mock_exec"

    @property
    def description(self):
        return "Mock exec tool"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        return "exec result"


class MockSecurityTool(BaseTool):
    category = ToolCategory.SECURITY
    render_in = RenderIn.BACKGROUND
    risk_level = RiskLevel.SAFE
    icon = "🛡️"
    tags = ["security", "scan"]

    @property
    def name(self):
        return "mock_security"

    @property
    def description(self):
        return "Mock security scanner"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        return "scan passed"


# ═══════════════ A) BaseTool 메타데이터 테스트 ═══════════════

class TestBaseToolMetadata:
    """tiptap-vuetify AbstractExtension 패턴 적용 테스트."""

    def test_default_metadata(self):
        """기본 메타데이터 값이 올바르게 설정되는지 확인."""
        tool = MockReadTool()
        assert tool.category == ToolCategory.FILE_IO
        assert tool.render_in == RenderIn.TOOLBAR
        assert tool.risk_level == RiskLevel.SAFE
        assert tool.icon == "📄"
        assert "file" in tool.tags

    def test_to_metadata(self):
        """to_metadata()가 메타데이터를 올바르게 반환하는지 확인."""
        tool = MockExecTool()
        meta = tool.to_metadata()
        
        assert meta["name"] == "mock_exec"
        assert meta["category"] == "code_exec"
        assert meta["render_in"] == "contextual"
        assert meta["risk_level"] == "high"
        assert meta["icon"] == "⚡"
        assert "exec" in meta["tags"]

    def test_to_tool_call_schema(self):
        """LLM 스키마가 여전히 올바르게 동작하는지 확인."""
        tool = MockReadTool()
        schema = tool.to_tool_call_schema()
        
        assert schema["name"] == "mock_read"
        assert schema["description"] == "Mock read tool"
        assert "input_schema" in schema

    def test_tool_execution(self):
        """도구 실행이 여전히 정상 동작하는지 확인."""
        tool = MockReadTool()
        result = tool()
        assert result == "read result"

    def test_enum_values(self):
        """Enum 값들이 문자열로 직렬화 가능한지 확인."""
        assert ToolCategory.FILE_IO.value == "file_io"
        assert RenderIn.TOOLBAR.value == "toolbar"
        assert RiskLevel.CRITICAL.value == "critical"


# ═══════════════ B) ToolRegistry 테스트 ═══════════════

class TestToolRegistry:
    """tiptap-vuetify Plugin.install() 패턴 테스트."""

    def test_install_class(self):
        """클래스로 도구를 등록할 수 있는지 확인."""
        reg = ToolRegistry()
        reg.install(MockReadTool)
        assert "mock_read" in reg
        assert len(reg) == 1

    def test_install_instance(self):
        """인스턴스로 도구를 등록할 수 있는지 확인."""
        reg = ToolRegistry()
        reg.install(MockReadTool())
        assert "mock_read" in reg

    def test_install_many(self):
        """여러 도구를 한번에 등록할 수 있는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockWriteTool, MockExecTool)
        assert len(reg) == 3

    def test_install_chaining(self):
        """체이닝 패턴이 동작하는지 확인."""
        reg = ToolRegistry()
        reg.install(MockReadTool).install(MockWriteTool)
        assert len(reg) == 2

    def test_install_invalid(self):
        """잘못된 타입 등록 시 에러가 발생하는지 확인."""
        reg = ToolRegistry()
        with pytest.raises(TypeError):
            reg.install("not_a_tool")

    def test_get_tool(self):
        """이름으로 도구를 조회할 수 있는지 확인."""
        reg = ToolRegistry()
        reg.install(MockReadTool)
        tool = reg.get("mock_read")
        assert tool is not None
        assert tool.name == "mock_read"

    def test_get_nonexistent(self):
        """존재하지 않는 도구 조회 시 None 반환 확인."""
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_filter_by_category(self):
        """카테고리별 필터링이 동작하는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockWriteTool, MockExecTool, MockSecurityTool)
        
        file_tools = reg.filter_by_category(ToolCategory.FILE_IO)
        assert len(file_tools) == 2
        
        exec_tools = reg.filter_by_category(ToolCategory.CODE_EXEC)
        assert len(exec_tools) == 1

    def test_filter_by_risk(self):
        """위험도별 필터링이 동작하는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockWriteTool, MockExecTool, MockSecurityTool)
        
        safe_tools = reg.filter_by_risk(RiskLevel.SAFE)
        assert len(safe_tools) == 2  # MockRead + MockSecurity
        
        low_tools = reg.filter_by_risk(RiskLevel.LOW)
        assert len(low_tools) == 3  # SAFE + LOW

    def test_filter_by_render(self):
        """렌더 위치별 필터링이 동작하는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockWriteTool, MockExecTool, MockSecurityTool)
        
        toolbar_tools = reg.get_toolbar_tools()
        assert len(toolbar_tools) == 1
        assert toolbar_tools[0].name == "mock_read"
        
        bg_tools = reg.filter_by_render(RenderIn.BACKGROUND)
        assert len(bg_tools) == 1
        assert bg_tools[0].name == "mock_security"

    def test_to_llm_schemas(self):
        """LLM 스키마 목록 생성이 동작하는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockWriteTool)
        
        schemas = reg.to_llm_schemas()
        assert len(schemas) == 2
        assert all("name" in s and "input_schema" in s for s in schemas)

    def test_to_llm_schemas_filtered(self):
        """이름 기반 LLM 스키마 필터링이 동작하는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockWriteTool, MockExecTool)
        
        schemas = reg.to_llm_schemas(names=["mock_read"])
        assert len(schemas) == 1

    def test_to_metadata_list(self):
        """메타데이터 목록이 올바르게 생성되는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockExecTool)
        
        metas = reg.to_metadata_list()
        assert len(metas) == 2
        assert all("category" in m and "risk_level" in m for m in metas)

    def test_summary(self):
        """레지스트리 요약이 생성되는지 확인."""
        reg = ToolRegistry()
        reg.install_many(MockReadTool, MockExecTool)
        
        summary = reg.summary()
        assert "2 tools installed" in summary

    def test_overwrite_warning(self):
        """중복 등록 시 덮어쓰기가 되는지 확인."""
        reg = ToolRegistry()
        reg.install(MockReadTool)
        reg.install(MockReadTool)  # 중복 → 경고 후 덮어쓰기
        assert len(reg) == 1  # 여전히 1개


# ═══════════════ C) I18n 테스트 ═══════════════

class TestI18n:
    """tiptap-vuetify i18n 자동 언어 감지 패턴 테스트."""

    def test_default_locale(self):
        """기본 로케일이 설정되는지 확인."""
        i18n = I18n(locale_code="ko")
        assert i18n.locale == "ko"

    def test_translation_ko(self):
        """한국어 번역이 동작하는지 확인."""
        i18n = I18n(locale_code="ko")
        msg = i18n.t("agent.task_complete")
        assert msg == "작업이 완료되었습니다."

    def test_translation_en(self):
        """영어 번역이 동작하는지 확인."""
        i18n = I18n(locale_code="en")
        msg = i18n.t("agent.task_complete")
        assert msg == "Task completed successfully."

    def test_translation_ja(self):
        """일본어 번역이 동작하는지 확인."""
        i18n = I18n(locale_code="ja")
        msg = i18n.t("agent.task_complete")
        assert msg == "タスクが完了しました。"

    def test_translation_with_params(self):
        """매개변수가 포함된 번역이 동작하는지 확인."""
        i18n = I18n(locale_code="ko")
        msg = i18n.t("agent.greeting", agent_name="PM")
        assert "PM" in msg

    def test_fallback_to_english(self):
        """지원되지 않는 언어 시 영어로 폴백하는지 확인."""
        i18n = I18n(locale_code="zh")  # 중국어 미지원
        assert i18n.locale == "en"  # 폴백

    def test_missing_key_returns_key(self):
        """번역 키가 없으면 키 자체를 반환하는지 확인."""
        i18n = I18n(locale_code="ko")
        msg = i18n.t("nonexistent.key")
        assert msg == "nonexistent.key"

    def test_add_custom_translations(self):
        """동적 번역 추가가 동작하는지 확인."""
        i18n = I18n(locale_code="ko")
        i18n.add_translations("ko", {"custom.hello": "안녕!"})
        assert i18n.t("custom.hello") == "안녕!"

    def test_add_new_locale(self):
        """새로운 언어를 동적으로 추가할 수 있는지 확인."""
        i18n = I18n(locale_code="ko")
        i18n.add_translations("zh", {"agent.task_complete": "任务完成。"})
        assert "zh" in i18n.available_locales()

    def test_locale_change(self):
        """로케일 변경이 동작하는지 확인."""
        i18n = I18n(locale_code="ko")
        assert i18n.locale == "ko"
        
        i18n.locale = "en"
        assert i18n.locale == "en"
        assert i18n.t("agent.task_complete") == "Task completed successfully."

    def test_global_t_function(self):
        """글로벌 t() 함수가 동작하는지 확인."""
        set_locale("en")
        msg = t("agent.task_complete")
        assert msg == "Task completed successfully."
        
        # 원복
        set_locale("ko")

    def test_summary(self):
        """i18n 요약 정보가 생성되는지 확인."""
        i18n = I18n(locale_code="ko")
        summary = i18n.summary()
        assert summary["current_locale"] == "ko"
        assert "ko" in summary["available_locales"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
