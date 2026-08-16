"""Tests for healing_loop.py — HealingLoop and HealingLoopV2.

Covers:
- HealingLoop.__init__, _find_candidates recursive search
- HealingLoop.try_with_healing: success, heal, all fail
- HealingLoopV2.__init__, _ensure_dom_parser, _record_heal, get_heal_stats
- HealingLoopV2._analyze_and_heal: heal_memory hit, semantic parser, a11y tree, bbox
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.engine.harness_models import TestIntent, TestStatus
from antigravity_k.engine.healing_loop import HealingLoop, HealingLoopV2

# ─── TestIntent fixture ──────────────────────────────────────────


@pytest.fixture
def intent() -> TestIntent:
    return TestIntent(
        id="heal-test-001",
        intent="test-healing",
        category="ui",
    )


# ─── HealingLoop ─────────────────────────────────────────────────


class TestHealingLoopInit:
    def test_default_max_attempts(self):
        loop = HealingLoop()
        assert loop.max_attempts == 3
        assert loop.heal_log == []

    def test_custom_max_attempts(self):
        loop = HealingLoop(max_attempts=5)
        assert loop.max_attempts == 5


class TestHealingLoopFindCandidates:
    """_find_candidates — recursive accessibility tree search."""

    def test_empty_node(self):
        loop = HealingLoop()
        result = loop._find_candidates({}, "test")
        assert result == []

    def test_matching_name_in_root(self):
        loop = HealingLoop()
        node = {"name": "Submit Button", "role": "button"}
        result = loop._find_candidates(node, "Submit")
        assert len(result) == 1
        assert "role=button" in result[0]

    def test_matching_name_in_child(self):
        loop = HealingLoop()
        node = {
            "name": "Form",
            "role": "form",
            "children": [
                {"name": "Username Input", "role": "textbox"},
                {"name": "Submit Button", "role": "button"},
            ],
        }
        result = loop._find_candidates(node, "Submit")
        assert len(result) == 1
        assert "role=button" in result[0]
        assert "Submit Button" in result[0]

    def test_multiple_matches(self):
        loop = HealingLoop()
        node = {
            "name": "Root",
            "role": "root",
            "children": [
                {"name": "Save", "role": "button"},
                {"name": "Save As", "role": "button"},
            ],
        }
        result = loop._find_candidates(node, "Save")
        assert len(result) == 2

    def test_no_match(self):
        loop = HealingLoop()
        node = {"name": "Cancel", "role": "button"}
        result = loop._find_candidates(node, "Submit")
        assert result == []

    def test_case_insensitive_match(self):
        loop = HealingLoop()
        node = {"name": "SUBMIT BUTTON", "role": "button"}
        result = loop._find_candidates(node, "submit")
        assert len(result) == 1

    def test_empty_target_text(self):
        loop = HealingLoop()
        node = {"name": "Anything", "role": "button"}
        result = loop._find_candidates(node, "")
        assert result == []

    def test_nested_children(self):
        loop = HealingLoop()
        node = {
            "name": "Outer",
            "role": "dialog",
            "children": [
                {
                    "name": "Inner Section",
                    "role": "section",
                    "children": [
                        {"name": "Deep Button", "role": "button"},
                    ],
                },
            ],
        }
        result = loop._find_candidates(node, "Deep")
        assert len(result) == 1
        assert "Deep Button" in result[0]

    def test_node_without_name(self):
        loop = HealingLoop()
        node = {"role": "separator"}
        result = loop._find_candidates(node, "anything")
        assert result == []


class TestHealingLoopTryWithHealing:
    """try_with_healing — success, healed, all fail."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self, intent):
        loop = HealingLoop(max_attempts=2)
        page = MagicMock()

        async def action_fn(p, ctx):
            return "All good"

        result = await loop.try_with_healing(action_fn, page, {}, intent)
        assert result.status == TestStatus.PASSED
        assert result.healed is False

    @pytest.mark.asyncio
    async def test_healed_after_retry(self, intent):
        loop = HealingLoop(max_attempts=2)
        page = MagicMock()
        call_count = [0]

        # Mock accessibility snapshot for healing
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Root",
                "role": "root",
                "children": [
                    {"name": "Target Button", "role": "button"},
                ],
            }
        )

        async def action_fn(p, ctx):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Element not found")
            return "Found after healing"

        result = await loop.try_with_healing(
            action_fn,
            page,
            {"target_text": "Target", "selector": "#btn"},
            intent,
        )
        assert result.status == TestStatus.HEALED
        assert result.healed is True
        assert "Attempt 2" in (result.heal_details or "")
        assert len(loop.heal_log) >= 1

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self, intent):
        loop = HealingLoop(max_attempts=1)
        page = MagicMock()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(return_value=None)

        async def action_fn(p, ctx):
            raise ValueError("Always fails")

        result = await loop.try_with_healing(action_fn, page, {}, intent)
        assert result.status == TestStatus.FAILED
        assert "All" in (result.message or "")
        assert "2 attempts failed" in (result.message or "")

    @pytest.mark.asyncio
    async def test_heal_log_recorded_on_successful_heal(self, intent):
        loop = HealingLoop(max_attempts=2)
        page = MagicMock()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Test Button",
                "role": "button",
            }
        )
        call_count = [0]

        async def action_fn(p, ctx):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("fail")
            return "ok"

        await loop.try_with_healing(
            action_fn,
            page,
            {"target_text": "Test", "selector": "#btn"},
            intent,
        )
        assert len(loop.heal_log) >= 1
        entry = loop.heal_log[0]
        assert entry["original"] == "#btn"
        assert "healed" in entry
        assert "error" in entry


# ─── HealingLoopV2 ───────────────────────────────────────────────


class TestHealingLoopV2Init:
    def test_default_max_attempts(self):
        loop = HealingLoopV2()
        assert loop.max_attempts == 5
        assert loop._heal_memory == {}
        assert loop.heal_log == []

    def test_custom_max_attempts(self):
        loop = HealingLoopV2(max_attempts=3)
        assert loop.max_attempts == 3


class TestHealingLoopV2RecordHeal:
    def test_records_to_memory_and_log(self):
        loop = HealingLoopV2()
        heal_info = {
            "heal_strategy": "a11y_tree: role=button, name=Click",
            "selector": "#new-btn",
            "target_text": "Click",
        }
        loop._record_heal("#old-btn", heal_info)
        assert "#old-btn" in loop._heal_memory
        assert loop._heal_memory["#old-btn"]["healed"] == "a11y_tree: role=button, name=Click"
        assert loop._heal_memory["#old-btn"]["count"] == 1

    def test_increments_count_on_duplicate(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test", "selector": "", "target_text": ""}
        loop._record_heal("#btn", heal_info)
        loop._record_heal("#btn", heal_info)
        assert loop._heal_memory["#btn"]["count"] == 2

    def test_empty_original_skips_memory(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test", "selector": "", "target_text": ""}
        loop._record_heal("", heal_info)
        assert len(loop._heal_memory) == 0

    def test_appends_to_heal_log(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test_strategy", "selector": "", "target_text": ""}
        loop._record_heal("#btn", heal_info)
        assert len(loop.heal_log) == 1
        assert loop.heal_log[0]["original"] == "#btn"
        assert loop.heal_log[0]["healed"] == "test_strategy"


class TestHealingLoopV2GetHealStats:
    def test_empty_stats(self):
        loop = HealingLoopV2()
        stats = loop.get_heal_stats()
        assert stats["total_heals"] == 0
        assert stats["memory_entries"] == 0
        assert stats["strategies_used"] == []

    def test_with_heals(self):
        loop = HealingLoopV2()
        heal_info1 = {"heal_strategy": "a11y_tree: role=button, name=Click", "selector": "", "target_text": ""}
        heal_info2 = {"heal_strategy": "semantic_intent: #input, name=Search", "selector": "", "target_text": ""}
        loop._record_heal("#btn1", heal_info1)
        loop._record_heal("#btn2", heal_info2)

        stats = loop.get_heal_stats()
        assert stats["total_heals"] == 2
        assert stats["memory_entries"] == 2
        assert "a11y_tree" in stats["strategies_used"]
        assert "semantic_intent" in stats["strategies_used"]

    def test_memory_contains_count(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test", "selector": "", "target_text": ""}
        loop._record_heal("#btn", heal_info)
        loop._record_heal("#btn", heal_info)

        stats = loop.get_heal_stats()
        assert stats["memory"]["#btn"]["count"] == 2


class TestHealingLoopV2AnalyzeAndHeal:
    """_analyze_and_heal — heal_memory hit, semantic parser, a11y tree, bbox."""

    @pytest.mark.asyncio
    async def test_heal_memory_hit(self):
        loop = HealingLoopV2()
        loop._heal_memory["#old-btn"] = {
            "healed": "a11y_tree: role=button, name=Click",
            "healed_selector": "#new-btn",
            "healed_text": "Click",
            "count": 1,
            "timestamp": 1000.0,
        }
        page = MagicMock()
        result = await loop._analyze_and_heal(
            page,
            {"selector": "#old-btn", "target_text": "Click"},
            "Element not found",
        )
        assert result is not None
        assert result["heal_strategy"].startswith("heal_memory")
        assert "selector" in result

    @pytest.mark.asyncio
    async def test_semantic_parser_finds_element(self):
        loop = HealingLoopV2()
        page = MagicMock()

        mock_parser = MagicMock()
        mock_element = MagicMock()
        mock_element.ref = "ref-1"
        mock_element.css_selector = "#semantic-btn"
        mock_element.display_name = "Click Me"
        mock_element.role.value = "button"
        mock_parser.snapshot_async = AsyncMock(return_value=MagicMock())
        mock_parser.find_by_intent.return_value = mock_element

        with patch.object(loop, "_ensure_dom_parser", return_value=mock_parser):
            result = await loop._analyze_and_heal(
                page,
                {"selector": "#btn", "target_text": "Click"},
                "not found",
            )
        assert result is not None
        assert result["heal_strategy"].startswith("semantic_intent")

    @pytest.mark.asyncio
    async def test_a11y_tree_fallback(self):
        loop = HealingLoopV2()
        page = MagicMock()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Root",
                "role": "root",
                "children": [{"name": "Target Item", "role": "button"}],
            }
        )

        # Semantic parser not available
        with patch.object(loop, "_ensure_dom_parser", return_value=None):
            result = await loop._analyze_and_heal(
                page,
                {"selector": "#btn", "target_text": "Target"},
                "not found",
            )
        assert result is not None
        assert result["heal_strategy"].startswith("a11y_tree")

    @pytest.mark.asyncio
    async def test_bbox_fallback(self):
        loop = HealingLoopV2()
        page = MagicMock()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(return_value=None)  # No a11y tree

        mock_parser = MagicMock()
        mock_parser.find_by_intent.return_value = None  # Semantic parser doesn't find
        mock_snapshot = MagicMock()
        mock_element = MagicMock()
        mock_element.ref = "ref-bbox"
        mock_element.css_selector = "#bbox-btn"
        mock_element.display_name = "BBox Target"
        mock_element.bbox = MagicMock()
        mock_element.bbox.to_compact.return_value = "(100,200)-(150,250)"
        mock_snapshot.interactable_elements.return_value = [mock_element]
        mock_parser.snapshot_async = AsyncMock(return_value=mock_snapshot)

        with patch.object(loop, "_ensure_dom_parser", return_value=mock_parser):
            result = await loop._analyze_and_heal(
                page,
                {"selector": "#btn", "target_text": "Something"},
                "not found",
            )
        assert result is not None
        assert result["heal_strategy"].startswith("bbox")

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self):
        loop = HealingLoopV2()
        page = MagicMock()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(return_value=None)

        with patch.object(loop, "_ensure_dom_parser", return_value=None):
            result = await loop._analyze_and_heal(
                page,
                {"selector": "#btn", "target_text": "Nonexistent"},
                "not found",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_updated_on_successful_heal(self):
        loop = HealingLoopV2()
        page = MagicMock()
        page.accessibility = MagicMock()
        page.accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Root",
                "role": "root",
                "children": [{"name": "Target Item", "role": "button"}],
            }
        )

        with patch.object(loop, "_ensure_dom_parser", return_value=None):
            result = await loop._analyze_and_heal(
                page,
                {"selector": "#btn", "target_text": "Target"},
                "not found",
            )
        assert result is not None
        # Memory should be updated
        assert "#btn" in loop._heal_memory
        assert loop._heal_memory["#btn"]["healed"].startswith("a11y_tree")
