from collections.abc import Mapping, Sequence
from typing import cast, final
from unittest.mock import MagicMock

from pydantic import JsonValue

from antigravity_k.engine.long_context_fusion import LongContextFusion, project_doubly_stochastic
from antigravity_k.engine.rag_indexer import RAGIndexer


@final
class RecordingVectorStore:
    def __init__(self, chunks: Sequence[Mapping[str, JsonValue]]) -> None:
        self._chunks: tuple[Mapping[str, JsonValue], ...] = tuple(chunks)
        self.search_limits: list[int] = []

    def search(self, _query: str, n_results: int = 5) -> list[Mapping[str, JsonValue]]:
        self.search_limits.append(n_results)
        return list(self._chunks[:n_results])


def test_long_context_search_keeps_sparse_needle_with_bounded_candidate_pool():
    chunks: list[dict[str, JsonValue]] = [
        {
            "id": f"noise-{index}",
            "text": "generic context",
            "metadata": {"source": f"noise-{index}.py", "node_name": "generic"},
        }
        for index in range(8)
    ]
    chunks.append(
        {
            "id": "needle",
            "text": "critical_marker is the recovery path",
            "metadata": {"source": "recovery.py", "node_name": "CriticalMarker"},
        },
    )
    store = RecordingVectorStore(chunks)
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    results = indexer.search_long_context("critical_marker", n_results=3, candidate_pool=4)

    assert results[0]["id"] == "needle"
    metadata = cast(dict[str, object], results[0]["metadata"])
    assert metadata["retrieval_architecture"] == "sparse_linear_mhc"
    assert max(store.search_limits) <= 4


def test_long_context_search_keeps_source_diversity():
    chunks: list[dict[str, JsonValue]] = [
        {
            "id": f"dominant-{index}",
            "text": "shared target",
            "metadata": {"source": "dominant.py", "node_name": f"target_{index}"},
        }
        for index in range(6)
    ]
    chunks.append(
        {
            "id": "secondary",
            "text": "shared target",
            "metadata": {"source": "secondary.py", "node_name": "target_secondary"},
        },
    )
    store = RecordingVectorStore(chunks)
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    results = indexer.search_long_context("shared target", n_results=4, candidate_pool=7)

    sources = [cast(dict[str, object], result["metadata"])["source"] for result in results]
    assert sources.count("dominant.py") <= 2
    assert "secondary.py" in sources


def test_long_context_search_caps_output_to_candidate_pool():
    chunks: list[dict[str, JsonValue]] = [
        {
            "id": f"chunk-{index}",
            "text": "shared target",
            "metadata": {"source": f"source-{index}.py", "node_name": "target"},
        }
        for index in range(8)
    ]
    store = RecordingVectorStore(chunks)
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    results = indexer.search_long_context("shared target", n_results=8, candidate_pool=4)

    assert len(results) == 4
    assert max(store.search_limits) <= 4


def test_idless_sparse_and_dense_chunks_are_fused_once():
    chunk: dict[str, JsonValue] = {
        "text": "critical marker",
        "metadata": {"source": "recovery.py", "node_name": "recover"},
    }
    fusion = LongContextFusion()

    results = fusion.rank("critical marker", [chunk], [chunk], n_results=2, candidate_pool=4)

    assert len(results) == 1
    metadata = results[0].get("metadata")
    assert isinstance(metadata, dict)
    assert metadata.get("sparse_score") == 1.0
    assert metadata.get("dense_score") == 1.0


def test_duplicate_sparse_chunk_keeps_best_rank_score():
    first: dict[str, JsonValue] = {
        "id": "duplicate",
        "text": "critical marker",
        "metadata": {"source": "recovery.py", "node_name": "recover"},
    }
    second: dict[str, JsonValue] = {
        "id": "duplicate",
        "text": "critical marker",
        "metadata": {"source": "recovery.py", "node_name": "recover"},
    }
    fusion = LongContextFusion()

    results = fusion.rank("critical marker", [first, second], [], n_results=1, candidate_pool=4)

    assert len(results) == 1
    metadata = results[0].get("metadata")
    assert isinstance(metadata, dict)
    assert metadata.get("sparse_score") == 1.0


def test_zero_candidate_pool_returns_no_results():
    chunk: dict[str, JsonValue] = {
        "id": "chunk",
        "text": "critical marker",
        "metadata": {"source": "recovery.py", "node_name": "recover"},
    }
    fusion = LongContextFusion()

    results = fusion.rank("critical marker", [chunk], [chunk], n_results=1, candidate_pool=0)

    assert results == []


def test_format_context_forwards_candidate_pool_to_long_context_search():
    indexer = RAGIndexer(project_root="/tmp")
    indexer.search_long_context = MagicMock(return_value=[])

    _ = indexer.format_context("needle", n_results=3, mode="long_context", candidate_pool=7)

    indexer.search_long_context.assert_called_once_with("needle", n_results=3, candidate_pool=7)


def test_manifold_projection_keeps_rows_and_columns_normalized():
    matrix = project_doubly_stochastic(((3.0, 1.0, 0.5), (0.2, 4.0, 1.0), (1.0, 0.4, 2.0)))

    assert all(abs(sum(row) - 1.0) < 1e-3 for row in matrix)
    assert all(abs(sum(matrix[row][column] for row in range(3)) - 1.0) < 1e-3 for column in range(3))
    assert all(cell >= 0.02 for row in matrix for cell in row)
