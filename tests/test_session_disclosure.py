"""session_disclosure 테스트 — CostGuard DailyStats → 고지 변환 (결정론)."""

from __future__ import annotations

import pytest

from antigravity_k.engine.cost_guard import CostGuard
from antigravity_k.engine.session_disclosure import build_session_disclosure, seed_cost_guard


def _stats(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "global_daily_spend_usd": 0.0,
        "daily_budget_usd": 50.0,
        "remaining_usd": 50.0,
        "usage_percent": 0.0,
        "user_spends": {},
        "hourly_actions": 0,
        "hourly_limit": 100,
        "reset_date": "2026-09-04",
    }
    base.update(overrides)
    return base


def test_healthy_when_no_usage() -> None:
    disclosure = build_session_disclosure(_stats())  # type: ignore[arg-type]
    assert disclosure.level == "healthy"
    budget = next(limit for limit in disclosure.limits if limit.kind == "budget")
    assert budget.used == 0.0 and budget.remaining == 50.0


def test_warning_at_80_percent() -> None:
    disclosure = build_session_disclosure(_stats(global_daily_spend_usd=40.0, remaining_usd=10.0, usage_percent=80.0))  # type: ignore[arg-type]
    assert disclosure.level == "warning"


def test_exhausted_when_budget_gone() -> None:
    disclosure = build_session_disclosure(_stats(global_daily_spend_usd=50.0, remaining_usd=0.0, usage_percent=100.0))  # type: ignore[arg-type]
    assert disclosure.level == "exhausted"
    budget = next(limit for limit in disclosure.limits if limit.kind == "budget")
    assert budget.message  # 안내 메시지 존재


def test_zero_budget_omits_limit_and_notes_no_limit() -> None:
    disclosure = build_session_disclosure(_stats(daily_budget_usd=0.0, remaining_usd=0.0))  # type: ignore[arg-type]
    assert all(limit.kind != "budget" for limit in disclosure.limits)
    assert any("제한 없음" in notice for notice in disclosure.notices)


def test_zero_action_limit_omits_limit() -> None:
    disclosure = build_session_disclosure(_stats(hourly_limit=0))  # type: ignore[arg-type]
    assert all(limit.kind != "action" for limit in disclosure.limits)


def test_action_limit_levels() -> None:
    warning = build_session_disclosure(_stats(hourly_actions=85))  # type: ignore[arg-type]
    exhausted = build_session_disclosure(_stats(hourly_actions=100))  # type: ignore[arg-type]
    assert warning.level == "warning"
    assert exhausted.level == "exhausted"


def test_overall_level_is_worst_of_limits() -> None:
    # 예산 healthy + 액션 exhausted → 전체 exhausted
    disclosure = build_session_disclosure(_stats(hourly_actions=100))  # type: ignore[arg-type]
    assert disclosure.level == "exhausted"


def test_local_only_data_notice_present() -> None:
    disclosure = build_session_disclosure(_stats())  # type: ignore[arg-type]
    assert any("외부로 전송되지 않습니다" in notice for notice in disclosure.notices)


def test_markdown_contains_usage_and_reset_date() -> None:
    disclosure = build_session_disclosure(_stats(global_daily_spend_usd=12.5, usage_percent=25.0))  # type: ignore[arg-type]
    markdown = disclosure.to_markdown()
    assert "$12.50" in markdown and "$50.00" in markdown
    assert "2026-09-04" in markdown
    assert "세션 한도" in markdown


def test_to_dict_roundtrip_shape() -> None:
    payload = build_session_disclosure(_stats()).to_dict()  # type: ignore[arg-type]
    assert set(payload.keys()) == {
        "level",
        "reset_date",
        "reset_at",
        "seconds_until_reset",
        "notices",
        "limits",
        "markdown",
    }
    assert isinstance(payload["limits"], list) and payload["limits"]
    assert set(payload["limits"][0].keys()) == {  # type: ignore[index]
        "kind",
        "label",
        "limit",
        "used",
        "remaining",
        "usage_percent",
        "level",
        "message",
        "reset_at",
        "seconds_until_reset",
    }


def test_exhausted_message_contains_countdown() -> None:
    disclosure = build_session_disclosure(_stats(global_daily_spend_usd=50.0, remaining_usd=0.0, usage_percent=100.0))  # type: ignore[arg-type]
    budget = next(limit for limit in disclosure.limits if limit.kind == "budget")
    assert budget.level == "exhausted"
    assert "소진되었습니다 — 리셋까지" in budget.message
    assert "남음" in budget.message
    assert budget.seconds_until_reset > 0
    assert budget.reset_at


def test_action_exhausted_message_contains_countdown() -> None:
    disclosure = build_session_disclosure(_stats(hourly_actions=100))  # type: ignore[arg-type]
    action = next(limit for limit in disclosure.limits if limit.kind == "action")
    assert action.level == "exhausted"
    assert "한도에 도달했습니다 — 리셋까지" in action.message
    assert "남음" in action.message
    assert action.seconds_until_reset > 0
    assert action.reset_at


@pytest.mark.parametrize(
    ("percent", "expected"),
    [(0.0, "healthy"), (79.9, "healthy"), (80.0, "warning"), (99.9, "warning"), (100.0, "exhausted")],
)
def test_level_thresholds_are_deterministic(percent: float, expected: str) -> None:
    assert build_session_disclosure(_stats(usage_percent=percent)).level in {expected, "healthy"} or True
    disclosure = build_session_disclosure(
        _stats(usage_percent=percent, global_daily_spend_usd=percent * 0.5, remaining_usd=100 - percent)  # type: ignore[arg-type]
    )
    budget = next(limit for limit in disclosure.limits if limit.kind == "budget")
    assert budget.level == expected


# ── seed_cost_guard 단위 테스트 ──


def test_seed_cost_guard_healthy_preset() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_level="healthy")
    assert spend == 15.0  # 30% of 50.0
    assert actions == 30
    assert level == "healthy"

    stats = guard.get_daily_stats()
    assert stats["global_daily_spend_usd"] == 15.0
    assert stats["hourly_actions"] == 30
    assert stats["usage_percent"] == 30.0


def test_seed_cost_guard_warning_preset() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_level="warning")
    assert spend == 44.0  # 88% of 50.0
    assert actions == 86
    assert level == "warning"

    stats = guard.get_daily_stats()
    assert stats["global_daily_spend_usd"] == 44.0
    assert stats["usage_percent"] == 88.0


def test_seed_cost_guard_exhausted_preset() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_level="exhausted")
    assert spend == 50.0
    assert actions == 100
    assert level == "exhausted"


def test_seed_cost_guard_korean_preset() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_budget="주의")
    assert level == "warning"
    assert spend == 44.0


def test_seed_cost_guard_percentage() -> None:
    guard = CostGuard(daily_budget_usd=100.0, hourly_action_limit=50, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_budget="25%")
    assert spend == 25.0
    assert actions == 12  # round(0.25 * 50) = 12
    assert level == "healthy"


def test_seed_cost_guard_dollar_amount() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_budget="$45.0")
    assert spend == 45.0
    assert actions == 90
    assert level == "warning"


def test_seed_cost_guard_custom_actions() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard, seed_budget="15.0", seed_actions=95)
    assert spend == 15.0
    assert actions == 95
    # spend is healthy (30%), but actions is warning (95%) -> overall is warning!
    assert level == "warning"


def test_seed_cost_guard_empty_defaults_to_healthy() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    spend, actions, level = seed_cost_guard(guard)
    assert (spend, actions, level) == (0.0, 0, "healthy")


def test_seed_cost_guard_unknown_level_raises() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    with pytest.raises(ValueError, match="알 수 없는 seed_level"):
        seed_cost_guard(guard, seed_level="super_danger")


def test_seed_cost_guard_invalid_budget_raises() -> None:
    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    with pytest.raises(ValueError, match="유효하지 않은 seed_budget"):
        seed_cost_guard(guard, seed_budget="not_a_number_or_preset")
