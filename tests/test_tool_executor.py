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
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.tool_contracts import Permission
from antigravity_k.tools.tool_registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _registry_tools(registry: MagicMock) -> dict[str, MagicMock]:
    return cast(dict[str, MagicMock], getattr(registry, "_tools"))


def _lookup_tool(registry: MagicMock, name: str) -> MagicMock | None:
    return _registry_tools(registry).get(name)


def _contains_tool(_registry: object, name: str) -> bool:
    return name in _registry_tools(cast(MagicMock, _registry))


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
    _registry_tools(reg)["dummy"] = dummy
    reg.get = MagicMock(side_effect=partial(_lookup_tool, reg))
    reg.__contains__ = _contains_tool

    def execute_with_permission(
        _name: str, _args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
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
    setattr(ex, "_immune_system", None)
    return ex


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


def test_execute_unknown_tool_returns_error(executor: ToolExecutor):
    """Calling an unregistered tool must return a structured error."""
    result = executor.execute("nonexistent", {})
    assert "Unknown tool" in result
    assert "nonexistent" in result
    # 스키마 실수는 롤백 임계 카운터에 가산되지 않는다 (과잉 볼트 롤백 방지)
    assert cast(int, getattr(executor, "_consecutive_errors")) == 0


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def test_readonly_tool_uses_permission_boundary(executor: ToolExecutor, tool_registry: MagicMock):
    readonly_tool = MagicMock()
    readonly_tool.parameters_schema = {"required": []}
    readonly_tool.return_value = "file content"
    _registry_tools(tool_registry)["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))

    called: list[str] = []

    def execute_with_permission(
        name: str, args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
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
    install = cast(Callable[..., ToolRegistry], getattr(registry, "install"))
    _ = install(ReadFileTool())
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
    install = cast(Callable[..., ToolRegistry], getattr(registry, "install"))
    _ = install(ReadFileTool())
    registry.permission_gate.set_override("read_file", Permission.DENY)

    result = registry.execute_approved("read_file", {"file_path": str(target)})

    assert "[DENIED]" in result


def test_readonly_tool_records_history(executor: ToolExecutor, tool_registry: MagicMock):
    """Readonly tool execution must be recorded in tool_call_history."""
    readonly_tool = MagicMock(return_value="content")
    readonly_tool.parameters_schema = {"required": []}
    _registry_tools(tool_registry)["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))

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
    _registry_tools(tool_registry)["write_file"] = write_tool

    guard = MagicMock()
    decision = MagicMock()
    decision.allows_execution = False
    decision.message = "Write tools not allowed in PLAN mode"
    setattr(guard, "evaluate_tool_call", MagicMock(return_value=decision))
    executor.plan_guard = guard

    result = executor.execute("write_file", {"file_path": "x"})
    assert "[BLOCKED]" in result
    assert "PLAN mode" in result
    # 정책 차단은 롤백 임계 카운터에 가산되지 않는다
    assert cast(int, getattr(executor, "_consecutive_errors")) == 0


def test_plan_guard_allows_tool(executor: ToolExecutor):
    """When PlanGuard allows, execution proceeds normally."""
    guard = MagicMock()
    decision = MagicMock()
    decision.allows_execution = True
    setattr(guard, "evaluate_tool_call", MagicMock(return_value=decision))
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
    # 스키마 실수는 롤백 임계 카운터에 가산되지 않는다
    assert cast(int, getattr(executor, "_consecutive_errors")) == 0


# ---------------------------------------------------------------------------
# Preflight directory creation
# ---------------------------------------------------------------------------


def test_preflight_validation_has_no_write_side_effect(executor: ToolExecutor, tool_registry: MagicMock, tmp_path: Path):
    """검증 단계는 디렉터리를 생성하지 않는다 — 생성은 실제 쓰기 도구의 책임.

    (오타 경로가 조용히 잘못된 디렉터리 트리를 만드는 부수효과 방지)
    """
    # no-op 도구로 등록 (실제 쓰기는 일어나지 않음)
    write_tool = _make_tool("write_file", required=[])
    _registry_tools(tool_registry)["write_file"] = write_tool
    tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))

    target = str(tmp_path / "newdir" / "subdir" / "file.txt")
    result = executor.execute("write_file", {"file_path": target})
    assert result == "ok"
    # 검증만 거친 시점에는 디렉터리가 생성되지 않는다.
    assert not os.path.isdir(os.path.dirname(target))


# ---------------------------------------------------------------------------
# Permission DENY / PROMPT
# ---------------------------------------------------------------------------


def test_permission_deny_returns_blocked(executor: ToolExecutor, tool_registry: MagicMock):
    """When execute_with_permission returns DENY, a [DENIED] error is returned."""
    def deny_execution(
        _name: str, _args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.DENY, "blocked"

    tool_registry.execute_with_permission = deny_execution
    result = executor.execute("dummy", {"x": 1})
    assert "[DENIED]" in result
    assert cast(int, getattr(executor, "_consecutive_errors")) == 0  # 정책 차단은 카운터 제외
    assert executor.tool_call_history[-1]["permission"] == "deny"


def test_permission_prompt_returns_approval_required(executor: ToolExecutor, tool_registry: MagicMock):
    """When execute_with_permission returns PROMPT, an [APPROVAL REQUIRED] message is returned."""
    def prompt_execution(
        _name: str, _args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.PROMPT, "needs approval"

    tool_registry.execute_with_permission = prompt_execution
    result = executor.execute("dummy", {"x": 1})
    assert "[APPROVAL REQUIRED]" in result
    assert executor.tool_call_history[-1]["permission"] == "prompt"


# ---------------------------------------------------------------------------
# Error tracking and recovery
# ---------------------------------------------------------------------------


def test_consecutive_error_reset_on_success(executor: ToolExecutor):
    """A successful tool call resets the consecutive error counter."""
    setattr(executor, "_consecutive_errors", 2)
    _ = executor.execute("dummy", {"x": 1})
    assert cast(int, getattr(executor, "_consecutive_errors")) == 0


def test_three_consecutive_errors_trigger_recovery(executor: ToolExecutor, tool_registry: MagicMock):
    """Three consecutive errors trigger the recovery path (_trigger_recovery)."""
    # Make execute_with_permission return errors.
    def failing_execution(
        _name: str, _args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.ALLOW, "Error: something failed"

    tool_registry.execute_with_permission = failing_execution
    # Mock _trigger_recovery to verify it's called.
    recovery = MagicMock(return_value="recovery result")
    setattr(executor, "_trigger_recovery", recovery)

    _ = executor.execute("dummy", {"x": 1})  # error 1
    _ = executor.execute("dummy", {"x": 1})  # error 2
    result = executor.execute("dummy", {"x": 1})  # error 3 → trigger

    assert result == "recovery result"
    recovery.assert_called_once()


# ---------------------------------------------------------------------------
# History capping
# ---------------------------------------------------------------------------


def test_tool_call_history_capped_at_20(executor: ToolExecutor, tool_registry: MagicMock):
    """The history list must not exceed 20 entries."""
    readonly_tool = MagicMock(return_value="ok")
    readonly_tool.parameters_schema = {"required": []}
    _registry_tools(tool_registry)["read_file"] = readonly_tool
    tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))

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
    validate = cast(
        Callable[[str, dict[str, object]], str | None],
        getattr(executor, "_validate_and_preflight"),
    )
    result = validate("dummy", {"x": 1})
    assert result is None


def test_validate_and_preflight_missing_args(executor: ToolExecutor):
    """_validate_and_preflight returns an error string for missing args."""
    validate = cast(
        Callable[[str, dict[str, object]], str | None],
        getattr(executor, "_validate_and_preflight"),
    )
    result = validate("dummy", {})
    assert result is not None
    assert "Missing required arguments" in result


def test_record_tool_call_adds_entry(executor: ToolExecutor):
    """_record_tool_call appends a single history entry."""
    initial = len(executor.tool_call_history)
    record = cast(
        Callable[[str, dict[str, object], str], None],
        getattr(executor, "_record_tool_call"),
    )
    record("test_tool", {"k": "v"}, "result")
    assert len(executor.tool_call_history) == initial + 1
    entry = executor.tool_call_history[-1]
    assert entry["name"] == "test_tool"
    assert entry["success"] is True


def test_record_tool_call_error_result_marked_unsuccessful(executor: ToolExecutor):
    """An error result string must be marked as unsuccessful in history."""
    record = cast(
        Callable[[str, dict[str, object], str], None],
        getattr(executor, "_record_tool_call"),
    )
    record("bad_tool", {}, "Error: failed")
    assert executor.tool_call_history[-1]["success"] is False


# ---------------------------------------------------------------------------
# File event broadcasting
# ---------------------------------------------------------------------------


def test_broadcast_file_event_skips_non_file_tools(executor: ToolExecutor):
    """_broadcast_file_event does nothing for non-file tools."""
    # Should not raise even if the tool is not a file tool.
    broadcast = cast(
        Callable[[str, dict[str, object]], None],
        getattr(executor, "_broadcast_file_event"),
    )
    _ = broadcast("web_search", {"query": "test"})


def test_broadcast_file_event_publishes_for_read_file(executor: ToolExecutor, tmp_path: Path):
    """_broadcast_file_event publishes FileOpened for read_file on an existing file."""
    test_file = tmp_path / "test.txt"
    _ = test_file.write_text("hello")

    published: list[tuple[str, dict[str, object]]] = []
    with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
        def publish(event_type: str, **kwargs: object) -> None:
            published.append((event_type, kwargs))

        mock_bus.publish = publish
        broadcast = cast(
            Callable[[str, dict[str, object]], None],
            getattr(executor, "_broadcast_file_event"),
        )
        _ = broadcast("read_file", {"file_path": str(test_file)})

    assert len(published) == 1
    assert published[0][0] == "FileOpened"
    assert published[0][1]["filepath"] == str(test_file)


def test_broadcast_file_event_publishes_for_write_file(executor: ToolExecutor, tmp_path: Path):
    """_broadcast_file_event publishes FileModified for write_file."""
    test_file = tmp_path / "output.txt"
    _ = test_file.write_text("data")

    published: list[tuple[str, dict[str, object]]] = []
    with patch("antigravity_k.engine.event_bus.global_event_bus") as mock_bus:
        def publish(event_type: str, **kwargs: object) -> None:
            published.append((event_type, kwargs))

        mock_bus.publish = publish
        broadcast = cast(
            Callable[[str, dict[str, object]], None],
            getattr(executor, "_broadcast_file_event"),
        )
        _ = broadcast("write_file", {"file_path": str(test_file)})

    assert published[0][0] == "FileModified"


def test_broadcast_file_event_skips_nonexistent_file(executor: ToolExecutor):
    """_broadcast_file_event does nothing for a non-existent file path."""
    # Should not raise.
    broadcast = cast(
        Callable[[str, dict[str, object]], None],
        getattr(executor, "_broadcast_file_event"),
    )
    _ = broadcast("read_file", {"file_path": "/nonexistent/path/file.txt"})


def test_explicitly_contracted_tool_bypasses_approval_pause(tmp_path: Path):
    # Given: a task whose checkpoint records write_file as a tool the user explicitly requested.
    from antigravity_k.engine import gate_pipeline
    from antigravity_k.engine.task_state_store import (
        TaskExecutionContext,
        TaskStateStore,
        bind_task_execution_context,
    )

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("task-contract", "write and run", "pending", "2026-08-13T00:00:00+00:00")
    store.save_checkpoint("task-contract", 0, '{"expected_tools": ["write_file"]}', "")

    reg = MagicMock(spec=ToolRegistry)
    reg._tools = {}
    write_tool = _make_tool("write_file", required=["file_path"])
    write_tool.return_value = "wrote"
    _registry_tools(reg)["write_file"] = write_tool
    reg.get = MagicMock(side_effect=partial(_lookup_tool, reg))
    reg.__contains__ = _contains_tool

    def write_execution(
        _name: str, _args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.ALLOW, "wrote"

    reg.execute_with_permission = write_execution

    gate = MagicMock(spec=PermissionGate)
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        ex = ToolExecutor(
            tool_registry=reg,
            permission_gate=gate,
            project_root=str(tmp_path),
            gate_pipeline=cast(
                Callable[[], object], getattr(gate_pipeline, "create_default_pipeline")
            )(),
        )
    setattr(ex, "_immune_system", None)

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
    _registry_tools(tool_registry)["run_bash_command"] = failing_tool
    tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))

    def failing_command_execution(
        _name: str, _args: dict[str, object], objective: str = ""
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.ALLOW, "[exit_code=2]\nSTDERR:\nboom"

    tool_registry.execute_with_permission = failing_command_execution

    # When: the executor runs the tool and records the outcome.
    _ = executor.execute("run_bash_command", {"command": "false"})

    # Then: the result is classified as a failure so the consecutive-error counter
    # advances and the recovery loop can trigger — the exit-code marker must not mask it.
    assert executor.tool_call_history[-1]["success"] is False
    assert cast(int, getattr(executor, "_consecutive_errors")) == 1


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


class TestApprovalWiring:
    """게이트 일시정지 ↔ ApprovalManager 연동."""

    @staticmethod
    def _executor_with_pipeline(tool_registry, permission_gate, tmp_path):
        from antigravity_k.engine import gate_pipeline
        from antigravity_k.engine.tool_executor import ToolExecutor

        with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
            ex = ToolExecutor(
                tool_registry=tool_registry,
                permission_gate=permission_gate,
                project_root=str(tmp_path),
                gate_pipeline=cast(
                    Callable[[], object], getattr(gate_pipeline, "create_default_pipeline")
                )(),
            )
        setattr(ex, "_immune_system", None)
        return ex

    def test_pause_registers_approval_request(
        self, tool_registry, permission_gate, tmp_path, monkeypatch
    ):
        """게이트 일시정지 시 승인 요청이 등록되고 요청 ID가 결과에 포함된다."""
        from antigravity_k.engine import approval_manager as am

        requests: list[dict] = []

        class FakeManager:
            def is_always_allowed(self, tool_name):
                return False

            def consume_one_time_approval(self, tool_name):
                return False

            def get_pending(self):
                return []

            def request_approval(self, tool_name, tool_args, description="", project_root=None, **kw):
                requests.append({"tool": tool_name, "desc": description})
                req = am.ApprovalRequest(
                    request_id="req-123",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    description=description,
                )
                return req

        monkeypatch.setattr(am, "get_approval_manager", lambda: FakeManager())
        write_tool = _make_tool("write_file", required=[])
        _registry_tools(tool_registry)["write_file"] = write_tool
        tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))
        ex = self._executor_with_pipeline(tool_registry, permission_gate, tmp_path)

        result = ex.execute("write_file", {"file_path": str(tmp_path / "a.txt"), "content": "x"})

        assert "[APPROVAL REQUIRED]" in result
        assert "req-123" in result
        assert requests and requests[0]["tool"] == "write_file"

    def test_always_allowed_tool_executes_without_pause(
        self, tool_registry, permission_gate, tmp_path, monkeypatch
    ):
        from antigravity_k.engine import approval_manager as am

        class FakeManager:
            def is_always_allowed(self, tool_name):
                return True

            def consume_one_time_approval(self, tool_name):
                return False

            def get_pending(self):
                return []

            def request_approval(self, tool_name, tool_args, **kw):
                req = am.ApprovalRequest(
                    request_id="auto-1",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    status=am.ApprovalStatus.ALWAYS_ALLOW,
                )
                return req

        monkeypatch.setattr(am, "get_approval_manager", lambda: FakeManager())
        write_tool = _make_tool("write_file", required=[])
        _registry_tools(tool_registry)["write_file"] = write_tool
        tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))
        ex = self._executor_with_pipeline(tool_registry, permission_gate, tmp_path)

        result = ex.execute("write_file", {"file_path": str(tmp_path / "b.txt"), "content": "x"})

        assert result == "ok"  # 일시정지 없이 실행됨

    def test_one_time_approval_consumed_on_retry(
        self, tool_registry, permission_gate, tmp_path, monkeypatch
    ):
        from antigravity_k.engine import approval_manager as am

        class FakeManager:
            def __init__(self):
                self.consumed = False

            def is_always_allowed(self, tool_name):
                return False

            def consume_one_time_approval(self, tool_name):
                if self.consumed:
                    return False
                self.consumed = True
                return True

            def get_pending(self):
                return []

            def request_approval(self, *a, **kw):
                raise AssertionError("소비 가능한 승인이 있으면 새 요청을 만들지 않는다")

        monkeypatch.setattr(am, "get_approval_manager", lambda: fake)
        fake = FakeManager()
        monkeypatch.setattr(am, "get_approval_manager", lambda: fake)
        write_tool = _make_tool("write_file", required=[])
        _registry_tools(tool_registry)["write_file"] = write_tool
        tool_registry.get = MagicMock(side_effect=partial(_lookup_tool, tool_registry))
        ex = self._executor_with_pipeline(tool_registry, permission_gate, tmp_path)

        result = ex.execute("write_file", {"file_path": str(tmp_path / "c.txt"), "content": "x"})

        assert result == "ok"
        assert fake.consumed
