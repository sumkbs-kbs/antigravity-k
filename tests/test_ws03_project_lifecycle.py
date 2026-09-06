"""WS-03 · project-scoped runtime / memory / RAG / artifact / compressor lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from antigravity_k.api.contracts.execution_context import RequestExecutionContext
from antigravity_k.api.dependencies import (
    acquire_project_runtime,
    evict_project_runtime,
    get_memory_manager,
    get_orchestrator,
    get_scheduled_job_service,
    get_session_manager,
    get_slash_registry,
    reset_runtime_dependencies,
)
from antigravity_k.api.project_binding import (
    reset_bound_request_execution_context,
    set_bound_request_execution_context,
)
from antigravity_k.engine.project_memory import ProjectMemoryProvider
from antigravity_k.engine.project_registry import ProjectRegistry
from antigravity_k.engine.project_runtime import (
    ProjectRuntime,
    ProjectRuntimeRegistry,
    build_project_memory_manager,
)
from antigravity_k.engine.session_manager import SessionManager


@pytest.fixture(autouse=True)
def _reset_runtimes() -> Iterator[None]:
    reset_runtime_dependencies()
    reset_bound_request_execution_context()
    yield
    reset_runtime_dependencies()
    reset_bound_request_execution_context()


@pytest.fixture
def projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str, str]:
    storage = tmp_path / "projects.json"
    monkeypatch.setattr(
        "antigravity_k.engine.project_registry._DEFAULT_STORAGE_PATH",
        storage,
    )
    import antigravity_k.engine.project_registry as preg

    monkeypatch.setattr(preg, "_global_registry", None)

    from antigravity_k.config import config

    allow_root = tmp_path.resolve()
    monkeypatch.setattr(config.paths, "project_root", allow_root)
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
        actor_subject="test",
        session_id="sess",
        model_id="m1",
        correlation_id="",
        project_name="n",
    )
    set_bound_request_execution_context(ctx)


def test_orchestrator_cache_keyed_by_project_id(projects: tuple[Path, Path, str, str]) -> None:
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "r1")
    orch_a1 = get_orchestrator()
    _bind(id_b, project_b, "r2")
    orch_b = get_orchestrator()
    _bind(id_a, project_a, "r3")
    orch_a2 = get_orchestrator()

    assert orch_a1 is orch_a2
    assert orch_a1 is not orch_b
    assert orch_a1.project_id == id_a
    assert orch_b.project_id == id_b
    assert Path(orch_a1.project_root).resolve() == project_a.resolve()
    assert Path(orch_b.project_root).resolve() == project_b.resolve()


def test_memory_persistence_isolated_across_aba_switch(
    projects: tuple[Path, Path, str, str],
) -> None:
    project_a, project_b, id_a, id_b = projects

    _bind(id_a, project_a)
    mm_a = get_memory_manager()
    provider_a = next(p for p in mm_a.providers if isinstance(p, ProjectMemoryProvider))
    provider_a.sync_turn(
        "이 프로젝트에서는 데이터베이스로 SQLite를 사용하기로 했어",
        "알겠습니다",
    )

    _bind(id_b, project_b)
    mm_b = get_memory_manager()
    assert mm_a is not mm_b
    provider_b = next(p for p in mm_b.providers if isinstance(p, ProjectMemoryProvider))
    provider_b.sync_turn(
        "이 프로젝트에서는 데이터베이스로 PostgreSQL을 사용하기로 했어",
        "알겠습니다",
    )

    recalled_a = provider_a.prefetch("데이터베이스 설정을 적용해줘")
    recalled_b = provider_b.prefetch("데이터베이스 설정을 적용해줘")
    assert "sqlite" in recalled_a
    assert "postgresql" not in recalled_a
    assert "postgresql" in recalled_b
    assert "sqlite" not in recalled_b

    # A → B → A: same A manager instance, still no B facts.
    _bind(id_a, project_a)
    mm_a2 = get_memory_manager()
    assert mm_a2 is mm_a
    provider_a2 = next(p for p in mm_a2.providers if isinstance(p, ProjectMemoryProvider))
    recalled = provider_a2.prefetch("데이터베이스 설정을 적용해줘")
    assert "postgresql" not in recalled
    assert "sqlite" in recalled


def test_compressor_cache_is_project_keyed(projects: tuple[Path, Path, str, str]) -> None:
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a)
    orch_a = get_orchestrator()
    comp_a = orch_a.context_compressor_for("model-x")
    _bind(id_b, project_b)
    orch_b = get_orchestrator()
    comp_b = orch_b.context_compressor_for("model-x")

    assert comp_a is not None and comp_b is not None
    assert comp_a is not comp_b
    assert getattr(comp_a, "persistence_dir") != getattr(comp_b, "persistence_dir")
    assert str(project_a) in str(getattr(comp_a, "persistence_dir"))
    assert str(project_b) in str(getattr(comp_b, "persistence_dir"))

    # Same project + model returns cached compressor (not rebuilt).
    _bind(id_a, project_a)
    assert get_orchestrator().context_compressor_for("model-x") is comp_a


def test_artifact_engine_rooted_per_project(projects: tuple[Path, Path, str, str]) -> None:
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a)
    art_a = get_orchestrator().artifact_engine
    _bind(id_b, project_b)
    art_b = get_orchestrator().artifact_engine
    assert art_a is not None and art_b is not None
    assert art_a is not art_b
    assert Path(art_a.project_root).resolve() == project_a.resolve()
    assert Path(art_b.project_root).resolve() == project_b.resolve()


def test_rag_indexer_attached_per_orchestrator(projects: tuple[Path, Path, str, str]) -> None:
    """Factory must wire a real per-project RAGIndexer (not None / not shared)."""
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a)
    orch_a = get_orchestrator()
    _bind(id_b, project_b)
    orch_b = get_orchestrator()

    rag_a = getattr(orch_a, "_rag_indexer", None)
    rag_b = getattr(orch_b, "_rag_indexer", None)
    assert rag_a is not None and rag_b is not None
    assert rag_a is not rag_b
    assert os.path.abspath(rag_a.project_root) == os.path.abspath(str(project_a))
    assert os.path.abspath(rag_b.project_root) == os.path.abspath(str(project_b))
    # Vault engines must also be distinct per project (no shared process vault).
    assert orch_a.vault_engine is not None and orch_b.vault_engine is not None
    assert orch_a.vault_engine is not orch_b.vault_engine
    assert str(project_a.resolve()) in str(orch_a.vault_engine.vault_path)
    assert str(project_b.resolve()) in str(orch_b.vault_engine.vault_path)


def test_eviction_keeps_other_projects_and_cleans_watchdog(
    projects: tuple[Path, Path, str, str],
) -> None:
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a)
    orch_a = get_orchestrator()
    watchdog = MagicMock()
    orch_a.watchdog = watchdog
    mock_store = MagicMock()
    rag = MagicMock()
    rag.vector_store = mock_store
    orch_a._rag_indexer = rag
    orch_a._context_compressor_by_model["m"] = object()

    _bind(id_b, project_b)
    orch_b = get_orchestrator()
    assert orch_b is not orch_a

    assert evict_project_runtime(id_a) is True
    watchdog.stop.assert_called_once()
    mock_store.close.assert_called_once()

    # B still alive.
    _bind(id_b, project_b)
    assert get_orchestrator() is orch_b

    # A recreated fresh after eviction (restart semantics).
    _bind(id_a, project_a)
    orch_a2 = get_orchestrator()
    assert orch_a2 is not orch_a
    assert orch_a2.project_id == id_a


def test_init_failure_does_not_damage_other_runtime(
    projects: tuple[Path, Path, str, str],
) -> None:
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a)
    orch_a = get_orchestrator()

    registry = ProjectRuntimeRegistry(max_entries=8)

    def boom(pid: str, root: str) -> ProjectRuntime:
        raise RuntimeError("init exploded")

    with pytest.raises(RuntimeError, match="init exploded"):
        registry.get_or_create(id_b, str(project_b), factory=boom)

    assert registry.get(id_b) is None
    # Pre-existing A (process registry) untouched.
    _bind(id_a, project_a)
    assert get_orchestrator() is orch_a


def test_lru_eviction_shutdowns_victim(tmp_path: Path) -> None:
    registry = ProjectRuntimeRegistry(max_entries=2)
    created: list[str] = []
    shut: list[str] = []

    def factory(pid: str, root: str) -> ProjectRuntime:
        created.append(pid)
        session = SessionManager()
        mm = build_project_memory_manager(root, session)
        orch = MagicMock()
        orch.project_id = pid
        orch.project_root = root

        def _shutdown() -> None:
            shut.append(pid)

        orch.shutdown = _shutdown
        return ProjectRuntime(
            project_id=pid,
            project_root=root,
            memory_manager=mm,
            session_manager=session,
            orchestrator=orch,
        )

    roots = []
    for name in ("p1", "p2", "p3"):
        root = tmp_path / name
        root.mkdir()
        roots.append(root)
        registry.get_or_create(name, str(root), factory=factory)

    assert set(registry.active_project_ids()) == {"p2", "p3"}
    assert "p1" in shut
    assert registry.get("p1") is None


def test_restart_reload_preserves_disk_isolation(
    projects: tuple[Path, Path, str, str],
) -> None:
    """Evict + recreate (restart) still loads only that project's on-disk memory."""
    project_a, project_b, id_a, id_b = projects

    _bind(id_a, project_a)
    mm_a = get_memory_manager()
    next(p for p in mm_a.providers if isinstance(p, ProjectMemoryProvider)).sync_turn(
        "이 프로젝트에서는 백엔드로 FastAPI를 사용하기로 했어",
        "알겠습니다",
    )
    _bind(id_b, project_b)
    next(p for p in get_memory_manager().providers if isinstance(p, ProjectMemoryProvider)).sync_turn(
        "이 프로젝트에서는 백엔드로 Django를 사용하기로 했어",
        "알겠습니다",
    )

    assert evict_project_runtime(id_a)
    assert evict_project_runtime(id_b)

    _bind(id_a, project_a)
    recalled_a = next(p for p in get_memory_manager().providers if isinstance(p, ProjectMemoryProvider)).prefetch(
        "백엔드 구현"
    )
    _bind(id_b, project_b)
    recalled_b = next(p for p in get_memory_manager().providers if isinstance(p, ProjectMemoryProvider)).prefetch(
        "백엔드 구현"
    )

    assert "django" not in recalled_a
    assert "fastapi" not in recalled_b
    assert "fastapi" in recalled_a
    assert "django" in recalled_b


def test_acquire_by_explicit_project_id(projects: tuple[Path, Path, str, str]) -> None:
    _project_a, _project_b, id_a, id_b = projects
    reset_bound_request_execution_context()
    rt_a = acquire_project_runtime(project_id=id_a)
    rt_b = acquire_project_runtime(project_id=id_b)
    assert rt_a.project_id == id_a
    assert rt_b.project_id == id_b
    assert rt_a.orchestrator is not rt_b.orchestrator
    assert rt_a.memory_manager is not rt_b.memory_manager


def test_session_manager_di_is_project_scoped(projects: tuple[Path, Path, str, str]) -> None:
    """F1/F1c: get_session_manager() must return ProjectRuntime.session_manager."""
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "s1")
    sm_a = get_session_manager()
    rt_a = acquire_project_runtime()
    assert sm_a is rt_a.session_manager

    _bind(id_b, project_b, "s2")
    sm_b = get_session_manager()
    rt_b = acquire_project_runtime()
    assert sm_b is rt_b.session_manager
    assert sm_a is not sm_b


def test_chat_session_resume_does_not_leak_secret_across_projects(
    projects: tuple[Path, Path, str, str],
) -> None:
    """F2: A→B resume must not surface A's session secret."""
    project_a, project_b, id_a, id_b = projects
    secret = "SECRET_FROM_PROJECT_A_ONLY_xyz"

    _bind(id_a, project_a, "sess-a")
    sm_a = get_session_manager()
    sid_a = sm_a.start_session(project_path=str(project_a.resolve()), resume=False)
    sm_a.add_turn(role="user", content=secret)
    sm_a.add_turn(role="assistant", content="ack-a")
    sm_a.save()

    _bind(id_b, project_b, "sess-b")
    sm_b = get_session_manager()
    sid_b = sm_b.start_session(project_path=str(project_b.resolve()), resume=True)
    msgs_b = sm_b.get_messages()
    blob_b = " ".join(m.get("content", "") for m in msgs_b)
    assert secret not in blob_b
    assert sid_b != sid_a

    _bind(id_a, project_a, "sess-a2")
    sm_a2 = get_session_manager()
    sid_a2 = sm_a2.start_session(project_path=str(project_a.resolve()), resume=True)
    msgs_a = sm_a2.get_messages()
    blob_a = " ".join(m.get("content", "") for m in msgs_a)
    assert secret in blob_a
    assert sid_a2 == sid_a
    assert sm_a2 is sm_a


def test_slash_registry_rebinds_agent_runtime_per_project(
    projects: tuple[Path, Path, str, str],
) -> None:
    """F3: get_slash_registry must not freeze the first project's agent_runtime."""
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "sl-a")
    reg_a = get_slash_registry()
    runtime_a = acquire_project_runtime().agent_runtime
    assert getattr(reg_a, "_agent_runtime") is runtime_a

    _bind(id_b, project_b, "sl-b")
    reg_b = get_slash_registry()
    runtime_b = acquire_project_runtime().agent_runtime
    assert reg_a is not reg_b
    assert getattr(reg_b, "_agent_runtime") is runtime_b
    assert runtime_a is not runtime_b
    assert getattr(reg_a, "_agent_runtime") is runtime_a


def test_durable_clear_a_does_not_wipe_b_vector(
    projects: tuple[Path, Path, str, str],
) -> None:
    """F5: clear(all) on A must not delete B's project-scoped durable/vector data."""
    from antigravity_k.engine.project_memory_paths import project_rag_vector_dir, project_search_cache_dir
    from antigravity_k.engine.vector_store import VectorStore

    project_a, project_b, id_a, id_b = projects

    # Seed distinct search-cache files under each project root.
    cache_a = project_search_cache_dir(project_a) / "a.json"
    cache_b = project_search_cache_dir(project_b) / "b.json"
    cache_a.write_text('{"cached_at": "2099-01-01T00:00:00+00:00", "q": "a"}', encoding="utf-8")
    cache_b.write_text('{"cached_at": "2099-01-01T00:00:00+00:00", "q": "b"}', encoding="utf-8")

    # Seed RAG vector collections when chroma is available.
    seeded_b = False
    try:
        vs_b = VectorStore(str(project_rag_vector_dir(project_b)), collection_name="project_code")
        vs_b.upsert_chunks(
            [
                {
                    "id": "b-chunk-1",
                    "text": "PROJECT_B_VECTOR_MARKER",
                    "metadata": {"source": "b.py"},
                }
            ]
        )
        vs_b.close()
        seeded_b = True
    except Exception:
        seeded_b = False

    _bind(id_a, project_a, "clr-a")
    mm_a = get_memory_manager()
    _ = mm_a.clear("all")

    assert cache_a.exists() is False or not cache_a.read_text(encoding="utf-8")
    # B's project-scoped cache must survive A's clear.
    assert cache_b.exists()
    assert "b" in cache_b.read_text(encoding="utf-8")

    if seeded_b:
        vs_b2 = VectorStore(str(project_rag_vector_dir(project_b)), collection_name="project_code")
        try:
            exported = vs_b2.export_all()
        finally:
            vs_b2.close()
        blob = str(exported)
        assert "PROJECT_B_VECTOR_MARKER" in blob or "b-chunk-1" in blob


def test_scheduled_job_service_is_project_scoped(projects: tuple[Path, Path, str, str]) -> None:
    """F7: scheduled job service must not freeze the first agent_runtime forever."""
    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a, "job-a")
    svc_a = get_scheduled_job_service()
    rt_a = acquire_project_runtime()
    assert svc_a is rt_a.scheduled_job_service
    assert svc_a.submit_agent == rt_a.agent_runtime.submit_task

    _bind(id_b, project_b, "job-b")
    svc_b = get_scheduled_job_service()
    rt_b = acquire_project_runtime()
    assert svc_b is not svc_a
    assert svc_b is rt_b.scheduled_job_service
    assert svc_b.submit_agent == rt_b.agent_runtime.submit_task
