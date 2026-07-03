#!/usr/bin/env python3
"""Freebuff-Style Proactive Pipeline — 성능 벤치마크 스크립트.

각 파이프라인 단계의 지연시간(latency)을 측정합니다.

측정 대상:
  P1+P2: context_enrich — CodeTreeIndexer.build_tree() + FileSummarizer.summarize_files()
  P3:    code_review — Git diff + LLM 리뷰 (모의 응답)
  P4:    max_engine — 워커 구성 + 병렬 실행 + Selector

사용법:
  python scripts/benchmark_proactive_pipeline.py [--iterations 5] [--project-dir .]
  python scripts/benchmark_proactive_pipeline.py --json          # JSON 출력
  python scripts/benchmark_proactive_pipeline.py --compare       # 이전 결과와 비교
"""

import argparse
import contextlib
import json
import logging
import os
import sys
import tempfile
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any, Callable
from unittest.mock import MagicMock

# ─── 로깅 비활성화 (벤치마크 노이즈 최소화) ───────────────────────
logging.disable(logging.CRITICAL)


# ─── 데이터 클래스 ────────────────────────────────────────────────


@dataclass
class BenchmarkSample:
    """단일 측정 샘플."""

    stage: str
    iteration: int
    elapsed_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """벤치마크 결과 집계."""

    stage: str
    samples: list[BenchmarkSample] = field(default_factory=list)

    def add(self, sample: BenchmarkSample):
        self.samples.append(sample)

    @property
    def elapsed_ms_list(self) -> list[float]:
        return [s.elapsed_ms for s in self.samples]

    @property
    def min_ms(self) -> float:
        return min(self.elapsed_ms_list)

    @property
    def max_ms(self) -> float:
        return max(self.elapsed_ms_list)

    @property
    def avg_ms(self) -> float:
        vals = self.elapsed_ms_list
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def median_ms(self) -> float:
        vals = sorted(self.elapsed_ms_list)
        n = len(vals)
        if n == 0:
            return 0.0
        return vals[n // 2]

    @property
    def p95_ms(self) -> float:
        vals = sorted(self.elapsed_ms_list)
        if not vals:
            return 0.0
        idx = int(len(vals) * 0.95)
        return vals[min(idx, len(vals) - 1)]

    @property
    def stddev_ms(self) -> float:
        vals = self.elapsed_ms_list
        n = len(vals)
        if n < 2:
            return 0.0
        avg = sum(vals) / n
        variance = sum((v - avg) ** 2 for v in vals) / (n - 1)
        return variance**0.5


# ─── 타이머 헬퍼 ──────────────────────────────────────────────────


@contextlib.contextmanager
def timer() -> Generator[float, None, None]:
    """밀리초 단위 타이머 컨텍스트 매니저. elapsed_ms를 yield."""
    start = time.perf_counter()
    yield lambda: (time.perf_counter() - start) * 1000


# ─── 벤치마크: context_enrich (P1+P2) ────────────────────────────

NAME_CONTEXT_ENRICH = "context_enrich"
DESC_CONTEXT_ENRICH = "CodeTreeIndexer.build_tree() + FileSummarizer.summarize_files()"


def benchmark_context_enrich(project_root: str, iteration: int) -> BenchmarkSample:
    """CodeTreeIndexer + FileSummarizer의 성능을 측정합니다.

    측정 항목:
      - CodeTreeIndexer.build_tree() 최초 빌드 시간
      - CodeTreeIndexer.build_tree() 캐시 히트 시간
      - CodeTreeIndexer.search() 시간 (4개 쿼리 평균)
      - FileSummarizer.summarize_files() 시간
    """
    from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer
    from antigravity_k.engine.file_summarizer import FileSummarizer

    indexer = CodeTreeIndexer(project_root)
    summarizer = FileSummarizer()

    # 1. build_tree() 최초 빌드
    with timer() as get_t1:
        _tree = indexer.build_tree()
    t_build_first = get_t1()

    # 2. build_tree() 캐시 히트
    with timer() as get_t2:
        _tree_cached = indexer.build_tree()
    t_build_cache = get_t2()

    # 3. search() — 여러 쿼리 평균
    test_queries = [
        "benchmark performance test",
        "code tree indexer",
        "file summarizer",
        "user authentication",
    ]
    search_times = []
    search_results = []
    for q in test_queries:
        with timer() as get_t3:
            _results = indexer.search(q, max_files=8)
        search_times.append(get_t3())
        search_results.append(len(_results))

    t_search_avg = sum(search_times) / len(search_times) if search_times else 0.0

    # 4. summarize_files()
    related = indexer.search("code tree", max_files=8)
    with timer() as get_t4:
        _ctx = summarizer.summarize_files(related, project_root, query="code tree")
    t_summarize = get_t4()

    stats = indexer.stats()

    return BenchmarkSample(
        stage=NAME_CONTEXT_ENRICH,
        iteration=iteration,
        elapsed_ms=t_build_first + t_search_avg + t_summarize,
        metadata={
            "tree_size_kb": stats["tree_size_kb"],
            "files_indexed": stats["files_indexed"],
            "total_functions": stats["total_functions"],
            "total_classes": stats["total_classes"],
            "build_first_ms": round(t_build_first, 2),
            "build_cache_ms": round(t_build_cache, 2),
            "search_avg_ms": round(t_search_avg, 2),
            "search_results": search_results,
            "summarize_ms": round(t_summarize, 2),
        },
    )


# ─── 벤치마크: code_review (P3) ──────────────────────────────────

NAME_CODE_REVIEW = "code_review"
DESC_CODE_REVIEW = "Git diff + Mock LLM review response"


def benchmark_code_review(project_root: str, iteration: int) -> BenchmarkSample:
    """code_review_handler의 성능을 측정합니다.

    측정 항목:
      - Git diff --stat 실행 시간
      - Git diff 상세 실행 시간
      - 모의 LLM 리뷰 호출 시간
    """
    import subprocess

    # 1. Git diff --stat
    with timer() as get_t1:
        stat_result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    t_diff_stat = get_t1()
    diff_stat = stat_result.stdout.strip()

    # 2. Git diff 상세
    with timer() as get_t2:
        detail_result = subprocess.run(
            ["git", "diff"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    t_diff_detail = get_t2()
    diff_content = detail_result.stdout

    # 3. 모의 LLM 리뷰 (manager.generate() 대체)
    mock_manager = MagicMock()
    mock_manager.generate.return_value = "BUGS: None\nTYPES: None\nQUALITY: None"

    with timer() as get_t3:
        review_prompt = f"""Review the following code changes for bugs or issues.

Respond in EXACTLY this format (one line per category, 'None' if none):
BUGS: <brief description or None>
TYPES: <type error description or None>
QUALITY: <quality concern or None>

```diff
{diff_content[:2000]}
```"""
        _review_response = mock_manager.generate(
            prompt=review_prompt,
            target="qa-model",
            max_tokens=256,
        )
    t_llm_mock = get_t3()

    changed_files_count = len([line for line in diff_stat.split("\n") if line.strip()]) if diff_stat else 0

    return BenchmarkSample(
        stage=NAME_CODE_REVIEW,
        iteration=iteration,
        elapsed_ms=t_diff_stat + t_diff_detail + t_llm_mock,
        metadata={
            "diff_stat_ms": round(t_diff_stat, 2),
            "diff_detail_ms": round(t_diff_detail, 2),
            "llm_mock_ms": round(t_llm_mock, 2),
            "changed_files": changed_files_count,
            "diff_size_bytes": len(diff_content),
        },
    )


# ─── 벤치마크: rag_indexing (Vector Search + Context Retrieval) ──

NAME_RAG = "rag_indexing"
DESC_RAG = "RAGIndexer.index_project() + VectorStore.search() + format_context()"

NAME_MAX_ENGINE = "max_engine"
DESC_MAX_ENGINE = "Worker config + mock run + Selector"


# ─── 벤치마크: max_engine ───────────────────────────────────────


def benchmark_rag_indexing(project_root: str, iteration: int) -> BenchmarkSample:
    """RAGIndexer + VectorStore의 성능을 측정합니다.

    측정 항목:
      - RAGIndexer._chunk_python() — Python 파일 청킹 시간
      - RAGIndexer._chunk_markdown() — Markdown 파일 청킹 시간
      - VectorStore.search() — 시맨틱 검색 시간
      - RAGIndexer._keyword_search() — 키워드 검색 시간
      - RAGIndexer._hybrid_search_rrf() — 하이브리드 검색 시간
      - RAGIndexer.format_context() — 전체 검색 + 포맷 파이프라인 시간
    """

    from antigravity_k.engine.rag_indexer import RAGIndexer
    from antigravity_k.engine.vector_store import VectorStore

    def _py_module(i: int) -> str:
        """Generate Python module content for module index i."""
        lines = [
            "import os",
            "from typing import Optional",
            "",
            "",
            f"def process_{i}(data: str) -> str:",
            f'    """Process data for module {i}."""',
            "    result = data.upper()",
            "    return result.strip()",
            "",
            "",
            f"class Handler{i}:",
            f'    """Handler for module {i}."""',
            "",
            '    def __init__(self, name: str = "default"):',
            "        self.name = name",
            "",
            "    def handle(self, payload: dict) -> dict:",
            f'        return {{"status": "ok", "module": {i}, "payload": payload}}',
            "",
            "    def validate(self, data: str) -> bool:",
            "        return len(data) > 0",
            "",
        ]
        return "\n".join(lines)

    def _md_chapter(i: int) -> str:
        """Generate Markdown chapter content for chapter index i."""
        lines = [
            f"# Chapter {i}",
            "",
            f"This is the introduction to chapter {i}.",
            "",
            f"## Section {i}.1",
            "",
            f"Content for section {i}.1 goes here.",
            f"It has some important details about module {i}.",
            "",
            f"## Section {i}.2",
            "",
            "### Subsection",
            "",
            "Detailed explanation for subsection.",
            "",
            "| Key | Value | Description |",
            "|-----|-------|-------------|",
            f"| param_{i} | value_{i} | Parameter {i} description |",
            "| timeout | 30s | Default timeout |",
            "",
        ]
        return "\n".join(lines)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        # ── 가상 프로젝트 생성 ──
        src = os.path.join(tmpdir, "src")
        os.makedirs(src)

        # Python 파일들
        py_files: dict[str, str] = {}
        for i in range(8):
            py_files[f"src/mod{i}.py"] = _py_module(i)

        # Markdown 파일들
        md_files: dict[str, str] = {}
        for i in range(6):
            md_files[f"doc/chapter_{i}.md"] = _md_chapter(i)

        for rel_path, content in {**py_files, **md_files}.items():
            full_path = os.path.join(tmpdir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        # VectorStore (인메모리 ChromaDB)
        store = VectorStore(persist_directory=os.path.join(tmpdir, ".chroma"), collection_name="bench_rag")
        indexer = RAGIndexer(tmpdir, vector_store=store)

        # 1. _chunk_python() — 단일 Python 파일 청킹
        py_path = "src/mod0.py"
        py_content = py_files[py_path]
        with timer() as get_t1:
            _py_chunks = indexer._chunk_python(py_path, py_content.lstrip("\n"))
        t_chunk_python = get_t1()

        # 2. _chunk_markdown() — 단일 Markdown 파일 청킹
        md_path = "doc/chapter_0.md"
        md_content = md_files[md_path]
        with timer() as get_t2:
            _md_chunks = indexer._chunk_markdown(md_path, md_content.lstrip("\n"))
        t_chunk_markdown = get_t2()

        # 3. index_project() — 전체 프로젝트 인덱싱
        with timer() as get_t3:
            total_chunks = indexer.index_project()
        t_index_project = get_t3()

        # 4. VectorStore.search() — 시맨틱 검색
        with timer() as get_t4:
            _semantic_results = store.search("data processing", n_results=5)
        t_search_semantic = get_t4()

        # 5. RAGIndexer._keyword_search()
        with timer() as get_t5:
            _kw_results = indexer._keyword_search("Handler validate", n_results=5)
        t_search_keyword = get_t5()

        # 6. RAGIndexer._hybrid_search_rrf()
        with timer() as get_t6:
            _hybrid_results = indexer._hybrid_search_rrf("process module data", n_results=5)
        t_search_hybrid = get_t6()

        # 7. RAGIndexer.search() — 통합 검색 (hybrid mode)
        with timer() as get_t7:
            _search_results = indexer.search("module handler", n_results=5, mode="hybrid")
        t_search_unified = get_t7()

        # 8. format_context() — 전체 RAG 파이프라인
        with timer() as get_t8:
            _ctx_formatted = indexer.format_context("Handler processing", n_results=3, max_chars=3000)
        t_format_context = get_t8()

        # 정리
        store.close()

    return BenchmarkSample(
        stage=NAME_RAG,
        iteration=iteration,
        elapsed_ms=t_index_project + t_search_unified + t_format_context,
        metadata={
            "chunk_python_ms": round(t_chunk_python, 3),
            "chunk_markdown_ms": round(t_chunk_markdown, 3),
            "index_project_ms": round(t_index_project, 2),
            "total_chunks": total_chunks,
            "search_semantic_ms": round(t_search_semantic, 3),
            "search_keyword_ms": round(t_search_keyword, 3),
            "search_hybrid_ms": round(t_search_hybrid, 3),
            "search_unified_ms": round(t_search_unified, 3),
            "format_context_ms": round(t_format_context, 3),
        },
    )


def benchmark_max_engine(project_root: str, iteration: int) -> BenchmarkSample:
    """MaxModeEngine의 각 서브 단계 성능을 측정합니다.

    측정 항목:
      - _build_worker_configs() 시간 (1/2/3 모델 시나리오)
      - _build_worker_prompt() 시간 (4개 전략)
      - _select_best() 시간 (2개, 3개 후보)
      - 모의 run() 전체 시간 (모의 _run_worker 사용)
    """
    from antigravity_k.engine.max_engine import (
        MaxModeEngine,
        WorkerResult,
    )

    mgr = MagicMock()
    mgr._loaded_models = {"model-a": {}, "model-b": {}, "model-c": {}}

    engine = MaxModeEngine(mgr, project_root=project_root)

    # 1. _build_worker_configs() — 시나리오별
    config_times: dict[str, float] = {}

    # 1a: 1개 모델
    engine._get_available_models = lambda: ["model-a"]
    with timer() as get_t:
        _ = engine._build_worker_configs("WORKER", "model-a")
    config_times["1_model"] = get_t()

    # 1b: 2개 모델
    engine._get_available_models = lambda: ["model-a", "model-b"]
    with timer() as get_t:
        _ = engine._build_worker_configs("WORKER", "model-a")
    config_times["2_models"] = get_t()

    # 1c: 3개 모델
    engine._get_available_models = lambda: ["model-a", "model-b", "model-c"]
    with timer() as get_t:
        configs_3 = engine._build_worker_configs("WORKER", "model-a")
    config_times["3_models"] = get_t()

    # 2. _build_worker_prompt() — 전략별
    prompt_times: dict[str, float] = {}
    for strategy in ("default", "creative", "safe", "balanced"):
        with timer() as get_t:
            _ = engine._build_worker_prompt(
                "Create a high-performance API endpoint",
                "model-a",
                strategy,
                0.4,
            )
        prompt_times[strategy] = get_t()

    # 3. _select_best() — 후보 수별
    select_times: dict[str, float] = {}
    qa_orch = MagicMock()
    qa_orch.manager = mgr
    qa_orch.manager.generate.return_value = "SELECTED: 1\nREASON: Best output"
    qa_orch._get_model_for_role = lambda role: "qa-model"

    # 3a: 2개 후보
    with timer() as get_t:
        _ = engine._select_best(
            "task",
            [
                WorkerResult(0, "a", "default", "short", 0.5),
                WorkerResult(1, "b", "creative", "longer complete", 1.2),
            ],
            "WORKER",
            qa_orch,
        )
    select_times["2_candidates"] = get_t()

    # 3b: 3개 후보
    with timer() as get_t:
        _ = engine._select_best(
            "task",
            [
                WorkerResult(0, "a", "default", "short", 0.5),
                WorkerResult(1, "b", "creative", "medium", 1.0),
                WorkerResult(2, "c", "safe", "longest complete solution", 1.5),
            ],
            "WORKER",
            qa_orch,
        )
    select_times["3_candidates"] = get_t()

    # 4. _format_trace()
    with timer() as get_t:
        _ = engine._format_trace(
            [
                WorkerResult(0, "a", "default", "out1", 0.5),
                WorkerResult(1, "b", "creative", "out2", 1.2),
            ],
            1,
            configs_3[:2],
        )
    t_trace = get_t()

    # 5. total simulation: 모의 run()
    def mock_run_worker(*args, **kwargs):
        return WorkerResult(0, "model-a", "default", "output result", 0.3)

    engine._run_worker = mock_run_worker

    mock_orch = MagicMock()
    mock_orch.manager = mgr
    mock_orch._get_model_for_role = lambda role: "qa-model"
    mock_orch.manager.generate.return_value = "SELECTED: 1\nREASON: Best"

    with timer() as get_t:
        result = engine.run(
            {
                "prompt": "Create a test function",
                "messages": [{"role": "user", "content": "Create a test function"}],
                "task_type": "coding",
                "delegate_to": "WORKER",
                "max_steps": 5,
                "target_model": "model-a",
            },
            orchestrator=mock_orch,
        )
    t_run_total = get_t()

    return BenchmarkSample(
        stage=NAME_MAX_ENGINE,
        iteration=iteration,
        elapsed_ms=t_run_total,
        metadata={
            "config_1_model_ms": round(config_times["1_model"], 3),
            "config_2_models_ms": round(config_times["2_models"], 3),
            "config_3_models_ms": round(config_times["3_models"], 3),
            "prompt_default_ms": round(prompt_times["default"], 3),
            "prompt_creative_ms": round(prompt_times["creative"], 3),
            "prompt_safe_ms": round(prompt_times["safe"], 3),
            "prompt_balanced_ms": round(prompt_times["balanced"], 3),
            "select_2_candidates_ms": round(select_times["2_candidates"], 3),
            "select_3_candidates_ms": round(select_times["3_candidates"], 3),
            "trace_format_ms": round(t_trace, 3),
            "run_total_ms": round(t_run_total, 2),
            "total_workers": result.total_workers,
            "successful": result.successful,
        },
    )


# ─── 벤치마크 러너 ────────────────────────────────────────────────


def run_benchmark(
    stage: str,
    benchmark_fn: Callable,
    project_root: str,
    iterations: int,
    warmup: bool = True,
) -> BenchmarkResult:
    """지정된 스테이지의 벤치마크를 실행합니다."""
    result = BenchmarkResult(stage=stage)

    # 웜업 (1회 실행, 결과 폐기)
    if warmup:
        try:
            benchmark_fn(project_root, -1)
        except Exception:
            pass  # 웜업 실패는 무시

    for i in range(iterations):
        sample = benchmark_fn(project_root, i)
        result.add(sample)

    return result


# ─── 결과 출력 ────────────────────────────────────────────────────


def print_header(text: str):
    """섹션 헤더를 출력합니다."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def print_result(name: str, desc: str, result: BenchmarkResult):
    """단일 벤치마크 결과를 포맷팅하여 출력합니다."""
    print_header(f"{name} — {desc}")

    print(f"  샘플 수:      {len(result.samples):>3}")
    print(f"  평균 지연시간: {result.avg_ms:>8.1f} ms")
    print(f"  중앙값:       {result.median_ms:>8.1f} ms")
    print(f"  최소:         {result.min_ms:>8.1f} ms")
    print(f"  최대:         {result.max_ms:>8.1f} ms")
    print(f"  P95:          {result.p95_ms:>8.1f} ms")
    print(f"  표준편차:     {result.stddev_ms:>7.1f} ms")

    # 메타데이터 표시 (첫 번째 샘플)
    if result.samples and result.samples[0].metadata:
        md = result.samples[0].metadata
        print("\n  --- 세부 항목 (1회차) ---")
        for key, value in md.items():
            if isinstance(value, float):
                print(f"    {key}: {value:>10.2f}")
            else:
                print(f"    {key}: {value!s:>10}")


def print_summary(
    results: dict[str, BenchmarkResult],
    total_elapsed: float,
):
    """전체 요약을 출력합니다."""
    print_header("PIPELINE BENCHMARK SUMMARY")

    print(f"  {'Stage':<25} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'P95 (ms)':<12}")
    print(f"  {'-' * 25} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 12}")
    for name, r in results.items():
        print(f"  {name:<25} {r.avg_ms:<12.1f} {r.min_ms:<12.1f} {r.max_ms:<12.1f} {r.p95_ms:<12.1f}")
    print(f"\n  총 소요 시간: {total_elapsed:.1f}초")


def export_json(results: dict[str, BenchmarkResult], path: str):
    """결과를 JSON 파일로 내보냅니다."""
    data = {}
    for name, r in results.items():
        data[name] = {
            "stage": r.stage,
            "samples": [
                {
                    "iteration": s.iteration,
                    "elapsed_ms": round(s.elapsed_ms, 2),
                    "metadata": s.metadata,
                }
                for s in r.samples
            ],
            "stats": {
                "avg_ms": round(r.avg_ms, 2),
                "median_ms": round(r.median_ms, 2),
                "min_ms": round(r.min_ms, 2),
                "max_ms": round(r.max_ms, 2),
                "p95_ms": round(r.p95_ms, 2),
                "stddev_ms": round(r.stddev_ms, 2),
                "n": len(r.samples),
            },
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n📄 JSON 결과 저장: {path}")


def load_previous_results(path: str) -> dict[str, Any]:
    """이전 벤치마크 결과를 로드합니다."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def print_comparison(
    current: dict[str, BenchmarkResult],
    previous: dict[str, Any],
):
    """이전 결과와 비교하여 변화량을 출력합니다."""
    print_header("COMPARISON WITH PREVIOUS RUN")

    for name, r in current.items():
        prev = previous.get(name, {}).get("stats", {})
        prev_avg = prev.get("avg_ms", 0)
        diff = r.avg_ms - prev_avg
        pct = (diff / prev_avg * 100) if prev_avg else 0

        arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
        color = "🔴" if diff > 10 else "🟢" if diff < -10 else "⚪"

        print(
            f"  {color} {name:<25} 이전: {prev_avg:>8.1f} ms → 현재: {r.avg_ms:>8.1f} ms  {arrow} {diff:+.1f} ms ({pct:+.1f}%)"
        )


# ─── 메인 ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Freebuff-Style Proactive Pipeline 성능 벤치마크",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="각 스테이지의 반복 횟수 (기본: 5)",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="프로젝트 루트 디렉토리 (기본: 현재 디렉토리)",
    )
    parser.add_argument(
        "--json",
        default="",
        nargs="?",
        const="benchmark_results.json",
        help="결과를 JSON 파일로 저장 (기본: benchmark_results.json)",
    )
    parser.add_argument(
        "--compare",
        default="",
        nargs="?",
        const="benchmark_results.json",
        help="이전 JSON 결과와 비교",
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="웜업 실행 건너뛰기",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        choices=[NAME_CONTEXT_ENRICH, NAME_CODE_REVIEW, NAME_RAG, NAME_MAX_ENGINE],
        help="건너뛸 스테이지",
    )
    args = parser.parse_args()

    project_root = os.path.abspath(args.project_dir)
    iterations = max(1, args.iterations)
    skip_list = set(args.skip or [])
    json_path = args.json
    compare_path = args.compare or json_path

    print("📊 Freebuff-Style Proactive Pipeline Benchmark")
    print(f"   프로젝트: {project_root}")
    print(f"   반복 횟수: {iterations}")
    print(f"   웜업: {'OFF' if args.no_warmup else 'ON'}")
    print()

    if not os.path.exists(os.path.join(project_root, "src/antigravity_k")):
        print("⚠️  프로젝트 디렉토리에서 src/antigravity_k 를 찾을 수 없습니다.")
        print("   --project-dir 플래그로 올바른 경로를 지정해주세요.")
        sys.exit(1)

    # 실제 import 가능 여부 검증
    try:
        sys.path.insert(0, project_root)
        from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer  # noqa: F401
    except ImportError as e:
        print(f"⚠️  antigravity_k 패키지 import 실패: {e}")
        print("   --project-dir 플래그로 올바른 경로를 지정해주세요.")
        sys.exit(1)

    # PYTHONPATH 설정
    sys.path.insert(0, project_root)

    stages = []

    if NAME_CONTEXT_ENRICH not in skip_list:
        stages.append(
            (NAME_CONTEXT_ENRICH, DESC_CONTEXT_ENRICH, benchmark_context_enrich),
        )
    if NAME_CODE_REVIEW not in skip_list:
        stages.append(
            (NAME_CODE_REVIEW, DESC_CODE_REVIEW, benchmark_code_review),
        )
    if NAME_RAG not in skip_list:
        stages.append(
            (NAME_RAG, DESC_RAG, benchmark_rag_indexing),
        )
    if NAME_MAX_ENGINE not in skip_list:
        stages.append(
            (NAME_MAX_ENGINE, DESC_MAX_ENGINE, benchmark_max_engine),
        )

    if not stages:
        print("⚠️  모든 스테이지가 skip되었습니다.")
        return

    results: dict[str, BenchmarkResult] = {}
    total_start = time.time()

    try:
        for name, desc, fn in stages:
            print(f"⏳ [{name}] 벤치마킹 중... ({iterations}회 반복)", end="", flush=True)
            try:
                result = run_benchmark(
                    name,
                    fn,
                    project_root,
                    iterations,
                    warmup=not args.no_warmup,
                )
                results[name] = result
                print(f" 완료 ({result.avg_ms:.1f} ms 평균)")
            except Exception as e:
                print(f" 실패: {e}")
                import traceback

                traceback.print_exc()

        total_elapsed = time.time() - total_start

        # 개별 결과 출력
        for name, desc, _ in stages:
            if name in results:
                print_result(name, desc, results[name])

        # 요약
        if results:
            print_summary(results, total_elapsed)

        # JSON 저장
        if json_path and results:
            export_json(results, json_path)

        # 이전 결과 비교
        if compare_path and results:
            previous = load_previous_results(compare_path)
            if previous:
                print_comparison(results, previous)
            else:
                print(f"\nℹ️  비교할 이전 결과가 없습니다: {compare_path}")
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(130)


if __name__ == "__main__":
    main()
