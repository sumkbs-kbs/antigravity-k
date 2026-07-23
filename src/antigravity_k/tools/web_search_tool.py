"""웹 검색 도구 — 동기식 검색 + execute() 메서드.

WebSearchTool (BaseTool 래퍼), 동기식 검색 메서드들.
execute()의 큰 try 블록을 5개 private 메서드로 분해.
web_search.py에서 분리됨 (Phase 23 리팩토링).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional
from urllib.parse import quote_plus, unquote

import httpx

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory
from .web_search_cache import _generate_fallback_queries
from .web_search_engine import WebSearchEngine

logger = logging.getLogger("web_search")


class WebSearchTool(BaseTool):
    """Multi-Engine 웹 검색 도구.

    무료 기술 조합: Jina Search + DuckDuckGo + Jina Reader + wttr.in
    """

    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🔍"
    tags = ["search", "web", "jina", "duckduckgo", "multi-engine", "realtime"]

    def __init__(self) -> None:
        super().__init__()
        self._name = "web_search"
        self._description = (
            "Performs a real-time web search using multiple search engines "
            "(SearxNG + Jina AI + DuckDuckGo) to find current information. Automatically "
            "extracts page content from top results for deep analysis."
        )
        self.searxng_url = os.environ.get("SEARXNG_URL", "http://localhost:8080")
        self.tavily_api_key = os.environ.get("TAVILY_API_KEY")
        self.max_results = 8
        self._schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query. You MUST preserve the exact location names, "
                        "proper nouns, and keywords provided by the user without altering them."
                    ),
                },
                "depth": {
                    "type": "string",
                    "description": (
                        "Search depth. 'standard' for general search, "
                        "'deep' for comprehensive multi-page search. Default: 'standard'."
                    ),
                    "enum": ["standard", "deep"],
                },
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
    def parameters_schema(self) -> dict[str, Any]:
        return self._schema

    # ════════════════════════════════════════════════════════════════
    # execute() — 메인 진입점 (분해된 메서드들로 구성)
    # ════════════════════════════════════════════════════════════════

    def execute(self, **kwargs) -> Any:
        query = kwargs.get("query")
        if not query:
            return "Error: Missing query"

        depth = kwargs.get("depth", "standard")
        is_deep = depth == "deep"

        # 1. 종목코드 검증
        query = self._validate_stock_codes(query)

        try:
            # 2. Multi-Engine 검색
            all_results, engines_used = self._execute_multi_engine_search(query)

            # 3. Fallback: 결과 0건 → 대체 쿼리
            if not all_results:
                all_results, engines_used = self._execute_fallback(query)

            # 4. 중복 URL 제거
            results = _deduplicate_results(all_results)

            # 5. Deep 모드: 추가 결과
            if is_deep:
                results = self._execute_deep_search(query, results)

            if not results:
                return f"[웹 검색] '{query}' — 결과 없음"

            # 6. 응답 포맷팅
            return self._format_search_response(query, results, engines_used)

        except (httpx.RequestError, json.JSONDecodeError, KeyError, IndexError) as e:
            logger.exception("Search pipeline error")
            return f"Search Error: {e}"

    # ─── 1. 종목코드 검증 ─────────────────────────────────────────

    def _validate_stock_codes(self, query: str) -> str:
        """종목코드 검증 및 쿼리 보강. 실패 시 원본 쿼리 반환."""
        try:
            from antigravity_k.engine.stock_code_validator import (
                enrich_search_query,
                validate_query_stock_codes,
            )

            stock_validation = validate_query_stock_codes(query)
            if stock_validation.needs_correction:
                original = query
                query = enrich_search_query(query, stock_validation)
                logger.info(
                    "종목코드 자동 교정: '%s' → '%s' (잘못된 코드: %s)",
                    original[:60],
                    query[:60],
                    [v.original_code for v in stock_validation.codes_found if v.needs_correction],
                )
        except Exception:
            logger.debug("종목코드 검증 실패 (non-critical)", exc_info=True)
        return query

    # ─── 2. Multi-Engine 검색 ─────────────────────────────────────

    def _execute_multi_engine_search(self, query: str) -> tuple[list, list[str]]:
        """4개 엔진을 순차적으로 호출하여 결과를 수집합니다."""
        all_results = []
        engines_used: list[str] = []

        # 0차: Self-Hosted Search Engine
        self_hosted_results = self._sync_search_self_hosted(query)
        if self_hosted_results:
            all_results.extend(self_hosted_results)
            engines_used.append("SelfHosted")

        # 1차: SearxNG
        if len(all_results) < self.max_results:
            searxng_results = self._sync_search_searxng(query)
            if searxng_results:
                all_results.extend(searxng_results)
                engines_used.append("SearxNG")

        # 2차: Jina Search
        if len(all_results) < self.max_results:
            jina_results = self._sync_search_jina(query)
            if jina_results:
                all_results.extend(jina_results)
                engines_used.append("Jina")

        # 3차: DuckDuckGo (최종 폴백)
        if len(all_results) < self.max_results:
            ddg_results = self._sync_search_duckduckgo(query)
            if ddg_results:
                all_results.extend(ddg_results)
                engines_used.append("DuckDuckGo")

        return all_results, engines_used

    # ─── 3. Fallback 검색 ─────────────────────────────────────────

    def _execute_fallback(self, query: str) -> tuple[list, list[str]]:
        """결과 0건 시 대체 쿼리로 재시도합니다."""
        fallback_queries = _generate_fallback_queries(query)
        logger.info(
            "0건 결과, Fallback 쿼리 %d개 생성: %s",
            len(fallback_queries),
            fallback_queries[:3],
        )

        for fb_query in fallback_queries[1:4]:
            fb_results = self._sync_search_self_hosted(fb_query)
            if not fb_results:
                fb_results = self._sync_search_searxng(fb_query)
            if not fb_results:
                fb_results = self._sync_search_duckduckgo(fb_query)
            if fb_results:
                logger.info("Fallback 성공: '%s' → %d개", fb_query[:40], len(fb_results))
                return fb_results, ["fallback"]
        return [], []

    # ─── 4. Deep 모드 검색 ────────────────────────────────────────

    def _execute_deep_search(self, query: str, results: list) -> list:
        """Deep 모드: Self-Hosted 추가 결과 요청."""
        logger.info("Deep 모드: 추가 결과 요청 (query=%s)", query[:40])
        extra_results = self._sync_search_self_hosted(query, deep=True)
        if extra_results:
            seen = {r[1].rstrip("/").lower() for r in results}
            for r in extra_results:
                key = r[1].rstrip("/").lower()
                if key not in seen:
                    seen.add(key)
                    results.append(r)
            logger.info("Deep 검색 추가 결과: %d개", len(extra_results))
        return results

    # ─── 5. 응답 포맷팅 ───────────────────────────────────────────

    def _format_search_response(
        self,
        query: str,
        results: list,
        engines_used: list[str],
    ) -> str:
        """검색 결과를 LLM 친화적 문자열로 포맷팅합니다.

        Args:
            query: 원본 검색 쿼리
            results: [(title, url, snippet), ...] 튜플 리스트
            engines_used: 사용된 엔진 이름 리스트

        Returns:
            포맷팅된 결과 문자열 (날씨 데이터, TOP 1 분석, 구조화 데이터 포함)
        """
        engine_label = "+".join(engines_used) if engines_used else "none"
        lines = [
            f"[웹 검색 결과] 쿼리: '{query}' ({engine_label}, {len(results)}개)",
            "",
        ]

        content = ""  # TOP 1 본문 저장용

        # ── 날씨 데이터 주입 ──
        self._inject_weather_data(query, lines)

        # ── TOP 1 심층 분석 ──
        if results:
            content = self._inject_top1_analysis(results[0], query, lines)

        # ── 나머지 결과 ──
        for i, (title, url, snippet) in enumerate(results[1:5], 2):
            lines.append(f"{i}. **{title}**\n   {snippet}\n   🔗 {url}\n")

        # ── 구조화 데이터 추출 ──
        self._inject_structured_data(results, content, lines, query=query)

        # ── 시스템 인스트럭션 ──
        lines.append(self._get_citation_instruction())

        return "\n".join(lines)

    def _inject_weather_data(self, query: str, lines: list[str]):
        """날씨 쿼리 시 wttr.in 직통 데이터 주입."""
        if "날씨" not in query:
            return

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
                    lines.append(f"☁️ **[기상청/wttr.in 직통 데이터] 지역: {loc_query}**")
                    lines.append(f"```text\n{weather_ascii}\n```")
                    lines.append("")
        except httpx.RequestError:
            logger.warning("wttr.in 날씨 조회 실패 (non-critical)")

    def _inject_top1_analysis(self, top_result: tuple, query: str, lines: list[str]) -> str:
        """TOP 1 결과의 본문을 분석하여 주입합니다."""
        top_title, top_url, top_snippet = top_result
        lines.append(f"👑 **[TOP 1 심층 분석] {top_title}**")
        lines.append(f"🔗 {top_url}")

        # 1차: Jina Reader
        max_chars = 4000 if any(kw in query for kw in ("주가", "주식", "stock")) else 2000
        content = self.engine._extract_content_jina(top_url, max_chars=max_chars)
        if content:
            lines.append(f"📄 본문 마크다운 요약 (Jina Reader):\n{content}")
            return content

        # 2차: httpx 직접 스크래핑 폴백
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(top_url)
                if resp.status_code == 200:
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
                    fallback = text[:1500]
                    lines.append(f"📄 본문 요약 (Fallback): {fallback}...")
                    return fallback
                else:
                    lines.append(f"   (본문 스크래핑 실패: HTTP {resp.status_code}) - 스니펫: {top_snippet}")
        except httpx.RequestError as e:
            logger.warning("TOP 1 본문 스크래핑 실패: %s", e)
            lines.append(f"   (본문 스크래핑 실패: {e}) - 스니펫: {top_snippet}")

        lines.append("")
        return ""

    def _inject_structured_data(
        self,
        results: list,
        content: str,
        lines: list[str],
        query: str = "",
    ):
        """검색 결과에서 구조화 데이터를 추출하여 주입합니다."""
        try:
            from antigravity_k.engine.data_extractor import extract_structured_data

            all_texts = [snippet for (_, _, snippet) in results]
            if content:
                all_texts.append(content)

            structured = extract_structured_data(all_texts, query=query)
            if structured:
                lines.append("\n📊 **[구조화 데이터 추출]**:\n")
                lines.append(structured)
                lines.append(
                    "\n[중요] 위 구조화 데이터는 검색 결과에서 자동 추출된 값입니다. "
                    "답변 시 반드시 이 값들을 우선적으로 사용하고, "
                    "원본 검색 결과의 [N] 출처 번호도 함께 표기하세요.\n"
                )
        except Exception:
            logger.debug("데이터 추출 실패 (non-critical)", exc_info=True)

    @staticmethod
    def _get_citation_instruction() -> str:
        """Perplexity 스타일 인용 지시사항을 반환합니다."""
        return (
            "\n[SYSTEM INSTRUCTION: PERPLEXITY-STYLE SYNTHESIS & CITATION]\n"
            "위 검색 결과는 여러 출처에서 가져온 정보이며, "
            "특히 TOP 1 결과는 사이트 본문을 직접 읽어온 데이터입니다.\n"
            "1. **교차 검증 (Cross-validation)**: 반드시 여러 출처의 정보를 종합하여 "
            "모순이 없는지 확인하고, 단일 출처에만 의존하지 마세요.\n"
            "2. **인라인 인용구 (Inline Citations)**: 답변의 각 주장이나 팩트 끝에 "
            "해당 정보를 참조한 출처의 번호를 `[1]`, `[2]` 형식으로 반드시 표기하세요.\n"
            "3. 날씨 정보 등 수치가 중요한 경우, 스니펫보다 "
            "**[TOP 1 심층 분석]** 본문의 구체적 수치를 우선적으로 신뢰하세요."
        )

    # ════════════════════════════════════════════════════════════════
    # 동기식 검색 메서드들
    # ════════════════════════════════════════════════════════════════

    def _sync_search_self_hosted(
        self,
        query: str,
        max_results: Optional[int] = None,
        deep: bool = False,
    ) -> list:
        """자체 검색 엔진 (Cloudflare Pages 배포)을 통한 검색."""
        base_url = os.environ.get(
            "AGK_SEARCH_ENGINE_URL",
            "https://main.search-engine-api.pages.dev",
        ).rstrip("/")

        limit = max_results
        if limit is None:
            limit = self.max_results * 2 if deep else self.max_results

        timeout_sec = 20.0 if deep else 15.0
        snippet_max = 500 if deep else 300
        answer_label = "💡 AI Answer (Deep)" if deep else "💡 AI Answer"

        try:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
                resp = client.post(
                    f"{base_url}/api/search",
                    json={
                        "query": query,
                        "max_results": limit,
                        "include_answer": True,
                        "include_raw_content": deep,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []

                answer = data.get("answer")
                if answer and answer.get("text"):
                    results.append(
                        (
                            answer_label,
                            f"{base_url}/api/search?query={query}",
                            answer["text"][: 1000 if deep else 500],
                        )
                    )

                for item in data.get("results", [])[:limit]:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    snippet = item.get("content", "")[:snippet_max]

                    if deep:
                        raw = item.get("raw_content", "")
                        if raw:
                            snippet += f"\n[본문 발췌] {raw[:500]}"

                    stock = item.get("stock_data")
                    if stock:
                        snippet = (
                            f"📊 {stock.get('name', '')} ({stock.get('ticker', '')}) "
                            f"{stock.get('price', 0):,}원 "
                            f"{stock.get('change_percent', 0):+.2f}% "
                            f"({stock.get('direction', '')})\n{snippet}"
                        )

                    if title and url:
                        results.append((title, url, snippet))

                return results

        except httpx.RequestError:
            logger.warning("Self-hosted search 동기 오류", exc_info=True)
            return []

    def _sync_search_jina(self, query: str) -> list:
        """동기 Jina Search (s.jina.ai)."""
        try:
            headers = {"Accept": "application/json"}
            jina_key = os.environ.get("JINA_API_KEY")
            if jina_key:
                headers["Authorization"] = f"Bearer {jina_key}"

            with httpx.Client(timeout=12.0, follow_redirects=True) as client:
                resp = client.get(
                    f"https://s.jina.ai/{quote_plus(query)}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", data.get("results", []))

                results = []
                for item in items[:8]:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        url = item.get("url", "")
                        snippet = str(item.get("description", item.get("content", "")) or "")[:300]
                        if title and url:
                            results.append((title, url, snippet))
                return results

        except (httpx.RequestError, json.JSONDecodeError, ConnectionError):
            logger.warning("Jina Search 동기 오류", exc_info=True)
            return []

    def _sync_search_searxng(self, query: str) -> list:
        """동기 SearxNG 메타 검색."""
        if not self.searxng_url:
            return []

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{self.searxng_url}/search",
                    params={"q": query, "format": "json", "language": "ko-KR", "safesearch": 0},
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []
                for item in data.get("results", [])[: self.max_results]:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    snippet = item.get("content", "")
                    if title and url:
                        results.append((title, url, snippet))
                return results

        except httpx.RequestError:
            logger.debug("SearxNG 동기 검색 실패 (non-critical)")
            return []

    def _sync_search_duckduckgo(self, query: str) -> list:
        """동기 DuckDuckGo HTML 검색."""
        with httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        ) as client:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = client.get(url)
            if resp.status_code != 200:
                return []

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

            results = []
            for i, (url_raw, title_html) in enumerate(titles[:8]):
                title = re.sub(r"<[^>]+>", "", title_html).strip()
                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

                actual_url = url_raw
                if "uddg=" in url_raw:
                    match = re.search(r"uddg=([^&]+)", url_raw)
                    if match:
                        actual_url = unquote(match.group(1))

                if title and actual_url:
                    results.append((title, actual_url, snippet[:300]))

            return results


# ─── 유틸리티 함수 ──────────────────────────────────────────────


def _deduplicate_results(results: list) -> list:
    """중복 URL을 제거합니다 (먼저 들어온 결과 우선).

    Args:
        results: [(title, url, snippet), ...] 튜플 리스트

    Returns:
        중복 제거된 리스트
    """
    seen: set[str] = set()
    deduped: list = []
    for r in results:
        key = r[1].rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


__all__ = [
    "WebSearchTool",
    "_deduplicate_results",
]
