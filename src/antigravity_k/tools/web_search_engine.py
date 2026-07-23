"""웹 검색 엔진 — 비동기 Multi-Engine 검색.

WebSearchEngine (async search), PageScraper (URL 본문 추출).
web_search.py에서 분리됨 (Phase 23 리팩토링).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

import httpx

from .web_search_cache import SearchCache, _generate_fallback_queries  # noqa: F811
from .web_search_models import SearchResponse, SearchResult

logger = logging.getLogger("web_search")


class WebSearchEngine:
    """통합 웹 검색 엔진.

    검색 우선순위:
        1. 로컬 캐시 조회
        2. Tavily AI (API 키 설정 시)
        3. SearXNG (자체 호스팅)
        4. Jina Search (무료 시맨틱 검색)
        5. DuckDuckGo HTML (최종 폴백)

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
    ) -> None:
        self.searxng_url = searxng_url or os.environ.get("SEARXNG_URL", "http://localhost:8080")
        self.tavily_api_key = os.environ.get("TAVILY_API_KEY")
        self.max_results = max_results
        self.cache: SearchCache = SearchCache(ttl_hours=cache_ttl_hours)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
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
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning("DuckDuckGo 응답 실패: %s", resp.status_code)
                return results

            html = resp.text
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

                actual_url = url_raw
                if "uddg=" in url_raw:
                    match = re.search(r"uddg=([^&]+)", url_raw)
                    if match:
                        from urllib.parse import unquote

                        actual_url = unquote(match.group(1))

                if title and actual_url:
                    results.append(
                        SearchResult(
                            title=title,
                            url=actual_url,
                            snippet=snippet,
                            source="DuckDuckGo",
                            timestamp=datetime.now().isoformat(),
                            relevance_score=1.0 - (i * 0.1),
                        )
                    )
        except httpx.RequestError:
            logger.warning("DuckDuckGo 검색 오류")

        return results

    # ─── Tavily AI 검색 ───────────────────────────────────────────

    async def _search_tavily(self, query: str) -> list[SearchResult]:
        """Tavily AI API — LLM-Ready 정제 데이터."""
        if not self.tavily_api_key:
            return []

        client = await self._get_client()
        results: list[SearchResult] = []

        try:
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": self.max_results,
            }
            resp = await client.post("https://api.tavily.com/search", json=payload, timeout=15.0)

            if resp.status_code != 200:
                return results

            data = resp.json()
            for i, item in enumerate(data.get("results", [])[: self.max_results]):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        source="Tavily AI",
                        timestamp=datetime.now().isoformat(),
                        relevance_score=item.get("score", 1.0 - i * 0.1),
                    )
                )
        except httpx.RequestError:
            logger.warning("Tavily AI 검색 오류")

        return results

    # ─── SearXNG 검색 ────────────────────────────────────────────

    async def _search_searxng(self, query: str) -> list[SearchResult]:
        """SearXNG 자체 호스팅 검색 엔진."""
        if not self.searxng_url:
            return []

        client = await self._get_client()
        results: list[SearchResult] = []

        try:
            params = {
                "q": query,
                "format": "json",
                "language": "ko-KR",
                "safesearch": 0,
            }
            resp = await client.get(f"{self.searxng_url}/search", params=params)

            if resp.status_code != 200:
                return results

            data = resp.json()
            for i, item in enumerate(data.get("results", [])[: self.max_results]):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        source=f"SearXNG/{item.get('engine', '')}",
                        timestamp=datetime.now().isoformat(),
                        relevance_score=item.get("score", 1.0 - i * 0.1),
                    )
                )
        except httpx.RequestError:
            logger.warning("SearXNG 검색 오류")

        return results

    # ─── Jina Search ──────────────────────────────────────────────

    async def _search_jina(self, query: str) -> list[SearchResult]:
        """Jina AI Search Grounding (s.jina.ai) — 무료, API 키 선택적."""
        client = await self._get_client()
        results: list[SearchResult] = []

        try:
            headers = {"Accept": "application/json"}
            jina_key = os.environ.get("JINA_API_KEY")
            if jina_key:
                headers["Authorization"] = f"Bearer {jina_key}"

            resp = await client.get(
                f"https://s.jina.ai/{quote_plus(query)}",
                headers=headers,
                timeout=12.0,
            )

            if resp.status_code != 200:
                return results

            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", data.get("results", []))

            for i, item in enumerate(items[: self.max_results]):
                if isinstance(item, dict):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=str(item.get("description", item.get("content", "")) or "")[:300],
                            source="Jina Search",
                            timestamp=datetime.now().isoformat(),
                            relevance_score=1.0 - (i * 0.08),
                        )
                    )
        except (httpx.RequestError, json.JSONDecodeError):
            logger.warning("Jina Search 오류 (폴백 전환)")

        return results

    # ─── Jina Reader ──────────────────────────────────────────────

    def _extract_content_jina(self, url: str, max_chars: int = 2000) -> str:
        """Jina Reader (r.jina.ai) — URL을 클린 마크다운으로 변환."""
        try:
            headers = {"Accept": "text/markdown"}
            jina_key = os.environ.get("JINA_API_KEY")
            if jina_key:
                headers["Authorization"] = f"Bearer {jina_key}"

            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(f"https://r.jina.ai/{url}", headers=headers)
                if resp.status_code == 200:
                    text = resp.text.strip()
                    if len(text) > 50:
                        return text[:max_chars]
            return ""
        except httpx.RequestError:
            logger.warning("Jina Reader 오류", exc_info=True)
            return ""

    # ─── 통합 검색 ───────────────────────────────────────────────

    async def search(
        self,
        query: str,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> SearchResponse:
        """Multi-Engine 통합 웹 검색.

        엔진 우선순위:
            1. 캐시 조회 (force_refresh=False일 때)
            2. Tavily AI (LLM 친화적, 키 설정 시)
            3. SearXNG (메타 검색 — Google+Bing+DDG 집계)
            4. Jina Search (시맨틱 그라운딩, 무료)
            5. DuckDuckGo HTML (최종 폴백)
            6. Fallback: 대체 쿼리로 재시도

        Args:
            query: 검색 쿼리
            use_cache: 캐시 사용 여부
            force_refresh: True면 캐시 무시하고 새로 검색
        """
        start = time.time()

        # 1. 캐시 확인
        if use_cache and not force_refresh:
            cached = self.cache.get(query, force_refresh=False)
            if cached:
                logger.info("캐시 히트: '%s' (%d개 결과)", query, len(cached.results))
                return cached

        # 2. Multi-Engine 검색
        all_results: list[SearchResult] = []
        engines_used: list[str] = []

        # 2a. Tavily AI
        if self.tavily_api_key:
            tavily_results = await self._search_tavily(query)
            if tavily_results:
                all_results.extend(tavily_results)
                engines_used.append("tavily")

        # 2b. SearXNG
        if self.searxng_url and len(all_results) < self.max_results:
            searxng_results = await self._search_searxng(query)
            if searxng_results:
                all_results.extend(searxng_results)
                engines_used.append("searxng")

        # 2c. Jina Search
        if len(all_results) < self.max_results:
            jina_results = await self._search_jina(query)
            if jina_results:
                all_results.extend(jina_results)
                engines_used.append("jina")

        # 2d. DuckDuckGo (폴백)
        if len(all_results) < self.max_results:
            ddg_results = await self._search_duckduckgo(query)
            if ddg_results:
                all_results.extend(ddg_results)
                engines_used.append("duckduckgo")

        # 2e. Fallback: 모든 엔진 결과 0건 → 대체 쿼리
        if not all_results:
            fallback_queries = _generate_fallback_queries(query)
            for fb_query in fallback_queries[1:4]:
                fb_results = await self._search_searxng(fb_query)
                if not fb_results:
                    fb_results = await self._search_duckduckgo(fb_query)
                if fb_results:
                    all_results.extend(fb_results)
                    engines_used.append("fallback")
                    break

        # 3. 중복 URL 제거
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            normalized = r.url.rstrip("/").lower()
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_results.append(r)

        # 4. 신뢰 도메인 기반 재정렬
        _boost_by_trusted_domains(unique_results, query)

        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
        final_results = unique_results[: self.max_results]

        elapsed = (time.time() - start) * 1000
        engine_label = "+".join(engines_used) if engines_used else "none"

        response = SearchResponse(
            query=query,
            results=final_results,
            total_results=len(final_results),
            search_time_ms=round(elapsed, 1),
            engine=engine_label,
        )

        if final_results:
            self.cache.set(query, response)

        return response

    # ─── LLM 컨텍스트 생성 ──────────────────────────────────────

    def format_for_llm(self, response: SearchResponse, max_chars: int = 3000) -> str:
        """검색 결과를 LLM이 이해할 수 있는 포맷으로 변환합니다."""
        if not response.results:
            return f"[웹 검색] '{response.query}' — 결과 없음"

        lines = [
            f"[웹 검색 결과] 쿼리: '{response.query}' ({response.engine}, {len(response.results)}개)",
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


# ─── 신뢰 도메인 부스팅 ──────────────────────────────────────────


def _boost_by_trusted_domains(results: list[SearchResult], query: str):
    """신뢰 도메인 기반 relevance_score 부스팅."""
    trusted_domains = [
        "naver.com",
        "google.com",
        "daum.net",
        "kma.go.kr",
        "wikipedia.org",
        "namu.wiki",
    ]
    for r in results:
        if any(domain in r.url for domain in trusted_domains):
            r.relevance_score += 5.0
        if "weather" in query or "날씨" in query:
            if "weather.naver.com" in r.url or "kma.go.kr" in r.url:
                r.relevance_score += 15.0


# ─── 웹 페이지 스크래핑 ──────────────────────────────────────────


class PageScraper:
    """검색 결과 URL의 본문을 추출합니다. (httpx + 정규식)"""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Antigravity-K/1.0)"},
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
            for tag in ["script", "style", "nav", "footer", "header", "aside"]:
                html = re.sub(
                    rf"<{tag}[^>]*>.*?</{tag}>",
                    "",
                    html,
                    flags=re.DOTALL | re.IGNORECASE,
                )

            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]

        except Exception as e:
            return f"[스크래핑 오류: {e}]"

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


__all__ = [
    "WebSearchEngine",
    "PageScraper",
    "_boost_by_trusted_domains",
]
