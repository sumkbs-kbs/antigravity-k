"""Tests for ModeManager — Plan/Build/Interactive execution mode state machine."""

from __future__ import annotations

from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.mode_manager import ModeManager


class TestModeManagerBasics:
    """ModeManager initialization and properties."""

    def test_default_mode_is_interactive(self):
        """New ModeManager starts in INTERACTIVE mode."""
        mgr = ModeManager()
        assert mgr.is_interactive is True
        assert mgr.is_plan is False
        assert mgr.is_build is False

    def test_initial_mode_plan(self):
        """Can initialize directly in PLAN mode."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        assert mgr.is_plan is True

    def test_plan_artifact_path_none_by_default(self):
        mgr = ModeManager()
        assert mgr.plan_artifact_path is None

    def test_empty_history_on_init(self):
        mgr = ModeManager()
        assert mgr.mode_history == []


class TestSwitchToPlan:
    """switch_to_plan transitions."""

    def test_switch_from_interactive_to_plan(self):
        mgr = ModeManager()
        assert mgr.switch_to_plan("user request") is True
        assert mgr.is_plan is True

    def test_switch_to_plan_idempotent(self):
        """Switching to PLAN when already in PLAN is a no-op success."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        assert mgr.switch_to_plan() is True
        assert mgr.is_plan is True

    def test_switch_to_plan_records_history(self):
        mgr = ModeManager()
        mgr.switch_to_plan("testing")
        assert len(mgr.mode_history) == 1
        transition = mgr.mode_history[0]
        assert transition.to_mode == ExecutionMode.PLAN

    def test_switch_to_plan_clears_artifact(self):
        """Entering PLAN mode clears any prior plan artifact/quality state."""
        mgr = ModeManager()
        mgr.set_plan_artifact("/some/path")
        mgr.set_plan_quality_passed(True)
        mgr.switch_to_plan()
        assert mgr.plan_artifact_path is None
        assert mgr.can_auto_transition_to_build is False


class TestSwitchToBuild:
    """switch_to_build transitions and gating."""

    def test_switch_from_interactive_to_build_directly(self):
        """Interactive → Build is allowed directly."""
        mgr = ModeManager()
        assert mgr.switch_to_build() is True
        assert mgr.is_build is True

    def test_plan_to_build_requires_quality_pass(self):
        """Plan → Build without quality gate passing fails."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_artifact("/plan.md")
        # quality NOT passed
        assert mgr.switch_to_build() is False
        assert mgr.is_plan is True

    def test_plan_to_build_succeeds_with_quality_and_artifact(self):
        """Plan → Build succeeds when artifact + quality both set."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_artifact("/plan.md")
        mgr.set_plan_quality_passed(True)
        assert mgr.switch_to_build() is True
        assert mgr.is_build is True

    def test_plan_to_build_with_explicit_artifact_path(self):
        """Passing plan_artifact_path to switch_to_build sets it."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_quality_passed(True)
        mgr.switch_to_build(plan_artifact_path="/custom/plan.md")
        assert mgr.plan_artifact_path == "/custom/plan.md"

    def test_build_idempotent(self):
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        assert mgr.switch_to_build() is True
        assert mgr.is_build is True


class TestSwitchToInteractive:
    """switch_to_interactive transitions."""

    def test_switch_from_plan_to_interactive(self):
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        assert mgr.switch_to_interactive() is True
        assert mgr.is_interactive is True

    def test_switch_from_build_to_interactive(self):
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        assert mgr.switch_to_interactive() is True
        assert mgr.is_interactive is True

    def test_interactive_idempotent(self):
        mgr = ModeManager()
        assert mgr.switch_to_interactive() is True

    def test_switch_to_interactive_clears_artifact(self):
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        mgr.set_plan_artifact("/path")
        mgr.switch_to_interactive()
        assert mgr.plan_artifact_path is None


class TestAutoTransition:
    """can_auto_transition_to_build property."""

    def test_auto_transition_false_by_default(self):
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        assert mgr.can_auto_transition_to_build is False

    def test_auto_transition_true_with_both_conditions(self):
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_artifact("/plan.md")
        mgr.set_plan_quality_passed(True)
        assert mgr.can_auto_transition_to_build is True

    def test_auto_transition_false_without_artifact(self):
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_quality_passed(True)
        # artifact not set
        assert mgr.can_auto_transition_to_build is False

    def test_auto_transition_false_without_quality(self):
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_artifact("/plan.md")
        # quality not passed
        assert mgr.can_auto_transition_to_build is False


class TestToolPermission:
    """check_tool_permission in different modes."""

    def test_plan_mode_blocks_write_tools(self):
        """In PLAN mode, write tools are blocked."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        result = mgr.check_tool_permission("write_file")
        assert result["allowed"] is False

    def test_plan_mode_allows_read_tools(self):
        """In PLAN mode, read tools are allowed."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        result = mgr.check_tool_permission("read_file")
        assert result["allowed"] is True

    def test_build_mode_allows_tools(self):
        """In BUILD mode, tools are generally allowed."""
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        result = mgr.check_tool_permission("write_file")
        assert result["allowed"] is True

    def test_interactive_mode_allows_tools(self):
        """In INTERACTIVE mode, tools are allowed."""
        mgr = ModeManager()
        result = mgr.check_tool_permission("write_file")
        assert result["allowed"] is True


class TestToDict:
    """to_dict serialization."""

    def test_to_dict_contains_mode(self):
        mgr = ModeManager()
        d = mgr.to_dict()
        assert "current_mode" in d
        assert d["current_mode"] == "interactive"

    def test_to_dict_contains_history(self):
        mgr = ModeManager()
        mgr.switch_to_plan()
        d = mgr.to_dict()
        assert "history_count" in d
        assert d["history_count"] >= 1
