"""BrowserTools — DOM 파싱 및 브라우저 검증 도구.

==============================================
SPA(React, Vue 등)의 동적 렌더링 요소를 에이전트가 직접 파싱할 수 있도록 지원.

포함 도구:
- FetchDOMTool: Playwright를 사용하여 URL에 접속하고 렌더링된 후의 DOM 텍스트를 반환합니다.
"""

from __future__ import annotations

import logging
from typing import Callable, Protocol, cast, override

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)

# ─── 전역 브라우저 세션 (Stateful) ───


class _LocatorLike(Protocol):
    def inner_text(self) -> str: ...


class _PageLike(Protocol):
    def is_closed(self) -> bool: ...

    def goto(self, url: str, *, wait_until: str) -> object: ...

    def new_page(self) -> _PageLike: ...

    def click(self, selector: str) -> None: ...

    def wait_for_timeout(self, timeout: int) -> None: ...

    def fill(self, selector: str, value: str) -> None: ...

    def wait_for_selector(self, selector: str, *, timeout: int) -> object | None: ...

    def content(self) -> str: ...

    def locator(self, selector: str) -> _LocatorLike: ...

    def screenshot(self, *, path: str) -> bytes: ...

    def close(self) -> None: ...


class _BrowserLike(Protocol):
    def is_connected(self) -> bool: ...

    def new_page(self) -> _PageLike: ...

    def close(self) -> None: ...


class _ChromiumLike(Protocol):
    def launch(self, *, headless: bool) -> _BrowserLike: ...


class _PlaywrightLike(Protocol):
    chromium: _ChromiumLike

    def start(self) -> _PlaywrightLike: ...

    def stop(self) -> None: ...


_playwright: _PlaywrightLike | None = None
_browser: _BrowserLike | None = None
_page: _PageLike | None = None


def get_browser_page() -> _PageLike:
    """싱글톤 패턴으로 브라우저 페이지를 유지합니다."""
    global _playwright, _browser, _page
    if _page is None or _page.is_closed():
        try:
            from playwright.sync_api import sync_playwright

            if _playwright is None:
                start_playwright = cast(Callable[[], _PlaywrightLike], sync_playwright)
                _playwright = start_playwright().start()
            playwright = _playwright
            assert playwright is not None
            if _browser is None or not _browser.is_connected():
                # Headless=False 로 설정하여 사용자 화면에 보이도록 함
                _browser = playwright.chromium.launch(headless=False)
            browser = _browser
            assert browser is not None
            _page = browser.new_page()
        except ImportError:
            raise ImportError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium",
            )
    return _page


def close_browser() -> None:
    """브라우저 세션을 명시적으로 닫습니다."""
    global _playwright, _browser, _page
    if _page:
        try:
            _page.close()
        except Exception:
            logger.exception("Failed to close page")
        _page = None
    if _browser:
        try:
            _browser.close()
        except Exception:
            logger.exception("Failed to close browser")
        _browser = None
    if _playwright:
        try:
            _playwright.stop()
        except Exception:
            logger.exception("Failed to stop playwright")
        _playwright = None


class BrowserDOMTool(BaseTool):
    """Stateful 브라우저 세션을 관리하며 자바스크립트 기반 웹 페이지와 상호작용합니다."""

    category: ToolCategory = ToolCategory.SEARCH
    render_in: RenderIn = RenderIn.CONTEXTUAL
    risk_level: RiskLevel = RiskLevel.SAFE
    icon: str = "🌐"
    tags: list[str] = ["browser", "stateful", "qa", "test", "interact"]

    def __init__(self) -> None:
        """Initialize the BrowserDOMTool."""
        super().__init__()
        self._name: str = "fetch_dom"
        self._description: str = (
            "A stateful browser tool. It keeps the browser open across multiple tool calls. "
            "Use actions sequentially: 'goto' a URL, 'fill' forms, 'click' buttons, then 'extract' the DOM. "
            "Finally, use 'close' to clean up."
        )
        self._schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["goto", "click", "fill", "extract", "screenshot", "close"],
                    "description": "The browser action to perform.",
                },
                "url": {
                    "type": "string",
                    "description": "URL to visit (required for 'goto').",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector to click or fill, or wait for before extraction.",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type (required for 'fill').",
                },
                "extract_html": {
                    "type": "boolean",
                    "description": "If true during 'extract', returns raw HTML instead of text.",
                    "default": False,
                },
                "path": {
                    "type": "string",
                    "description": "File path to save the screenshot (required for 'screenshot').",
                },
            },
            "required": ["action"],
        }

    @property
    @override
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    @override
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    @override
    def parameters_schema(self) -> dict[str, object]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    @override
    def execute(self, **kwargs: object) -> str:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        action_value = kwargs.get("action")
        action = action_value if isinstance(action_value, str) else ""
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
            logger.exception("Unhandled exception")
            return f"Error starting browser: {e}"

        try:
            if action == "goto":
                url_value = kwargs.get("url")
                url = url_value if isinstance(url_value, str) else ""
                if not url:
                    return "Error: 'url' required for goto action."
                _ = page.goto(url, wait_until="networkidle")
                return f"Successfully navigated to {url}."

            elif action == "click":
                selector_value = kwargs.get("selector")
                selector = selector_value if isinstance(selector_value, str) else ""
                if not selector:
                    return "Error: 'selector' required for click action."
                page.click(selector)
                page.wait_for_timeout(500)
                return f"Clicked element: {selector}"

            elif action == "fill":
                selector_value = kwargs.get("selector")
                selector = selector_value if isinstance(selector_value, str) else ""
                text_value = kwargs.get("text", "")
                text = text_value if isinstance(text_value, str) else ""
                if not selector:
                    return "Error: 'selector' required for fill action."
                page.fill(selector, text)
                return f"Filled '{text}' into {selector}"

            elif action == "extract":
                selector_value = kwargs.get("selector")
                selector = selector_value if isinstance(selector_value, str) else ""
                extract_html_value = kwargs.get("extract_html", False)
                extract_html = extract_html_value if isinstance(extract_html_value, bool) else False
                if selector:
                    try:
                        _ = page.wait_for_selector(selector, timeout=5000)
                    except Exception:
                        logger.exception("Timeout waiting for selector '%s'", selector)

                if extract_html:
                    return page.content()
                else:
                    return page.locator("body").inner_text()

            elif action == "screenshot":
                path_value = kwargs.get("path", "browser_screenshot.png")
                path = path_value if isinstance(path_value, str) else "browser_screenshot.png"
                _ = page.screenshot(path=path)
                return f"Screenshot successfully saved to {path}."

            else:
                return f"Error: Unknown action '{action}'"

        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Browser error during '{action}': {str(e)}"
