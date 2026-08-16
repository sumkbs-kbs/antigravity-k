from datetime import UTC, datetime

import pytest

from antigravity_k.tools.search_benchmark import run_search_benchmark, run_search_load_benchmark
from antigravity_k.tools.search_quality_evaluator import SearchGoldenCase
from antigravity_k.tools.web_search_models import SearchResponse, SearchResult


class FakeSearchEngine:
    async def search(self, query: str, use_cache: bool = True, force_refresh: bool = False) -> SearchResponse:
        assert use_cache is True
        assert force_refresh is True
        return SearchResponse(
            query=query,
            engine="fake",
            search_time_ms=12.5,
            results=[
                SearchResult(
                    title="Python release notes",
                    url="https://docs.python.org/3/whatsnew/3.13.html",
                    snippet="Python 3.13 release notes.",
                    timestamp=datetime.now(UTC).isoformat(),
                ),
                SearchResult(
                    title="Python downloads",
                    url="https://www.python.org/downloads/release/python-3130/",
                    snippet="Python 3.13.0 release.",
                ),
            ],
        )


@pytest.mark.asyncio
async def test_search_benchmark_forces_refresh_and_aggregates_retrieval_metrics():
    case = SearchGoldenCase(
        case_id="python-313-release",
        query="Python 3.13 release date",
        relevant_urls=(
            "https://docs.python.org/3/whatsnew/3.13.html",
            "https://www.python.org/downloads/release/python-3130/",
        ),
    )

    report = await run_search_benchmark(FakeSearchEngine(), [case], k=2)

    assert report.results[0].engine == "fake"
    assert report.results[0].quality.precision_at_k == 1.0
    assert report.results[0].quality.recall_at_k == 1.0
    assert report.aggregate["mean_ndcg_at_k"] == 1.0
    assert report.to_dict()["case_count"] == 1
    assert report.to_dict()["results"][0]["retrieved"][0]["url"] == "https://docs.python.org/3/whatsnew/3.13.html"


class FailingSearchEngine:
    async def search(self, query: str, use_cache: bool = True, force_refresh: bool = False) -> SearchResponse:
        raise OSError("provider unavailable")


class EmptySearchEngine:
    async def search(self, query: str, use_cache: bool = True, force_refresh: bool = False) -> SearchResponse:
        return SearchResponse(query=query, engine="none", search_time_ms=10.0, results=[])


@pytest.mark.asyncio
async def test_search_benchmark_records_provider_failure_without_losing_case():
    case = SearchGoldenCase(
        case_id="failure",
        query="provider failure",
        relevant_urls=("https://example.com/expected",),
    )

    report = await run_search_benchmark(FailingSearchEngine(), [case], k=3)

    assert report.results[0].error == "provider unavailable"
    assert report.results[0].quality.retrieved_count == 0
    assert report.aggregate["error_count"] == 1


@pytest.mark.asyncio
async def test_search_benchmark_records_empty_result_as_provider_failure():
    case = SearchGoldenCase(
        case_id="empty",
        query="empty provider response",
        relevant_urls=("https://example.com/expected",),
    )

    report = await run_search_benchmark(EmptySearchEngine(), [case], k=3)

    assert report.results[0].error == "empty_result"
    assert report.aggregate["error_count"] == 1


@pytest.mark.asyncio
async def test_search_load_benchmark_records_percentiles_and_empty_results():
    report = await run_search_load_benchmark(EmptySearchEngine(), ["one", "two"], repeats=2, concurrency=2)

    assert len(report.samples) == 4
    assert report.error_count == 4
    assert report.p50_ms >= 0.0
    assert report.p95_ms >= report.p50_ms
    assert report.to_dict()["sample_count"] == 4
