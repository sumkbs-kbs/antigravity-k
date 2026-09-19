from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from fastapi.testclient import TestClient
from pydantic import JsonValue, TypeAdapter

from antigravity_k.api.server import app
from antigravity_k.engine.artifact_provenance import create_manifest, manifest_digest
from antigravity_k.engine.task_runner import BackgroundTaskRunner, TaskStatus


def test_task_provenance_api_records_manifest_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    from antigravity_k.api.routes import artifact_api

    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    _ = runner.state_store.create_task(
        "task-provenance",
        "record artifact",
        TaskStatus.RUNNING,
        "2026-09-01T00:00:00+00:00",
    )

    class Runtime:
        task_runner: Final[BackgroundTaskRunner] = runner

        def get_task_status(self, task_id: str, owner_subject: str | None = None) -> dict[str, object] | None:
            return runner.get_status(task_id, owner_subject=owner_subject)

    monkeypatch.setattr(artifact_api, "get_agent_runtime", lambda: Runtime())

    # When
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks/task-provenance/provenance",
            json={"paths": ["README.md"], "source": "build"},
        )

    # Then
    assert response.status_code == 201
    payload = TypeAdapter(dict[str, JsonValue]).validate_python(response.json())
    assert payload["status"] == "recorded"
    assert payload["source"] == "build"
    digest = payload["digest"]
    assert isinstance(digest, str)
    assert len(digest) == 64
    events = runner.state_store.list_execution_events("task-provenance")
    assert events[0]["event_type"] == "artifact.provenance.recorded"


def test_task_provenance_manifest_api_records_ci_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    from antigravity_k.api.routes import artifact_api

    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    _ = runner.state_store.create_task(
        "task-ci-provenance",
        "record CI artifact",
        TaskStatus.RUNNING,
        "2026-09-01T00:00:00+00:00",
    )
    manifest = create_manifest(Path.cwd(), (Path("README.md"),))

    class Runtime:
        task_runner: Final[BackgroundTaskRunner] = runner

        def get_task_status(self, task_id: str, owner_subject: str | None = None) -> dict[str, object] | None:
            return runner.get_status(task_id, owner_subject=owner_subject)

    monkeypatch.setattr(artifact_api, "get_agent_runtime", lambda: Runtime())

    # When
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks/task-ci-provenance/provenance/manifest",
            json={"manifest": manifest.model_dump(mode="json"), "source": "ui_bundle"},
        )

    # Then
    assert response.status_code == 201
    payload = TypeAdapter(dict[str, JsonValue]).validate_python(response.json())
    assert payload["digest"] == manifest_digest(manifest)
    events = runner.state_store.list_execution_events("task-ci-provenance")
    assert events[0]["event_type"] == "artifact.provenance.recorded"
    assert '"source": "ui_bundle"' in events[0]["payload_json"]


def test_provenance_task_registration_is_idempotent_and_publishable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    from antigravity_k.api.routes import artifact_api

    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    class Runtime:
        task_runner: Final[BackgroundTaskRunner] = runner

        def get_task_status(self, task_id: str, owner_subject: str | None = None) -> dict[str, object] | None:
            return runner.get_status(task_id, owner_subject=owner_subject)

    monkeypatch.setattr(artifact_api, "get_agent_runtime", lambda: Runtime())
    manifest = create_manifest(Path.cwd(), (Path("README.md"),))

    # When
    with TestClient(app) as client:
        first = client.post(
            "/api/tasks/provenance/register",
            json={"source": "build", "idempotency_key": "ci-run-123"},
        )
        second = client.post(
            "/api/tasks/provenance/register",
            json={"source": "build", "idempotency_key": "ci-run-123"},
        )
        first_payload = TypeAdapter(dict[str, JsonValue]).validate_python(first.json())
        second_payload = TypeAdapter(dict[str, JsonValue]).validate_python(second.json())
        task_id = first_payload["task_id"]
        assert isinstance(task_id, str)
        published = client.post(
            f"/api/tasks/{task_id}/provenance/manifest",
            json={"manifest": manifest.model_dump(mode="json"), "source": "build"},
        )

    # Then
    assert first.status_code == 201
    assert second.status_code == 201
    assert first_payload["task_id"] == second_payload["task_id"]
    assert published.status_code == 201
    events = runner.state_store.list_execution_events(task_id)
    assert [event["event_type"] for event in events] == [
        "artifact.provenance.task_registered",
        "artifact.provenance.recorded",
    ]
