#!/usr/bin/env python3
"""Run Continuous Evolution & Working Memory Benchmark for Antigravity-K (Qwen3.8-27B).

Validates:
1. Self-Evolving Prompt Compilation
2. Smart Breakpoint & Multi-Choice Clarification Gate
3. Long-Horizon Working Memory Compaction (ADRs & State Preservation)
"""

import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.prompt_compiler import PromptCompiler
from antigravity_k.engine.smart_breakpoint import SmartBreakpointGate
from antigravity_k.engine.working_memory_compactor import WorkingMemoryCompactor


def run_benchmark():
    print("=" * 75)
    print("🧬 RUNNING CONTINUOUS EVOLUTION & WORKING MEMORY BENCHMARK (Qwen3.8-27B)")
    print("=" * 75)

    passed = 0
    total = 3

    # 1. Prompt Compiler
    print("\n[1/3] Self-Evolving Prompt Optimizer (DSPy-style)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        compiler = PromptCompiler(tmpdir)
        compiler.record_trajectory("worker", "Fix bug in parser", "applied patch tool", "never overwrite file")
        compiled = compiler.compile_optimized_prompt("worker", "Base instructions")
        if "applied patch tool" in compiled and "never overwrite file" in compiled:
            print("  ✅ Passed (Golden trajectory compiled into Few-Shot rules)")
            passed += 1
        else:
            print("  ❌ Failed prompt compilation")

    # 2. Smart Breakpoint
    print("\n[2/3] Smart Breakpoint & Clarification Gate...")
    gate = SmartBreakpointGate(max_consecutive_failures=3)
    _ = gate.record_attempt(False)
    _ = gate.record_attempt(False)
    triggered = gate.record_attempt(False)
    if triggered:
        prompt = gate.generate_breakpoint("OAuth Setup", "401 Unauthorized", [("Use Mock", "mock")])
        if "OAuth Setup" in prompt.core_question and len(prompt.options) >= 2:
            print("  ✅ Passed (Breakpoint triggered and clean multiple-choice dialog synthesized)")
            passed += 1
        else:
            print("  ❌ Failed breakpoint dialog")
    else:
        print("  ❌ Failed breakpoint trigger")

    # 3. Long-Horizon Working Memory
    print("\n[3/3] Long-Horizon Working Memory Compaction...")
    simulated_msgs = [
        {"role": "user", "content": "Working on src/server.py"},
        {"role": "assistant", "content": "Updated src/server.py and tests/test_server.py"},
    ]
    state = WorkingMemoryCompactor.compact(simulated_msgs, adrs=["ADR-001: FastAPI"], pending_subgoals=["Deploy"])
    pinned = state.format_pinned_working_memory()
    if "ADR-001: FastAPI" in pinned and "src/server.py" in pinned:
        print("  ✅ Passed (ADRs and modified files preserved in compact 8k-token state)")
        passed += 1
    else:
        print("  ❌ Failed working memory compaction")

    print("\n" + "=" * 75)
    print(f"🏆 CONTINUOUS EVOLUTION SCORE: {passed}/{total} ({(passed / total) * 100:.0f}%)")
    print("=" * 75)
    return passed == total


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
