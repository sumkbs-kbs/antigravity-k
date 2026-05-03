#!/usr/bin/env python3
"""
Antigravity-K: LLM Wiki — 세컨드 브레인 (Second Brain)
======================================================
로컬 LLM의 지식을 확장하는 영속적 지식 관리 시스템.

핵심 기능:
    1. Markdown / Obsidian 볼트 자동 파싱 & 벡터화
    2. 위키 CRUD API (등록/검색/갱신/삭제)
    3. 대화 중 자동 지식 참조 (RAG 연동)
    4. 웹 검색 결과 자동 저장
    5. 지식 그래프 메타데이터 관리

아키텍처:
    ┌─────────┐     ┌──────────┐     ┌──────────┐
    │ LLM 채팅 │ ──▶ │ Wiki API │ ──▶ │ SQLite   │
    └─────────┘     └──────────┘     │ + FTS5   │
         ▲               │           └──────────┘
         │               ▼
    ┌─────────┐     ┌──────────┐
    │ 웹 검색  │ ──▶ │ 벡터 DB  │
    └─────────┘     │(ChromaDB)│
                    └──────────┘

사용법:
    from antigravity_k.knowledge.wiki import LLMWiki

    wiki = LLMWiki()
    wiki.add_entry("FastAPI 3.0", "2025년 출시된 FastAPI 3.0의 주요 변경사항...")
    results = wiki.search("FastAPI 비동기 패턴")
"""

import json
import logging
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("llm_wiki")

# ─── 데이터 디렉토리 ──────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
WIKI_DB_PATH = DATA_DIR / "wiki.db"
WIKI_DIR = DATA_DIR / "wiki_entries"


# ─── 데이터 모델 ──────────────────────────────────────────────────


@dataclass
class WikiEntry:
    """위키 항목."""

    id: Optional[int] = None
    title: str = ""
    content: str = ""
    category: str = "general"      # general, code, domain, web, note
    tags: list[str] = field(default_factory=list)
    source: str = ""               # manual, web_search, obsidian, chat
    source_url: str = ""
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = json.dumps(self.tags, ensure_ascii=False)
        return d


@dataclass
class SearchHit:
    """검색 결과."""

    entry: WikiEntry
    score: float = 0.0
    matched_field: str = ""       # title, content, tags


# ─── LLM Wiki 코어 ───────────────────────────────────────────────


class LLMWiki:
    """
    세컨드 브레인 — 로컬 LLM을 위한 영속적 지식 관리.

    SQLite FTS5 (Full-Text Search)를 사용하여
    외부 벡터 DB 없이도 빠른 키워드 + 의미 검색을 지원합니다.
    ChromaDB 통합은 선택적입니다.

    Args:
        db_path: SQLite DB 경로
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or WIKI_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        WIKI_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """DB 스키마 초기화."""
        conn = self._connect()
        conn.executescript("""
            -- 메인 위키 테이블
            CREATE TABLE IF NOT EXISTS wiki_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                content     TEXT NOT NULL,
                category    TEXT DEFAULT 'general',
                tags        TEXT DEFAULT '[]',
                source      TEXT DEFAULT 'manual',
                source_url  TEXT DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            -- FTS5 전문 검색 인덱스
            CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                title,
                content,
                tags,
                content=wiki_entries,
                content_rowid=id,
                tokenize='unicode61'
            );

            -- FTS 트리거 (자동 동기화)
            CREATE TRIGGER IF NOT EXISTS wiki_ai AFTER INSERT ON wiki_entries BEGIN
                INSERT INTO wiki_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS wiki_ad AFTER DELETE ON wiki_entries BEGIN
                INSERT INTO wiki_fts(wiki_fts, rowid, title, content, tags)
                VALUES ('delete', old.id, old.title, old.content, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS wiki_au AFTER UPDATE ON wiki_entries BEGIN
                INSERT INTO wiki_fts(wiki_fts, rowid, title, content, tags)
                VALUES ('delete', old.id, old.title, old.content, old.tags);
                INSERT INTO wiki_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END;

            -- 지식 그래프 (항목 간 관계)
            CREATE TABLE IF NOT EXISTS wiki_links (
                from_id INTEGER NOT NULL,
                to_id   INTEGER NOT NULL,
                relation TEXT DEFAULT 'related',
                created_at TEXT NOT NULL,
                PRIMARY KEY (from_id, to_id),
                FOREIGN KEY (from_id) REFERENCES wiki_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (to_id) REFERENCES wiki_entries(id) ON DELETE CASCADE
            );

            -- 접근 이력
            CREATE TABLE IF NOT EXISTS wiki_access_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id   INTEGER NOT NULL,
                query      TEXT,
                accessed_at TEXT NOT NULL,
                context    TEXT DEFAULT ''
            );
        """)
        conn.close()
        logger.info(f"Wiki DB 초기화 완료: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ─── CRUD ────────────────────────────────────────────────────

    def add_entry(
        self,
        title: str,
        content: str,
        category: str = "general",
        tags: Optional[list[str]] = None,
        source: str = "manual",
        source_url: str = "",
    ) -> int:
        """
        위키에 새 항목을 추가합니다.

        Args:
            title: 제목
            content: 내용 (Markdown 지원)
            category: 카테고리 (general/code/domain/web/note)
            tags: 태그 목록
            source: 출처 (manual/web_search/obsidian/chat)
            source_url: 출처 URL

        Returns:
            생성된 항목 ID
        """
        now = datetime.now().isoformat()
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        conn = self._connect()
        cursor = conn.execute(
            """INSERT INTO wiki_entries
               (title, content, category, tags, source, source_url, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, content, category, tags_json, source, source_url, now, now),
        )
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Markdown 파일로도 저장 (Obsidian 호환)
        self._save_markdown(entry_id, title, content, category, tags or [])

        logger.info(f"위키 항목 추가: [{entry_id}] {title}")
        return entry_id

    def update_entry(self, entry_id: int, **kwargs) -> bool:
        """
        기존 항목을 업데이트합니다.

        사용법:
            wiki.update_entry(1, content="새로운 내용", tags=["python", "async"])
        """
        allowed = {"title", "content", "category", "tags", "source_url"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}

        if not updates:
            return False

        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"], ensure_ascii=False)

        updates["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entry_id]

        conn = self._connect()
        conn.execute(
            f"UPDATE wiki_entries SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
        conn.close()

        logger.info(f"위키 항목 업데이트: [{entry_id}]")
        return True

    def delete_entry(self, entry_id: int) -> bool:
        """항목을 삭제합니다."""
        conn = self._connect()
        cursor = conn.execute("DELETE FROM wiki_entries WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def get_entry(self, entry_id: int) -> Optional[WikiEntry]:
        """ID로 항목을 조회합니다."""
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM wiki_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_entry(row)

    # ─── 검색 ────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        """
        위키를 전문 검색합니다.

        FTS5 기반 검색 + 접근 빈도 가중치.

        Args:
            query: 검색 쿼리
            category: 카테고리 필터
            limit: 최대 결과 수

        Returns:
            관련도 순으로 정렬된 검색 결과
        """
        conn = self._connect()

        # FTS5 검색
        fts_query = self._prepare_fts_query(query)

        if category:
            rows = conn.execute(
                """SELECT e.*, bm25(wiki_fts) as score
                   FROM wiki_fts f
                   JOIN wiki_entries e ON f.rowid = e.id
                   WHERE wiki_fts MATCH ?
                     AND e.category = ?
                   ORDER BY score
                   LIMIT ?""",
                (fts_query, category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT e.*, bm25(wiki_fts) as score
                   FROM wiki_fts f
                   JOIN wiki_entries e ON f.rowid = e.id
                   WHERE wiki_fts MATCH ?
                   ORDER BY score
                   LIMIT ?""",
                (fts_query, limit),
            ).fetchall()

        results = []
        for row in rows:
            entry = self._row_to_entry(row)
            results.append(SearchHit(
                entry=entry,
                score=abs(row["score"]),
                matched_field="fts",
            ))

        # 접근 이력 기록
        for hit in results:
            self._log_access(conn, hit.entry.id, query)

        conn.commit()
        conn.close()

        logger.info(f"위키 검색: '{query}' → {len(results)}개 결과")
        return results

    def search_for_llm(self, query: str, max_chars: int = 2000) -> str:
        """
        LLM 컨텍스트에 주입할 수 있도록 검색 결과를 포맷합니다.

        api_forwarder.py에서 자동으로 호출됩니다.
        """
        hits = self.search(query, limit=5)

        if not hits:
            return ""

        lines = ["[📚 세컨드 브레인 — 관련 지식]", ""]
        chars = 0

        for hit in hits:
            entry = hit.entry
            block = (
                f"### {entry.title}\n"
                f"{entry.content[:500]}\n"
                f"_(카테고리: {entry.category}, "
                f"출처: {entry.source})_\n"
            )
            if chars + len(block) > max_chars:
                break
            lines.append(block)
            chars += len(block)

        return "\n".join(lines)

    # ─── Obsidian / Markdown 파싱 ────────────────────────────────

    def import_obsidian_vault(self, vault_path: str) -> int:
        """
        Obsidian 볼트를 일괄 임포트합니다.

        Args:
            vault_path: Obsidian 볼트 디렉토리 경로

        Returns:
            임포트된 항목 수
        """
        vault = Path(vault_path)
        if not vault.exists():
            logger.error(f"볼트 경로 없음: {vault_path}")
            return 0

        count = 0
        for md_file in vault.rglob("*.md"):
            # .obsidian, .trash 제외
            if any(p.startswith(".") for p in md_file.parts):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem

                # Obsidian 프론트매터 파싱
                tags = []
                category = "note"
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end > 0:
                        frontmatter = content[3:end]
                        content = content[end + 3:].strip()

                        # 태그 추출
                        tag_match = re.search(r"tags:\s*\[(.+?)\]", frontmatter)
                        if tag_match:
                            tags = [
                                t.strip().strip("'\"")
                                for t in tag_match.group(1).split(",")
                            ]

                        # 카테고리 추출
                        cat_match = re.search(r"category:\s*(.+)", frontmatter)
                        if cat_match:
                            category = cat_match.group(1).strip()

                # 중복 체크
                existing = self.search(title, limit=1)
                if existing and existing[0].entry.title == title:
                    self.update_entry(existing[0].entry.id, content=content, tags=tags)
                else:
                    self.add_entry(
                        title=title,
                        content=content,
                        category=category,
                        tags=tags,
                        source="obsidian",
                        source_url=str(md_file),
                    )
                count += 1

            except Exception as e:
                logger.warning(f"Markdown 파싱 실패: {md_file} — {e}")

        logger.info(f"Obsidian 임포트 완료: {count}개 항목")
        return count

    # ─── 웹 검색 결과 저장 ────────────────────────────────────────

    def save_web_search(
        self,
        query: str,
        results: list[dict],
        auto_tag: bool = True,
    ) -> int:
        """
        웹 검색 결과를 위키에 저장합니다.

        Args:
            query: 검색 쿼리
            results: 검색 결과 리스트 [{"title":..., "snippet":..., "url":...}]
            auto_tag: 자동 태깅 여부

        Returns:
            저장된 항목 ID
        """
        # 검색 결과를 하나의 위키 항목으로 통합
        content_parts = [f"## 웹 검색: {query}\n", f"_검색 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"]

        for i, r in enumerate(results[:8], 1):
            content_parts.append(
                f"### {i}. {r.get('title', '')}\n"
                f"{r.get('snippet', '')}\n"
                f"🔗 [{r.get('url', '')}]({r.get('url', '')})\n"
            )

        content = "\n".join(content_parts)
        tags = ["web-search", query.split()[0]] if auto_tag else ["web-search"]

        return self.add_entry(
            title=f"웹검색: {query}",
            content=content,
            category="web",
            tags=tags,
            source="web_search",
        )

    # ─── 통계 ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """위키 통계를 반환합니다."""
        conn = self._connect()

        total = conn.execute("SELECT COUNT(*) FROM wiki_entries").fetchone()[0]

        by_category = {}
        for row in conn.execute(
            "SELECT category, COUNT(*) as cnt FROM wiki_entries GROUP BY category"
        ):
            by_category[row["category"]] = row["cnt"]

        by_source = {}
        for row in conn.execute(
            "SELECT source, COUNT(*) as cnt FROM wiki_entries GROUP BY source"
        ):
            by_source[row["source"]] = row["cnt"]

        recent = []
        for row in conn.execute(
            "SELECT id, title, updated_at FROM wiki_entries ORDER BY updated_at DESC LIMIT 5"
        ):
            recent.append({"id": row["id"], "title": row["title"], "updated_at": row["updated_at"]})

        most_accessed = []
        for row in conn.execute(
            "SELECT id, title, access_count FROM wiki_entries ORDER BY access_count DESC LIMIT 5"
        ):
            most_accessed.append({"id": row["id"], "title": row["title"], "count": row["access_count"]})

        conn.close()

        return {
            "total_entries": total,
            "by_category": by_category,
            "by_source": by_source,
            "recent_entries": recent,
            "most_accessed": most_accessed,
        }

    # ─── 내부 유틸 ───────────────────────────────────────────────

    def _row_to_entry(self, row) -> WikiEntry:
        tags = json.loads(row["tags"]) if row["tags"] else []
        return WikiEntry(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            category=row["category"],
            tags=tags,
            source=row["source"],
            source_url=row["source_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
        )

    def _prepare_fts_query(self, query: str) -> str:
        """FTS5 쿼리 문법으로 변환."""
        # 특수문자 제거 + 단어별 OR 검색
        words = re.findall(r"[\w가-힣]+", query)
        if not words:
            return query
        return " OR ".join(words)

    def _log_access(self, conn: sqlite3.Connection, entry_id: int, query: str):
        """접근 이력 기록."""
        conn.execute(
            "UPDATE wiki_entries SET access_count = access_count + 1 WHERE id = ?",
            (entry_id,),
        )
        conn.execute(
            "INSERT INTO wiki_access_log (entry_id, query, accessed_at) VALUES (?, ?, ?)",
            (entry_id, query, datetime.now().isoformat()),
        )

    def _save_markdown(
        self,
        entry_id: int,
        title: str,
        content: str,
        category: str,
        tags: list[str],
    ):
        """위키 항목을 Markdown 파일로도 저장 (Obsidian 호환)."""
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:80]
        md_file = WIKI_DIR / category / f"{safe_title}.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)

        frontmatter = (
            f"---\n"
            f"id: {entry_id}\n"
            f"category: {category}\n"
            f"tags: {json.dumps(tags, ensure_ascii=False)}\n"
            f"created: {datetime.now().isoformat()}\n"
            f"---\n\n"
        )
        md_file.write_text(frontmatter + content, encoding="utf-8")


# ─── CLI 테스트 ──────────────────────────────────────────────────

if __name__ == "__main__":
    wiki = LLMWiki()

    # 테스트 항목 추가
    wiki.add_entry(
        "FastAPI 비동기 패턴",
        "FastAPI는 Starlette 기반의 ASGI 프레임워크로...",
        category="code",
        tags=["python", "fastapi", "async"],
    )

    # 검색
    hits = wiki.search("fastapi")
    for hit in hits:
        print(f"[{hit.score:.2f}] {hit.entry.title}")

    # 통계
    print(json.dumps(wiki.get_stats(), indent=2, ensure_ascii=False))
