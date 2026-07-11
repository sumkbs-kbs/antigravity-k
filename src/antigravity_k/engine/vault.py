"""Vault module."""

import logging
import os
import re
import subprocess
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml
from filelock import SoftFileLock

# RAG Imports
from antigravity_k.engine.chunker import MarkdownChunker
from antigravity_k.engine.event_bus import global_event_bus
from antigravity_k.engine.vector_store import VectorStore

logger = logging.getLogger(__name__)

# YAML frontmatter delimiter: a line that is exactly "---" (optionally with
# trailing whitespace). Used to split frontmatter from body precisely, instead
# of the previous naive str.split("---\n", 2) which mis-split horizontal rules.
_FRONTMATTER_DELIMITER = re.compile(r"^---[ \t]*$", re.MULTILINE)


class VaultCommitError(RuntimeError):
    """Raised when a Git auto-commit fails after acquiring the vault lock.

    Callers (API handlers) should translate this into a 5xx/503 response so the
    user is not silently told a write succeeded when version control failed.
    """


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
        self.vault_path = Path(vault_path).resolve()
        # In-process lock (re-entrant so internal helpers may re-enter).
        self._lock = threading.RLock()
        # Cross-process lock. Placed inside .git so it is co-located with the
        # index it guards; created alongside the repo in _ensure_git_repo.
        self._lock_file = self.vault_path / ".git" / ".agk_vault.lock"
        self._file_lock = SoftFileLock(str(self._lock_file), timeout=30)
        self._ensure_git_repo()

        self.sync_rag = sync_rag
        if self.sync_rag:
            chroma_path = self.vault_path / ".chroma"
            chroma_path.mkdir(parents=True, exist_ok=True)
            self.vector_store = VectorStore(str(chroma_path))
            self.chunker = MarkdownChunker()

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
            resolved.relative_to(self.vault_path)
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
            self.vault_path.mkdir(parents=True, exist_ok=True)
            git_dir = self.vault_path / ".git"
            if not git_dir.exists():
                try:
                    subprocess.run(
                        ["git", "init"],
                        cwd=self.vault_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.info("Initialized Git repository at %s", self.vault_path)
                except subprocess.CalledProcessError as e:
                    logger.error("Failed to initialize Git repo: %s", e.stderr)

    def _auto_commit(self, file_path: str, message: str = "Auto-commit via VaultEngine"):
        """Stage the file and commit changes to the local Git repository.

        Must be called while holding the vault lock (see ``_acquire_vault_lock``).
        Treats "nothing to commit" (git exit code 1) as a non-error, since a
        no-op write is not a failure. Any other git failure raises
        ``VaultCommitError`` so the caller can surface it instead of silently
        reporting success.

        Args:
            file_path (str): Path of the file to stage, relative to the vault.
            message (str): Commit message.

        Raises:
            VaultCommitError: If ``git add`` fails or ``git commit`` fails for
                a reason other than "nothing to commit".

        """
        try:
            # Stage the specific file.
            subprocess.run(
                ["git", "add", file_path],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
            logger.error("Failed to stage %s: %s", file_path, stderr)
            raise VaultCommitError(f"git add failed for {file_path}: {stderr}") from e

        # Commit the changes. ``git commit`` exits 1 when there is nothing to
        # commit; that is a normal no-op, not a failure.
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.vault_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Git commit successful: %s", message)
            return

        combined = (result.stdout or "") + (result.stderr or "")
        if "nothing to commit" in combined or "no changes added" in combined:
            logger.debug("Nothing to commit for %s (no-op)", file_path)
            return

        # Any other non-zero status is a real failure the caller must see.
        logger.error("Git commit failed: %s", combined.strip())
        raise VaultCommitError(f"git commit failed for {file_path}: {combined.strip()}")

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
                subprocess.run(
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
                logger.error("Failed to create snapshot: %s", e.stderr)
        return None

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
                subprocess.run(
                    ["git", "reset", "--hard", commit_hash],
                    cwd=self.vault_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # 2. Clean untracked files.
                subprocess.run(
                    ["git", "clean", "-fd"],
                    cwd=self.vault_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Successfully restored snapshot to %s", commit_hash)
                return True
            except subprocess.CalledProcessError as e:
                logger.error("Failed to restore snapshot %s: %s", commit_hash, e.stderr)
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

    def parse_markdown(self, content: str) -> tuple[dict[str, Any], str]:
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
            return {}, content

        # Find frontmatter delimiters: lines that are exactly "---".
        delim_positions = [m.start() for m in _FRONTMATTER_DELIMITER.finditer(content)]
        # Need at least the opening + closing delimiter.
        if len(delim_positions) < 2:
            return {}, content

        # The opening delimiter is at position 0. The closing delimiter is the
        # next delimiter that starts at the beginning of a line (guaranteed by
        # the MULTILINE regex) and comes after the opening.
        open_end = delim_positions[0] + 3  # length of "---"
        # Find the first delimiter after the opening line.
        closing = next((p for p in delim_positions[1:] if p >= open_end), None)
        if closing is None:
            return {}, content

        # Extract the YAML between the opening and closing delimiters. Account
        # for the trailing newline of the opening "---" line.
        yaml_start = content.index("\n", open_end) + 1
        frontmatter_str = content[yaml_start:closing]
        # Body starts after the closing delimiter line.
        body_start = content.index("\n", closing + 3) + 1
        body_content = content[body_start:]

        try:
            parsed = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError as e:
            logger.error("YAML parsing error in frontmatter: %s", e)
            return {}, body_content

        # Normalize: only accept a mapping as metadata.
        if isinstance(parsed, dict):
            metadata: dict[str, Any] = parsed
        elif parsed is None:
            metadata = {}
        else:
            logger.warning(
                "Frontmatter parsed to %s, expected a mapping; normalizing to empty metadata.",
                type(parsed).__name__,
            )
            metadata = {}
        return metadata, body_content

    def format_markdown(self, metadata: dict[str, Any], content: str) -> str:
        """Format metadata dictionary and body content into a markdown string with frontmatter."""
        if not metadata:
            return content
        frontmatter = yaml.dump(metadata, sort_keys=False, default_flow_style=False)
        return f"---\n{frontmatter}---\n{content}"

    def read_note(self, relative_path: str) -> tuple[dict[str, Any], str]:
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
        metadata: dict[str, Any],
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
                f.write(formatted_content)
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
                chunks = self.chunker.chunk_document(str(relative_path), metadata, content)
                # 3. Upsert new chunks.
                self.vector_store.upsert_chunks(chunks)
            except Exception:
                logger.exception("Failed to sync RAG for %s", relative_path)

        # LLM Wiki 동기화 — 모든 Vault 기록을 /Users/mr.k/wiki에 통합
        self._sync_to_wiki(relative_path, metadata, content)

        # 지식 진화 트리거 (Agentic GraphRAG)
        global_event_bus.publish(
            "WikiNoteUpdated",
            relative_path=str(relative_path),
            title=metadata.get("title", ""),
        )

    def _sync_to_wiki(self, relative_path: str, metadata: dict[str, Any], content: str):
        """Vault에 기록된 노트를 LLM Wiki(SQLite + Markdown)에 동기화합니다.

        실패 시 Vault 기록에는 영향을 주지 않습니다 (best-effort).
        """
        try:
            from antigravity_k.knowledge.wiki import LLMWiki

            wiki = LLMWiki()
            title = metadata.get("title", Path(relative_path).stem)
            # 경로에서 카테고리 추론: .agent/memory/* → agent_memory, 기타 → vault
            parts = Path(relative_path).parts
            if "memory" in parts:
                category = "agent_memory"
            elif "decisions" in parts or "adr" in parts:
                category = "decision"
            else:
                category = metadata.get("type", "vault")

            tags = metadata.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            # 기존 동일 제목 항목이 있으면 업데이트, 없으면 신규
            existing = wiki.search(title, limit=1)
            if existing and existing[0].entry.title == title:
                entry_id = existing[0].entry.id
                if entry_id is not None:
                    wiki.update_entry(entry_id, content=content, tags=tags)
            else:
                wiki.add_entry(
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
