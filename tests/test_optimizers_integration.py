from __future__ import annotations

import json
from pathlib import Path

from antigravity_k.engine.optimizers import (
    ContentKind,
    HeadroomCompressor,
    apply_ponytail,
    build_graph,
    explain_node,
    query_graph,
)


def test_headroom_compresses_json() -> None:
    h = HeadroomCompressor()
    text = json.dumps({"a": 1, "b": [1, 2, 3], "c": {"d": "e"}}, indent=2)
    compressed, report = h.compress(text)
    assert report.kind is ContentKind.JSON
    assert report.compressed_chars < report.original_chars
    assert json.loads(compressed) == {"a": 1, "b": [1, 2, 3], "c": {"d": "e"}}


def test_headroom_strips_code_docstrings() -> None:
    h = HeadroomCompressor()
    code = 'def f(x):\n    """long docstring wastes tokens"""\n    return x\n'
    compressed, report = h.compress(code)
    assert report.kind is ContentKind.CODE
    assert "docstring wastes tokens" not in compressed
    assert "return x" in compressed


def test_ponytail_injects_directive() -> None:
    msgs: list[dict[str, object]] = [{"role": "user", "content": "write code"}]
    result = apply_ponytail(msgs)
    assert result[0]["role"] == "system"
    assert "lazy-senior-developer" in str(result[0]["content"])


def test_ponytail_appends_to_existing_system() -> None:
    msgs: list[dict[str, object]] = [
        {"role": "system", "content": "Be safe."},
        {"role": "user", "content": "hi"},
    ]
    result = apply_ponytail(msgs)
    assert "Be safe." in str(result[0]["content"])
    assert "lazy-senior-developer" in str(result[0]["content"])
    assert len(result) == 2


def test_ponytail_idempotent() -> None:
    msgs: list[dict[str, object]] = [{"role": "user", "content": "hi"}]
    once = apply_ponytail(msgs)
    twice = apply_ponytail(once)
    assert once == twice


def test_graphify_builds_graph(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("def foo():\n    pass\nclass Bar:\n    pass\n", encoding="utf-8")
    graph = build_graph(tmp_path)
    names = {n.name.split()[0] for n in graph.nodes}
    assert "foo" in names
    assert "Bar" in names


def test_graphify_query_and_explain(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("def alpha():\n    pass\ndef beta():\n    pass\n", encoding="utf-8")
    graph = build_graph(tmp_path)
    hits = query_graph(graph, "alpha")
    assert hits and hits[0].name.split()[0] == "alpha"
    exp = explain_node(graph, "alpha")
    assert exp["found"] is True
