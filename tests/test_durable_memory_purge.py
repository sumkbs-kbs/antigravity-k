from pathlib import Path
from unittest.mock import MagicMock

import networkx as nx
import pytest

from antigravity_k.engine.durable_memory import DurableMemoryProvider
from antigravity_k.engine.gbrain import GBrain
from antigravity_k.engine.memory_provider import MemoryManager
from antigravity_k.engine.vector_store import VectorStore
from antigravity_k.knowledge import wiki
from antigravity_k.knowledge.memory_service import MemoryService


def test_memory_service_clear_all_removes_rows_and_embeddings(tmp_path: Path):
    service = MemoryService(db_path=str(tmp_path / "memory.db"))
    service.add_knowledge("topic", "private knowledge")
    service.save_snapshot("agent", {"secret": "snapshot"})
    vector_store = MagicMock()
    service._vector_store = vector_store

    deleted = service.clear_all()

    assert deleted == 2
    assert service.get_stats()["knowledge_items"] == 0
    assert service.get_stats()["context_snapshots"] == 0
    vector_store.clear.assert_called_once_with()


def test_vector_store_clear_deletes_all_collection_ids():
    class Collection:
        def get(self):
            return {"ids": ["one", "two"]}

        def delete(self, ids):
            self.deleted = ids

    store = object.__new__(VectorStore)
    store.collection = Collection()
    store._closed = True

    assert store.clear() == 2
    assert store.collection.deleted == ["one", "two"]


def test_wiki_clear_all_removes_entries_and_generated_markdown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(wiki, "WIKI_DIR", tmp_path / "wiki")
    knowledge = wiki.LLMWiki(db_path=tmp_path / "wiki.db")
    knowledge.add_entry("Private note", "secret content", category="note")

    deleted = knowledge.clear_all()

    assert deleted == 1
    assert knowledge.get_stats()["total_entries"] == 0
    assert list((tmp_path / "wiki").rglob("*.md")) == []


def test_gbrain_clear_all_removes_graph_and_vectors():
    class Collection:
        def get(self):
            return {"ids": ["one", "two"]}

        def delete(self, ids):
            self.deleted = ids

    brain = object.__new__(GBrain)
    brain.graph = nx.DiGraph()
    brain.graph.add_nodes_from(["one", "two"])
    brain.collection = Collection()
    brain._closed = True
    brain._save_graph = MagicMock()

    assert brain.clear_all() == 2
    assert brain.graph.number_of_nodes() == 0
    assert brain.collection.deleted == ["one", "two"]
    brain._save_graph.assert_called_once_with()


def test_durable_provider_runs_purge_only_for_all_scope():
    clear_all = MagicMock(return_value=3)
    manager = MemoryManager()
    manager.add_provider(DurableMemoryProvider("durable", clear_all))

    assert manager.clear("global") == {"durable": 0}
    clear_all.assert_not_called()
    assert manager.clear("all") == {"durable": 3}
    clear_all.assert_called_once_with()


def test_dependency_memory_manager_registers_durable_providers(tmp_path: Path, monkeypatch):
    from antigravity_k.api import dependencies
    from antigravity_k.engine.memory_provider import (
        EpisodicMemoryProvider,
        GlobalMemoryProvider,
    )
    from antigravity_k.engine.session_manager import SessionManager

    session_manager = SessionManager(base_dir=str(tmp_path / "sessions"))
    monkeypatch.setattr(dependencies, "_memory_manager", None)
    monkeypatch.setattr(dependencies, "_get_session_manager", lambda: session_manager)
    monkeypatch.setattr(
        dependencies,
        "EpisodicMemoryProvider",
        lambda max_episodes, persist_dir: EpisodicMemoryProvider(
            max_episodes,
            persist_dir=str(tmp_path / "episodes"),
        ),
    )
    monkeypatch.setattr(
        dependencies,
        "GlobalMemoryProvider",
        lambda: GlobalMemoryProvider(memory_dir=str(tmp_path / "global")),
    )
    monkeypatch.setattr(dependencies, "_clear_memory_service", lambda: 0)
    monkeypatch.setattr(dependencies, "_clear_wiki", lambda: 0)
    monkeypatch.setattr(dependencies, "_clear_gbrain", lambda: 0)
    monkeypatch.setattr(dependencies, "_clear_project_vector", lambda: 0)
    monkeypatch.setattr(dependencies, "_clear_search_cache", lambda: 0)

    project_root = tmp_path / "project"
    project_root.mkdir()
    manager = dependencies.get_memory_manager(str(project_root))

    assert [provider.name for provider in manager.providers] == [
        "builtin",
        "episodic",
        "working_memory",
        "global",
        "project",
        "memory_service",
        "wiki",
        "gbrain",
        "project_vector",
        "search_cache",
    ]


@pytest.mark.asyncio
async def test_memory_purge_route_reports_durable_provider_counts(monkeypatch):
    from antigravity_k.api.routes import system_api

    manager = MemoryManager()
    manager.add_provider(DurableMemoryProvider("wiki", lambda: 4))
    audit_logger = MagicMock()
    monkeypatch.setattr(system_api, "_get_memory_manager", lambda: manager)
    monkeypatch.setattr(system_api, "get_audit_logger", lambda: audit_logger)

    class Request:
        async def json(self):
            return {"scope": "all"}

    result = await system_api.purge_memory(Request())

    assert result["deleted"] == {"wiki": 4}
    audit_logger.log_event.assert_called_once_with(
        "memory_purge",
        {"scope": "all", "deleted": {"wiki": 4}},
    )
