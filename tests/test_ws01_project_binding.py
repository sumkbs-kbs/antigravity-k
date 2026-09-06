"""WS-01 · request-scoped project binding and DI integration tests."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.project_binding import (
    clear_runtime_captures,
    disable_runtime_capture,
    enable_runtime_capture,
    get_request_project_root,
    get_runtime_captures,
    get_session_project_bindings,
    reset_bound_request_execution_context,
    resolve_project_execution_context,
)
from antigravity_k.api.routes import filesystem
from antigravity_k.api.server import app
from antigravity_k.engine.project_registry import ProjectRegistry, get_project_registry


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from antigravity_k.config import config

    storage = tmp_path / "projects.json"
    monkeypatch.setattr(
        "antigravity_k.engine.project_registry._DEFAULT_STORAGE_PATH",
        storage,
    )
    # Reset global registry singleton for isolation
    import antigravity_k.engine.project_registry as preg

    monkeypatch.setattr(preg, "_global_registry", None)

    allow_root = tmp_path.resolve()
    monkeypatch.setattr(config.paths, "project_root", allow_root)
    monkeypatch.delenv("AGK_ALLOWED_ROOTS", raising=False)

    get_session_project_bindings().reset_all()
    clear_runtime_captures()
    disable_runtime_capture()
    reset_bound_request_execution_context()

    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client

    get_session_project_bindings().reset_all()
    clear_runtime_captures()
    disable_runtime_capture()
    reset_bound_request_execution_context()
    monkeypatch.setattr(preg, "_global_registry", None)


def _register_project(client: TestClient, name: str, path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    res = client.post("/api/projects", json={"name": name, "path": str(path)})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    return data["project"]


def test_resolve_requires_project_id_or_session_binding(client: TestClient) -> None:
    get_session_project_bindings().reset_all()
    res = client.post(
        "/api/execution-context/resolve",
        json={"model_id": "m1", "request_id": "req_missing"},
    )
    assert res.status_code == 400, res.text
    body = res.json()
    assert body.get("error") == "missing_execution_context"


def test_invalid_project_rejected_before_workspace_side_effect(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = filesystem.WORKSPACE_ROOT
    marker = tmp_path / "should-not-mutate"
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(marker))

    res = client.post(
        "/api/execution-context/resolve",
        json={
            "project_id": "proj_does_not_exist",
            "model_id": "m1",
            "request_id": "req_missing_proj",
            "conversation_id": "c1",
            "conversation_revision": 0,
            "actor_subject": "tester",
            "session_id": "sess_a",
        },
    )
    assert res.status_code == 404, res.text
    assert res.json().get("error") == "project_not_found"
    assert filesystem.WORKSPACE_ROOT == str(marker)
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", before)


def test_deleted_project_rejected(client: TestClient, tmp_path: Path) -> None:
    proj = _register_project(client, "Doomed", tmp_path / "doomed")
    # Ensure another project remains so delete is allowed
    _ = _register_project(client, "Survivor", tmp_path / "survivor")
    del_res = client.delete(f"/api/projects/{proj['id']}")
    assert del_res.status_code == 200, del_res.text

    res = client.post(
        "/api/execution-context/resolve",
        json={
            "project_id": proj["id"],
            "model_id": "m1",
            "request_id": "req_deleted",
            "conversation_id": "c1",
            "conversation_revision": 0,
            "actor_subject": "tester",
            "session_id": "sess_a",
        },
    )
    assert res.status_code == 404, res.text
    assert res.json().get("error") == "project_not_found"


def test_route_to_runtime_capture_preserves_project_id(client: TestClient, tmp_path: Path) -> None:
    enable_runtime_capture()
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")
    res = client.post(
        "/api/execution-context/resolve",
        json={
            "project_id": alpha["id"],
            "model_id": "qwen-test",
            "request_id": "req_capture_1",
            "conversation_id": "conv_1",
            "conversation_revision": 0,
            "actor_subject": "tester",
            "session_id": "sess_capture",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["ok"] is True
    assert payload["execution_context"]["project_id"] == alpha["id"]
    assert Path(payload["execution_context"]["canonical_project_root"]) == (tmp_path / "alpha").resolve()
    assert payload["bound_project_root"] == payload["execution_context"]["canonical_project_root"]

    captures = get_runtime_captures()
    assert len(captures) == 1
    assert captures[0].project_id == alpha["id"]
    assert Path(captures[0].canonical_project_root) == (tmp_path / "alpha").resolve()


def test_concurrent_a_b_requests_do_not_share_roots(client: TestClient, tmp_path: Path) -> None:
    enable_runtime_capture()
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")
    beta = _register_project(client, "Beta", tmp_path / "beta")
    registry = get_project_registry()

    results: dict[str, object] = {}
    errors: list[BaseException] = []

    def _resolve_direct(project_id: str, request_id: str, key: str) -> None:
        try:
            ctx = resolve_project_execution_context(
                payload={
                    "project_id": project_id,
                    "model_id": "m",
                    "request_id": request_id,
                    "conversation_id": f"c_{request_id}",
                    "conversation_revision": 0,
                    "actor_subject": "tester",
                    "session_id": f"sess_{request_id}",
                },
                registry=registry,
                bind=True,
            )
            results[key] = ctx
        except BaseException as exc:  # noqa: BLE001 — surface in main thread
            errors.append(exc)

    threads = [
        threading.Thread(target=_resolve_direct, args=(alpha["id"], "req_a", "a")),
        threading.Thread(target=_resolve_direct, args=(beta["id"], "req_b", "b")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    ctx_a = results["a"]
    ctx_b = results["b"]
    assert ctx_a.project_id == alpha["id"]  # type: ignore[union-attr]
    assert ctx_b.project_id == beta["id"]  # type: ignore[union-attr]
    assert ctx_a.canonical_project_root != ctx_b.canonical_project_root  # type: ignore[union-attr]
    assert Path(ctx_a.canonical_project_root) == (tmp_path / "alpha").resolve()  # type: ignore[union-attr]
    assert Path(ctx_b.canonical_project_root) == (tmp_path / "beta").resolve()  # type: ignore[union-attr]

    # Route-level sequential resolve also preserves distinct roots
    res_a = client.post(
        "/api/execution-context/resolve",
        json={
            "project_id": alpha["id"],
            "model_id": "m",
            "request_id": "req_route_a",
            "conversation_id": "c_ra",
            "conversation_revision": 0,
            "actor_subject": "tester",
            "session_id": "sess_ra",
        },
    )
    res_b = client.post(
        "/api/execution-context/resolve",
        json={
            "project_id": beta["id"],
            "model_id": "m",
            "request_id": "req_route_b",
            "conversation_id": "c_rb",
            "conversation_revision": 0,
            "actor_subject": "tester",
            "session_id": "sess_rb",
        },
    )
    assert res_a.status_code == 200 and res_b.status_code == 200
    assert (
        res_a.json()["execution_context"]["canonical_project_root"]
        != res_b.json()["execution_context"]["canonical_project_root"]
    )

    captures = get_runtime_captures()
    project_ids = {c.project_id for c in captures}
    roots = {c.canonical_project_root for c in captures}
    assert alpha["id"] in project_ids and beta["id"] in project_ids
    assert len(roots) >= 2


def test_active_project_switch_does_not_change_inflight_root(client: TestClient, tmp_path: Path) -> None:
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")
    beta = _register_project(client, "Beta", tmp_path / "beta")

    # Capture in-flight context for alpha
    inflight = resolve_project_execution_context(
        payload={
            "project_id": alpha["id"],
            "model_id": "m",
            "request_id": "req_inflight",
            "conversation_id": "c_inf",
            "conversation_revision": 0,
            "actor_subject": "tester",
            "session_id": "sess_inf",
        },
        bind=True,
    )
    assert get_request_project_root() == inflight.canonical_project_root
    frozen_root = inflight.canonical_project_root

    # Switch active project to beta (browse + session binding)
    switch = client.post("/api/projects/switch", json={"project_id": beta["id"]})
    assert switch.status_code == 200, switch.text
    binding = switch.json()["session_active_project"]
    assert binding["project_id"] == beta["id"]
    assert binding["revision"] >= 1

    # In-flight bound context must remain alpha
    assert get_request_project_root() == frozen_root
    assert inflight.project_id == alpha["id"]
    assert Path(inflight.canonical_project_root) == (tmp_path / "alpha").resolve()


def test_session_binding_allows_resolve_without_project_id(client: TestClient, tmp_path: Path) -> None:
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")
    switch = client.post(
        "/api/projects/switch",
        json={"project_id": alpha["id"]},
        headers={"X-AGK-Session-Id": "sess_explicit"},
    )
    assert switch.status_code == 200, switch.text
    assert switch.json()["session_active_project"]["project_id"] == alpha["id"]

    res = client.post(
        "/api/execution-context/resolve",
        headers={"X-AGK-Session-Id": "sess_explicit"},
        json={
            "model_id": "m",
            "request_id": "req_session_bind",
            "conversation_id": "c1",
            "conversation_revision": 0,
            "actor_subject": "tester",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["execution_context"]["project_id"] == alpha["id"]


def test_task_submit_stores_immutable_project_context(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")

    captured: dict[str, object] = {}

    class _FakeRuntime:
        def submit_task(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            return "task_ws01_1"

        def get_task_status(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(
        "antigravity_k.api.routes.task_api._runtime",
        lambda: _FakeRuntime(),
    )

    res = client.post(
        "/api/tasks/submit",
        json={
            "prompt": "do something safe",
            "model": "m1",
            "context": {"project_id": alpha["id"]},
        },
    )
    assert res.status_code == 202, res.text
    assert res.json()["task_id"] == "task_ws01_1"
    ctx = captured.get("context")
    assert isinstance(ctx, dict)
    assert ctx.get("project_id") == alpha["id"]
    assert Path(str(ctx.get("canonical_project_root"))) == (tmp_path / "alpha").resolve()
    assert "execution_context" in ctx


def test_chat_rejects_missing_project_before_side_effects(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    get_session_project_bindings().reset_all()
    started = {"count": 0}

    class _FakeSessionManager:
        def start_session(self, resume: bool = False):  # type: ignore[no-untyped-def]
            started["count"] += 1
            return "sess"

        def auto_restore(self):  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(
        "antigravity_k.api.dependencies._get_session_manager",
        lambda: _FakeSessionManager(),
    )
    monkeypatch.setattr(
        "antigravity_k.api.dependencies.get_session_manager",
        lambda: _FakeSessionManager(),
    )

    res = client.post(
        "/v1/chat/completions",
        json={
            "model": "dummy",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "agent_mode": False,
        },
    )
    assert res.status_code == 400, res.text
    assert res.json().get("error") == "missing_execution_context"
    assert started["count"] == 0


def test_di_get_memory_manager_uses_request_root(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from antigravity_k.api import dependencies as deps

    alpha_dir = tmp_path / "alpha"
    alpha_dir.mkdir()
    registry = ProjectRegistry(storage_path=tmp_path / "reg.json")
    record = registry.add_project(name="Alpha", path=str(alpha_dir))
    monkeypatch.setattr(
        "antigravity_k.engine.project_registry._global_registry",
        registry,
    )
    monkeypatch.setattr(deps, "_memory_manager", None)

    ctx = resolve_project_execution_context(
        payload={
            "project_id": record.id,
            "model_id": "m",
            "request_id": "req_mem",
            "conversation_id": "c",
            "conversation_revision": 0,
            "actor_subject": "t",
            "session_id": "s",
        },
        registry=registry,
        bind=True,
    )
    mm = deps.get_memory_manager()
    assert Path(mm.project_root).resolve() == Path(ctx.canonical_project_root).resolve()
