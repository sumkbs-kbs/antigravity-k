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
    assert data["project_name"] == "Ssak-Ai"
    assert data["target"] == "로컬"
    assert "branch" in data
    assert isinstance(data["projects"], list)
    assert len(data["projects"]) >= 1


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
