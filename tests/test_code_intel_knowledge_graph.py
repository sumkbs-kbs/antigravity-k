"""Tests for KnowledgeGraph (code_intel/knowledge_graph.py)."""

from antigravity_k.engine.code_intel.knowledge_graph import KnowledgeGraph, NodeType


class TestKnowledgeGraph:
    def test_add_node_and_retrieve(self):
        kg = KnowledgeGraph()
        kg.add_node("file1", NodeType.FILE, {"name": "main.py"})
        assert "file1" in kg.nodes
        assert kg.nodes["file1"]["name"] == "main.py"
        assert kg.nodes["file1"]["node_type"] == NodeType.FILE

    def test_add_edge(self):
        kg = KnowledgeGraph()
        kg.add_node("f1", NodeType.FILE, {"name": "a.py"})
        kg.add_node("f2", NodeType.FUNCTION, {"name": "func_a"})
        kg.add_edge("f1", "f2", "CONTAINS")
        assert len(kg.edges) == 1
        assert kg.edges[0]["source"] == "f1"
        assert kg.edges[0]["target"] == "f2"
        assert kg.edges[0]["relationship"] == "CONTAINS"

    def test_get_nodes_by_type(self):
        kg = KnowledgeGraph()
        kg.add_node("f1", NodeType.FILE, {"name": "a.py"})
        kg.add_node("f2", NodeType.FILE, {"name": "b.py"})
        kg.add_node("func1", NodeType.FUNCTION, {"name": "func"})
        files = kg.get_nodes_by_type(NodeType.FILE)
        funcs = kg.get_nodes_by_type(NodeType.FUNCTION)
        assert len(files) == 2
        assert len(funcs) == 1

    def test_stats_empty(self):
        kg = KnowledgeGraph()
        stats = kg.stats()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0
        assert stats["node_types"] == {}

    def test_stats_with_data(self):
        kg = KnowledgeGraph()
        kg.add_node("a", NodeType.FILE, {})
        kg.add_node("b", NodeType.FUNCTION, {})
        kg.add_node("c", NodeType.CLASS, {})
        kg.add_edge("a", "b", "CONTAINS")
        stats = kg.stats()
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 1
        assert stats["node_types"][NodeType.FILE] == 1
        assert stats["node_types"][NodeType.FUNCTION] == 1
        assert stats["node_types"][NodeType.CLASS] == 1

    def test_node_type_enum_values(self):
        assert NodeType.FILE.value == "File"
        assert NodeType.FUNCTION.value == "Function"
        assert NodeType.CLASS.value == "Class"
        assert NodeType.VARIABLE.value == "Variable"
        assert NodeType.MODULE.value == "Module"
