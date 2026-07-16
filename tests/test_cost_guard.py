"""Tests for CostGuard — budget tracking and rate limiting for LLM calls.

Covers CostDecision, SpendRecord, CostGuard budget checks, spend recording,
rate limiting, daily reset, and dashboard data.
"""

from __future__ import annotations

from antigravity_k.engine.cost_guard import (
    CostDecision,
    CostGuard,
    SpendRecord,
)

# ---------------------------------------------------------------------------
# CostDecision
# ---------------------------------------------------------------------------


class TestCostDecision:
    """CostDecision properties."""

    def test_budget_usage_zero_when_no_spend(self):
        d = CostDecision(daily_spend_usd=0, remaining_budget_usd=50)
        assert d.budget_usage_percent == 0.0

    def test_budget_usage_50_percent(self):
        d = CostDecision(daily_spend_usd=25, remaining_budget_usd=25)
        assert d.budget_usage_percent == 50.0

    def test_budget_usage_100_when_no_remaining(self):
        d = CostDecision(daily_spend_usd=50, remaining_budget_usd=0)
        assert d.budget_usage_percent == 100.0

    def test_budget_usage_zero_when_both_zero(self):
        d = CostDecision(daily_spend_usd=0, remaining_budget_usd=0)
        assert d.budget_usage_percent == 0.0

    def test_default_allowed(self):
        d = CostDecision()
        assert d.allowed is True


# ---------------------------------------------------------------------------
# SpendRecord
# ---------------------------------------------------------------------------


class TestSpendRecord:
    """SpendRecord dataclass."""

    def test_creation(self):
        r = SpendRecord(timestamp=1000.0, cost_usd=0.01, model="test")
        assert r.cost_usd == 0.01
        assert r.model == "test"
        assert r.user_id == "default"

    def test_defaults(self):
        r = SpendRecord(timestamp=0, cost_usd=0)
        assert r.tokens_in == 0
        assert r.tokens_out == 0


# ---------------------------------------------------------------------------
# CostGuard — budget checking
# ---------------------------------------------------------------------------


class TestCheckBudget:
    """CostGuard.check_budget logic."""

    def test_allows_within_budget(self):
        """A call within budget is allowed."""
        guard = CostGuard(daily_budget_usd=10.0)
        decision = guard.check_budget(tokens_in=100, tokens_out=50)
        assert decision.allowed is True

    def test_blocks_when_budget_exceeded(self):
        """After spending the full budget, further calls with real pricing are blocked."""
        guard = CostGuard(daily_budget_usd=0.001, user_daily_budget_usd=0.001)
        guard.record_spend(0.001)
        # Use a priced model so _estimate_cost > 0.
        decision = guard.check_budget(model="gpt-4o", tokens_in=10000, tokens_out=10000)
        assert decision.allowed is False
        assert "예산" in decision.reason

    def test_disabled_guard_always_allows(self):
        """A disabled guard always allows."""
        guard = CostGuard(enabled=False)
        decision = guard.check_budget(tokens_in=999999, tokens_out=999999)
        assert decision.allowed is True
        assert "disabled" in decision.reason

    def test_user_budget_blocks(self):
        """A user-specific budget can block even if global budget remains."""
        # Use a model that has pricing (gpt-4o) so _estimate_cost > 0.
        guard = CostGuard(daily_budget_usd=10000, user_daily_budget_usd=0.0001)
        decision = guard.check_budget(model="gpt-4o", tokens_in=100000, tokens_out=100000, user_id="test-user")
        assert decision.allowed is False
        assert "test-user" in decision.reason

    def test_decision_contains_estimated_cost(self):
        """The decision includes the estimated cost for a priced model."""
        guard = CostGuard(daily_budget_usd=10000)
        decision = guard.check_budget(model="gpt-4o", tokens_in=1000, tokens_out=500)
        assert decision.estimated_cost_usd > 0

    def test_decision_contains_remaining_budget(self):
        guard = CostGuard(daily_budget_usd=100)
        decision = guard.check_budget(tokens_in=100, tokens_out=100)
        assert decision.remaining_budget_usd > 0
        assert decision.remaining_budget_usd <= 100


# ---------------------------------------------------------------------------
# CostGuard — rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    """Hourly action rate limiting."""

    def test_rate_limit_blocks_excess(self):
        """Exceeding the hourly action limit blocks further calls."""
        guard = CostGuard(daily_budget_usd=10000, hourly_action_limit=3)
        # Exhaust the limit
        for _ in range(3):
            d = guard.check_budget(tokens_in=1, tokens_out=1)
            assert d.allowed is True
        # 4th should be blocked
        d = guard.check_budget(tokens_in=1, tokens_out=1)
        assert d.allowed is False
        assert "시간당" in d.reason or "액션" in d.reason

    def test_rate_limit_decision_has_hourly_count(self):
        """The decision includes the hourly action count."""
        guard = CostGuard(hourly_action_limit=100)
        d = guard.check_budget(tokens_in=10, tokens_out=10)
        assert d.hourly_actions >= 1
        assert d.hourly_limit == 100


# ---------------------------------------------------------------------------
# CostGuard — spend recording
# ---------------------------------------------------------------------------


class TestRecordSpend:
    """CostGuard.record_spend tracking."""

    def test_record_increases_global_spend(self):
        guard = CostGuard(daily_budget_usd=100)
        guard.record_spend(5.0)
        assert guard._global_daily_spend == 5.0

    def test_record_tracks_per_user(self):
        guard = CostGuard(daily_budget_usd=100, user_daily_budget_usd=50)
        guard.record_spend(3.0, user_id="alice")
        guard.record_spend(2.0, user_id="bob")
        assert guard._user_daily_spend["alice"] == 3.0
        assert guard._user_daily_spend["bob"] == 2.0

    def test_get_remaining_budget(self):
        """get_remaining_budget returns min(global_remaining, user_remaining)."""
        guard = CostGuard(daily_budget_usd=100, user_daily_budget_usd=100)
        guard.record_spend(30)
        assert guard.get_remaining_budget() == 70.0

    def test_get_remaining_budget_zero_when_exhausted(self):
        guard = CostGuard(daily_budget_usd=10, user_daily_budget_usd=10)
        guard.record_spend(15)
        assert guard.get_remaining_budget() == 0.0

    def test_spend_history_capped(self):
        """Spend history is capped at 5000 entries (trimmed to 2500)."""
        guard = CostGuard(daily_budget_usd=1e9)
        for i in range(5001):
            guard.record_spend(0.001, model=f"model-{i}")
        assert len(guard._spend_history) <= 5000

    def test_record_spend_creates_spend_record(self):
        guard = CostGuard()
        guard.record_spend(0.5, model="gpt-4", tokens_in=100, tokens_out=50)
        assert len(guard._spend_history) == 1
        record = guard._spend_history[0]
        assert record.cost_usd == 0.5
        assert record.model == "gpt-4"
        assert record.tokens_in == 100


# ---------------------------------------------------------------------------
# CostGuard — dashboard/stats
# ---------------------------------------------------------------------------


class TestStatsAndDashboard:
    """Daily stats and dashboard data."""

    def test_daily_stats_structure(self):
        guard = CostGuard(daily_budget_usd=100)
        guard.record_spend(10)
        stats = guard.get_daily_stats()
        assert "daily_spend_usd" in stats or "global_daily_spend" in stats or "spend" in str(stats).lower()

    def test_to_dashboard_data_structure(self):
        guard = CostGuard(daily_budget_usd=100, hourly_action_limit=50)
        guard.record_spend(5)
        data = guard.to_dashboard_data()
        assert isinstance(data, dict)

    def test_empty_guard_stats(self):
        """A fresh guard has zero spend in stats."""
        guard = CostGuard(daily_budget_usd=100, user_daily_budget_usd=100)
        remaining = guard.get_remaining_budget()
        assert remaining == 100.0
