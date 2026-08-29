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
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tool(
    name: str = "dummy",
    *,
    required: list[str] | None = None,
    schema: dict[str, object] | None = None,
) -> MagicMock:
    """Create a mock tool object with a parameters_schema."""
    tool = MagicMock()
    tool.name = name
    tool.parameters_schema = schema or {"required": required or []}
    return tool


@pytest.fixture
def tool_registry() -> MagicMock:
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
def permission_gate() -> MagicMock:
    return MagicMock(spec=PermissionGate)


@pytest.fixture
def executor(tool_registry: MagicMock, permission_gate: MagicMock, tmp_path: Path) -> ToolExecutor:
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


def test_execute_unknown_tool_returns_error(executor: ToolExecutor):
    """Calling an unregistered tool must return a structured error."""
    result = executor.execute("nonexistent", {})
    assert "Unknown tool" in result
    assert "nonexistent" in result
    assert executor._consecutive_errors == 1


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def test_readonly_tool_uses_permission_boundary(executor: ToolExecutor, tool_registry: MagicMock):
    readonly_tool = MagicMock()
    readonly_tool.parameters_schema = {"required": []}
    readonly_tool.return_value = "file content"
    tool_registry._tools["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    called = []

    def execute_with_permission(name, args, objective=""):
        called.append(name)
        return Permission.ALLOW, readonly_tool(**args)

    tool_registry.execute_with_permission = execute_with_permission

    result = executor.execute("read_file", {"file_path": "/tmp/test.txt"})
    assert result == "file content"
    assert called == ["read_file"]


def test_readonly_protected_path_is_denied_by_permission_gate(tmp_path: Path):
    from antigravity_k.engine.tool_executor import ToolExecutor
    from antigravity_k.tools.system_tools import ReadFileTool

    registry = ToolRegistry(project_root=str(tmp_path))
    _ = registry.install(ReadFileTool())
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        executor = ToolExecutor(
            tool_registry=registry,
            permission_gate=registry.permission_gate,
            project_root=str(tmp_path),
        )

    result = executor.execute("read_file", {"file_path": "/etc/passwd"})

    assert "[DENIED]" in result


def test_approved_execution_rechecks_permission_boundary(tmp_path: Path):
    from antigravity_k.tools.system_tools import ReadFileTool

    target = tmp_path / "protected-by-override.txt"
    _ = target.write_text("must not be read", encoding="utf-8")
    registry = ToolRegistry(project_root=str(tmp_path))
    _ = registry.install(ReadFileTool())
    registry.permission_gate.set_override("read_file", Permission.DENY)

    result = registry.execute_approved("read_file", {"file_path": str(target)})

    assert "[DENIED]" in result


def test_readonly_tool_records_history(executor: ToolExecutor, tool_registry: MagicMock):
    """Readonly tool execution must be recorded in tool_call_history."""
    readonly_tool = MagicMock(return_value="content")
    readonly_tool.parameters_schema = {"required": []}
    tool_registry._tools["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    _ = executor.execute("read_file", {"file_path": "/tmp/x"})
    assert len(executor.tool_call_history) == 1
    assert executor.tool_call_history[0]["name"] == "read_file"
    assert executor.tool_call_history[0]["success"] is True


# ---------------------------------------------------------------------------
# PlanGuard blocking
# ---------------------------------------------------------------------------


def test_plan_guard_blocks_tool(executor: ToolExecutor, tool_registry: MagicMock):
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


def test_plan_guard_allows_tool(executor: ToolExecutor, tool_registry: MagicMock):
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


def test_missing_required_args_returns_error(executor: ToolExecutor):
    """Missing required arguments must produce a structured error."""
    result = executor.execute("dummy", {})
    assert "Missing required arguments" in result
    assert "x" in result
    assert executor._consecutive_errors == 1


# ---------------------------------------------------------------------------
# Preflight directory creation
# ---------------------------------------------------------------------------


def test_preflight_creates_missing_directory(executor: ToolExecutor, tool_registry: MagicMock, tmp_path: Path):
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


def test_permission_deny_returns_blocked(executor: ToolExecutor, tool_registry: MagicMock):
    """When execute_with_permission returns DENY, a [DENIED] error is returned."""
    tool_registry.execute_with_permission = lambda n, a, objective="": (Permission.DENY, "blocked")
    result = executor.execute("dummy", {"x": 1})
    assert "[DENIED]" in result
    assert executor._consecutive_errors == 1
    assert executor.tool_call_history[-1]["permission"] == "deny"


def test_permission_prompt_returns_approval_required(executor: ToolExecutor, tool_registry: MagicMock):
    """When execute_with_permission returns PROMPT, an [APPROVAL REQUIRED] message is returned."""
    tool_registry.execute_with_permission = lambda n, a, objective="": (Permission.PROMPT, "needs approval")
    result = executor.execute("dummy", {"x": 1})
    assert "[APPROVAL REQUIRED]" in result
    assert executor.tool_call_history[-1]["permission"] == "prompt"


# ---------------------------------------------------------------------------
# Error tracking and recovery
# ---------------------------------------------------------------------------


def test_consecutive_error_reset_on_success(executor: ToolExecutor, tool_registry: MagicMock):
    """A successful tool call resets the consecutive error counter."""
    executor._consecutive_errors = 2
    _ = executor.execute("dummy", {"x": 1})
    assert executor._consecutive_errors == 0


def test_three_consecutive_errors_trigger_recovery(executor: ToolExecutor, tool_registry: MagicMock):
    """Three consecutive errors trigger the recovery path (_trigger_recovery)."""
    # Make execute_with_permission return errors.
    tool_registry.execute_with_permission = lambda n, a, objective="": (Permission.ALLOW, "Error: something failed")
    # Mock _trigger_recovery to verify it's called.
    executor._trigger_recovery = MagicMock(return_value="recovery result")

    _ = executor.execute("dummy", {"x": 1})  # error 1
    _ = executor.execute("dummy", {"x": 1})  # error 2
    result = executor.execute("dummy", {"x": 1})  # error 3 → trigger

    assert result == "recovery result"
    executor._trigger_recovery.assert_called_once()


# ---------------------------------------------------------------------------
# History capping
# ---------------------------------------------------------------------------


def test_tool_call_history_capped_at_20(executor: ToolExecutor, tool_registry: MagicMock):
    """The history list must not exceed 20 entries."""
    readonly_tool = MagicMock(return_value="ok")
    readonly_tool.parameters_schema = {"required": []}
    tool_registry._tools["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))

    for i in range(25):
        _ = executor.execute("read_file", {"file_path": f"/tmp/{i}"})

    assert len(executor.tool_call_history) == 20
    # The oldest entries should have been dropped; the last should be the most recent.
    assert executor.tool_call_history[-1]["arguments"]["file_path"] == "/tmp/24"


# ---------------------------------------------------------------------------
# Helper methods (extracted during refactor)
# ---------------------------------------------------------------------------


def test_validate_and_preflight_returns_none_on_success(executor: ToolExecutor):
    """_validate_and_preflight returns None when validation passes."""
    result = executor._validate_and_preflight("dummy", {"x": 1})
    assert result is None


def test_validate_and_preflight_missing_args(executor: ToolExecutor):
    """_validate_and_preflight returns an error string for missing args."""
    result = executor._validate_and_preflight("dummy", {})
    assert result is not None
    assert "Missing required arguments" in result


def test_record_tool_call_adds_entry(executor: ToolExecutor):
    """_record_tool_call appends a single history entry."""
    initial = len(executor.tool_call_history)
    executor._record_tool_call("test_tool", {"k": "v"}, "result")
    assert len(executor.tool_call_history) == initial + 1
    entry = executor.tool_call_history[-1]
    assert entry["name"] == "test_tool"
    assert entry["success"] is True


def test_record_tool_call_error_result_marked_unsuccessful(executor: ToolExecutor):
    """An error result string must be marked as unsuccessful in history."""
    executor._record_tool_call("bad_tool", {}, "Error: failed")
    assert executor.tool_call_history[-1]["success"] is False


# ---------------------------------------------------------------------------
# File event broadcasting
# ---------------------------------------------------------------------------


def test_broadcast_file_event_skips_non_file_tools(executor: ToolExecutor):
    """_broadcast_file_event does nothing for non-file tools."""
    # Should not raise even if the tool is not a file tool.
    _ = executor._broadcast_file_event("web_search", {"query": "test"})


def test_broadcast_file_event_publishes_for_read_file(executor: ToolExecutor, tmp_path: Path):
    """_broadcast_file_event publishes FileOpened for read_file on an existing file."""
    test_file = tmp_path / "test.txt"
    _ = test_file.write_text("hello")

    published = []
    with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
        mock_bus.publish = lambda event_type, **kwargs: published.append((event_type, kwargs))
        _ = executor._broadcast_file_event("read_file", {"file_path": str(test_file)})

    assert len(published) == 1
    assert published[0][0] == "FileOpened"
    assert published[0][1]["filepath"] == str(test_file)


def test_broadcast_file_event_publishes_for_write_file(executor: ToolExecutor, tmp_path: Path):
    """_broadcast_file_event publishes FileModified for write_file."""
    test_file = tmp_path / "output.txt"
    _ = test_file.write_text("data")

    published = []
    with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
        mock_bus.publish = lambda event_type, **kwargs: published.append((event_type, kwargs))
        _ = executor._broadcast_file_event("write_file", {"file_path": str(test_file)})

    assert published[0][0] == "FileModified"


def test_broadcast_file_event_skips_nonexistent_file(executor: ToolExecutor):
    """_broadcast_file_event does nothing for a non-existent file path."""
    # Should not raise.
    _ = executor._broadcast_file_event("read_file", {"file_path": "/nonexistent/path/file.txt"})


def test_explicitly_contracted_tool_bypasses_approval_pause(tmp_path: Path):
    # Given: a task whose checkpoint records write_file as a tool the user explicitly requested.
    from antigravity_k.engine.gate_pipeline import create_default_pipeline
    from antigravity_k.engine.task_state_store import (
        TaskExecutionContext,
        TaskStateStore,
        bind_task_execution_context,
    )

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-contract", "write and run", "pending", "2026-08-13T00:00:00+00:00")
    store.save_checkpoint("task-contract", 0, '{"expected_tools": ["write_file"]}', "")

    reg = MagicMock(spec=ToolRegistry)
    reg._tools = {}
    write_tool = _make_tool("write_file", required=["file_path"])
    write_tool.return_value = "wrote"
    reg._tools["write_file"] = write_tool
    reg.get = MagicMock(side_effect=lambda n: reg._tools.get(n))
    reg.__contains__ = lambda self, name: name in reg._tools
    reg.execute_with_permission = lambda n, a, objective="": (Permission.ALLOW, "wrote")

    gate = MagicMock(spec=PermissionGate)
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        ex = ToolExecutor(
            tool_registry=reg,
            permission_gate=gate,
            project_root=str(tmp_path),
            gate_pipeline=create_default_pipeline(),
        )
    ex._immune_system = None

    # When: write_file executes inside a task that explicitly contracted it.
    with bind_task_execution_context(TaskExecutionContext("task-contract", store)):
        result = ex.execute("write_file", {"file_path": str(tmp_path / "out.txt"), "content": "x"})

    # Then: the user's explicit request pre-approves the tool, so the loop runs it
    # instead of pausing for interactive confirmation.
    assert result == "wrote"
    assert "APPROVAL REQUIRED" not in str(result)


def test_nonzero_exit_code_result_is_classified_as_failure(executor: ToolExecutor, tool_registry: MagicMock):
    # Given: a tool whose result carries the [exit_code=N] failure marker surfaced by
    # run_bash_command when a command exits non-zero.
    failing_tool = _make_tool("run_bash_command", required=["command"])
    failing_tool.return_value = "[exit_code=2]\nSTDERR:\nboom"
    tool_registry._tools["run_bash_command"] = failing_tool
    tool_registry.get = MagicMock(side_effect=lambda n: tool_registry._tools.get(n))
    tool_registry.execute_with_permission = lambda n, a, objective="": (
        Permission.ALLOW,
        "[exit_code=2]\nSTDERR:\nboom",
    )

    # When: the executor runs the tool and records the outcome.
    _ = executor.execute("run_bash_command", {"command": "false"})

    # Then: the result is classified as a failure so the consecutive-error counter
    # advances and the recovery loop can trigger — the exit-code marker must not mask it.
    assert executor.tool_call_history[-1]["success"] is False
    assert executor._consecutive_errors == 1


def test_dangerous_command_is_denied_even_when_run_bash_is_user_contracted(tmp_path: Path):
    # Given: a task that explicitly contracted run_bash_command (auto-approved via the
    # user-contract path), so the ApprovalGate is bypassed.
    from antigravity_k.tools.permission_gate import PermissionGate
    from antigravity_k.tools.tool_contracts import ToolInvocation, ToolSpec

    # When: a destructive command runs inside the contracted task — the permission gate
    # must still deny it regardless of the ApprovalGate pre-approval.
    real_gate = PermissionGate(project_root=str(tmp_path), mode="auto-pilot")
    spec = ToolSpec(name="run_bash_command", risk_level="high", category="code_exec")
    decision = real_gate.decide(ToolInvocation(spec=spec, arguments={"command": "rm -rf /"}))

    # Then: the dangerous-command policy denies it — pre-approval authorizes *which tool*
    # but never *which destructive payload*.
    assert decision.is_denied
