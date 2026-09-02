#!/usr/bin/env python3
"""Integrated Frontier Amplification Suite for Qwen3.8-27B.

Validates the full chain of 27B amplification capabilities:
1. Robust Tool Call Parsing & Self-Healing
2. Subgoal DAG Planning & Topological Ordering
3. AST Symbol Navigation
4. Post-Write Deterministic Code Verifier
5. Automated TDD & Assertion Extraction
6. Episodic Reflexion & Negative Constraint Injection
7. Error Distillation
8. Active Tool Masking
"""

import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.code_verifier import DeterministicCodeVerifier
from antigravity_k.engine.error_distiller import ErrorDistiller
from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.reflexion_memory import ReflexionMemory
from antigravity_k.engine.robust_tool_parser import RobustToolParser
from antigravity_k.engine.subgoal_graph import SubgoalGraph
from antigravity_k.engine.symbol_navigator import SymbolNavigator
from antigravity_k.engine.tdd_verifier import TDDVerifier
from antigravity_k.engine.tool_masker import ActiveToolMasker


def run_frontier_tests():
    print("=" * 70)
    print("🔥 Running Antigravity-K Qwen3.8-27B Frontier Amplification Test Suite")
    print("=" * 70)

    passed_count = 0
    total_tests = 8

    # Test 1: Self-Healing Tool Parser
    print("\n[1/8] Testing Robust Tool Call Parser (Glitch Healing)...")
    malformed = '<tool_call>{"name": "write_file", "arguments": {"file_path": "test.py", "flag": True,}}</tool_call>'
    calls = RobustToolParser.extract_tool_calls(malformed)
    if len(calls) == 1 and calls[0].arguments.get("flag") is True:
        print("  ✅ Successfully healed trailing comma and Python booleans")
        passed_count += 1
    else:
        print("  ❌ Failed tool call parser healing")

    # Test 2: Subgoal DAG Execution
    print("\n[2/8] Testing Deterministic Subgoal DAG Engine...")
    dag = SubgoalGraph("Build microservice")
    dag.add_subgoal("design", "Design API schema")
    dag.add_subgoal("code", "Implement routes", depends_on=["design"])
    dag.add_subgoal("test", "Run integration tests", depends_on=["code"])

    ready_init = dag.get_ready_subgoals()
    dag.complete_subgoal("design")
    ready_after = dag.get_ready_subgoals()
    if len(ready_init) == 1 and ready_init[0].task_id == "design" and ready_after[0].task_id == "code":
        print("  ✅ DAG readiness and dependency propagation verified")
        passed_count += 1
    else:
        print("  ❌ DAG dependency resolution failed")

    # Test 3: AST Symbol Navigator
    print("\n[3/8] Testing Symbol-Aware Code Graph Navigator...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        (tmp_root / "service.py").write_text(
            "class PaymentProcessor:\n    def charge(self, amount):\n        pass\n", encoding="utf-8"
        )
        nav = SymbolNavigator(tmp_root)
        results = nav.find_symbol("PaymentProcessor")
        if len(results) == 1 and results[0].kind == "class":
            print(
                f"  ✅ Symbol located instantly: {results[0].signature} at {results[0].file_path}:{results[0].line_number}"
            )
            passed_count += 1
        else:
            print("  ❌ Symbol navigator failed")

    # Test 4: AST Syntax Verifier
    print("\n[4/8] Testing Deterministic Code Verifier (AST Guard)...")
    res = DeterministicCodeVerifier.verify_file("app.py", content="def hello():\n    return 'world'\n")
    if res.is_valid:
        print("  ✅ AST verified cleanly with 0ms latency")
        passed_count += 1
    else:
        print("  ❌ AST verification failed")

    # Test 5: TDD Assertion Extraction
    print("\n[5/8] Testing TDD Verifier (Assertion Extraction)...")
    mock_out = "FAILED tests/test_core.py::test_auth - AssertionError: 401 != 200"
    tdd_res = TDDVerifier._parse_pytest_output(mock_out, is_zero_return=False)
    if not tdd_res.passed and "test_auth" in tdd_res.format_tdd_feedback():
        print("  ✅ High-signal TDD failure feedback extracted")
        passed_count += 1
    else:
        print("  ❌ TDD parsing failed")

    # Test 6: Episodic Reflexion & Negative Constraints
    print("\n[6/8] Testing Episodic Reflexion Memory...")
    reflexion = ReflexionMemory()
    reflexion.record_failure("file write", "overwriting file directly", "wiped configuration", "use patch tool instead")
    prompt = reflexion.render_negative_constraints_prompt()
    if "NEGATIVE CONSTRAINTS" in prompt and "overwriting file directly" in prompt:
        print("  ✅ Negative constraint prompt generated cleanly")
        passed_count += 1
    else:
        print("  ❌ Reflexion memory failed")

    # Test 7: Error Distiller
    print("\n[7/8] Testing Error Distillation...")
    trace = "Traceback (most recent call last):\n  File 'a.py', line 10, in run\n    1/0\nZeroDivisionError: division by zero"
    distilled = ErrorDistiller.distill("tool", trace)
    if "ZeroDivisionError" in distilled and "line 10" in distilled:
        print("  ✅ Traceback distilled to actionable feedback")
        passed_count += 1
    else:
        print("  ❌ Error distillation failed")

    # Test 8: Active Tool Masker
    print("\n[8/8] Testing Active Tool Masking...")
    masker = ActiveToolMasker(mode=ExecutionMode.PLAN)
    filtered = masker.filter_tools([{"name": "read_file"}, {"name": "deploy"}, {"name": "payment"}])
    filtered_names = [getattr(item, "name", None) for item in filtered]
    if len(filtered) == 1 and filtered_names == ["read_file"]:
        print("  ✅ Dangerous and non-plan tools filtered in PLAN mode")
        passed_count += 1
    else:
        print("  ❌ Tool masker failed")

    print("\n" + "=" * 70)
    print(
        f"🏆 Final Frontier Amplification Score: {passed_count}/{total_tests} ({(passed_count/total_tests)*100:.0f}%)"
    )
    print("=" * 70)
    return passed_count == total_tests


if __name__ == "__main__":
    success = run_frontier_tests()
    sys.exit(0 if success else 1)
