"""Tests for healing_loop.py — HealingLoop and HealingLoopV2.

Covers:
- HealingLoop.__init__, _find_candidates recursive search
- HealingLoop.try_with_healing: success, heal, all fail
- HealingLoopV2.__init__, _ensure_dom_parser, _record_heal, get_heal_stats
- HealingLoopV2._analyze_and_heal: heal_memory hit, semantic parser, a11y tree, bbox
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_k.engine.harness_models import TestIntent, TestResult, TestStatus
from antigravity_k.engine.healing_loop import HealingLoop, HealingLoopV2


def _find_candidates(loop: HealingLoop, node: Mapping[str, object], target: str) -> list[str]:
    finder = cast(Callable[[Mapping[str, object], str], list[str]], getattr(loop, "_find_candidates"))
    return finder(node, target)


def _try_with_healing(
    loop: HealingLoop,
    action: Callable[[object, dict[str, object]], Awaitable[str]],
    page: object,
    context: dict[str, object],
    intent: TestIntent,
) -> Awaitable[TestResult]:
    runner = cast(
        Callable[[Callable[..., object], object, dict[str, object], TestIntent], Awaitable[TestResult]],
        getattr(loop, "try_with_healing"),
    )
    return runner(action, page, context, intent)


def _analyze_and_heal(
    loop: HealingLoopV2,
    page: object,
    context: dict[str, object],
    error: str,
) -> Awaitable[dict[str, object] | None]:
    analyzer = cast(
        Callable[[object, dict[str, object], str], Awaitable[dict[str, object] | None]],
        getattr(loop, "_analyze_and_heal"),
    )
    return analyzer(page, context, error)


def _heal_memory(loop: HealingLoopV2) -> dict[str, dict[str, object]]:
    return cast(dict[str, dict[str, object]], getattr(loop, "_heal_memory"))


def _record_heal(loop: HealingLoopV2, original: str, info: Mapping[str, object]) -> None:
    recorder = cast(Callable[[str, Mapping[str, object]], None], getattr(loop, "_record_heal"))
    recorder(original, info)

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
        result = _find_candidates(loop, {}, "test")
        assert result == []

    def test_matching_name_in_root(self):
        loop = HealingLoop()
        node = {"name": "Submit Button", "role": "button"}
        result = _find_candidates(loop, node, "Submit")
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
        result = _find_candidates(loop, node, "Submit")
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
        result = _find_candidates(loop, node, "Save")
        assert len(result) == 2

    def test_no_match(self):
        loop = HealingLoop()
        node = {"name": "Cancel", "role": "button"}
        result = _find_candidates(loop, node, "Submit")
        assert result == []

    def test_case_insensitive_match(self):
        loop = HealingLoop()
        node = {"name": "SUBMIT BUTTON", "role": "button"}
        result = _find_candidates(loop, node, "submit")
        assert len(result) == 1

    def test_empty_target_text(self):
        loop = HealingLoop()
        node = {"name": "Anything", "role": "button"}
        result = _find_candidates(loop, node, "")
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
        result = _find_candidates(loop, node, "Deep")
        assert len(result) == 1
        assert "Deep Button" in result[0]

    def test_node_without_name(self):
        loop = HealingLoop()
        node = {"role": "separator"}
        result = _find_candidates(loop, node, "anything")
        assert result == []


class TestHealingLoopTryWithHealing:
    """try_with_healing — success, healed, all fail."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self, intent: TestIntent) -> None:
        loop = HealingLoop(max_attempts=2)
        page = MagicMock()

        async def action_fn(_p: object, _ctx: dict[str, object]) -> str:
            return "All good"

        result = await _try_with_healing(loop, action_fn, page, {}, intent)
        assert result.status == TestStatus.PASSED
        assert result.healed is False

    @pytest.mark.asyncio
    async def test_healed_after_retry(self, intent: TestIntent) -> None:
        loop = HealingLoop(max_attempts=2)
        page = MagicMock()
        call_count = [0]

        # Mock accessibility snapshot for healing
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Root",
                "role": "root",
                "children": [
                    {"name": "Target Button", "role": "button"},
                ],
            }
        )
        setattr(page, "accessibility", accessibility)

        async def action_fn(_p: object, _ctx: dict[str, object]) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Element not found")
            return "Found after healing"

        result = await _try_with_healing(
            loop,
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
    async def test_all_attempts_fail(self, intent: TestIntent) -> None:
        loop = HealingLoop(max_attempts=1)
        page = MagicMock()
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(return_value=None)
        setattr(page, "accessibility", accessibility)

        async def action_fn(_p: object, _ctx: dict[str, object]) -> str:
            raise ValueError("Always fails")

        result = await _try_with_healing(loop, action_fn, page, {}, intent)
        assert result.status == TestStatus.FAILED
        assert "All" in (result.message or "")
        assert "2 attempts failed" in (result.message or "")

    @pytest.mark.asyncio
    async def test_heal_log_recorded_on_successful_heal(self, intent: TestIntent) -> None:
        loop = HealingLoop(max_attempts=2)
        page = MagicMock()
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Test Button",
                "role": "button",
            }
        )
        setattr(page, "accessibility", accessibility)
        call_count = [0]

        async def action_fn(_p: object, _ctx: dict[str, object]) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("fail")
            return "ok"

        _ = await _try_with_healing(
            loop,
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
        assert _heal_memory(loop) == {}
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
        _record_heal(loop, "#old-btn", heal_info)
        memory = _heal_memory(loop)
        assert "#old-btn" in memory
        assert memory["#old-btn"]["healed"] == "a11y_tree: role=button, name=Click"
        assert memory["#old-btn"]["count"] == 1

    def test_increments_count_on_duplicate(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test", "selector": "", "target_text": ""}
        _record_heal(loop, "#btn", heal_info)
        _record_heal(loop, "#btn", heal_info)
        assert _heal_memory(loop)["#btn"]["count"] == 2

    def test_empty_original_skips_memory(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test", "selector": "", "target_text": ""}
        _record_heal(loop, "", heal_info)
        assert len(_heal_memory(loop)) == 0

    def test_appends_to_heal_log(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test_strategy", "selector": "", "target_text": ""}
        _record_heal(loop, "#btn", heal_info)
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
        _record_heal(loop, "#btn1", heal_info1)
        _record_heal(loop, "#btn2", heal_info2)

        stats = loop.get_heal_stats()
        assert stats["total_heals"] == 2
        assert stats["memory_entries"] == 2
        assert "a11y_tree" in stats["strategies_used"]
        assert "semantic_intent" in stats["strategies_used"]

    def test_memory_contains_count(self):
        loop = HealingLoopV2()
        heal_info = {"heal_strategy": "test", "selector": "", "target_text": ""}
        _record_heal(loop, "#btn", heal_info)
        _record_heal(loop, "#btn", heal_info)

        stats = loop.get_heal_stats()
        assert stats["memory"]["#btn"]["count"] == 2


class TestHealingLoopV2AnalyzeAndHeal:
    """_analyze_and_heal — heal_memory hit, semantic parser, a11y tree, bbox."""

    @pytest.mark.asyncio
    async def test_heal_memory_hit(self):
        loop = HealingLoopV2()
        _heal_memory(loop)["#old-btn"] = {
            "healed": "a11y_tree: role=button, name=Click",
            "healed_selector": "#new-btn",
            "healed_text": "Click",
            "count": 1,
            "timestamp": 1000.0,
        }
        page = MagicMock()
        result = await _analyze_and_heal(
            loop,
            page,
            {"selector": "#old-btn", "target_text": "Click"},
            "Element not found",
        )
        assert result is not None
        assert cast(str, result["heal_strategy"]).startswith("heal_memory")
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
        role = MagicMock()
        setattr(role, "value", "button")
        setattr(mock_element, "role", role)
        mock_parser.snapshot_async = AsyncMock(return_value=MagicMock())
        setattr(mock_parser, "find_by_intent", MagicMock(return_value=mock_element))

        with patch.object(loop, "_ensure_dom_parser", return_value=mock_parser):
            result = await _analyze_and_heal(
                loop,
                page,
                {"selector": "#btn", "target_text": "Click"},
                "not found",
            )
        assert result is not None
        assert cast(str, result["heal_strategy"]).startswith("semantic_intent")

    @pytest.mark.asyncio
    async def test_a11y_tree_fallback(self):
        loop = HealingLoopV2()
        page = MagicMock()
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Root",
                "role": "root",
                "children": [{"name": "Target Item", "role": "button"}],
            }
        )
        setattr(page, "accessibility", accessibility)

        # Semantic parser not available
        with patch.object(loop, "_ensure_dom_parser", return_value=None):
            result = await _analyze_and_heal(
                loop,
                page,
                {"selector": "#btn", "target_text": "Target"},
                "not found",
            )
        assert result is not None
        assert cast(str, result["heal_strategy"]).startswith("a11y_tree")

    @pytest.mark.asyncio
    async def test_bbox_fallback(self):
        loop = HealingLoopV2()
        page = MagicMock()
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(return_value=None)  # No a11y tree
        setattr(page, "accessibility", accessibility)

        mock_parser = MagicMock()
        setattr(mock_parser, "find_by_intent", MagicMock(return_value=None))  # Semantic parser doesn't find
        mock_snapshot = MagicMock()
        mock_element = MagicMock()
        mock_element.ref = "ref-bbox"
        mock_element.css_selector = "#bbox-btn"
        mock_element.display_name = "BBox Target"
        bbox = MagicMock()
        setattr(bbox, "to_compact", MagicMock(return_value="(100,200)-(150,250)"))
        setattr(mock_element, "bbox", bbox)
        setattr(mock_snapshot, "interactable_elements", MagicMock(return_value=[mock_element]))
        mock_parser.snapshot_async = AsyncMock(return_value=mock_snapshot)

        with patch.object(loop, "_ensure_dom_parser", return_value=mock_parser):
            result = await _analyze_and_heal(
                loop,
                page,
                {"selector": "#btn", "target_text": "Something"},
                "not found",
            )
        assert result is not None
        assert cast(str, result["heal_strategy"]).startswith("bbox")

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self):
        loop = HealingLoopV2()
        page = MagicMock()
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(return_value=None)
        setattr(page, "accessibility", accessibility)

        with patch.object(loop, "_ensure_dom_parser", return_value=None):
            result = await _analyze_and_heal(
                loop,
                page,
                {"selector": "#btn", "target_text": "Nonexistent"},
                "not found",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_updated_on_successful_heal(self):
        loop = HealingLoopV2()
        page = MagicMock()
        accessibility = MagicMock()
        accessibility.snapshot = AsyncMock(
            return_value={
                "name": "Root",
                "role": "root",
                "children": [{"name": "Target Item", "role": "button"}],
            }
        )
        setattr(page, "accessibility", accessibility)

        with patch.object(loop, "_ensure_dom_parser", return_value=None):
            result = await _analyze_and_heal(
                loop,
                page,
                {"selector": "#btn", "target_text": "Target"},
                "not found",
            )
        assert result is not None
        # Memory should be updated
        memory = _heal_memory(loop)
        assert "#btn" in memory
        assert cast(str, memory["#btn"]["healed"]).startswith("a11y_tree")
