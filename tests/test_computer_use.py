"""
Computer Use 통합 테스트
========================
ComputerUseTool, ActionGuard, OS Drivers, YAML Frontmatter 파싱을
종합적으로 검증합니다.
"""

import pytest
import sys
import os

# 프로젝트 src를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ─────────────────── OS Drivers 테스트 ───────────────────

class TestOSDrivers:
    """OS 드라이버 추상화 테스트 (Stub 모드)."""

    def test_get_driver_set_stub(self):
        """Stub 드라이버 셋을 정상적으로 생성할 수 있어야 합니다."""
        from antigravity_k.tools.os_drivers import get_driver_set
        ds = get_driver_set(force_stub=True)
        assert ds.mouse is not None
        assert ds.keyboard is not None
        assert ds.screen is not None

    def test_stub_mouse_move(self):
        """Stub 마우스 드라이버가 이동 명령을 기록해야 합니다."""
        from antigravity_k.tools.os_drivers import StubMouseDriver
        mouse = StubMouseDriver()
        mouse.move(100, 200)
        assert mouse.last_action == ("move", 100, 200)

    def test_stub_mouse_click(self):
        """Stub 마우스 드라이버가 클릭 명령을 기록해야 합니다."""
        from antigravity_k.tools.os_drivers import StubMouseDriver
        mouse = StubMouseDriver()
        mouse.click(50, 60, button="right")
        assert mouse.last_action == ("click", 50, 60, "right")

    def test_stub_keyboard_type(self):
        """Stub 키보드 드라이버가 타이핑을 기록해야 합니다."""
        from antigravity_k.tools.os_drivers import StubKeyboardDriver
        kb = StubKeyboardDriver()
        kb.type_text("Hello")
        assert kb.last_action == ("type", "Hello")

    def test_stub_keyboard_hotkey(self):
        """Stub 키보드 드라이버가 핫키 조합을 기록해야 합니다."""
        from antigravity_k.tools.os_drivers import StubKeyboardDriver
        kb = StubKeyboardDriver()
        kb.hotkey("ctrl", "c")
        assert kb.last_action == ("hotkey", ("ctrl", "c"))

    def test_stub_screenshot(self):
        """Stub 화면 드라이버가 base64 PNG를 반환해야 합니다."""
        from antigravity_k.tools.os_drivers import StubScreenDriver
        screen = StubScreenDriver()
        result = screen.screenshot()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_stub_screen_size(self):
        """Stub 화면 드라이버가 1920x1080을 반환해야 합니다."""
        from antigravity_k.tools.os_drivers import StubScreenDriver
        screen = StubScreenDriver()
        w, h = screen.get_screen_size()
        assert w == 1920
        assert h == 1080


# ─────────────────── ActionGuard 테스트 ───────────────────

class TestActionGuard:
    """Computer Use 보안 Guardrail 테스트."""

    def test_safe_action_allowed(self):
        """안전한 액션은 허용되어야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard()
        result = guard.validate_action("screenshot", {})
        assert result["allowed"] is True
        assert result["requires_hitl"] is False

    def test_blocked_action_denied(self):
        """차단 목록의 액션은 거부되어야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard()
        result = guard.validate_action("format_disk", {})
        assert result["allowed"] is False

    def test_unknown_action_denied(self):
        """알 수 없는 액션은 거부되어야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard()
        result = guard.validate_action("launch_missile", {})
        assert result["allowed"] is False

    def test_danger_zone_click_blocked(self):
        """작업 표시줄 영역 클릭은 차단되어야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard()
        # 작업 표시줄 영역 (y=1050, Windows 기준)
        result = guard.validate_action("left_click", {"x": 500, "y": 1050})
        assert result["allowed"] is False
        assert "DANGER ZONE" in result["reason"]

    def test_safe_click_allowed(self):
        """안전한 영역 클릭은 허용되어야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard()
        result = guard.validate_action("left_click", {"x": 500, "y": 500})
        assert result["allowed"] is True

    def test_hitl_required_action(self):
        """HITL 필요 액션은 requires_hitl=True를 반환해야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard(hitl_required=True)
        result = guard.validate_action("left_click_drag", {"x": 10, "y": 10})
        assert result["allowed"] is True
        assert result["requires_hitl"] is True

    def test_guard_disabled(self):
        """보안이 비활성화되면 모든 액션이 허용되어야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard(enabled=False)
        result = guard.validate_action("format_disk", {})
        assert result["allowed"] is True

    def test_audit_log(self):
        """감사 로그에 기록이 남아야 합니다."""
        from antigravity_k.security.computer_use_guard import ActionGuard
        guard = ActionGuard()
        guard.validate_action("screenshot", {})
        guard.validate_action("format_disk", {})
        log = guard.get_audit_log()
        assert len(log) == 2
        assert log[0]["allowed"] is True
        assert log[1]["allowed"] is False


# ─────────────────── ComputerUseTool 테스트 ───────────────

class TestComputerUseTool:
    """ComputerUseTool 통합 테스트 (Stub 모드)."""

    def _make_tool(self):
        from antigravity_k.tools.computer_use import ComputerUseTool
        return ComputerUseTool(force_stub=True)

    def test_tool_schema(self):
        """LLM 스키마가 올바르게 생성되어야 합니다."""
        tool = self._make_tool()
        schema = tool.to_tool_call_schema()
        assert schema["name"] == "computer_use"
        assert "input_schema" in schema
        assert "action" in schema["input_schema"]["properties"]

    def test_screenshot_action(self):
        """screenshot 액션이 base64 이미지를 반환해야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="screenshot")
        assert "image_base64" in result
        assert "screen_size" in result

    def test_mouse_move_action(self):
        """mouse_move 액션이 성공해야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="mouse_move", x=100, y=200)
        assert result["status"] == "ok"
        assert result["position"] == {"x": 100, "y": 200}

    def test_left_click_action(self):
        """left_click 액션이 성공해야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="left_click", x=300, y=400)
        assert result["status"] == "ok"

    def test_type_action(self):
        """type 액션이 텍스트 길이를 반환해야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="type", text="Hello World")
        assert result["status"] == "ok"
        assert result["text_length"] == 11

    def test_key_combo_action(self):
        """key 액션이 조합 키를 처리해야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="key", key_combo="ctrl+c")
        assert result["status"] == "ok"
        assert result["key_combo"] == "ctrl+c"

    def test_scroll_action(self):
        """scroll 액션이 성공해야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="scroll", x=500, y=500, direction="down", amount=5)
        assert result["status"] == "ok"
        assert result["amount"] == 5

    def test_blocked_action(self):
        """위험 영역 클릭이 차단되어야 합니다."""
        tool = self._make_tool()
        result = tool.execute(action="left_click", x=1800, y=1060)
        assert "error" in result

    def test_no_action(self):
        """액션이 없으면 에러를 반환해야 합니다."""
        tool = self._make_tool()
        result = tool.execute()
        assert "error" in result

    def test_callable_interface(self):
        """__call__ 인터페이스가 문자열을 반환해야 합니다."""
        tool = self._make_tool()
        result_str = tool(action="screenshot")
        assert isinstance(result_str, str)
        assert "image_base64" in result_str


# ────────────── YAML Frontmatter 파싱 테스트 ──────────────

class TestYAMLFrontmatter:
    """YAML frontmatter 파싱 테스트."""

    def test_parse_with_frontmatter(self):
        """frontmatter가 있는 파일을 올바르게 파싱해야 합니다."""
        from antigravity_k.agents.skills_registry import _parse_yaml_frontmatter
        content = """---
name: MY_SKILL
description: Test description
tools:
  - computer_use
  - read_file
---

# Body Content
This is the body.
"""
        result = _parse_yaml_frontmatter(content)
        assert result["name"] == "MY_SKILL"
        assert result["description"] == "Test description"
        assert result["tools"] == ["computer_use", "read_file"]
        assert "Body Content" in result["body"]

    def test_parse_without_frontmatter(self):
        """frontmatter가 없으면 전체를 body로 반환해야 합니다."""
        from antigravity_k.agents.skills_registry import _parse_yaml_frontmatter
        content = "# Just a regular markdown\nSome content."
        result = _parse_yaml_frontmatter(content)
        assert "body" in result
        assert "Just a regular markdown" in result["body"]

    def test_parse_simple_kv(self):
        """간단한 key: value만 있는 frontmatter를 파싱해야 합니다."""
        from antigravity_k.agents.skills_registry import _parse_yaml_frontmatter
        content = """---
name: SIMPLE
description: A simple skill
---

Body here.
"""
        result = _parse_yaml_frontmatter(content)
        assert result["name"] == "SIMPLE"
        assert result["description"] == "A simple skill"


# ─────────────── Config 테스트 ────────────────

class TestComputerUseConfig:
    """ComputerUseConfig 설정 테스트."""

    def test_config_exists(self):
        """AppConfig에 computer_use 필드가 존재해야 합니다."""
        from antigravity_k.config import AppConfig
        cfg = AppConfig()
        assert hasattr(cfg, "computer_use")
        assert cfg.computer_use.enabled is True
        assert cfg.computer_use.hitl_required is True

    def test_config_summary_includes_computer_use(self):
        """설정 요약에 Computer Use 상태가 표시되어야 합니다."""
        from antigravity_k.config import AppConfig
        cfg = AppConfig()
        summary = cfg.summary()
        assert "Computer Use" in summary


# ───────── SkillsRegistry 도구 바인딩 테스트 ─────────

class TestSkillsRegistryToolBinding:
    """SkillsRegistry의 도구 자동 바인딩 테스트."""

    def test_devops_has_computer_use(self):
        """DEVOPS 프로필에 computer_use 도구가 있어야 합니다."""
        from antigravity_k.agents.skills_registry import SkillsRegistry
        registry = SkillsRegistry()
        devops = registry.get_profile("DEVOPS")
        assert "computer_use" in devops.tools

    def test_dynamic_skill_tools_loaded(self):
        """동적 스킬의 tools 필드가 파싱되어야 합니다."""
        from antigravity_k.agents.skills_registry import SkillsRegistry
        registry = SkillsRegistry()
        os_ai = registry.get_profile("OS-AI-COMPUTER-USE")
        assert "computer_use" in os_ai.tools
