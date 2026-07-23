"""Tests for semantic_dom.py — BoundingBox, ElementInfo, SemanticSnapshot, SemanticDOMParser.

Covers pure-logic methods without needing Playwright or browser.
"""

import pytest

from antigravity_k.tools.semantic_dom import (
    BoundingBox,
    ElementInfo,
    ElementRole,
    SemanticDOMParser,
    SemanticSnapshot,
)

# ── BoundingBox ────────────────────────────────────────────────────────


class TestBoundingBox:
    def test_center_default(self):
        box = BoundingBox()
        assert box.center == (0.0, 0.0)

    def test_center_positive(self):
        box = BoundingBox(x=100, y=200, width=50, height=30)
        assert box.center == (125.0, 215.0)

    def test_center_negative(self):
        box = BoundingBox(x=-50, y=-100, width=40, height=20)
        assert box.center == (-30.0, -90.0)

    def test_to_compact_default(self):
        box = BoundingBox()
        assert box.to_compact() == "(0,0,0,0)"

    def test_to_compact_with_values(self):
        box = BoundingBox(x=152.3, y=290.7, width=200.1, height=32.9)
        assert box.to_compact() == "(152,290,200,32)"

    def test_to_compact_rounded(self):
        box = BoundingBox(x=10.1, y=20.9, width=99.5, height=40.0)
        compact = box.to_compact()
        parts = compact.strip("()").split(",")
        assert all(p.isdigit() for p in parts)


# ── ElementInfo.display_name ───────────────────────────────────────────


class TestElementInfoDisplayName:
    def test_name_priority(self):
        el = ElementInfo(ref="@ref1", name="Login Button", aria_label="login", placeholder="user")
        assert el.display_name == "Login Button"

    def test_aria_label_fallback(self):
        el = ElementInfo(ref="@ref2", name="", aria_label="username input", placeholder="enter")
        assert el.display_name == "username input"

    def test_placeholder_fallback(self):
        el = ElementInfo(ref="@ref3", name="", aria_label="", placeholder="Enter email")
        assert el.display_name == "Enter email"

    def test_tag_fallback(self):
        el = ElementInfo(ref="@ref4", name="", aria_label="", placeholder="", tag="button")
        assert el.display_name == "button"

    def test_all_empty(self):
        el = ElementInfo(ref="@ref5")
        assert el.display_name == ""

    def test_name_truncation(self):
        long_name = "A" * 100
        el = ElementInfo(ref="@ref1", name=long_name)
        assert len(el.display_name) == 60
        assert el.display_name.endswith("A" * 60)
        assert el.display_name == long_name[:60]

    def test_aria_truncation(self):
        long_label = "B" * 80
        el = ElementInfo(ref="@ref2", aria_label=long_label)
        assert len(el.display_name) == 60


# ── ElementInfo.to_compact_line ────────────────────────────────────────


class TestElementInfoToCompactLine:
    def test_basic(self):
        el = ElementInfo(ref="@ref1", tag="button", role=ElementRole.BUTTON, name="Submit")
        line = el.to_compact_line()
        assert "@ref1" in line
        assert "[button]" in line
        assert "Submit" in line

    def test_with_href(self):
        el = ElementInfo(
            ref="@ref2", tag="a", role=ElementRole.LINK, name="Docs", href="https://docs.example.com/guide"
        )
        line = el.to_compact_line()
        assert "href=https://docs.example.com/guide" in line

    def test_href_truncation(self):
        long_href = "https://example.com/" + "x" * 50
        el = ElementInfo(ref="@ref3", tag="a", role=ElementRole.LINK, href=long_href)
        line = el.to_compact_line()
        assert "..." in line
        assert len(line) < len(long_href) + 50

    def test_with_value(self):
        el = ElementInfo(ref="@ref1", tag="input", role=ElementRole.INPUT, value="test@email.com")
        line = el.to_compact_line()
        assert "value=test@email.com" in line

    def test_value_truncation(self):
        long_val = "v" * 50
        el = ElementInfo(ref="@ref1", tag="input", value=long_val)
        line = el.to_compact_line()
        assert "value=vvvv" in line
        assert len(line) < 200

    def test_disabled(self):
        el = ElementInfo(ref="@ref1", tag="button", is_disabled=True)
        line = el.to_compact_line()
        assert "(disabled)" in line

    def test_with_bbox(self):
        el = ElementInfo(ref="@ref1", tag="button", bbox=BoundingBox(x=10, y=20, width=100, height=30))
        line = el.to_compact_line()
        assert "(10,20,100,30)" in line

    def test_interactable_button(self):
        el = ElementInfo(
            ref="@ref5",
            tag="button",
            role=ElementRole.BUTTON,
            name="Send",
            is_interactable=True,
            bbox=BoundingBox(x=0, y=0, width=80, height=36),
        )
        line = el.to_compact_line()
        assert "@ref5" in line
        assert "[button]" in line
        assert "Send" in line
        assert "(0,0,80,36)" in line

    def test_empty_name(self):
        el = ElementInfo(ref="@ref6", tag="div")
        line = el.to_compact_line()
        assert "@ref6" in line
        assert "[other]" in line

    def test_input_with_placeholder(self):
        el = ElementInfo(
            ref="@ref7",
            tag="input",
            role=ElementRole.INPUT,
            placeholder="Search...",
            bbox=BoundingBox(x=100, y=50, width=300, height=40),
        )
        line = el.to_compact_line()
        assert "@ref7" in line
        assert "[input]" in line
        assert "Search..." in line


# ── SemanticSnapshot ───────────────────────────────────────────────────


class TestSemanticSnapshot:
    def test_initial_state(self):
        snap = SemanticSnapshot()
        assert snap.elements == {}
        assert snap.url == ""
        assert snap.interactable_count == 0
        assert snap.total_count == 0

    def test_get_existing(self):
        el = ElementInfo(ref="@ref1", tag="button")
        snap = SemanticSnapshot(elements={"@ref1": el})
        assert snap.get("@ref1") is el

    def test_get_missing(self):
        snap = SemanticSnapshot()
        assert snap.get("@ref100") is None

    def test_interactable_elements(self):
        e1 = ElementInfo(ref="@ref1", tag="button", is_interactable=True)
        e2 = ElementInfo(ref="@ref2", tag="div", is_interactable=False)
        e3 = ElementInfo(ref="@ref3", tag="a", is_interactable=True)
        snap = SemanticSnapshot(elements={"@ref1": e1, "@ref2": e2, "@ref3": e3})
        interactable = snap.interactable_elements()
        assert len(interactable) == 2
        assert e1 in interactable
        assert e3 in interactable

    def test_by_role(self):
        e1 = ElementInfo(ref="@ref1", role=ElementRole.BUTTON)
        e2 = ElementInfo(ref="@ref2", role=ElementRole.INPUT)
        e3 = ElementInfo(ref="@ref3", role=ElementRole.BUTTON)
        snap = SemanticSnapshot(elements={"@ref1": e1, "@ref2": e2, "@ref3": e3})
        buttons = snap.by_role(ElementRole.BUTTON)
        assert len(buttons) == 2
        links = snap.by_role(ElementRole.LINK)
        assert links == []

    def test_empty_snapshot_methods(self):
        snap = SemanticSnapshot()
        assert snap.interactable_elements() == []
        assert snap.by_role(ElementRole.BUTTON) == []


# ── SemanticDOMParser._intent_match_score ──────────────────────────────


class TestIntentMatchScore:
    """Tests for SemanticDOMParser._intent_match_score private method."""

    def test_exact_name_match(self, parser):
        el = ElementInfo(ref="@ref1", name="Login")
        score = parser._intent_match_score(el, "login")
        assert score > 0

    def test_no_match(self, parser):
        el = ElementInfo(ref="@ref1", name="Signup")
        score = parser._intent_match_score(el, "login")
        assert score == 0.0

    def test_aria_label_match(self, parser):
        el = ElementInfo(ref="@ref1", name="", aria_label="submit button")
        score = parser._intent_match_score(el, "submit")
        assert score > 0

    def test_placeholder_match(self, parser):
        el = ElementInfo(ref="@ref1", placeholder="Enter your email")
        score = parser._intent_match_score(el, "email")
        assert score > 0

    def test_href_match(self, parser):
        el = ElementInfo(ref="@ref1", href="https://example.com/login")
        score = parser._intent_match_score(el, "login")
        assert score > 0

    def test_interactable_bonus(self, parser):
        el1 = ElementInfo(ref="@ref1", name="Submit", is_interactable=True)
        el2 = ElementInfo(ref="@ref2", name="Submit", is_interactable=False)
        score1 = parser._intent_match_score(el1, "submit")
        score2 = parser._intent_match_score(el2, "submit")
        assert score1 > score2

    def test_partial_word_match(self, parser):
        el = ElementInfo(ref="@ref1", name="User Login Form")
        score = parser._intent_match_score(el, "login form")
        assert score > 0.5 * 2.0 * 0.5  # partial word match minimum

    def test_mixed_fields(self, parser):
        el = ElementInfo(
            ref="@ref1",
            name="Search",
            aria_label="search the site",
            placeholder="Search...",
            is_interactable=True,
        )
        score = parser._intent_match_score(el, "search")
        # name (3.0) + aria_label (2.5) + placeholder (2.0) + interactable bonus (1.2x)
        assert score > 7.0

    def test_empty_name_with_match(self, parser):
        el = ElementInfo(ref="@ref1", name="", aria_label="")
        score = parser._intent_match_score(el, "anything")
        assert score == 0.0


# ── SemanticDOMParser.find_by_intent ───────────────────────────────────


class TestFindByIntent:
    def test_exact_name(self, parser, snapshot_with_elements):
        result = parser.find_by_intent(snapshot_with_elements, "Login")
        assert result is not None
        assert result.ref == "@ref1"

    def test_partial_match(self, parser, snapshot_with_elements):
        result = parser.find_by_intent(snapshot_with_elements, "log")
        assert result is not None
        assert result.ref == "@ref1"

    def test_no_match_returns_none(self, parser, snapshot_with_elements):
        result = parser.find_by_intent(snapshot_with_elements, "nonexistent")
        assert result is None

    def test_role_keyword_button(self, parser, snapshot_with_elements):
        result = parser.find_by_intent(snapshot_with_elements, "버튼")
        assert result is not None
        assert result.role == ElementRole.BUTTON

    def test_role_keyword_input(self, parser, snapshot_with_elements):
        result = parser.find_by_intent(snapshot_with_elements, "입력")
        assert result is not None
        assert result.role == ElementRole.INPUT

    def test_role_with_clean_intent(self, parser, snapshot_with_elements):
        result = parser.find_by_intent(snapshot_with_elements, "링크 문서")
        assert result is not None

    def test_complex_intent(self, parser):
        """Should find the best match from multiple elements."""
        snap = SemanticSnapshot(
            elements={
                "@ref1": ElementInfo(ref="@ref1", name="Search products", role=ElementRole.INPUT, is_interactable=True),
                "@ref2": ElementInfo(ref="@ref2", name="Submit", role=ElementRole.BUTTON, is_interactable=True),
                "@ref3": ElementInfo(ref="@ref3", name="Cancel", role=ElementRole.BUTTON, is_interactable=True),
            }
        )
        result = parser.find_by_intent(snap, "검색 입력")
        assert result is not None

    def test_empty_snapshot(self, parser):
        snap = SemanticSnapshot()
        result = parser.find_by_intent(snap, "anything")
        assert result is None


# ── SemanticDOMParser._parse_element ───────────────────────────────────


class TestParseElement:
    def test_button_element(self, parser):
        raw = {
            "tag": "button",
            "name": "Click me",
            "isInteractive": True,
            "bbox": {"x": 10, "y": 20, "width": 100, "height": 30},
        }
        el = parser._parse_element("@ref1", raw)
        assert el.tag == "button"
        assert el.role == ElementRole.BUTTON
        assert el.name == "Click me"
        assert el.is_interactable is True
        assert el.bbox.x == 10
        assert el.bbox.y == 20

    def test_input_text(self, parser):
        raw = {"tag": "input", "type": "text", "name": "username", "placeholder": "Enter user", "isInteractive": True}
        el = parser._parse_element("@ref2", raw)
        assert el.role == ElementRole.INPUT
        assert el.placeholder == "Enter user"

    def test_checkbox(self, parser):
        raw = {"tag": "input", "type": "checkbox", "name": "agree", "isInteractive": True}
        el = parser._parse_element("@ref3", raw)
        assert el.role == ElementRole.CHECKBOX

    def test_radio(self, parser):
        raw = {"tag": "input", "type": "radio", "name": "gender", "isInteractive": True}
        el = parser._parse_element("@ref4", raw)
        assert el.role == ElementRole.RADIO

    def test_submit_button(self, parser):
        raw = {"tag": "input", "type": "submit", "name": "Go", "isInteractive": True}
        el = parser._parse_element("@ref5", raw)
        assert el.role == ElementRole.BUTTON

    def test_link(self, parser):
        raw = {"tag": "a", "href": "https://example.com", "name": "Example", "isInteractive": True}
        el = parser._parse_element("@ref6", raw)
        assert el.role == ElementRole.LINK
        assert el.href == "https://example.com"

    def test_heading(self, parser):
        raw = {"tag": "h1", "name": "Welcome"}
        el = parser._parse_element("@ref7", raw)
        assert el.role == ElementRole.HEADING
        assert el.is_interactable is False

    def test_aria_role_priority(self, parser):
        raw = {"tag": "div", "role": "button", "name": "Custom btn", "isInteractive": True}
        el = parser._parse_element("@ref8", raw)
        assert el.role == ElementRole.BUTTON

    def test_unknown_element(self, parser):
        raw = {"tag": "section", "name": "Content"}
        el = parser._parse_element("@ref9", raw)
        assert el.role == ElementRole.OTHER

    def test_disabled_element(self, parser):
        raw = {"tag": "button", "disabled": True, "isInteractive": False}
        el = parser._parse_element("@ref10", raw)
        assert el.is_disabled is True

    def test_missing_bbox(self, parser):
        raw = {"tag": "div"}
        el = parser._parse_element("@ref11", raw)
        assert el.bbox is not None
        assert el.bbox.x == 0
        assert el.bbox.y == 0


# ── SemanticDOMParser.to_llm_context ───────────────────────────────────


class TestToLLMContext:
    def test_basic_context(self, parser, snapshot_with_elements):
        ctx = parser.to_llm_context(snapshot_with_elements, max_elements=10)
        assert "Page:" in ctx
        assert "Elements (" in ctx
        assert "@ref1" in ctx
        assert "@ref2" in ctx
        assert "@ref3" in ctx

    def test_interactable_only(self, parser):
        snap = SemanticSnapshot(
            elements={
                "@ref1": ElementInfo(ref="@ref1", tag="button", is_interactable=True),
                "@ref2": ElementInfo(ref="@ref2", tag="div", is_interactable=False),
            }
        )
        ctx = parser.to_llm_context(snap, interactable_only=True)
        assert "@ref1" in ctx
        assert "@ref2" not in ctx

    def test_max_elements_truncation(self, parser):
        elements = {}
        for i in range(100):
            elements[f"@ref{i}"] = ElementInfo(ref=f"@ref{i}", tag="div")
        snap = SemanticSnapshot(elements=elements, total_count=100)
        ctx = parser.to_llm_context(snap, max_elements=5)
        assert "more elements" in ctx

    def test_empty_snapshot(self, parser):
        snap = SemanticSnapshot()
        ctx = parser.to_llm_context(snap)
        assert 'Page: "" ()' in ctx or "Page:" in ctx
        assert "interactable" in ctx

    def test_with_bbox(self, parser):
        el = ElementInfo(ref="@ref1", tag="button", bbox=BoundingBox(10, 20, 100, 30))
        snap = SemanticSnapshot(elements={"@ref1": el})
        ctx = parser.to_llm_context(snap, include_bbox=True)
        assert "(10,20,100,30)" in ctx

    def test_default_bbox_included(self, parser):
        """By default (include_bbox=True), bbox should be in the context."""
        el = ElementInfo(ref="@ref1", tag="button", bbox=BoundingBox(10, 20, 100, 30))
        snap = SemanticSnapshot(elements={"@ref1": el})
        ctx = parser.to_llm_context(snap)
        assert "(10,20,100,30)" in ctx

    def test_include_bbox_false_omits_bbox(self, parser):
        """When include_bbox=False, bbox should NOT be in the context."""
        el = ElementInfo(ref="@ref1", tag="button", name="OK", bbox=BoundingBox(10, 20, 100, 30))
        snap = SemanticSnapshot(elements={"@ref1": el})
        ctx = parser.to_llm_context(snap, include_bbox=False)
        assert "(10,20,100,30)" not in ctx


# ── SemanticDOMParser.resolve_ref ──────────────────────────────────────


class TestResolveRef:
    def test_ref_lookup(self, parser, snapshot_with_elements):
        result = parser.resolve_ref(snapshot_with_elements, "@ref1")
        assert result is not None
        assert result.ref == "@ref1"

    def test_natural_language(self, parser, snapshot_with_elements):
        result = parser.resolve_ref(snapshot_with_elements, "Login")
        assert result is not None
        assert result.ref == "@ref1"

    def test_missing_ref(self, parser, snapshot_with_elements):
        result = parser.resolve_ref(snapshot_with_elements, "@ref100")
        assert result is None


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def parser():
    return SemanticDOMParser()


@pytest.fixture
def snapshot_with_elements():
    """Basic snapshot with 3 elements for find_by_intent tests."""
    return SemanticSnapshot(
        elements={
            "@ref1": ElementInfo(
                ref="@ref1",
                tag="button",
                role=ElementRole.BUTTON,
                name="Login",
                is_interactable=True,
            ),
            "@ref2": ElementInfo(
                ref="@ref2",
                tag="input",
                role=ElementRole.INPUT,
                name="email",
                placeholder="Enter your email",
                is_interactable=True,
            ),
            "@ref3": ElementInfo(
                ref="@ref3",
                tag="a",
                role=ElementRole.LINK,
                name="Documentation",
                href="https://docs.example.com",
                is_interactable=True,
            ),
        },
        url="https://example.com",
        title="Test Page",
    )
