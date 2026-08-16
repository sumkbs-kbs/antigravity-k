"""Tests for ErrorDistiller module."""

from antigravity_k.engine.error_distiller import ErrorDistiller


def test_distill_empty_error():
    result = ErrorDistiller.distill("test_tool", "")
    assert "ToolExecutionError" in result


def test_distill_python_traceback():
    traceback_sample = """
Traceback (most recent call last):
  File "src/antigravity_k/engine/sample.py", line 42, in calculate_metrics
    result = values[index] / divisor
ZeroDivisionError: division by zero
"""
    result = ErrorDistiller.distill("run_command", traceback_sample)
    assert "ZeroDivisionError" in result
    assert "line 42" in result
    assert "division by zero" in result


def test_distill_command_not_found():
    raw_error = "zsh: command not found: unknown_binary"
    result = ErrorDistiller.distill("run_command", raw_error)
    assert "CommandNotFound" in result
    assert "unknown_binary" in result


def test_distill_permission_denied():
    raw_error = "Permission denied: '/etc/shadow'"
    result = ErrorDistiller.distill("read_file", raw_error)
    assert "PermissionDenied" in result
    assert "/etc/shadow" in result


def test_distill_json_decode_error():
    raw_error = "JSONDecodeError: Expecting ',' delimiter: line 1 column 15 (char 14)"
    result = ErrorDistiller.distill("api_call", raw_error)
    assert "JSONParseError" in result
