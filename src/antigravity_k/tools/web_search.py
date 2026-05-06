#!/usr/bin/env python3
"""
Antigravity-K: Multi-Engine 웹 서칭 엔진 (Web Search Tool)
==========================================================
로컬 LLM이 최신 정보에 접근할 수 있도록 무료 검색 기술 조합을 제공합니다.

무료 기술 조합:
    - Jina Search (s.jina.ai): 시맨틱 검색 그라운딩 (무료, API 키 선택적)
    - Jina Reader (r.jina.ai): URL→클린 마크다운 변환 (Playwright 대체)
    - DuckDuckGo: HTML 스크래핑 기반 검색 (최종 폴백)
    - SearXNG: 자체 호스팅 메타 검색 (선택적)
    - wttr.in: 날씨 전용 직통 데이터

아키텍처:
    검색: Jina Search → SearXNG → DuckDuckGo (폴백 체인 + 결과 병합)
    본문: Jina Reader → httpx 직접 스크래핑 (폴백)

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
    source: str = ""  # 검색 엔진 이름
    timestamp: str = ""  # 검색 시각
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

CACHE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "search_cache"
)


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

        # 실시간성이 중요한 키워드는 무조건 캐시를 무시 (날씨, 시간 등)
        realtime_keywords = [
            "날씨",
            "시간",
            "오늘",
            "내일",
            "뉴스",
            "주가",
            "환율",
            "현재",
        ]
        if any(kw in query for kw in realtime_keywords):
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
        # 실시간 키워드는 캐시에 아예 저장하지 않음
        realtime_keywords = [
            "날씨",
            "시간",
            "오늘",
            "내일",
            "뉴스",
            "주가",
            "환율",
            "현재",
        ]
        if any(kw in query for kw in realtime_keywords):
            return

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

        except Exception as e:
            logger.error(f"SearXNG 검색 오류: {e}")

        return results

    # ─── Jina Search (무료 시맨틱 검색 그라운딩) ──────────────────

    async def _search_jina(self, query: str) -> list[SearchResult]:
        """Jina AI Search Grounding (s.jina.ai) — 무료, API 키 선택적."""
        client = await self._get_client()
        results: list[SearchResult] = []

        try:
            import os

            headers = {"Accept": "application/json"}
            jina_key = os.environ.get("JINA_API_KEY")
            if jina_key:
                headers["Authorization"] = f"Bearer {jina_key}"

            url = f"https://s.jina.ai/{quote_plus(query)}"
            resp = await client.get(url, headers=headers, timeout=12.0)

            if resp.status_code != 200:
                logger.warning(f"Jina Search 응답 실패: {resp.status_code}")
                return results

            data = resp.json()
            items = (
                data
                if isinstance(data, list)
                else data.get("data", data.get("results", []))
            )

            for i, item in enumerate(items[: self.max_results]):
                if isinstance(item, dict):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("description", item.get("content", ""))[
                                :300
                            ],
                            source="Jina Search",
                            timestamp=datetime.now().isoformat(),
                            relevance_score=1.0 - (i * 0.08),
                        )
                    )
        except Exception as e:
            logger.warning(f"Jina Search 오류 (폴백 전환): {e}")

        return results

    # ─── Jina Reader (무료 URL→마크다운 변환) ─────────────────────

    def _extract_content_jina(self, url: str, max_chars: int = 2000) -> str:
        """Jina Reader (r.jina.ai) — URL을 클린 마크다운으로 변환 (Playwright 대체)."""
        import os

        try:
            headers = {"Accept": "text/markdown"}
            jina_key = os.environ.get("JINA_API_KEY")
            if jina_key:
                headers["Authorization"] = f"Bearer {jina_key}"

            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(f"https://r.jina.ai/{url}", headers=headers)
                if resp.status_code == 200:
                    text = resp.text.strip()
                    # 너무 짧으면 실패로 간주
                    if len(text) > 50:
                        return text[:max_chars]
            return ""
        except Exception as e:
            logger.warning(f"Jina Reader 오류: {e}")
            return ""

    # ─── 통합 검색 ───────────────────────────────────────────────

    async def search(self, query: str, use_cache: bool = True) -> SearchResponse:
        """
        Multi-Engine 통합 웹 검색.

        엔진 우선순위 (무료 기술 조합):
            1. 캐시 조회
            2. Jina Search (시맨틱 그라운딩, 무료)
            3. SearXNG (자체 호스팅, 설정 시)
            4. DuckDuckGo HTML (최종 폴백)
        결과를 병합하고 신뢰 도메인 기반 재정렬합니다.
        """
        start = time.time()

        # 1. 캐시 확인
        if use_cache:
            cached = self.cache.get(query)
            if cached:
                logger.info(f"캐시 히트: '{query}' ({len(cached.results)}개 결과)")
                return cached

        # 2. Multi-Engine 검색 (폴백 체인 + 결과 병합)
        all_results: list[SearchResult] = []
        engines_used: list[str] = []

        # 2a. Jina Search (무료 시맨틱 검색)
        jina_results = await self._search_jina(query)
        if jina_results:
            all_results.extend(jina_results)
            engines_used.append("jina")
            logger.info(f"Jina Search: {len(jina_results)}개 결과")

        # 2b. SearXNG (자체 호스팅)
        if self.searxng_url:
            searxng_results = await self._search_searxng(query)
            if searxng_results:
                all_results.extend(searxng_results)
                engines_used.append("searxng")
                logger.info(f"SearXNG: {len(searxng_results)}개 결과")

        # 2c. DuckDuckGo (폴백 또는 보완)
        if len(all_results) < 3:
            ddg_results = await self._search_duckduckgo(query)
            if ddg_results:
                all_results.extend(ddg_results)
                engines_used.append("duckduckgo")
                logger.info(f"DuckDuckGo: {len(ddg_results)}개 결과")

        # 3. 중복 URL 제거 (먼저 들어온 결과 우선)
        seen_urls: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            normalized = r.url.rstrip("/").lower()
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_results.append(r)

        # 4. 신뢰 도메인 기반 결과 재정렬 (Trusted Domains Boosting)
        trusted_domains = [
            "naver.com",
            "google.com",
            "daum.net",
            "kma.go.kr",
            "wikipedia.org",
            "namu.wiki",
        ]
        for r in unique_results:
            r.relevance_score = max(r.relevance_score, 1.0)
            if any(domain in r.url for domain in trusted_domains):
                r.relevance_score += 5.0
            if "weather" in query or "날씨" in query:
                if "weather.naver.com" in r.url or "kma.go.kr" in r.url:
                    r.relevance_score += 15.0

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

        logger.info(
            f"검색 완료: '{query}' → {len(final_results)}개 결과 "
            f"(엔진: {engine_label}, {elapsed:.0f}ms)"
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
                lines.append(
                    f"... (나머지 {len(response.results) - i + 1}개 결과 생략)"
                )
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
    Multi-Engine 웹 검색 도구.
    무료 기술 조합: Jina Search + DuckDuckGo + Jina Reader + wttr.in
    """

    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🔍"
    tags = ["search", "web", "jina", "duckduckgo", "multi-engine", "realtime"]

    def __init__(self):
        super().__init__()
        self._name = "web_search"
        self._description = (
            "Performs a real-time web search using multiple free search engines "
            "(Jina AI + DuckDuckGo) to find current information. Automatically "
            "extracts page content from top results for deep analysis."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. You MUST preserve the exact location names, proper nouns, and keywords provided by the user without altering them.",
                }
            },
            "required": ["query"],
        }
        self.engine = WebSearchEngine()

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def execute(self, **kwargs) -> Any:
        query = kwargs.get("query")
        if not query:
            return "Error: Missing query"

        try:
            # Multi-Engine 동기 검색: Jina → DuckDuckGo 폴백
            all_results = []
            engines_used = []

            # 1차: Jina Search (무료 시맨틱 검색)
            jina_results = self._sync_search_jina(query)
            if jina_results:
                all_results.extend(jina_results)
                engines_used.append("Jina")

            # 2차: DuckDuckGo (보완 또는 폴백)
            if len(all_results) < 3:
                ddg_results = self._sync_search_duckduckgo(query)
                if ddg_results:
                    all_results.extend(ddg_results)
                    engines_used.append("DuckDuckGo")

            # 중복 URL 제거
            seen = set()
            results = []
            for r in all_results:
                key = r[1].rstrip("/").lower()  # url
                if key not in seen:
                    seen.add(key)
                    results.append(r)

            if not results:
                return f"[웹 검색] '{query}' — 결과 없음"

            engine_label = "+".join(engines_used)
            lines = [
                f"[웹 검색 결과] 쿼리: '{query}' ({engine_label}, {len(results)}개)",
                "",
            ]

            # [기상청/wttr.in 직통 날씨 데이터 주입]
            if "날씨" in query:
                loc_query = (
                    query.replace("날씨", "")
                    .replace("오늘", "")
                    .replace("내일", "")
                    .replace("모레", "")
                    .replace("알려줘", "")
                    .strip()
                )
                if not loc_query:
                    loc_query = "Seoul"
                try:
                    with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                        resp = client.get(f"https://wttr.in/{loc_query}?T&M")
                        if resp.status_code == 200:
                            weather_ascii = re.sub(r"\x1b\[[0-9;]*m", "", resp.text)
                            lines.append(
                                f"☁️ **[기상청/wttr.in 직통 데이터] 지역: {loc_query}**"
                            )
                            lines.append(f"```text\n{weather_ascii}\n```")
                            lines.append("")
                except Exception:
                    pass

            # [TOP 1 심층 분석] Jina Reader로 본문 추출 (Playwright 대체)
            if results:
                top_title, top_url, top_snippet = results[0]
                lines.append(f"👑 **[TOP 1 심층 분석] {top_title}**")
                lines.append(f"🔗 {top_url}")

                # 1차: Jina Reader (r.jina.ai) — 무료, 클린 마크다운
                content = self.engine._extract_content_jina(top_url, max_chars=2000)
                if content:
                    lines.append(f"📄 본문 마크다운 요약 (Jina Reader):\n{content}")
                else:
                    # 2차: httpx 직접 스크래핑 폴백
                    try:
                        with httpx.Client(
                            timeout=10.0, follow_redirects=True
                        ) as client:
                            resp = client.get(top_url)
                            if resp.status_code == 200:
                                html = resp.text
                                for tag in [
                                    "script",
                                    "style",
                                    "nav",
                                    "footer",
                                    "header",
                                    "aside",
                                ]:
                                    html = re.sub(
                                        rf"<{tag}[^>]*>.*?</{tag}>",
                                        "",
                                        html,
                                        flags=re.DOTALL | re.IGNORECASE,
                                    )
                                text = re.sub(r"<[^>]+>", " ", html)
                                text = re.sub(r"\s+", " ", text).strip()
                                lines.append(
                                    f"📄 본문 요약 (Fallback): {text[:1500]}..."
                                )
                            else:
                                lines.append(
                                    f"   (본문 스크래핑 실패: HTTP {resp.status_code}) - 스니펫: {top_snippet}"
                                )
                    except Exception as e:
                        lines.append(
                            f"   (본문 스크래핑 실패: {e}) - 스니펫: {top_snippet}"
                        )
                lines.append("")

            # 나머지 결과는 스니펫 제공
            for i, (title, url, snippet) in enumerate(results[1:5], 2):
                lines.append(f"{i}. **{title}**\n   {snippet}\n   🔗 {url}\n")

            # Perplexity 스타일 인용 지시사항
            lines.append(
                "\n[SYSTEM INSTRUCTION: PERPLEXITY-STYLE SYNTHESIS & CITATION]\n"
                "위 검색 결과는 여러 출처에서 가져온 정보이며, 특히 TOP 1 결과는 사이트 본문을 직접 읽어온 데이터입니다.\n"
                "1. **교차 검증 (Cross-validation)**: 반드시 여러 출처의 정보를 종합하여 모순이 없는지 확인하고, 단일 출처에만 의존하지 마세요.\n"
                "2. **인라인 인용구 (Inline Citations)**: 답변의 각 주장이나 팩트 끝에 해당 정보를 참조한 출처의 번호를 `[1]`, `[2]` 형식으로 반드시 표기하세요.\n"
                "3. 날씨 정보 등 수치가 중요한 경우, 스니펫보다 **[TOP 1 심층 분석]** 본문의 구체적 수치를 우선적으로 신뢰하세요."
            )
            return "\n".join(lines)
        except Exception as e:
            return f"Search Error: {e}"

    # ─── 동기 Jina Search ──────────────────────────────────────

    def _sync_search_jina(self, query: str) -> list:
        """동기 Jina Search (s.jina.ai) — 무료 시맨틱 검색."""
        import os

        try:
            headers = {"Accept": "application/json"}
            jina_key = os.environ.get("JINA_API_KEY")
            if jina_key:
                headers["Authorization"] = f"Bearer {jina_key}"

            with httpx.Client(timeout=12.0, follow_redirects=True) as client:
                resp = client.get(
                    f"https://s.jina.ai/{quote_plus(query)}", headers=headers
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                items = (
                    data
                    if isinstance(data, list)
                    else data.get("data", data.get("results", []))
                )

                results = []
                for i, item in enumerate(items[:8]):
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        url = item.get("url", "")
                        snippet = item.get("description", item.get("content", ""))[:300]
                        if title and url:
                            results.append((title, url, snippet))
                return results
        except Exception as e:
            logger.warning(f"Jina Search 동기 오류: {e}")
            return []

    # ─── 동기 DuckDuckGo ───────────────────────────────────────

    def _sync_search_duckduckgo(self, query: str) -> list:
        """동기 DuckDuckGo HTML 검색 (스레드 안전)."""
        import re as _re
        from urllib.parse import quote_plus, unquote

        with httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
            follow_redirects=True,
        ) as client:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = client.get(url)
            if resp.status_code != 200:
                return []

            html = resp.text
            title_pattern = _re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                _re.DOTALL,
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
                    results.append(
                        {
                            "title": title,
                            "url": actual_url,
                            "snippet": snippet,
                            "score": 1.0,
                        }
                    )

            # 신뢰 도메인 가중치 부여 (Sync 모드)
            trusted_domains = [
                "naver.com",
                "google.com",
                "daum.net",
                "kma.go.kr",
                "wikipedia.org",
                "namu.wiki",
            ]
            for r in results:
                if any(domain in r["url"] for domain in trusted_domains):
                    r["score"] += 5.0
                if "weather" in query or "날씨" in query:
                    if "weather.naver.com" in r["url"] or "kma.go.kr" in r["url"]:
                        r["score"] += 15.0

            # 점수순 내림차순 정렬 후 튜플 형태로 변환
            results.sort(key=lambda x: x["score"], reverse=True)
            return [(r["title"], r["url"], r["snippet"]) for r in results]


# ─── CLI 테스트 ──────────────────────────────────────────────────

if __name__ == "__main__":

    async def main():
        engine = WebSearchEngine()
        result = await engine.search("Python 3.13 새로운 기능")
        print(engine.format_for_llm(result))
        print(f"\n사용 엔진: {result.engine}")
        await engine.close()

    asyncio.run(main())
