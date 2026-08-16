from unittest.mock import AsyncMock

import pytest

from antigravity_k.tools.web_search_engine import WebSearchEngine
from antigravity_k.tools.web_search_models import SearchResult
from antigravity_k.tools.web_search_tool import WebSearchTool


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
        patcher.setattr(engine.cache, "get", lambda query, force_refresh=False: None)
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
        patcher.setattr(engine.cache, "get", lambda query, force_refresh=False: None)
        patcher.setattr(
            engine, "_search_self_hosted", AsyncMock(side_effect=[_irrelevant_results(), _irrelevant_results()])
        )
        patcher.setattr(engine, "_search_searxng", AsyncMock(return_value=[]))
        patcher.setattr(engine, "_search_jina", jina)
        patcher.setattr(engine, "_search_duckduckgo", AsyncMock(return_value=[]))
        patcher.setattr(
            "antigravity_k.tools.web_search_engine._generate_fallback_queries",
            lambda query: [query, "Qwen3.7 local model official"],
        )
        response = await engine.search("Qwen3.7 local model", use_cache=False)

    assert response.results[0].title == "Qwen3.7 local model"
    assert jina.await_count == 2


@pytest.mark.asyncio
async def test_async_search_keeps_official_qwen_sources_when_providers_miss():
    engine = WebSearchEngine(max_results=2)
    engine.self_hosted_url = "https://search.example"

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(engine.cache, "get", lambda query, force_refresh=False: None)
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
    irrelevant = [
        ("Other local model", "https://example.com/other-model", "A different local model."),
        ("General overview", "https://example.com/overview", "Unrelated model news."),
    ]
    relevant = [("Qwen3.7 local model", "https://example.com/qwen37", "Qwen3.7 runs locally.")]
    jina_queries: list[str] = []

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(tool, "_sync_search_self_hosted", lambda query, **kwargs: irrelevant)
        patcher.setattr(tool, "_sync_search_searxng", lambda query: [])
        patcher.setattr(
            tool,
            "_sync_search_jina",
            lambda query: jina_queries.append(query) or (relevant if "official" in query else []),
        )
        patcher.setattr(tool, "_sync_search_duckduckgo", lambda query: [])
        patcher.setattr(tool.engine, "_extract_content_jina", lambda url, max_chars=2000: "")
        patcher.setattr(
            "antigravity_k.tools.web_search_tool._generate_fallback_queries",
            lambda query: [query, "Qwen3.7 local model official"],
        )
        response = tool.execute(query="Qwen3.7 local model")

    assert "fallback" in response
    assert response.index("**Qwen3.7 local model**") < response.index("**Other local model**")
    assert jina_queries == ["Qwen3.7 local model official"]


def test_sync_tool_keeps_official_qwen_sources_when_providers_miss():
    tool = WebSearchTool()

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(tool, "_sync_search_self_hosted", lambda query, **kwargs: [])
        patcher.setattr(tool, "_sync_search_searxng", lambda query: [])
        patcher.setattr(tool, "_sync_search_jina", lambda query: [])
        patcher.setattr(tool, "_sync_search_duckduckgo", lambda query: [])
        patcher.setattr(tool.engine, "_extract_content_jina", lambda url, max_chars=2000: "")
        response = tool.execute(query="Qwen3.6 local model Ollama")

    assert "https://github.com/QwenLM/Qwen3.6" in response
    assert "https://ollama.com/library/qwen3.6" in response
