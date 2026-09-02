"""Tests for browser_tool.py — BrowserTool class.

Covers:
- __init__, name, description, parameters_schema properties
- _format_a11y_tree recursive tree formatting
- _ensure_dom_parser, _ensure_vision_hybrid
- execute with various actions (playwright mocked)
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.tools.browser_tool import BrowserTool


def _mock_method(obj: object, name: str) -> MagicMock:
    return cast(MagicMock, getattr(obj, name))


def _private_value(obj: object, name: str) -> object:
    return cast(object, getattr(obj, name))


def _format_tree(tool: BrowserTool, node: Mapping[str, object], max_depth: int = 3) -> str:
    formatter = cast(Callable[..., object], getattr(tool, "_format_a11y_tree"))
    return cast(str, formatter(node, max_depth=max_depth))


def _ensure_parser(tool: BrowserTool) -> object:
    return cast(Callable[[], object], getattr(tool, "_ensure_dom_parser"))()


def _ensure_hybrid(tool: BrowserTool) -> object:
    return cast(Callable[[], object], getattr(tool, "_ensure_vision_hybrid"))()


class TestBrowserToolInit:
    def test_default_attributes(self):
        tool = BrowserTool()
        assert tool.page is None
        assert tool.context is None
        assert tool.browser is None
        assert tool.playwright is None
        assert tool.is_running is False
        assert _private_value(tool, "_dom_parser") is None
        assert _private_value(tool, "_vision_hybrid") is None
        assert _private_value(tool, "_last_snapshot") is None

    def test_tags_and_category(self):
        tool = BrowserTool()
        assert "browser" in tool.tags
        assert "playwright" in tool.tags
        assert "automation" in tool.tags


class TestBrowserToolProperties:
    def test_name(self):
        assert BrowserTool().name == "browser"

    def test_description(self):
        desc = BrowserTool().description
        assert "브라우저" in desc
        assert "goto" in desc
        assert "click_by_intent" in desc

    def test_parameters_schema(self):
        schema = BrowserTool().parameters_schema
        assert schema["type"] == "object"
        assert cast(list[str], schema["required"]) == ["action"]
        properties = cast(dict[str, object], schema["properties"])
        action = cast(dict[str, object], properties["action"])
        actions = cast(list[str], action["enum"])
        assert "goto" in actions
        assert "click" in actions
        assert "type" in actions
        assert "semantic_snapshot" in actions
        assert "click_by_intent" in actions
        assert "vision_analyze" in actions
        assert "som_screenshot" in actions
        assert "detect_obstacles" in actions


class TestBrowserToolFormatA11yTree:
    """_format_a11y_tree — recursive accessibility tree formatting."""

    def test_empty_node(self):
        tool = BrowserTool()
        result = _format_tree(tool, {})
        assert result == "[]"

    def test_node_with_role_only(self):
        tool = BrowserTool()
        result = _format_tree(tool, {"role": "button"})
        assert result == "[button]"

    def test_node_with_role_and_name(self):
        tool = BrowserTool()
        result = _format_tree(tool, {"role": "button", "name": "Submit"})
        assert result == '[button] "Submit"'

    def test_with_child(self):
        tool = BrowserTool()
        node = {
            "role": "form",
            "name": "Login",
            "children": [{"role": "button", "name": "Submit"}],
        }
        result = _format_tree(tool, node)
        lines = result.split("\n")
        assert len(lines) == 2
        assert '[form] "Login"' in lines[0]
        assert '[button] "Submit"' in lines[1]

    def test_with_max_depth(self):
        tool = BrowserTool()
        deep = {
            "role": "root",
            "children": [
                {
                    "role": "section",
                    "children": [
                        {
                            "role": "group",
                            "children": [{"role": "button", "name": "Deep"}],
                        },
                    ],
                },
            ],
        }
        result = _format_tree(tool, deep, max_depth=2)
        lines = result.split("\n")
        # depth 0 (root) and depth 1 (section) should appear
        assert "[root]" in lines[0]
        assert "[section]" in lines[1]
        # depth 2 (group) and depth 3 (button) should be truncated
        assert "[group]" not in result or "[group]" not in lines[:3]

    def test_no_name_attribute(self):
        """role='separator' with no name attr."""
        tool = BrowserTool()
        node = {"role": "separator"}
        result = _format_tree(tool, node)
        assert result == "[separator]"

    def test_multiple_children(self):
        tool = BrowserTool()
        node = {
            "role": "toolbar",
            "children": [
                {"role": "button", "name": "Cut"},
                {"role": "button", "name": "Copy"},
                {"role": "button", "name": "Paste"},
            ],
        }
        result = _format_tree(tool, node)
        lines = result.split("\n")
        assert len(lines) == 4
        assert "Cut" in lines[1]
        assert "Copy" in lines[2]
        assert "Paste" in lines[3]


@pytest.fixture
def mock_setup() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Fixture: patch sync_playwright and return (mock_pw_instance, mock_page)."""
    with patch("playwright.sync_api.sync_playwright") as mp:
        page = MagicMock()
        pw_instance = MagicMock()
        browser = MagicMock()
        context = MagicMock()
        _mock_method(pw_instance, "start").return_value = pw_instance
        chromium = MagicMock()
        setattr(pw_instance, "chromium", chromium)
        _mock_method(chromium, "launch").return_value = browser
        _mock_method(browser, "new_context").return_value = context
        _mock_method(context, "new_page").return_value = page
        setattr(mp, "return_value", pw_instance)
        yield mp, page


class TestBrowserToolExecute:
    """execute with playwright mocked — various actions."""

    def test_execute_import_error(self):
        """playwright.sync_api를 찾을 수 없으면 ImportError -> 설치 안내 반환."""
        tool = BrowserTool()
        with patch.dict("sys.modules", {"playwright": None}):
            result = tool.execute(action="goto", url="http://example.com")
            assert "playwright" in result.lower()
            assert "설치" in result

    def test_execute_unknown_action(self):
        tool = BrowserTool()
        with patch("playwright.sync_api.sync_playwright") as mock_pw:
            start = _mock_method(cast(object, mock_pw.return_value), "start")
            start.return_value = MagicMock()
            result = tool.execute(action="unknown_action_xyz")
            assert "Unknown" in result

    def test_execute_goto_success(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        _mock_method(page, "title").return_value = "Test Page"
        tool = BrowserTool()

        result = tool.execute(action="goto", url="http://example.com")

        assert "Navigated" in result
        assert "Test Page" in result
        _mock_method(page, "goto").assert_called_once_with("http://example.com", wait_until="networkidle", timeout=15000)

    def test_execute_click_with_selector(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        tool = BrowserTool()

        result = tool.execute(action="click", selector="#btn")
        _mock_method(page, "click").assert_called_once_with("#btn", timeout=5000)
        assert "Clicked on" in result

    def test_execute_click_with_text(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        _mock_method(page, "get_by_text").return_value = MagicMock()
        tool = BrowserTool()

        result = tool.execute(action="click", text="Submit")
        assert "Clicked element with text" in result

    def test_execute_type_with_selector(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        tool = BrowserTool()

        result = tool.execute(action="type", selector="#input", text="hello")
        assert "hello" in result
        _mock_method(page, "fill").assert_called_once()

    def test_execute_type_via_keyboard(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        tool = BrowserTool()

        result = tool.execute(action="type", text="hello")
        assert "keyboard" in result
        keyboard = cast(MagicMock, getattr(page, "keyboard"))
        _mock_method(keyboard, "type").assert_called_once_with("hello")

    def test_execute_screenshot(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        tool = BrowserTool()

        result = tool.execute(action="screenshot", path="/tmp/test.png")
        assert "saved" in result.lower()
        _mock_method(page, "screenshot").assert_called_once()

    def test_execute_close(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        page.video = None
        tool = BrowserTool()

        # execute sets up is_running automatically via mock
        result = tool.execute(action="close")
        assert "closed" in result.lower()
        assert tool.is_running is False

    def test_execute_close_with_video(self, mock_setup: tuple[MagicMock, MagicMock]):
        _, page = mock_setup
        mock_video = MagicMock()
        _mock_method(mock_video, "path").return_value = "/tmp/video.webm"
        page.video = mock_video
        tool = BrowserTool()

        # First call sets up, second closes
        _ = tool.execute(action="goto", url="http://example.com")
        result = tool.execute(action="close")
        assert "Video recorded" in result


class TestBrowserToolEnsureDomParser:
    """_ensure_dom_parser and _ensure_vision_hybrid lazy init."""

    def test_ensure_dom_parser_initializes(self):
        tool = BrowserTool()
        assert _private_value(tool, "_dom_parser") is None

        with patch("antigravity_k.tools.semantic_dom.SemanticDOMParser") as mock_parser:
            mock_parser.return_value = MagicMock()
            parser = _ensure_parser(tool)
            assert parser is not None
            assert _private_value(tool, "_dom_parser") is not None

    def test_ensure_dom_parser_caches(self):
        tool = BrowserTool()
        with patch("antigravity_k.tools.semantic_dom.SemanticDOMParser") as mock_parser:
            mock_parser.return_value = MagicMock()
            p1 = _ensure_parser(tool)
            p2 = _ensure_parser(tool)
            assert p1 is p2
            assert mock_parser.call_count == 1

    def test_ensure_vision_hybrid_initializes(self):
        tool = BrowserTool()
        assert _private_value(tool, "_vision_hybrid") is None

        with (
            patch("antigravity_k.tools.semantic_dom.SemanticDOMParser") as mock_parser,
            patch("antigravity_k.tools.vision_dom_hybrid.VisionDOMHybrid") as mock_hybrid,
        ):
            mock_parser.return_value = MagicMock()
            mock_hybrid.return_value = MagicMock()
            hybrid = _ensure_hybrid(tool)
            assert hybrid is not None

    def test_ensure_vision_hybrid_caches(self):
        tool = BrowserTool()
        with (
            patch("antigravity_k.tools.semantic_dom.SemanticDOMParser") as mock_parser,
            patch("antigravity_k.tools.vision_dom_hybrid.VisionDOMHybrid") as mock_hybrid,
        ):
            mock_parser.return_value = MagicMock()
            mock_hybrid.return_value = MagicMock()
            h1 = _ensure_hybrid(tool)
            h2 = _ensure_hybrid(tool)
            assert h1 is h2
            assert mock_hybrid.call_count == 1
