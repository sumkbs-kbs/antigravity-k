"""Vault module."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

# RAG Imports
from antigravity_k.engine.chunker import MarkdownChunker
from antigravity_k.engine.event_bus import global_event_bus
from antigravity_k.engine.vector_store import VectorStore

logger = logging.getLogger(__name__)


class VaultEngine:
    """Vaultengine."""

    def __init__(self, vault_path: str, sync_rag: bool = True):
        """Initialize the VaultEngine.

        Args:
            vault_path (str): str vault path.
            sync_rag (bool): bool sync rag.

        """
        self.vault_path = Path(vault_path).resolve()
        self._ensure_git_repo()

        self.sync_rag = sync_rag
        if self.sync_rag:
            chroma_path = self.vault_path / ".chroma"
            chroma_path.mkdir(parents=True, exist_ok=True)
            self.vector_store = VectorStore(str(chroma_path))
            self.chunker = MarkdownChunker()

    def _ensure_git_repo(self):
        """Ensure the vault directory exists and is a git repository."""
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
        """Stage the file and commit changes to the local Git repository."""
        try:
            # Stage the specific file
            subprocess.run(
                ["git", "add", file_path],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
                text=True,
            )
            # Commit the changes
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
            )
            # Git commit returns non-zero if there's nothing to commit.
            if result.returncode == 0:
                logger.info("Git commit successful: %s", message)
            elif "nothing to commit" not in result.stdout:
                logger.warning("Git commit warning/error: %s", result.stderr or result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to auto-commit %s: %s", file_path, e.stderr)

    def create_snapshot(self, message: str) -> str | None:
        """Create a filesystem checkpoint (snapshot) by committing all current changes.
        Returns the commit hash if successful, None otherwise.
        """
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
            if result.returncode == 0 or "nothing to commit" in result.stdout:
                # Get the current commit hash
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
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create snapshot: %s", e.stderr)
        return None

    def restore_snapshot(self, commit_hash: str) -> bool:
        """Restore the filesystem to a specific snapshot (commit hash)."""
        # I-9: 안전 검증 — 위험한 경로에서의 git reset --hard 방지
        real_path = os.path.realpath(self.vault_path)
        dangerous_paths = [
            "/",
            os.path.expanduser("~"),
            os.path.expanduser("~/Desktop"),
        ]
        if any(real_path == d or real_path.startswith(d + os.sep) for d in dangerous_paths) or len(real_path) < 5:
            logger.error("[SAFETY] Refusing git reset --hard in dangerous path: %s", real_path)
            return False

        try:
            # 1. Reset hard to the specific commit
            subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
                text=True,
            )
            # 2. Clean untracked files
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

    def parse_markdown(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse a markdown string containing YAML frontmatter.

        Returns a tuple of (metadata_dict, body_content).
        """
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                frontmatter_str = parts[1]
                body_content = parts[2]
                try:
                    metadata = yaml.safe_load(frontmatter_str) or {}
                    return metadata, body_content
                except yaml.YAMLError as e:
                    logger.error("YAML parsing error: %s", e)
        return {}, content

    def format_markdown(self, metadata: dict[str, Any], content: str) -> str:
        """Format metadata dictionary and body content into a markdown string with frontmatter."""
        if not metadata:
            return content
        frontmatter = yaml.dump(metadata, sort_keys=False, default_flow_style=False)
        return f"---\n{frontmatter}---\n{content}"

    def read_note(self, relative_path: str) -> tuple[dict[str, Any], str]:
        """Read a note and return its metadata and content."""
        file_path = self.vault_path / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {file_path}")

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
        """Write a note with metadata and trigger an auto-commit."""
        file_path = self.vault_path / relative_path

        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        formatted_content = self.format_markdown(metadata, content)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(formatted_content)

        message = commit_message or f"Update note: {relative_path}"
        self._auto_commit(str(relative_path), message)

        # RAG Sync
        if self.sync_rag:
            try:
                # 1. Delete old chunks for this file
                self.vector_store.delete_file_chunks(str(relative_path))
                # 2. Chunk the new content
                chunks = self.chunker.chunk_document(str(relative_path), metadata, content)
                # 3. Upsert new chunks
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
                wiki.update_entry(existing[0].entry.id, content=content, tags=tags)
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
        """Search text across all notes in the vault (excluding .git)."""
        results = []
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
