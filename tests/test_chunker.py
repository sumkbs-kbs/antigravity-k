"""Tests for MarkdownChunker — RAG document splitting by headers."""

from __future__ import annotations

from antigravity_k.engine.chunker import MarkdownChunker


class TestMarkdownChunker:
    """MarkdownChunker header-based splitting."""

    def test_empty_content_returns_empty_list(self):
        """Empty content produces no chunks."""
        chunker = MarkdownChunker()
        result = chunker.chunk_document("test.md", {"title": "Test"}, "")
        assert result == []

    def test_single_paragraph_no_headers(self):
        """Content without headers produces one chunk."""
        chunker = MarkdownChunker()
        result = chunker.chunk_document("test.md", {}, "Just some text.")
        assert len(result) == 1
        assert "Just some text." in result[0]["text"]

    def test_split_by_h1_header(self):
        """Content with H1 headers splits into separate chunks."""
        chunker = MarkdownChunker()
        content = "# Section A\nContent A\n# Section B\nContent B"
        result = chunker.chunk_document("test.md", {}, content)
        assert len(result) == 2
        assert "Section A" in result[0]["text"]
        assert "Section B" in result[1]["text"]

    def test_split_by_h2_header(self):
        """Content with H2 headers splits into separate chunks."""
        chunker = MarkdownChunker()
        content = "## Sub A\nText A\n## Sub B\nText B"
        result = chunker.chunk_document("test.md", {}, content)
        assert len(result) == 2

    def test_chunk_ids_are_unique(self):
        """Each chunk gets a unique id."""
        chunker = MarkdownChunker()
        content = "# A\nx\n# B\ny\n# C\nz"
        result = chunker.chunk_document("test.md", {}, content)
        ids = [c["id"] for c in result]
        assert len(ids) == len(set(ids))

    def test_chunk_metadata_contains_source(self):
        """Each chunk metadata includes the source file path."""
        chunker = MarkdownChunker()
        result = chunker.chunk_document("path/to/file.md", {}, "text")
        assert result[0]["metadata"]["source"] == "path/to/file.md"

    def test_chunk_metadata_contains_header(self):
        """Each chunk metadata includes the header it belongs to."""
        chunker = MarkdownChunker()
        content = "# My Header\nbody text"
        result = chunker.chunk_document("test.md", {}, content)
        assert "# My Header" in result[0]["metadata"]["header"]

    def test_chunk_metadata_preserves_input_metadata(self):
        """Input metadata fields are preserved in each chunk."""
        chunker = MarkdownChunker()
        result = chunker.chunk_document("t.md", {"title": "Doc", "tags": ["a"]}, "text")
        assert result[0]["metadata"]["title"] == "Doc"

    def test_chunk_index_increments(self):
        """chunk_index increments from 0 for each chunk."""
        chunker = MarkdownChunker()
        content = "# A\nx\n# B\ny\n# C\nz"
        result = chunker.chunk_document("test.md", {}, content)
        assert result[0]["metadata"]["chunk_index"] == 0
        assert result[1]["metadata"]["chunk_index"] == 1
        assert result[2]["metadata"]["chunk_index"] == 2

    def test_large_chunk_is_sub_chunked(self):
        """A chunk exceeding max_chunk_size is split into sub-chunks."""
        chunker = MarkdownChunker(max_chunk_size=50)
        long_text = "x" * 120
        result = chunker.chunk_document("test.md", {}, long_text)
        assert len(result) >= 2

    def test_custom_max_chunk_size(self):
        """Custom max_chunk_size controls sub-chunking."""
        chunker = MarkdownChunker(max_chunk_size=20)
        text = "a" * 45
        result = chunker.chunk_document("test.md", {}, text)
        # 45 chars / 20 max = ceil(45/20) = 3 sub-chunks
        assert len(result) == 3

    def test_header_prepended_to_first_subchunk(self):
        """The header is prepended to the first sub-chunk of a section."""
        chunker = MarkdownChunker(max_chunk_size=30)
        content = "# Header\n" + "b" * 50
        result = chunker.chunk_document("test.md", {}, content)
        assert "# Header" in result[0]["text"]
        # Subsequent sub-chunks should not repeat the header.
        if len(result) > 1:
            assert "# Header" not in result[1]["text"]
