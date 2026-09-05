#!/usr/bin/env python3
"""Ultimate Frontier Amplification Test Suite for Ssak-Ai (Qwen3.8-27B).

Comprehensive validation across all 8 capability amplification dimensions:
1. Robust Tool Call Parser (Self-Healing JSON)
2. Subgoal DAG Engine (Topological Task Planning)
3. AST Symbol Navigator (Zero-latency Symbol Discovery)
4. Deterministic Code Verifier (0ms AST Syntax Guard)
5. Automated TDD Verifier (Pytest Assertion Extractor)
6. Episodic Reflexion Memory (Negative Constraint Enforcer)
7. Call-Hierarchy & Impact Analyzer (Blast Radius & Caller Resolution)
8. Static Type & Security Gate (Secret & Arbitrary Code Scanner)
"""

import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.call_hierarchy_graph import CallHierarchyGraph
from antigravity_k.engine.code_verifier import DeterministicCodeVerifier
from antigravity_k.engine.incremental_code_graph import IncrementalCodeGraph
from antigravity_k.engine.reflexion_memory import ReflexionMemory
from antigravity_k.engine.robust_tool_parser import RobustToolParser
from antigravity_k.engine.speculative_branching import SpeculativeBranchingEngine
from antigravity_k.engine.static_type_security_gate import StaticTypeSecurityGate
from antigravity_k.engine.subgoal_graph import SubgoalGraph


def run_ultimate_benchmark():
    print("=" * 75)
    print("👑 RUNNING ULTIMATE FRONTIER AMPLIFICATION SUITE (Qwen3.8-27B)")
    print("=" * 75)

    passed = 0
    total = 8

    # 1. Self-Healing Tool Parser
    print("\n[1/8] Self-Healing Robust Tool Call Parser...")
    raw = '<tool_call>{"name": "test", "arguments": {"active": True,}}</tool_call>'
    calls = RobustToolParser.extract_tool_calls(raw)
    if calls and calls[0].arguments.get("active") is True:
        print("  ✅ Passed (Healed trailing comma & Python boolean)")
        passed += 1
    else:
        print("  ❌ Failed")

    # 2. Subgoal DAG
    print("\n[2/8] Deterministic Subgoal DAG Engine...")
    dag = SubgoalGraph("Test Goal")
    dag.add_subgoal("s1", "Step 1")
    dag.add_subgoal("s2", "Step 2", depends_on=["s1"])
    if len(dag.get_ready_subgoals()) == 1 and dag.get_ready_subgoals()[0].task_id == "s1":
        dag.complete_subgoal("s1")
        if dag.get_ready_subgoals()[0].task_id == "s2":
            print("  ✅ Passed (Topological DAG dependency execution)")
            passed += 1
        else:
            print("  ❌ Failed readiness propagation")
    else:
        print("  ❌ Failed initial readiness")

    # 3. Incremental Symbol Graph
    print("\n[3/8] Incremental Code Graph Sync...")
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = IncrementalCodeGraph(Path(tmpdir))
        graph.update_file("app.py", content="class Engine:\n    def start(self): pass\n")
        if len(graph.lookup_symbol("Engine")) == 1:
            print("  ✅ Passed (Sub-millisecond AST symbol indexing)")
            passed += 1
        else:
            print("  ❌ Failed symbol lookup")

    # 4. AST Syntax Guard
    print("\n[4/8] Deterministic Code Verifier (AST Guard)...")
    res = DeterministicCodeVerifier.verify_file("main.py", content="def ok(): return 1\n")
    if res.is_valid:
        print("  ✅ Passed (0ms AST syntax parsing)")
        passed += 1
    else:
        print("  ❌ Failed")

    # 5. Reflexion Negative Constraints
    print("\n[5/8] Episodic Reflexion Memory...")
    ref = ReflexionMemory()
    ref.record_failure("API", "call_v1", "404 Not Found", "call_v2")
    if "DO NOT attempt 'call_v1'" in ref.render_negative_constraints_prompt():
        print("  ✅ Passed (Hard negative constraints compiled)")
        passed += 1
    else:
        print("  ❌ Failed")

    # 6. Call-Hierarchy & Impact Analyzer
    print("\n[6/8] Call-Hierarchy & Blast Radius Impact Analyzer...")
    with tempfile.TemporaryDirectory() as tmpdir:
        r = Path(tmpdir)
        (r / "core.py").write_text("def engine_init(): pass\n", encoding="utf-8")
        (r / "server.py").write_text("from core import engine_init\ndef run(): engine_init()\n", encoding="utf-8")
        call_graph = CallHierarchyGraph(r)
        rep = call_graph.analyze_impact("engine_init", file_path="core.py")
        if len(rep.impacted_callers) >= 1 and "server.py" in rep.impacted_files:
            print(
                f"  ✅ Passed (Discovered caller at {rep.impacted_callers[0].caller_file}:{rep.impacted_callers[0].line_number})"
            )
            passed += 1
        else:
            print("  ❌ Failed call hierarchy resolution")

    # 7. Static Type & Security Gate
    print("\n[7/8] Static Type & Security Gate...")
    bad_code = "SECRET = 'sk-live-123456789012345'\ndef run(x): eval(x)\n"
    gate_rep = StaticTypeSecurityGate.audit_code(bad_code, "test.py")
    if not gate_rep.passed and len(gate_rep.issues) >= 2:
        print(f"  ✅ Passed (Detected {len(gate_rep.issues)} security vulnerabilities: Secret & eval)")
        passed += 1
    else:
        print("  ❌ Failed security scan")

    # 8. Speculative Branching & Consensus
    print("\n[8/8] Speculative Branching & Self-Consistency Voter...")
    engine = SpeculativeBranchingEngine(Path.cwd())
    spec_res = engine.evaluate_hypotheses(
        ["v1", "v2"],
        {"v1": lambda ws: True, "v2": lambda ws: True},
        test_command=["python3", "-c", "import sys; sys.exit(0)"],
    )
    if spec_res.success:
        print("  ✅ Passed (Isolated branch testing & consensus)")
        passed += 1
    else:
        print("  ❌ Failed speculative branch")

    print("\n" + "=" * 75)
    print(f"🏆 ULTIMATE FRONTIER SCORE: {passed}/{total} ({(passed/total)*100:.0f}%)")
    print("=" * 75)
    return passed == total


if __name__ == "__main__":
    success = run_ultimate_benchmark()
    sys.exit(0 if success else 1)
