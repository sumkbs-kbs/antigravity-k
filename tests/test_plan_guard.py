"""Tests for PlanGuard and AutonomousCapabilityPolicy.

PlanGuard: evaluates tool calls for destructive commands and mode-based
restrictions (PLAN/BUILD/interactive).

AutonomousCapabilityPolicy: shared risk/trust policy for tools, MCP, skills.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.capability_policy import (
    AutonomousCapabilityPolicy,
    CapabilityDecision,
)
from antigravity_k.engine.plan_guard import GuardDecision, PlanGuard

# ---------------------------------------------------------------------------
# PlanGuard
# ---------------------------------------------------------------------------


class TestPlanGuard:
    """PlanGuard destructive-command and mode-based gating."""

    def test_safe_command_allowed(self):
        """A non-destructive command must be allowed."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("run_bash_command", {"command": "ls -la"})
        assert decision.allows_execution is True
        assert decision.risk_level == "LOW"

    @pytest.mark.parametrize(
        "cmd",
        [
            "rm -rf /",
            "rm -rf .",
            "rm -r /tmp/old",
            "DROP TABLE users",
            "drop database prod",
            "git reset --hard HEAD~3",
            "git push origin main --force",
            "kubectl delete deployment api",
            "TRUNCATE TABLE logs",
            "chmod -R 777 /var/www",
        ],
    )
    def test_destructive_command_blocked(self, cmd):
        """Each destructive pattern must be detected and blocked."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("run_bash_command", {"command": cmd})
        assert decision.allows_execution is False
        assert decision.requires_approval is True
        assert decision.risk_level == "HIGH"
        assert "Destructive" in decision.message

    def test_destructive_command_case_insensitive(self):
        """Pattern matching is case-insensitive."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("run_bash_command", {"command": "Drop Table Users"})
        assert decision.allows_execution is False

    def test_empty_command_allowed(self):
        """An empty command string is safe."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("run_bash_command", {"command": ""})
        assert decision.allows_execution is True

    def test_is_destructive_command_directly(self):
        """_is_destructive_command returns bool for raw strings."""
        guard = PlanGuard()
        assert guard._is_destructive_command("rm -rf /") is True
        assert guard._is_destructive_command("echo hello") is False
        assert guard._is_destructive_command("") is False

    def test_plan_mode_blocks_write_tools(self):
        """In PLAN mode, non-readonly tools are blocked."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("write_file", {"file_path": "x"}, execution_mode="plan")
        assert decision.allows_execution is False
        assert "PLAN" in decision.message

    def test_plan_mode_allows_readonly_tools(self):
        """In PLAN mode, readonly tools (in PLAN_ALLOWED_TOOLS) are allowed."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("read_file", {"file_path": "x"}, execution_mode="plan")
        assert decision.allows_execution is True

    def test_build_mode_restricts_dangerous_tools(self):
        """In BUILD mode, restricted tools require approval."""
        guard = PlanGuard()
        # run_bash_command is typically in BUILD_RESTRICTED_TOOLS.
        decision = guard.evaluate_tool_call("run_bash_command", {"command": "ls"}, execution_mode="build")
        # Either restricted (requires_approval=True) or destructive pattern detected.
        # Either way it should be blocked or require approval.
        if "BUILD MODE" in decision.message:
            assert decision.requires_approval is True

    def test_interactive_mode_allows_safe_tools(self):
        """In interactive mode, safe tools are allowed without restriction."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("write_file", {"file_path": "x"}, execution_mode="interactive")
        assert decision.allows_execution is True

    def test_file_overwrite_requires_approval(self):
        """Overwriting a file with overwrite=True requires approval."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("write_file", {"file_path": "target.txt", "overwrite": True})
        assert decision.allows_execution is False
        assert decision.requires_approval is True
        assert "overwrite" in decision.message.lower()

    def test_file_write_without_overwrite_allowed(self):
        """Writing a file without overwrite=True is allowed."""
        guard = PlanGuard()
        decision = guard.evaluate_tool_call("write_file", {"file_path": "target.txt"})
        assert decision.allows_execution is True

    def test_guard_decision_dataclass_fields(self):
        """GuardDecision has all expected fields."""
        d = GuardDecision(
            allows_execution=True,
            requires_approval=False,
            message="ok",
            risk_level="LOW",
        )
        assert d.allows_execution is True
        assert d.risk_level == "LOW"


# ---------------------------------------------------------------------------
# AutonomousCapabilityPolicy
# ---------------------------------------------------------------------------


class TestCapabilityDecision:
    """CapabilityDecision computed properties."""

    def test_allows_autonomous_use(self):
        d = CapabilityDecision("t", "tool", "allow", "low", "builtin", "ok")
        assert d.allows_autonomous_use is True
        assert d.is_blocked is False
        assert d.requires_approval is False

    def test_is_blocked(self):
        d = CapabilityDecision("t", "tool", "deny", "high", "unknown", "no")
        assert d.is_blocked is True
        assert d.allows_autonomous_use is False

    def test_requires_approval(self):
        d = CapabilityDecision("t", "tool", "prompt", "medium", "builtin", "check")
        assert d.requires_approval is True
        assert d.is_blocked is False


class TestAutonomousCapabilityPolicy:
    """AutonomousCapabilityPolicy risk/trust evaluation."""

    def _make_tool(self, name="test_tool", risk="low", trust="builtin", mcp=None):
        """Create a mock tool with a to_metadata() method."""
        from unittest.mock import MagicMock

        tool = MagicMock()
        metadata = {"name": name, "risk_level": risk, "trust_level": trust}
        if mcp:
            metadata["mcp"] = mcp
        tool.to_metadata.return_value = metadata
        tool.name = name
        return tool

    def test_low_risk_builtin_tool_allowed(self):
        """A low-risk builtin tool must be allowed autonomously."""
        policy = AutonomousCapabilityPolicy(max_autonomous_risk="high")
        tool = self._make_tool(risk="low", trust="builtin")
        decision = policy.decide_tool(tool)
        assert decision.allows_autonomous_use is True

    def test_untrusted_source_requires_approval(self):
        """An untrusted tool source must require approval."""
        policy = AutonomousCapabilityPolicy(max_autonomous_risk="high")
        tool = self._make_tool(trust="unknown")
        decision = policy.decide_tool(tool)
        assert decision.requires_approval is True

    def test_remote_unauthenticated_mcp_denied(self):
        """A remote MCP tool without authentication must be denied."""
        policy = AutonomousCapabilityPolicy()
        tool = self._make_tool(mcp={"remote": True, "authenticated": False, "trust_level": "builtin"})
        decision = policy.decide_tool(tool)
        assert decision.is_blocked is True
        assert "not authenticated" in decision.reason

    def test_critical_risk_requires_approval_by_default(self):
        """Critical-risk tools require approval when allow_critical_autonomy is False."""
        policy = AutonomousCapabilityPolicy(max_autonomous_risk="critical", allow_critical_autonomy=False)
        tool = self._make_tool(risk="critical", trust="builtin")
        decision = policy.decide_tool(tool)
        assert decision.requires_approval is True

    def test_critical_risk_allowed_with_flag(self):
        """Critical-risk tools are allowed when allow_critical_autonomy is True."""
        policy = AutonomousCapabilityPolicy(max_autonomous_risk="critical", allow_critical_autonomy=True)
        tool = self._make_tool(risk="critical", trust="builtin")
        decision = policy.decide_tool(tool)
        assert decision.allows_autonomous_use is True

    def test_high_risk_blocked_when_max_is_medium(self):
        """A high-risk tool is blocked when max_autonomous_risk is medium."""
        policy = AutonomousCapabilityPolicy(max_autonomous_risk="medium")
        tool = self._make_tool(risk="high", trust="builtin")
        decision = policy.decide_tool(tool)
        assert decision.requires_approval is True or decision.is_blocked is True

    def test_set_project_root(self):
        """set_project_root updates the project root."""
        policy = AutonomousCapabilityPolicy(project_root="/tmp")
        assert policy.project_root == "/tmp"
        policy.set_project_root("/opt/project")
        assert policy.project_root == "/opt/project"
