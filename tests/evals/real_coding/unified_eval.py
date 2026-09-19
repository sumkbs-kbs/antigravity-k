from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from antigravity_k.engine.unified_agent import UnifiedAgent
from tests.evals.real_coding.unified_tasks import TASKS, UnifiedTask


@dataclass(slots=True)
class UnifiedResult:
    task_id: str
    task_type: str
    passed: bool
    used_web: bool
    used_graphify: bool
    seconds: float
    steps: int


def _score(outcome, task: UnifiedTask) -> bool:
    if task.task_type == "code":
        return outcome.passed is True
    answer_lower = outcome.answer.lower()
    return all(needle.lower() in answer_lower for needle in task.must_contain)


def run_suite(generate_fn, model: str) -> list[UnifiedResult]:
    agent = UnifiedAgent(generate_fn, model, project_root=Path("src"))
    results = []
    for task in TASKS:
        outcome = agent.run(task.prompt, test_code=task.test_code, max_repairs=2)
        passed = _score(outcome, task)
        results.append(
            UnifiedResult(
                task.task_id,
                task.task_type,
                passed,
                outcome.used_web,
                outcome.used_graphify,
                outcome.total_seconds,
                len(outcome.steps),
            )
        )
        tools = []
        if outcome.used_web:
            tools.append("web")
        if outcome.used_graphify:
            tools.append("graphify")
        print(
            f"[{task.task_type}] {task.task_id}: {'PASS' if passed else 'FAIL'} "
            f"tools=[{','.join(tools) or '-'}] steps={len(outcome.steps)} {outcome.total_seconds:.0f}s",
            flush=True,
        )
    return results


def summarize(results: list[UnifiedResult]) -> dict:
    total = len(results)
    by_type = {}
    for r in results:
        by_type.setdefault(r.task_type, {"total": 0, "passed": 0})
        by_type[r.task_type]["total"] += 1
        by_type[r.task_type]["passed"] += 1 if r.passed else 0
    return {
        "total": total,
        "passed": sum(1 for r in results if r.passed),
        "used_web": sum(1 for r in results if r.used_web),
        "used_graphify": sum(1 for r in results if r.used_graphify),
        "by_type": by_type,
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    mm = ModelManager(ModelRegistry())
    print(f"=== unified agent | model={model} ===")
    results = run_suite(mm.generate, model)
    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(results), indent=2))
