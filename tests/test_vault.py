import pytest
import os
from pathlib import Path
import tempfile
import yaml
from antigravity_k.engine.vault import VaultEngine
import subprocess

@pytest.fixture
def vault_engine():
    # Use a temporary directory for testing the vault
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = VaultEngine(tmpdir)
        yield engine

def test_vault_initialization(vault_engine):
    """Test if vault engine initializes git repo."""
    git_dir = vault_engine.vault_path / ".git"
    assert git_dir.exists(), ".git directory should be created"

def test_write_and_read_note(vault_engine):
    """Test writing a markdown file with frontmatter and reading it back."""
    metadata = {
        "title": "Test Note",
        "tags": ["test", "agent"],
        "version": 1.0
    }
    content = "# Hello World\nThis is a test note."
    
    vault_engine.write_note("test_note.md", metadata, content)
    
    # Read it back
    read_meta, read_content = vault_engine.read_note("test_note.md")
    
    assert read_meta["title"] == "Test Note"
    assert "test" in read_meta["tags"]
    assert "Hello World" in read_content

def test_git_auto_commit(vault_engine):
    """Test if git auto-commit works correctly after writing a note."""
    metadata = {"title": "Commit Test"}
    content = "Test content"
    
    vault_engine.write_note("folder/commit_test.md", metadata, content, commit_message="Add commit test")
    
    # Verify git log
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=vault_engine.vault_path,
        capture_output=True,
        text=True
    )
    
    assert "Add commit test" in result.stdout

def test_search_notes(vault_engine):
    """Test text search across notes."""
    vault_engine.write_note("file1.md", {"title": "One"}, "Apple banana orange")
    vault_engine.write_note("file2.md", {"title": "Two"}, "Grape banana mango")
    
    results = vault_engine.search_notes("banana")
    assert len(results) == 2
    assert any("file1.md" in res for res in results)
    assert any("file2.md" in res for res in results)
    
    results2 = vault_engine.search_notes("apple")
    assert len(results2) == 1
    assert "file1.md" in results2[0]
