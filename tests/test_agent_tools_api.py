from fastapi.testclient import TestClient

from antigravity_k.api.routes import agent_tools
from antigravity_k.api.server import app
from antigravity_k.config import config


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


def test_vision_analyze_without_screenshot_returns_400():
    agent_tools.browser_state.page = None

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/browser/vision-analyze",
            json={"prompt": "check the UI"},
            headers=_auth_headers(),
        )

    assert response.status_code == 400
    assert "No screenshot" in response.json()["detail"]


def test_browser_action_requires_launch_returns_400():
    agent_tools.browser_state.page = None

    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/browser/action",
            json={"action": "snapshot"},
            headers=_auth_headers(),
        )

    assert response.status_code == 400
    assert "Browser is not launched" in response.json()["detail"]


def test_agent_fs_write_and_read_are_limited_to_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(agent_tools.config.paths, "project_root", project_root)

    target = project_root / "qa-note.txt"
    outside = tmp_path / "outside.txt"

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

    assert write_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json()["content"] == "qa-ok"
    assert denied_response.status_code == 403


def test_agent_shell_blocks_dangerous_commands():
    with TestClient(app) as client:
        response = client.post(
            "/api/agent/tools/shell/run",
            json={"command": "rm -rf /"},
            headers=_auth_headers(),
        )

    assert response.status_code == 403
