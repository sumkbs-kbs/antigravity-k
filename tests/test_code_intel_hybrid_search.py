"""Tests for HybridSearchEngine (code_intel/hybrid_search.py)."""

import pytest

from antigravity_k.engine.code_intel.hybrid_search import HybridSearchEngine


@pytest.fixture
def graph():
    """Create a graph with some nodes for testing."""

    class FakeGraph:
        def __init__(self):
            self.nodes = {
                "f1": {"name": "orchestrator.py", "type": "file"},
                "f2": {"name": "model_manager.py", "type": "file"},
                "f3": {"name": "main.py", "type": "file"},
            }

    return FakeGraph()


class TestHybridSearchEngine:
    def test_init(self, graph):
        engine = HybridSearchEngine(graph)
        assert engine.graph == graph
        assert not engine.index_built

    def test_build_index(self, graph):
        engine = HybridSearchEngine(graph)
        engine.build_index()
        assert engine.index_built

    def test_search_finds_results(self, graph):
        engine = HybridSearchEngine(graph)
        results = engine.search("orchestrator", top_k=5)
        assert len(results) >= 1
        assert any(r["name"] == "orchestrator.py" for r in results)

    def test_search_auto_builds_index(self, graph):
        engine = HybridSearchEngine(graph)
        assert not engine.index_built
        engine.search("main", top_k=5)
        assert engine.index_built  # auto-builds

    def test_search_case_insensitive(self, graph):
        engine = HybridSearchEngine(graph)
        results = engine.search("MODEL_MANAGER", top_k=5)
        assert len(results) >= 1

    def test_search_empty_query(self, graph):
        engine = HybridSearchEngine(graph)
        results = engine.search("", top_k=5)
        assert len(results) == 0

    def test_search_no_match(self, graph):
        engine = HybridSearchEngine(graph)
        results = engine.search("nonexistent", top_k=5)
        assert len(results) == 0

    def test_search_top_k_limit(self, graph):
        engine = HybridSearchEngine(graph)
        results = engine.search("orchestrator", top_k=1)
        assert len(results) <= 1
