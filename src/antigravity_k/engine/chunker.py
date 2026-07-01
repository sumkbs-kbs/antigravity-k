"""Chunker module."""

import re
from typing import Any


class MarkdownChunker:
    """Markdownchunker."""

    def __init__(self, max_chunk_size: int = 1000):
        """Initialize the MarkdownChunker.

        Args:
            max_chunk_size (int): int max chunk size.

        """
        self.max_chunk_size = max_chunk_size

    def chunk_document(
        self,
        file_path: str,
        metadata: dict[str, Any],
        content: str,
    ) -> list[dict[str, Any]]:
        """Split markdown content into chunks based on headers and length.

        Returns a list of chunk dictionaries with metadata.
        """
        chunks = []
        # Split by markdown headers (e.g. ## Header)
        # Using a regex that captures the header to keep it with the content
        parts = re.split(r"(^#{1,6}\s+.*$)", content, flags=re.MULTILINE)

        current_chunk_text = ""
        current_header = ""

        def add_chunk(text, header):
            text = text.strip()
            if not text:
                return

            # If a single chunk is still too large, we could sub-chunk it by paragraphs.
            # For simplicity, we just split by max_chunk_size characters.
            for i in range(0, len(text), self.max_chunk_size):
                sub_text = text[i : i + self.max_chunk_size]
                chunk_meta = metadata.copy()
                chunk_meta.update(
                    {"source": file_path, "header": header, "chunk_index": len(chunks)},
                )
                chunks.append(
                    {
                        "text": (header + "\n" + sub_text).strip() if header and i == 0 else sub_text,
                        "metadata": chunk_meta,
                        "id": f"{file_path}_{len(chunks)}",
                    },
                )

        for part in parts:
            if re.match(r"^#{1,6}\s+", part):
                # Before starting a new header section, flush the old one
                if current_chunk_text:
                    add_chunk(current_chunk_text, current_header)
                current_header = part.strip()
                current_chunk_text = ""
            else:
                current_chunk_text += part

        if current_chunk_text:
            add_chunk(current_chunk_text, current_header)

        return chunks
