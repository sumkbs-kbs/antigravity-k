import json
import typing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from antigravity_k.api.routes import task_api


class FakeTaskRuntime:
    def __init__(self) -> None:
        self.submit_calls: list[dict[str, object]] = []
        self.event_calls: list[tuple[str, int, int]] = []

    def submit_task(self, **kwargs: object) -> str:
        self.submit_calls.append(kwargs)
        return "task-123"

    def get_task_status(self, task_id: str) -> dict[str, object] | None:
        if task_id == "missing":
            return None
        return {"task_id": task_id, "status": "done"}

    def list_task_events(self, task_id: str, after_sequence: int, limit: int) -> list[dict[str, object]]:
        self.event_calls.append((task_id, after_sequence, limit))
        if after_sequence >= 7:
            return []
        return [
            {
                "sequence": 7,
                "schema_version": 2,
                "task_id": task_id,
                "step_id": "step-1",
                "agent_id": "agent-root",
                "parent_id": None,
                "tool_call_id": None,
                "approval_id": None,
                "resource_job_id": None,
                "correlation_id": "request-1",
                "event_type": "task.completed",
                "payload_json": '{"result":"ok"}',
                "created_at": "2026-08-20T00:00:00+00:00",
            },
        ]


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> FakeTaskRuntime:
    fake = FakeTaskRuntime()
    monkeypatch.setattr(task_api, "get_agent_runtime", lambda: fake)
    return fake


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(task_api.router)
    return TestClient(app)


def test_submit_task_uses_typed_canonical_runtime_contract(client: TestClient, runtime: FakeTaskRuntime) -> None:
    response = client.post(
        "/api/tasks/submit",
        json={
            "prompt": "  inspect the repository  ",
            "context": {"expected_tools": ["read_file"]},
            "model": "qwen-local",
            "use_worktree": True,
            "idempotency_key": "request-1",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "submitted", "task_id": "task-123"}
    assert runtime.submit_calls == [
        {
            "prompt": "inspect the repository",
            "context": {"expected_tools": ["read_file"]},
            "target_model": "qwen-local",
            "use_worktree": True,
            "idempotency_key": "request-1",
        },
    ]


def test_submit_task_rejects_blank_prompt(client: TestClient, runtime: FakeTaskRuntime) -> None:
    response = client.post("/api/tasks/submit", json={"prompt": "   "})

    assert response.status_code == 422
    assert runtime.submit_calls == []


def test_task_event_replay_is_task_scoped_and_decodes_payload(client: TestClient, runtime: FakeTaskRuntime) -> None:
    response = client.get("/api/tasks/task-123/events?after_sequence=3&limit=25")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "events": [
            {
                "sequence": 7,
                "schema_version": 2,
                "task_id": "task-123",
                "step_id": "step-1",
                "agent_id": "agent-root",
                "parent_id": None,
                "tool_call_id": None,
                "approval_id": None,
                "resource_job_id": None,
                "correlation_id": "request-1",
                "event_type": "task.completed",
                "payload": {"result": "ok"},
                "created_at": "2026-08-20T00:00:00+00:00",
            },
        ],
        "last_sequence": 7,
    }
    assert runtime.event_calls == [("task-123", 3, 25)]


def test_task_event_replay_rejects_unknown_task(client: TestClient, runtime: FakeTaskRuntime) -> None:
    response = client.get("/api/tasks/missing/events")

    assert response.status_code == 404
    assert runtime.event_calls == []


def test_task_event_sse_replays_then_ends_for_terminal_task(
    client: TestClient,
    runtime: FakeTaskRuntime,
) -> None:
    response = client.get("/api/tasks/task-123/events/stream?after_sequence=0")

    assert response.status_code == 200
    frames = [frame for frame in response.text.strip().split("\n\n") if frame]
    assert frames[0].startswith("id: 7\nevent: task.completed\ndata: ")
    event = typing.cast(dict[str, object], json.loads(frames[0].split("data: ", 1)[1]))
    assert runtime.event_calls == [("task-123", 0, 200)]
    assert event["task_id"] == "task-123"
    assert event["payload"] == {"result": "ok"}
    assert frames[1].startswith("event: stream.end\ndata: ")
    end = typing.cast(dict[str, object], json.loads(frames[1].split("data: ", 1)[1]))
    assert end == {"task_id": "task-123", "last_sequence": 7, "status": "done"}


def test_task_event_sse_resumes_from_last_event_id_header(
    client: TestClient,
    runtime: FakeTaskRuntime,
) -> None:
    response = client.get(
        "/api/tasks/task-123/events/stream?after_sequence=3",
        headers={"Last-Event-ID": "7"},
    )

    assert response.status_code == 200
    assert response.text.startswith("event: stream.end\ndata: ")
    assert runtime.event_calls == [("task-123", 7, 200)]


def test_task_event_websocket_replays_task_scoped_events_and_ends(
    client: TestClient,
    runtime: FakeTaskRuntime,
) -> None:
    with client.websocket_connect("/api/tasks/task-123/events/ws?after_sequence=3") as websocket:
        replay = typing.cast(dict[str, object], websocket.receive_json())
        stream_end = typing.cast(dict[str, object], websocket.receive_json())

    assert replay == {
        "sequence": 7,
        "schema_version": 2,
        "task_id": "task-123",
        "step_id": "step-1",
        "agent_id": "agent-root",
        "parent_id": None,
        "tool_call_id": None,
        "approval_id": None,
        "resource_job_id": None,
        "correlation_id": "request-1",
        "event_type": "task.completed",
        "payload": {"result": "ok"},
        "created_at": "2026-08-20T00:00:00+00:00",
    }
    assert stream_end == {
        "type": "stream.end",
        "task_id": "task-123",
        "last_sequence": 7,
        "status": "done",
    }
    assert runtime.event_calls == [("task-123", 3, 200)]


def test_task_event_websocket_rejects_unknown_task_before_replay(
    client: TestClient,
    runtime: FakeTaskRuntime,
) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/tasks/missing/events/ws"):
            pass

    assert runtime.event_calls == []
