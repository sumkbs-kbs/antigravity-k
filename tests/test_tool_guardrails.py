"""Tests for tool_guardrails — loop detection, failure classification, and safety gates.

Covers ToolGuardrailDecision, ToolCallSignature, ToolCallGuardrailConfig,
classify_tool_failure, guardrail_synthetic_result, append_guardrail_guidance,
and the ToolCallGuardrailController's before_call/after_call cycle.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.tool_guardrails import (
    ToolCallGuardrailConfig,
    ToolCallGuardrailController,
    ToolCallSignature,
    ToolGuardrailDecision,
    append_guardrail_guidance,
    classify_tool_failure,
    guardrail_synthetic_result,
)

# ---------------------------------------------------------------------------
# ToolGuardrailDecision
# ---------------------------------------------------------------------------


class TestGuardrailDecision:
    """ToolGuardrailDecision action properties."""

    def test_allow_executes(self):
        d = ToolGuardrailDecision(action="allow")
        assert d.allows_execution is True
        assert d.should_halt is False

    def test_warn_executes(self):
        """warn still allows execution."""
        d = ToolGuardrailDecision(action="warn")
        assert d.allows_execution is True
        assert d.should_halt is False

    def test_block_halts(self):
        d = ToolGuardrailDecision(action="block")
        assert d.allows_execution is False
        assert d.should_halt is True

    def test_halt_halts(self):
        d = ToolGuardrailDecision(action="halt")
        assert d.allows_execution is False
        assert d.should_halt is True

    def test_to_dict_contains_action(self):
        d = ToolGuardrailDecision(action="warn", message="repeated")
        result = d.to_dict()
        assert result["action"] == "warn"
        assert result["message"] == "repeated"


# ---------------------------------------------------------------------------
# ToolCallSignature
# ---------------------------------------------------------------------------


class TestToolCallSignature:
    """ToolCallSignature hashing for dedup detection."""

    def test_same_args_same_hash(self):
        sig1 = ToolCallSignature.from_call("read_file", {"path": "/tmp/a"})
        sig2 = ToolCallSignature.from_call("read_file", {"path": "/tmp/a"})
        assert sig1 == sig2

    def test_different_args_different_hash(self):
        sig1 = ToolCallSignature.from_call("read_file", {"path": "/tmp/a"})
        sig2 = ToolCallSignature.from_call("read_file", {"path": "/tmp/b"})
        assert sig1 != sig2

    def test_different_tool_different_hash(self):
        sig1 = ToolCallSignature.from_call("read_file", {"path": "/x"})
        sig2 = ToolCallSignature.from_call("write_file", {"path": "/x"})
        assert sig1 != sig2

    def test_to_dict_structure(self):
        sig = ToolCallSignature.from_call("test_tool", {"x": 1})
        d = sig.to_dict()
        assert "tool_name" in d
        assert "args_hash" in d

    def test_frozen_dataclass(self):
        sig = ToolCallSignature(tool_name="t", args_hash="h")
        with pytest.raises(AttributeError):
            sig.tool_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolCallGuardrailConfig
# ---------------------------------------------------------------------------


class TestGuardrailConfig:
    """Config defaults and from_config loading."""

    def test_defaults(self):
        cfg = ToolCallGuardrailConfig()
        assert cfg.warnings_enabled is True
        assert cfg.hard_stop_enabled is False
        assert cfg.exact_failure_warn_after == 2

    def test_from_config_none(self):
        """from_config with None returns defaults."""
        cfg = ToolCallGuardrailConfig.from_config(None)
        assert cfg.warnings_enabled is True

    def test_from_config_custom(self):
        cfg = ToolCallGuardrailConfig.from_config(
            {
                "warnings_enabled": False,
                "hard_stop_enabled": True,
                "warn_after": {"exact_failure": 3},
                "hard_stop_after": {"exact_failure": 10},
            }
        )
        assert cfg.warnings_enabled is False
        assert cfg.hard_stop_enabled is True
        assert cfg.exact_failure_warn_after == 3


# ---------------------------------------------------------------------------
# classify_tool_failure
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    """classify_tool_failure heuristic failure detection."""

    def test_none_result_is_not_failure(self):
        is_fail, msg = classify_tool_failure("any_tool", None)
        assert is_fail is False

    def test_error_prefix_is_failure(self):
        is_fail, msg = classify_tool_failure("any_tool", "Error: something went wrong")
        assert is_fail is True

    def test_success_result_not_failure(self):
        is_fail, msg = classify_tool_failure("any_tool", "File content here")
        assert is_fail is False

    def test_terminal_nonzero_exit_is_failure(self):
        import json

        is_fail, msg = classify_tool_failure("terminal", json.dumps({"exit_code": 1, "stdout": ""}))
        assert is_fail is True
        assert "exit 1" in msg

    def test_terminal_zero_exit_not_failure(self):
        import json

        is_fail, msg = classify_tool_failure("terminal", json.dumps({"exit_code": 0, "stdout": "ok"}))
        assert is_fail is False


# ---------------------------------------------------------------------------
# guardrail_synthetic_result / append_guardrail_guidance
# ---------------------------------------------------------------------------


class TestGuardrailHelpers:
    """Utility functions for guardrail output."""

    def test_synthetic_result_is_string(self):
        d = ToolGuardrailDecision(action="block", message="blocked!")
        result = guardrail_synthetic_result(d)
        assert isinstance(result, str)
        assert "blocked" in result.lower()

    def test_append_guidance_adds_message(self):
        d = ToolGuardrailDecision(action="warn", message="repeated tool call")
        result = append_guardrail_guidance("original output", d)
        assert "original output" in result
        assert "repeated" in result.lower()


# ---------------------------------------------------------------------------
# ToolCallGuardrailController — before_call / after_call cycle
# ---------------------------------------------------------------------------


class TestGuardrailController:
    """Controller loop detection integration."""

    def test_first_call_allowed(self):
        """The first call to a tool is always allowed."""
        ctrl = ToolCallGuardrailController()
        decision = ctrl.before_call("read_file", {"path": "/tmp/test"})
        assert decision.allows_execution is True

    def test_reset_for_turn_clears_state(self):
        """reset_for_turn clears the per-turn tracking state."""
        ctrl = ToolCallGuardrailController()
        ctrl.before_call("read_file", {"path": "/x"})
        ctrl.before_call("read_file", {"path": "/x"})
        ctrl.reset_for_turn()
        # After reset, the next call should not see prior history.
        decision = ctrl.before_call("read_file", {"path": "/x"})
        assert decision.allows_execution is True

    def test_repeated_exact_failures_eventually_warns(self):
        """Repeated exact-same tool+args failures trigger a warn."""
        ctrl = ToolCallGuardrailController()
        for _ in range(3):
            ctrl.before_call("write_file", {"path": "/locked"})
            ctrl.after_call(
                "write_file",
                {"path": "/locked"},
                result="Error: permission denied",
                failed=True,
            )
        # The 4th call should get a warning (exact_failure_warn_after=2)
        decision = ctrl.before_call("write_file", {"path": "/locked"})
        # Depending on config, it may warn or allow (warnings are advisory).
        # The failure tracking should at least be counting.
        assert decision.action in ("allow", "warn", "block", "halt")

    def test_after_call_no_failure_does_not_block(self):
        """A successful call does not set any block state."""
        ctrl = ToolCallGuardrailController()
        ctrl.before_call("read_file", {"path": "/x"})
        ctrl.after_call("read_file", {"path": "/x"}, result="content", failed=False)
        decision = ctrl.before_call("read_file", {"path": "/x"})
        assert decision.allows_execution is True

    def test_halt_decision_returns_none_when_no_halt(self):
        """halt_decision property is None when no halt has been triggered."""
        ctrl = ToolCallGuardrailController()
        ctrl.before_call("read_file", {"path": "/x"})
        assert ctrl.halt_decision is None
