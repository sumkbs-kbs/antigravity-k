from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from antigravity_k.engine.unified_agent import UnifiedAgent
from tests.evals.real_coding.hard_composite_tasks import TASKS, CompositeTask


@dataclass(slots=True)
class CompositeResult:
    task_id: str
    task_type: str
    passed: bool
    used_web: bool
    used_graphify: bool
    seconds: float


def _score(outcome, task: CompositeTask) -> bool:
    if task.task_type == "code":
        return outcome.passed is True
    answer_lower = outcome.answer.lower()
    return all(n.lower() in answer_lower for n in task.must_contain)


def run_suite(generate_fn, model: str) -> list[CompositeResult]:
    agent = UnifiedAgent(generate_fn, model, project_root=Path("src"))
    results = []
    for task in TASKS:
        outcome = agent.run(task.prompt, test_code=task.test_code, max_repairs=2)
        passed = _score(outcome, task)
        results.append(
            CompositeResult(
                task.task_id, task.task_type, passed, outcome.used_web, outcome.used_graphify, outcome.total_seconds
            )
        )
        tools = []
        if outcome.used_web:
            tools.append("web")
        if outcome.used_graphify:
            tools.append("graphify")
        print(
            f"[{task.task_type}] {task.task_id}: {'PASS' if passed else 'FAIL'} tools=[{','.join(tools) or '-'}] {outcome.total_seconds:.0f}s",
            flush=True,
        )
    return results


def summarize(results: list[CompositeResult]) -> dict:
    by_type = {}
    for r in results:
        by_type.setdefault(r.task_type, {"total": 0, "passed": 0})
        by_type[r.task_type]["total"] += 1
        by_type[r.task_type]["passed"] += 1 if r.passed else 0
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "by_type": by_type,
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    mm = ModelManager(ModelRegistry())
    print(f"=== hard composite | model={model} ===")
    results = run_suite(mm.generate, model)
    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(results), indent=2))
