"""Tests for FailureClassifier + RecoveryStrategy — tool failure classification and recovery playbook."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.engine.failure_classifier import (
    ClassifiedFailure,
    FailureCategory,
    RecoveryAction,
    RecoveryStrategy,
    RecoveryStrategyRegistry,
    classify_tool_failure,
)
from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.tool_contracts import Permission
from antigravity_k.tools.tool_registry import ToolRegistry

ClassificationCase = tuple[str, str, FailureCategory]

CLASSIFICATION_CASES: list[ClassificationCase] = [
    ("git_commit", "Error: fatal: not a git repository", FailureCategory.git_conflict),
    ("git_commit", "Error: Your local changes would be overwritten", FailureCategory.git_conflict),
    ("run_bash_command", "Error: [exit_code=1] pytest FAILED 2 tests", FailureCategory.test_failure),
    ("web_search", "❌ [web_search Error] No results found for query", FailureCategory.external_service),
    ("write_file", "Error: [DENIED] Tool execution blocked by permission rules.", FailureCategory.permission_denied),
    ("read_file", "Error: [BLOCKED] cannot read outside sandbox", FailureCategory.blocked_by_guard),
    ("run_bash_command", "Error: [exit_code=124] command timed out", FailureCategory.timeout),
    ("edit_file", "FileNotFoundError: No such file or directory: foo.py", FailureCategory.file_not_found),
    ("run_bash_command", "Error: [exit_code=1] ruff check failed", FailureCategory.lint_failure),
    ("run_bash_command", "Error: sandbox-exec: Operation not permitted", FailureCategory.sandbox_violation),
    ("write_file", "Error: Unknown tool 'frobnicate'", FailureCategory.unknown_tool),
    ("read_file", "Error: Missing required arguments: file_path", FailureCategory.missing_arguments),
    ("read_file", "Error: invalid value for path: None", FailureCategory.invalid_arguments),
    ("write_file", "Error: [APPROVAL REQUIRED] needs user consent", FailureCategory.approval_required),
    ("run_bash_command", "Error: [exit_code=1] No space left on device", FailureCategory.resource_exhausted),
    ("run_bash_command", "Error: [exit_code=1] connection refused", FailureCategory.external_service),
    ("run_bash_command", "Error: something completely unexpected", FailureCategory.unknown),
]


@pytest.mark.parametrize(("tool", "message", "expected"), CLASSIFICATION_CASES)
def test_classify_tool_failure(tool: str, message: str, expected: FailureCategory) -> None:
    failure = classify_tool_failure(tool, message)
    assert failure.category is expected
    assert failure.tool_name == tool
    assert failure.message == message


def test_classify_accepts_non_string():
    failure = classify_tool_failure("read_file", cast(str, cast(object, 42)))
    assert failure.category is FailureCategory.unknown


RetryableCase = tuple[FailureCategory, bool]

RETRYABLE_CASES: list[RetryableCase] = [
    (FailureCategory.timeout, True),
    (FailureCategory.external_service, True),
    (FailureCategory.unknown, True),
    (FailureCategory.test_failure, False),
    (FailureCategory.sandbox_violation, False),
    (FailureCategory.git_conflict, False),
]


@pytest.mark.parametrize(("category", "expected"), RETRYABLE_CASES)
def test_retryable_property(category: FailureCategory, expected: bool) -> None:
    failure = ClassifiedFailure(category, "tool", "msg")
    assert failure.retryable is expected


def test_registry_default_strategy_per_category():
    reg = RecoveryStrategyRegistry()
    assert reg.strategy_for("any_tool", FailureCategory.sandbox_violation).action is RecoveryAction.STOP
    assert reg.strategy_for("any_tool", FailureCategory.approval_required).action is RecoveryAction.ASK_USER
    assert reg.strategy_for("any_tool", FailureCategory.permission_denied).action is RecoveryAction.ASK_USER
    assert reg.strategy_for("any_tool", FailureCategory.timeout).action is RecoveryAction.RETRY
    assert reg.strategy_for("any_tool", FailureCategory.test_failure).action is RecoveryAction.RETRY_FIXED
    assert reg.strategy_for("any_tool", FailureCategory.unknown).action is RecoveryAction.ESCALATE_IMMUNE


def test_registry_tool_override_web_search():
    reg = RecoveryStrategyRegistry()
    failure = classify_tool_failure("web_search", "❌ No results found")
    assert reg.strategy_for("web_search", failure.category).action is RecoveryAction.SUGGEST_ALTERNATIVE
    assert reg.strategy_for("read_file", FailureCategory.external_service).action is RecoveryAction.RETRY


def test_registry_register_override():
    reg = RecoveryStrategyRegistry()
    reg.register_override(
        "write_file",
        FailureCategory.permission_denied,
        RecoveryStrategy(RecoveryAction.STOP, guidance_template="nope"),
    )
    assert reg.strategy_for("write_file", FailureCategory.permission_denied).action is RecoveryAction.STOP
    assert reg.strategy_for("read_file", FailureCategory.permission_denied).action is RecoveryAction.ASK_USER


def test_suggest_recovery_renders_guidance():
    reg = RecoveryStrategyRegistry()
    failure = classify_tool_failure("git_commit", "Error: fatal: not a git repository")
    guidance = reg.suggest_recovery(failure)
    assert "git_commit" in guidance
    assert "git status" in guidance


def test_render_without_template_falls_back():
    strategy = RecoveryStrategy(RecoveryAction.STOP)
    failure = ClassifiedFailure(FailureCategory.timeout, "tool", "boom")
    out = strategy.render(failure)
    assert "[RECOVERY:stop]" in out
    assert "boom" in out


def _make_tool(name: str = "dummy", *, required: list[str] | None = None) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.parameters_schema = {"required": required or []}
    return tool


def _registry_tools(reg: MagicMock) -> dict[str, MagicMock]:
    return cast(dict[str, MagicMock], getattr(reg, "_tools"))


def _last_failure(executor: ToolExecutor) -> ClassifiedFailure | None:
    return cast(ClassifiedFailure | None, getattr(executor, "_last_failure"))


def _set_last_failure(executor: ToolExecutor, value: ClassifiedFailure | None) -> None:
    setattr(executor, "_last_failure", value)


def _set_immune_system(executor: ToolExecutor, value: object) -> None:
    setattr(executor, "_immune_system", value)


def _consecutive_errors(executor: ToolExecutor) -> int:
    return cast(int, getattr(executor, "_consecutive_errors"))


def _trigger_recovery(
    executor: ToolExecutor,
    name: str,
    args: dict[str, object],
    result: str,
) -> str:
    callback = cast(Callable[[str, dict[str, object], str], str], getattr(executor, "_trigger_recovery"))
    return callback(name, args, result)


def _make_executor(tmp_path: Path) -> tuple[ToolExecutor, MagicMock]:
    reg = MagicMock(spec=ToolRegistry)
    setattr(reg, "_tools", {})
    dummy = _make_tool("dummy", required=["x"])
    _registry_tools(reg)["dummy"] = dummy

    def lookup(name: str) -> MagicMock | None:
        return _registry_tools(reg).get(name)

    def contains(_self: object, name: str) -> bool:
        return name in _registry_tools(reg)

    def execute_with_permission(
        _name: str,
        _args: dict[str, object],
        objective: str = "",
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.ALLOW, "ok"

    reg.get = MagicMock(side_effect=lookup)
    reg.__contains__ = contains
    reg.execute_with_permission = execute_with_permission
    gate = MagicMock(spec=PermissionGate)
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        ex = ToolExecutor(tool_registry=reg, permission_gate=gate, project_root=str(tmp_path))
    _set_immune_system(ex, None)
    return ex, reg


def test_post_execute_records_classified_failure(tmp_path: Path) -> None:
    ex, reg = _make_executor(tmp_path)
    def failing_execution(
        _name: str,
        _args: dict[str, object],
        objective: str = "",
    ) -> tuple[Permission, str]:
        _ = objective
        return (
        Permission.ALLOW,
        "Error: [exit_code=1] command timed out",
        )

    reg.execute_with_permission = failing_execution
    _ = ex.execute("dummy", {"x": 1})
    failure = _last_failure(ex)
    assert failure is not None
    assert failure.category is FailureCategory.timeout


def test_post_execute_resets_failure_on_success(tmp_path: Path) -> None:
    ex, reg = _make_executor(tmp_path)
    def failing_execution(
        _name: str,
        _args: dict[str, object],
        objective: str = "",
    ) -> tuple[Permission, str]:
        _ = objective
        return (
        Permission.ALLOW,
        "Error: [exit_code=1] command timed out",
        )

    def successful_execution(
        _name: str,
        _args: dict[str, object],
        objective: str = "",
    ) -> tuple[Permission, str]:
        _ = objective
        return Permission.ALLOW, "ok"

    reg.execute_with_permission = failing_execution
    _ = ex.execute("dummy", {"x": 1})
    assert _last_failure(ex) is not None
    reg.execute_with_permission = successful_execution
    _ = ex.execute("dummy", {"x": 1})
    assert _last_failure(ex) is None


def test_trigger_recovery_returns_playbook_for_sandbox_violation(tmp_path: Path) -> None:
    ex, _ = _make_executor(tmp_path)
    _set_last_failure(ex, classify_tool_failure("run_bash_command", "Error: sandbox-exec: Operation not permitted"))
    result = _trigger_recovery(ex, "run_bash_command", {}, "Error: sandbox-exec")
    assert "sandbox" in result
    assert _consecutive_errors(ex) == 0


def test_trigger_recovery_escalates_unknown_to_immune(tmp_path: Path) -> None:
    ex, _ = _make_executor(tmp_path)
    immune = MagicMock()
    heal = MagicMock(return_value="healed")
    immune.heal = heal
    _set_immune_system(ex, immune)
    _set_last_failure(ex, classify_tool_failure("dummy", "Error: mysterious bug in executor"))
    result = _trigger_recovery(ex, "dummy", {}, "Error: mysterious")
    # 복구 메시지는 실제 오류 원문을 포함한다 (원문 상실 방지)
    assert result.endswith("healed")
    assert "Error: mysterious" in result
    assert cast(int, getattr(heal, "call_count")) == 1
