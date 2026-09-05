"""Git-first markdown vault with concurrent-safe writes, RAG sync, and YAML frontmatter parsing."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, cast, final, overload, override

import yaml
from filelock import SoftFileLock

# RAG Imports
from antigravity_k.engine.chunker import MarkdownChunker
from antigravity_k.engine.event_bus import global_event_bus
from antigravity_k.engine.vault_git import VaultCommitError, commit_output, vault_stage_transaction
from antigravity_k.engine.vector_store import VectorStore

if TYPE_CHECKING:
    from antigravity_k.engine.vault_privacy_contracts import VaultPrivacyMutation, VaultPrivacyResult

logger = logging.getLogger(__name__)


class JSONMetadata(dict[str, object]):
    @overload
    def __getitem__(self, key: Literal["title"]) -> str: ...

    @overload
    def __getitem__(self, key: Literal["tags"]) -> list[str]: ...

    @overload
    def __getitem__(self, key: str) -> object: ...

    @override
    def __getitem__(self, key: str) -> object:
        return super().__getitem__(key)


class JSONExportRecord(dict[str, object]):
    @overload
    def __getitem__(self, key: Literal["content"]) -> str: ...

    @overload
    def __getitem__(self, key: Literal["path"]) -> str: ...

    @overload
    def __getitem__(self, key: str) -> object: ...

    @override
    def __getitem__(self, key: str) -> object:
        return super().__getitem__(key)


def _error_text(value: object) -> str:
    return value if isinstance(value, str) else str(value)


# YAML frontmatter delimiter: a line that is exactly "---" (optionally with
# trailing whitespace). Used to split frontmatter from body precisely, instead
# of the previous naive str.split("---\n", 2) which mis-split horizontal rules.
_FRONTMATTER_DELIMITER = re.compile(r"^---[ \t]*$", re.MULTILINE)


@final
class VaultEngine:
    """Git-first markdown vault with concurrent-safe writes.

    Concurrency model
    -----------------
    Writes are guarded by two layers:
      1. ``self._lock`` (``threading.RLock``) — serializes access *within* one
         process (async request handlers sharing one engine instance).
      2. ``self._file_lock`` (``filelock.SoftFileLock``) — serializes access
         *across* processes (multiple uvicorn workers each holding their own
         ``VaultEngine``). The lock file lives inside ``.git`` so it is
         co-located with the index it protects.

    Together these prevent the ``.git/index.lock`` race where two concurrent
    ``write_note`` calls could interleave ``git add`` + ``git commit`` and have
    one commit silently fail.
    """

    def __init__(self, vault_path: str, sync_rag: bool = True):
        """Initialize the VaultEngine.

        Args:
            vault_path (str): Absolute or relative path to the vault directory.
            sync_rag (bool): When True, index note contents into a local
                VectorStore for semantic retrieval.

        """
        self.vault_path: Path = Path(vault_path).resolve()
        # In-process lock (re-entrant so internal helpers may re-enter).
        self._lock: threading.RLock = threading.RLock()
        # Cross-process lock. Placed inside .git so it is co-located with the
        # index it guards; created alongside the repo in _ensure_git_repo.
        self._lock_file: Path = self.vault_path / ".git" / ".agk_vault.lock"
        self._file_lock: SoftFileLock = SoftFileLock(str(self._lock_file), timeout=30)
        self._ensure_git_repo()

        self.sync_rag = sync_rag
        if self.sync_rag:
            chroma_path = self.vault_path / ".chroma"
            chroma_path.mkdir(parents=True, exist_ok=True)
            self.vector_store: VectorStore = VectorStore(str(chroma_path))
            self.chunker: MarkdownChunker = MarkdownChunker()

    @contextmanager
    def _acquire_vault_lock(self) -> Generator[None, None, None]:
        """Acquire both the in-process and cross-process locks.

        The threading lock is taken first (cheap) to serialize threads within
        this process, then the file lock to serialize across worker processes.
        ``SoftFileLock`` raises ``Timeout`` if it cannot acquire within the
        configured timeout; we let that propagate so the API layer can map it
        to a 503.
        """
        with self._lock:
            with self._file_lock:
                yield

    def _safe_resolve(self, relative_path: str) -> Path:
        """Resolve ``relative_path`` against the vault and guard against traversal.

        Rejects paths that escape the vault via ``..``, absolute paths, or
        symlink redirection. Returns the resolved absolute Path on success and
        raises ``ValueError`` otherwise.

        Args:
            relative_path (str): Caller-supplied path, expected to be relative
                to the vault root.

        Returns:
            Path: The resolved absolute path, guaranteed to be inside the vault.

        Raises:
            ValueError: If the path is absolute, escapes the vault, or resolves
                outside the vault via symlinks.

        """
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError(f"Absolute paths are not allowed: {relative_path}")

        resolved = (self.vault_path / candidate).resolve()
        try:
            _ = resolved.relative_to(self.vault_path)
        except ValueError as exc:
            raise ValueError(f"Path '{relative_path}' escapes the vault root {self.vault_path}") from exc
        return resolved

    def _ensure_git_repo(self):
        """Ensure the vault directory exists and is a git repository.

        Holds the in-process lock so two concurrent first-writers in the same
        process do not both invoke ``git init``. The on-disk ``.git`` existence
        check is the guard for the cross-process case.
        """
        with self._lock:
            _ = self.vault_path.mkdir(parents=True, exist_ok=True)
            git_dir = self.vault_path / ".git"
            if not git_dir.exists():
                try:
                    _ = subprocess.run(
                        ["git", "init"],
                        cwd=self.vault_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.info("Initialized Git repository at %s", self.vault_path)
                except subprocess.CalledProcessError as e:
                    logger.error("Failed to initialize Git repo: %s", _error_text(cast(object, e.stderr)))

    def _auto_commit(self, file_path: str, message: str = "Auto-commit via VaultEngine"):
        with vault_stage_transaction(self.vault_path, file_path) as commit_env:
            try:
                result = subprocess.run(
                    ["git", "commit", "--only", file_path, "-m", message],
                    cwd=self.vault_path,
                    env=commit_env,
                    capture_output=True,
                    text=True,
                )
            except OSError as e:
                raise VaultCommitError(f"git commit failed for {file_path}: {e}") from e
        if result.returncode == 0:
            logger.info("Git commit successful: %s", message)
            if commit_env is not None:
                try:
                    _ = subprocess.run(
                        ["git", "add", file_path],
                        cwd=self.vault_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    output = _error_text(cast(object, e.stderr))
                    raise VaultCommitError(f"git add failed for {file_path}: {output}") from e
            return
        output = commit_output(result)
        if "nothing to commit" in output or "no changes added" in output:
            logger.debug("Nothing to commit for %s (no-op)", file_path)
            return
        logger.error("Git commit failed for %s (exit %d): %s", file_path, result.returncode, output)
        raise VaultCommitError(
            f"git commit failed for {file_path} (exit {result.returncode}): {output}",
        )

    def create_snapshot(self, message: str) -> str | None:
        """Create a filesystem checkpoint (snapshot) by committing all current changes.

        Acquires the full two-layer vault lock so concurrent writers cannot
        interleave with the ``git add .`` / ``git commit`` sequence.

        Returns:
            The new commit hash on success, or None if there was nothing to
            commit (a clean tree) or the commit failed.

        """
        with self._acquire_vault_lock():
            try:
                _ = subprocess.run(
                    ["git", "add", "."],
                    cwd=self.vault_path,
                    check=True,
                    capture_output=True,
                )
                result = subprocess.run(
                    ["git", "commit", "-m", f"[Snapshot] {message}"],
                    cwd=self.vault_path,
                    capture_output=True,
                    text=True,
                )
                combined = (result.stdout or "") + (result.stderr or "")
                if result.returncode == 0 or "nothing to commit" in combined:
                    # Get the current commit hash.
                    hash_res = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=self.vault_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    commit_hash = hash_res.stdout.strip()
                    logger.info("Snapshot created: %s - %s", commit_hash, message)
                    return commit_hash
                logger.error("Snapshot commit failed: %s", combined.strip())
            except subprocess.CalledProcessError as e:
                logger.error("Failed to create snapshot: %s", _error_text(cast(object, e.stderr)))
        return None

    def apply_privacy_mutation(self, mutation: VaultPrivacyMutation) -> VaultPrivacyResult:
        from antigravity_k.engine.vault_privacy import apply_vault_privacy_mutation
        from antigravity_k.engine.vault_privacy_derivatives import sync_vault_privacy_derivatives

        return apply_vault_privacy_mutation(
            vault_path=self.vault_path,
            acquire_lock=self._acquire_vault_lock,
            resolve_path=self._safe_resolve,
            mutation=mutation,
            sync_derivatives=lambda requested, replacements: sync_vault_privacy_derivatives(
                self,
                requested,
                replacements,
            ),
            is_safe_restore_target=self._is_safe_restore_target,
        )

    def restore_privacy_snapshot(self, snapshot_commit: str, paths: tuple[str, ...]) -> bool:
        from antigravity_k.engine.vault_privacy import resolve_vault_privacy_paths
        from antigravity_k.engine.vault_privacy_contracts import VaultPrivacyAction, VaultPrivacyMutation
        from antigravity_k.engine.vault_privacy_derivatives import sync_vault_privacy_derivatives
        from antigravity_k.engine.vault_privacy_git import (
            restore_vault_privacy_paths,
            validate_snapshot_paths,
        )

        with self._acquire_vault_lock():
            if not self._is_safe_restore_target():
                return False
            _ = resolve_vault_privacy_paths(paths, self._safe_resolve, require_files=False)
            validate_snapshot_paths(self.vault_path, snapshot_commit, paths)
            _ = restore_vault_privacy_paths(self.vault_path, snapshot_commit, paths)
            restored_paths = resolve_vault_privacy_paths(paths, self._safe_resolve, require_files=True)
            resolved = {path: path.read_text(encoding="utf-8") for path in restored_paths}
            sync_vault_privacy_derivatives(
                self,
                VaultPrivacyMutation(action=VaultPrivacyAction.REDACT, paths=paths),
                resolved,
            )
        return True

    def restore_snapshot(self, commit_hash: str) -> bool:
        """Restore the filesystem to a specific snapshot (commit hash).

        Refuses to run in a dangerous root path (``/``, home, Desktop, or any
        path that is a direct child of the home directory) because
        ``git reset --hard`` + ``git clean -fd`` would destroy unrelated files.

        Returns:
            True on success, False on failure or when the vault path is deemed
            unsafe.

        """
        # Safety check: never ``git reset --hard`` in a dangerous root path.
        if not self._is_safe_restore_target():
            return False

        with self._acquire_vault_lock():
            try:
                # 1. Reset hard to the specific commit.
                _ = subprocess.run(
                    ["git", "reset", "--hard", commit_hash],
                    cwd=self.vault_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # 2. Clean untracked files.
                _ = subprocess.run(
                    ["git", "clean", "-fd"],
                    cwd=self.vault_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Successfully restored snapshot to %s", commit_hash)
                return True
            except subprocess.CalledProcessError as e:
                logger.error(
                    "Failed to restore snapshot %s: %s",
                    commit_hash,
                    _error_text(cast(object, e.stderr)),
                )
        return False

    def _is_safe_restore_target(self) -> bool:
        """Return True if the vault path is safe for a destructive reset/clean.

        Dangerous targets: the filesystem root, the user's home, the Desktop,
        or any direct child of the home directory (e.g. ``~/Documents`` would
        be allowed only if it is at least two levels deep as a real project).
        The previous ``len(real_path) < 5`` heuristic is removed as ineffective.
        """
        real_path = Path(os.path.realpath(self.vault_path))
        home = Path(os.path.expanduser("~"))

        dangerous = {Path("/"), home, home / "Desktop"}
        if real_path in dangerous:
            logger.error("[SAFETY] Refusing git reset --hard in dangerous path: %s", real_path)
            return False
        # Reject a path that is a direct child of home (e.g. ~/something).
        if real_path.parent == home:
            logger.error("[SAFETY] Refusing git reset --hard in home-child path: %s", real_path)
            return False
        return True

    def parse_markdown(self, content: str) -> tuple[JSONMetadata, str]:
        """Parse a markdown string containing YAML frontmatter.

        Frontmatter is delimited by a line that is exactly ``---`` (RFC-style).
        A body containing a ``---`` horizontal rule is handled correctly because
        only the *closing* delimiter line (the second exact ``---`` at column 0)
        terminates the frontmatter block.

        On malformed YAML, the raw frontmatter text is **not** leaked into the
        body (previous behavior); instead metadata is returned as ``{}`` and the
        body is everything after the closing delimiter. Non-dict YAML payloads
        (lists, scalars) are normalized to ``{}`` so downstream ``.get()`` calls
        never raise ``AttributeError``.

        Returns:
            A tuple of (metadata_dict, body_content).

        """
        if not content.startswith("---\n") and not content.startswith("---\r\n"):
            return JSONMetadata(), content

        # Find frontmatter delimiters: lines that are exactly "---".
        delim_positions = [m.start() for m in _FRONTMATTER_DELIMITER.finditer(content)]
        # Need at least the opening + closing delimiter.
        if len(delim_positions) < 2:
            return JSONMetadata(), content

        # The opening delimiter is at position 0. The closing delimiter is the
        # next delimiter that starts at the beginning of a line (guaranteed by
        # the MULTILINE regex) and comes after the opening.
        open_end = delim_positions[0] + 3  # length of "---"
        # Find the first delimiter after the opening line.
        closing = next((p for p in delim_positions[1:] if p >= open_end), None)
        if closing is None:
            return JSONMetadata(), content

        # Extract the YAML between the opening and closing delimiters. Account
        # for the trailing newline of the opening "---" line.
        yaml_start = content.index("\n", open_end) + 1
        frontmatter_str = content[yaml_start:closing]
        # Body starts after the closing delimiter line.
        body_start = content.index("\n", closing + 3) + 1
        body_content = content[body_start:]

        try:
            parsed = cast(object, yaml.safe_load(frontmatter_str))
        except yaml.YAMLError as e:
            logger.error("YAML parsing error in frontmatter: %s", e)
            return JSONMetadata(), body_content

        # Normalize: only accept a mapping as metadata.
        if isinstance(parsed, Mapping):
            metadata = JSONMetadata(cast(Mapping[str, object], parsed))
        elif parsed is None:
            metadata = JSONMetadata()
        else:
            logger.warning(
                "Frontmatter parsed to %s, expected a mapping; normalizing to empty metadata.",
                type(parsed).__name__,
            )
            metadata = JSONMetadata()
        return metadata, body_content

    def format_markdown(self, metadata: Mapping[str, object], content: str) -> str:
        """Format metadata dictionary and body content into a markdown string with frontmatter."""
        if not metadata:
            return content
        frontmatter = yaml.dump(metadata, sort_keys=False, default_flow_style=False)
        return f"---\n{frontmatter}---\n{content}"

    def read_note(self, relative_path: str) -> tuple[JSONMetadata, str]:
        """Read a note and return its metadata and content.

        Uses the cross-process file lock (shared with writers) so that a read
        never observes a half-written file from a concurrent ``write_note``.

        Raises:
            ValueError: If ``relative_path`` escapes the vault.
            FileNotFoundError: If the note does not exist.

        """
        file_path = self._safe_resolve(relative_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {file_path}")

        # Acquire the file lock only (no need for the in-process lock for a
        # pure read, but the file lock prevents reading mid-write from another
        # process).
        with self._file_lock:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

        return self.parse_markdown(content)

    def write_note(
        self,
        relative_path: str,
        metadata: Mapping[str, object],
        content: str,
        commit_message: str | None = None,
    ):
        """Write a note with metadata and trigger an auto-commit.

        The full write (file + git commit) runs under the two-layer vault lock
        so concurrent writes are serialized at both the thread and process
        level. The file is fsync'd before staging so ``git add`` never sees a
        partially-flushed buffer.

        Raises:
            ValueError: If ``relative_path`` escapes the vault.
            VaultCommitError: If the git commit fails (propagated to caller).

        """
        file_path = self._safe_resolve(relative_path)

        with self._acquire_vault_lock():
            # Ensure parent directories exist.
            file_path.parent.mkdir(parents=True, exist_ok=True)

            formatted_content = self.format_markdown(metadata, content)

            # Write + fsync so a concurrent reader (or git staging in another
            # commit) never observes a partial buffer.
            with open(file_path, "w", encoding="utf-8") as f:
                _ = f.write(formatted_content)
                f.flush()
                os.fsync(f.fileno())

            message = commit_message or f"Update note: {relative_path}"
            self._auto_commit(str(relative_path), message)

        # RAG sync and downstream side-effects happen outside the git lock so a
        # slow indexer does not block other writers. File I/O is already durable
        # at this point.
        if self.sync_rag:
            try:
                # 1. Delete old chunks for this file.
                self.vector_store.delete_file_chunks(str(relative_path))
                # 2. Chunk the new content.
                chunks = self.chunker.chunk_document(str(relative_path), JSONMetadata(metadata), content)
                # 3. Upsert new chunks.
                self.vector_store.upsert_chunks(chunks)
            except Exception:
                logger.exception("Failed to sync RAG for %s", relative_path)

        # LLM Wiki 동기화 — 모든 Vault 기록을 LLM Wiki(config.paths.wiki_dir)에 통합
        self._sync_to_wiki(relative_path, metadata, content)

        # 지식 진화 트리거 (Agentic GraphRAG)
        event_title = metadata.get("title")
        publish = cast(Callable[..., None], global_event_bus.publish)
        publish(
            "WikiNoteUpdated",
            relative_path=str(relative_path),
            title=event_title if isinstance(event_title, str) else "",
        )

    def _sync_to_wiki(self, relative_path: str, metadata: Mapping[str, object], content: str) -> None:
        """Vault에 기록된 노트를 LLM Wiki(SQLite + Markdown)에 동기화합니다.

        실패 시 Vault 기록에는 영향을 주지 않습니다 (best-effort).
        """
        try:
            from antigravity_k.knowledge.wiki import LLMWiki

            wiki = LLMWiki()
            title_value = metadata.get("title")
            title: str = title_value if isinstance(title_value, str) else Path(relative_path).stem
            # 경로에서 카테고리 추론: .agent/memory/* → agent_memory, 기타 → vault
            parts = Path(relative_path).parts
            if "memory" in parts:
                category: str = "agent_memory"
            elif "decisions" in parts or "adr" in parts:
                category = "decision"
            else:
                category_value = metadata.get("type")
                category = category_value if isinstance(category_value, str) else "vault"

            tags_value = metadata.get("tags", [])
            if isinstance(tags_value, str):
                tags: list[str] = [tag.strip() for tag in tags_value.split(",")]
            elif isinstance(tags_value, list):
                tags = [tag for tag in cast(list[object], tags_value) if isinstance(tag, str)]
            else:
                tags = []

            # 기존 동일 제목 항목이 있으면 업데이트, 없으면 신규
            existing = wiki.search(title, limit=1)
            if existing and existing[0].entry.title == title:
                entry_id = existing[0].entry.id
                if entry_id is not None:
                    _ = wiki.update_entry(entry_id, content=content, tags=tags)
            else:
                _ = wiki.add_entry(
                    title=title,
                    content=content,
                    category=category,
                    tags=tags,
                    source="vault",
                    source_url=str(self.vault_path / relative_path),
                )
        except Exception:
            logger.exception("LLM Wiki 동기화 실패 (Vault 기록은 정상)")

    def search_notes(self, query: str) -> list[str]:
        """Search text across all notes in the vault (excluding .git).

        Runs under the cross-process file lock so the walk does not observe
        files mid-write from a concurrent ``write_note``.
        """
        results: list[str] = []
        with self._file_lock:
            for root, dirs, files in os.walk(self.vault_path):
                if ".git" in dirs:
                    dirs.remove(".git")
                for file in files:
                    if file.endswith(".md"):
                        file_path = Path(root) / file
                        try:
                            with open(file_path, encoding="utf-8") as f:
                                if query.lower() in f.read().lower():
                                    results.append(str(file_path.relative_to(self.vault_path)))
                        except Exception:
                            logger.exception("Error reading %s during search", file_path)
        return results

    def export_notes(self, include_assets: bool = False, redact: bool = True) -> list[JSONExportRecord]:
        from antigravity_k.engine.secret_scanner import redact_full

        def redact_value(value: object) -> object:
            if isinstance(value, str):
                return redact_full(value)
            if isinstance(value, Mapping):
                mapping = cast(Mapping[str, object], value)
                return {key: redact_value(item) for key, item in mapping.items()}
            if isinstance(value, list):
                return [redact_value(item) for item in cast(list[object], value)]
            return value

        records: list[JSONExportRecord] = []
        with self._file_lock:
            for file_path in self.vault_path.rglob("*.md"):
                if ".git" in file_path.parts or ".chroma" in file_path.parts:
                    continue
                try:
                    metadata, content = self.parse_markdown(file_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
                safe_metadata: object = redact_value(metadata) if redact else metadata
                record = JSONExportRecord()
                record["path"] = str(file_path.relative_to(self.vault_path))
                record["metadata"] = safe_metadata
                if include_assets:
                    record["content"] = redact_full(content) if redact else content
                records.append(record)
        return records

    def ingest_workspace(self, workspace_path: str):
        """Ingest an entire workspace folder into the VectorStore for RAG.

        Reads text and code files, chunks them, and upserts them.
        """
        if not self.sync_rag:
            logger.warning("RAG sync is disabled. Cannot ingest workspace.")
            return

        workspace = Path(workspace_path).resolve()
        if not workspace.exists() or not workspace.is_dir():
            logger.error("Workspace path does not exist: %s", workspace_path)
            return

        ignore_dirs = {
            ".git",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
            ".chroma",
            "venv",
            ".venv",
        }
        valid_extensions = {
            ".md",
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".json",
            ".txt",
            ".sh",
            ".yaml",
            ".yml",
        }

        total_chunks = 0
        logger.info("Starting workspace ingestion for: %s", workspace)

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() not in valid_extensions:
                    continue

                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    if not content.strip():
                        continue

                    # Delete old chunks
                    rel_path = str(file_path.relative_to(workspace))
                    self.vector_store.delete_file_chunks(rel_path)

                    # Create new chunks
                    metadata = {"type": "workspace_file", "extension": file_path.suffix}
                    chunks = self.chunker.chunk_document(rel_path, metadata, content)

                    if chunks:
                        self.vector_store.upsert_chunks(chunks)
                        total_chunks += len(chunks)

                except UnicodeDecodeError:
                    # Skip binary or non-utf8 files
                    continue
                except Exception:
                    logger.exception("Failed to ingest %s", file_path)

        logger.info("Workspace ingestion complete. Total chunks: %s", total_chunks)
        return {
            "status": "success",
            "total_chunks": total_chunks,
            "workspace": str(workspace),
        }
