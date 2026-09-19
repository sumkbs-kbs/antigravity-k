from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from antigravity_k.api.routes import gateway_api
from antigravity_k.engine.scheduled_job_service import ScheduledJobService
from antigravity_k.engine.scheduled_job_store import ScheduledJobStore


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def submit_task(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return "task-gateway-1"

    def get_task_status(self, task_id: str) -> dict[str, object]:
        return {"task_id": task_id, "status": "done", "output": "gateway response"}


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeRuntime:
    fake = FakeRuntime()
    service = ScheduledJobService(
        ScheduledJobStore(str(tmp_path / "jobs.db")),
        fake.submit_task,
        fake.get_task_status,
        delivery_sender=lambda *_: None,
    )
    monkeypatch.setattr(gateway_api, "get_scheduled_job_service", lambda: service)
    return fake


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(gateway_api.router)
    return TestClient(app)


def test_gateway_message_creates_traceable_jarvis_job(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post(
        "/api/gateway/messages",
        json={
            "channel": "telegram",
            "sender_id": "user-42",
            "text": "Summarize today's priorities",
            "model": "qwen3.8:27b",
            "context_mode": "continue",
            "reply_webhook": "https://example.com/replies/42",
            "idempotency_key": "telegram-update-100",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"].startswith("job_")
    assert body["run_id"].startswith("run_")
    assert body["task_id"] == "task-gateway-1"
    call = runtime.calls[0]
    assert call["prompt"] == "Summarize today's priorities"
    assert call["target_model"] == "qwen3.8:27b"
    context = cast(dict[str, object], call["context"])
    assert context["gateway"] == {
        "channel": "telegram",
        "sender_id": "user-42",
        "idempotency_key": "telegram-update-100",
    }


def test_gateway_rejects_blank_message(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post(
        "/api/gateway/messages",
        json={"channel": "slack", "sender_id": "u1", "text": "   "},
    )

    assert response.status_code == 422
    assert runtime.calls == []


def test_gateway_idempotency_reuses_original_run(client: TestClient, runtime: FakeRuntime) -> None:
    payload = {
        "channel": "telegram",
        "sender_id": "user-42",
        "text": "Handle this update once",
        "idempotency_key": "telegram-update-101",
    }

    first = client.post("/api/gateway/messages", json=payload)
    second = client.post("/api/gateway/messages", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json() == first.json()
    assert len(runtime.calls) == 1
