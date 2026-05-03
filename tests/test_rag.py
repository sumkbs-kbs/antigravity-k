import pytest
import os
import tempfile
from antigravity_k.engine.chunker import MarkdownChunker
from antigravity_k.engine.vector_store import VectorStore
from antigravity_k.engine.vault import VaultEngine

def test_markdown_chunker():
    chunker = MarkdownChunker(max_chunk_size=100)
    markdown_content = """# First Header
This is a test paragraph under the first header.

## Second Header
Another paragraph under the second header. Let's make it slightly longer.
"""
    chunks = chunker.chunk_document("test.md", {"author": "AI"}, markdown_content)
    
    assert len(chunks) == 2
    assert "First Header" in chunks[0]["text"]
    assert "Second Header" in chunks[1]["text"]
    assert chunks[0]["metadata"]["author"] == "AI"

@pytest.fixture
def temp_chroma():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        yield tmpdir

def test_vector_store(temp_chroma):
    store = VectorStore(persist_directory=temp_chroma, collection_name="test_collection")
    chunks = [
        {"id": "test1_0", "text": "Apple is a fruit", "metadata": {"source": "test1"}},
        {"id": "test1_1", "text": "Banana is also a fruit", "metadata": {"source": "test1"}},
        {"id": "test2_0", "text": "Carrot is a vegetable", "metadata": {"source": "test2"}}
    ]
    
    store.upsert_chunks(chunks)
    
    # Search for fruit
    results = store.search("fruit", n_results=2)
    assert len(results) == 2
    assert "fruit" in results[0]["text"]

    # Test delete
    store.delete_file_chunks("test1")
    results_after_delete = store.search("fruit", n_results=2)
    
    # Only the carrot should remain, even if it's not a fruit, or nothing
    assert len(results_after_delete) == 1
    assert "Carrot" in results_after_delete[0]["text"]

def test_vault_rag_sync():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        vault = VaultEngine(tmpdir, sync_rag=True)
        
        # Write a note
        vault.write_note(
            "fruits.md", 
            {"tags": ["fruit"]}, 
            "# Apples\nApples are sweet and red.\n## Oranges\nOranges are citrus fruits."
        )
        
        # Write another note
        vault.write_note(
            "vegetables.md",
            {"tags": ["veg"]},
            "# Carrots\nCarrots are good for your eyes."
        )
        
        # Search via VectorStore directly
        results = vault.vector_store.search("sweet red", n_results=1)
        assert len(results) == 1
        assert "Apples" in results[0]["text"]
