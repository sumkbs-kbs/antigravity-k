"""Tests for state graph handler output boundaries."""

import time
from unittest.mock import MagicMock, patch

from antigravity_k.engine.orchestrator_handlers import code_review_handler
from antigravity_k.engine.state_graph import StateContext


def _review_context() -> StateContext:
    return StateContext(
        task_type="coding",
        user_message="코드를 설명해줘",
        agent_output="x" * 120,
    )


def _orchestrator(tool_names: tuple[str, ...]) -> MagicMock:
    orch = MagicMock()
    orch.project_root = "/tmp/project"
    orch.ctx.tool_executor.tool_call_history = [
        {"name": tool_name, "arguments": {}, "success": True, "timestamp": time.time()} for tool_name in tool_names
    ]
    return orch


def test_code_review_skips_workspace_diff_when_agent_only_read_files():
    # Given: the workspace is dirty but this agent turn used no mutating tool.
    ctx = _review_context()
    orch = _orchestrator(("read_file", "glob_search"))

    with patch("subprocess.run") as run:
        chunks = list(code_review_handler(ctx, orch))

    # Then: unrelated pre-existing changes stay out of the user's answer.
    assert chunks == []
    run.assert_not_called()
    orch.manager.generate.assert_not_called()


def test_code_review_reviews_diff_after_mutating_tool_use():
    # Given: this agent turn actually edited a file.
    ctx = _review_context()
    orch = _orchestrator(("read_file", "edit_file"))
    orch.manager.generate.return_value = "BUGS: None\nTYPES: None\nQUALITY: None"

    with patch("subprocess.run") as run:
        run.side_effect = [
            MagicMock(stdout="src/file.py | 5 +++--"),
            MagicMock(stdout="diff --git a/src/file.py b/src/file.py"),
        ]
        chunks = list(code_review_handler(ctx, orch))

    # Then: the review path runs for the agent-owned change.
    assert chunks == []
    assert run.call_count == 2
    orch.manager.generate.assert_called_once()


def test_code_review_ignores_mutating_tools_from_previous_turns():
    # Given: an earlier turn edited a file, but this turn only explains code.
    ctx = _review_context()
    orch = _orchestrator(("read_file",))
    orch.ctx.tool_executor.tool_call_history = [
        {"name": "edit_file", "arguments": {}, "success": True, "timestamp": 0.0},
        {"name": "read_file", "arguments": {}, "success": True, "timestamp": time.time()},
    ]

    with patch("subprocess.run") as run:
        chunks = list(code_review_handler(ctx, orch))

    # Then: stale history cannot make this answer review an unrelated diff.
    assert chunks == []
    run.assert_not_called()
