import os
import subprocess
import yaml
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import logging

# RAG Imports
from antigravity_k.engine.chunker import MarkdownChunker
from antigravity_k.engine.vector_store import VectorStore

logger = logging.getLogger(__name__)

class VaultEngine:
    def __init__(self, vault_path: str, sync_rag: bool = True):
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
                    text=True
                )
                logger.info(f"Initialized Git repository at {self.vault_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to initialize Git repo: {e.stderr}")

    def _auto_commit(self, file_path: str, message: str = "Auto-commit via VaultEngine"):
        """Stage the file and commit changes to the local Git repository."""
        try:
            # Stage the specific file
            subprocess.run(
                ["git", "add", file_path],
                cwd=self.vault_path,
                check=True,
                capture_output=True,
                text=True
            )
            # Commit the changes
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.vault_path,
                capture_output=True,
                text=True
            )
            # Git commit returns non-zero if there's nothing to commit.
            if result.returncode == 0:
                logger.info(f"Git commit successful: {message}")
            elif "nothing to commit" not in result.stdout:
                logger.warning(f"Git commit warning/error: {result.stderr or result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to auto-commit {file_path}: {e.stderr}")

    def create_snapshot(self, message: str) -> Optional[str]:
        """Create a filesystem checkpoint (snapshot) by committing all current changes.
        Returns the commit hash if successful, None otherwise."""
        try:
            subprocess.run(["git", "add", "."], cwd=self.vault_path, check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"[Snapshot] {message}"],
                cwd=self.vault_path, capture_output=True, text=True
            )
            if result.returncode == 0 or "nothing to commit" in result.stdout:
                # Get the current commit hash
                hash_res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.vault_path, capture_output=True, text=True, check=True
                )
                commit_hash = hash_res.stdout.strip()
                logger.info(f"Snapshot created: {commit_hash} - {message}")
                return commit_hash
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create snapshot: {e.stderr}")
        return None

    def restore_snapshot(self, commit_hash: str) -> bool:
        """Restore the filesystem to a specific snapshot (commit hash)."""
        try:
            # 1. Reset hard to the specific commit
            subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                cwd=self.vault_path, check=True, capture_output=True, text=True
            )
            # 2. Clean untracked files
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=self.vault_path, check=True, capture_output=True, text=True
            )
            logger.info(f"Successfully restored snapshot to {commit_hash}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restore snapshot {commit_hash}: {e.stderr}")
            return False

    def parse_markdown(self, content: str) -> Tuple[Dict[str, Any], str]:
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
                    logger.error(f"YAML parsing error: {e}")
        return {}, content

    def format_markdown(self, metadata: Dict[str, Any], content: str) -> str:
        """Format metadata dictionary and body content into a markdown string with frontmatter."""
        if not metadata:
            return content
        frontmatter = yaml.dump(metadata, sort_keys=False, default_flow_style=False)
        return f"---\n{frontmatter}---\n{content}"

    def read_note(self, relative_path: str) -> Tuple[Dict[str, Any], str]:
        """Read a note and return its metadata and content."""
        file_path = self.vault_path / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Note not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return self.parse_markdown(content)

    def write_note(self, relative_path: str, metadata: Dict[str, Any], content: str, commit_message: Optional[str] = None):
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
            except Exception as e:
                logger.error(f"Failed to sync RAG for {relative_path}: {e}")

    def search_notes(self, query: str) -> list[str]:
        """Simple text search across all notes in the vault (excluding .git)."""
        results = []
        for root, dirs, files in os.walk(self.vault_path):
            if ".git" in dirs:
                dirs.remove(".git")
            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            if query.lower() in f.read().lower():
                                results.append(str(file_path.relative_to(self.vault_path)))
                    except Exception as e:
                        logger.warning(f"Error reading {file_path} during search: {e}")
        return results

    def ingest_workspace(self, workspace_path: str):
        """
        Ingest an entire workspace folder into the VectorStore for RAG.
        Reads text and code files, chunks them, and upserts them.
        """
        if not self.sync_rag:
            logger.warning("RAG sync is disabled. Cannot ingest workspace.")
            return

        workspace = Path(workspace_path).resolve()
        if not workspace.exists() or not workspace.is_dir():
            logger.error(f"Workspace path does not exist: {workspace_path}")
            return

        ignore_dirs = {".git", "node_modules", "dist", "build", "__pycache__", ".chroma", "venv", ".venv"}
        valid_extensions = {".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".txt", ".sh", ".yaml", ".yml"}

        total_chunks = 0
        logger.info(f"Starting workspace ingestion for: {workspace}")
        
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() not in valid_extensions:
                    continue
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
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
                except Exception as e:
                    logger.warning(f"Failed to ingest {file_path}: {e}")

        logger.info(f"Workspace ingestion complete. Total chunks: {total_chunks}")
        return {"status": "success", "total_chunks": total_chunks, "workspace": str(workspace)}
