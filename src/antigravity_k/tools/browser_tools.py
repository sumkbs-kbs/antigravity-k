"""
BrowserTools — DOM 파싱 및 브라우저 검증 도구
==============================================
SPA(React, Vue 등)의 동적 렌더링 요소를 에이전트가 직접 파싱할 수 있도록 지원.

포함 도구:
- FetchDOMTool: Playwright를 사용하여 URL에 접속하고 렌더링된 후의 DOM 텍스트를 반환합니다.
"""

import asyncio
import logging
from typing import Any, Dict

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)

# ─── 전역 브라우저 세션 (Stateful) ───
_playwright = None
_browser = None
_page = None

def get_browser_page():
    """싱글톤 패턴으로 브라우저 페이지를 유지합니다."""
    global _playwright, _browser, _page
    if _page is None or _page.is_closed():
        try:
            from playwright.sync_api import sync_playwright
            if _playwright is None:
                _playwright = sync_playwright().start()
            if _browser is None or not _browser.is_connected():
                # Headless=False 로 설정하여 사용자 화면에 보이도록 함
                _browser = _playwright.chromium.launch(headless=False)
            _page = _browser.new_page()
        except ImportError:
            raise ImportError("Playwright is not installed. Run: pip install playwright && playwright install chromium")
    return _page

def close_browser():
    """브라우저 세션을 명시적으로 닫습니다."""
    global _playwright, _browser, _page
    if _page:
        try: _page.close()
        except: pass
        _page = None
    if _browser:
        try: _browser.close()
        except: pass
        _browser = None
    if _playwright:
        try: _playwright.stop()
        except: pass
        _playwright = None


class BrowserDOMTool(BaseTool):
    """
    Stateful 브라우저 세션을 관리하며 자바스크립트 기반 웹 페이지와 상호작용합니다.
    """
    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🌐"
    tags = ["browser", "stateful", "qa", "test", "interact"]

    def __init__(self):
        super().__init__()
        self._name = "fetch_dom"
        self._description = (
            "A stateful browser tool. It keeps the browser open across multiple tool calls. "
            "Use actions sequentially: 'goto' a URL, 'fill' forms, 'click' buttons, then 'extract' the DOM. "
            "Finally, use 'close' to clean up."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["goto", "click", "fill", "extract", "screenshot", "close"],
                    "description": "The browser action to perform."
                },
                "url": {"type": "string", "description": "URL to visit (required for 'goto')."},
                "selector": {"type": "string", "description": "CSS selector to click or fill, or wait for before extraction."},
                "text": {"type": "string", "description": "Text to type (required for 'fill')."},
                "extract_html": {"type": "boolean", "description": "If true during 'extract', returns raw HTML instead of text.", "default": False},
                "path": {"type": "string", "description": "File path to save the screenshot (required for 'screenshot')."}
            },
            "required": ["action"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        action = kwargs.get("action")
        if not action:
            return "Error: 'action' parameter is required."

        if action == "close":
            close_browser()
            return "Browser session closed successfully."

        try:
            page = get_browser_page()
        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error starting browser: {e}"

        try:
            if action == "goto":
                url = kwargs.get("url")
                if not url:
                    return "Error: 'url' required for goto action."
                page.goto(url, wait_until="networkidle")
                return f"Successfully navigated to {url}."
                
            elif action == "click":
                selector = kwargs.get("selector")
                if not selector:
                    return "Error: 'selector' required for click action."
                page.click(selector)
                page.wait_for_timeout(500)
                return f"Clicked element: {selector}"
                
            elif action == "fill":
                selector = kwargs.get("selector")
                text = kwargs.get("text", "")
                if not selector:
                    return "Error: 'selector' required for fill action."
                page.fill(selector, text)
                return f"Filled '{text}' into {selector}"
                
            elif action == "extract":
                selector = kwargs.get("selector")
                extract_html = kwargs.get("extract_html", False)
                if selector:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                    except Exception as e:
                        logger.warning(f"Timeout waiting for selector '{selector}': {e}")
                
                if extract_html:
                    return page.content()
                else:
                    return page.locator("body").inner_text()
                    
            elif action == "screenshot":
                path = kwargs.get("path", "browser_screenshot.png")
                page.screenshot(path=path)
                return f"Screenshot successfully saved to {path}."
                    
            else:
                return f"Error: Unknown action '{action}'"
                
        except Exception as e:
            return f"Browser error during '{action}': {str(e)}"

