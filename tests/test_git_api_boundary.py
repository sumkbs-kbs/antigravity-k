import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from antigravity_k.api.routes import git_api
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.tools.permission_gate import Permission


def test_git_helper_rejects_working_directory_outside_project(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(git_api.config.paths, "project_root", project_root)

    with pytest.raises(HTTPException) as error:
        git_api._git(["status"], cwd=str(outside))

    assert error.value.status_code == 403


def test_git_helper_resolves_relative_path_inside_project(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    repo = project_root / "repo"
    repo.mkdir(parents=True)
    monkeypatch.setattr(git_api.config.paths, "project_root", project_root)
    calls = {}

    class FakeCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return FakeCompleted()

    monkeypatch.setattr(git_api.subprocess, "run", fake_run)

    assert git_api._git(["status"], cwd="repo") == "ok"
    assert calls["args"] == ["git", "status"]
    assert calls["kwargs"]["cwd"] == str(repo.resolve())
    assert calls["kwargs"]["check"] is False


def test_git_file_path_rejects_escape_from_repository(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(git_api.config.paths, "project_root", project_root)

    with pytest.raises(HTTPException) as error:
        git_api._resolve_repo_file("../outside.txt", ".")

    assert error.value.status_code == 403


def test_git_commit_honors_permission_denial_before_subprocess(monkeypatch):
    from unittest.mock import MagicMock

    permission_gate = MagicMock()
    permission_gate.check.return_value = Permission.DENY
    monkeypatch.setattr(git_api, "_permission_gate", lambda: permission_gate, raising=False)
    monkeypatch.setattr(git_api, "_git", lambda *args, **kwargs: "no-op")
    headers = {"X-Access-Pin": config.security.access_pin}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/git/commit",
            json={"path": ".", "message": "should be denied"},
            headers=headers,
        )

    assert response.status_code == 403
