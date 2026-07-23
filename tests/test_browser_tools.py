"""Tests for the browser_tools module."""

from unittest import mock

from antigravity_k.tools.browser_tools import (
    BrowserDOMTool,
    close_browser,
    get_browser_page,
)


class TestBrowserDOMModel:
    def test_properties(self):
        tool = BrowserDOMTool()
        assert tool.name == "fetch_dom"
        assert tool.parameters_schema["required"] == ["action"]
        assert "goto" in str(tool.parameters_schema["properties"]["action"]["enum"])

    def test_execute_no_action(self):
        tool = BrowserDOMTool()
        result = tool.execute()
        assert "action" in result

    def test_execute_unknown_action(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = mock.MagicMock()
            result = tool.execute(action="unknown_action_xyz")
            assert "Unknown" in result

    def test_execute_close(self):
        with mock.patch("antigravity_k.tools.browser_tools.close_browser") as mock_close:
            tool = BrowserDOMTool()
            result = tool.execute(action="close")
            mock_close.assert_called_once()
            assert "closed" in result.lower()

    def test_execute_import_error(self):
        tool = BrowserDOMTool()
        with mock.patch(
            "antigravity_k.tools.browser_tools.get_browser_page", side_effect=ImportError("Playwright not installed")
        ):
            result = tool.execute(action="goto", url="http://example.com")
            assert "Playwright" in result

    def test_execute_browser_start_error(self):
        tool = BrowserDOMTool()
        with mock.patch(
            "antigravity_k.tools.browser_tools.get_browser_page", side_effect=RuntimeError("Connection refused")
        ):
            result = tool.execute(action="goto", url="http://example.com")
            assert "Error" in result

    def test_execute_goto_no_url(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = mock.MagicMock()
            result = tool.execute(action="goto")
            assert "url" in result.lower()

    def test_execute_goto_success(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="goto", url="http://example.com")
            page.goto.assert_called_once_with("http://example.com", wait_until="networkidle")
            assert "navigated" in result.lower()

    def test_execute_click_no_selector(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = mock.MagicMock()
            result = tool.execute(action="click")
            assert "selector" in result.lower()

    def test_execute_click_success(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="click", selector="#btn")
            page.click.assert_called_once_with("#btn")
            assert "Clicked" in result

    def test_execute_fill_no_selector(self):
        tool = BrowserDOMTool()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page") as mock_get:
            mock_get.return_value = mock.MagicMock()
            result = tool.execute(action="fill")
            assert "selector" in result.lower()

    def test_execute_fill_success(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="fill", selector="#input", text="hello")
            page.fill.assert_called_once_with("#input", "hello")
            assert "Filled" in result

    def test_execute_extract_text(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        page.locator.return_value.inner_text.return_value = "body text"
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="extract")
            page.locator.assert_called_once_with("body")
            assert "body text" == result

    def test_execute_extract_html(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        page.content.return_value = "<html>content</html>"
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="extract", extract_html=True)
            page.content.assert_called_once()
            assert "<html>" in result

    def test_execute_extract_with_selector(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        page.locator.return_value.inner_text.return_value = "selected text"
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="extract", selector="main")
            page.wait_for_selector.assert_called_once_with("main", timeout=5000)
            assert "selected text" == result

    def test_execute_screenshot(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="screenshot", path="/tmp/test.png")
            page.screenshot.assert_called_once_with(path="/tmp/test.png")
            assert "saved" in result.lower()

    def test_execute_browser_action_error(self):
        tool = BrowserDOMTool()
        page = mock.MagicMock()
        page.goto.side_effect = RuntimeError("Navigation failed")
        with mock.patch("antigravity_k.tools.browser_tools.get_browser_page", return_value=page):
            result = tool.execute(action="goto", url="http://fail.com")
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
                get_browser_page()
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
