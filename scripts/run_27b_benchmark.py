#!/usr/bin/env python3
"""Run benchmark suite specifically tuned for Qwen3.8-27B and 30B-class models.

Evaluates:
1. Deterministic Code Verifier accuracy & latency
2. Active Tool Masking token savings
3. Error Distillation compactness and actionability
4. End-to-end task simulation health
"""

import sys
import time
from pathlib import Path
from typing import cast

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.code_verifier import DeterministicCodeVerifier
from antigravity_k.engine.error_distiller import ErrorDistiller
from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.structural_snapshot import StructuralSnapshotBuilder
from antigravity_k.engine.tool_masker import ActiveToolMasker


def run_benchmark():
    print("=" * 60)
    print("🚀 Running Antigravity-K 27B/30B Amplification Benchmark")
    print("=" * 60)

    score = 0
    max_score = 4

    # 1. Benchmark: Deterministic Code Verifier
    print("\n[1/4] Testing Deterministic Code Verifier (AST Guard)...")
    start = time.perf_counter()
    valid_py = "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)\n"
    invalid_py = "def fib(n:\n    return 42"
    res_valid = DeterministicCodeVerifier.verify_file("fib.py", content=valid_py)
    res_invalid = DeterministicCodeVerifier.verify_file("fib.py", content=invalid_py)
    elapsed_ms = (time.perf_counter() - start) * 1000

    if res_valid.is_valid and not res_invalid.is_valid and res_invalid.line_number == 1:
        print(f"  ✅ Passed AST verification in {elapsed_ms:.2f}ms")
        score += 1
    else:
        print("  ❌ AST verification failed")

    # 2. Benchmark: Active Tool Masker Token Savings
    print("\n[2/4] Testing Active Tool Masker...")
    mock_tools = [
        {"name": name}
        for name in [
            "read_file",
            "write_file",
            "replace_file_content",
            "git_status",
            "run_command",
            "web_search",
            "db_migration",
            "deploy",
            "payment",
        ]
    ]
    masker = ActiveToolMasker(mode=ExecutionMode.PLAN)
    plan_tools = cast(list[dict[str, str]], masker.filter_tools(mock_tools))
    reduction = (1 - len(plan_tools) / len(mock_tools)) * 100
    if len(plan_tools) < len(mock_tools) and "deploy" not in [t["name"] for t in plan_tools]:
        print(f"  ✅ Tool schema reduction: {reduction:.1f}% filtered in PLAN mode")
        score += 1
    else:
        print("  ❌ Tool masker failed")

    # 3. Benchmark: Error Distillation
    print("\n[3/4] Testing Error Distiller...")
    sample_trace = """Traceback (most recent call last):
  File "test.py", line 12, in do_work
    1 / 0
ZeroDivisionError: division by zero"""
    distilled = ErrorDistiller.distill("run_command", sample_trace)
    if "ZeroDivisionError" in distilled and "line 12" in distilled and len(distilled) <= 256:
        print(f"  ✅ Distilled {len(sample_trace)} chars -> {len(distilled)} chars cleanly")
        score += 1
    else:
        print("  ❌ Error distillation failed")

    # 4. Benchmark: Structural Snapshot Builder
    print("\n[4/4] Testing Structural Context Snapshot...")
    snapshot = StructuralSnapshotBuilder.build(Path.cwd(), max_tree_lines=15)
    pinned = snapshot.format_pinned_block()
    if "PINNED_STRUCTURAL_CONTEXT" in pinned:
        print(f"  ✅ Pinned snapshot generated cleanly ({len(pinned)} chars)")
        score += 1
    else:
        print("  ❌ Snapshot generation failed")

    print("\n" + "=" * 60)
    print(f"🏆 Final Amplification Benchmark Score: {score}/{max_score} ({(score / max_score) * 100:.0f}%)")
    print("=" * 60)
    return score == max_score


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
