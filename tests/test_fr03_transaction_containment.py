"""FR-03 regression: transaction containment and faithful rollback.

Covers:

- traversal / outside-absolute / symlinked targets are rejected at stage time,
  before the original file is read
- path swaps between stage and commit are re-verified before the first write
- Nth-write failure restores originals, keeps originally-empty files present,
  removes newly created files, and leaves unrelated files untouched
- foreign edits during a failing transaction are reported, not overwritten
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from antigravity_k.engine.atomic_transaction_engine import AtomicTransactionEngine
from antigravity_k.tools.tool_path import ToolPathError


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "existing.py").write_text("ORIG\n", encoding="utf-8")
    (proj / "empty.py").write_text("", encoding="utf-8")
    (proj / "unrelated.py").write_text("UNTOUCHED\n", encoding="utf-8")
    return proj


@pytest.fixture()
def outside(tmp_path: Path) -> Path:
    ext = tmp_path / "outside"
    ext.mkdir()
    (ext / "secret.py").write_text("SECRET\n", encoding="utf-8")
    return ext


class TestStageContainment:
    def test_traversal_rejected_before_outside_read(
        self, root: Path, outside: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = AtomicTransactionEngine(root)
        reads: list[str] = []
        real_read = Path.read_text

        def counting_read(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            reads.append(str(self))
            return real_read(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", counting_read)
        with pytest.raises(ToolPathError):
            engine.stage_file_patch(f"../outside/{outside.name}/secret.py", "PWNED\n")
        assert reads == []

    def test_outside_absolute_rejected(self, root: Path, outside: Path) -> None:
        engine = AtomicTransactionEngine(root)
        with pytest.raises(ToolPathError):
            engine.stage_file_patch(str(outside / "secret.py"), "PWNED\n")
        assert (outside / "secret.py").read_text(encoding="utf-8") == "SECRET\n"

    def test_outside_symlink_rejected(self, root: Path, outside: Path) -> None:
        link = root / "linked.py"
        try:
            link.symlink_to(outside / "secret.py")
        except OSError:
            pytest.skip("symlinks unavailable")
        engine = AtomicTransactionEngine(root)
        with pytest.raises(ToolPathError):
            engine.stage_file_patch("linked.py", "PWNED\n")
        assert (outside / "secret.py").read_text(encoding="utf-8") == "SECRET\n"

    def test_new_leaf_via_outside_parent_rejected(self, root: Path, outside: Path) -> None:
        engine = AtomicTransactionEngine(root)
        with pytest.raises(ToolPathError):
            engine.stage_file_patch(f"../outside/{outside.name}/new_file.py", "PWNED\n")
        assert not (outside / "new_file.py").exists()

    def test_new_leaf_via_symlink_parent_rejected(self, root: Path, outside: Path) -> None:
        link = root / "linked-directory"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks unavailable")
        engine = AtomicTransactionEngine(root)
        with pytest.raises(ToolPathError):
            engine.stage_file_patch("linked-directory/new_file.py", "PWNED\n")
        assert not (outside / "new_file.py").exists()


class TestCommitReverification:
    def test_target_swapped_to_symlink_after_stage_is_rejected(self, root: Path, outside: Path) -> None:
        engine = AtomicTransactionEngine(root)
        victim = root / "victim.py"
        victim.write_text("ORIG\n", encoding="utf-8")
        engine.stage_file_patch("victim.py", "NEW\n")

        # Swap the staged target for a symlink pointing outside the root.
        victim.unlink()
        victim.symlink_to(outside / "secret.py")

        res = engine.commit_transaction()
        assert res.committed is False
        assert "target path rejected" in res.error_message
        assert (outside / "secret.py").read_text(encoding="utf-8") == "SECRET\n"

    def test_symlink_swap_after_preflight_cannot_redirect_write(self, root: Path, outside: Path) -> None:
        engine = AtomicTransactionEngine(root)
        victim = root / "victim.py"
        victim.write_text("ORIG\n", encoding="utf-8")
        engine.stage_file_patch("victim.py", "NEW\n")

        real_write = engine._write_content

        def swap_before_write(relative_path: str, content: str) -> None:
            if relative_path == "victim.py":
                victim.unlink()
                victim.symlink_to(outside / "secret.py")
            real_write(relative_path, content)

        with patch.object(engine, "_write_content", swap_before_write):
            res = engine.commit_transaction()

        assert res.committed is False
        assert (outside / "secret.py").read_text(encoding="utf-8") == "SECRET\n"


class TestRollbackFidelity:
    def test_two_file_success(self, root: Path) -> None:
        engine = AtomicTransactionEngine(root)
        engine.stage_file_patch("a.py", "A = 1\n")
        engine.stage_file_patch("b.py", "B = 2\n")
        res = engine.commit_transaction()
        assert res.committed is True
        assert sorted(res.touched_files) == ["a.py", "b.py"]
        assert (root / "a.py").read_text(encoding="utf-8") == "A = 1\n"
        assert (root / "b.py").read_text(encoding="utf-8") == "B = 2\n"

    def _fail_on(self, engine: AtomicTransactionEngine, target_name: str):
        real_write = engine._write_content

        def guarded(relative_path: str, content: str) -> None:
            if Path(relative_path).name == target_name:
                raise OSError("injected write failure")
            real_write(relative_path, content)

        return patch.object(engine, "_write_content", guarded)

    def test_nth_write_failure_restores_all(self, root: Path) -> None:
        engine = AtomicTransactionEngine(root)
        engine.stage_file_patch("existing.py", "CHANGED = 1\n")
        engine.stage_file_patch("newfile.py", "CREATED = 1\n")
        engine.stage_file_patch("empty.py", "filled = True\n")

        with self._fail_on(engine, "newfile.py"):
            res = engine.commit_transaction()

        assert res.committed is False
        assert res.rolled_back_count == 1  # only the file written before the failure
        # Original content restored (existing file).
        assert (root / "existing.py").read_text(encoding="utf-8") == "ORIG\n"
        # Originally-empty file still exists and is empty again.
        assert (root / "empty.py").exists()
        assert (root / "empty.py").read_text(encoding="utf-8") == ""
        # New file removed entirely.
        assert not (root / "newfile.py").exists()
        # Unrelated file untouched.
        assert (root / "unrelated.py").read_text(encoding="utf-8") == "UNTOUCHED\n"

    def test_new_parent_directory_removed_after_write_failure(self, root: Path) -> None:
        engine = AtomicTransactionEngine(root)
        engine.stage_file_patch("created/first.py", "FIRST = 1\n")
        engine.stage_file_patch("boom.py", "x = 1\n")

        with self._fail_on(engine, "boom.py"):
            result = engine.commit_transaction()

        assert result.committed is False
        assert not (root / "created").exists()

    def test_foreign_edit_reported_not_overwritten(self, root: Path) -> None:
        engine = AtomicTransactionEngine(root)
        engine.stage_file_patch("existing.py", "CHANGED\n")
        engine.stage_file_patch("newfile.py", "CREATED\n")

        real_write = engine._write_content

        def guarded(relative_path: str, content: str) -> None:
            if relative_path == "newfile.py":
                # Simulate a concurrent worker rewriting the first file after
                # our write, then fail the transaction on the second file.
                real_write("existing.py", "FOREIGN EDIT\n")
                raise OSError("injected write failure")
            real_write(relative_path, content)

        with patch.object(engine, "_write_content", guarded):
            res = engine.commit_transaction()

        assert res.committed is False
        assert "existing.py" in res.conflicts
        # The foreign change is preserved, not clobbered with our preimage.
        assert (root / "existing.py").read_text(encoding="utf-8") == "FOREIGN EDIT\n"
        assert not (root / "newfile.py").exists()

    def test_mode_preserved_on_rollback(self, root: Path) -> None:
        engine = AtomicTransactionEngine(root)
        target = root / "existing.py"
        os.chmod(target, 0o600)
        engine.stage_file_patch("existing.py", "CHANGED\n")
        engine.stage_file_patch("boom.py", "x = 1\n")

        with self._fail_on(engine, "boom.py"):
            res = engine.commit_transaction()

        assert res.committed is False
        assert (target.stat().st_mode & 0o7777) == 0o600
