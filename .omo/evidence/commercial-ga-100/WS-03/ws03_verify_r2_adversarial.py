"""Independent adversarial probes for WS-03 F1-F7 (ws_03_verify r2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_k.api.contracts.execution_context import RequestExecutionContext
from antigravity_k.api.dependencies import (
    acquire_project_runtime,
    get_agent_runtime,
    get_memory_manager,
    get_orchestrator,
    get_scheduled_job_service,
    get_session_manager,
    get_slash_registry,
    get_vault_engine,
    reset_runtime_dependencies,
)
from antigravity_k.api.project_binding import (
    reset_bound_request_execution_context,
    set_bound_request_execution_context,
)
from antigravity_k.engine.project_memory_paths import (
    project_rag_vector_dir,
    project_search_cache_dir,
    project_sessions_dir,
)
from antigravity_k.engine.project_registry import ProjectRegistry


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_dependencies()
    reset_bound_request_execution_context()
    yield
    reset_runtime_dependencies()
    reset_bound_request_execution_context()


@pytest.fixture
def projects(tmp_path, monkeypatch):
    storage = tmp_path / "projects.json"
    monkeypatch.setattr(
        "antigravity_k.engine.project_registry._DEFAULT_STORAGE_PATH",
        storage,
    )
    import antigravity_k.engine.project_registry as preg

    monkeypatch.setattr(preg, "_global_registry", None)
    from antigravity_k.config import config

    monkeypatch.setattr(config.paths, "project_root", tmp_path.resolve())
    monkeypatch.delenv("AGK_ALLOWED_ROOTS", raising=False)
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    registry = ProjectRegistry(storage_path=storage)
    monkeypatch.setattr(preg, "_global_registry", registry)
    rec_a = registry.add_project("A", str(project_a))
    rec_b = registry.add_project("B", str(project_b))
    return project_a, project_b, rec_a.id, rec_b.id


def _bind(project_id: str, root: Path, request_id: str = "req") -> None:
    reset_bound_request_execution_context()
    ctx = RequestExecutionContext(
        schema_version=1,
        request_id=request_id,
        task_id=None,
        project_id=project_id,
        canonical_project_root=str(root.resolve()),
        conversation_id="conv",
        conversation_revision=0,
        actor_subject="verify-r2",
        session_id=f"sess-{request_id}",
        model_id="m1",
        correlation_id="",
        project_name="n",
    )
    set_bound_request_execution_context(ctx)


def test_f1_session_di_project_scoped(projects):
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "s1")
    sm_a = get_session_manager()
    rt_a = acquire_project_runtime()
    assert sm_a is rt_a.session_manager
    base = Path(sm_a.base_dir)
    assert str(project_a.resolve()) in str(base.resolve())
    _bind(id_b, project_b, "s2")
    sm_b = get_session_manager()
    rt_b = acquire_project_runtime()
    assert sm_b is rt_b.session_manager
    assert sm_a is not sm_b


def test_f2_chat_session_no_secret_leak(projects):
    project_a, project_b, id_a, id_b = projects
    secret = "SECRET_FROM_PROJECT_A_ONLY_xyz_VERIFY_R2"
    _bind(id_a, project_a, "sess-a")
    sm_a = get_session_manager()
    sid_a = sm_a.start_session(project_path=str(project_a.resolve()), resume=False)
    sm_a.add_turn(role="user", content=secret)
    sm_a.add_turn(role="assistant", content="ack-a")
    sm_a.save()
    _bind(id_b, project_b, "sess-b")
    sm_b = get_session_manager()
    sid_b = sm_b.start_session(project_path=str(project_b.resolve()), resume=True)
    blob_b = " ".join(m.get("content", "") for m in sm_b.get_messages())
    assert secret not in blob_b
    assert sid_b != sid_a
    _bind(id_a, project_a, "sess-a2")
    sm_a2 = get_session_manager()
    sid_a2 = sm_a2.start_session(project_path=str(project_a.resolve()), resume=True)
    blob_a = " ".join(m.get("content", "") for m in sm_a2.get_messages())
    assert secret in blob_a
    assert sid_a2 == sid_a
    assert sm_a2 is sm_a


def test_f3_slash_registry_not_sticky(projects):
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "sl-a")
    reg_a = get_slash_registry()
    ar_a = get_agent_runtime()
    _bind(id_b, project_b, "sl-b")
    reg_b = get_slash_registry()
    ar_b = get_agent_runtime()
    assert reg_a is not reg_b
    assert getattr(reg_a, "_agent_runtime") is ar_a
    assert getattr(reg_b, "_agent_runtime") is ar_b
    assert ar_a is not ar_b


def test_f5_durable_clear_a_leaves_b(projects):
    from antigravity_k.engine.vector_store import VectorStore

    project_a, project_b, id_a, id_b = projects
    cache_a = project_search_cache_dir(project_a) / "a.json"
    cache_b = project_search_cache_dir(project_b) / "b.json"
    cache_a.write_text('{"cached_at":"2099-01-01T00:00:00+00:00","q":"a"}')
    cache_b.write_text('{"cached_at":"2099-01-01T00:00:00+00:00","q":"b"}')
    seeded = False
    try:
        vs_b = VectorStore(str(project_rag_vector_dir(project_b)), collection_name="project_code")
        vs_b.upsert_chunks([{"id": "b-chunk-1", "text": "PROJECT_B_VECTOR_MARKER", "metadata": {"source": "b.py"}}])
        vs_b.close()
        seeded = True
    except Exception:
        seeded = False
    _bind(id_a, project_a, "clr-a")
    _ = get_memory_manager().clear("all")
    assert cache_b.exists()
    assert "b" in cache_b.read_text()
    if seeded:
        vs_b2 = VectorStore(str(project_rag_vector_dir(project_b)), collection_name="project_code")
        try:
            blob = str(vs_b2.export_all())
        finally:
            vs_b2.close()
        assert "PROJECT_B_VECTOR_MARKER" in blob or "b-chunk-1" in blob


def test_f6_factory_wires_real_rag_and_project_vault(projects):
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "rag-a")
    rt_a = acquire_project_runtime()
    _bind(id_b, project_b, "rag-b")
    rt_b = acquire_project_runtime()
    rag_a = getattr(rt_a.orchestrator, "_rag_indexer", None)
    rag_b = getattr(rt_b.orchestrator, "_rag_indexer", None)
    assert rag_a is not None and rag_b is not None and rag_a is not rag_b
    vault_a = rt_a.orchestrator.vault_engine
    vault_b = rt_b.orchestrator.vault_engine
    assert vault_a is not None and vault_b is not None and vault_a is not vault_b
    va = Path(vault_a.vault_path)
    vb = Path(vault_b.vault_path)
    assert str(project_a.resolve()) in str(va.resolve())
    assert str(project_b.resolve()) in str(vb.resolve())
    assert rt_a.vault_engine is vault_a
    assert rt_b.vault_engine is vault_b
    assert get_vault_engine() is get_vault_engine()


def test_f7_scheduled_jobs_project_scoped(projects):
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "job-a")
    svc_a = get_scheduled_job_service()
    rt_a = acquire_project_runtime()
    _bind(id_b, project_b, "job-b")
    svc_b = get_scheduled_job_service()
    rt_b = acquire_project_runtime()
    assert svc_a is not svc_b
    assert svc_a is rt_a.scheduled_job_service
    assert svc_b is rt_b.scheduled_job_service
    assert svc_a.submit_agent == rt_a.agent_runtime.submit_task
    assert svc_b.submit_agent == rt_b.agent_runtime.submit_task


def test_extra_sessions_not_under_repo_cwd(projects, monkeypatch):
    project_a, project_b, id_a, id_b = projects
    repo = Path("/Users/mr.k/program/coding/ssak_comp/Ssak-Ai-ws-03").resolve()
    monkeypatch.chdir(repo)
    _bind(id_a, project_a, "cwd-a")
    sm = get_session_manager()
    base = Path(sm.base_dir).resolve()
    assert str(project_a.resolve()) in str(base)
    assert base == project_sessions_dir(project_a).resolve()
    assert base != (repo / ".antigravity" / "sessions").resolve()


def test_extra_clear_a_does_not_touch_repo_cwd_vault(projects, monkeypatch):
    project_a, project_b, id_a, id_b = projects
    repo = Path("/Users/mr.k/program/coding/ssak_comp/Ssak-Ai-ws-03").resolve()
    monkeypatch.chdir(repo)
    cwd_vault = repo / "vault_data"
    cwd_vault.mkdir(exist_ok=True)
    marker = cwd_vault / "VERIFY_R2_MARKER_DO_NOT_DELETE.txt"
    marker.write_text("keep-me", encoding="utf-8")
    try:
        _bind(id_a, project_a, "cwd-clr")
        _ = get_memory_manager().clear("all")
        assert marker.exists()
    finally:
        marker.unlink(missing_ok=True)


def test_extra_orchestrators_distinct(projects):
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "o-a")
    oa = get_orchestrator()
    _bind(id_b, project_b, "o-b")
    ob = get_orchestrator()
    assert oa is not ob
