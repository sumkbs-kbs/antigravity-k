import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from antigravity_k.api.routes import agent_tools
from antigravity_k.api.routes.agent_tools import (
    AutonomousQARequest,
    TDDGenerateRequest,
    VisionAnalyzeRequest,
    _accessibility_tree,
    _browser_error_status,
    _guard_browser_route,
)
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.sandbox import SandboxResult
from antigravity_k.tools.permission_gate import Permission


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


def _browser_session_key(session_id: str) -> str:
    subject = "pin-user" if config.security.access_pin else "loopback"
    return hashlib.sha256(f"{subject}:{session_id}".encode("utf-8")).hexdigest()


def _browser_headers(session_id: str) -> dict[str, str]:
    return {**_auth_headers(), "X-AGK-Browser-Session": session_id}


def test_missing_playwright_executable_is_service_unavailable() -> None:
    error = RuntimeError("Executable doesn't exist at /tmp/chromium")

    assert _browser_error_status(error) == 503
    assert _browser_error_status(RuntimeError("browser crashed")) == 500


async def test_accessibility_tree_uses_current_playwright_aria_snapshot() -> None:
    page = MagicMock()
    page.aria_snapshot = AsyncMock(return_value="- document")
    del page.accessibility

    assert await _accessibility_tree(page) == "- document"


def test_vision_analyze_without_screenshot_returns_400():
    session_id = "vision-test"
    session_key = _browser_session_key(session_id)
    agent_tools.browser_sessions.get(session_key).page = None

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/agent/tools/browser/vision-analyze",
                json={"prompt": "check the UI"},
                headers=_browser_headers(session_id),
            )
    finally:
        agent_tools.browser_sessions.discard(session_key)

    assert response.status_code == 400
    assert "No screenshot" in response.json()["detail"]


def test_browser_action_requires_launch_returns_400():
    session_id = "snapshot-test"
    session_key = _browser_session_key(session_id)
    agent_tools.browser_sessions.get(session_key).page = None

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/agent/tools/browser/action",
                json={"action": "snapshot"},
                headers=_browser_headers(session_id),
            )
    finally:
        agent_tools.browser_sessions.discard(session_key)

    assert response.status_code == 400
    assert "Browser is not launched" in response.json()["detail"]


def test_browser_navigation_honors_permission_denial_before_side_effect(monkeypatch):
    session_id = "navigation-test"
    session_key = _browser_session_key(session_id)
    page = MagicMock()
    page.goto = AsyncMock()
    agent_tools.browser_sessions.get(session_key).page = page

    gate = MagicMock()
    gate.decide.return_value = MagicMock(permission=Permission.DENY)
    monkeypatch.setattr(agent_tools, "_permission_gate", lambda: gate)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/agent/tools/browser/action",
                json={"action": "goto", "url": "https://example.com"},
                headers=_browser_headers(session_id),
            )
    finally:
        agent_tools.browser_sessions.discard(session_key)

    assert response.status_code == 403
    page.goto.assert_not_awaited()


async def test_browser_route_aborts_non_http_schemes():
    route = MagicMock()
    route.abort = AsyncMock()
    route.continue_ = AsyncMock()
    request = MagicMock(url="file:///etc/passwd")

    await _guard_browser_route(route, request)

    route.abort.assert_awaited_once_with(error_code="blockedbyclient")
    route.continue_.assert_not_awaited()


def test_tdd_generate_rejects_target_outside_project_before_engine(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config.paths, "project_root", tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/tdd-generate",
            json={"prompt": "write code", "target_file_path": "/tmp/escape.py"},
            headers=_auth_headers(),
        )

    assert response.status_code == 403
    assert "project root" in response.json()["detail"]


def test_autonomous_qa_honors_permission_denial_before_engine_start(monkeypatch):
    gate = MagicMock()
    gate.decide.return_value = MagicMock(permission=Permission.DENY)
    monkeypatch.setattr(agent_tools, "_permission_gate", lambda: gate)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/browser/autonomous-qa",
            json={"url": "http://127.0.0.1:5173"},
            headers=_auth_headers(),
        )

    assert response.status_code == 403


def test_external_brain_send_honors_permission_denial_before_adapter_start(monkeypatch):
    gate = MagicMock()
    gate.decide.return_value = MagicMock(permission=Permission.DENY)
    monkeypatch.setattr(agent_tools, "_permission_gate", lambda: gate)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/external-brain/send",
            json={"prompt": "run a check", "target": "gemini_app"},
            headers=_auth_headers(),
        )

    assert response.status_code == 403


def test_tdd_generate_honors_permission_denial_before_engine_start(monkeypatch):
    gate = MagicMock()
    gate.decide.return_value = MagicMock(permission=Permission.DENY)
    monkeypatch.setattr(agent_tools, "_permission_gate", lambda: gate)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/tdd-generate",
            json={"prompt": "write a test"},
            headers=_auth_headers(),
        )

    assert response.status_code == 403


def test_agent_model_defaults_prioritize_local_qwen():
    assert AutonomousQARequest().vision_model == "qwen3.6:latest"
    assert AutonomousQARequest().coding_model == "qwen3.6:latest"
    assert VisionAnalyzeRequest().model == "qwen3.6:latest"
    assert TDDGenerateRequest(prompt="write a test").coding_model == "qwen3.6:latest"


@pytest.mark.parametrize("request_model", [AutonomousQARequest, TDDGenerateRequest])
@pytest.mark.parametrize("max_iterations", [0, 11])
def test_autonomous_loop_iteration_budget_is_bounded(request_model, max_iterations):
    payload = {"max_iterations": max_iterations}
    if request_model is TDDGenerateRequest:
        payload["prompt"] = "write a test"

    with pytest.raises(ValidationError):
        request_model(**payload)


def test_agent_fs_write_and_read_are_limited_to_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(agent_tools.config.paths, "project_root", project_root)

    target = project_root / "qa-note.txt"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with TestClient(app) as client:
        write_response = client.post(
            "/api/agent/tools/fs/write",
            json={"path": str(target), "content": "qa-ok"},
            headers=_auth_headers(),
        )
        read_response = client.post(
            "/api/agent/tools/fs/read",
            json={"path": str(target)},
            headers=_auth_headers(),
        )
        denied_response = client.post(
            "/api/agent/tools/fs/write",
            json={"path": str(outside), "content": "nope"},
            headers=_auth_headers(),
        )
        denied_read_response = client.post(
            "/api/agent/tools/fs/read",
            json={"path": str(outside)},
            headers=_auth_headers(),
        )

    assert write_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json()["content"] == "qa-ok"
    assert denied_response.status_code == 403
    assert denied_read_response.status_code == 403


def test_agent_shell_blocks_dangerous_commands():
    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/shell/run",
            json={"command": "rm -rf /"},
            headers=_auth_headers(),
        )

    assert response.status_code == 403


def test_agent_shell_uses_sandbox_runner_and_clamps_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_tools.config.paths, "project_root", tmp_path)
    calls = {}

    class FakeSandboxRunner:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def execute(self, command, **kwargs):
            calls["execute"] = {"command": command, **kwargs}
            return SandboxResult(success=True, stdout="sandbox-ok", sandboxed=True)

    monkeypatch.setattr(agent_tools, "SandboxRunner", FakeSandboxRunner)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/shell/run",
            json={"command": "printf sandbox-ok", "cwd": str(tmp_path), "timeout": 999},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["sandboxed"] is True
    assert response.json()["stdout"] == "sandbox-ok"
    assert calls["execute"]["cwd"] == str(tmp_path)
    assert calls["execute"]["timeout"] == config.security.max_execution_time


def test_agent_shell_rejects_cwd_outside_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(agent_tools.config.paths, "project_root", project_root)

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/shell/run",
            json={"command": "echo blocked", "cwd": str(outside)},
            headers=_auth_headers(),
        )

    assert response.status_code == 403
