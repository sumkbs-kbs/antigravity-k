"""Tests for the GatePipeline — priority-based multi-stage tool gating.

Covers GateDecision/GateAction/GateContext data structures, GatePipeline
(priority sorting, short-circuit evaluation, fail-open on gate errors),
and individual gates (RateLimitGate, CostBudgetGate, ApprovalGate).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

import pytest

from antigravity_k.engine.gate_pipeline import (
    ExecutionGate,
    GateAction,
    GateContext,
    GateDecision,
    GatePipeline,
    RateLimitGate,
    ResumeKind,
)


class _GateMethod:
    def __init__(self) -> None:
        self.return_value: object = None
        self.side_effect: Callable[..., object] | BaseException | None = None
        self.call_count: int = 0

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.call_count += 1
        effect = self.side_effect
        if isinstance(effect, BaseException):
            raise effect
        if effect is not None:
            return effect(*args, **kwargs)
        return self.return_value


class _ConfigurableGate(Protocol):
    name: _GateMethod
    priority: _GateMethod
    evaluate: _GateMethod


class _GateDouble:
    def __init__(self) -> None:
        self.name: _GateMethod = _GateMethod()
        self.priority: _GateMethod = _GateMethod()
        self.evaluate: _GateMethod = _GateMethod()


def _mock_gate() -> _ConfigurableGate:
    return _GateDouble()


def _as_execution_gate(gate: _ConfigurableGate) -> ExecutionGate:
    return cast(ExecutionGate, cast(object, gate))


def _record_and_allow(call_order: list[str], label: str) -> Callable[..., object]:
    def callback(*_args: object, **_kwargs: object) -> object:
        call_order.append(label)
        return GateDecision()

    return callback

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
            setattr(d, "action", GateAction.DENY)


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
        gate = _mock_gate()
        gate.name.return_value = "test_gate"
        gate.priority.return_value = 10
        gate.evaluate.return_value = GateDecision(action=GateAction.ALLOW)

        pipeline = GatePipeline().add_gate(_as_execution_gate(gate))
        decision = pipeline.evaluate(GateContext(tool_name="x"))
        assert decision.is_allowed

    def test_single_denying_gate_short_circuits(self):
        """A gate that returns DENY short-circuits the pipeline."""
        gate = _mock_gate()
        gate.name.return_value = "blocker"
        gate.priority.return_value = 10
        gate.evaluate.return_value = GateDecision(action=GateAction.DENY, reason="no")

        pipeline = GatePipeline().add_gate(_as_execution_gate(gate))
        decision = pipeline.evaluate(GateContext(tool_name="x"))
        assert decision.is_denied
        assert decision.reason == "no"

    def test_priority_ordering(self):
        """Gates are evaluated in priority order (lower number = higher priority)."""
        call_order: list[str] = []

        gate_low = _mock_gate()
        gate_low.name.return_value = "high_priority"
        gate_low.priority.return_value = 1
        gate_low.evaluate.side_effect = _record_and_allow(call_order, "first")

        gate_high = _mock_gate()
        gate_high.name.return_value = "low_priority"
        gate_high.priority.return_value = 100
        gate_high.evaluate.side_effect = _record_and_allow(call_order, "second")

        pipeline = GatePipeline().add_gate(_as_execution_gate(gate_high)).add_gate(_as_execution_gate(gate_low))
        _ = pipeline.evaluate(GateContext(tool_name="x"))

        assert call_order == ["first", "second"]

    def test_short_circuit_skips_lower_priority(self):
        """When a high-priority gate denies, lower-priority gates are not called."""
        gate1 = _mock_gate()
        gate1.name.return_value = "gate1"
        gate1.priority.return_value = 1
        gate1.evaluate.return_value = GateDecision(action=GateAction.DENY)

        gate2 = _mock_gate()
        gate2.name.return_value = "gate2"
        gate2.priority.return_value = 2
        gate2.evaluate.return_value = GateDecision()

        pipeline = GatePipeline().add_gate(_as_execution_gate(gate2)).add_gate(_as_execution_gate(gate1))
        _ = pipeline.evaluate(GateContext(tool_name="x"))

        assert gate2.evaluate.call_count == 0

    def test_gate_error_fail_open(self):
        """If a gate raises an exception, the pipeline continues (fail-open)."""
        bad_gate = _mock_gate()
        bad_gate.name.return_value = "bad"
        bad_gate.priority.return_value = 1
        bad_gate.evaluate.side_effect = RuntimeError("gate crashed")

        good_gate = _mock_gate()
        good_gate.name.return_value = "good"
        good_gate.priority.return_value = 2
        good_gate.evaluate.return_value = GateDecision(action=GateAction.ALLOW)

        pipeline = GatePipeline().add_gate(_as_execution_gate(bad_gate)).add_gate(_as_execution_gate(good_gate))
        decision = pipeline.evaluate(GateContext(tool_name="x"))
        assert decision.is_allowed

    def test_list_gates(self):
        """list_gates returns name and priority of each gate."""
        g1 = _mock_gate()
        g1.name.return_value = "alpha"
        g1.priority.return_value = 5
        g2 = _mock_gate()
        g2.name.return_value = "beta"
        g2.priority.return_value = 10

        pipeline = GatePipeline().add_gate(_as_execution_gate(g1)).add_gate(_as_execution_gate(g2))
        gates = pipeline.list_gates()
        assert len(gates) == 2
        assert gates[0]["name"] == "alpha"
        assert gates[1]["name"] == "beta"

    def test_add_gate_returns_self_for_chaining(self):
        """add_gate returns the pipeline for method chaining."""
        pipeline = GatePipeline()
        result = pipeline.add_gate(_as_execution_gate(_mock_gate()))
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
        approval_gate = _mock_gate()
        approval_gate.name.return_value = "approval"
        approval_gate.priority.return_value = 50
        approval_gate.evaluate.return_value = GateDecision(
            action=GateAction.PAUSE,
            reason="User approval required",
            resume_kind=ResumeKind.APPROVAL,
            allow_always=True,
        )

        pipeline = GatePipeline().add_gate(_as_execution_gate(approval_gate))
        decision = pipeline.evaluate(GateContext(tool_name="delete_database"))
        assert decision.is_paused
        assert decision.resume_kind == ResumeKind.APPROVAL
        assert decision.allow_always is True

    def test_rate_limit_denies_before_approval(self):
        """Rate limit (priority 10) denies before approval gate (priority 50)."""
        rate_gate = _mock_gate()
        rate_gate.name.return_value = "rate_limit"
        rate_gate.priority.return_value = 10
        rate_gate.evaluate.return_value = GateDecision(action=GateAction.DENY, reason="Rate exceeded")

        approval_gate = _mock_gate()
        approval_gate.name.return_value = "approval"
        approval_gate.priority.return_value = 50
        approval_gate.evaluate.return_value = GateDecision(action=GateAction.PAUSE)

        pipeline = GatePipeline().add_gate(_as_execution_gate(approval_gate)).add_gate(_as_execution_gate(rate_gate))
        decision = pipeline.evaluate(GateContext(tool_name="api_call"))
        assert decision.is_denied
        assert "Rate exceeded" in decision.reason
        # Approval gate was never reached.
        assert approval_gate.evaluate.call_count == 0
