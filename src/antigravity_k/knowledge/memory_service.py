"""Memory Service module."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryService:
    """에이전트 팀의 지속적 메모리(GBrain 모델)를 담당합니다.

    작업 이력, 학습된 지식, 컨텍스트 스냅샷을 영구적으로 저장하고 조회할 수 있습니다.

    Phase 3 업그레이드:
    - VectorStore 통합으로 시맨틱 검색 지원
    - 하이브리드 검색: 벡터 유사도 + 키워드 LIKE 결합
    - 자동 임베딩 갱신
    """

    def __init__(self, db_path: str | None = None):
        """Initialize the MemoryService.

        Args:
            db_path (str | None): str | None db path.

        """
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "memory.db")

        self.db_path = db_path
        self._vector_store = None  # 지연 초기화
        self._init_db()

    @property
    def vector_store(self):
        """VectorStore를 지연 로드합니다."""
        if self._vector_store is None:
            try:
                from antigravity_k.knowledge.vector_store import VectorStore

                self._vector_store = VectorStore(db_path=self.db_path)
                logger.info("VectorStore initialized for hybrid search")
            except Exception:
                logger.exception("VectorStore init failed, keyword-only mode")
        return self._vector_store

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_items (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_snapshots (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    snapshot_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_knowledge(self, topic: str, content: str, tags: list[str] = None):
        """새로운 지식 항목을 저장하고 벡터 임베딩을 자동 생성합니다."""
        now = datetime.now().isoformat()
        tags_str = json.dumps(tags) if tags else "[]"
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge_items (topic, content, tags, created_at) VALUES (?, ?, ?, ?)",
                (topic, content, tags_str, now),
            )
            conn.commit()
            item_id = cursor.lastrowid

        # 벡터 임베딩 자동 생성
        if self.vector_store is not None:
            embed_text = f"{topic} {content}"
            self.vector_store.store_embedding("knowledge_items", item_id, embed_text)

        logger.info("Knowledge added on topic: %s (id=%s)", topic, item_id)
        return item_id

    def search_knowledge(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """지식을 검색합니다.

        Args:
            query: 검색 쿼리
            mode: 검색 모드
                - "keyword": 기존 LIKE 검색
                - "vector": 벡터 유사도 검색
                - "hybrid": 벡터 + 키워드 결합 (기본값)
            top_k: 반환할 최대 결과 수

        Returns:
            검색 결과 리스트 (유사도/관련성 내림차순)

        """
        if mode == "keyword" or self.vector_store is None:
            return self._keyword_search(query, top_k)
        elif mode == "vector":
            return self._vector_search(query, top_k)
        else:  # hybrid
            return self._hybrid_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """기존 LIKE 기반 키워드 검색."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM knowledge_items WHERE topic LIKE ? OR content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", top_k),
            )
            results = [dict(row) for row in cur.fetchall()]
            for r in results:
                r["_search_mode"] = "keyword"
                r["_score"] = 1.0  # 키워드 매칭은 바이너리
            return results

    def _vector_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """벡터 유사도 검색."""
        if self.vector_store is None:
            return self._keyword_search(query, top_k)

        similar = self.vector_store.search_similar(
            query,
            source_table="knowledge_items",
            top_k=top_k,
        )

        if not similar:
            return []

        # source_id로 원본 데이터 조회
        ids = [s["source_id"] for s in similar]
        sim_map = {s["source_id"]: s["similarity"] for s in similar}

        placeholders = ",".join("?" * len(ids))
        with self._get_connection() as conn:
            cur = conn.execute(f"SELECT * FROM knowledge_items WHERE id IN ({placeholders})", ids)
            rows = [dict(row) for row in cur.fetchall()]

        # 유사도 순 정렬
        for row in rows:
            row["_search_mode"] = "vector"
            row["_score"] = sim_map.get(row["id"], 0.0)
        rows.sort(key=lambda x: x["_score"], reverse=True)

        return rows

    def _hybrid_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """하이브리드 검색: 벡터 + 키워드 결과를 결합합니다.

        Reciprocal Rank Fusion (RRF) 알고리즘 사용.
        """
        k_results = self._keyword_search(query, top_k * 2)
        v_results = self._vector_search(query, top_k * 2)

        # RRF 스코어 계산
        rrf_scores: dict[int, float] = {}
        rrf_k = 60  # RRF 상수

        for rank, item in enumerate(k_results):
            item_id = item["id"]
            rrf_scores[item_id] = rrf_scores.get(item_id, 0) + 1.0 / (rrf_k + rank + 1)

        for rank, item in enumerate(v_results):
            item_id = item["id"]
            rrf_scores[item_id] = rrf_scores.get(item_id, 0) + 1.0 / (rrf_k + rank + 1)

        # 모든 결과를 id 기준으로 병합
        all_items: dict[int, dict] = {}
        for item in k_results + v_results:
            if item["id"] not in all_items:
                all_items[item["id"]] = item

        # RRF 점수 부여 및 정렬
        results = []
        for item_id, item in all_items.items():
            item["_search_mode"] = "hybrid"
            item["_score"] = round(rrf_scores.get(item_id, 0), 6)
            results.append(item)

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    def rebuild_embeddings(self) -> int:
        """기존 지식 항목의 벡터 임베딩을 재생성합니다."""
        if self.vector_store is None:
            logger.warning("VectorStore not available — cannot rebuild embeddings")
            return 0

        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, topic, content FROM knowledge_items").fetchall()

        # TF-IDF 학습 (전체 문서로)
        documents = [f"{r['topic']} {r['content']}" for r in rows]
        if documents:
            self.vector_store.fit_tfidf(documents)

        count = 0
        for row in rows:
            text = f"{row['topic']} {row['content']}"
            if self.vector_store.store_embedding("knowledge_items", row["id"], text):
                count += 1

        logger.info("Rebuilt %s/%s embeddings", count, len(rows))
        return count

    def save_snapshot(self, agent_name: str, snapshot_data: dict[str, Any]):
        """에이전트의 현재 상태(컨텍스트) 스냅샷을 저장합니다."""
        now = datetime.now().isoformat()
        data_str = json.dumps(snapshot_data, ensure_ascii=False)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO context_snapshots (agent_name, snapshot_data, created_at) VALUES (?, ?, ?)",
                (agent_name, data_str, now),
            )
            conn.commit()
        logger.info("Context snapshot saved for agent %s", agent_name)

    def load_latest_snapshot(self, agent_name: str) -> dict[str, Any] | None:
        """에이전트의 가장 최근 상태 스냅샷을 불러옵니다."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT snapshot_data FROM context_snapshots WHERE agent_name = ? ORDER BY created_at DESC LIMIT 1",
                (agent_name,),
            )
            row = cur.fetchone()
            if row:
                return json.loads(row["snapshot_data"])
        return None

    def get_stats(self) -> dict[str, Any]:
        """메모리 서비스 통계."""
        with self._get_connection() as conn:
            ki_count = conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0]
            snap_count = conn.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0]

        stats = {
            "knowledge_items": ki_count,
            "context_snapshots": snap_count,
            "db_path": self.db_path,
        }

        if self.vector_store is not None:
            stats["vector_store"] = self.vector_store.get_stats()

        return stats
