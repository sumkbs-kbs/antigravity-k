import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, final, runtime_checkable

from antigravity_k.engine.rag_indexer import RAGIndexer


@final
class OrderedVectorStore:
    def __init__(self, chunks: Sequence[Mapping[str, object]]) -> None:
        self._chunks: list[Mapping[str, object]] = list(chunks)
        self.queries: list[str] = []

    def search(self, query: str, n_results: int = 5) -> list[dict[str, object]]:
        self.queries.append(query)
        return [dict(chunk) for chunk in self._chunks[:n_results]]


@runtime_checkable
class MetadataLike(Protocol):
    def get(self, key: str, default: object | None = None, /) -> object | None: ...


def source_of(result: Mapping[str, object]) -> str:
    metadata = result.get("metadata")
    if not isinstance(metadata, MetadataLike):
        raise AssertionError("result metadata must be a mapping")
    source = metadata.get("source")
    if not isinstance(source, str):
        raise AssertionError("result metadata source must be a string")
    return source


def test_keyword_search_splits_snake_case_identifiers():
    store = OrderedVectorStore(
        [
            {
                "id": "recall",
                "text": "class ContextArtifactRecall: ...",
                "metadata": {"source": "recall.py", "node_name": "ContextArtifactRecall"},
            },
        ],
    )
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    results = indexer.search("context_artifact_recall", n_results=1, mode="keyword")

    assert [result["id"] for result in results] == ["recall"]


def test_hybrid_search_keeps_multiple_sources_when_one_source_dominates():
    chunks = [
        {"id": "a1", "text": "target", "metadata": {"source": "a.py", "node_name": "target_a1"}},
        {"id": "a2", "text": "target", "metadata": {"source": "a.py", "node_name": "target_a2"}},
        {"id": "a3", "text": "target", "metadata": {"source": "a.py", "node_name": "target_a3"}},
        {"id": "b1", "text": "target", "metadata": {"source": "b.py", "node_name": "target_b1"}},
    ]
    store = OrderedVectorStore(chunks)
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    results = indexer.search("target", n_results=3, mode="hybrid")

    assert {source_of(result) for result in results} == {"a.py", "b.py"}
    assert len(results) == 3


def test_hybrid_search_drops_stale_sources_before_context_injection(tmp_path: Path):
    stale_source = tmp_path / "stale.py"
    fresh_source = tmp_path / "fresh.py"
    _ = stale_source.write_text("new content", encoding="utf-8")
    _ = fresh_source.write_text("fresh content", encoding="utf-8")
    stale_hash = hashlib.md5(b"old content").hexdigest()
    fresh_hash = hashlib.md5(fresh_source.read_bytes()).hexdigest()
    store = OrderedVectorStore(
        [
            {
                "id": "stale",
                "text": "target stale",
                "metadata": {
                    "source": "stale.py",
                    "node_name": "target_stale",
                    "source_hash": stale_hash,
                },
            },
            {
                "id": "fresh",
                "text": "target fresh",
                "metadata": {
                    "source": "fresh.py",
                    "node_name": "target_fresh",
                    "source_hash": fresh_hash,
                },
            },
        ],
    )
    indexer = RAGIndexer(project_root=str(tmp_path), vector_store=store)

    results = indexer.search("target", n_results=2, mode="hybrid")

    assert [result["id"] for result in results] == ["fresh"]


def test_hybrid_search_prefers_executable_chunks_over_import_headers_when_terms_tie():
    # Given: an import header and an executable chunk contain the same query terms.
    chunks = [
        {
            "id": "imports",
            "text": "source hash freshness provenance citation",
            "metadata": {
                "source": "imports.py",
                "node_type": "module_header",
                "node_name": "imports",
            },
        },
        {
            "id": "implementation",
            "text": "source hash freshness provenance citation",
            "metadata": {"source": "implementation.py", "node_type": "function", "node_name": "worker"},
        },
    ]
    indexer = RAGIndexer(project_root="/tmp", vector_store=OrderedVectorStore(chunks))

    # When: hybrid search ranks the query.
    results = indexer.search("source hash freshness provenance citation", n_results=2, mode="hybrid")

    # Then: executable evidence is preferred over a header-only chunk.
    assert [result["id"] for result in results] == ["implementation", "imports"]


def test_hybrid_search_prefers_new_sources_before_duplicate_chunks():
    # Given: the highest-ranked candidates contain several chunks from the same source.
    chunks = [
        {"id": "a1", "text": "target", "metadata": {"source": "a.py", "node_name": "a1"}},
        {"id": "a2", "text": "target", "metadata": {"source": "a.py", "node_name": "a2"}},
        {"id": "b1", "text": "target", "metadata": {"source": "b.py", "node_name": "b1"}},
        {"id": "b2", "text": "target", "metadata": {"source": "b.py", "node_name": "b2"}},
        {"id": "c1", "text": "target", "metadata": {"source": "c.py", "node_name": "c1"}},
    ]
    indexer = RAGIndexer(project_root="/tmp", vector_store=OrderedVectorStore(chunks))

    # When: hybrid search selects three results.
    results = indexer.search("target", n_results=3, mode="hybrid")

    # Then: each available source contributes before a duplicate is used.
    assert [source_of(result) for result in results] == ["a.py", "b.py", "c.py"]


def test_keyword_search_prefers_more_specific_source_name_when_token_coverage_ties():
    # Given: two sources contain the same query terms but one source name is more specific.
    chunks = [
        {
            "id": "enforcer",
            "text": "context budget compaction",
            "metadata": {"source": "context_budget_enforcer.py", "node_name": "worker"},
        },
        {
            "id": "budget",
            "text": "context budget compaction",
            "metadata": {"source": "context_budget.py", "node_name": "worker"},
        },
    ]
    indexer = RAGIndexer(project_root="/tmp", vector_store=OrderedVectorStore(chunks))

    # When: keyword retrieval scores both candidates.
    results = indexer.search("context budget compaction", n_results=2, mode="keyword")

    # Then: the exact source stem is ranked before its longer sibling.
    assert [result["id"] for result in results] == ["budget", "enforcer"]


def test_hybrid_search_expands_architectural_query_terms_for_dense_retrieval():
    # Given: a hybrid store records every dense query it receives.
    chunks = [
        {"id": "recall", "text": "retrieve restore context", "metadata": {"source": "recall.py"}},
    ]
    store = OrderedVectorStore(chunks)
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    # When: hybrid retrieval searches an architectural query.
    _ = indexer.search("context artifact recall compaction", n_results=1, mode="hybrid")

    # Then: the dense channel receives deterministic retrieval synonyms.
    assert any("retrieve" in query and "compress" in query for query in store.queries)
