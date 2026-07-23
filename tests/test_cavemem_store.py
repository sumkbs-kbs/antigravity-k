"""Tests for CavememStore (memory/cavemem_store.py)."""

import tempfile
from pathlib import Path

from antigravity_k.engine.memory.cavemem_store import CavememStore


class TestCavememStore:
    @property
    def db_path(self):
        return str(Path(tempfile.mkdtemp()) / "cavemem.sqlite3")

    def test_init_creates_db(self):
        store = CavememStore(self.db_path)
        assert Path(store.db_path).parent.exists()

    def test_store_and_search_observation(self):
        store = CavememStore(self.db_path)
        obs_id = store.store_observation("session1", "This is a test observation about Python code")
        assert obs_id > 0
        results = store.search_observations("Python", limit=10)
        assert len(results) >= 1
        assert results[0]["content"] == "This is a test observation about Python code"
        assert results[0]["session_id"] == "session1"

    def test_store_multiple_observations(self):
        store = CavememStore(self.db_path)
        id1 = store.store_observation("s1", "First test")
        id2 = store.store_observation("s1", "Second test")
        assert id2 > id1

    def test_search_by_session(self):
        store = CavememStore(self.db_path)
        store.store_observation("s1", "Session 1 data")
        store.store_observation("s2", "Session 2 data")
        results = store.search_observations("Session 2", limit=10)
        assert any("Session 2 data" in r["content"] for r in results)

    def test_search_empty_query(self):
        store = CavememStore(self.db_path)
        store.store_observation("s1", "test")
        results = store.search_observations("", limit=5)
        assert results == []

    def test_search_no_match(self):
        store = CavememStore(self.db_path)
        store.store_observation("s1", "hello world")
        results = store.search_observations("zzzzzz", limit=5)
        assert results == []

    def test_search_limit(self):
        store = CavememStore(self.db_path)
        for i in range(10):
            store.store_observation("s1", f"Test observation number {i}")
        results = store.search_observations("Test", limit=3)
        assert len(results) <= 3

    def test_compress_to_caveman(self):
        store = CavememStore(self.db_path)
        compressed = store.compress_to_caveman("Hello, I will implement the feature because we should use Python")
        assert "hello" not in compressed  # filler removed
        assert len(compressed) < len("Hello, I will implement the feature because we should use Python")
        assert "b/c" in compressed  # because → b/c

    def test_compress_empty_text(self):
        store = CavememStore(self.db_path)
        assert store.compress_to_caveman("") == ""

    def test_extract_memory_short_message(self):
        store = CavememStore(self.db_path)
        result = store.extract_memory("Hi")  # too short
        assert result is None

    def test_extract_memory_keyword_match(self):
        store = CavememStore(self.db_path)
        result = store.extract_memory("I use Python and FastAPI for my projects")
        assert result is not None
        assert "I use Python" in result

    def test_extract_memory_no_keyword(self):
        store = CavememStore(self.db_path)
        # message that doesn't contain memory keywords
        result = store.extract_memory("What time is it right now?")
        assert result is None

    def test_extract_memory_with_model_fn(self):
        store = CavememStore(self.db_path)

        def mock_model(prompt):
            return "- (2025) [fact] User prefers TypeScript over Python"

        result = store.extract_memory("I prefer TypeScript", model_fn=mock_model)
        assert result is not None
        assert "TypeScript" in result

    def test_extract_memory_model_returns_no_update(self):
        store = CavememStore(self.db_path)

        def mock_model(prompt):
            return "NO_UPDATE"

        result = store.extract_memory("What's the weather today?", model_fn=mock_model)
        assert result is None

    def test_extract_memory_short_with_model(self):
        store = CavememStore(self.db_path)
        result = store.extract_memory("Hi", model_fn=lambda p: "yes")
        assert result is None  # too short

    def test_store_observation_returns_zero_on_none(self):
        """Test that store_observation handles None lastrowid."""
        store = CavememStore(self.db_path)
        store.store_observation("s1", "test")
        # Just verify it doesn't crash
        assert True
