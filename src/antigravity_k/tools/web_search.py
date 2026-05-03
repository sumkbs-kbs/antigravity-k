#!/usr/bin/env python3
"""
Antigravity-K: 웹 서칭 엔진 (Web Search Tool)
==============================================
로컬 LLM이 최신 정보에 접근할 수 있도록 자체 웹 검색 기능을 제공합니다.

특징:
    - DuckDuckGo 기반 검색 (API 키 불필요, 에어갭 친화)
    - SearXNG 자체 호스팅 검색 지원 (선택적)
    - 검색 결과 자동 요약 → LLM 컨텍스트에 주입
    - 결과를 LLM Wiki에 자동 저장하는 옵션

사용법:
    from antigravity_k.tools.web_search import WebSearchEngine

    engine = WebSearchEngine()
    results = await engine.search("FastAPI 최신 버전")
    summary = await engine.search_and_summarize("Python 3.13 새 기능")
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote_plus

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

import httpx

logger = logging.getLogger("web_search")

# ─── 데이터 모델 ──────────────────────────────────────────────────


@dataclass
class SearchResult:
    """단일 검색 결과."""

    title: str
    url: str
    snippet: str
    source: str = ""           # 검색 엔진 이름
    timestamp: str = ""        # 검색 시각
    relevance_score: float = 0.0


@dataclass
class SearchResponse:
    """검색 응답 전체."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0
    search_time_ms: float = 0.0
    engine: str = "duckduckgo"
    cached: bool = False


# ─── 검색 캐시 ────────────────────────────────────────────────────

CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "search_cache"


class SearchCache:
    """검색 결과 로컬 캐시 (디스크 기반)."""

    def __init__(self, ttl_hours: int = 24):
        self.ttl_hours = ttl_hours
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, query: str) -> str:
        """쿼리를 안전한 파일명으로 변환."""
        safe = re.sub(r"[^\w\s-]", "", query.lower()).strip()
        safe = re.sub(r"\s+", "_", safe)
        return safe[:80]

    def get(self, query: str) -> Optional[SearchResponse]:
        """캐시에서 결과 조회."""
        key = self._cache_key(query)
        cache_file = CACHE_DIR / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            # TTL 확인
            cached_time = datetime.fromisoformat(data.get("cached_at", ""))
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600

            if age_hours > self.ttl_hours:
                cache_file.unlink(missing_ok=True)
                return None

            results = [SearchResult(**r) for r in data.get("results", [])]
            return SearchResponse(
                query=data["query"],
                results=results,
                total_results=len(results),
                engine=data.get("engine", "cache"),
                cached=True,
            )
        except Exception as e:
            logger.warning(f"캐시 읽기 실패: {e}")
            return None

    def set(self, query: str, response: SearchResponse):
        """검색 결과를 캐시에 저장."""
        key = self._cache_key(query)
        cache_file = CACHE_DIR / f"{key}.json"

        data = {
            "query": query,
            "cached_at": datetime.now().isoformat(),
            "engine": response.engine,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                    "timestamp": r.timestamp,
                    "relevance_score": r.relevance_score,
                }
                for r in response.results
            ],
        }
        cache_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ─── 검색 엔진 ────────────────────────────────────────────────────


class WebSearchEngine:
    """
    통합 웹 검색 엔진.

    검색 우선순위:
        1. 로컬 캐시 조회
        2. SearXNG (자체 호스팅, 설정 시)
        3. DuckDuckGo HTML API (기본)

    Args:
        searxng_url: SearXNG 인스턴스 URL (선택)
        max_results: 최대 결과 수
        cache_ttl_hours: 캐시 유효 시간
    """

    def __init__(
        self,
        searxng_url: Optional[str] = None,
        max_results: int = 8,
        cache_ttl_hours: int = 24,
    ):
        self.searxng_url = searxng_url
        self.max_results = max_results
        self.cache = SearchCache(ttl_hours=cache_ttl_hours)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/125.0.0.0 Safari/537.36",
                },
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """HTTP 클라이언트 종료."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─── DuckDuckGo 검색 ─────────────────────────────────────────

    async def _search_duckduckgo(self, query: str) -> list[SearchResult]:
        """DuckDuckGo HTML 검색 (API 키 불필요)."""
        client = await self._get_client()
        results: list[SearchResult] = []

        try:
            # DuckDuckGo HTML Lite 버전 사용
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning(f"DuckDuckGo 응답 실패: {resp.status_code}")
                return results

            html = resp.text

            # 간단한 HTML 파싱 (BeautifulSoup 의존성 제거)
            # <a class="result__a" href="...">제목</a>
            # <a class="result__snippet">스니펫</a>
            title_pattern = re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL,
            )
            snippet_pattern = re.compile(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL,
            )

            titles = title_pattern.findall(html)
            snippets = snippet_pattern.findall(html)

            for i, (url_raw, title_html) in enumerate(titles[: self.max_results]):
                title = re.sub(r"<[^>]+>", "", title_html).strip()
                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

                # DuckDuckGo는 리다이렉트 URL을 사용 — 실제 URL 추출
                actual_url = url_raw
                if "uddg=" in url_raw:
                    match = re.search(r"uddg=([^&]+)", url_raw)
                    if match:
                        from urllib.parse import unquote
                        actual_url = unquote(match.group(1))

                if title and actual_url:
                    results.append(SearchResult(
                        title=title,
                        url=actual_url,
                        snippet=snippet,
                        source="DuckDuckGo",
                        timestamp=datetime.now().isoformat(),
                        relevance_score=1.0 - (i * 0.1),
                    ))

        except Exception as e:
            logger.error(f"DuckDuckGo 검색 오류: {e}")

        return results

    # ─── SearXNG 검색 ────────────────────────────────────────────

    async def _search_searxng(self, query: str) -> list[SearchResult]:
        """SearXNG 자체 호스팅 검색 엔진."""
        if not self.searxng_url:
            return []

        client = await self._get_client()
        results: list[SearchResult] = []

        try:
            url = f"{self.searxng_url}/search"
            params = {
                "q": query,
                "format": "json",
                "language": "ko-KR",
                "safesearch": 0,
            }
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.warning(f"SearXNG 응답 실패: {resp.status_code}")
                return results

            data = resp.json()
            for i, item in enumerate(data.get("results", [])[: self.max_results]):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source=f"SearXNG/{item.get('engine', '')}",
                    timestamp=datetime.now().isoformat(),
                    relevance_score=item.get("score", 1.0 - i * 0.1),
                ))

        except Exception as e:
            logger.error(f"SearXNG 검색 오류: {e}")

        return results

    # ─── 통합 검색 ───────────────────────────────────────────────

    async def search(self, query: str, use_cache: bool = True) -> SearchResponse:
        """
        통합 웹 검색을 실행합니다.

        Args:
            query: 검색 쿼리
            use_cache: 캐시 사용 여부

        Returns:
            SearchResponse: 검색 결과
        """
        start = time.time()

        # 1. 캐시 확인
        if use_cache:
            cached = self.cache.get(query)
            if cached:
                logger.info(f"캐시 히트: '{query}' ({len(cached.results)}개 결과)")
                return cached

        # 2. SearXNG 시도 → 실패 시 DuckDuckGo 폴백
        results: list[SearchResult] = []
        engine_used = "duckduckgo"

        if self.searxng_url:
            results = await self._search_searxng(query)
            if results:
                engine_used = "searxng"

        if not results:
            results = await self._search_duckduckgo(query)
            engine_used = "duckduckgo"

        elapsed = (time.time() - start) * 1000

        response = SearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=round(elapsed, 1),
            engine=engine_used,
        )

        # 3. 캐시 저장
        if results:
            self.cache.set(query, response)

        logger.info(
            f"검색 완료: '{query}' → {len(results)}개 결과 "
            f"({engine_used}, {elapsed:.0f}ms)"
        )
        return response

    # ─── LLM 컨텍스트 생성 ───────────────────────────────────────

    def format_for_llm(self, response: SearchResponse, max_chars: int = 3000) -> str:
        """
        검색 결과를 LLM이 이해할 수 있는 포맷으로 변환합니다.

        이 텍스트가 LLM의 system/user 메시지에 주입됩니다.
        """
        if not response.results:
            return f"[웹 검색] '{response.query}' — 결과 없음"

        lines = [
            f"[웹 검색 결과] 쿼리: '{response.query}' "
            f"({response.engine}, {len(response.results)}개)",
            "",
        ]

        chars_used = len(lines[0])
        for i, r in enumerate(response.results, 1):
            entry = f"{i}. **{r.title}**\n   {r.snippet}\n   🔗 {r.url}\n"
            if chars_used + len(entry) > max_chars:
                lines.append(f"... (나머지 {len(response.results) - i + 1}개 결과 생략)")
                break
            lines.append(entry)
            chars_used += len(entry)

        return "\n".join(lines)

    async def search_and_summarize(self, query: str) -> str:
        """검색 후 LLM 컨텍스트 포맷으로 반환하는 원스텝 API."""
        response = await self.search(query)
        return self.format_for_llm(response)


# ─── 웹 페이지 스크래핑 (선택적) ──────────────────────────────────


class PageScraper:
    """
    검색 결과 URL의 본문을 추출합니다.
    (requests/BeautifulSoup 없이 순수 httpx + 정규식)
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Antigravity-K/1.0)",
                },
            )
        return self._client

    async def extract_text(self, url: str, max_chars: int = 5000) -> str:
        """URL에서 본문 텍스트를 추출합니다."""
        client = await self._get_client()

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return f"[HTTP {resp.status_code}]"

            html = resp.text

            # <script>, <style>, <nav>, <footer> 제거
            for tag in ["script", "style", "nav", "footer", "header", "aside"]:
                html = re.sub(
                    rf"<{tag}[^>]*>.*?</{tag}>",
                    "",
                    html,
                    flags=re.DOTALL | re.IGNORECASE,
                )

            # HTML 태그 제거
            text = re.sub(r"<[^>]+>", " ", html)
            # 공백 정리
            text = re.sub(r"\s+", " ", text).strip()
            # 길이 제한
            return text[:max_chars]

        except Exception as e:
            return f"[스크래핑 오류: {e}]"

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ─── 에이전트 도구 (Tool) 래퍼 ────────────────────────────────────────

class WebSearchTool(BaseTool):
    """
    로컬 에이전트가 실시간 웹 검색을 수행할 수 있도록 하는 도구입니다.
    """
    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🔍"
    tags = ["search", "web", "duckduckgo", "realtime"]

    def __init__(self):
        super().__init__()
        self._name = "web_search"
        self._description = (
            "Performs a real-time web search to find current information, documentation, "
            "or specific URLs. Use this when you need up-to-date information that might not "
            "be in your training data."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query."
                }
            },
            "required": ["query"]
        }
        self.engine = WebSearchEngine()

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        query = kwargs.get("query")
        if not query:
            return "Error: Missing query"

        try:
            # 동기 httpx.Client를 사용하여 FastAPI 이벤트 루프 충돌 방지
            results = self._sync_search_duckduckgo(query)
            if not results:
                return f"[웹 검색] '{query}' — 결과 없음"

            lines = [
                f"[웹 검색 결과] 쿼리: '{query}' (DuckDuckGo, {len(results)}개)",
                "",
            ]
            for i, (title, url, snippet) in enumerate(results[:8], 1):
                lines.append(f"{i}. **{title}**\n   {snippet}\n   🔗 {url}\n")
            return "\n".join(lines)
        except Exception as e:
            return f"Search Error: {e}"

    def _sync_search_duckduckgo(self, query: str) -> list:
        """동기 DuckDuckGo HTML 검색 (스레드 안전)."""
        import re as _re
        from urllib.parse import quote_plus, unquote

        with httpx.Client(
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            follow_redirects=True,
        ) as client:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = client.get(url)
            if resp.status_code != 200:
                return []

            html = resp.text
            title_pattern = _re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', _re.DOTALL
            )
            snippet_pattern = _re.compile(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', _re.DOTALL
            )

            titles = title_pattern.findall(html)
            snippets = snippet_pattern.findall(html)

            results = []
            for i, (url_raw, title_html) in enumerate(titles[:8]):
                title = _re.sub(r"<[^>]+>", "", title_html).strip()
                snippet = ""
                if i < len(snippets):
                    snippet = _re.sub(r"<[^>]+>", "", snippets[i]).strip()

                actual_url = url_raw
                if "uddg=" in url_raw:
                    match = _re.search(r"uddg=([^&]+)", url_raw)
                    if match:
                        actual_url = unquote(match.group(1))

                if title and actual_url:
                    results.append((title, actual_url, snippet))
            return results

# ─── CLI 테스트 ──────────────────────────────────────────────────

if __name__ == "__main__":
    async def main():
        engine = WebSearchEngine()
        result = await engine.search("Python 3.13 새로운 기능")
        print(engine.format_for_llm(result))
        await engine.close()

    asyncio.run(main())
