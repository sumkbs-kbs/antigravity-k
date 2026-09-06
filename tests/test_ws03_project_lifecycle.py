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
    from antigravity_k.engine.rag_indexer import RAGIndexer

    project_a, project_b, id_a, id_b = projects
    _bind(id_a, project_a)
    orch_a = get_orchestrator()
    orch_a._rag_indexer = RAGIndexer(project_root=str(project_a))
    _bind(id_b, project_b)
    orch_b = get_orchestrator()
    orch_b._rag_indexer = RAGIndexer(project_root=str(project_b))

    assert orch_a._rag_indexer is not orch_b._rag_indexer
    assert orch_a._rag_indexer.project_root == str(project_a.resolve()) or os.path.abspath(
        orch_a._rag_indexer.project_root
    ) == os.path.abspath(str(project_a))
    assert os.path.abspath(orch_b._rag_indexer.project_root) == os.path.abspath(str(project_b))


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
