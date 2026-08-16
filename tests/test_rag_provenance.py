import hashlib

from antigravity_k.engine.rag_indexer import RAGIndexer


class RecordingVectorStore:
    def __init__(self):
        self.chunks = []

    def delete_file_chunks(self, file_path):
        self.chunks = [chunk for chunk in self.chunks if chunk["metadata"].get("source") != file_path]

    def upsert_chunks(self, chunks):
        self.chunks.extend(chunks)

    def search(self, query, n_results=5):
        return [
            {
                "id": chunk["id"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            }
            for chunk in self.chunks[:n_results]
        ]


def test_indexed_chunks_expose_provenance_and_freshness(tmp_path):
    source = tmp_path / "module.py"
    source.write_text("def answer():\n    return 42\n", encoding="utf-8")
    store = RecordingVectorStore()
    indexer = RAGIndexer(project_root=str(tmp_path), vector_store=store)

    assert indexer.index_file("module.py") == 1
    indexed_metadata = store.chunks[0]["metadata"]
    expected_hash = hashlib.md5(source.read_bytes()).hexdigest()
    assert indexed_metadata["source_hash"] == expected_hash
    assert indexed_metadata["source_type"] == "code"
    assert indexed_metadata["indexed_at"]

    result = indexer.search("answer", mode="semantic")[0]
    assert result["provenance"] == {
        "source_id": result["id"],
        "source": "module.py",
        "source_type": "code",
        "node_type": "function",
        "node_name": "answer",
        "start_line": 1,
        "end_line": 2,
        "source_hash": expected_hash,
        "indexed_at": indexed_metadata["indexed_at"],
        "freshness": "fresh",
    }

    source.write_text("def answer():\n    return 43\n", encoding="utf-8")
    stale_result = indexer.search("answer", mode="semantic")[0]
    assert stale_result["provenance"]["freshness"] == "stale"


def test_format_context_exposes_citation_marker():
    store = RecordingVectorStore()
    store.chunks = [
        {
            "id": "abc123",
            "text": "def answer(): pass",
            "metadata": {
                "source": "module.py",
                "source_hash": "hash",
                "source_type": "code",
                "indexed_at": "2026-08-09T00:00:00+00:00",
                "node_type": "function",
                "node_name": "answer",
                "start_line": 1,
                "end_line": 1,
            },
        },
    ]
    indexer = RAGIndexer(project_root="/tmp", vector_store=store)

    context = indexer.format_context("answer")

    assert "[citation:abc123]" in context
    assert "Cite code evidence" in context


def test_validate_citations_rejects_missing_unknown_and_unverified_sources():
    indexer = RAGIndexer(project_root="/tmp")
    fresh_result = {"id": "fresh", "provenance": {"source_id": "fresh", "freshness": "fresh"}}
    stale_result = {"id": "stale", "provenance": {"source_id": "stale", "freshness": "stale"}}

    valid = indexer.validate_citations("Answer [citation:fresh]", [fresh_result])
    missing = indexer.validate_citations("Answer", [fresh_result])
    invalid = indexer.validate_citations("Answer [citation:unknown]", [fresh_result])
    stale = indexer.validate_citations("Answer [citation:stale]", [stale_result])

    assert valid["valid"] is True
    assert missing["missing_citation"] is True
    assert invalid["unknown"] == ["unknown"]
    assert stale["unverified"] == ["stale"]
