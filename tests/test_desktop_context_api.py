"""Unit tests for Codex/Ssak-Ai Desktop Support Endpoints."""

import pytest
from starlette.testclient import TestClient

from antigravity_k.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_workspace_context(client):
    response = client.get("/api/workspace/context")
    assert response.status_code == 200
    data = response.json()
    # VAL-02: 레지스트리 active 프로젝트의 실제 이름을 반환한다 — 체크아웃
    # 디렉터리 이름(Ssak-Ai vs worktree 이름)에 결합하지 않는다.
    assert data["project_name"], "project_name은 비어 있으면 안 된다"
    assert data["workspace_path"], "workspace_path는 비어 있으면 안 된다"
    assert data["target"] == "로컬"
    assert "branch" in data
    assert isinstance(data["projects"], list)
    assert len(data["projects"]) >= 1
    active_projects = [p for p in data["projects"] if p["is_active"]]
    assert active_projects, "활성 프로젝트가 1개 이상 있어야 한다"
    assert active_projects[0]["name"] == data["project_name"]


def test_system_quota(client):
    response = client.get("/api/system/quota")
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["percent_remaining"] <= 100
    assert data["period_label"] in ["1주", "이번 주"]
    assert "Resets on" in data["resets_note"]


def test_access_mode(client):
    res1 = client.get("/api/system/access-mode")
    assert res1.status_code == 200
    assert res1.json()["mode"] in ["full_access", "read_only"]

    res2 = client.post("/api/system/access-mode", json={"mode": "read_only"})
    assert res2.status_code == 200
    assert res2.json()["mode"] == "read_only"

    res3 = client.post("/api/system/access-mode", json={"mode": "full_access"})
    assert res3.status_code == 200
    assert res3.json()["mode"] == "full_access"
