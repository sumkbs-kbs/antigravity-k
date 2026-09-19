from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from subprocess import CompletedProcess
from typing import cast

import pytest

from antigravity_k.engine.vault import VaultCommitError, VaultEngine


@pytest.fixture
def vault_engine() -> Iterator[VaultEngine]:
    # Use a temporary directory for testing the vault
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = VaultEngine(tmpdir, sync_rag=False)
        yield engine


def test_vault_initialization(vault_engine: VaultEngine):
    """Test if vault engine initializes git repo."""
    git_dir = vault_engine.vault_path / ".git"
    assert git_dir.exists(), ".git directory should be created"


def test_write_and_read_note(vault_engine: VaultEngine):
    """Test writing a markdown file with frontmatter and reading it back."""
    metadata = {"title": "Test Note", "tags": ["test", "agent"], "version": 1.0}
    content = "# Hello World\nThis is a test note."

    vault_engine.write_note("test_note.md", metadata, content)

    # Read it back
    read_meta, read_content = vault_engine.read_note("test_note.md")

    assert read_meta["title"] == "Test Note"
    assert "test" in read_meta["tags"]
    assert "Hello World" in read_content


def test_git_auto_commit(vault_engine: VaultEngine):
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


def _git_status(engine: VaultEngine) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=engine.vault_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def _committed_paths(engine: VaultEngine) -> list[str]:
    result = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=engine.vault_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def test_write_note_preserves_unrelated_staged_file(vault_engine: VaultEngine) -> None:
    vault_engine.write_note("base.md", {"title": "base"}, "base body")
    unrelated = vault_engine.vault_path / "unrelated.md"
    _ = unrelated.write_text("user staged change", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.md"], cwd=vault_engine.vault_path, check=True)

    vault_engine.write_note("folder/note.md", {"title": "note"}, "note body")

    assert _committed_paths(vault_engine) == ["folder/note.md"]
    assert _git_status(vault_engine) == ["A  unrelated.md"]
    assert not (vault_engine.vault_path / ".git" / "agk-vault-index").exists()
    assert not (vault_engine.vault_path / ".git" / "agk-vault-index-backup").exists()


def test_write_note_preserves_existing_note_staged_and_unstaged_state(vault_engine: VaultEngine) -> None:
    vault_engine.write_note("note.md", {"title": "base"}, "base body")
    note = vault_engine.vault_path / "note.md"
    _ = note.write_text("---\ntitle: staged\n---\nstaged body\n", encoding="utf-8")
    subprocess.run(["git", "add", "note.md"], cwd=vault_engine.vault_path, check=True)
    _ = note.write_text("---\ntitle: unstaged\n---\nstaged and unstaged body\n", encoding="utf-8")

    vault_engine.write_note("unrelated.md", {"title": "other"}, "other body")

    assert _committed_paths(vault_engine) == ["unrelated.md"]
    assert _git_status(vault_engine) == ["MM note.md"]


def test_identical_write_does_not_create_commit(vault_engine: VaultEngine) -> None:
    metadata = {"title": "same"}
    vault_engine.write_note("note.md", metadata, "same body")
    before = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=vault_engine.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    vault_engine.write_note("note.md", metadata, "same body")

    after = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=vault_engine.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert after == before


def test_failed_hook_preserves_file_user_index_and_head(vault_engine: VaultEngine) -> None:
    vault_engine.write_note("base.md", {"title": "base"}, "base body")
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault_engine.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    unrelated = vault_engine.vault_path / "unrelated.md"
    _ = unrelated.write_text("user staged change", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.md"], cwd=vault_engine.vault_path, check=True)
    hook = vault_engine.vault_path / ".git" / "hooks" / "pre-commit"
    _ = hook.write_text("#!/bin/sh\necho 'hook rejected note' >&2\nexit 17\n", encoding="utf-8")
    _ = hook.chmod(0o755)

    with pytest.raises(VaultCommitError, match="hook rejected note"):
        vault_engine.write_note("failed.md", {"title": "failed"}, "failed body")

    assert (vault_engine.vault_path / "failed.md").exists()
    assert _git_status(vault_engine) == ["A  unrelated.md", "?? failed.md"]
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=vault_engine.vault_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == head_before
    )
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\necho 'hook rejected note' >&2\nexit 17\n"


def test_search_notes(vault_engine: VaultEngine):
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


def _capture_git_stderr(_vault_path: object, fn: Callable[[], None]) -> str:
    """Run ``fn`` while capturing git's stderr across all subprocess calls.

    Wraps ``VaultEngine._auto_commit``-style calls so we can assert git never
    printed an ``index.lock`` error. Returns the concatenated stderr.
    """
    captured: list[str] = []
    real_run = cast(Callable[..., CompletedProcess[str]], subprocess.run)

    def spying_run(*args: object, **kwargs: object) -> CompletedProcess[str]:
        # Only spy on git invocations; pass through everything else.
        res = real_run(*args, **kwargs)
        if args and isinstance(args[0], list) and args[0][:1] == ["git"]:
            captured.append(res.stderr or "")
        return res

    original = subprocess.run
    subprocess.run = spying_run
    try:
        fn()
    finally:
        subprocess.run = original
    return "\n".join(captured)


def test_concurrent_writes_are_serialized(vault_engine: VaultEngine):
    """50 concurrent writes from 8 threads must all land on disk and in git log."""
    n = 50

    def write_one(i: int) -> None:
        vault_engine.write_note(
            f"notes/note_{i:03d}.md",
            {"title": f"Note {i}", "tags": ["concurrent"]},
            f"# Note {i}\nbody content {i}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        _ = list(pool.map(write_one, range(n)))

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


def test_concurrent_writes_no_index_lock_error(vault_engine: VaultEngine):
    """During concurrent writes, git stderr must never mention index.lock."""
    n = 30

    def write_one(i: int) -> None:
        vault_engine.write_note(
            f"lock/note_{i:03d}.md",
            {"title": f"Lock {i}"},
            f"body {i}",
        )

    def run_all() -> None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            _ = list(pool.map(write_one, range(n)))

    stderr = _capture_git_stderr(vault_engine.vault_path, run_all)
    assert "index.lock" not in stderr.lower(), f"git hit index.lock contention under concurrent writes:\n{stderr}"


def _process_write(vault_path: str, index: int) -> tuple[str, list[str]]:
    engine = VaultEngine(vault_path, sync_rag=False)
    relative_path = f"process-{index}.md"
    engine.write_note(relative_path, {"title": f"process {index}"}, f"process body {index}")
    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=engine.vault_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return relative_path, committed


def test_process_writes_commit_one_note_each(vault_engine: VaultEngine) -> None:
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_process_write, [str(vault_engine.vault_path)] * 4, range(4)))

    assert [relative_path for relative_path, _ in results] == [
        "process-0.md",
        "process-1.md",
        "process-2.md",
        "process-3.md",
    ]
    for _, committed in results:
        assert len(committed) == 1
        assert committed[0].startswith("process-")


# ---------------------------------------------------------------------------
# Path traversal / absolute path defense
# ---------------------------------------------------------------------------


def test_path_traversal_blocked(vault_engine: VaultEngine):
    """A ``..`` traversal target must be rejected, not written outside the vault."""
    with pytest.raises(ValueError):
        vault_engine.write_note("../../etc/agk_payload.md", {"title": "x"}, "pwn")

    # read_note must also reject traversal.
    with pytest.raises(ValueError):
        _ = vault_engine.read_note("../../etc/agk_payload.md")


def test_absolute_path_blocked(vault_engine: VaultEngine):
    """An absolute path must be rejected regardless of where it points."""
    with pytest.raises(ValueError):
        vault_engine.write_note("/tmp/agk_abs.md", {"title": "x"}, "pwn")


# ---------------------------------------------------------------------------
# YAML frontmatter parsing hardening
# ---------------------------------------------------------------------------


def test_malformed_yaml_does_not_leak_into_body(vault_engine: VaultEngine):
    """Malformed frontmatter must not appear as body content; metadata = {}."""
    # Tabs are invalid in YAML indentation and will raise a YAMLError.
    raw = "---\n\tbad: indent\n---\n# Real body\n"
    metadata, body = vault_engine.parse_markdown(raw)
    assert metadata == {}
    assert "Real body" in body
    assert "bad: indent" not in body, "malformed YAML must not leak into body"


def test_yaml_list_frontmatter_normalized(vault_engine: VaultEngine):
    """A frontmatter that parses to a list must be normalized to {} (not crash)."""
    raw = "---\n- a\n- b\n---\nbody text\n"
    metadata, body = vault_engine.parse_markdown(raw)
    # Must be a dict so downstream .get() calls don't raise AttributeError.
    assert isinstance(metadata, dict)
    assert metadata == {}
    assert "body text" in body


def test_frontmatter_with_horizontal_rule_in_body(vault_engine: VaultEngine):
    """A ``---`` horizontal rule in the body must not corrupt parsing."""
    raw = "---\ntitle: Hello\n---\nIntro\n\n---\n\nMore after rule\n"
    metadata, body = vault_engine.parse_markdown(raw)
    assert metadata.get("title") == "Hello"
    assert "Intro" in body
    assert "More after rule" in body


# ---------------------------------------------------------------------------
# Commit failure propagation
# ---------------------------------------------------------------------------


def test_write_failure_propagates(vault_engine: VaultEngine, monkeypatch: pytest.MonkeyPatch):
    """If the git commit step fails, VaultCommitError must propagate."""
    # Write one valid note first so the repo has a baseline.
    vault_engine.write_note("base.md", {"title": "base"}, "base body")

    # Patch _auto_commit to always raise, simulating a git failure.
    def boom(_file_path: str, _message: str = "x") -> None:
        raise VaultCommitError("simulated git failure")

    monkeypatch.setattr(vault_engine, "_auto_commit", boom)

    with pytest.raises(VaultCommitError):
        vault_engine.write_note("boom.md", {"title": "boom"}, "boom body")
