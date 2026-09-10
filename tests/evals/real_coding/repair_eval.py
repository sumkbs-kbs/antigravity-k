from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from tests.evals.real_coding.tasks import TASKS, CodingTask

_PYTHON_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True, slots=True)
class AttemptResult:
    code: str
    passed: bool
    error_excerpt: str
    exit_code: int


@dataclass(slots=True)
class TaskResult:
    task_id: str
    difficulty: str
    passed_first_try: bool
    passed_after_repairs: bool
    total_model_calls: int
    total_seconds: float
    attempts: list[AttemptResult] = field(default_factory=list)

    test_in_prompt: bool = False
    rich_feedback: bool = False


def _extract_code(text: str) -> str:
    match = _PYTHON_CODE_FENCE.search(text)
    if match:
        return match.group(1).strip()
    open_idx = text.find("def ")
    if open_idx != -1:
        return text[open_idx:].split("```")[0].strip()
    return text.strip()


def _build_prompt(task: CodingTask, feedback: str, *, test_in_prompt: bool = False) -> str:
    base = f"You are an expert Python programmer. Solve this coding task.\n\nProblem: {task.problem}\n\n"
    if test_in_prompt:
        base += (
            "Your solution will be verified against these exact tests:\n"
            "```python\n"
            f"{task.test_code}\n"
            "```\n\n"
            "Make sure every assertion passes, including edge cases.\n\n"
        )
    base += (
        "Write only the Python code that solves it. The solution must define "
        "the required function(s). Put the code in a ```python fenced block.\n"
    )
    if feedback:
        base += (
            f"\nYour previous attempt failed. Here is the test error output:\n"
            f"```\n{feedback}\n```\n"
            "Fix the code so the tests pass. Output only the corrected code in "
            "a python fenced block.\n"
        )
    return base


def _run_pytest(workdir: Path, *, rich: bool = False) -> AttemptResult:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "--tb=long", "test_solution.py"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    error = ""
    if result.returncode != 0:
        combined = result.stdout + result.stderr
        limit = 4000 if rich else 1500
        error = combined[-limit:] if len(combined) > limit else combined
    return AttemptResult(
        code="",
        passed=result.returncode == 0,
        error_excerpt=error,
        exit_code=result.returncode,
    )


def _evaluate_attempt(task: CodingTask, code: str, workdir: Path, *, rich: bool = False) -> AttemptResult:
    solution_path = workdir / "solution.py"
    solution_path.write_text(code, encoding="utf-8")
    (workdir / "test_solution.py").write_text(task.test_code, encoding="utf-8")
    verdict = _run_pytest(workdir, rich=rich)
    return AttemptResult(
        code=code,
        passed=verdict.passed,
        error_excerpt=verdict.error_excerpt,
        exit_code=verdict.exit_code,
    )


def run_task(
    generate_fn,
    model: str,
    task: CodingTask,
    max_repairs: int = 2,
    *,
    test_in_prompt: bool = False,
    rich_feedback: bool = False,
) -> TaskResult:
    t0 = time.time()
    feedback = ""
    attempts: list[AttemptResult] = []
    with tempfile.TemporaryDirectory() as raw_dir:
        workdir = Path(raw_dir)
        for call_idx in range(max_repairs + 1):
            prompt = _build_prompt(task, feedback, test_in_prompt=test_in_prompt)
            raw = generate_fn(prompt=prompt, target=model, max_tokens=2048, temperature=0.0)
            code = _extract_code(raw)
            verdict = _evaluate_attempt(task, code, workdir, rich=rich_feedback)
            verdict = AttemptResult(
                code=code[:200], passed=verdict.passed, error_excerpt=verdict.error_excerpt, exit_code=verdict.exit_code
            )
            attempts.append(verdict)
            if verdict.passed:
                return TaskResult(
                    task_id=task.task_id,
                    difficulty=task.difficulty,
                    passed_first_try=(call_idx == 0),
                    passed_after_repairs=True,
                    total_model_calls=call_idx + 1,
                    total_seconds=time.time() - t0,
                    attempts=attempts,
                    test_in_prompt=test_in_prompt,
                    rich_feedback=rich_feedback,
                )
            feedback = verdict.error_excerpt
    return TaskResult(
        task_id=task.task_id,
        difficulty=task.difficulty,
        passed_first_try=False,
        passed_after_repairs=False,
        total_model_calls=max_repairs + 1,
        total_seconds=time.time() - t0,
        attempts=attempts,
        test_in_prompt=test_in_prompt,
        rich_feedback=rich_feedback,
    )


def run_suite(
    generate_fn,
    model: str,
    max_repairs: int = 2,
    *,
    test_in_prompt: bool = False,
    rich_feedback: bool = False,
) -> list[TaskResult]:
    results: list[TaskResult] = []
    for task in TASKS:
        print(f"[run] {task.task_id} ({task.difficulty})...", flush=True)
        result = run_task(
            generate_fn,
            model,
            task,
            max_repairs=max_repairs,
            test_in_prompt=test_in_prompt,
            rich_feedback=rich_feedback,
        )
        status = "PASS" if result.passed_after_repairs else "FAIL"
        first = "yes" if result.passed_first_try else "no"
        print(
            f"  -> {status} | first_try={first} | calls={result.total_model_calls} | {result.total_seconds:.1f}s",
            flush=True,
        )
        results.append(result)
    return results


def summarize(results: list[TaskResult]) -> dict:
    total = len(results)
    first_try = sum(1 for r in results if r.passed_first_try)
    after_repair = sum(1 for r in results if r.passed_after_repairs)
    return {
        "total": total,
        "pass_at_1": first_try,
        "pass_after_repair": after_repair,
        "repair_uplift": after_repair - first_try,
        "by_difficulty": {
            d: {
                "total": sum(1 for r in results if r.difficulty == d),
                "pass_at_1": sum(1 for r in results if r.difficulty == d and r.passed_first_try),
                "pass_after_repair": sum(1 for r in results if r.difficulty == d and r.passed_after_repairs),
            }
            for d in ("easy", "medium", "hard")
        },
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    target_model = sys.argv[1] if len(sys.argv) > 1 else "mlx-qwen3-30b-a3b-4bit"
    repairs = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    test_in_prompt = "--test-in-prompt" in sys.argv
    rich_feedback = "--rich-feedback" in sys.argv
    mm = ModelManager(ModelRegistry())
    results = run_suite(
        mm.generate,
        target_model,
        max_repairs=repairs,
        test_in_prompt=test_in_prompt,
        rich_feedback=rich_feedback,
    )
    summary = summarize(results)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"pass@1: {summary['pass_at_1']}/{summary['total']}")
    print(f"pass after repair: {summary['pass_after_repair']}/{summary['total']}")
    print(f"repair uplift: +{summary['repair_uplift']}")
