from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

from antigravity_k.engine.orchestrator_handlers import context_enrich_handler
from antigravity_k.engine.state_graph import StateContext


class _SearchResult(TypedDict):
    file: str
    score: float
    functions: list[str]
    classes: list[str]


class _SearchBackend:
    def __init__(self, name: str, results: list[_SearchResult], calls: list[str]) -> None:
        self._name: str = name
        self._results: list[_SearchResult] = results
        self._calls: list[str] = calls

    def build_tree(self) -> str:
        return ""

    def search(self, _query: str, max_files: int) -> list[_SearchResult]:
        self._calls.append(self._name)
        return self._results[:max_files]

    def search_files(self, _query: str, max_files: int) -> list[_SearchResult]:
        self._calls.append(self._name)
        return self._results[:max_files]


class _EmptyRagIndexer:
    def format_context(self, _query: str) -> str:
        return ""


class _KnowledgeEngine:
    def build_ki_prompt(self) -> str:
        return ""


def _result(file_path: str, score: float) -> _SearchResult:
    return {"file": file_path, "score": score, "functions": [], "classes": []}


def _run_enrichment(project_root: Path, memory: _SearchBackend, fallback: _SearchBackend) -> StateContext:
    message = {"role": "user", "content": "select relevant implementation files"}
    context = StateContext(messages=[message], user_message=message["content"], custom_messages=[message])
    orchestrator = SimpleNamespace(
        ctx=SimpleNamespace(ki_engine=_KnowledgeEngine()),
        vault_engine=None,
        project_root=str(project_root),
        _rag_indexer=_EmptyRagIndexer(),
        codebase_memory_search=memory,
        code_tree_indexer=fallback,
        manager=None,
    )
    context_enrich_handler(context, orchestrator)
    return context


def test_graph_memory_results_prevent_fallback_file_search(tmp_path: Path) -> None:
    # Given: graph memory and filesystem fallback disagree about the relevant file.
    graph_file = tmp_path / "src" / "graph_target.py"
    fallback_file = tmp_path / "src" / "fallback_target.py"
    graph_file.parent.mkdir()
    _ = graph_file.write_text("def graph_target():\n    return 'graph'\n", encoding="utf-8")
    _ = fallback_file.write_text("def fallback_target():\n    return 'fallback'\n", encoding="utf-8")
    calls: list[str] = []
    memory = _SearchBackend("memory", [_result("src/graph_target.py", 10.0)], calls)
    fallback = _SearchBackend("fallback", [_result("src/fallback_target.py", 99.0)], calls)

    # When: the real context-enrichment handler selects files.
    context = _run_enrichment(tmp_path, memory, fallback)

    # Then: memory wins and the fallback backend is never queried.
    assert calls == ["memory"]
    assert "src/graph_target.py" in context.rag_context
    assert "src/fallback_target.py" not in context.rag_context


def test_empty_graph_memory_uses_existing_code_tree_fallback(tmp_path: Path) -> None:
    # Given: graph memory has no result and the existing code tree has one safe candidate.
    fallback_file = tmp_path / "src" / "fallback_target.py"
    fallback_file.parent.mkdir()
    _ = fallback_file.write_text("def fallback_target():\n    return 'fallback'\n", encoding="utf-8")
    calls: list[str] = []
    memory = _SearchBackend("memory", [], calls)
    fallback = _SearchBackend("fallback", [_result("src/fallback_target.py", 4.0)], calls)

    # When: context enrichment selects files.
    context = _run_enrichment(tmp_path, memory, fallback)

    # Then: the fallback is queried only after the empty memory result.
    assert calls == ["memory", "fallback"]
    assert "src/fallback_target.py" in context.rag_context


def test_graph_memory_path_escape_is_rejected_before_file_read(tmp_path: Path) -> None:
    # Given: graph memory returns a traversal path and fallback returns an in-project file.
    fallback_file = tmp_path / "src" / "safe_target.py"
    fallback_file.parent.mkdir()
    _ = fallback_file.write_text("def safe_target():\n    return 'safe'\n", encoding="utf-8")
    calls: list[str] = []
    memory = _SearchBackend("memory", [_result("../outside.py", 100.0)], calls)
    fallback = _SearchBackend("fallback", [_result("src/safe_target.py", 1.0)], calls)

    # When: context enrichment validates graph candidates against the project root.
    context = _run_enrichment(tmp_path, memory, fallback)

    # Then: no escaped path is read or rendered and the safe fallback is used.
    assert calls == ["memory", "fallback"]
    assert "../outside.py" not in context.rag_context
    assert "src/safe_target.py" in context.rag_context
