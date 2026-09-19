from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import filesystem
from antigravity_k.api.server import app
from antigravity_k.config import config


def test_fs_browse_cannot_escape_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(workspace))

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app) as client:
        response = client.get("/api/fs/browse", params={"dir": "/"}, headers=headers)

    assert response.status_code == 403


def test_fs_list_uses_runtime_workspace_as_permission_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "runtime-workspace"
    workspace.mkdir()
    _ = (workspace / "README.md").write_text("runtime wheel workspace", encoding="utf-8")
    installed_package_root = tmp_path / "site-packages"
    installed_package_root.mkdir()

    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(workspace))
    monkeypatch.setattr(config.paths, "project_root", installed_package_root)

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app) as client:
        response = client.get("/api/fs/list", params={"dir": "."}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "items": [{"name": "README.md", "path": "README.md", "is_dir": False}],
    }
