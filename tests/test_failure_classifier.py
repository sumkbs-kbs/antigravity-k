"""Tests for FailureClassifier + RecoveryStrategy — tool failure classification and recovery playbook."""

from __future__ import annotations

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
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_registry import ToolRegistry

CLASSIFICATION_CASES = [
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
def test_classify_tool_failure(tool, message, expected):
    failure = classify_tool_failure(tool, message)
    assert failure.category is expected
    assert failure.tool_name == tool
    assert failure.message == message


def test_classify_accepts_non_string():
    failure = classify_tool_failure("read_file", 42)
    assert failure.category is FailureCategory.unknown


RETRYABLE_CASES = [
    (FailureCategory.timeout, True),
    (FailureCategory.external_service, True),
    (FailureCategory.unknown, True),
    (FailureCategory.test_failure, False),
    (FailureCategory.sandbox_violation, False),
    (FailureCategory.git_conflict, False),
]


@pytest.mark.parametrize(("category", "expected"), RETRYABLE_CASES)
def test_retryable_property(category, expected):
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


def _make_tool(name="dummy", *, required=None):
    tool = MagicMock()
    tool.name = name
    tool.parameters_schema = {"required": required or []}
    return tool


def _make_executor(tmp_path):
    reg = MagicMock(spec=ToolRegistry)
    reg._tools = {}
    dummy = _make_tool("dummy", required=["x"])
    reg._tools["dummy"] = dummy
    reg.get = MagicMock(side_effect=lambda n: reg._tools.get(n))
    reg.__contains__ = lambda self, name: name in reg._tools
    reg.execute_with_permission = lambda name, args, objective="": (Permission.ALLOW, "ok")
    gate = MagicMock(spec=PermissionGate)
    with patch("antigravity_k.engine.tool_executor.ImmuneSystem"):
        ex = ToolExecutor(tool_registry=reg, permission_gate=gate, project_root=str(tmp_path))
    ex._immune_system = None
    return ex, reg


def test_post_execute_records_classified_failure(tmp_path):
    ex, reg = _make_executor(tmp_path)
    reg.execute_with_permission = lambda name, args, objective="": (
        Permission.ALLOW,
        "Error: [exit_code=1] command timed out",
    )
    ex.execute("dummy", {"x": 1})
    assert ex._last_failure is not None
    assert ex._last_failure.category is FailureCategory.timeout


def test_post_execute_resets_failure_on_success(tmp_path):
    ex, reg = _make_executor(tmp_path)
    reg.execute_with_permission = lambda name, args, objective="": (
        Permission.ALLOW,
        "Error: [exit_code=1] command timed out",
    )
    ex.execute("dummy", {"x": 1})
    assert ex._last_failure is not None
    reg.execute_with_permission = lambda name, args, objective="": (Permission.ALLOW, "ok")
    ex.execute("dummy", {"x": 1})
    assert ex._last_failure is None


def test_trigger_recovery_returns_playbook_for_sandbox_violation(tmp_path):
    ex, _ = _make_executor(tmp_path)
    ex._last_failure = classify_tool_failure("run_bash_command", "Error: sandbox-exec: Operation not permitted")
    result = ex._trigger_recovery("run_bash_command", {}, "Error: sandbox-exec")
    assert "sandbox" in result
    assert ex._consecutive_errors == 0


def test_trigger_recovery_escalates_unknown_to_immune(tmp_path):
    ex, _ = _make_executor(tmp_path)
    ex._immune_system = MagicMock()
    ex._immune_system.heal = MagicMock(return_value="healed")
    ex._last_failure = classify_tool_failure("dummy", "Error: mysterious bug in executor")
    result = ex._trigger_recovery("dummy", {}, "Error: mysterious")
    assert result == "healed"
    ex._immune_system.heal.assert_called_once()