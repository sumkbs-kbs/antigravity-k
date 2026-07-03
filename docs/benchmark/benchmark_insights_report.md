# Proactive Pipeline Benchmark Insights Report

**Generated:** July 3, 2026 | **Runs:** 5 iterations per stage | **Total time:** 6.5s

---

## 01 — Overview Dashboard

### Pipeline Latency at a Glance

| Stage | Avg (ms) | Median | Min | Max | P95 | StdDev | n |
|:---|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **context_enrich** | 114.1 | 114.3 | 109.4 | 116.9 | 116.9 | 3.0 | 5 |
| **code_review** | 241.7 | 241.1 | 239.9 | 254.2 | 254.2 | 5.5 | 5 |
| **rag_indexing** | 681.4 | 677.4 | 661.6 | 715.1 | 715.1 | 19.1 | 5 |
| **max_engine** | 0.2 | 0.2 | 0.2 | 0.4 | 0.4 | 0.1 | 5 |

**Key insight:** RAG indexing dominates pipeline latency (~65% of total), followed by code review (~23%). context_enrich is ~11%. MAX Engine is effectively zero-cost.

### Bottleneck Distribution
```
context_enrich  ██████████████    114ms (11%)
code_review     ████████████████  242ms (23%)
rag_indexing    ████████████████  681ms (65%)
max_engine                        0.2ms (0%)
```

---

## 02 — Latency Trends

| Stage | StdDev | CV | Trend |
|:---|---:|:---:|:---|
| context_enrich | 3.0 ms | 2.6% | Flat (109–117 ms) |
| code_review | 5.5 ms | 2.3% | Flat (240–254 ms) |
| rag_indexing | 19.1 ms | 2.8% | Flat (662–715 ms) |
| max_engine | 0.1 ms | 33% | Sub-ms noise (expected) |

**Key insight:** All stages exhibit low variability (<3% CV). No regressions or flaky behavior across 5 iterations.

---

## 03a — Context Enrich Breakdown

- **build_tree (최초)** — 110.5 ms (97% of stage)
- **search (평균)** — 2.2 ms (2%)
- **summarize_files** — 1.4 ms (1%)

1,158 files indexed, 5,688 functions, 628 classes across 272.8 KB tree.

**28.7% improvement** vs initial baseline (159.9ms to 114.1ms)

---

## 03b — Code Review Breakdown

- **git diff --stat** — 47.2 ms (20%)
- **git diff (상세)** — 193.4 ms (80%)
- **LLM Mock 호출** — 0.03 ms (<1%)

**16.0% improvement** vs initial baseline (287.9ms to 241.7ms)

---

## 03c — MAX Engine Breakdown (all sub-ms)

| Component | Time (ms) |
|:---|---:|
| Config (1/2/3 models) | ~0.023 |
| Prompt (4 strategies) | ~0.003 |
| Selector (2/3 candidates) | ~0.040 / ~0.026 |
| Format trace | ~0.004 |
| **Total run()** | **0.2** |

Selector is the most expensive sub-component (manager.generate call).

---

## 03d — RAG Indexing Breakdown

### Main Pipeline
- **index_project** — 503.1 ms (74%)
- **search (hybrid)** — 88.0 ms (13%)
- **format_context** — 90.3 ms (13%)

### Search Mode Comparison
- **Semantic** — 44.6 ms
- **Keyword** — 40.7 ms
- **Hybrid (RRF)** — 83.4 ms (2x slower than either alone)

78 chunks indexed. Baseline established for new RAG stage.

---

## 04 — Heatmap

| Stage | Avg | Median | Min | Max | P95 | StdDev |
|:---|---:|:---:|:---:|:---:|:---:|:---:|
| context_enrich | 114 | 114 | 109 | 117 | 117 | 3.0 |
| code_review | 242 | 241 | 240 | 254 | 254 | 5.5 |
| rag_indexing | 681 | 677 | 662 | 715 | 715 | 19.1 |
| max_engine | 0.2 | 0.2 | 0.2 | 0.4 | 0.4 | 0.1 |

Three latency tiers: sub-ms (MAX), ~100ms (context), ~250ms (review), ~700ms (RAG).

---

## 05 — Sub-component Comparison

Top 3 bottlenecks across all stages:
1. **index_project** (503ms) — ChromaDB upsert + AST chunking
2. **git diff detail** (193ms) — full git diff read
3. **build_tree** (110ms) — file system walk + symbol extraction

---

## Action Items

| Priority | Area | Current | Target | Action |
|:--------:|:---|:---:|:---:|:---|
| 1 | RAG indexing | 503ms | <300ms | Batch ChromaDB upserts, parallelize chunking |
| 2 | git diff detail | 193ms | <100ms | Use --diff-filter or limit to changed file types |
| 3 | build_tree | 110ms | <60ms | Incremental watch-mode instead of full rebuild |
| 4 | MAX Engine | 0.2ms | — | Already optimal |
