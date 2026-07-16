"""Tests for EventBus, ExecutionMode, and SamplingProfile.

These are foundational modules used across the entire engine:
- EventBus: pub/sub with sync and async callback support.
- ExecutionMode: PLAN/BUILD/INTERACTIVE mode tool-gating enum.
- SamplingProfile: temperature/sampling config presets.
"""

from __future__ import annotations

import asyncio

from antigravity_k.engine.event_bus import EventBus
from antigravity_k.engine.execution_mode import (
    BUILD_RESTRICTED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    ExecutionMode,
)
from antigravity_k.engine.sampling_config import SAMPLING_PROFILES, SamplingProfile

# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class TestEventBusSync:
    """EventBus synchronous publish/subscribe."""

    def test_subscribe_and_publish(self):
        """A subscribed callback is called on publish."""
        bus = EventBus()
        received = []
        bus.subscribe("test_event", lambda **kw: received.append(kw))
        bus.publish("test_event", key="value")
        assert received == [{"key": "value"}]

    def test_unsubscribe_removes_callback(self):
        """After unsubscribe, the callback is not called."""
        bus = EventBus()
        received = []
        cb = lambda **kw: received.append(kw)  # noqa: E731
        bus.subscribe("evt", cb)
        bus.unsubscribe("evt", cb)
        bus.publish("evt", x=1)
        assert received == []

    def test_publish_no_subscribers_is_noop(self):
        """Publishing an event with no subscribers does nothing."""
        bus = EventBus()
        bus.publish("nonexistent", a=1)  # should not raise

    def test_multiple_subscribers_all_called(self):
        """Multiple subscribers for the same event are all called."""
        bus = EventBus()
        calls = []
        bus.subscribe("evt", lambda **kw: calls.append("first"))
        bus.subscribe("evt", lambda **kw: calls.append("second"))
        bus.publish("evt")
        assert calls == ["first", "second"]

    def test_subscribe_is_idempotent(self):
        """Subscribing the same callback twice does not duplicate it."""
        bus = EventBus()
        calls = []
        cb = lambda **kw: calls.append(1)  # noqa: E731
        bus.subscribe("evt", cb)
        bus.subscribe("evt", cb)  # duplicate
        bus.publish("evt")
        assert len(calls) == 1

    def test_failing_callback_does_not_propagate(self):
        """A callback that raises does not crash publish."""
        bus = EventBus()
        calls = []
        bus.subscribe("evt", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))  # noqa: E731
        bus.subscribe("evt", lambda **kw: calls.append("survived"))  # noqa: E731
        bus.publish("evt")
        assert calls == ["survived"]

    def test_unsubscribe_nonexistent_is_noop(self):
        """Unsubscribing from a nonexistent event or callback is safe."""
        bus = EventBus()
        bus.unsubscribe("nonexistent", lambda **kw: None)


class TestEventBusAsync:
    """EventBus async callback support."""

    def test_async_callback_called(self):
        """An async coroutine callback is invoked on publish."""
        bus = EventBus()
        received = []

        async def async_cb(**kw):
            received.append(kw)

        bus.subscribe("evt", async_cb)
        bus.publish("evt", val=42)
        # The async callback runs via asyncio.run inside publish (no running loop in test).
        assert received == [{"val": 42}]

    def test_publish_async_gathers_coroutines(self):
        """publish_async awaits all async callbacks."""
        bus = EventBus()
        results = []

        async def cb1(**kw):
            results.append("cb1")

        async def cb2(**kw):
            results.append("cb2")

        bus.subscribe("evt", cb1)
        bus.subscribe("evt", cb2)

        asyncio.run(bus.publish_async("evt"))
        assert "cb1" in results
        assert "cb2" in results


# ---------------------------------------------------------------------------
# ExecutionMode
# ---------------------------------------------------------------------------


class TestExecutionMode:
    """ExecutionMode enum properties and tool gating."""

    def test_plan_is_plan(self):
        assert ExecutionMode.PLAN.is_plan is True
        assert ExecutionMode.PLAN.is_build is False
        assert ExecutionMode.PLAN.is_interactive is False

    def test_build_is_build(self):
        assert ExecutionMode.BUILD.is_build is True
        assert ExecutionMode.BUILD.is_plan is False

    def test_interactive_is_interactive(self):
        assert ExecutionMode.INTERACTIVE.is_interactive is True

    def test_string_enum_equality(self):
        """ExecutionMode values are comparable to strings."""
        assert ExecutionMode.PLAN == "plan"
        assert ExecutionMode.BUILD == "build"
        assert ExecutionMode.INTERACTIVE == "interactive"


class TestPlanAllowedTools:
    """PLAN mode tool permissions."""

    def test_read_file_allowed_in_plan(self):
        assert "read_file" in PLAN_ALLOWED_TOOLS
        assert ExecutionMode.PLAN.tool_is_allowed("read_file") is True

    def test_write_file_blocked_in_plan(self):
        assert ExecutionMode.PLAN.tool_is_allowed("write_file") is False

    def test_web_search_allowed_in_plan(self):
        assert ExecutionMode.PLAN.tool_is_allowed("web_search") is True

    def test_write_artifact_allowed_in_plan(self):
        assert "write_artifact" in PLAN_ALLOWED_TOOLS

    def test_plan_never_requires_approval(self):
        """PLAN mode blocks tools outright, never requires approval."""
        assert ExecutionMode.PLAN.tool_requires_approval("write_file") is False
        assert ExecutionMode.PLAN.tool_requires_approval("read_file") is False

    def test_get_block_reason_for_blocked_tool(self):
        """get_block_reason returns a message for blocked tools in PLAN mode."""
        reason = ExecutionMode.PLAN.get_block_reason("write_file")
        assert "write_file" in reason
        assert reason != ""

    def test_get_block_reason_empty_for_allowed_tool(self):
        """get_block_reason returns empty string for allowed tools in PLAN mode."""
        reason = ExecutionMode.PLAN.get_block_reason("read_file")
        assert reason == ""


class TestBuildMode:
    """BUILD mode tool permissions."""

    def test_all_tools_allowed_in_build(self):
        """BUILD mode allows all tools (restricted ones need approval)."""
        assert ExecutionMode.BUILD.tool_is_allowed("write_file") is True
        assert ExecutionMode.BUILD.tool_is_allowed("read_file") is True

    def test_restricted_tools_require_approval(self):
        """BUILD_RESTRICTED_TOOLS require approval in BUILD mode."""
        assert "db_migration" in BUILD_RESTRICTED_TOOLS
        assert ExecutionMode.BUILD.tool_requires_approval("db_migration") is True

    def test_non_restricted_no_approval_in_build(self):
        assert ExecutionMode.BUILD.tool_requires_approval("write_file") is False

    def test_get_block_reason_empty_in_build(self):
        """get_block_reason returns empty string in BUILD mode."""
        assert ExecutionMode.BUILD.get_block_reason("write_file") == ""


class TestInteractiveMode:
    """INTERACTIVE mode tool permissions."""

    def test_all_tools_allowed(self):
        assert ExecutionMode.INTERACTIVE.tool_is_allowed("write_file") is True
        assert ExecutionMode.INTERACTIVE.tool_is_allowed("anything") is True

    def test_no_approval_required(self):
        assert ExecutionMode.INTERACTIVE.tool_requires_approval("write_file") is False

    def test_no_block_reason(self):
        assert ExecutionMode.INTERACTIVE.get_block_reason("write_file") == ""


# ---------------------------------------------------------------------------
# SamplingProfile
# ---------------------------------------------------------------------------


class TestSamplingProfiles:
    """SAMPLING_PROFILES preset configuration."""

    def test_all_expected_keys_present(self):
        expected = {"SEARCH", "CODE", "ANALYSIS", "CREATIVE", "GENERAL"}
        assert expected == set(SAMPLING_PROFILES.keys())

    def test_search_profile_low_temperature(self):
        """SEARCH profile has the lowest temperature (hallucination minimization)."""
        assert SAMPLING_PROFILES["SEARCH"].temperature == 0.15

    def test_creative_profile_high_temperature(self):
        """CREATIVE profile has the highest temperature."""
        assert SAMPLING_PROFILES["CREATIVE"].temperature == 0.7

    def test_code_profile(self):
        p = SAMPLING_PROFILES["CODE"]
        assert p.temperature == 0.25
        assert p.description != ""

    def test_all_profiles_have_descriptions(self):
        """Every profile has a non-empty description."""
        for name, profile in SAMPLING_PROFILES.items():
            assert profile.description, f"{name} has empty description"

    def test_all_temperatures_in_valid_range(self):
        """All temperatures are between 0 and 1."""
        for profile in SAMPLING_PROFILES.values():
            assert 0 <= profile.temperature <= 1

    def test_dataclass_equality(self):
        """SamplingProfile supports dataclass equality."""
        p1 = SamplingProfile(temperature=0.5, min_p=0.05, repeat_penalty=1.3)
        p2 = SamplingProfile(temperature=0.5, min_p=0.05, repeat_penalty=1.3)
        assert p1 == p2

    def test_default_top_p(self):
        """The default top_p is 0.9."""
        p = SamplingProfile(temperature=0.5, min_p=0.05, repeat_penalty=1.3)
        assert p.top_p == 0.9
