from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.testclient import TestClient

from antigravity_k.api.routes import agency_api
from antigravity_k.engine.persistent_agency import AgencyConfig, PersistentAgencyController


class _Orchestrator:
    def __init__(self, controller: PersistentAgencyController) -> None:
        self.persistent_agency: PersistentAgencyController = controller


class _Runtime:
    def __init__(self, controller: PersistentAgencyController) -> None:
        self.orchestrator: _Orchestrator = _Orchestrator(controller)


def _client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[TestClient, PersistentAgencyController]:
    controller = PersistentAgencyController(str(tmp_path), AgencyConfig(enabled=True))
    monkeypatch.setattr(agency_api, "get_agent_runtime", lambda: _Runtime(controller))
    app = FastAPI()
    app.include_router(cast(APIRouter, getattr(agency_api, "router")))
    return TestClient(app), controller


def test_objective_control_plane_supports_create_get_and_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, controller = _client(monkeypatch, tmp_path)

    created = client.post(
        "/api/agency/objectives",
        json={"title": "Index the repository", "description": "Build durable context", "priority": 4},
    )

    assert created.status_code == 201
    objective = cast(dict[str, object], created.json())
    assert objective["project_id"] == controller.project_id
    assert objective["status"] == "pending"

    fetched = client.get(f"/api/agency/objectives/{objective['objective_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == objective
    listed = client.get("/api/agency/objectives")
    assert listed.status_code == 200
    assert listed.json() == [objective]

    rejected = client.post(
        "/api/agency/objectives",
        json={"project_id": "/another/project", "title": "out of scope"},
    )
    assert rejected.status_code == 403


def test_agency_status_pause_resume_and_context_are_observable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, controller = _client(monkeypatch, tmp_path)
    _ = controller.record_summary(controller.project_id, "main", "Durable memory is ready")

    status = client.get("/api/agency/status?query=memory")
    assert status.status_code == 200
    body = cast(dict[str, object], status.json())
    assert body["project_id"] == controller.project_id
    assert body["enabled"] is True
    assert body["paused"] is False
    context_text = cast(str, body["context_text"])
    scheduler = cast(dict[str, object], body["scheduler"])
    assert "Durable memory is ready" in context_text
    assert scheduler["reason"] == "idle_backoff"

    paused = client.post("/api/agency/pause", json={})
    assert paused.status_code == 200
    assert paused.json() == {"project_id": controller.project_id, "paused": True}
    paused_body = cast(dict[str, object], client.get("/api/agency/status").json())
    paused_scheduler = cast(dict[str, object], paused_body["scheduler"])
    assert paused_scheduler["reason"] == "paused"

    resumed = client.post("/api/agency/resume", json={})
    assert resumed.status_code == 200
    assert resumed.json() == {"project_id": controller.project_id, "paused": False}


def test_agency_objective_not_found_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _ = _client(monkeypatch, tmp_path)

    response = client.get("/api/agency/objectives/missing")

    assert response.status_code == 404
