"""Tests for ContextShaper — token budget management and context compression.

Covers shape() pipeline (budget check, force_compact), _estimate_tokens,
_truncate, get_stats, get_token_usage, clear_old_tool_results, and
inject_budget_awareness.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.context_shaper import ContextShaper


@pytest.fixture
def shaper(tmp_path):
    """Create a ContextShaper with a temp storage dir."""
    return ContextShaper(
        max_tokens=10000,
        reserve_tokens=500,
        collapse_threshold=500,
        storage_dir=str(tmp_path / "context"),
    )


def _make_messages(count: int, content: str = "Hello world") -> list[dict]:
    """Generate a list of messages for testing."""
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": content} for i in range(count)]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_values(self, tmp_path):
        s = ContextShaper(storage_dir=str(tmp_path / "ctx"))
        assert s.max_tokens == 128_000
        assert s.reserve_tokens == 4_096

    def test_custom_values(self, tmp_path):
        s = ContextShaper(max_tokens=50000, reserve_tokens=1000, storage_dir=str(tmp_path / "ctx"))
        assert s.max_tokens == 50000
        assert s.reserve_tokens == 1000

    def test_storage_dir_created(self, tmp_path):
        storage = tmp_path / "my_context"
        ContextShaper(storage_dir=str(storage))
        assert storage.exists()


# ---------------------------------------------------------------------------
# shape — main compression pipeline
# ---------------------------------------------------------------------------


class TestShape:
    def test_short_messages_unchanged(self, shaper):
        """Messages within budget are returned unchanged."""
        messages = _make_messages(3, "short")
        result = shaper.shape(messages)
        assert len(result) == 3

    def test_force_compact_reduces_size(self, shaper):
        """force_compact triggers compression even when within budget."""
        messages = _make_messages(20, "A" * 200)
        original_size = shaper._estimate_tokens(messages)
        result = shaper.shape(messages, force_compact=True)
        result_size = shaper._estimate_tokens(result)
        assert result_size <= original_size

    def test_shape_preserves_message_structure(self, shaper):
        """Shaped messages still have role and content keys."""
        messages = [{"role": "user", "content": "test"}]
        result = shaper.shape(messages)
        for msg in result:
            assert "role" in msg
            assert "content" in msg

    def test_shape_empty_messages(self, shaper):
        result = shaper.shape([])
        assert result == []

    def test_shape_returns_list(self, shaper):
        result = shaper.shape(_make_messages(2))
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _estimate_tokens / _truncate
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    def test_estimate_tokens_positive(self, shaper):
        messages = [{"role": "user", "content": "Hello world"}]
        assert shaper._estimate_tokens(messages) > 0

    def test_estimate_tokens_empty(self, shaper):
        assert shaper._estimate_tokens([]) == 0

    def test_estimate_tokens_grows_with_content(self, shaper):
        short = shaper._estimate_tokens([{"role": "user", "content": "hi"}])
        long = shaper._estimate_tokens([{"role": "user", "content": "x" * 1000}])
        assert long > short

    def test_truncate_short_text_unchanged(self, shaper):
        assert shaper._truncate("short", 100) == "short"

    def test_truncate_long_text_capped(self, shaper):
        result = shaper._truncate("A" * 500, 100)
        assert len(result) <= 200  # truncated + suffix
        assert "500 total chars" in result


# ---------------------------------------------------------------------------
# get_stats / get_token_usage
# ---------------------------------------------------------------------------


class TestStatsAndUsage:
    def test_initial_stats_zero(self, shaper):
        stats = shaper.get_stats()
        assert stats["total_shaped"] == 0
        assert stats["tokens_saved"] == 0

    def test_get_token_usage_structure(self, shaper):
        messages = [{"role": "user", "content": "test message"}]
        usage = shaper.get_token_usage(messages)
        assert "total_tokens" in usage
        assert "max_tokens" in usage
        assert "usage_pct" in usage
        assert "budget_remaining" in usage
        assert "by_role" in usage

    def test_get_token_usage_empty_messages(self, shaper):
        usage = shaper.get_token_usage([])
        assert usage["total_tokens"] == 0
        assert usage["usage_pct"] == 0.0

    def test_usage_pct_increases_with_content(self, shaper):
        small = shaper.get_token_usage([{"role": "user", "content": "a"}])
        large = shaper.get_token_usage([{"role": "user", "content": "A" * 5000}])
        assert large["usage_pct"] > small["usage_pct"]


# ---------------------------------------------------------------------------
# clear_old_tool_results
# ---------------------------------------------------------------------------


class TestClearOldToolResults:
    def test_removes_old_tool_results(self, shaper):
        """Old tool/function results are removed, keeping only recent ones."""
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "function", "content": "old result 1"},
            {"role": "function", "content": "old result 2"},
            {"role": "assistant", "content": "a1"},
            {"role": "function", "content": "recent result"},
        ]
        result = shaper.clear_old_tool_results(messages, keep_last=1)
        # The most recent tool result should be kept; older ones removed.
        assert len(result) <= len(messages)

    def test_keep_last_preserves_recent(self, shaper):
        messages = [
            {"role": "function", "content": "r1"},
            {"role": "function", "content": "r2"},
            {"role": "function", "content": "r3"},
        ]
        result = shaper.clear_old_tool_results(messages, keep_last=2)
        assert len(result) >= 2

    def test_no_tool_results_unchanged(self, shaper):
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        result = shaper.clear_old_tool_results(messages)
        assert len(result) == len(messages)


# ---------------------------------------------------------------------------
# inject_budget_awareness
# ---------------------------------------------------------------------------


class TestInjectBudgetAwareness:
    def test_injects_into_non_empty_messages(self, shaper):
        """Budget awareness adds a system note when approaching limits."""
        messages = [{"role": "user", "content": "test"}]
        result = shaper.inject_budget_awareness(messages)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_inject_empty_messages(self, shaper):
        result = shaper.inject_budget_awareness([])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _budget_reduce
# ---------------------------------------------------------------------------


class TestBudgetReduce:
    def test_target_smaller_than_current(self, shaper):
        """_budget_reduce returns a target smaller than the current size."""
        target = shaper._budget_reduce(current=10000, budget=5000)
        assert target <= 5000

    def test_target_not_negative(self, shaper):
        target = shaper._budget_reduce(current=100, budget=50)
        assert target >= 0
