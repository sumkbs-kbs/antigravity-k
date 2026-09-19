"""Tests for the browser_tools module."""

from collections.abc import Callable
from typing import cast
from unittest import mock

from antigravity_k.tools.browser_tools import (
    BrowserDOMTool,
    close_browser,
    get_browser_page,
)


class _LocatorDouble:
    def __init__(self, text: str) -> None:
        self._text: str = text

    def inner_text(self) -> str:
        return self._text


class _PageDouble:
    goto: mock.Mock
    click: mock.Mock
    wait_for_timeout: mock.Mock
    fill: mock.Mock
    locator: mock.Mock
    wait_for_selector: mock.Mock
    content: mock.Mock
    screenshot: mock.Mock

    def __init__(self, locator_text: str = "") -> None:
        self.goto = mock.Mock()
        self.click = mock.Mock()
        self.wait_for_timeout = mock.Mock()
        self.fill = mock.Mock()
        self.locator = mock.Mock(return_value=_LocatorDouble(locator_text))
        self.wait_for_selector = mock.Mock()
        self.content = mock.Mock(return_value="")
        self.screenshot = mock.Mock()


def _execute(tool: BrowserDOMTool, **kwargs: object) -> str:
    execute = cast(Callable[..., str], getattr(tool, "execute"))
    return execute(**kwargs)


def _assert_called_once(value: object) -> None:
    checker = cast(Callable[[], object], getattr(value, "assert_called_once"))
    _ = checker()


def _mock_attr(value: object, name: str) -> object:
    return cast(object, getattr(value, name))


def _assert_called_once_with(value: object, *args: object, **kwargs: object) -> None:
    checker = cast(Callable[..., object], getattr(value, "assert_called_once_with"))
    _ = checker(*args, **kwargs)


def _set_side_effect(value: object, effect: object) -> None:
    setattr(value, "side_effect", effect)


class TestBrowserDOMModel:
    def test_properties(self):
        tool = BrowserDOMTool()
        assert tool.name == "fetch_dom"
        assert tool.parameters_schema["required"] == ["action"]
        assert "goto" in str(cast(object, tool.parameters_schema))

    def test_execute_no_action(self):
        tool = BrowserDOMTool()
        result = _execute(tool)
        assert "action" in result

    def test_execute_unknown_action(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = _PageDouble()
            result = _execute(tool, action="unknown_action_xyz")
            assert "Unknown" in result

    def test_execute_close(self):
        with mock.patch("antigravity_k.tools.browser_tools.close_browser") as mock_close:
            tool = BrowserDOMTool()
            result = _execute(tool, action="close")
            _assert_called_once(mock_close)
            assert "closed" in result.lower()

    def test_execute_import_error(self):
        tool = BrowserDOMTool()
        with mock.patch(
            "antigravity_k.tools.browser_tools.get_browser_page", side_effect=ImportError("Playwright not installed")
        ):
            result = _execute(tool, action="goto", url="http://example.com")
            assert "Playwright" in result

    def test_execute_browser_start_error(self):
        tool = BrowserDOMTool()
        with mock.patch(
            "antigravity_k.tools.browser_tools.get_browser_page", side_effect=RuntimeError("Connection refused")
        ):
            result = _execute(tool, action="goto", url="http://example.com")
            assert "Error" in result

    def test_execute_goto_no_url(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = mock.MagicMock()
            result = _execute(tool, action="goto")
            assert "url" in result.lower()

    def test_execute_goto_success(self):
        tool = BrowserDOMTool()
        page = _PageDouble()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="goto", url="http://example.com")
            _assert_called_once_with(_mock_attr(page, "goto"), "http://example.com", wait_until="networkidle")
            assert "navigated" in result.lower()

    def test_execute_click_no_selector(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = _PageDouble()
            result = _execute(tool, action="click")
            assert "selector" in result.lower()

    def test_execute_click_success(self):
        tool = BrowserDOMTool()
        page = _PageDouble()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="click", selector="#btn")
            _assert_called_once_with(_mock_attr(page, "click"), "#btn")
            assert "Clicked" in result

    def test_execute_fill_no_selector(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = _PageDouble()
            result = _execute(tool, action="fill")
            assert "selector" in result.lower()

    def test_execute_fill_success(self):
        tool = BrowserDOMTool()
        page = _PageDouble()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="fill", selector="#input", text="hello")
            _assert_called_once_with(_mock_attr(page, "fill"), "#input", "hello")
            assert "Filled" in result

    def test_execute_extract_text(self):
        tool = BrowserDOMTool()
        page = _PageDouble("body text")
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="extract")
            _assert_called_once_with(_mock_attr(page, "locator"), "body")
            assert "body text" == result

    def test_execute_extract_html(self):
        tool = BrowserDOMTool()
        page = _PageDouble()
        page.content = mock.Mock(return_value="<html>content</html>")
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="extract", extract_html=True)
            _assert_called_once(_mock_attr(page, "content"))
            assert "<html>" in result

    def test_execute_extract_with_selector(self):
        tool = BrowserDOMTool()
        page = _PageDouble("selected text")
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="extract", selector="main")
            _assert_called_once_with(_mock_attr(page, "wait_for_selector"), "main", timeout=5000)
            assert "selected text" == result

    def test_execute_screenshot(self):
        tool = BrowserDOMTool()
        page = _PageDouble()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="screenshot", path="/tmp/test.png")
            _assert_called_once_with(_mock_attr(page, "screenshot"), path="/tmp/test.png")
            assert "saved" in result.lower()

    def test_execute_browser_action_error(self):
        tool = BrowserDOMTool()
        page = _PageDouble()
        _set_side_effect(_mock_attr(page, "goto"), RuntimeError("Navigation failed"))
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = _execute(tool, action="goto", url="http://fail.com")
            assert "Browser error" in result or "Error" in result


class TestGetBrowserPage:
    @mock.patch("antigravity_k.tools.browser_tools._page", None)
    @mock.patch("antigravity_k.tools.browser_tools._browser", None)
    @mock.patch("antigravity_k.tools.browser_tools._playwright", None)
    def test_import_error(self):
        # Patch at the import source since sync_playwright is imported inside
        # get_browser_page() via: from playwright.sync_api import sync_playwright
        with mock.patch("playwright.sync_api.sync_playwright", side_effect=ImportError("no playwright")):
            try:
                _ = get_browser_page()
                assert False, "Should have raised ImportError"
            except ImportError as e:
                assert "Playwright" in str(e)


class TestCloseBrowser:
    def test_close_no_session(self):
        close_browser()  # should not raise

    @mock.patch("antigravity_k.tools.browser_tools._page", mock.MagicMock())
    @mock.patch("antigravity_k.tools.browser_tools._browser", mock.MagicMock())
    @mock.patch("antigravity_k.tools.browser_tools._playwright", mock.MagicMock())
    def test_close_active_session(self):
        close_browser()
        # should not raise
