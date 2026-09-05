"""Global brain — persistent cross-session memory and knowledge synthesis."""

import atexit
import concurrent.futures
import logging
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast, final

import networkx as nx

logger = logging.getLogger(__name__)

GraphAttributes = dict[str, str | int | float | bool]
ChromaValue = str | int | float | bool
JsonMap = dict[str, object]
if TYPE_CHECKING:
    Graph: TypeAlias = nx.DiGraph[str, GraphAttributes]
else:
    Graph = nx.DiGraph


class _ChromaCollectionOps(Protocol):
    def count(self) -> int: ...

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, ChromaValue]],
    ) -> object: ...

    def query(
        self,
        *,
        query_texts: list[str],
        n_results: int,
        where: dict[str, str] | None,
    ) -> JsonMap: ...

    def get(self, *, include: list[str] | None = None) -> JsonMap: ...

    def delete(self, *, ids: list[str]) -> object: ...


class _ChromaClient(Protocol):
    def get_or_create_collection(self, *, name: str) -> _ChromaCollectionOps: ...

    def close(self) -> object: ...


class _ChromaModule(Protocol):
    def PersistentClient(self, *, path: str, settings: object) -> _ChromaClient: ...


class _CollectionBoundary(Protocol):
    deleted: list[str]


class _SettingsFactory(Protocol):
    def __call__(self, *, anonymized_telemetry: bool) -> object: ...


def _read_graphml(path: str) -> Graph:
    reader = cast(Callable[[str], Graph], getattr(nx, "read_graphml"))
    return reader(path)


def _write_graphml(graph: Graph, path: str) -> object:
    writer = cast(Callable[[Graph, str], object], getattr(nx, "write_graphml"))
    return writer(graph, path)


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, str)]


def _as_float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, (int, float))]


def _as_graph_attributes(value: Mapping[object, object]) -> GraphAttributes:
    return {str(key): item for key, item in value.items() if isinstance(item, (str, int, float, bool))}


def _as_chroma_map(value: object) -> dict[str, ChromaValue]:
    if not isinstance(value, Mapping):
        return {}
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items() if isinstance(item, (str, int, float, bool))}


def _collection_or_none(owner: object) -> _ChromaCollectionOps | None:
    value = getattr(owner, "collection", None)
    return cast(_ChromaCollectionOps, value) if value is not None else None


# 선택적 의존성. import 실패 시 전체 런타임 부팅을 막지 않도록 방어 로드 (graceful degradation).
chromadb: object | None = None
SharedSystemClient: object | None = None
Settings: object | None = None
_chroma_available = False
_chroma_import_error: BaseException | None = None

try:
    import chromadb as _chromadb
    from chromadb.api.shared_system_client import SharedSystemClient as _SharedSystemClient
    from chromadb.config import Settings as _Settings

    chromadb = _chromadb
    Settings = _Settings
    SharedSystemClient = _SharedSystemClient
    _chroma_available = True
except Exception as _chroma_exc:  # pragma: no cover - 환경 의존적 의존성 로드 실패  # noqa: BLE001
    _chroma_import_error = _chroma_exc


@final
class GBrain:
    """Ssak-Ai Graph + Vector Memory (GBrain).

    JSONL 파일의 한계를 극복하기 위해, 노드 간 관계(NetworkX)와 의미론적 검색(ChromaDB)을 결합합니다.
    """

    def __init__(self, storage_dir: str | None = None):
        """Initialize the GBrain.

        Args:
            storage_dir (str | None): str | None storage dir.

        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path.home() / ".antigravity" / "gbrain"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.graph_file = self.storage_dir / "knowledge_graph.graphml"

        # 그래프 데이터베이스 초기화
        self.graph: Graph
        if self.graph_file.exists():
            try:
                self.graph = nx.DiGraph(_read_graphml(str(self.graph_file)))
            except Exception:
                logger.exception("[GBrain] Failed to load graph")
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

        db_path = self.storage_dir / "chroma"
        db_path.mkdir(exist_ok=True)

        self.chroma_client: _ChromaClient | None = None
        self.collection: _CollectionBoundary = cast(_CollectionBoundary, cast(object, None))

        if _chroma_available and chromadb is not None and Settings is not None:
            try:
                chroma_module = cast(_ChromaModule, chromadb)
                settings_factory = cast(_SettingsFactory, Settings)
                self.chroma_client = chroma_module.PersistentClient(
                    path=str(db_path),
                    settings=settings_factory(anonymized_telemetry=False),
                )
                self.collection = cast(
                    _CollectionBoundary,
                    cast(object, self.chroma_client.get_or_create_collection(name="gbrain_nodes")),
                )
            except Exception:
                logger.exception("[GBrain] chromadb 초기화 실패, 벡터 검색을 비활성화합니다.")
        else:
            logger.warning(
                "[GBrain] chromadb 비활성화 (%s). 벡터 검색 없이 그래프 메모리만 동작합니다.",
                type(_chroma_import_error).__name__,
            )

        # 비동기 백그라운드 저장을 위한 스레드 풀
        self._save_lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._closed = False

    def close(self) -> None:
        """ChromaDB 클라이언트 연결과 스레드 풀을 정리합니다."""
        if self._closed:
            return
        self._closed = True
        # 스레드 풀 먼저 종료
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            logger.exception("[GBrain] executor shutdown 실패")
        # ChromaDB 클라이언트 정리
        try:
            close = getattr(self.chroma_client, "close", None)
            if callable(close):
                _ = close()
        except Exception:
            logger.exception("[GBrain] chromadb client close 실패")
        finally:
            try:
                clear_system_cache = getattr(SharedSystemClient, "clear_system_cache", None)
                if callable(clear_system_cache):
                    _ = clear_system_cache()
            except Exception:
                logger.exception("[GBrain] clear_system_cache 실패")
            self.chroma_client = None

    def __del__(self):
        self.close()

    def _save_graph(self) -> None:
        """그래프를 백그라운드 스레드에서 디스크에 저장합니다."""
        # Mutation 방지를 위해 얕은 복사본을 만들어 넘깁니다.
        # (노드 속성까지 완전 복사가 필요하면 deepcopy를 써야 하지만, graphml 특성상 copy()로 충분합니다)
        graph_copy = self.graph.copy()

        def write_task(g: Graph) -> None:
            with self._save_lock:
                try:
                    _ = _write_graphml(g, str(self.graph_file))
                except Exception:
                    logger.exception("[GBrain] Failed to save graph background")

        _ = self._executor.submit(write_task, graph_copy)

    def add_node(
        self,
        node_id: str,
        label: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """그래프와 벡터DB에 노드를 추가합니다.

        label: "failure", "user_pref", "concept", etc.
        """
        metadata = metadata or {}
        metadata["label"] = label

        # 1. 그래프에 추가 (label이 metadata에도 있으므로 중복 키 방지)
        graph_meta = {k: v for k, v in metadata.items() if k not in ("label", "content")}
        self.graph.add_node(node_id, label=label, content=content, **graph_meta)

        # 2. 벡터DB에 추가
        # ChromaDB metadata values must be str, int, float or bool
        chroma_meta = {k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}

        collection = _collection_or_none(self)
        if collection is not None:
            _ = collection.upsert(documents=[content], metadatas=[chroma_meta], ids=[node_id])

        self._save_graph()
        logger.debug("[GBrain] Added node: %s (%s)", node_id, label)

    def add_edge(self, source_id: str, target_id: str, relation: str) -> None:
        """두 노드 간에 관계를 추가합니다."""
        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            logger.warning(
                "[GBrain] Cannot add edge: node missing (%s -> %s)",
                source_id,
                target_id,
            )
            return

        _ = self.graph.add_edge(source_id, target_id, relation=relation)
        self._save_graph()

    def search_semantic(
        self,
        query: str,
        limit: int = 3,
        filter_label: str | None = None,
    ) -> list[GraphAttributes]:
        """의미론적 검색을 통해 노드를 찾습니다."""
        collection = _collection_or_none(self)
        if collection is None or collection.count() == 0:
            return []

        where: dict[str, str] | None = {"label": filter_label} if filter_label else None

        results = collection.query(
            query_texts=[query],
            n_results=min(limit, collection.count()),
            where=where,
        )

        matched_nodes: list[GraphAttributes] = []
        raw_ids = results.get("ids")
        id_rows = cast(list[object], raw_ids) if isinstance(raw_ids, list) else []
        ids = [_as_string_list(row) for row in id_rows]
        raw_distances = results.get("distances")
        distance_rows = cast(list[object], raw_distances) if isinstance(raw_distances, list) else []
        distances = [_as_float_list(row) for row in distance_rows]
        if ids and ids[0]:
            for i, doc_id in enumerate(ids[0]):
                if self.graph.has_node(doc_id):
                    node_data = _as_graph_attributes(cast(Mapping[object, object], self.graph.nodes[doc_id]))
                    node_data["id"] = doc_id
                    node_data["distance"] = distances[0][i] if distances and i < len(distances[0]) else 0
                    matched_nodes.append(node_data)

        return matched_nodes

    def get_related(self, node_id: str, max_depth: int = 1) -> list[GraphAttributes]:
        """특정 노드와 연결된 그래프 이웃을 반환합니다."""
        _ = max_depth
        if not self.graph.has_node(node_id):
            return []

        related: list[GraphAttributes] = []
        # 간단한 1-hop 조회
        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            node_data = _as_graph_attributes(cast(Mapping[object, object], self.graph.nodes[neighbor]))
            node_data["id"] = str(neighbor)
            edge_attributes = cast(Mapping[object, object], edge_data or {})
            relation = edge_attributes.get("relation", "linked")
            node_data["relation_from_source"] = str(relation)
            related.append(node_data)

        return related

    def clear_all(self) -> int:
        deleted = self.graph.number_of_nodes()
        collection = _collection_or_none(self)
        if collection is not None:
            ids = _as_string_list(collection.get().get("ids", []))
            if ids:
                _ = collection.delete(ids=ids)
        self.graph.clear()
        self._save_graph()
        return deleted

    def export_all(self) -> list[GraphAttributes]:
        return [
            {"id": str(node_id), **_as_graph_attributes(cast(Mapping[object, object], data))}
            for node_id, data in self.graph.nodes(data=True)
        ]

    def redact_all(self) -> int:
        from antigravity_k.engine.secret_scanner import redact_full

        changed = 0
        for _node_id, raw_data in self.graph.nodes(data=True):
            data = cast(dict[object, object], raw_data)
            for key, value in list(data.items()):
                if isinstance(value, str):
                    redacted = redact_full(value)
                    changed += int(redacted != value)
                    data[key] = redacted
        collection = _collection_or_none(self)
        if collection is not None:
            payload = collection.get(include=["documents", "metadatas"])
            ids = _as_string_list(payload.get("ids", []))
            documents = _as_string_list(payload.get("documents", []))
            raw_metadatas = payload.get("metadatas", [])
            metadatas = cast(list[object], raw_metadatas) if isinstance(raw_metadatas, list) else []
            if ids:
                safe_documents = [redact_full(document) for document in documents]
                safe_metadatas: list[dict[str, ChromaValue]] = []
                for metadata in metadatas:
                    safe_metadatas.append(
                        {
                            key: redact_full(value) if isinstance(value, str) else value
                            for key, value in _as_chroma_map(metadata).items()
                        }
                    )
                _ = collection.upsert(ids=ids, documents=safe_documents, metadatas=safe_metadatas)
        if changed:
            self._save_graph()
        return changed

    def apply_retention(self, max_age_days: int) -> int:
        if max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")
        return 0


# 전역 싱글톤 인스턴스
global_gbrain = GBrain()


def _close_global_gbrain():
    """프로세스 종료 시 전역 GBrain의 리소스를 정리합니다."""
    try:
        _ = global_gbrain.close()
    except Exception:
        logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)


_ = atexit.register(_close_global_gbrain)
