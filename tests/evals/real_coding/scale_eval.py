from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from antigravity_k.engine.optimizers.graphify_builder import build_graph, query_graph
from tests.evals.real_coding.scale_tasks import TASKS, ScaleQuestion


@dataclass(slots=True)
class ScaleResult:
    qid: str
    passed: bool
    context_tokens: int
    answer: str


def _naive_prompt(q: ScaleQuestion) -> tuple[str, int]:
    p = (
        f"Question about a 343-file Python codebase (SSAK-AI):\n{q.question}\n\n"
        f"Answer with file name(s) and symbol name(s). If you don't know, say so."
    )
    return p, len(p) // 4


def _build_full_index(graph) -> str:
    fs: dict[str, list[str]] = {}
    for n in graph.nodes:
        if n.kind in ("class", "function"):
            fs.setdefault(n.file, []).append(n.name)
    lines = [f"{Path(f).name} ({f}): {', '.join(s[:10])}" for f, s in sorted(fs.items())]
    return "\n".join(lines)


def _full_prompt(q: ScaleQuestion, full_index: str) -> tuple[str, int]:
    p = (
        f"Here is the complete structural index of a 343-file Python codebase "
        f"(file: symbols defined):\n\n{full_index}\n\n"
        f"Question: {q.question}\n\nAnswer with file name(s) and symbol name(s)."
    )
    return p, len(p) // 4


def _build_targeted_index(graph, q: ScaleQuestion) -> str:
    keywords = [
        w.lower()
        for w in q.question.replace("?", "").split()
        if len(w) > 3 and w.lower() not in {"which", "where", "what", "that", "this", "defined"}
    ]
    seen: set[str] = set()
    rows: list[str] = []
    for kw in keywords[:5]:
        for hit in query_graph(graph, kw, limit=4):
            key = hit.file
            if key in seen:
                continue
            seen.add(key)
            syms = [n.name for n in graph.nodes if n.file == key][:10]
            rows.append(f"{Path(key).name} ({key}): {', '.join(syms)}")
    return "\n".join(rows[:20])


def _targeted_prompt(q: ScaleQuestion, targeted_index: str) -> tuple[str, int]:
    p = (
        f"Here are the most relevant files for your question (file: symbols):\n\n{targeted_index}\n\n"
        f"Question: {q.question}\n\nAnswer with file name(s) and symbol name(s)."
    )
    return p, len(p) // 4


def _score(answer: str, q: ScaleQuestion) -> bool:
    lower = answer.lower()
    return all(f.lower().replace(".py", "") in lower for f in q.expected_files[:1])


def run_suite(generate_fn, model: str, mode: str) -> list[ScaleResult]:
    graph = build_graph(Path("src"))
    full_index = _build_full_index(graph)
    results = []
    for q in TASKS:
        if mode == "naive":
            prompt, tokens = _naive_prompt(q)
        elif mode == "full":
            prompt, tokens = _full_prompt(q, full_index)
        else:
            targeted = _build_targeted_index(graph, q)
            prompt, tokens = _targeted_prompt(q, targeted)
        raw = generate_fn(prompt=prompt, target=model, max_tokens=600, temperature=0.0)
        passed = _score(raw, q)
        results.append(ScaleResult(q.qid, passed, tokens, raw[:200]))
        print(f"[{mode}] {q.qid}: {'PASS' if passed else 'FAIL'} ctx~{tokens}t", flush=True)
    return results


def summarize(results: list[ScaleResult]) -> dict:
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
    mode = sys.argv[2] if len(sys.argv) > 2 else "targeted"
    mm = ModelManager(ModelRegistry())
    print(f"=== mode={mode} | model={model} ===")
    results = run_suite(mm.generate, model, mode)
    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(results), indent=2))
