from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from tests.evals.real_coding.swe_tasks import TASKS, SWETask

_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


@dataclass(slots=True)
class Attempt:
    passed: bool
    error: str


@dataclass(slots=True)
class TaskResult:
    task_id: str
    difficulty: str
    passed_first_try: bool
    passed_after_repairs: bool
    total_model_calls: int
    total_seconds: float
    attempts: list[Attempt] = field(default_factory=list)


def _extract_code(text: str) -> str:
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip()
    idx = text.find("def ")
    if idx != -1:
        return text[idx:].split("```")[0].strip()
    return text.strip()


def _capture_failure(workdir: Path, rich: bool) -> str:
    args = [sys.executable, "-m", "pytest", "-x", "-q"]
    args.append("--tb=long" if rich else "--tb=short")
    args.append("test_solution.py")
    try:
        result = subprocess.run(args, cwd=workdir, capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired:
        return "TIMEOUT: the function likely has an infinite loop. Re-examine loop termination."
    combined = result.stdout + result.stderr
    if result.returncode == 0:
        return ""
    limit = 3000 if rich else 1200
    return combined[-limit:] if len(combined) > limit else combined


def _build_single_shot_prompt(task: SWETask, error: str) -> str:
    base = (
        f"You are fixing a bug. Here is the current (buggy) code:\n\n"
        f"```python\n{task.buggy_code}\n```\n\n"
        f"Scenario: {task.scenario}\n\n"
        f"When run, the tests fail with this output:\n```\n{error}\n```\n\n"
        f"Return the COMPLETE corrected code in a ```python fenced block. "
        f"Keep the same function name and signature.\n"
    )
    return base


def _build_multistep_prompt(task: SWETask, error: str, attempt_num: int) -> str:
    steps = (
        "Reason step by step:\n"
        "1. Identify which assertion failed and the exact inputs.\n"
        "2. Trace the code path for those inputs.\n"
        "3. State the root cause in one sentence.\n"
        "4. Write the minimal fix.\n"
    )
    return (
        f"You are a senior debugging an existing bug (attempt {attempt_num}).\n\n"
        f"Current code:\n```python\n{task.buggy_code if attempt_num == 1 else ''}\n```\n\n"
        f"{steps}\n"
        f"Scenario: {task.scenario}\n\n"
        f"Full failure trace:\n```\n{error}\n```\n\n"
        f"Return ONLY the complete corrected code in a ```python fenced block.\n"
    )


def _verify(workdir: Path) -> Attempt:
    error = _capture_failure(workdir, rich=False)
    return Attempt(passed=(error == ""), error=error)


def run_task(generate_fn, model: str, task: SWETask, max_repairs: int, mode: str) -> TaskResult:
    t0 = time.time()
    workdir = Path(tempfile.mkdtemp())
    initial_error = ""
    try:
        (workdir / "test_solution.py").write_text(task.test_code)
        (workdir / "solution.py").write_text(task.buggy_code)
        initial_error = _capture_failure(workdir, rich=True)
        feedback = initial_error
        attempts: list[Attempt] = []
        for call_idx in range(max_repairs + 1):
            if mode == "multistep":
                prompt = _build_multistep_prompt(task, feedback, call_idx + 1)
            else:
                prompt = _build_single_shot_prompt(task, feedback)
            raw = generate_fn(prompt=prompt, target=model, max_tokens=2048, temperature=0.0)
            code = _extract_code(raw)
            (workdir / "solution.py").write_text(code)
            verdict = _verify(workdir)
            attempts.append(verdict)
            if verdict.passed:
                return TaskResult(
                    task.task_id, task.difficulty, call_idx == 0, True, call_idx + 1, time.time() - t0, attempts
                )
            feedback = verdict.error
        return TaskResult(task.task_id, task.difficulty, False, False, max_repairs + 1, time.time() - t0, attempts)
    finally:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)


def run_suite(generate_fn, model: str, max_repairs: int, mode: str) -> list[TaskResult]:
    results = []
    for task in TASKS:
        print(f"[run {mode}] {task.task_id} ({task.difficulty})...", flush=True)
        r = run_task(generate_fn, model, task, max_repairs, mode)
        st = "PASS" if r.passed_after_repairs else "FAIL"
        first = "yes" if r.passed_first_try else "no"
        print(f"  -> {st} | first_try={first} | calls={r.total_model_calls} | {r.total_seconds:.0f}s", flush=True)
        results.append(r)
    return results


def summarize(results: list[TaskResult]) -> dict:
    total = len(results)
    first = sum(1 for r in results if r.passed_first_try)
    after = sum(1 for r in results if r.passed_after_repairs)
    return {
        "total": total,
        "pass_at_1": first,
        "pass_after_repair": after,
        "repair_uplift": after - first,
        "by_difficulty": {
            d: {
                "total": sum(1 for r in results if r.difficulty == d),
                "pass_at_1": sum(1 for r in results if r.difficulty == d and r.passed_first_try),
                "pass_after_repair": sum(1 for r in results if r.difficulty == d and r.passed_after_repairs),
            }
            for d in ("medium", "hard")
        },
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    repairs = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    mode = sys.argv[3] if len(sys.argv) > 3 else "single"
    mm = ModelManager(ModelRegistry())
    results = run_suite(mm.generate, model, repairs, mode)
    s = summarize(results)
    print("\n=== SUMMARY ===")
    print(json.dumps(s, indent=2))
