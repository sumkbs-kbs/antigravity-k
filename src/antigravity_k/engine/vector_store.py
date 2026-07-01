"""Vector Store module."""

import logging
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Vectorstore."""

    def __init__(self, persist_directory: str, collection_name: str = "vault_notes"):
        """Initialize the VectorStore.

        Args:
            persist_directory (str): str persist directory.
            collection_name (str): str collection name.

        """
        import os

        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
        except KeyError:
            # ChromaDB SharedSystemClient 캐시 충돌 시 Settings 으로 재시도
            logger.warning("ChromaDB 캐시 충돌 감지, Settings 모드로 재초기화합니다.")
            settings = Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
            )
            try:
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=settings,
                )
            except Exception:
                # 최종 폴백: 인메모리 클라이언트
                logger.exception("PersistentClient 실패, 인메모리 ChromaDB로 폴백합니다.")
                self.client = chromadb.Client()

        # Get or create the collection.
        self.collection = self.client.get_or_create_collection(name=collection_name)
        logger.info(
            "Initialized ChromaDB VectorStore at %s, collection: %s",
            persist_directory,
            collection_name,
        )

    def upsert_chunks(self, chunks: list[dict[str, Any]]):
        """Upsert a list of chunk dictionaries into ChromaDB.

        Each chunk should have 'id', 'text', and 'metadata'.
        """
        if not chunks:
            return

        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]

        # Chroma metadata requires values to be str, int, float, or bool.
        # We need to sanitize the metadata dictionaries.
        metadatas = []
        for chunk in chunks:
            safe_meta = {}
            for k, v in chunk["metadata"].items():
                if isinstance(v, (str, int, float, bool)):
                    safe_meta[k] = v
                elif isinstance(v, list):
                    # Convert list to comma-separated string
                    safe_meta[k] = ", ".join(str(x) for x in v)
                else:
                    safe_meta[k] = str(v)
            metadatas.append(safe_meta)

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Upserted %s chunks into ChromaDB.", len(chunks))

    def delete_file_chunks(self, file_path: str):
        """Delete all chunks belonging to a specific file.

        Useful when a file is deleted or completely rewritten.
        """
        try:
            self.collection.delete(where={"source": file_path})
            logger.info("Deleted chunks for file: %s", file_path)
        except Exception:
            logger.exception("Error deleting chunks for %s", file_path)

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Search for the most relevant chunks given a query string."""
        results = self.collection.query(query_texts=[query], n_results=n_results)

        # Format results
        formatted_results = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": (results["metadatas"][0][i] if results["metadatas"] else {}),
                        "distance": (results["distances"][0][i] if results["distances"] else None),
                    },
                )
        return formatted_results
