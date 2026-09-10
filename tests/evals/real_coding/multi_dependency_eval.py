from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from tests.evals.real_coding.multi_dependency_tasks import TASKS, DependencyTask

_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


@dataclass(slots=True)
class TaskResult:
    task_id: str
    passed_first_try: bool
    passed_after_repairs: bool
    total_model_calls: int
    total_seconds: float


def _extract_code(text: str) -> str:
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip()
    idx = text.find("def ")
    if idx == -1:
        idx = text.find("class ")
    if idx != -1:
        return text[idx:].split("```")[0].strip()
    return text.strip()


def _capture_failure(workdir: Path, rich: bool) -> str:
    args = [sys.executable, "-m", "pytest", "-x", "-q", "--tb=long" if rich else "--tb=short", "test_solution.py"]
    try:
        result = subprocess.run(args, cwd=workdir, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return "TIMEOUT: likely infinite loop."
    if result.returncode == 0:
        return ""
    combined = result.stdout + result.stderr
    limit = 3000 if rich else 1200
    return combined[-limit:] if len(combined) > limit else combined


def _build_prompt(task: DependencyTask, error: str) -> str:
    return (
        f"You are debugging a multi-function Python module. The test imports several "
        f"functions; the failing test may call one function but the ROOT CAUSE is often "
        f"in a DIFFERENT helper it depends on. Trace the dependencies.\n\n"
        f"Scenario: {task.scenario}\n\n"
        f"Current module (solution.py):\n```python\n{task.module_code}\n```\n\n"
        f"Failure trace:\n```\n{error}\n```\n\n"
        f"Return the COMPLETE corrected module in a ```python fenced block. "
        f"Fix the root cause, keep all function names and signatures.\n"
    )


def run_task(generate_fn, model: str, task: DependencyTask, max_repairs: int) -> TaskResult:
    t0 = time.time()
    workdir = Path(tempfile.mkdtemp())
    try:
        (workdir / "test_solution.py").write_text(task.test_code)
        (workdir / "solution.py").write_text(task.module_code)
        feedback = _capture_failure(workdir, rich=True)
        for call_idx in range(max_repairs + 1):
            prompt = _build_prompt(task, feedback)
            raw = generate_fn(prompt=prompt, target=model, max_tokens=2048, temperature=0.0)
            code = _extract_code(raw)
            (workdir / "solution.py").write_text(code)
            error = _capture_failure(workdir, rich=False)
            if not error:
                return TaskResult(task.task_id, call_idx == 0, True, call_idx + 1, time.time() - t0)
            feedback = error
        return TaskResult(task.task_id, False, False, max_repairs + 1, time.time() - t0)
    finally:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)


def run_suite(generate_fn, model: str, max_repairs: int) -> list[TaskResult]:
    results = []
    for task in TASKS:
        print(f"[run] {task.task_id} ({task.difficulty})...", flush=True)
        r = run_task(generate_fn, model, task, max_repairs)
        st = "PASS" if r.passed_after_repairs else "FAIL"
        first = "yes" if r.passed_first_try else "no"
        print(f"  -> {st} | first_try={first} | calls={r.total_model_calls} | {r.total_seconds:.0f}s", flush=True)
        results.append(r)
    return results


def summarize(results: list[TaskResult]) -> dict:
    total = len(results)
    return {
        "total": total,
        "pass_at_1": sum(1 for r in results if r.passed_first_try),
        "pass_after_repair": sum(1 for r in results if r.passed_after_repairs),
        "repair_uplift": sum(1 for r in results if r.passed_after_repairs)
        - sum(1 for r in results if r.passed_first_try),
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    repairs = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    mm = ModelManager(ModelRegistry())
    results = run_suite(mm.generate, model, repairs)
    s = summarize(results)
    print("\n=== SUMMARY ===")
    print(json.dumps(s, indent=2))
