from pathlib import Path
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.memory_contracts import ProjectMemoryBindingError
from antigravity_k.engine.memory_provider import GlobalMemoryProvider, MemoryManager
from antigravity_k.engine.project_memory import (
    ProjectMemoryProvider,
    UnsafeProjectMemoryPathError,
    extract_project_memory_facts,
)


def test_default_engine_context_registers_project_memory_provider(tmp_path: Path) -> None:
    # Given: an engine context is created for one concrete workspace.
    project_root = tmp_path / "project-a"
    project_root.mkdir()

    # When: the default memory stack is initialized.
    context = EngineContext(model_manager=MagicMock(), project_root=str(project_root))

    # Then: project memory participates in the same canonical manager.
    assert "project" in [provider.name for provider in context.memory_manager.providers]


def test_default_engine_context_keeps_episodic_memory_inside_project(tmp_path: Path) -> None:
    # Given: a context is created outside the process working directory.
    project_root = tmp_path / "project-a"
    project_root.mkdir()

    # When: one turn is persisted through the canonical manager.
    context = EngineContext(model_manager=MagicMock(), project_root=str(project_root))
    context.memory_manager.sync_all("project-only turn", "stored")

    # Then: episodic persistence is rooted in that project rather than the user-global store.
    assert (project_root / ".antigravity" / "memory" / "episodic" / "episodes.json").exists()


def test_cognitive_memory_database_is_project_scoped(tmp_path: Path) -> None:
    # Given: two workspaces use independent engine contexts.
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()

    # When: both cognitive loops initialize their durable stores.
    context_a = EngineContext(model_manager=MagicMock(), project_root=str(project_a))
    context_b = EngineContext(model_manager=MagicMock(), project_root=str(project_b))

    # Then: each SQLite database resides under its own project root.
    path_a = Path(context_a.cognitive_loop.cavemem_store.db_path).resolve()
    path_b = Path(context_b.cognitive_loop.cavemem_store.db_path).resolve()
    assert path_a == project_a / ".antigravity" / "memory" / "cavemem.sqlite3"
    assert path_b == project_b / ".antigravity" / "memory" / "cavemem.sqlite3"


def test_project_decision_is_latest_wins_across_restart(tmp_path: Path) -> None:
    # Given: one project changes its explicit database decision.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("이 프로젝트에서는 데이터베이스로 PostgreSQL을 사용하기로 했어", "알겠습니다")
    provider.sync_turn("이 프로젝트에서는 데이터베이스로 SQLite를 사용하기로 했어", "알겠습니다")

    # When: a new process-level provider reloads the same project.
    recalled = ProjectMemoryProvider(project_root).prefetch("데이터베이스 설정을 적용해줘")

    # Then: one normalized latest decision remains.
    assert "[project:decision:database] sqlite" in recalled
    assert "postgresql" not in recalled


def test_current_project_decision_correction_wins_before_sync(tmp_path: Path) -> None:
    # Given: durable project memory still holds the old framework decision.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    project = ProjectMemoryProvider(project_root)
    project.sync_turn("이 프로젝트에서는 프론트엔드로 React를 사용하기로 했어", "알겠습니다")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(project)

    # When: the current request changes the same decision before turn sync.
    recalled = manager.prefetch_all("이 프로젝트에서는 프론트엔드로 Svelte를 사용하기로 했어")

    # Then: the current explicit value is the only model-visible decision.
    assert "[resolved:project:decision:frontend source=current_user scope=project] svelte" in recalled
    assert "react" not in recalled


def test_project_memory_never_crosses_workspace_boundary(tmp_path: Path) -> None:
    # Given: two projects choose different values for the same decision key.
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    memory_a = ProjectMemoryProvider(project_a)
    memory_b = ProjectMemoryProvider(project_b)
    memory_a.sync_turn("이 프로젝트에서는 백엔드로 FastAPI를 사용하기로 했어", "알겠습니다")
    memory_b.sync_turn("이 프로젝트에서는 백엔드로 Django를 사용하기로 했어", "알겠습니다")

    # When: each workspace recalls its own architecture.
    recalled_a = memory_a.prefetch("백엔드 구현")
    recalled_b = memory_b.prefetch("백엔드 구현")

    # Then: neither provider can observe the other workspace's value.
    assert "fastapi" in recalled_a
    assert "django" not in recalled_a
    assert "django" in recalled_b
    assert "fastapi" not in recalled_b


def test_structured_project_fact_persists_without_prose_inference(tmp_path: Path) -> None:
    # Given: a caller supplies an arbitrary fact through the typed metadata boundary.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)

    # When: the turn sync stores a fact with a stable key.
    provider.sync_turn(
        "record project configuration",
        "stored",
        metadata={"project_memory_facts": {"facts": {"python_version": "3.13"}}},
    )

    # Then: a fresh provider exposes the project fact with provenance.
    recalled = ProjectMemoryProvider(project_root).prefetch("Python runtime")
    assert "[project:fact:python_version] 3.13" in recalled


def _manager_with_project_and_global(tmp_path: Path) -> tuple[MemoryManager, GlobalMemoryProvider]:
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    project = ProjectMemoryProvider(project_root)
    project.sync_turn("이 프로젝트에서는 데이터베이스로 SQLite를 사용하기로 했어", "알겠습니다")
    global_memory = GlobalMemoryProvider(memory_dir=str(tmp_path / "global"))
    global_memory.sync_turn("내 이름은 김철수야", "안녕하세요")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(project)
    manager.add_provider(global_memory)
    return manager, global_memory


def test_project_scope_export_excludes_global_memory(tmp_path: Path) -> None:
    # Given: one manager owns both project and global durable facts.
    manager, _ = _manager_with_project_and_global(tmp_path)

    # When: only project memory is exported.
    exported = manager.export("project")

    # Then: the export contains project provenance and no global identity.
    assert exported["providers"]["project"][0]["value"] == "sqlite"
    assert exported["providers"]["global"] == []


def test_project_scope_clear_does_not_mutate_global_memory(tmp_path: Path) -> None:
    # Given: one manager owns both project and global durable facts.
    manager, global_memory = _manager_with_project_and_global(tmp_path)

    # When: only project memory is purged.
    deleted = manager.clear("project")

    # Then: project data is removed while global identity survives.
    assert deleted == {"project": 1, "global": 0}
    assert global_memory.get_identity_fact("name") == "김철수"


def test_project_memory_redaction_persists_across_restart(tmp_path: Path) -> None:
    # Given: a project fact contains secret-like data.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn(
        "record",
        "stored",
        metadata={"project_memory_facts": {"facts": {"private_token": "TOKEN=project-secret-123456"}}},
    )

    # When: project-scoped redaction is applied.
    changed = provider.redact("project")

    # Then: masking survives a new provider instance.
    assert changed == 1
    assert "TOKEN=<REDACTED>" in ProjectMemoryProvider(project_root).prefetch("token")


def test_project_memory_retention_persists_across_restart(tmp_path: Path) -> None:
    # Given: a project fact was recorded more than one day ago.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    writer = ProjectMemoryProvider(project_root, clock=lambda: 1.0)
    writer.sync_turn("이 프로젝트에서는 데이터베이스로 SQLite를 사용하기로 했어", "알겠습니다")
    reloaded = ProjectMemoryProvider(project_root, clock=lambda: 200_000.0)

    # When: one-day retention is applied after restart.
    deleted = reloaded.apply_retention(1)

    # Then: the expired fact remains absent in subsequent instances.
    assert deleted == 1
    assert ProjectMemoryProvider(project_root).prefetch("database") == ""


def test_memory_manager_rejects_a_second_project_binding(tmp_path: Path) -> None:
    # Given: a shared manager is already bound to project A.
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    manager = MemoryManager(project_root=str(project_a))

    # When / Then: rebinding to project B fails instead of leaking A's providers.
    with pytest.raises(ProjectMemoryBindingError):
        manager.bind_project_root(project_b)


def test_project_memory_rejects_symlink_escape(tmp_path: Path) -> None:
    # Given: the internal metadata directory is redirected outside the project.
    project_root = tmp_path / "project-a"
    outside = tmp_path / "outside"
    project_root.mkdir()
    outside.mkdir()
    (project_root / ".antigravity").symlink_to(outside, target_is_directory=True)

    # When / Then: provider construction fails before accepting the escaped path.
    with pytest.raises(UnsafeProjectMemoryPathError):
        ProjectMemoryProvider(project_root)
    assert not (outside / "memory").exists()


def test_engine_context_rejects_memory_symlink_escape_before_writing(tmp_path: Path) -> None:
    # Given: the project metadata directory redirects durable memory outside the workspace.
    project_root = tmp_path / "project-a"
    outside = tmp_path / "outside"
    project_root.mkdir()
    outside.mkdir()
    (project_root / ".antigravity").symlink_to(outside, target_is_directory=True)

    # When / Then: full context construction fails before any memory store writes outside.
    with pytest.raises(UnsafeProjectMemoryPathError):
        EngineContext(model_manager=MagicMock(), project_root=str(project_root))
    assert not (outside / "memory").exists()


def test_project_decision_extractor_is_conservative() -> None:
    # Given: messages mention technologies without declaring a project decision.
    messages = (
        "PostgreSQL 문서를 조사해줘",
        "React와 Svelte를 비교해줘",
        "I usually use Django for examples",
    )

    # When: each message crosses the project decision extraction boundary.
    extracted = tuple(extract_project_memory_facts(message) for message in messages)

    # Then: none is promoted to durable project architecture.
    assert extracted == ({}, {}, {})


def test_explicit_project_fact_syntax_is_available_to_normal_turn_sync(tmp_path: Path) -> None:
    # Given: a project provider receives an explicit typed fact in a normal user message.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)

    # When: the normal turn lifecycle processes the message without caller metadata.
    provider.sync_turn("프로젝트 사실: python_version=3.13", "기억했습니다")

    # Then: the arbitrary fact is durable and model-visible after restart.
    recalled = ProjectMemoryProvider(project_root).prefetch("runtime")
    assert "[project:fact:python_version] 3.13" in recalled


def test_explicit_project_decision_correction_resolves_before_sync(tmp_path: Path) -> None:
    # Given: durable project memory contains an older arbitrary decision.
    project_root = tmp_path / "project-a"
    project_root.mkdir()
    provider = ProjectMemoryProvider(project_root)
    provider.sync_turn("프로젝트 결정: deployment=vm", "기억했습니다")
    manager = MemoryManager(project_root=str(project_root))
    manager.add_provider(provider)

    # When: the current turn changes that decision using the explicit syntax.
    recalled = manager.prefetch_all("프로젝트 결정: deployment=kubernetes")

    # Then: the current value replaces the stale durable value before persistence.
    assert "[resolved:project:decision:deployment source=current_user scope=project] kubernetes" in recalled
    assert "vm" not in recalled


def test_engine_context_rejects_memory_manager_from_another_project(tmp_path: Path) -> None:
    # Given: a manager is bound to a different workspace.
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    manager = MemoryManager(project_root=str(project_a))

    # When / Then: context construction fails closed before using foreign providers.
    with pytest.raises(ProjectMemoryBindingError):
        EngineContext(
            model_manager=MagicMock(),
            project_root=str(project_b),
            memory_manager=manager,
        )


def test_dependency_memory_manager_rejects_workspace_switch(tmp_path: Path, monkeypatch) -> None:
    # Given: the API singleton has been initialized for project A.
    from antigravity_k.api import dependencies

    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    manager = MemoryManager(project_root=str(project_a))
    monkeypatch.setattr(dependencies, "_memory_manager", manager)

    # When / Then: requesting project B fails instead of returning A's singleton.
    with pytest.raises(ProjectMemoryBindingError):
        dependencies.get_memory_manager(str(project_b))


def test_engine_context_recall_isolated_across_project_episodic_stores(tmp_path: Path) -> None:
    # Given: two project contexts persist different architecture turns.
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    context_a = EngineContext(model_manager=MagicMock(), project_root=str(project_a))
    context_b = EngineContext(model_manager=MagicMock(), project_root=str(project_b))
    context_a.memory_manager.sync_all("이 프로젝트에서는 백엔드로 FastAPI를 사용하기로 했어", "확인")
    context_b.memory_manager.sync_all("이 프로젝트에서는 백엔드로 Django를 사용하기로 했어", "확인")

    # When: each full manager recalls backend context.
    recalled_a = context_a.memory_manager.prefetch_all("백엔드 구현")
    recalled_b = context_b.memory_manager.prefetch_all("백엔드 구현")

    # Then: neither typed nor episodic memory crosses the workspace boundary.
    assert "fastapi" in recalled_a.lower()
    assert "django" not in recalled_a.lower()
    assert "django" in recalled_b.lower()
    assert "fastapi" not in recalled_b.lower()


@pytest.mark.asyncio
async def test_project_scope_purge_route_is_audited(tmp_path: Path, monkeypatch) -> None:
    # Given: the authenticated route resolves a manager with one project decision.
    from antigravity_k.api.routes import system_api

    project_root = tmp_path / "project-a"
    project_root.mkdir()
    manager = MemoryManager(project_root=str(project_root))
    project = ProjectMemoryProvider(project_root)
    project.sync_turn("프로젝트 결정: deployment=kubernetes", "기억했습니다")
    manager.add_provider(project)
    audit = MagicMock()
    monkeypatch.setattr(system_api, "_get_memory_manager", lambda: manager)
    monkeypatch.setattr(system_api, "get_audit_logger", lambda: audit)

    class Request:
        async def json(self):
            return {"scope": "project"}

    # When: project memory is purged through the route surface.
    result = await system_api.purge_memory(Request())

    # Then: the project provider count and scope are audited.
    assert result == {"ok": True, "scope": "project", "deleted": {"project": 1}}
    audit.log_event.assert_called_once_with(
        "memory_purge",
        {"scope": "project", "deleted": {"project": 1}},
    )
