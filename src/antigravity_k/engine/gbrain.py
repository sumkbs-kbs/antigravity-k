"""Global brain — persistent cross-session memory and knowledge synthesis."""

import atexit
import concurrent.futures
import logging
import threading
from pathlib import Path
from typing import Any, cast

import chromadb
import networkx as nx
from chromadb.api.client import SharedSystemClient
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class GBrain:
    """Antigravity-K Graph + Vector Memory (GBrain).

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
        if self.graph_file.exists():
            try:
                self.graph = nx.read_graphml(str(self.graph_file))
            except Exception:
                logger.exception("[GBrain] Failed to load graph")
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

        # 벡터 데이터베이스 (ChromaDB)
        db_path = self.storage_dir / "chroma"
        db_path.mkdir(exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma_client.get_or_create_collection(name="gbrain_nodes")

        # 비동기 백그라운드 저장을 위한 스레드 풀
        self._save_lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._closed = False

    def close(self):
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
            if hasattr(self, "chroma_client") and self.chroma_client is not None:
                self.chroma_client.close()
        except Exception:
            logger.exception("[GBrain] chromadb client close 실패")
        finally:
            try:
                SharedSystemClient.clear_system_cache()
            except Exception:
                logger.exception("[GBrain] clear_system_cache 실패")
            self.chroma_client = None

    def __del__(self):
        self.close()

    def _save_graph(self):
        """그래프를 백그라운드 스레드에서 디스크에 저장합니다."""
        # Mutation 방지를 위해 얕은 복사본을 만들어 넘깁니다.
        # (노드 속성까지 완전 복사가 필요하면 deepcopy를 써야 하지만, graphml 특성상 copy()로 충분합니다)
        graph_copy = self.graph.copy()

        def write_task(g):
            with self._save_lock:
                try:
                    nx.write_graphml(g, str(self.graph_file))
                except Exception:
                    logger.exception("[GBrain] Failed to save graph background")

        self._executor.submit(write_task, graph_copy)

    def add_node(
        self,
        node_id: str,
        label: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ):
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

        self.collection.upsert(documents=[content], metadatas=[chroma_meta], ids=[node_id])

        self._save_graph()
        logger.debug("[GBrain] Added node: %s (%s)", node_id, label)

    def add_edge(self, source_id: str, target_id: str, relation: str):
        """두 노드 간에 관계를 추가합니다."""
        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            logger.warning(
                "[GBrain] Cannot add edge: node missing (%s -> %s)",
                source_id,
                target_id,
            )
            return

        self.graph.add_edge(source_id, target_id, relation=relation)
        self._save_graph()

    def search_semantic(
        self,
        query: str,
        limit: int = 3,
        filter_label: str | None = None,
    ) -> list[dict[str, Any]]:
        """의미론적 검색을 통해 노드를 찾습니다."""
        if self.collection.count() == 0:
            return []

        where: dict[str, str] | None = {"label": filter_label} if filter_label else None

        results = self.collection.query(
            query_texts=[query],
            n_results=min(limit, self.collection.count()),
            where=cast(Any, where),
        )

        matched_nodes = []
        if results and results["ids"] and len(results["ids"]) > 0:
            for i, doc_id in enumerate(results["ids"][0]):
                if self.graph.has_node(doc_id):
                    node_data = self.graph.nodes[doc_id].copy()
                    node_data["id"] = doc_id
                    node_data["distance"] = (
                        results["distances"][0][i] if "distances" in results and results["distances"] else 0
                    )
                    matched_nodes.append(node_data)

        return matched_nodes

    def get_related(self, node_id: str, max_depth: int = 1) -> list[dict[str, Any]]:
        """특정 노드와 연결된 그래프 이웃을 반환합니다."""
        if not self.graph.has_node(node_id):
            return []

        related = []
        # 간단한 1-hop 조회
        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            node_data = self.graph.nodes[neighbor].copy()
            node_data["id"] = neighbor
            node_data["relation_from_source"] = edge_data.get("relation", "linked")
            related.append(node_data)

        return related


# 전역 싱글톤 인스턴스
global_gbrain = GBrain()


def _close_global_gbrain():
    """프로세스 종료 시 전역 GBrain의 리소스를 정리합니다."""
    try:
        global_gbrain.close()
    except Exception:
        logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)


atexit.register(_close_global_gbrain)
