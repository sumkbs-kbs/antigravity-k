"""Tests for ToolExecutor — the core tool dispatch and permission engine.

Covers the main execution paths:
- Unknown tool handling
- Readonly auto-approval (bypasses gates)
- PlanGuard blocking (plan mode denies write tools)
- GatePipeline deny / pause (approval required)
- Schema validation (missing required args)
- Preflight directory auto-creation for write tools
- Permission DENY / PROMPT from execute_with_permission
- Tool call history recording and capping
- Consecutive error tracking and recovery trigger
- File event broadcasting (FileOpened / FileModified)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tool(name="dummy", *, required=None, schema=None):
    """Create a mock tool object with a parameters_schema."""
    tool = MagicMock()
    tool.name = name
    tool.parameters_schema = schema or {"required": required or []}
    return tool


@pytest.fixture
def tool_registry():
    """A minimal ToolRegistry with one registered 'dummy' tool and readonly tools."""
    reg = MagicMock(spec=ToolRegistry)
    reg._tools = {}

    # Register a dummy tool
    dummy = _make_tool("dummy", required=["x"])
    reg._tools["dummy"] = dummy
    reg.get = MagicMock(side_effect=lambda n: reg._tools.get(n))
    reg.__contains__ = lambda self, name: name in reg._tools

    def execute_with_permission(name, args, objective=""):
        return Permission.ALLOW, "ok"

    reg.execute_with_permission = execute_with_permission
    return reg


@pytest.fixture
def permission_gate():
    return MagicMock(spec=PermissionGate)


@pytest.fixture
def executor(tool_registry, permission_gate, tmp_path):
    """Create a ToolExecutor with mocked ImmuneSystem (disabled)."""
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        ex = ToolExecutor(
            tool_registry=tool_registry,
            permission_gate=permission_gate,
            project_root=str(tmp_path),
        )
    # Disable immune system for deterministic tests.
    ex._immune_system = None
    return ex


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


def test_execute_unknown_tool_returns_error(executor):
    """Calling an unregistered tool must return a structured error."""
    result = executor.execute("nonexistent", {})
    assert "Unknown tool" in result
    assert "nonexistent" in result
    assert executor._consecutive_errors == 1


# ---------------------------------------------------------------------------
# Readonly auto-approval
# ---------------------------------------------------------------------------


def test_readonly_tool_bypasses_gates(executor, tool_registry):
    """Readonly tools (read_file, web_search, etc.) execute without gate checks."""
    # Register a readonly tool.
    readonly_tool = MagicMock()
    readonly_tool.parameters_schema = {"required": []}
    readonly_tool.return_value = "file content"
    tool_registry._tools["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    # Mock tool_registry.execute_with_permission won't be called for readonly.
    called = []
    tool_registry.execute_with_permission = lambda n, a, objective="": (
        called.append(n) or (Permission.ALLOW, "should-not-reach")
    )

    result = executor.execute("read_file", {"file_path": "/tmp/test.txt"})
    assert result == "file content"
    # The full execute_with_permission path was NOT used (readonly shortcut).
    assert called == []


def test_readonly_tool_records_history(executor, tool_registry):
    """Readonly tool execution must be recorded in tool_call_history."""
    readonly_tool = MagicMock(return_value="content")
    readonly_tool.parameters_schema = {"required": []}
    tool_registry._tools["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    executor.execute("read_file", {"file_path": "/tmp/x"})
    assert len(executor.tool_call_history) == 1
    assert executor.tool_call_history[0]["name"] == "read_file"
    assert executor.tool_call_history[0]["success"] is True


# ---------------------------------------------------------------------------
# PlanGuard blocking
# ---------------------------------------------------------------------------


def test_plan_guard_blocks_tool(executor, tool_registry):
    """When PlanGuard denies execution, a [BLOCKED] error is returned."""
    # Register write_file so it passes the 'name not in tool_registry' check.
    write_tool = _make_tool("write_file", required=["file_path"])
    tool_registry._tools["write_file"] = write_tool

    guard = MagicMock()
    decision = MagicMock()
    decision.allows_execution = False
    decision.message = "Write tools not allowed in PLAN mode"
    guard.evaluate_tool_call.return_value = decision
    executor.plan_guard = guard

    result = executor.execute("write_file", {"file_path": "x"})
    assert "[BLOCKED]" in result
    assert "PLAN mode" in result
    assert executor._consecutive_errors == 1


def test_plan_guard_allows_tool(executor, tool_registry):
    """When PlanGuard allows, execution proceeds normally."""
    guard = MagicMock()
    decision = MagicMock()
    decision.allows_execution = True
    guard.evaluate_tool_call.return_value = decision
    executor.plan_guard = guard

    # The dummy tool is not readonly, so it goes through the full path.
    result = executor.execute("dummy", {"x": 1})
    assert result == "ok"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_missing_required_args_returns_error(executor):
    """Missing required arguments must produce a structured error."""
    result = executor.execute("dummy", {})
    assert "Missing required arguments" in result
    assert "x" in result
    assert executor._consecutive_errors == 1


# ---------------------------------------------------------------------------
# Preflight directory creation
# ---------------------------------------------------------------------------


def test_preflight_creates_missing_directory(executor, tool_registry, tmp_path):
    """Write tools auto-create missing parent directories."""
    # Register write_file as a real tool with no required args for simplicity.
    write_tool = _make_tool("write_file", required=[])
    tool_registry._tools["write_file"] = write_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    target = str(tmp_path / "newdir" / "subdir" / "file.txt")
    result = executor.execute("write_file", {"file_path": target})
    assert result == "ok"
    # The parent directory should now exist.
    assert os.path.isdir(os.path.dirname(target))


# ---------------------------------------------------------------------------
# Permission DENY / PROMPT
# ---------------------------------------------------------------------------


def test_permission_deny_returns_blocked(executor, tool_registry):
    """When execute_with_permission returns DENY, a [DENIED] error is returned."""
    tool_registry.execute_with_permission = lambda n, a, objective="": (Permission.DENY, "blocked")
    result = executor.execute("dummy", {"x": 1})
    assert "[DENIED]" in result
    assert executor._consecutive_errors == 1


def test_permission_prompt_returns_approval_required(executor, tool_registry):
    """When execute_with_permission returns PROMPT, an [APPROVAL REQUIRED] message is returned."""
    tool_registry.execute_with_permission = lambda n, a, objective="": (Permission.PROMPT, "needs approval")
    result = executor.execute("dummy", {"x": 1})
    assert "[APPROVAL REQUIRED]" in result


# ---------------------------------------------------------------------------
# Error tracking and recovery
# ---------------------------------------------------------------------------


def test_consecutive_error_reset_on_success(executor, tool_registry):
    """A successful tool call resets the consecutive error counter."""
    executor._consecutive_errors = 2
    executor.execute("dummy", {"x": 1})
    assert executor._consecutive_errors == 0


def test_three_consecutive_errors_trigger_recovery(executor, tool_registry):
    """Three consecutive errors trigger the recovery path (_trigger_recovery)."""
    # Make execute_with_permission return errors.
    tool_registry.execute_with_permission = lambda n, a, objective="": (Permission.ALLOW, "Error: something failed")
    # Mock _trigger_recovery to verify it's called.
    executor._trigger_recovery = MagicMock(return_value="recovery result")

    executor.execute("dummy", {"x": 1})  # error 1
    executor.execute("dummy", {"x": 1})  # error 2
    result = executor.execute("dummy", {"x": 1})  # error 3 → trigger

    assert result == "recovery result"
    executor._trigger_recovery.assert_called_once()


# ---------------------------------------------------------------------------
# History capping
# ---------------------------------------------------------------------------


def test_tool_call_history_capped_at_20(executor, tool_registry):
    """The history list must not exceed 20 entries."""
    readonly_tool = MagicMock(return_value="ok")
    readonly_tool.parameters_schema = {"required": []}
    tool_registry._tools["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    for i in range(25):
        executor.execute("read_file", {"file_path": f"/tmp/{i}"})

    assert len(executor.tool_call_history) == 20
    # The oldest entries should have been dropped; the last should be the most recent.
    assert executor.tool_call_history[-1]["arguments"]["file_path"] == "/tmp/24"


# ---------------------------------------------------------------------------
# Helper methods (extracted during refactor)
# ---------------------------------------------------------------------------


def test_validate_and_preflight_returns_none_on_success(executor):
    """_validate_and_preflight returns None when validation passes."""
    result = executor._validate_and_preflight("dummy", {"x": 1})
    assert result is None


def test_validate_and_preflight_missing_args(executor):
    """_validate_and_preflight returns an error string for missing args."""
    result = executor._validate_and_preflight("dummy", {})
    assert result is not None
    assert "Missing required arguments" in result


def test_record_tool_call_adds_entry(executor):
    """_record_tool_call appends a single history entry."""
    initial = len(executor.tool_call_history)
    executor._record_tool_call("test_tool", {"k": "v"}, "result")
    assert len(executor.tool_call_history) == initial + 1
    entry = executor.tool_call_history[-1]
    assert entry["name"] == "test_tool"
    assert entry["success"] is True


def test_record_tool_call_error_result_marked_unsuccessful(executor):
    """An error result string must be marked as unsuccessful in history."""
    executor._record_tool_call("bad_tool", {}, "Error: failed")
    assert executor.tool_call_history[-1]["success"] is False


# ---------------------------------------------------------------------------
# File event broadcasting
# ---------------------------------------------------------------------------


def test_broadcast_file_event_skips_non_file_tools(executor):
    """_broadcast_file_event does nothing for non-file tools."""
    # Should not raise even if the tool is not a file tool.
    executor._broadcast_file_event("web_search", {"query": "test"})


def test_broadcast_file_event_publishes_for_read_file(executor, tmp_path):
    """_broadcast_file_event publishes FileOpened for read_file on an existing file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")

    published = []
    with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
        mock_bus.publish = lambda event_type, **kwargs: published.append((event_type, kwargs))
        executor._broadcast_file_event("read_file", {"file_path": str(test_file)})

    assert len(published) == 1
    assert published[0][0] == "FileOpened"
    assert published[0][1]["filepath"] == str(test_file)


def test_broadcast_file_event_publishes_for_write_file(executor, tmp_path):
    """_broadcast_file_event publishes FileModified for write_file."""
    test_file = tmp_path / "output.txt"
    test_file.write_text("data")

    published = []
    with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
        mock_bus.publish = lambda event_type, **kwargs: published.append((event_type, kwargs))
        executor._broadcast_file_event("write_file", {"file_path": str(test_file)})

    assert published[0][0] == "FileModified"


def test_broadcast_file_event_skips_nonexistent_file(executor):
    """_broadcast_file_event does nothing for a non-existent file path."""
    # Should not raise.
    executor._broadcast_file_event("read_file", {"file_path": "/nonexistent/path/file.txt"})
