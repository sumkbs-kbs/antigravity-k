from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from antigravity_k.tools.web_search_engine import WebSearchEngine
from antigravity_k.tools.web_search_models import SearchResult
from antigravity_k.tools.web_search_tool import WebSearchTool

SearchTuple = tuple[str, str, str]


def _patch(patcher: pytest.MonkeyPatch, target: object, name: str, value: object) -> None:
    patcher.setattr(target, name, value)


def _patch_path(patcher: pytest.MonkeyPatch, target: str, value: object) -> None:
    patcher.setattr(target, value)


def _cache_miss(_query: str, _force_refresh: bool = False) -> None:
    return None


def _fallback_queries(query: str) -> list[str]:
    return [query, "Qwen3.7 local model official"]


def _empty_sync(_query: str) -> list[SearchTuple]:
    return []


def _empty_content(_url: str, max_chars: int = 2000) -> str:
    _ = max_chars
    return ""


def _irrelevant_sync(_query: str, **_kwargs: object) -> list[SearchTuple]:
    return [
        ("Other local model", "https://example.com/other-model", "A different local model."),
        ("General overview", "https://example.com/overview", "Unrelated model news."),
    ]


def _irrelevant_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Other local model",
            url="https://example.com/other-model",
            snippet="A local model without the requested Qwen version.",
            relevance_score=0.9,
        ),
        SearchResult(
            title="General model overview",
            url="https://example.com/model-overview",
            snippet="An unrelated model overview.",
            relevance_score=0.8,
        ),
    ]


def _qwen_result() -> SearchResult:
    return SearchResult(
        title="Qwen3.7 local model",
        url="https://example.com/qwen37",
        snippet="Qwen3.7 runs locally with Ollama.",
        relevance_score=0.4,
    )


@pytest.mark.asyncio
async def test_async_search_augments_low_relevance_full_primary_results_with_jina():
    engine = WebSearchEngine(max_results=2)
    engine.self_hosted_url = "https://search.example"
    jina = AsyncMock(return_value=[_qwen_result()])

    with pytest.MonkeyPatch.context() as patcher:
        _patch(patcher, engine.cache, "get", _cache_miss)
        patcher.setattr(engine, "_search_self_hosted", AsyncMock(return_value=_irrelevant_results()))
        patcher.setattr(engine, "_search_searxng", AsyncMock(return_value=[]))
        patcher.setattr(engine, "_search_jina", jina)
        patcher.setattr(engine, "_search_duckduckgo", AsyncMock(return_value=[]))
        response = await engine.search("Qwen3.7 local model", use_cache=False)

    assert response.results[0].title == "Qwen3.7 local model"
    jina.assert_awaited_once_with("Qwen3.7 local model")


@pytest.mark.asyncio
async def test_async_search_augments_low_relevance_fallback_results_with_jina():
    engine = WebSearchEngine(max_results=2)
    engine.self_hosted_url = "https://search.example"
    jina = AsyncMock(side_effect=[[], [_qwen_result()]])

    with pytest.MonkeyPatch.context() as patcher:
        _patch(patcher, engine.cache, "get", _cache_miss)
        patcher.setattr(
            engine, "_search_self_hosted", AsyncMock(side_effect=[_irrelevant_results(), _irrelevant_results()])
        )
        patcher.setattr(engine, "_search_searxng", AsyncMock(return_value=[]))
        patcher.setattr(engine, "_search_jina", jina)
        patcher.setattr(engine, "_search_duckduckgo", AsyncMock(return_value=[]))
        _patch_path(patcher, "antigravity_k.tools.web_search_engine._generate_fallback_queries", _fallback_queries)
        response = await engine.search("Qwen3.7 local model", use_cache=False)

    assert response.results[0].title == "Qwen3.7 local model"
    assert jina.await_count == 2


@pytest.mark.asyncio
async def test_async_search_keeps_official_qwen_sources_when_providers_miss():
    engine = WebSearchEngine(max_results=2)
    engine.self_hosted_url = "https://search.example"

    with pytest.MonkeyPatch.context() as patcher:
        _patch(patcher, engine.cache, "get", _cache_miss)
        patcher.setattr(engine, "_search_self_hosted", AsyncMock(return_value=_irrelevant_results()))
        patcher.setattr(engine, "_search_searxng", AsyncMock(return_value=[]))
        patcher.setattr(engine, "_search_jina", AsyncMock(return_value=[]))
        patcher.setattr(engine, "_search_duckduckgo", AsyncMock(return_value=[]))
        response = await engine.search("Qwen3.6 local model Ollama", use_cache=False)

    assert {result.url for result in response.results} == {
        "https://github.com/QwenLM/Qwen3.6",
        "https://ollama.com/library/qwen3.6",
    }


def test_sync_tool_rewrites_full_low_relevance_results_and_promotes_rescue():
    tool = WebSearchTool()
    tool.max_results = 2
    relevant = [("Qwen3.7 local model", "https://example.com/qwen37", "Qwen3.7 runs locally.")]
    jina_queries: list[str] = []

    with pytest.MonkeyPatch.context() as patcher:
        def jina_search(query: str) -> list[SearchTuple]:
            jina_queries.append(query)
            return relevant if "official" in query else []

        _patch(patcher, tool, "_sync_search_self_hosted", _irrelevant_sync)
        _patch(patcher, tool, "_sync_search_searxng", _empty_sync)
        _patch(patcher, tool, "_sync_search_jina", jina_search)
        _patch(patcher, tool, "_sync_search_duckduckgo", _empty_sync)
        _patch(patcher, tool.engine, "_extract_content_jina", _empty_content)
        _patch_path(patcher, "antigravity_k.tools.web_search_tool._generate_fallback_queries", _fallback_queries)
        response = tool.execute(query="Qwen3.7 local model")

    assert "fallback" in response
    assert response.index("**Qwen3.7 local model**") < response.index("**Other local model**")
    assert jina_queries == ["Qwen3.7 local model official"]


def test_sync_tool_keeps_official_qwen_sources_when_providers_miss():
    tool = WebSearchTool()

    with pytest.MonkeyPatch.context() as patcher:
        _patch(patcher, tool, "_sync_search_self_hosted", _empty_sync)
        _patch(patcher, tool, "_sync_search_searxng", _empty_sync)
        _patch(patcher, tool, "_sync_search_jina", _empty_sync)
        _patch(patcher, tool, "_sync_search_duckduckgo", _empty_sync)
        _patch(patcher, tool.engine, "_extract_content_jina", _empty_content)
        response = tool.execute(query="Qwen3.6 local model Ollama")

    assert "https://github.com/QwenLM/Qwen3.6" in response
    assert "https://ollama.com/library/qwen3.6" in response
