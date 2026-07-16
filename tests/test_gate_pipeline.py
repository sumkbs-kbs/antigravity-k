"""Tests for the GatePipeline — priority-based multi-stage tool gating.

Covers GateDecision/GateAction/GateContext data structures, GatePipeline
(priority sorting, short-circuit evaluation, fail-open on gate errors),
and individual gates (RateLimitGate, CostBudgetGate, ApprovalGate).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.gate_pipeline import (
    GateAction,
    GateContext,
    GateDecision,
    GatePipeline,
    RateLimitGate,
    ResumeKind,
)

# ---------------------------------------------------------------------------
# GateDecision / GateAction
# ---------------------------------------------------------------------------


class TestGateDecision:
    """GateDecision computed properties and serialization."""

    def test_default_is_allow(self):
        d = GateDecision()
        assert d.action == GateAction.ALLOW
        assert d.is_allowed is True
        assert d.is_paused is False
        assert d.is_denied is False

    def test_pause_decision(self):
        d = GateDecision(action=GateAction.PAUSE, resume_kind=ResumeKind.APPROVAL)
        assert d.is_paused is True
        assert d.is_allowed is False

    def test_deny_decision(self):
        d = GateDecision(action=GateAction.DENY, reason="blocked")
        assert d.is_denied is True
        assert d.is_allowed is False

    def test_to_dict_contains_action(self):
        d = GateDecision(action=GateAction.DENY, reason="test", gate_name="mygate")
        result = d.to_dict()
        assert result["action"] == "deny"
        assert result["reason"] == "test"
        assert result["gate_name"] == "mygate"

    def test_to_dict_resume_kind_none(self):
        d = GateDecision(action=GateAction.ALLOW)
        assert d.to_dict()["resume_kind"] is None

    def test_to_dict_resume_kind_approval(self):
        d = GateDecision(action=GateAction.PAUSE, resume_kind=ResumeKind.APPROVAL)
        assert d.to_dict()["resume_kind"] == "approval"

    def test_allow_always_flag(self):
        d = GateDecision(allow_always=True)
        assert d.allow_always is True
        assert d.to_dict()["allow_always"] is True

    def test_frozen_dataclass(self):
        """GateDecision is frozen — attributes cannot be reassigned."""
        d = GateDecision()
        with pytest.raises(AttributeError):
            d.action = GateAction.DENY  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GateContext
# ---------------------------------------------------------------------------


class TestGateContext:
    """GateContext construction and defaults."""

    def test_minimal_context(self):
        ctx = GateContext(tool_name="read_file")
        assert ctx.tool_name == "read_file"
        assert ctx.execution_mode == "interactive"
        assert ctx.user_id == "default"

    def test_full_context(self):
        ctx = GateContext(
            tool_name="write_file",
            args={"path": "/tmp/x"},
            execution_mode="autonomous",
            user_id="agent-1",
            session_id="sess-123",
        )
        assert ctx.execution_mode == "autonomous"
        assert ctx.user_id == "agent-1"
        assert ctx.session_id == "sess-123"

    def test_auto_approved_tools(self):
        ctx = GateContext(
            tool_name="x",
            auto_approved_tools=frozenset({"read_file", "grep"}),
        )
        assert "read_file" in ctx.auto_approved_tools


# ---------------------------------------------------------------------------
# GatePipeline
# ---------------------------------------------------------------------------


class TestGatePipeline:
    """GatePipeline priority sorting and short-circuit evaluation."""

    def test_empty_pipeline_allows_everything(self):
        """A pipeline with no gates returns ALLOW."""
        pipeline = GatePipeline()
        ctx = GateContext(tool_name="any_tool")
        decision = pipeline.evaluate(ctx)
        assert decision.is_allowed

    def test_single_allowing_gate(self):
        """A gate that returns ALLOW lets the pipeline pass."""
        gate = MagicMock()
        gate.name.return_value = "test_gate"
        gate.priority.return_value = 10
        gate.evaluate.return_value = GateDecision(action=GateAction.ALLOW)

        pipeline = GatePipeline().add_gate(gate)
        decision = pipeline.evaluate(GateContext(tool_name="x"))
        assert decision.is_allowed

    def test_single_denying_gate_short_circuits(self):
        """A gate that returns DENY short-circuits the pipeline."""
        gate = MagicMock()
        gate.name.return_value = "blocker"
        gate.priority.return_value = 10
        gate.evaluate.return_value = GateDecision(action=GateAction.DENY, reason="no")

        pipeline = GatePipeline().add_gate(gate)
        decision = pipeline.evaluate(GateContext(tool_name="x"))
        assert decision.is_denied
        assert decision.reason == "no"

    def test_priority_ordering(self):
        """Gates are evaluated in priority order (lower number = higher priority)."""
        call_order = []

        gate_low = MagicMock()
        gate_low.name.return_value = "high_priority"
        gate_low.priority.return_value = 1
        gate_low.evaluate.side_effect = lambda ctx: call_order.append("first") or GateDecision()

        gate_high = MagicMock()
        gate_high.name.return_value = "low_priority"
        gate_high.priority.return_value = 100
        gate_high.evaluate.side_effect = lambda ctx: call_order.append("second") or GateDecision()

        pipeline = GatePipeline().add_gate(gate_high).add_gate(gate_low)
        pipeline.evaluate(GateContext(tool_name="x"))

        assert call_order == ["first", "second"]

    def test_short_circuit_skips_lower_priority(self):
        """When a high-priority gate denies, lower-priority gates are not called."""
        gate1 = MagicMock()
        gate1.name.return_value = "gate1"
        gate1.priority.return_value = 1
        gate1.evaluate.return_value = GateDecision(action=GateAction.DENY)

        gate2 = MagicMock()
        gate2.name.return_value = "gate2"
        gate2.priority.return_value = 2
        gate2.evaluate.return_value = GateDecision()

        pipeline = GatePipeline().add_gate(gate2).add_gate(gate1)
        pipeline.evaluate(GateContext(tool_name="x"))

        gate2.evaluate.assert_not_called()

    def test_gate_error_fail_open(self):
        """If a gate raises an exception, the pipeline continues (fail-open)."""
        bad_gate = MagicMock()
        bad_gate.name.return_value = "bad"
        bad_gate.priority.return_value = 1
        bad_gate.evaluate.side_effect = RuntimeError("gate crashed")

        good_gate = MagicMock()
        good_gate.name.return_value = "good"
        good_gate.priority.return_value = 2
        good_gate.evaluate.return_value = GateDecision(action=GateAction.ALLOW)

        pipeline = GatePipeline().add_gate(bad_gate).add_gate(good_gate)
        decision = pipeline.evaluate(GateContext(tool_name="x"))
        assert decision.is_allowed

    def test_list_gates(self):
        """list_gates returns name and priority of each gate."""
        g1 = MagicMock()
        g1.name.return_value = "alpha"
        g1.priority.return_value = 5
        g2 = MagicMock()
        g2.name.return_value = "beta"
        g2.priority.return_value = 10

        pipeline = GatePipeline().add_gate(g1).add_gate(g2)
        gates = pipeline.list_gates()
        assert len(gates) == 2
        assert gates[0]["name"] == "alpha"
        assert gates[1]["name"] == "beta"

    def test_add_gate_returns_self_for_chaining(self):
        """add_gate returns the pipeline for method chaining."""
        pipeline = GatePipeline()
        result = pipeline.add_gate(MagicMock())
        assert result is pipeline


# ---------------------------------------------------------------------------
# RateLimitGate
# ---------------------------------------------------------------------------


class TestRateLimitGate:
    """RateLimitGate evaluates tool-call rate limits."""

    def test_gate_name(self):
        gate = RateLimitGate()
        assert "rate" in gate.name().lower() or "limit" in gate.name().lower()

    def test_priority_is_integer(self):
        gate = RateLimitGate()
        assert isinstance(gate.priority(), int)

    def test_allows_without_guardrails(self):
        """Without guardrails configured, the gate allows execution."""
        gate = RateLimitGate(guardrails=None)
        ctx = GateContext(tool_name="read_file")
        decision = gate.evaluate(ctx)
        assert decision.is_allowed


# ---------------------------------------------------------------------------
# Integration: realistic pipeline
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    """Realistic multi-gate pipeline scenarios."""

    def test_approval_gate_pauses_high_risk_tool(self):
        """A mock approval gate can pause execution for user approval."""
        approval_gate = MagicMock()
        approval_gate.name.return_value = "approval"
        approval_gate.priority.return_value = 50
        approval_gate.evaluate.return_value = GateDecision(
            action=GateAction.PAUSE,
            reason="User approval required",
            resume_kind=ResumeKind.APPROVAL,
            allow_always=True,
        )

        pipeline = GatePipeline().add_gate(approval_gate)
        decision = pipeline.evaluate(GateContext(tool_name="delete_database"))
        assert decision.is_paused
        assert decision.resume_kind == ResumeKind.APPROVAL
        assert decision.allow_always is True

    def test_rate_limit_denies_before_approval(self):
        """Rate limit (priority 10) denies before approval gate (priority 50)."""
        rate_gate = MagicMock()
        rate_gate.name.return_value = "rate_limit"
        rate_gate.priority.return_value = 10
        rate_gate.evaluate.return_value = GateDecision(action=GateAction.DENY, reason="Rate exceeded")

        approval_gate = MagicMock()
        approval_gate.name.return_value = "approval"
        approval_gate.priority.return_value = 50
        approval_gate.evaluate.return_value = GateDecision(action=GateAction.PAUSE)

        pipeline = GatePipeline().add_gate(approval_gate).add_gate(rate_gate)
        decision = pipeline.evaluate(GateContext(tool_name="api_call"))
        assert decision.is_denied
        assert "Rate exceeded" in decision.reason
        # Approval gate was never reached.
        approval_gate.evaluate.assert_not_called()
