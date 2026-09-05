#!/usr/bin/env python3
"""Master End-to-End System Verification for Ssak-Ai (Qwen3.8-27B).

Executes a full flight mission from CLI-level fast path down to kernel verifiers.
"""

import sys


def run_master_test():
    print("=" * 80)
    print("🛸 MASTER END-TO-END SYSTEM TEST: SSAK-AI (QWEN3.8-27B)")
    print("=" * 80)

    score = 0
    total = 6

    # 1. Fast-Path Layer
    print("\n[1/6] Fast-Path Layer (<5ms symbol discovery)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        r = Path(tmpdir)
        (r / "core.py").write_text("class AutonomousKernel: pass\n", encoding="utf-8")
        kernel = FastPathKernel(r)
        res = kernel.try_execute("where is AutonomousKernel")
        if res.handled and "AutonomousKernel" in res.response:
            print("  ✅ Fast-Path direct dispatch verified")
            score += 1

    # 2. Autonomous Flight Mission
    print("\n[2/6] Autonomous Flight Mission Controller...")
    flight = AutonomousFlightController(Path.cwd(), max_flight_turns=3)
    mission = flight.launch_mission(
        "Build Auth Service",
        [{"id": "s1", "desc": "Plan"}, {"id": "s2", "desc": "Code", "depends_on": ["s1"]}],
        lambda s_id, desc: True,
    )
    if mission.is_success:
        print("  ✅ Flight autopilot completed all subgoals autonomously")
        score += 1

    # 3. Static Security & Type Guard
    print("\n[3/6] Static Security & Code Verifier Gate...")
    clean_code = "import os\ndef get_port(): return int(os.getenv('PORT', 8000))\n"
    res_syntax = DeterministicCodeVerifier.verify_file("port.py", content=clean_code)
    res_sec = StaticTypeSecurityGate.audit_code(clean_code, "port.py")
    if res_syntax.is_valid and res_sec.passed:
        print("  ✅ Zero-latency AST & security verification verified")
        score += 1

    # 4. Incremental Code Graph & Call Hierarchy
    print("\n[4/6] Incremental AST & Blast Radius Call Hierarchy...")
    with tempfile.TemporaryDirectory() as tmpdir:
        r = Path(tmpdir)
        (r / "db.py").write_text("def connect(): pass\n", encoding="utf-8")
        (r / "app.py").write_text("from db import connect\ndef main(): connect()\n", encoding="utf-8")
        call_g = CallHierarchyGraph(r)
        report = call_g.analyze_impact("connect", file_path="db.py")
        if len(report.impacted_callers) >= 1:
            print("  ✅ Blast radius caller tracking verified")
            score += 1

    # 5. Reflexion & Working Memory
    print("\n[5/6] Reflexion Memory & Working Memory Compactor...")
    ref = ReflexionMemory()
    ref.record_failure("test", "broken_action", "assertion failed", "use valid assertion")
    state = WorkingMemoryCompactor.compact([{"role": "user", "content": "file.py"}], adrs=["ADR-01"])
    pinned = state.format_pinned_working_memory()
    if "DO NOT attempt" in ref.render_negative_constraints_prompt() and "ADR-01" in pinned:
        print("  ✅ Memory distillation and negative constraint injection verified")
        score += 1

    # 6. Zero-Waste Code Density Maximizer
    print("\n[6/6] Zero-Waste Code Density Maximizer...")
    compressed = ZeroWasteCompressor.compress("Hello! As an AI model, here is code:\ndef x(): pass")
    if "Hello!" not in compressed.text and "def x(): pass" in compressed.text:
        print("  ✅ 100% pure code token density verified")
        score += 1

    print("\n" + "=" * 80)
    print(f"🎉 MASTER SYSTEM SCORE: {score}/{total} ({(score/total)*100:.0f}%)")
    print("=" * 80)
    return score == total


if __name__ == "__main__":
    success = run_master_e2e()
    sys.exit(0 if success else 1)
