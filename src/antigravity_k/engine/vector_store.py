"""Vector Store module."""

import logging
from types import TracebackType
from typing import Any, final

# 선택적 의존성. import 실패 시 전체 런타임 부팅을 막지 않도록 방어 로드.
# chromadb는 VectorStore 인스턴스 생성 시점에만 필요하다.
chromadb: Any = None
SharedSystemClient: Any = None
Settings: Any = None
_chroma_available = False
_chroma_import_error: BaseException | None = None

try:
    import chromadb as _chromadb
    from chromadb.api.client import SharedSystemClient as _SharedSystemClient
    from chromadb.config import Settings as _Settings

    chromadb = _chromadb
    SharedSystemClient = _SharedSystemClient
    Settings = _Settings
    _chroma_available = True
except Exception as _chroma_exc:  # pragma: no cover - 환경 의존적 의존성 로드 실패  # noqa: BLE001
    _chroma_import_error = _chroma_exc

logger = logging.getLogger(__name__)


@final
class VectorStore:
    """ChromaDB-backed vector store for RAG chunk storage and retrieval."""

    def __init__(self, persist_directory: str, collection_name: str = "vault_notes"):
        """Initialize the VectorStore.

        Args:
            persist_directory (str): str persist directory.
            collection_name (str): str collection name.

        """
        import os

        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        self._closed = False
        self.client: Any = None
        self.collection: Any = None

        if not _chroma_available:
            raise RuntimeError(
                "VectorStore requires chromadb but it is unavailable: "
                f"{type(_chroma_import_error).__name__}: {_chroma_import_error}",
            )

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

    def close(self) -> None:
        """ChromaDB 클라이언트 연결을 정리합니다."""
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            close = getattr(self.client, "close", None)
            if callable(close):
                _ = close()
        except Exception:
            logger.exception("VectorStore: chromadb client close 실패")
        finally:
            try:
                clear_system_cache = getattr(SharedSystemClient, "clear_system_cache", None)
                if callable(clear_system_cache):
                    _ = clear_system_cache()
            except Exception:
                logger.exception("VectorStore: clear_system_cache 실패")
            self.client = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> "VectorStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> None:
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

    def store_embedding(self, source_table: str, source_id: int, text: str) -> bool:
        self.upsert_chunks(
            [
                {
                    "id": f"{source_table}:{source_id}",
                    "text": text,
                    "metadata": {"source_table": source_table, "source_id": source_id},
                },
            ],
        )
        return True

    def search_similar(
        self,
        query: str,
        source_table: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        matches = self.search(query, n_results=top_k)
        results: list[dict[str, Any]] = []
        for match in matches:
            metadata = match.get("metadata", {})
            if metadata.get("source_table") != source_table:
                continue
            distance = match.get("distance")
            similarity = 1.0 / (1.0 + float(distance)) if distance is not None else 0.0
            results.append(
                {
                    "source_id": metadata.get("source_id"),
                    "similarity": similarity,
                },
            )
        return results

    def fit_tfidf(self, documents: list[str]) -> None:
        _ = documents
        return None

    def get_stats(self) -> dict[str, Any]:
        count = self.collection.count() if self.collection is not None else 0
        return {"available": True, "persist_directory": self.persist_directory, "count": count}

    def delete_file_chunks(self, file_path: str) -> None:
        """Delete all chunks belonging to a specific file.

        Useful when a file is deleted or completely rewritten.
        """
        try:
            self.delete_file_chunks_strict(file_path)
            logger.info("Deleted chunks for file: %s", file_path)
        except Exception:
            logger.exception("Error deleting chunks for %s", file_path)

    def delete_file_chunks_strict(self, file_path: str) -> None:
        _ = self.collection.delete(where={"source": file_path})

    def clear(self) -> int:
        ids = self.collection.get().get("ids") or []
        if ids:
            _ = self.collection.delete(ids=ids)
        return len(ids)

    def export_all(self) -> list[dict[str, Any]]:
        payload = self.collection.get(include=["documents", "metadatas"])
        ids = payload.get("ids") or []
        documents = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []
        return [
            {
                "id": node_id,
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
            }
            for index, node_id in enumerate(ids)
        ]

    def redact_all(self) -> int:
        from antigravity_k.engine.secret_scanner import redact_full

        payload = self.collection.get(include=["documents", "metadatas"])
        ids = payload.get("ids") or []
        documents = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []
        safe_documents = [redact_full(document or "") for document in documents]
        safe_metadatas = [
            {key: redact_full(value) if isinstance(value, str) else value for key, value in (metadata or {}).items()}
            for metadata in metadatas
        ]
        changed = sum(old != new for old, new in zip(documents, safe_documents, strict=False))
        if ids:
            self.collection.upsert(ids=ids, documents=safe_documents, metadatas=safe_metadatas)
        return changed

    def apply_retention(self, max_age_days: int) -> int:
        if max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")
        return 0

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Search for the most relevant chunks given a query string."""
        results = self.collection.query(query_texts=[query], n_results=n_results)

        # Format results
        formatted_results: list[dict[str, Any]] = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                ids_val = results.get("ids")
                docs_val = results.get("documents")
                metadatas = results.get("metadatas")
                metadata_val: dict[str, Any] = {}
                if metadatas:
                    try:
                        metadata_val = dict(metadatas[0][i]) if len(metadatas) > 0 else {}
                    except (IndexError, TypeError):
                        metadata_val = {}
                distances = results.get("distances")
                distance_val: float | None = None
                if distances:
                    try:
                        distance_val = distances[0][i]
                    except (IndexError, TypeError):
                        distance_val = None
                formatted_results.append(
                    {
                        "id": ids_val[0][i] if ids_val else "",
                        "text": docs_val[0][i] if docs_val else "",
                        "metadata": metadata_val,
                        "distance": distance_val,
                    },
                )
        return formatted_results
