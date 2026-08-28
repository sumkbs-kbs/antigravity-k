import json
from collections.abc import Sequence
from pathlib import Path

from antigravity_k.engine.rag_indexer import RAGIndexer
from antigravity_k.engine.rag_quality import (
    RAGGoldenCase,
    RAGResultMapping,
    audit_rag_fixture,
    evaluate_rag_case,
    run_rag_benchmark,
)


def test_local_rag_benchmark_scopes_project_index_by_default(monkeypatch, tmp_path):
    # Given: the benchmark is invoked without an explicit scope.
    import sys

    import scripts.benchmark_local_rag as benchmark_module

    observed = {}

    class FakeStore:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeIndexer:
        def __init__(self, project_root, vector_store):
            del project_root, vector_store

        def index_project(self, subdirs=None):
            observed["subdirs"] = subdirs
            return 0

    monkeypatch.setattr(benchmark_module, "VectorStore", lambda *args, **kwargs: FakeStore())
    monkeypatch.setattr(benchmark_module, "RAGIndexer", FakeIndexer)
    monkeypatch.setattr(
        benchmark_module,
        "run_rag_benchmark",
        lambda *args, **kwargs: type("Report", (), {"to_dict": lambda self: {}})(),
    )
    monkeypatch.setattr(sys, "argv", ["benchmark_local_rag.py", "--output", str(tmp_path / "report.json")])

    # When: the benchmark entry point runs.
    result = benchmark_module.main()

    # Then: indexing is bounded to the fixture's engine scope.
    assert result == 0
    assert observed["subdirs"] == ["src/antigravity_k/engine"]


def test_evaluate_rag_case_scores_unique_sources_and_freshness():
    case = RAGGoldenCase(
        case_id="identifier",
        query="context artifact recall",
        relevant_sources=("src/recall.py", "src/store.py"),
        graded_relevance=(("src/recall.py", 3), ("src/store.py", 1)),
    )
    results: list[RAGResultMapping] = [
        {"id": "r1", "metadata": {"source": "src/recall.py"}, "provenance": {"freshness": "fresh"}},
        {"id": "r2", "metadata": {"source": "src/recall.py"}, "provenance": {"freshness": "fresh"}},
        {"id": "s1", "metadata": {"source": "src/store.py"}, "provenance": {"freshness": "stale"}},
    ]

    report = evaluate_rag_case(case, results, k=3)

    assert report.retrieved_count == 2
    assert report.retrieved_relevant == 2
    assert report.precision_at_k == 2 / 3
    assert report.recall_at_k == 1.0
    assert report.reciprocal_rank == 1.0
    assert report.ndcg_at_k > 0.9
    assert report.source_diversity == 2 / 3
    assert report.freshness_ratio == 0.5


def test_run_rag_benchmark_aggregates_cases_and_preserves_queries():
    cases = [
        RAGGoldenCase("one", "alpha", ("a.py",)),
        RAGGoldenCase("two", "beta", ("b.py",)),
    ]

    class FakeIndexer:
        def search(self, query: str, n_results: int = 5, mode: str = "hybrid") -> Sequence[RAGResultMapping]:
            source = "a.py" if query == "alpha" else "b.py"
            return [{"id": query, "metadata": {"source": source}, "provenance": {"freshness": "fresh"}}]

    report = run_rag_benchmark(FakeIndexer(), cases, k=1)

    assert report.aggregate["case_count"] == 2
    assert report.aggregate["mean_recall_at_k"] == 1.0
    assert [item.case_id for item in report.results] == ["one", "two"]
    assert [item.query for item in report.results] == ["alpha", "beta"]


def test_index_project_disambiguates_duplicate_markdown_heading_ids(tmp_path):
    (tmp_path / "notes.md").write_text("# Same\nfirst\n# Same\nsecond\n", encoding="utf-8")

    class Store:
        def __init__(self):
            self.ids = []

        def upsert_chunks(self, chunks):
            self.ids.extend(chunk["id"] for chunk in chunks)

    store = Store()
    indexed = RAGIndexer(str(tmp_path), store).index_project()

    assert indexed == 2
    assert len(store.ids) == len(set(store.ids))


def test_audit_rag_fixture_flags_expected_sources_without_query_evidence(tmp_path):
    # Given: one expected source shares the query vocabulary and one does not.
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "context_artifact_recall.py").write_text("def recall_context_artifact(): pass\n", encoding="utf-8")
    (source_dir / "rag_indexer.py").write_text("def index_project(): pass\n", encoding="utf-8")
    case = RAGGoldenCase(
        "identifier-recall",
        "context artifact recall",
        ("src/context_artifact_recall.py", "src/rag_indexer.py"),
    )

    # When: the fixture contract is audited against the project tree.
    audits = audit_rag_fixture(tmp_path, (case,))

    # Then: the weak expected source is visible without changing retrieval scores.
    assert audits[0].discoverable is True
    assert audits[0].coverage == 1.0
    assert audits[1].discoverable is False
    assert audits[1].matched_tokens == ()
    assert "weak lexical evidence" in audits[1].reason


def test_checked_in_rag_fixture_has_discoverable_expected_sources():
    fixture_path = Path(__file__).parent / "fixtures" / "rag_quality_cases.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = tuple(RAGGoldenCase.from_dict(item) for item in payload)

    audits = audit_rag_fixture(Path(__file__).parents[1], cases)

    assert audits
    assert all(item.discoverable for item in audits)
