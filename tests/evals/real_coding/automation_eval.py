from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from tests.evals.real_coding.automation_tasks import TASKS, AutomationTask

_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
_TOOL_CALL = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


@dataclass(slots=True)
class AttemptResult:
    passed: bool
    error: str
    exit_code: int
    tool_calls_detected: int


@dataclass(slots=True)
class TaskResult:
    task_id: str
    difficulty: str
    passed_first_try: bool
    passed_after_repairs: bool
    total_model_calls: int
    total_seconds: float
    attempts: list[AttemptResult] = field(default_factory=list)


def _build_prompt(task: AutomationTask, feedback: str, existing_files: list[str]) -> str:
    files_desc = ""
    if existing_files:
        files_desc = "These files already exist in the working directory: " + ", ".join(existing_files) + ".\n\n"
    base = (
        f"You are a file-automation agent. Operate on the current working directory.\n\n"
        f"Task: {task.prompt}\n\n"
        f"{files_desc}"
        f"Write a single Python script that performs the required file operations "
        f"using paths relative to the current directory. Put the script inside a "
        f"```python fenced block. The script will be executed as-is. Do not read "
        f"input or print anything.\n"
    )
    if feedback:
        base += (
            f"\nYour previous attempt failed verification:\n```\n{feedback}\n```\n"
            "Fix the script. Output only the corrected python fenced block.\n"
        )
    return base


def _extract_code(text: str) -> str:
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip()
    idx = text.find("import ")
    if idx == -1:
        idx = text.find("from ")
    if idx == -1:
        idx = text.find("open(")
    if idx != -1:
        return text[idx:].split("```")[0].strip()
    return text.strip()


def _setup_workdir(task: AutomationTask) -> Path:
    workdir = Path(tempfile.mkdtemp())
    for name, content in task.setup_files.items():
        (workdir / name).write_text(content, encoding="utf-8")
    return workdir


def _verify(workdir: Path, task: AutomationTask) -> AttemptResult:
    verify_path = workdir / "_verify.py"
    verify_path.write_text(task.verify, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "_verify.py"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=20,
    )
    error = ""
    if result.returncode != 0:
        combined = result.stdout + result.stderr
        error = combined[-2000:] if len(combined) > 2000 else combined
    return AttemptResult(
        passed=result.returncode == 0,
        error=error,
        exit_code=result.returncode,
        tool_calls_detected=0,
    )


def run_task(generate_fn, model: str, task: AutomationTask, max_repairs: int = 1) -> TaskResult:
    t0 = time.time()
    workdir = _setup_workdir(task)
    feedback = ""
    attempts: list[AttemptResult] = []
    try:
        for call_idx in range(max_repairs + 1):
            prompt = _build_prompt(task, feedback, list(task.setup_files.keys()))
            raw = generate_fn(prompt=prompt, target=model, max_tokens=2048, temperature=0.0)
            code = _extract_code(raw)
            script_path = workdir / "agent_action.py"
            script_path.write_text(code, encoding="utf-8")
            exec_result = subprocess.run(
                [sys.executable, "agent_action.py"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=20,
            )
            exec_error = ""
            if exec_result.returncode != 0:
                exec_error = (exec_result.stdout + exec_result.stderr)[-2000:]
            if exec_error:
                verdict = AttemptResult(
                    passed=False,
                    error=f"SCRIPT ERROR:\n{exec_error}",
                    exit_code=exec_result.returncode,
                    tool_calls_detected=1,
                )
            else:
                verdict = _verify(workdir, task)
            attempts.append(verdict)
            if verdict.passed:
                return TaskResult(
                    task.task_id, task.difficulty, call_idx == 0, True, call_idx + 1, time.time() - t0, attempts
                )
            feedback = verdict.error
    finally:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)
    return TaskResult(task.task_id, task.difficulty, False, False, max_repairs + 1, time.time() - t0, attempts)


def run_suite(generate_fn, model: str, max_repairs: int = 1) -> list[TaskResult]:
    results = []
    for task in TASKS:
        print(f"[run] {task.task_id} ({task.difficulty})...", flush=True)
        r = run_task(generate_fn, model, task, max_repairs=max_repairs)
        st = "PASS" if r.passed_after_repairs else "FAIL"
        first = "yes" if r.passed_first_try else "no"
        print(f"  -> {st} | first_try={first} | calls={r.total_model_calls} | {r.total_seconds:.1f}s", flush=True)
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
            for d in ("easy", "medium", "hard")
        },
    }


if __name__ == "__main__":
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:latest"
    repairs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    mm = ModelManager(ModelRegistry())
    results = run_suite(mm.generate, model, max_repairs=repairs)
    s = summarize(results)
    print("\n=== SUMMARY ===")
    print(json.dumps(s, indent=2))
    print(f"pass@1: {s['pass_at_1']}/{s['total']}")
    print(f"pass after repair: {s['pass_after_repair']}/{s['total']}")
