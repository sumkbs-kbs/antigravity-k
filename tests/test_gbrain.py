"""Tests for gbrain — Graph + Vector Memory system.

Covers GBrain init, add_node, add_edge, search_semantic, get_related,
close, atexit cleanup, and edge cases.
"""

from __future__ import annotations

import pytest

pytest.importorskip("chromadb", reason="chromadb not installed (pip install -e '.[rag]')")


class TestGBrainInit:
    def test_init_creates_storage_dir(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        storage = tmp_path / "gbrain_test"
        gbrain = GBrain(storage_dir=str(storage))
        assert storage.exists()
        assert gbrain.graph is not None
        assert gbrain.collection is not None
        gbrain.close()

    def test_init_loads_existing_graph(self, tmp_path):
        import networkx as nx

        from antigravity_k.engine.gbrain import GBrain

        storage = tmp_path / "gbrain_existing"
        storage.mkdir(parents=True, exist_ok=True)
        graph_file = storage / "knowledge_graph.graphml"
        g = nx.DiGraph()
        g.add_node("test_node", label="test", content="hello")
        nx.write_graphml(g, str(graph_file))

        gbrain = GBrain(storage_dir=str(storage))
        assert gbrain.graph.has_node("test_node")
        assert gbrain.graph.nodes["test_node"]["label"] == "test"
        gbrain.close()

    def test_init_handles_corrupt_graph(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        storage = tmp_path / "gbrain_corrupt"
        storage.mkdir(parents=True, exist_ok=True)
        graph_file = storage / "knowledge_graph.graphml"
        graph_file.write_text("not valid graphml")

        gbrain = GBrain(storage_dir=str(storage))
        assert len(gbrain.graph.nodes) == 0
        gbrain.close()


class TestGBrainAddNode:
    def test_adds_node_to_graph_and_vector(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_add"))
        gbrain.add_node("node_1", "test_label", "test content", {"source": "test"})

        assert gbrain.graph.has_node("node_1")
        assert gbrain.graph.nodes["node_1"]["label"] == "test_label"
        assert gbrain.collection.count() == 1
        gbrain.close()

    def test_add_node_without_metadata(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_nometa"))
        gbrain.add_node("node_1", "test_label", "content")

        assert gbrain.graph.has_node("node_1")
        assert gbrain.graph.nodes["node_1"]["label"] == "test_label"
        gbrain.close()

    def test_add_node_filters_non_chroma_metadata(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_meta"))
        gbrain.add_node(
            "node_1",
            "test_label",
            "content",
            metadata={"str_key": "val", "int_key": 42, "list_key": [1, 2, 3]},
        )

        result = gbrain.collection.get(ids=["node_1"])
        assert result["metadatas"][0]["str_key"] == "val"
        assert result["metadatas"][0]["int_key"] == 42
        assert "list_key" not in result["metadatas"][0]
        gbrain.close()

    def test_add_node_duplicate_id_updates(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_dup"))
        gbrain.add_node("node_1", "label_a", "content a")
        gbrain.add_node("node_1", "label_b", "content b")

        assert gbrain.graph.nodes["node_1"]["label"] == "label_b"
        gbrain.close()


class TestGBrainAddEdge:
    def test_adds_edge_between_existing_nodes(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_edge"))
        gbrain.add_node("source", "label", "content")
        gbrain.add_node("target", "label", "content")
        gbrain.add_edge("source", "target", "related_to")

        assert gbrain.graph.has_edge("source", "target")
        assert gbrain.graph.edges["source", "target"]["relation"] == "related_to"
        gbrain.close()

    def test_add_edge_missing_source_does_nothing(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_edge_missing"))
        gbrain.add_node("target", "label", "content")
        gbrain.add_edge("nonexistent", "target", "related_to")

        assert not gbrain.graph.has_edge("nonexistent", "target")
        gbrain.close()

    def test_add_edge_missing_target_does_nothing(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_edge_missing_t"))
        gbrain.add_node("source", "label", "content")
        gbrain.add_edge("source", "nonexistent", "related_to")

        assert not gbrain.graph.has_edge("source", "nonexistent")
        gbrain.close()


class TestGBrainSearchSemantic:
    def test_search_returns_results(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_search"))
        gbrain.add_node("n1", "concept", "machine learning overview")
        gbrain.add_node("n2", "concept", "deep learning techniques")

        results = gbrain.search_semantic("machine learning", limit=5)
        assert len(results) >= 1
        gbrain.close()

    def test_search_empty_collection_returns_empty(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_search_empty"))
        results = gbrain.search_semantic("anything")
        assert results == []
        gbrain.close()

    def test_search_with_label_filter(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_search_filter"))
        gbrain.add_node("n1", "concept", "neural networks")
        gbrain.add_node("n2", "preference", "dark mode")

        results = gbrain.search_semantic("networks", filter_label="concept")
        assert len(results) >= 1
        assert results[0]["label"] == "concept"
        gbrain.close()

    def test_search_with_filter_no_match(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_search_nomatch"))
        gbrain.add_node("n1", "concept", "neural networks")

        results = gbrain.search_semantic("networks", filter_label="nonexistent")
        assert len(results) == 0
        gbrain.close()


class TestGBrainGetRelated:
    def test_get_related_returns_neighbors(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_related"))
        gbrain.add_node("center", "concept", "main idea")
        gbrain.add_node("neighbor", "concept", "related idea")
        gbrain.add_edge("center", "neighbor", "links_to")

        related = gbrain.get_related("center")
        assert len(related) == 1
        assert related[0]["id"] == "neighbor"
        gbrain.close()

    def test_get_related_nonexistent_node(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_related_none"))
        result = gbrain.get_related("nonexistent")
        assert result == []
        gbrain.close()

    def test_get_related_node_with_no_edges(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_related_isolated"))
        gbrain.add_node("lonely", "concept", "isolated node")

        related = gbrain.get_related("lonely")
        assert related == []
        gbrain.close()


class TestGBrainClose:
    def test_close_is_idempotent(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_close"))
        gbrain.close()
        gbrain.close()
        assert gbrain._closed is True

    def test_close_cleans_up_chroma(self, tmp_path):
        from antigravity_k.engine.gbrain import GBrain

        gbrain = GBrain(storage_dir=str(tmp_path / "gbrain_close_chroma"))
        gbrain.add_node("test", "label", "content")
        gbrain.close()
        assert gbrain.chroma_client is None


class TestGBrainGlobal:
    def test_global_gbrain_is_singleton(self):
        from antigravity_k.engine.gbrain import global_gbrain

        assert global_gbrain is not None
        assert hasattr(global_gbrain, "graph")
        assert hasattr(global_gbrain, "collection")

    def test_close_global_is_callable(self):
        from antigravity_k.engine.gbrain import _close_global_gbrain

        assert callable(_close_global_gbrain)
