"""Tests for AgentErrorJournal — Agentic AI Error Diagnostic & Logging System."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from antigravity_k.api.error_handler import global_exception_handler
from antigravity_k.cli import app as cli_app
from antigravity_k.engine.agent_error_journal import (
    AgentErrorJournal,
    _extract_code_context,
    _sanitize_headers,
    _sanitize_value,
)


def _trigger_sample_exception():
    """Helper to trigger an exception with an actual source file frame."""
    x = 10
    y = 0
    return x / y


def test_sanitize_headers_and_values():
    """Verify sensitive tokens, passwords, and authorization headers are redacted."""
    headers = {
        "Host": "127.0.0.1:8000",
        "Authorization": "Bearer secret-token-12345",
        "X-API-Key": "my-secret-key",
        "Cookie": "session=abcde12345",
        "User-Agent": "pytest",
    }
    sanitized = _sanitize_headers(headers)
    assert sanitized["Host"] == "127.0.0.1:8000"
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["X-API-Key"] == "[REDACTED]"
    assert sanitized["Cookie"] == "[REDACTED]"
    assert sanitized["User-Agent"] == "pytest"

    # Value sanitization
    assert _sanitize_value("password", "super-secret") == "[REDACTED]"
    assert _sanitize_value("user_token", "jwt-token") == "[REDACTED]"
    assert _sanitize_value("normal_key", 42) == 42


def test_extract_code_context(tmp_path: Path):
    """Verify code context extracts 5 lines before and after with marker."""
    dummy_file = tmp_path / "dummy.py"
    lines = [f"line_{i} = {i}" for i in range(1, 21)]
    dummy_file.write_text("\n".join(lines), encoding="utf-8")

    snippet = _extract_code_context(str(dummy_file), line_no=10, context_lines=2)
    assert ">>>    10 | line_10 = 10" in snippet
    assert "        9 | line_9 = 9" in snippet
    assert "       11 | line_11 = 11" in snippet


def test_record_error_and_persistence(tmp_path: Path):
    """Verify recording an error produces JSONL log and markdown incident card."""
    journal = AgentErrorJournal(logs_dir=tmp_path)

    try:
        _trigger_sample_exception()
    except ZeroDivisionError as exc:
        record = journal.record_error(
            exc=exc,
            component="test_runner",
            correlation_id="cid-test-123",
            request_context={
                "method": "POST",
                "path": "/api/test/fail",
                "headers": {"Authorization": "Bearer raw-key-999"},
            },
        )

    # Validate in-memory record
    assert record.error_id.startswith("ERR-")
    assert record.error_type == "ZeroDivisionError"
    assert "division by zero" in record.message
    assert record.correlation_id == "cid-test-123"
    assert record.component == "test_runner"
    assert "test_agent_error_journal.py" in record.failing_file
    assert record.failing_function == "_trigger_sample_exception"
    assert ">>>" in record.code_context
    assert record.request_context["headers"]["Authorization"] == "[REDACTED]"
    assert "Agentic AI Code Fix Task" in record.ai_fix_prompt

    # Validate JSONL persistence
    jsonl_file = tmp_path / "agent_errors.jsonl"
    assert jsonl_file.is_file()
    lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    saved_data = json.loads(lines[0])
    assert saved_data["error_id"] == record.error_id
    assert saved_data["error_type"] == "ZeroDivisionError"

    # Validate Markdown card persistence
    card_file = tmp_path / "agent_diagnostics" / f"{record.error_id}.md"
    assert card_file.is_file()
    card_content = card_file.read_text(encoding="utf-8")
    assert f'error_id: "{record.error_id}"' in card_content
    assert "ZeroDivisionError" in card_content
    assert "### 🤖 [Agentic AI Code Fix Task:" in card_content

    # Query journal
    listed = journal.list_errors()
    assert len(listed) == 1
    assert listed[0].error_id == record.error_id

    fetched = journal.get_error(record.error_id)
    assert fetched is not None
    assert fetched.error_id == record.error_id


def test_fastapi_error_handler_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify FastAPI catch-all handler logs to AgentErrorJournal and returns error_id."""
    test_journal = AgentErrorJournal(logs_dir=tmp_path)
    monkeypatch.setattr("antigravity_k.engine.agent_error_journal._journal_instance", test_journal)

    app = FastAPI()
    app.add_exception_handler(Exception, global_exception_handler)

    @app.get("/trigger-crash")
    def trigger_crash():
        raise RuntimeError("simulated-system-crash")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/trigger-crash", headers={"Authorization": "Bearer secret-auth"})

    assert response.status_code == 500
    data = response.json()
    assert data["ok"] is False
    assert data["error"] == "internal_error"
    assert "correlation_id" in data
    assert "error_id" in data
    assert data["error_id"].startswith("ERR-")

    # Verify journal has the entry
    recorded = test_journal.list_errors()
    assert len(recorded) == 1
    assert recorded[0].error_id == data["error_id"]
    assert recorded[0].error_type == "RuntimeError"
    assert recorded[0].message == "simulated-system-crash"
    assert recorded[0].request_context["headers"]["authorization"] == "[REDACTED]"


def test_cli_error_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify 'agk error list', 'inspect', and 'prompt' CLI commands."""
    test_journal = AgentErrorJournal(logs_dir=tmp_path)
    monkeypatch.setattr("antigravity_k.engine.agent_error_journal._journal_instance", test_journal)

    runner = CliRunner()

    # Empty list
    res = runner.invoke(cli_app, ["error", "list"])
    assert res.exit_code == 0
    assert "No runtime errors recorded in journal" in res.stdout

    # Record a test error
    try:
        raise KeyError("missing_config_key")
    except KeyError as exc:
        rec = test_journal.record_error(exc=exc, component="cli_test")

    # List with 1 item
    res_list = runner.invoke(cli_app, ["error", "list"])
    assert res_list.exit_code == 0
    assert rec.error_id in res_list.stdout
    assert "KeyErr" in res_list.stdout

    # Inspect
    res_inspect = runner.invoke(cli_app, ["error", "inspect", rec.error_id])
    assert res_inspect.exit_code == 0
    assert "missing_config_key" in res_inspect.stdout
    assert "Source Code Context" in res_inspect.stdout

    # Prompt
    res_prompt = runner.invoke(cli_app, ["error", "prompt", rec.error_id])
    assert res_prompt.exit_code == 0
    assert "Agentic AI Code Fix Task" in res_prompt.stdout
    assert "missing_config_key" in res_prompt.stdout


def test_system_errors_api_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify GET /api/system/errors and GET /api/system/errors/{error_id}."""
    test_journal = AgentErrorJournal(logs_dir=tmp_path)
    monkeypatch.setattr("antigravity_k.engine.agent_error_journal._journal_instance", test_journal)

    from antigravity_k.api.server import app

    client = TestClient(app)

    # Empty list
    res = client.get("/api/system/errors")
    assert res.status_code == 200
    assert res.json()["total"] == 0

    # Record error
    try:
        raise ValueError("test-system-error-api")
    except ValueError as exc:
        rec = test_journal.record_error(exc=exc, component="api_test")

    # List
    res_list = client.get("/api/system/errors")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["ok"] is True
    assert data["total"] == 1
    assert data["errors"][0]["error_id"] == rec.error_id

    # Detail
    res_detail = client.get(f"/api/system/errors/{rec.error_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["ok"] is True
    assert detail["error"]["error_id"] == rec.error_id
    assert detail["error"]["error_type"] == "ValueError"
    assert "test-system-error-api" in detail["error"]["message"]

    # 404 for unknown
    res_404 = client.get("/api/system/errors/non-existent-id")
    assert res_404.status_code == 404
