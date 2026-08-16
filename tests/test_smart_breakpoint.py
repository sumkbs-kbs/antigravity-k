"""Unit tests for SmartBreakpointGate."""

from antigravity_k.engine.smart_breakpoint import SmartBreakpointGate


def test_breakpoint_trigger_after_consecutive_failures():
    gate = SmartBreakpointGate(max_consecutive_failures=3)

    assert gate.record_attempt(False) is False  # 1st fail
    assert gate.record_attempt(False) is False  # 2nd fail
    assert gate.record_attempt(True) is False  # reset on success
    assert gate.record_attempt(False) is False  # 1st fail
    assert gate.record_attempt(False) is False  # 2nd fail
    assert gate.record_attempt(False) is True  # 3rd fail -> triggers breakpoint

    prompt = gate.generate_breakpoint(
        task_context="Configuring OAuth2 Credentials",
        failing_error="Invalid client_id",
        possible_approaches=[
            ("Use local mock credentials", "use_mock"),
            ("Prompt user for real client_id", "prompt_user"),
        ],
    )

    dialog = prompt.format_interactive_dialog()
    assert "Agent Decision Breakpoint" in dialog
    assert "[1] Use local mock credentials" in dialog
    assert "[3] Abort current subgoal" in dialog
