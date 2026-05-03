"""
Antigravity-K: 브라우저 자동화 도구 (Harness Engineering 적용)
=============================================================
Playwright 기반 브라우저 자동화 + Intent 기반 테스트 + Self-Healing.
에이전트가 브라우저를 열고, 클릭하고, 입력하고, 스크린샷을 찍고,
자연어 의도 기반으로 UI를 검증할 수 있습니다.
"""
import json
import logging
import base64
import time
from typing import Any, Dict, List, Optional

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger("antigravity_k.tools.browser")


class BrowserTool(BaseTool):
    """
    Playwright 기반 브라우저 자동화 도구.
    
    하네스 엔지니어링 적용:
    - Intent 기반 테스트: CSS 셀렉터 대신 자연어 의도로 요소 탐색
    - Self-Healing: 셀렉터 실패 시 Accessibility Tree 기반 자동 복구
    - 스크린샷 + DOM 스냅샷 자동 캡처
    """

    category = ToolCategory.WEB
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "🌐"
    tags = ["browser", "playwright", "web", "test", "automation"]

    def __init__(self):
        self.page = None
        self.browser = None
        self.playwright = None
        self.is_running = False

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "브라우저를 조작하여 웹 페이지를 탐색하고 테스트합니다. "
            "페이지 이동(goto), 클릭(click), 텍스트 입력(type), "
            "스크린샷(screenshot), DOM 읽기(read_dom), "
            "접근성 트리 분석(accessibility), 브라우저 종료(close)를 지원합니다."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["goto", "click", "type", "screenshot", "read_dom", 
                             "accessibility", "wait", "evaluate", "close"],
                    "description": "실행할 브라우저 액션"
                },
                "url": {
                    "type": "string",
                    "description": "goto 액션 시 이동할 URL"
                },
                "selector": {
                    "type": "string",
                    "description": "click/type 액션 시 대상 CSS 셀렉터"
                },
                "text": {
                    "type": "string",
                    "description": "type 액션 시 입력할 텍스트, click 시 텍스트로 요소 찾기"
                },
                "path": {
                    "type": "string",
                    "description": "screenshot 저장 경로"
                },
                "timeout": {
                    "type": "integer",
                    "description": "대기 시간(ms)",
                    "default": 5000
                },
                "script": {
                    "type": "string",
                    "description": "evaluate 액션 시 실행할 JavaScript 코드"
                }
            },
            "required": ["action"]
        }

    def execute(self, **kwargs) -> str:
        action = kwargs.get("action")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return (
                "오류: playwright가 설치되어 있지 않습니다.\n"
                "'pip install playwright && playwright install chromium'을 실행하세요."
            )

        if not self.is_running:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            self.is_running = True

        try:
            if action == "goto":
                return self._action_goto(kwargs)
            elif action == "click":
                return self._action_click(kwargs)
            elif action == "type":
                return self._action_type(kwargs)
            elif action == "screenshot":
                return self._action_screenshot(kwargs)
            elif action == "read_dom":
                return self._action_read_dom(kwargs)
            elif action == "accessibility":
                return self._action_accessibility(kwargs)
            elif action == "wait":
                return self._action_wait(kwargs)
            elif action == "evaluate":
                return self._action_evaluate(kwargs)
            elif action == "close":
                return self._action_close()
            else:
                return f"Unknown action: {action}"

        except Exception as e:
            logger.error(f"Browser action '{action}' failed: {e}")
            return f"Error: {str(e)}"

    def _action_goto(self, params: dict) -> str:
        url = params.get("url")
        timeout = params.get("timeout", 15000)
        self.page.goto(url, wait_until="networkidle", timeout=timeout)
        title = self.page.title()
        return f"Navigated to {url}. Title: {title}"

    def _action_click(self, params: dict) -> str:
        selector = params.get("selector")
        text = params.get("text")
        timeout = params.get("timeout", 5000)

        if text and not selector:
            # Intent 기반 클릭: 텍스트로 요소 찾기 (Self-Healing 패턴)
            el = self.page.get_by_text(text, exact=False)
            el.click(timeout=timeout)
            return f"Clicked element with text '{text}'"
        elif selector:
            # 기존 CSS 셀렉터 클릭
            try:
                self.page.click(selector, timeout=timeout)
                return f"Clicked on {selector}"
            except Exception:
                # Self-Healing: CSS 실패 시 텍스트 기반으로 폴백
                if text:
                    el = self.page.get_by_text(text, exact=False)
                    el.click(timeout=timeout)
                    return f"[Healed] CSS '{selector}' failed → clicked by text '{text}'"
                raise
        else:
            return "Error: selector 또는 text 중 하나를 지정해야 합니다"

    def _action_type(self, params: dict) -> str:
        selector = params.get("selector")
        text = params.get("text", "")
        timeout = params.get("timeout", 5000)
        
        if selector:
            self.page.fill(selector, text, timeout=timeout)
            return f"Typed '{text}' into {selector}"
        else:
            # 현재 포커스된 요소에 타이핑
            self.page.keyboard.type(text)
            return f"Typed '{text}' via keyboard"

    def _action_screenshot(self, params: dict) -> str:
        path = params.get("path", f"screenshot_{int(time.time())}.png")
        self.page.screenshot(path=path, full_page=True)
        return f"Screenshot saved to {path}"

    def _action_read_dom(self, params: dict) -> str:
        """현재 페이지의 주요 DOM 구조를 읽습니다 (에이전트가 이해하기 쉬운 형태)"""
        selector = params.get("selector", "body")
        
        # 주요 인터랙티브 요소만 추출
        result = self.page.evaluate(f"""() => {{
            const el = document.querySelector('{selector}');
            if (!el) return 'Element not found';
            
            const interactives = el.querySelectorAll(
                'button, input, textarea, select, a[href], [role="button"], [onclick]'
            );
            
            return Array.from(interactives).slice(0, 50).map(e => ({{
                tag: e.tagName.toLowerCase(),
                id: e.id || null,
                text: (e.textContent || '').trim().slice(0, 100),
                type: e.type || null,
                placeholder: e.placeholder || null,
                role: e.getAttribute('role') || null,
                ariaLabel: e.getAttribute('aria-label') || null,
            }}));
        }}""")
        
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _action_accessibility(self, params: dict) -> str:
        """Accessibility Tree 스냅샷 (하네스 엔지니어링 핵심)"""
        snapshot = self.page.accessibility.snapshot()
        if not snapshot:
            return "Accessibility snapshot unavailable"
        
        # 트리를 간결하게 포맷
        return self._format_a11y_tree(snapshot, max_depth=3)

    def _action_wait(self, params: dict) -> str:
        selector = params.get("selector")
        timeout = params.get("timeout", 5000)
        
        if selector:
            self.page.wait_for_selector(selector, timeout=timeout)
            return f"Element '{selector}' appeared"
        else:
            self.page.wait_for_timeout(timeout)
            return f"Waited {timeout}ms"

    def _action_evaluate(self, params: dict) -> str:
        script = params.get("script", "")
        result = self.page.evaluate(script)
        return json.dumps(result, ensure_ascii=False, default=str)

    def _action_close(self) -> str:
        if self.is_running:
            self.browser.close()
            self.playwright.stop()
            self.is_running = False
        return "Browser closed."

    def _format_a11y_tree(self, node: dict, depth: int = 0, max_depth: int = 3) -> str:
        """Accessibility Tree를 읽기 쉬운 텍스트로 포맷"""
        if depth > max_depth:
            return ""
        
        indent = "  " * depth
        role = node.get("role", "")
        name = node.get("name", "")
        
        line = f"{indent}[{role}]"
        if name:
            line += f' "{name}"'
        
        lines = [line]
        for child in node.get("children", []):
            child_text = self._format_a11y_tree(child, depth + 1, max_depth)
            if child_text:
                lines.append(child_text)
        
        return "\n".join(lines)
