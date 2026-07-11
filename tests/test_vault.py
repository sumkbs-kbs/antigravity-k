import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from antigravity_k.engine.vault import VaultCommitError, VaultEngine


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
    metadata = {"title": "Test Note", "tags": ["test", "agent"], "version": 1.0}
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
        text=True,
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


# ---------------------------------------------------------------------------
# Concurrency tests — the core regression for the index.lock race.
# These must FAIL on the pre-fix code and PASS after the lock fix.
# ---------------------------------------------------------------------------


def _capture_git_stderr(vault_path, fn):
    """Run ``fn`` while capturing git's stderr across all subprocess calls.

    Wraps ``VaultEngine._auto_commit``-style calls so we can assert git never
    printed an ``index.lock`` error. Returns the concatenated stderr.
    """
    import antigravity_k.engine.vault as vault_mod

    captured: list[str] = []
    real_run = subprocess.run

    def spying_run(*args, **kwargs):
        # Only spy on git invocations; pass through everything else.
        res = real_run(*args, **kwargs)
        if args and isinstance(args[0], list) and args[0][:1] == ["git"]:
            captured.append(res.stderr or "")
        return res

    original = vault_mod.subprocess.run
    vault_mod.subprocess.run = spying_run
    try:
        fn()
    finally:
        vault_mod.subprocess.run = original
    return "\n".join(captured)


def test_concurrent_writes_are_serialized(vault_engine):
    """50 concurrent writes from 8 threads must all land on disk and in git log."""
    n = 50

    def write_one(i):
        vault_engine.write_note(
            f"notes/note_{i:03d}.md",
            {"title": f"Note {i}", "tags": ["concurrent"]},
            f"# Note {i}\nbody content {i}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_one, range(n)))

    # Every note file must exist on disk.
    for i in range(n):
        rel = f"notes/note_{i:03d}.md"
        assert (vault_engine.vault_path / rel).exists(), f"missing on disk: {rel}"

    # Git log must contain n commits (one per write). Count non-empty lines.
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=vault_engine.vault_path,
        capture_output=True,
        text=True,
    )
    commit_lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(commit_lines) == n, f"expected {n} commits, got {len(commit_lines)}"


def test_concurrent_writes_no_index_lock_error(vault_engine):
    """During concurrent writes, git stderr must never mention index.lock."""
    n = 30

    def write_one(i):
        vault_engine.write_note(
            f"lock/note_{i:03d}.md",
            {"title": f"Lock {i}"},
            f"body {i}",
        )

    def run_all():
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write_one, range(n)))

    stderr = _capture_git_stderr(vault_engine.vault_path, run_all)
    assert "index.lock" not in stderr.lower(), f"git hit index.lock contention under concurrent writes:\n{stderr}"


# ---------------------------------------------------------------------------
# Path traversal / absolute path defense
# ---------------------------------------------------------------------------


def test_path_traversal_blocked(vault_engine):
    """A ``..`` traversal target must be rejected, not written outside the vault."""
    with pytest.raises(ValueError):
        vault_engine.write_note("../../etc/agk_payload.md", {"title": "x"}, "pwn")

    # read_note must also reject traversal.
    with pytest.raises(ValueError):
        vault_engine.read_note("../../etc/agk_payload.md")


def test_absolute_path_blocked(vault_engine):
    """An absolute path must be rejected regardless of where it points."""
    with pytest.raises(ValueError):
        vault_engine.write_note("/tmp/agk_abs.md", {"title": "x"}, "pwn")


# ---------------------------------------------------------------------------
# YAML frontmatter parsing hardening
# ---------------------------------------------------------------------------


def test_malformed_yaml_does_not_leak_into_body(vault_engine):
    """Malformed frontmatter must not appear as body content; metadata = {}."""
    # Tabs are invalid in YAML indentation and will raise a YAMLError.
    raw = "---\n\tbad: indent\n---\n# Real body\n"
    metadata, body = vault_engine.parse_markdown(raw)
    assert metadata == {}
    assert "Real body" in body
    assert "bad: indent" not in body, "malformed YAML must not leak into body"


def test_yaml_list_frontmatter_normalized(vault_engine):
    """A frontmatter that parses to a list must be normalized to {} (not crash)."""
    raw = "---\n- a\n- b\n---\nbody text\n"
    metadata, body = vault_engine.parse_markdown(raw)
    # Must be a dict so downstream .get() calls don't raise AttributeError.
    assert isinstance(metadata, dict)
    assert metadata == {}
    assert "body text" in body


def test_frontmatter_with_horizontal_rule_in_body(vault_engine):
    """A ``---`` horizontal rule in the body must not corrupt parsing."""
    raw = "---\ntitle: Hello\n---\nIntro\n\n---\n\nMore after rule\n"
    metadata, body = vault_engine.parse_markdown(raw)
    assert metadata.get("title") == "Hello"
    assert "Intro" in body
    assert "More after rule" in body


# ---------------------------------------------------------------------------
# Commit failure propagation
# ---------------------------------------------------------------------------


def test_write_failure_propagates(vault_engine, monkeypatch):
    """If the git commit step fails, VaultCommitError must propagate."""
    # Write one valid note first so the repo has a baseline.
    vault_engine.write_note("base.md", {"title": "base"}, "base body")

    # Patch _auto_commit to always raise, simulating a git failure.
    def boom(file_path, message="x"):
        raise VaultCommitError("simulated git failure")

    monkeypatch.setattr(vault_engine, "_auto_commit", boom)

    with pytest.raises(VaultCommitError):
        vault_engine.write_note("boom.md", {"title": "boom"}, "boom body")
