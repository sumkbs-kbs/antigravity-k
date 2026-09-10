from __future__ import annotations

import json
from pathlib import Path

from antigravity_k.engine.optimizers.graphify_builder import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    build_file_index_rows,
    build_graph,
    find_path,
    hybrid_retrieve,
    load_graph,
    save_graph,
)
from antigravity_k.tools.graphify_tool import GraphifyTool


def test_ast_constant_and_docstring_extraction(tmp_path: Path) -> None:
    code = '''"""Module docstring explaining engine."""

DEFAULT_BUFFER_SIZE = 4096
API_ENDPOINT = "https://api.ssak.ai/v1"
_PRIVATE_CONST = 123

class EngineRunner:
    """Core engine runner for orchestrating execution."""
    def run(self):
        return True

def standalone_helper():
    """Helper function for parsing."""
    pass
'''
    (tmp_path / "engine.py").write_text(code, encoding="utf-8")
    graph = build_graph(tmp_path)

    # 1. Module docstring
    module_nodes = [n for n in graph.nodes if n.kind == "module"]
    assert len(module_nodes) == 1
    assert "Module docstring explaining engine" in module_nodes[0].name

    # 2. Constants
    const_nodes = [n for n in graph.nodes if n.kind == "constant"]
    const_names = [n.name for n in const_nodes]
    assert any("DEFAULT_BUFFER_SIZE" in name for name in const_names)
    assert any("API_ENDPOINT https://api.ssak.ai/v1" in name for name in const_names)
    assert not any("_PRIVATE_CONST" in name for name in const_names)

    # 3. Classes and functions with docstrings
    class_nodes = [n for n in graph.nodes if n.kind == "class"]
    assert len(class_nodes) == 1
    assert "EngineRunner" in class_nodes[0].name
    assert "Core engine runner" in class_nodes[0].name

    func_nodes = [n for n in graph.nodes if n.kind == "function"]
    assert any("run" in n.name for n in func_nodes)
    assert any("standalone_helper" in n.name and "Helper function" in n.name for n in func_nodes)


def test_multi_language_symbol_extraction(tmp_path: Path) -> None:
    ts_code = "export class TaskClient {\n  execute() {}\n}\nexport function fetchStatus() {}\n"
    (tmp_path / "client.ts").write_text(ts_code, encoding="utf-8")

    graph = build_graph(tmp_path)
    symbols = {n.name for n in graph.nodes if n.kind == "symbol"}
    assert "TaskClient" in symbols
    assert "fetchStatus" in symbols


def test_graph_call_edges_and_find_path(tmp_path: Path) -> None:
    code = """
def step_c():
    return 42

def step_b():
    return step_c()

def step_a():
    return step_b()
"""
    (tmp_path / "steps.py").write_text(code, encoding="utf-8")
    graph = build_graph(tmp_path)

    path = find_path(graph, "step_a", "step_c")
    assert path is not None
    assert len(path) >= 2


def test_incremental_hash_caching(tmp_path: Path) -> None:
    file_path = tmp_path / "cache_test.py"
    file_path.write_text("def v1(): pass\n", encoding="utf-8")

    graph1 = build_graph(tmp_path)
    assert any("v1" in n.name for n in graph1.nodes)
    hash_v1 = graph1.file_hashes.get("cache_test.py")
    assert hash_v1 is not None

    # Re-run with cache: should retain nodes without re-parsing
    graph2 = build_graph(tmp_path, cached_graph=graph1)
    assert graph2.file_hashes.get("cache_test.py") == hash_v1
    assert any("v1" in n.name for n in graph2.nodes)

    # Modify file: hash should change and new symbol appear
    file_path.write_text("def v2(): pass\n", encoding="utf-8")
    graph3 = build_graph(tmp_path, cached_graph=graph1)
    assert any("v2" in n.name for n in graph3.nodes)
    assert not any("v1" in n.name for n in graph3.nodes)
    assert graph3.file_hashes.get("cache_test.py") != hash_v1


def test_hybrid_retrieve_and_formatting(tmp_path: Path) -> None:
    (tmp_path / "auth_policy.py").write_text("class RoleBasedAuthGate:\n    pass\n", encoding="utf-8")
    (tmp_path / "database.py").write_text("class PostgresPool:\n    pass\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    retrieved = hybrid_retrieve(graph, "Where is the authentication policy gate defined?", top_k=5)
    assert "auth_policy.py" in retrieved

    rows = build_file_index_rows(graph, retrieved)
    assert any("auth_policy.py" in r and "RoleBasedAuthGate" in r for r in rows)


def test_save_and_load_graph_roundtrip(tmp_path: Path) -> None:
    g = KnowledgeGraph(
        nodes=[GraphNode("file.py:func:10", "function", "my_func", "file.py", 10)],
        edges=[GraphEdge("file.py:func:10", "other_func", "calls")],
        file_hashes={"file.py": "abcdef1234567890"},
    )
    json_path = tmp_path / "graph.json"
    save_graph(g, json_path)

    loaded = load_graph(json_path)
    assert len(loaded.nodes) == 1
    assert loaded.nodes[0].node_id == "file.py:func:10"
    assert len(loaded.edges) == 1
    assert loaded.edges[0].relation == "calls"
    assert loaded.file_hashes["file.py"] == "abcdef1234567890"


def test_graphify_tool_execution(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        '"""User billing service."""\nclass BillingService:\n    def invoice(self):\n        pass\n',
        encoding="utf-8",
    )

    tool = GraphifyTool(project_root=str(tmp_path))

    # 1. Action: hybrid_retrieve
    res_hybrid = tool.execute(action="hybrid_retrieve", query="billing service invoice")
    assert "Retrieved" in res_hybrid
    assert "service.py" in res_hybrid

    # 2. Action: query
    res_query = tool.execute(action="query", query="BillingService")
    assert "BillingService" in res_query
    assert "service.py" in res_query

    # 3. Action: explain
    res_explain = tool.execute(action="explain", query="BillingService")
    data = json.loads(res_explain)
    assert data["found"] is True
    assert data["node"]["file"] == "service.py"

    # 4. Error handling
    assert "required" in tool.execute(query="")
    assert "required" in tool.execute(action="path", query="foo")


def test_graphify_tool_auto_discovered() -> None:
    from antigravity_k.tools.tool_registry import ToolRegistry

    reg = ToolRegistry()
    reg.auto_discover("antigravity_k.tools")
    assert "graphify" in reg
    tool = reg.get_tool("graphify")
    assert tool is not None
    assert tool.name == "graphify"
