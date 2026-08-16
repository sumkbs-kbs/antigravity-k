"""Tests for memory_service.py — MemoryService class.

Covers:
- __init__ with custom/auto db_path, table creation
- add_knowledge with and without vector_store
- _keyword_search, _vector_search, _hybrid_search (RRF)
- search_knowledge dispatcher
- save_snapshot / load_latest_snapshot
- get_stats, rebuild_embeddings
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from antigravity_k.knowledge.memory_service import MemoryService

# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def mem(tmp_path: Path) -> MemoryService:
    """MemoryService with temporary SQLite database."""
    db_path = str(tmp_path / "test_memory.db")
    return MemoryService(db_path=db_path)


# ─── Init ────────────────────────────────────────────────────────


class TestMemoryServiceInit:
    def test_custom_db_path(self, tmp_path):
        db_path = str(tmp_path / "custom.db")
        ms = MemoryService(db_path=db_path)
        assert ms.db_path == db_path
        assert ms._vector_store is None

    def test_auto_db_path(self):
        """db_path=None이면 data/memory.db에 생성."""
        ms = MemoryService(db_path=None)
        assert ms.db_path is not None
        assert "memory.db" in ms.db_path
        assert "data" in ms.db_path

    def test_tables_created(self, mem: MemoryService):
        """초기화 시 knowledge_items와 context_snapshots 테이블 생성."""
        conn = mem._get_connection()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t["name"] for t in tables]
        assert "knowledge_items" in table_names
        assert "context_snapshots" in table_names


# ─── Add Knowledge ────────────────────────────────────────────────


class TestMemoryServiceAddKnowledge:
    def test_adds_knowledge(self, mem: MemoryService):
        item_id = mem.add_knowledge("python", "Python is a programming language")
        assert item_id is not None
        assert isinstance(item_id, int)

    def test_adds_knowledge_with_tags(self, mem: MemoryService):
        item_id = mem.add_knowledge("pytest", "Testing framework", tags=["test", "python"])
        assert item_id is not None

    def test_adds_knowledge_without_vector_store_still_works(self, mem: MemoryService):
        """vector_store가 None이어도 add_knowledge는 정상 동작."""
        assert mem.vector_store is None  # VectorStore not available by default
        item_id = mem.add_knowledge("topic", "content")
        assert item_id is not None

    def test_adds_knowledge_with_vector_store(self, mem: MemoryService, tmp_path):
        """vector_store가 있으면 store_embedding 호출."""
        ms = MemoryService(db_path=str(tmp_path / "vec_test.db"))

        mock_vs = MagicMock()
        mock_vs.store_embedding.return_value = True
        ms._vector_store = mock_vs

        ms.add_knowledge("test", "vector content")
        mock_vs.store_embedding.assert_called_once()


# ─── Keyword Search ──────────────────────────────────────────────


class TestMemoryServiceKeywordSearch:
    def test_empty_results(self, mem: MemoryService):
        results = mem._keyword_search("nonexistent", 10)
        assert results == []

    def test_matches_topic(self, mem: MemoryService):
        mem.add_knowledge("python", "A programming language")
        mem.add_knowledge("java", "Another language")
        results = mem._keyword_search("python", 10)
        assert len(results) == 1
        assert results[0]["topic"] == "python"

    def test_matches_content(self, mem: MemoryService):
        mem.add_knowledge("general", "This is about python programming")
        results = mem._keyword_search("python", 10)
        assert len(results) == 1

    def test_respects_top_k(self, mem: MemoryService):
        for i in range(5):
            mem.add_knowledge(f"topic{i}", f"content{i}")
        results = mem._keyword_search("topic", 3)
        assert len(results) <= 3

    def test_sets_search_mode(self, mem: MemoryService):
        mem.add_knowledge("python", "content")
        results = mem._keyword_search("python", 10)
        assert results[0]["_search_mode"] == "keyword"

    def test_sets_score(self, mem: MemoryService):
        mem.add_knowledge("python", "content")
        results = mem._keyword_search("python", 10)
        assert results[0]["_score"] == 1.0


# ─── Vector Search ───────────────────────────────────────────────


class TestMemoryServiceVectorSearch:
    def test_falls_back_to_keyword_when_no_vector_store(self, mem: MemoryService):
        """vector_store가 없으면 keyword 검색으로 폴백."""
        mem.add_knowledge("python", "content")
        results = mem._vector_search("python", 10)
        assert len(results) == 1
        assert results[0]["_search_mode"] == "keyword"

    def test_returns_empty_when_no_similar(self, mem: MemoryService):
        mock_vs = MagicMock()
        mock_vs.search_similar.return_value = []
        mem._vector_store = mock_vs
        results = mem._vector_search("anything", 10)
        assert results == []

    def test_uses_vector_store(self, mem: MemoryService):
        mem.add_knowledge("python", "content")
        mock_vs = MagicMock()
        # search_similar returns results with source_id
        mock_vs.search_similar.return_value = [
            {"source_id": 1, "similarity": 0.95},
        ]
        mem._vector_store = mock_vs

        results = mem._vector_search("python", 10)
        assert len(results) == 1
        assert results[0]["_search_mode"] == "vector"
        assert results[0]["_score"] == 0.95


# ─── Hybrid Search (RRF) ─────────────────────────────────────────


class TestMemoryServiceHybridSearch:
    def test_hybrid_search_empty(self, mem: MemoryService):
        results = mem._hybrid_search("nonexistent", 10)
        assert results == []

    def test_hybrid_search_with_data(self, mem: MemoryService):
        mem.add_knowledge("python", "programming")
        mem.add_knowledge("java", "programming")

        # Without vector_store, hybrid = keyword only
        results = mem._hybrid_search("programming", 10)
        assert len(results) >= 2
        assert all(r["_search_mode"] == "hybrid" for r in results)

    def test_hybrid_rrf_scoring(self, mem: MemoryService):
        mem.add_knowledge("python", "best language")

        mock_vs = MagicMock()
        mock_vs.search_similar.return_value = [
            {"source_id": 1, "similarity": 0.9},
        ]
        mem._vector_store = mock_vs

        results = mem._hybrid_search("python", 10)
        assert len(results) >= 1
        assert results[0]["_search_mode"] == "hybrid"
        # RRF score should be a small positive float
        assert 0 < results[0]["_score"] < 1.0

    def test_hybrid_respects_top_k(self, mem: MemoryService):
        for i in range(5):
            mem.add_knowledge(f"topic{i}", f"python related {i}")
        results = mem._hybrid_search("python", 2)
        assert len(results) <= 2


# ─── Search Knowledge ────────────────────────────────────────────


class TestMemoryServiceSearchKnowledge:
    def test_keyword_mode(self, mem: MemoryService):
        mem.add_knowledge("python", "content")
        results = mem.search_knowledge("python", mode="keyword")
        assert len(results) == 1

    def test_vector_mode_fallback(self, mem: MemoryService):
        mem.add_knowledge("python", "content")
        results = mem.search_knowledge("python", mode="vector")
        assert len(results) == 1

    def test_hybrid_mode_default(self, mem: MemoryService):
        mem.add_knowledge("python", "content")
        results = mem.search_knowledge("python")
        assert len(results) >= 1


# ─── Snapshots ────────────────────────────────────────────────────


class TestMemoryServiceSnapshots:
    def test_save_snapshot(self, mem: MemoryService):
        mem.save_snapshot("agent1", {"state": "running", "task": "test"})
        conn = mem._get_connection()
        count = conn.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0]
        assert count == 1

    def test_load_latest_snapshot_none(self, mem: MemoryService):
        result = mem.load_latest_snapshot("nonexistent")
        assert result is None

    def test_load_latest_snapshot(self, mem: MemoryService):
        mem.save_snapshot("agent1", {"state": "idle"})
        mem.save_snapshot("agent1", {"state": "running"})
        result = mem.load_latest_snapshot("agent1")
        assert result["state"] == "running"

    def test_load_latest_snapshot_multiple_agents(self, mem: MemoryService):
        mem.save_snapshot("agent_a", {"task": "A"})
        mem.save_snapshot("agent_b", {"task": "B"})
        result_a = mem.load_latest_snapshot("agent_a")
        result_b = mem.load_latest_snapshot("agent_b")
        assert result_a["task"] == "A"
        assert result_b["task"] == "B"


# ─── Stats ────────────────────────────────────────────────────────


class TestMemoryServiceGetStats:
    def test_empty_stats(self, mem: MemoryService):
        stats = mem.get_stats()
        assert stats["knowledge_items"] == 0
        assert stats["context_snapshots"] == 0
        assert stats["db_path"] == mem.db_path

    def test_with_data(self, mem: MemoryService):
        mem.add_knowledge("topic", "content")
        mem.save_snapshot("agent", {"data": "test"})
        stats = mem.get_stats()
        assert stats["knowledge_items"] == 1
        assert stats["context_snapshots"] == 1

    def test_with_vector_store_stats(self, mem: MemoryService):
        mock_vs = MagicMock()
        mock_vs.get_stats.return_value = {"embeddings": 5}
        mem._vector_store = mock_vs
        stats = mem.get_stats()
        assert "vector_store" in stats
        assert stats["vector_store"]["embeddings"] == 5


# ─── Rebuild Embeddings ──────────────────────────────────────────


class TestMemoryServiceRebuildEmbeddings:
    def test_no_vector_store_returns_zero(self, mem: MemoryService):
        assert mem.vector_store is None
        count = mem.rebuild_embeddings()
        assert count == 0

    def test_rebuilds_embeddings(self, mem: MemoryService):
        mem.add_knowledge("python", "content about python")
        mem.add_knowledge("java", "content about java")

        mock_vs = MagicMock()
        mock_vs.store_embedding.return_value = True
        mem._vector_store = mock_vs

        count = mem.rebuild_embeddings()
        assert count == 2
        assert mock_vs.fit_tfidf.called


# ─── VectorStore property ────────────────────────────────────────


class TestMemoryServiceVectorStoreProperty:
    def test_vector_store_returns_none_when_not_available(self, tmp_path):
        """vector_store 모듈이 없으면 property가 None 반환."""
        ms = MemoryService(db_path=str(tmp_path / "no_vs.db"))
        # VectorStore 모듈이 설치되지 않았으므로 None
        vs = ms.vector_store
        assert vs is None

    def test_vector_store_returns_mock_when_set_directly(self, tmp_path):
        """_vector_store 직접 설정 시 해당 값 반환."""
        ms = MemoryService(db_path=str(tmp_path / "mock_vs.db"))
        mock_vs = MagicMock()
        ms._vector_store = mock_vs
        assert ms.vector_store is mock_vs
