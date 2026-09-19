from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast, final

from antigravity_k.engine.rag_indexer import RAGIndexer


class _Metadata(TypedDict):
    source: str


class _Chunk(TypedDict):
    metadata: _Metadata


@final
class _Store:
    def __init__(self, persist_directory: Path) -> None:
        self.persist_directory: str = str(persist_directory)
        self.chunks: list[_Chunk] = []

    def get_stats(self) -> dict[str, int]:
        return {"count": len(self.chunks)}

    def upsert_chunks(self, chunks: list[dict[str, object]]) -> None:
        for chunk in chunks:
            metadata = chunk.get("metadata")
            if not isinstance(metadata, dict):
                continue
            typed_metadata = cast(dict[str, object], metadata)
            source = typed_metadata.get("source")
            if isinstance(source, str):
                self.chunks.append({"metadata": {"source": source}})

    def delete_file_chunks(self, source: str) -> None:
        self.chunks = [chunk for chunk in self.chunks if chunk["metadata"]["source"] != source]


def test_subdir_sync_does_not_delete_chunks_outside_scope(tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    inside_dir = tmp_path / "inside"
    inside_dir.mkdir()
    inside = inside_dir / "inside.py"
    _ = outside.write_text("def outside():\n    return 1\n", encoding="utf-8")
    _ = inside.write_text("def inside():\n    return 1\n", encoding="utf-8")

    store = _Store(tmp_path / "vectors")
    indexer = RAGIndexer(str(tmp_path), store)
    assert indexer.index_project() == 2

    outside.unlink()
    _ = indexer.sync(["inside"])

    sources = {chunk["metadata"]["source"] for chunk in store.chunks}
    assert "outside.py" in sources
    assert "inside/inside.py" in sources
