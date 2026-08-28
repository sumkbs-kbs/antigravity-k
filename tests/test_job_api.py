from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import JsonValue

from antigravity_k.api.routes import job_api
from antigravity_k.engine.scheduled_job_service import ScheduledJobService
from antigravity_k.engine.scheduled_job_store import ScheduledJobStore


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, JsonValue]] = []
        self.status = "done"
        self.output = "api output"
        self.error = "runtime failure"

    def submit_task(self, **kwargs: JsonValue) -> str:
        self.calls.append(kwargs)
        return "task-api-1"

    def get_task_status(self, task_id: str) -> dict[str, JsonValue]:
        return {
            "task_id": task_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
        }


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeRuntime:
    fake = FakeRuntime()
    service = ScheduledJobService(
        ScheduledJobStore(str(tmp_path / "jobs.db")),
        fake.submit_task,
        fake.get_task_status,
    )
    monkeypatch.setattr(job_api, "get_scheduled_job_service", lambda: service)
    return fake


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(job_api.router)
    return TestClient(app)


def test_job_crud_and_trigger_api(client: TestClient, runtime: FakeRuntime) -> None:
    run_at = datetime(2026, 8, 28, 9, 0, tzinfo=UTC).isoformat()
    created = client.post(
        "/api/jobs",
        json={
            "name": "morning briefing",
            "prompt": "Prepare my briefing",
            "model": "qwen3.8:27b",
            "context_mode": "continue",
            "schedule": {"kind": "once", "run_at": run_at},
        },
    )

    assert created.status_code == 201
    job = created.json()
    assert job["name"] == "morning briefing"
    assert job["status"] == "active"

    listed = client.get("/api/jobs")
    assert listed.status_code == 200
    assert [item["job_id"] for item in listed.json()] == [job["job_id"]]

    updated = client.patch(f"/api/jobs/{job['job_id']}", json={"name": "daily briefing"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "daily briefing"

    paused = client.post(f"/api/jobs/{job['job_id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post(f"/api/jobs/{job['job_id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"

    triggered = client.post(f"/api/jobs/{job['job_id']}/trigger")
    assert triggered.status_code == 202
    assert triggered.json()["task_id"] == "task-api-1"
    assert runtime.calls[0]["target_model"] == "qwen3.8:27b"

    history = client.get(f"/api/jobs/{job['job_id']}/runs")
    assert history.status_code == 200
    assert history.json()[0]["status"] == "succeeded"
    assert history.json()[0]["output"] == "api output"

    deleted = client.delete(f"/api/jobs/{job['job_id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/jobs/{job['job_id']}").status_code == 404


def test_job_api_rejects_invalid_cron(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "name": "bad cron",
            "prompt": "Never run",
            "schedule": {"kind": "cron", "cron": "not cron"},
        },
    )

    assert response.status_code == 422
    assert runtime.calls == []


def test_job_health_reports_failure_rate_and_stale_or_delivery_risks(
    client: TestClient,
    runtime: FakeRuntime,
) -> None:
    run_at = datetime(2026, 8, 28, 9, 0, tzinfo=UTC).isoformat()
    created = client.post(
        "/api/jobs",
        json={"name": "health", "prompt": "check", "schedule": {"kind": "once", "run_at": run_at}},
    ).json()
    client.post(f"/api/jobs/{created['job_id']}/trigger")
    client.get(f"/api/jobs/{created['job_id']}/runs")
    runtime.status = "failed"
    client.post(f"/api/jobs/{created['job_id']}/trigger")
    client.get(f"/api/jobs/{created['job_id']}/runs")

    response = client.get("/api/jobs/health", params={"maximum_failure_rate": 0.25})

    assert response.status_code == 200
    health = response.json()
    assert health["completed_runs"] == 2
    assert health["succeeded_runs"] == 1
    assert health["failed_runs"] == 1
    assert health["success_rate"] == 0.5
    assert health["healthy"] is False
    assert "failure rate exceeds policy" in health["reasons"]


def test_failed_job_run_retry_is_idempotent(client: TestClient, runtime: FakeRuntime) -> None:
    runtime.status = "failed"
    run_at = datetime(2026, 8, 28, 9, 0, tzinfo=UTC).isoformat()
    created = client.post(
        "/api/jobs",
        json={"name": "retry", "prompt": "recover", "schedule": {"kind": "once", "run_at": run_at}},
    ).json()
    client.post(f"/api/jobs/{created['job_id']}/trigger")
    source = client.get(f"/api/jobs/{created['job_id']}/runs").json()[0]
    runtime.status = "done"

    first = client.post(f"/api/jobs/{created['job_id']}/runs/{source['run_id']}/retry")
    second = client.post(f"/api/jobs/{created['job_id']}/runs/{source['run_id']}/retry")

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["source_run_id"] == source["run_id"]
    assert second.json()["run"]["run_id"] == first.json()["run"]["run_id"]
    assert len(runtime.calls) == 2
