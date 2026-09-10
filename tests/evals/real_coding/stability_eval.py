"""Stability evaluation harness for coding tasks."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from antigravity_k.engine.unified_agent import UnifiedAgent
from tests.evals.real_coding.hard_composite_tasks import TASKS


@dataclass(slots=True)
class StabilityResult:
    task_id: str
    mode: str
    passed: bool
    seconds: float


CODE_TASK_IDS = {"code_impl_stack_min", "code_impl_decoder", "code_fix_concurrent"}


def run_stability(
    generate_fn: Callable[..., str],
    model: str,
    trials: int,
    mode: str,
    *,
    target_tasks: tuple[Any, ...] | None = None,
) -> list[StabilityResult]:
    agent = UnifiedAgent(generate_fn, model, project_root=Path("src"))
    results = []
    tasks_to_run = target_tasks if target_tasks is not None else TASKS
    for task in tasks_to_run:
        if task.task_id not in CODE_TASK_IDS:
            continue
        for trial in range(trials):
            if mode == "adaptive":
                outcome = agent.run(
                    task.prompt,
                    test_code=task.test_code,
                    max_repairs=1,
                    consistency_samples=3,
                    adaptive=True,
                )
            elif mode.startswith("c"):
                consistency = int(mode[1:])
                outcome = agent.run(
                    task.prompt,
                    test_code=task.test_code,
                    max_repairs=1,
                    consistency_samples=consistency,
                )
            else:
                outcome = agent.run(
                    task.prompt,
                    test_code=task.test_code,
                    max_repairs=2,
                    consistency_samples=1,
                )
            passed = outcome.passed is True
            results.append(StabilityResult(task.task_id, mode, passed, outcome.total_seconds))
            print(
                f"  [{task.task_id}] {mode} trial{trial + 1}: {'PASS' if passed else 'FAIL'} {outcome.total_seconds:.0f}s",
                flush=True,
            )
    return results


def summarize(results: list[StabilityResult]) -> dict[str, Any]:
    by_task: dict[str, dict[str, int]] = {}
    for r in results:
        by_task.setdefault(r.task_id, {"pass": 0, "total": 0})
        by_task[r.task_id]["total"] += 1
        by_task[r.task_id]["pass"] += 1 if r.passed else 0
    return {
        "mode": results[0].mode if results else "?",
        "overall_pass_rate": f"{sum(1 for r in results if r.passed)}/{len(results)}",
        "by_task": {k: f"{v['pass']}/{v['total']}" for k, v in by_task.items()},
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    target_model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    eval_mode = sys.argv[2] if len(sys.argv) > 2 else "c1"
    trial_count = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    mm = ModelManager(ModelRegistry())
    print(f"=== stability | model={target_model} mode={eval_mode} trials={trial_count} ===")
    eval_results = run_stability(mm.generate, target_model, trial_count, eval_mode)
    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(eval_results), indent=2))
