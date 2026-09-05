from antigravity_k.tools.search_conflicts import source_conflict_sets
from antigravity_k.tools.search_quality_evaluator import CitationSource, evaluate_citations
from antigravity_k.tools.web_search_engine import WebSearchEngine
from antigravity_k.tools.web_search_models import SearchResponse, SearchResult
from antigravity_k.tools.web_search_quality import source_id_for_url


def test_source_conflict_sets_detects_disjoint_years_for_the_same_subject():
    sources = (
        CitationSource(
            source_id="release-2024",
            title="Python 3.13 release notes",
            text="Python 3.13 was released in 2024.",
        ),
        CitationSource(
            source_id="release-2025",
            title="Python 3.13 release archive",
            text="Python 3.13 was released in 2025.",
        ),
        CitationSource(
            source_id="unrelated",
            title="Kubernetes release notes",
            text="Kubernetes was released in 2025.",
        ),
    )

    conflicts = source_conflict_sets(sources)

    assert conflicts == (("release-2024", "release-2025"),)


def test_source_conflict_sets_detects_disjoint_declared_metric_values_for_the_same_subject():
    sources = (
        CitationSource(
            source_id="runtime-v36",
            title="Qwen local runtime status",
            text="Model version is 3.6. Context length is 128K tokens.",
        ),
        CitationSource(
            source_id="runtime-v37",
            title="Qwen local runtime benchmark",
            text="Model version is 3.7. Context length is 128K tokens.",
        ),
        CitationSource(
            source_id="unlabeled",
            title="Qwen local runtime notes",
            text="The benchmark mentions 3.8 without naming a metric.",
        ),
    )

    conflicts = source_conflict_sets(sources)

    assert conflicts == (("runtime-v36", "runtime-v37"),)


def test_citation_evaluator_detects_conflicts_without_caller_supplied_sets():
    sources = (
        CitationSource(
            source_id="release-2024",
            title="Python 3.13 release notes",
            text="Python 3.13 was released in 2024.",
        ),
        CitationSource(
            source_id="release-2025",
            title="Python 3.13 release archive",
            text="Python 3.13 was released in 2025.",
        ),
    )

    report = evaluate_citations(
        "Python 3.13 was released in 2024. [citation:release-2024][citation:release-2025]",
        sources,
        min_overlap=0.3,
    )

    assert report.conflicted_claim_count == 1
    assert report.unacknowledged_conflict_count == 1


def test_citation_evaluator_accepts_prior_conflict_acknowledgement_for_the_next_conflicting_claim():
    sources = (
        CitationSource(
            source_id="runtime-v36",
            title="Qwen local runtime status",
            text="Model version is 3.6.",
        ),
        CitationSource(
            source_id="runtime-v37",
            title="Qwen local runtime benchmark",
            text="Model version is 3.7.",
        ),
    )

    report = evaluate_citations(
        "The sources disagree on the model version. According to [citation:runtime-v36], "
        + "the model version is 3.6, while [citation:runtime-v37] states that the model version is 3.7.",
        sources,
        min_overlap=0.3,
    )

    assert report.conflicted_claim_count == 1
    assert report.unacknowledged_conflict_count == 0


def test_llm_context_exposes_detected_conflict_source_ids():
    first_url = "https://docs.python.org/3/whatsnew/3.13.html"
    second_url = "https://www.python.org/downloads/release/python-3130/"
    response = SearchResponse(
        query="Python 3.13 release date",
        results=[
            SearchResult(
                title="Python 3.13 release notes",
                url=first_url,
                snippet="Python 3.13 was released in 2024.",
            ),
            SearchResult(
                title="Python 3.13 release archive",
                url=second_url,
                snippet="Python 3.13 was released in 2025.",
            ),
        ],
        total_results=2,
        search_time_ms=1.0,
        engine="fixture",
    )

    context = WebSearchEngine().format_for_llm(response)

    assert "[search_conflicts]" in context
    assert source_id_for_url(first_url) in context
    assert source_id_for_url(second_url) in context


def test_llm_context_accounts_for_conflict_metadata_within_the_character_budget():
    response = SearchResponse(
        query="Python 3.13 release date",
        results=[
            SearchResult(
                title="Python 3.13 release notes",
                url="https://a.co/a",
                snippet="Python 3.13 was released in 2024.",
            ),
            SearchResult(
                title="Python 3.13 release archive",
                url="https://b.co/b",
                snippet="Python 3.13 was released in 2025.",
            ),
        ],
        total_results=2,
        search_time_ms=1.0,
        engine="fixture",
    )

    context = WebSearchEngine().format_for_llm(response, max_chars=300)

    assert "[search_conflicts]" in context
    assert "1. [citation:" not in context
