#!/usr/bin/env python3
"""성능 테스트 임계값 자동 계산 스크립트.

각 테스트를 N회 반복 실행하고 통계를 수집하여,
추천 임계값을 계산합니다.
  - 권장: max × 1.5 (예시)
  - 보수적: p95 × 2.0
  - 관대함: max × 2.0

사용법:
  python scripts/calc_recommended_thresholds.py [--runs 5] [--margin 1.5]
"""

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Callable, Generator

# 프로젝트 루트 탐색
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


# ─── 타이머 ──────────────────────────────────────────────────────


@contextlib.contextmanager
def timer_ms() -> Generator[Callable[[], float], None, None]:
    start = time.perf_counter()
    yield lambda: (time.perf_counter() - start) * 1000


# ─── 테스트 러너 ─────────────────────────────────────────────────


class TestRunner:
    """개별 테스트 함수를 N회 반복 실행하고 통계를 수집합니다."""

    def __init__(self, runs: int):
        self.runs = runs
        self.results: dict[str, list[float]] = {}

    def run(self, name: str, fn: Callable[..., object], *args: object, **kwargs: object) -> None:
        """테스트 함수를 N회 실행하고 elapsed_ms를 수집합니다."""
        times: list[float] = []
        for i in range(self.runs):
            try:
                with timer_ms() as get_ms:
                    fn(*args, **kwargs)
                elapsed = get_ms()
                times.append(elapsed)
            except Exception as e:
                print(f"  ⚠️  [{name}] run {i + 1} failed: {e}")
                times.append(0.0)
        self.results[name] = times
        avg = sum(times) / len(times)
        print(f"  {name:<45} avg={avg:>8.1f}ms  max={max(times):>8.1f}ms  p95={_p95(times):>8.1f}ms")


# ─── 통계 헬퍼 ─────────────────────────────────────────────────


def _p95(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = int(len(s) * 0.95)
    return s[min(idx, len(s) - 1)]


def _stats(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"avg": 0, "median": 0, "min": 0, "max": 0, "p95": 0, "stddev": 0}
    n = len(vals)
    avg = sum(vals) / n
    s = sorted(vals)
    median = s[n // 2]
    min_v = s[0]
    max_v = s[-1]
    p95 = _p95(vals)
    variance = sum((v - avg) ** 2 for v in vals) / (n - 1) if n > 1 else 0
    stddev = variance**0.5
    return {
        "avg": round(avg, 2),
        "median": round(median, 2),
        "min": round(min_v, 2),
        "max": round(max_v, 2),
        "p95": round(p95, 2),
        "stddev": round(stddev, 2),
    }


# ─── 테스트 함수들 (test_benchmark_performance.py에서 발췌) ───────


def _run_context_enrich_total():
    from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer
    from antigravity_k.engine.file_summarizer import FileSummarizer

    indexer = CodeTreeIndexer(PROJECT_ROOT)
    indexer.build_tree()
    related = indexer.search("benchmark performance test", max_files=8)
    summarizer = FileSummarizer()
    summarizer.summarize_files(related, PROJECT_ROOT, query="benchmark")


def _run_context_enrich_search():
    from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer

    indexer = CodeTreeIndexer(PROJECT_ROOT)
    indexer.build_tree()
    queries = ["benchmark performance test", "code tree indexer", "file summarizer", "user authentication"]
    times = []
    for q in queries:
        with timer_ms() as get_ms:
            _ = indexer.search(q, max_files=8)
        times.append(get_ms())
    return sum(times) / len(times)  # 평균 반환, 여러 번 측정하려면... 사실 개별 fn에서 집계 필요


def _run_context_enrich_build():
    import tempfile

    from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(10):
            p = os.path.join(tmpdir, f"mod{i}.py")
            with open(p, "w") as f:
                f.write(f"def func_{i}():\n    return {i}\n\nclass Class{i}:\n    pass\n")
        indexer = CodeTreeIndexer(tmpdir)
        indexer.build_tree()


def _run_context_enrich_build_cache():
    import tempfile

    from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(10):
            p = os.path.join(tmpdir, f"mod{i}.py")
            with open(p, "w") as f:
                f.write(f"def func_{i}():\n    return {i}\n\nclass Class{i}:\n    pass\n")
        indexer = CodeTreeIndexer(tmpdir)
        indexer.build_tree()  # warm
        indexer.build_tree()  # cache


def _run_code_review_total():
    import subprocess
    from unittest.mock import MagicMock

    mock_manager = MagicMock()
    mock_manager.generate.return_value = "BUGS: None\nTYPES: None\nQUALITY: None"
    subprocess.run(["git", "diff", "--stat"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)
    subprocess.run(["git", "diff"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)
    review_prompt = "Review the following code changes...\n\n$diff_content[:2000]"
    mock_manager.generate(prompt=review_prompt, target="qa-model", max_tokens=256)


def _run_code_review_git_stat():
    import subprocess

    subprocess.run(["git", "diff", "--stat"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)


def _run_code_review_git_detail():
    import subprocess

    subprocess.run(["git", "diff"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)


def _run_code_review_mock_llm():
    from unittest.mock import MagicMock

    mock_manager = MagicMock()
    mock_manager.generate.return_value = "BUGS: None\nTYPES: None\nQUALITY: None"
    mock_manager.generate(prompt="Review: some code", target="qa-model", max_tokens=256)


def _run_max_engine_total():
    from unittest.mock import MagicMock

    from antigravity_k.engine.max_engine import MaxModeEngine, WorkerResult

    mgr = MagicMock()
    mgr._loaded_models = {"model-a": {}, "model-b": {}}
    engine = MaxModeEngine(mgr)
    engine._get_available_models = lambda: ["model-a", "model-b"]
    engine._run_worker = lambda *a, **kw: WorkerResult(0, "model-a", "default", "output", 0.3)
    mock_orch = MagicMock()
    mock_orch.manager = mgr
    mock_orch._get_model_for_role = lambda role: "qa-model"
    mock_orch.manager.generate.return_value = "SELECTED: 1\nREASON: Best"
    engine.run(
        {
            "prompt": "Create a test function",
            "messages": [{"role": "user", "content": "test"}],
            "task_type": "coding",
            "delegate_to": "WORKER",
            "max_steps": 5,
            "target_model": "model-a",
        },
        orchestrator=mock_orch,
    )


def _run_max_engine_config():
    from unittest.mock import MagicMock

    from antigravity_k.engine.max_engine import MaxModeEngine

    mgr = MagicMock()
    mgr._loaded_models = {"a": {}, "b": {}, "c": {}}
    engine = MaxModeEngine(mgr)
    engine._get_available_models = lambda: ["a", "b", "c"]
    engine._build_worker_configs("WORKER", "a")


def _run_max_engine_prompt():
    from antigravity_k.engine.max_engine import MaxModeEngine

    engine = MaxModeEngine(None)
    for s in ("default", "creative", "safe", "balanced"):
        engine._build_worker_prompt("Create a test function", "model-a", s, 0.4)


def _run_max_engine_selector():
    from unittest.mock import MagicMock

    from antigravity_k.engine.max_engine import MaxModeEngine, WorkerResult

    mgr = MagicMock()
    mgr.generate.return_value = "SELECTED: 1\nREASON: Best"
    engine = MaxModeEngine(mgr)
    qa_orch = MagicMock()
    qa_orch.manager = mgr
    qa_orch._get_model_for_role = lambda role: "qa-model"
    engine._select_best(
        "task",
        [
            WorkerResult(0, "a", "default", "first", 0.5),
            WorkerResult(1, "b", "creative", "second", 1.0),
            WorkerResult(2, "c", "safe", "third", 1.5),
        ],
        "WORKER",
        qa_orch,
    )


def _run_max_engine_trace():
    from antigravity_k.engine.max_engine import MaxModeEngine, WorkerResult

    engine = MaxModeEngine(None)
    engine._format_trace(
        [WorkerResult(0, "a", "default", "out1", 1.0), WorkerResult(1, "b", "creative", "out2", 2.0)],
        1,
        [{"model": "a", "strategy": "default"}, {"model": "b", "strategy": "creative"}],
    )


# ─── RAG 테스트 함수 ─────────────────────────────────────────────


def _make_rag_project(tmpdir: str):
    """RAG 벤치마크용 가상 프로젝트를 생성합니다."""
    files = {}
    for i in range(8):
        files[f"src/mod{i}.py"] = (
            f"import os\nfrom typing import Optional\n\n"
            f"def process_{i}(data: str) -> str:\n"
            f"    result = data.upper()\n"
            f"    return result.strip()\n\n"
            f"class Handler{i}:\n"
            f'    def __init__(self, name: str = "default"):\n'
            f"        self.name = name\n"
            f"    def handle(self, payload: dict) -> dict:\n"
            f'        return {{"status": "ok", "module": {i}}}\n'
        )
    for i in range(6):
        files[f"doc/chapter_{i}.md"] = (
            f"# Chapter {i}\n\nIntroduction.\n\n"
            f"## Section {i}.1\n\nContent.\n\n"
            f"| Key | Value |\n|-----|-------|\n| param_{i} | value_{i} |\n"
        )
    for rel_path, content in files.items():
        full_path = os.path.join(tmpdir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def _run_rag_total():
    import tempfile

    from antigravity_k.engine.rag_indexer import RAGIndexer
    from antigravity_k.engine.vector_store import VectorStore

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        _make_rag_project(tmpdir)
        store = VectorStore(persist_directory=os.path.join(tmpdir, ".chroma"), collection_name="test")
        indexer = RAGIndexer(tmpdir, vector_store=store)
        indexer.index_project()
        store.search("process data", n_results=5)
        indexer.format_context("Handler processing", n_results=3, max_chars=3000)
        store.close()


def _run_rag_chunk_python():
    from antigravity_k.engine.rag_indexer import RAGIndexer

    indexer = RAGIndexer("/tmp", vector_store=None)
    content = (
        "import os\nfrom typing import Optional\n\n"
        "def process(data: str) -> str:\n    return data.strip()\n\n"
        "class Handler:\n    def __init__(self):\n        self.name = 'test'\n"
        "    def handle(self, payload: dict) -> dict:\n"
        "        return {'status': 'ok'}\n"
    )
    indexer._chunk_python("test.py", content)


def _run_rag_chunk_markdown():
    from antigravity_k.engine.rag_indexer import RAGIndexer

    indexer = RAGIndexer("/tmp", vector_store=None)
    content = (
        "# Chapter 1\n\nIntroduction.\n\n"
        "## Section 1.1\n\nContent here.\n\n"
        "| Key | Value |\n|-----|-------|\n| param | val |\n"
    )
    indexer._chunk_markdown("doc.md", content)


def _run_rag_search():
    import tempfile

    from antigravity_k.engine.rag_indexer import RAGIndexer
    from antigravity_k.engine.vector_store import VectorStore

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        _make_rag_project(tmpdir)
        store = VectorStore(persist_directory=os.path.join(tmpdir, ".chroma"), collection_name="test")
        indexer = RAGIndexer(tmpdir, vector_store=store)
        indexer.index_project()
        store.search("process data", n_results=5)
        store.close()


# ─── 메인 ────────────────────────────────────────────────────────

TEST_SUITE = [
    # (display_name, function, is_subtest)
    ("context_enrich_total", _run_context_enrich_total, True),
    ("context_enrich_search", _run_context_enrich_search, True),
    ("context_enrich_build_first", _run_context_enrich_build, True),
    ("context_enrich_build_cache", _run_context_enrich_build_cache, True),
    ("code_review_total", _run_code_review_total, True),
    ("code_review_git_stat", _run_code_review_git_stat, True),
    ("code_review_git_detail", _run_code_review_git_detail, True),
    ("code_review_mock_llm", _run_code_review_mock_llm, True),
    ("rag_total", _run_rag_total, True),
    ("rag_chunk_python", _run_rag_chunk_python, True),
    ("rag_chunk_markdown", _run_rag_chunk_markdown, True),
    ("rag_search", _run_rag_search, True),
    ("max_engine_total", _run_max_engine_total, True),
    ("max_engine_config", _run_max_engine_config, True),
    ("max_engine_prompt", _run_max_engine_prompt, True),
    ("max_engine_selector", _run_max_engine_selector, True),
    ("max_engine_trace", _run_max_engine_trace, True),
]

# Stage grouping (for pipeline-level recommendation)
STAGE_GROUPS: dict[str, list[str]] = {
    "context_enrich": [
        "context_enrich_total",
        "context_enrich_search",
        "context_enrich_build_first",
        "context_enrich_build_cache",
    ],
    "code_review": ["code_review_total", "code_review_git_stat", "code_review_git_detail", "code_review_mock_llm"],
    "rag_indexing": ["rag_total", "rag_chunk_python", "rag_chunk_markdown", "rag_search"],
    "max_engine": [
        "max_engine_total",
        "max_engine_config",
        "max_engine_prompt",
        "max_engine_selector",
        "max_engine_trace",
    ],
}


def main():
    parser = argparse.ArgumentParser(description="Calculate recommended performance test thresholds")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per test (default: 5)")
    parser.add_argument("--margin", type=float, default=1.5, help="Safety margin multiplier for max (default: 1.5)")
    parser.add_argument("--json", help="Output JSON path", default=None)
    parser.add_argument("--skip-stage", nargs="*", choices=list(STAGE_GROUPS.keys()), help="Skip stages")
    args = parser.parse_args()

    skip = set(args.skip_stage or [])

    runner = TestRunner(args.runs)

    print(f"\n{'=' * 60}")
    print(f"  Threshold Calculator — {args.runs} runs per test, margin={args.margin}x")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"{'=' * 60}\n")

    for name, fn, is_subtest in TEST_SUITE:
        stage = name.split("_")[0]
        if stage in skip:
            print(f"  ⏭️  Skipping {name} (stage {stage} skipped)")
            continue

        print(f"  ▶  Running {name} ({args.runs}x)...")
        if is_subtest:
            # run multiple iterations manually by calling run()
            times = []
            for i in range(args.runs):
                try:
                    with timer_ms() as get_ms:
                        fn()
                    elapsed = get_ms()
                    times.append(elapsed)
                except Exception as e:
                    print(f"  ⚠️  run {i + 1} failed: {e}")
                    times.append(0.0)
            runner.results[name] = times
        else:
            runner.run(name, fn)

    # 요약 출력
    print(f"\n{'=' * 60}")
    print(f"  RECOMMENDED THRESHOLDS (margin={args.margin}x)")
    print(f"{'=' * 60}\n")

    all_recommendations: dict[str, dict[str, object]] = {}

    print(f"  {'Test':<45} {'Max(ms)':<10} {'P95(ms)':<10} {'→ Thresh(ms)':<15}")
    print(f"  {'-' * 45} {'-' * 10} {'-' * 10} {'-' * 15}")
    for name in runner.results:
        times = runner.results[name]
        if not times:
            continue
        stats = _stats(times)
        recommended = round(max(stats["max"] * args.margin, stats["p95"] * args.margin), 2)
        print(f"  {name:<45} {stats['max']:<10.1f} {stats['p95']:<10.1f} {recommended:<15.1f}")
        all_recommendations[name] = {
            "stats": stats,
            "recommended_threshold_ms": recommended,
            "margin": args.margin,
        }

    # Pipeline-level recommendations (env var names)
    print(f"\n  {'=' * 40}")
    print("  Pipeline-level env var thresholds")
    print(f"  {'=' * 40}\n")

    pipeline_recs: dict[str, dict[str, object]] = {}
    for stage_name, test_names in STAGE_GROUPS.items():
        if stage_name in skip:
            continue
        max_vals = []
        p95_vals = []
        for tname in test_names:
            if tname in runner.results and runner.results[tname]:
                st = _stats(runner.results[tname])
                if st["p95"] > 0:
                    max_vals.append(st["max"])
                    p95_vals.append(st["p95"])

        if max_vals:
            # pipeline-level: 가장 큰 서브 테스트의 threshold를 사용
            env_name = f"BENCHMARK_THRESHOLD_{stage_name.upper()}"
            raw_max = max(max_vals)
            raw_p95 = max(p95_vals)
            recommended = round(max(raw_max * args.margin, raw_p95 * args.margin), 2)
            pipeline_recs[env_name] = {
                "recommended_ms": recommended,
                "max_subtest_ms": raw_max,
                "p95_subtest_ms": raw_p95,
            }
            print(f"  {env_name:<45} = {recommended:<8.1f} ms  (max_sub: {raw_max:.1f}, p95_sub: {raw_p95:.1f})")

    # JSON 출력
    if args.json:
        output = {
            "runs": args.runs,
            "margin": args.margin,
            "project": PROJECT_ROOT,
            "recommendations": all_recommendations,
            "pipeline_env_vars": pipeline_recs,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n  📄 JSON saved: {args.json}")

    print()


if __name__ == "__main__":
    main()
