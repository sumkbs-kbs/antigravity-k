from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from antigravity_k.engine.optimizers.graphify_builder import build_file_index_rows, build_graph, hybrid_retrieve
from tests.evals.real_coding.scale_eval import _score
from tests.evals.real_coding.scale_tasks import TASKS, ScaleQuestion


@dataclass(slots=True)
class HybridResult:
    qid: str
    passed: bool
    context_tokens: int


def _hybrid_prompt(q: ScaleQuestion, rows: list[str]) -> tuple[str, int]:
    index = "\n".join(rows)
    p = (
        f"Here are the most relevant files for your question (semantic + keyword "
        f"retrieval), with their symbols:\n\n{index}\n\n"
        f"Question: {q.question}\n\nAnswer with file name(s) and symbol name(s)."
    )
    return p, len(p) // 4


def run_suite(generate_fn, model: str) -> list[HybridResult]:
    graph = build_graph(Path("src"))
    results = []
    for q in TASKS:
        files = hybrid_retrieve(graph, q.question, top_k=12)
        rows = build_file_index_rows(graph, files, symbols_per_file=10)
        prompt, tokens = _hybrid_prompt(q, rows)
        raw = generate_fn(prompt=prompt, target=model, max_tokens=600, temperature=0.0)
        passed = _score(raw, q)
        results.append(HybridResult(q.qid, passed, tokens))
        print(f"[hybrid] {q.qid}: {'PASS' if passed else 'FAIL'} ctx~{tokens}t", flush=True)
    return results


def summarize(results: list[HybridResult]) -> dict:
    total = len(results)
    return {
        "total": total,
        "passed": sum(1 for r in results if r.passed),
        "avg_context_tokens": round(sum(r.context_tokens for r in results) / total) if total else 0,
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    mm = ModelManager(ModelRegistry())
    print(f"=== hybrid (embedding+keyword) | model={model} ===")
    results = run_suite(mm.generate, model)
    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(results), indent=2))
