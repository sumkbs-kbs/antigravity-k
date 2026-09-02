from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

from antigravity_k.engine.rag_indexer import RAGIndexer


class Chunk(TypedDict, total=False):
    id: str
    text: str
    metadata: dict[str, object]


class PersistentFakeStore:
    def __init__(self, persist_directory: Path, chunks: Sequence[Chunk] | None = None) -> None:
        self.persist_directory: str = str(persist_directory)
        self._chunks: list[Chunk] = list(chunks or [])
        self.upsert_calls: list[list[Chunk]] = []

    def get_stats(self) -> dict[str, object]:
        return {"count": len(self._chunks)}

    def upsert_chunks(self, chunks: Sequence[Chunk]) -> None:
        self.upsert_calls.append(list(chunks))
        self._chunks.extend(chunks)

    def delete_file_chunks(self, source: str) -> None:
        self._chunks = [
            chunk
            for chunk in self._chunks
            if chunk.get("metadata", {}).get("source") != source
        ]

    def get_chunks(self) -> list[Chunk]:
        return list(self._chunks)


def test_index_project_reuses_manifest_for_persistent_store(tmp_path: Path) -> None:
    source = tmp_path / "feature.py"
    _ = source.write_text("def stable():\n    return 1\n", encoding="utf-8")
    vector_dir = tmp_path / "vectors"
    _ = vector_dir.mkdir()

    first_store = PersistentFakeStore(vector_dir)
    first_indexer = RAGIndexer(str(tmp_path), first_store)
    assert first_indexer.index_project() == 1

    second_store = PersistentFakeStore(vector_dir, first_store.get_chunks())
    second_indexer = RAGIndexer(str(tmp_path), second_store)

    assert second_indexer.index_project() == 0
    assert second_store.upsert_calls == []


def test_index_project_batches_upserts_and_reindexes_changed_file(tmp_path: Path) -> None:
    _ = (tmp_path / "one.py").write_text("def one():\n    return 1\n", encoding="utf-8")
    _ = (tmp_path / "two.py").write_text("def two():\n    return 2\n", encoding="utf-8")
    store = PersistentFakeStore(tmp_path / "vectors")
    indexer = RAGIndexer(str(tmp_path), store, batch_size=1)

    assert indexer.index_project() == 2
    assert len(store.upsert_calls) == 2

    store.upsert_calls.clear()
    _ = (tmp_path / "one.py").write_text("def one():\n    return 3\n", encoding="utf-8")

    assert indexer.index_project() == 1
    assert len(store.upsert_calls) == 1


def test_index_project_removes_stale_chunks_when_file_becomes_empty(tmp_path: Path) -> None:
    source = tmp_path / "feature.py"
    _ = source.write_text("def stable():\n    return 1\n", encoding="utf-8")
    store = PersistentFakeStore(tmp_path / "vectors")
    indexer = RAGIndexer(str(tmp_path), store)

    assert indexer.index_project() == 1
    _ = source.write_text("", encoding="utf-8")

    assert indexer.index_project() == 0
    assert store.get_chunks() == []
