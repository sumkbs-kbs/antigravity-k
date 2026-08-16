from fastapi.testclient import TestClient

from antigravity_k.api.routes import filesystem
from antigravity_k.api.server import app
from antigravity_k.config import config


def test_fs_browse_cannot_escape_workspace_root(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(workspace))

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app) as client:
        response = client.get("/api/fs/browse", params={"dir": "/"}, headers=headers)

    assert response.status_code == 403
