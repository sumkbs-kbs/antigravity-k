"""CTX-01 conversation API: append/compact/fork + conflict payload."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from antigravity_k.api.routes import conversation_api
from antigravity_k.engine.conversation_store import reset_conversation_store_for_tests
from antigravity_k.engine.project_registry import ProjectRegistry


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Point store at tmp
    from antigravity_k.engine import conversation_store as cs

    fresh = cs.ConversationStore(storage_dir=tmp_path / "conversations")
    reset_conversation_store_for_tests(fresh)

    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    root = tmp_path / "proj"
    root.mkdir()
    record = registry.add_project(name="CTX", path=str(root))
    monkeypatch.setattr(
        "antigravity_k.api.project_binding.get_project_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "antigravity_k.engine.request_execution_context.get_project_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "antigravity_k.config.config.paths.project_root",
        tmp_path.resolve(),
    )
    monkeypatch.delenv("AGK_ALLOWED_ROOTS", raising=False)
    monkeypatch.setenv("AGK_ALLOWED_ROOTS", str(tmp_path.resolve()))

    app = FastAPI()
    from antigravity_k.api.error_handler import APIError, global_exception_handler

    app.add_exception_handler(APIError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(conversation_api.router)
    test = TestClient(app, raise_server_exceptions=False)
    test.project_id = record.id  # type: ignore[attr-defined]
    return test


def test_append_compact_fork_flow(client: TestClient) -> None:
    pid = client.project_id  # type: ignore[attr-defined]
    r = client.post(
        "/v1/conversations/append",
        json={
            "project_id": pid,
            "conversation_id": "conv_api",
            "expected_revision": 0,
            "role": "user",
            "content": "hello from tab A " + ("x" * 100),
        },
    )
    assert r.status_code == 200, r.text
    snap = r.json()
    assert snap["revision"] == 1

    r2 = client.post(
        "/v1/conversations/append",
        json={
            "project_id": pid,
            "conversation_id": "conv_api",
            "expected_revision": 1,
            "role": "assistant",
            "content": "reply " + ("y" * 100),
        },
    )
    assert r2.status_code == 200
    assert r2.json()["revision"] == 2

    # stale append → 409
    conflict = client.post(
        "/v1/conversations/append",
        json={
            "project_id": pid,
            "conversation_id": "conv_api",
            "expected_revision": 1,
            "role": "user",
            "content": "should conflict",
        },
    )
    assert conflict.status_code == 409
    body = conflict.json()
    assert body["error"] == "stale_conversation_revision"
    assert body["current_revision"] == 2

    # more messages then compact
    rev = 2
    for i in range(6):
        rr = client.post(
            "/v1/conversations/append",
            json={
                "project_id": pid,
                "conversation_id": "conv_api",
                "expected_revision": rev,
                "role": "user",
                "content": f"bulk-{i} " + ("z" * 80),
            },
        )
        assert rr.status_code == 200
        rev = rr.json()["revision"]

    compact = client.post(
        "/v1/conversations/compact",
        json={
            "project_id": pid,
            "conversation_id": "conv_api",
            "expected_revision": rev,
            "retain_tail": 3,
        },
    )
    assert compact.status_code == 200, compact.text
    cbody = compact.json()
    assert cbody["revision"] == rev + 1
    assert cbody.get("summary")
    assert cbody.get("retained_message_ids")
    assert cbody["tokens_after"] <= cbody["tokens_before"]

    hist = client.get(f"/v1/conversations/conv_api?project_id={pid}")
    assert hist.status_code == 200
    h = hist.json()
    assert h["snapshot"]["revision"] == cbody["revision"]

    forked = client.post(
        "/v1/conversations/fork",
        json={
            "project_id": pid,
            "conversation_id": "conv_api",
            "expected_revision": cbody["revision"],
        },
    )
    assert forked.status_code == 200
    assert forked.json()["revision"] == 0
    assert forked.json()["conversation_id"] != "conv_api"
