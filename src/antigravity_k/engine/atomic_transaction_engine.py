"""Multi-File Atomic Transaction Engine — ACID code transactional safety.

When a 27B model modifies 5+ files during a refactor, a failure on the 4th file
can leave the workspace in a broken, uncompilable intermediate state.

This engine executes multi-file patches inside an atomic transaction:
- Pre-mutation backup snapshot
- Atomic verification (AST + Static Type + TDD) across ALL touched files
- Zero-residue rollback on ANY verification failure
- Atomic commit on 100% clean verification

Containment contract (FR-03/RP-03): every staged path is resolved against the
canonical project root before the original is read, all targets are re-verified
before the first write, and rollback restores exactly the staged preimage —
an originally-empty file is restored as an empty file, only newly created
files are removed, and files changed by someone else mid-transaction are
reported as conflicts instead of being overwritten.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from antigravity_k.engine.code_verifier import DeterministicCodeVerifier
from antigravity_k.tools.tool_path import ToolPathError, resolve_tool_path

logger = logging.getLogger(__name__)


@dataclass
class FilePatchOp:
    """A discrete file modification operation in a transaction."""

    file_path: str
    original_content: str
    new_content: str
    original_existed: bool = True
    original_mode: int | None = None
    target_path: str = ""


@dataclass
class TransactionResult:
    """Outcome of an atomic multi-file transaction."""

    committed: bool
    touched_files: list[str]
    error_message: str = ""
    rolled_back_count: int = 0
    conflicts: list[str] = field(default_factory=list)


class AtomicTransactionEngine:
    """Manages transactional safety for multi-file modifications."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root: Path = Path(project_root).resolve()
        try:
            root_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        except AttributeError as exc:
            raise ToolPathError("Atomic transactions require no-follow directory descriptors") from exc
        self._root_fd: int = os.open(self.project_root, root_flags)
        self._active_ops: list[FilePatchOp] = []
        self._created_directories: list[str] = []

    def __del__(self) -> None:
        try:
            os.close(self._root_fd)
        except OSError:
            pass

    def _resolve_target(self, rel_path: str) -> Path:
        """Resolve a staged path to a canonical in-root absolute path.

        Raises ToolPathError for traversal, outside absolute paths, symlinks
        resolving outside the root, or leaf paths whose existing parents leave
        the root.
        """
        return Path(resolve_tool_path(rel_path, str(self.project_root)))

    def _relative_target(self, target: Path) -> str:
        return str(target.relative_to(self.project_root))

    def _open_parent(self, relative_path: str, *, create: bool) -> tuple[int, str]:
        parts = Path(relative_path).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise ToolPathError("Transaction target is not a file", raw_path=relative_path)

        parent_fd = os.dup(self._root_fd)
        try:
            for part in parts[:-1]:
                try:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, dir_fd=parent_fd)
                    except FileExistsError:
                        pass
                    else:
                        self._created_directories.append(str(Path(*parts[: len(self._created_directories) + 1])))
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                os.close(parent_fd)
                parent_fd = next_fd
            return parent_fd, parts[-1]
        except OSError:
            os.close(parent_fd)
            raise

    def _read_content(self, relative_path: str) -> tuple[bool, str, int | None]:
        try:
            parent_fd, leaf = self._open_parent(relative_path, create=False)
        except FileNotFoundError:
            return False, "", None
        try:
            try:
                file_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
            except FileNotFoundError:
                return False, "", None
            with os.fdopen(file_fd, "r", encoding="utf-8") as file_handle:
                mode = os.fstat(file_handle.fileno()).st_mode & 0o7777
                return True, file_handle.read(), mode
        finally:
            os.close(parent_fd)

    def _write_content(self, relative_path: str, content: str) -> None:
        parent_fd, leaf = self._open_parent(relative_path, create=True)
        try:
            file_fd = os.open(
                leaf,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
            with os.fdopen(file_fd, "w", encoding="utf-8") as file_handle:
                _ = file_handle.write(content)
        finally:
            os.close(parent_fd)

    def _remove_new_file(self, relative_path: str) -> None:
        parent_fd, leaf = self._open_parent(relative_path, create=False)
        try:
            os.unlink(leaf, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)

    def _restore_mode(self, relative_path: str, mode: int) -> None:
        parent_fd, leaf = self._open_parent(relative_path, create=False)
        try:
            file_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                os.fchmod(file_fd, mode)
            finally:
                os.close(file_fd)
        finally:
            os.close(parent_fd)

    def _cleanup_created_directories(self) -> None:
        for relative_path in reversed(self._created_directories):
            try:
                parent_fd, leaf = self._open_parent(relative_path, create=False)
                try:
                    os.rmdir(leaf, dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
            except OSError:
                pass
        self._created_directories.clear()

    def stage_file_patch(self, rel_path: str, new_content: str) -> None:
        """Stage a file modification in the current transaction.

        Containment is checked BEFORE the original file is read so a hostile
        path can never be used to exfiltrate or register outside content.
        """
        full_p = self._resolve_target(rel_path)
        target_path = self._relative_target(full_p)
        try:
            existed, original, mode = self._read_content(target_path)
        except OSError as exc:
            raise ToolPathError(f"Transaction target cannot be opened safely: {rel_path}") from exc
        self._active_ops.append(
            FilePatchOp(
                file_path=rel_path,
                original_content=original,
                new_content=new_content,
                original_existed=existed,
                original_mode=mode,
                target_path=target_path,
            )
        )

    def commit_transaction(self) -> TransactionResult:
        """Verify all staged files and atomically commit or rollback."""
        if not self._active_ops:
            return TransactionResult(committed=True, touched_files=[])

        # Step 1: Pre-flight syntax validation on all staged content, plus a
        # containment re-check of every target before the first write. The
        # re-check narrows (not eliminates) symlink-swap races between stage
        # and commit; full no-follow write boundaries are a platform feature.
        targets: list[Path] = []
        for op in self._active_ops:
            syntax_res = DeterministicCodeVerifier.verify_file(op.file_path, content=op.new_content)
            if not syntax_res.is_valid:
                self._active_ops.clear()
                return TransactionResult(
                    committed=False,
                    touched_files=[],
                    error_message=f"Transaction aborted: Syntax error in staged `{op.file_path}`: {syntax_res.error_message}",
                )
            try:
                target = self._resolve_target(op.file_path)
            except ToolPathError as exc:
                self._active_ops.clear()
                return TransactionResult(
                    committed=False,
                    touched_files=[],
                    error_message=f"Transaction aborted: target path rejected for `{op.file_path}`: {exc}",
                )
            if self._relative_target(target) != op.target_path:
                self._active_ops.clear()
                return TransactionResult(
                    committed=False,
                    touched_files=[],
                    error_message=f"Transaction aborted: target path changed for `{op.file_path}`",
                )
            targets.append(target)

        # Step 2: Apply changes to disk
        written: list[tuple[FilePatchOp, Path]] = []
        try:
            for op, full_p in zip(self._active_ops, targets):
                self._write_content(op.target_path, op.new_content)
                written.append((op, full_p))

            # Transaction successful
            committed_files = [op.file_path for op in self._active_ops]
            self._active_ops.clear()
            self._created_directories.clear()
            return TransactionResult(committed=True, touched_files=committed_files)

        except OSError as ex:
            # Step 3: Rollback on any I/O or filesystem error.
            rolled, conflicts = self._rollback_written(written)
            self._cleanup_created_directories()
            self._active_ops.clear()
            message = f"Transaction rolled back due to error: {ex}"
            if conflicts:
                message += f"; conflicting external changes preserved on: {', '.join(conflicts)}"
            return TransactionResult(
                committed=False,
                touched_files=[],
                error_message=message,
                rolled_back_count=rolled,
                conflicts=conflicts,
            )

    def _rollback_written(self, written: list[tuple[FilePatchOp, Path]]) -> tuple[int, list[str]]:
        """Restore staged preimages; report — never overwrite — foreign edits."""
        rolled = 0
        conflicts: list[str] = []
        for op, full_p in reversed(written):
            try:
                if op.original_existed:
                    exists, current_content, _ = self._read_content(op.target_path)
                    if not exists or current_content != op.new_content:
                        # Someone else rewrote the file after our write: keep
                        # their version and surface the conflict.
                        conflicts.append(op.file_path)
                        continue
                    # Restore content — including originally-empty files.
                    self._write_content(op.target_path, op.original_content)
                    if op.original_mode is not None:
                        self._restore_mode(op.target_path, op.original_mode)
                else:
                    exists, current_content, _ = self._read_content(op.target_path)
                    if exists and current_content != op.new_content:
                        conflicts.append(op.file_path)
                        continue
                    if exists:
                        self._remove_new_file(op.target_path)
                rolled += 1
            except OSError as restore_exc:
                logger.error("rollback restore failed for %s: %s", full_p, restore_exc)
                conflicts.append(op.file_path)
        return rolled, conflicts
