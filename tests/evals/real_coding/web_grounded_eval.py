from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from antigravity_k.tools.ssak_search_client import grounded_context
from tests.evals.real_coding.web_grounded_tasks import TASKS, GroundedQATask


@dataclass(slots=True)
class QAResult:
    task_id: str
    passed: bool
    needs_web: bool


def _build_prompt(task: GroundedQATask, web_context: str) -> str:
    ctx = ""
    if web_context:
        ctx = f"\n\nReference information from web search:\n{web_context}\n"
    return (
        f"Answer this technical question precisely and concisely (2-4 sentences).{ctx}\n\n"
        f"Question: {task.question}\n\n"
        "Be specific: include exact names, syntax, and version numbers when relevant."
    )


def _score(answer: str, must_contain: tuple[str, ...]) -> bool:
    lower = answer.lower()
    return all(needle.lower() in lower for needle in must_contain)


def run_one(generate_fn, model: str, task: GroundedQATask, *, use_web: bool) -> QAResult:
    web_ctx = ""
    if use_web:
        web_ctx = grounded_context(task.question, max_results=4)
    prompt = _build_prompt(task, web_ctx)
    raw = generate_fn(prompt=prompt, target=model, max_tokens=600, temperature=0.0)
    passed = _score(raw, task.must_contain)
    return QAResult(task.task_id, passed, task.needs_web)


def run_suite(generate_fn, model: str, *, use_web: bool) -> list[QAResult]:
    results = []
    for task in TASKS:
        r = run_one(generate_fn, model, task, use_web=use_web)
        tag = "web" if use_web else "no-web"
        print(f"[{tag}] {task.task_id}: {'PASS' if r.passed else 'FAIL'} (needs_web={r.needs_web})", flush=True)
        results.append(r)
    return results


def summarize(results: list[QAResult]) -> dict:
    total = len(results)
    web_tasks = [r for r in results if r.needs_web]
    local_tasks = [r for r in results if not r.needs_web]
    return {
        "total": total,
        "passed": sum(1 for r in results if r.passed),
        "web_tasks": {"total": len(web_tasks), "passed": sum(1 for r in web_tasks if r.passed)},
        "local_tasks": {"total": len(local_tasks), "passed": sum(1 for r in local_tasks if r.passed)},
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    use_web = len(sys.argv) > 2 and sys.argv[2] == "web"
    mm = ModelManager(ModelRegistry())
    print(f"=== {'WEB-AUGMENTED' if use_web else 'NO-WEB'} | model={model} ===")
    results = run_suite(mm.generate, model, use_web=use_web)
    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(results), indent=2))
