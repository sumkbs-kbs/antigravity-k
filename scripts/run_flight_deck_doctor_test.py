#!/usr/bin/env python3
"""Run Flight Deck Telemetry & Self-Healing Doctor verification.

Validates:
1. Rich Flight Deck panel rendering
2. Self-Healing Doctor diagnosis and repair
"""

import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.flight_deck_renderer import FlightDeckRenderer, FlightTelemetryState
from antigravity_k.engine.self_healing_doctor import SelfHealingDoctor


def run_flight_doctor_tests():
    print("=" * 75)
    print("🛸 RUNNING FLIGHT DECK & SELF-HEALING DOCTOR BENCHMARK (Qwen3.8-27B)")
    print("=" * 75)

    passed = 0
    total = 2

    # 1. Flight Deck Renderer
    print("\n[1/2] Testing Flight Deck Telemetry Renderer...")
    state = FlightTelemetryState(
        mission_goal="Deploy Autonomous Cluster",
        active_step="Verify Node Consensus",
        completed_steps=4,
        total_steps=5,
        tdd_passed=12,
        tdd_failed=0,
        active_negative_constraints=["DO NOT use unpinned dependencies"],
        fast_path_latency_ms=1.8,
    )
    panel = FlightDeckRenderer.render_panel(state)
    if panel and "FLIGHT DECK" in panel.title:
        print("  ✅ Flight Deck panel rendered cleanly with real-time telemetry")
        passed += 1
    else:
        print("  ❌ Flight deck failed")

    # 2. Self-Healing Doctor
    print("\n[2/2] Testing Self-Healing Doctor Diagnosis & Auto-Repair...")
    with tempfile.TemporaryDirectory() as tmpdir:
        r = Path(tmpdir)
        doc = SelfHealingDoctor(r)
        rep = doc.run_health_check(auto_heal=True)
        if rep.healthy_count >= 2:
            print(
                f"  ✅ Self-Healing Doctor resolved {rep.healthy_count}/{rep.total_checks} checks (Repaired: {rep.repaired_count})"
            )
            passed += 1
        else:
            print("  ❌ Doctor check failed")

    print("\n" + "=" * 75)
    print(f"🏆 FLIGHT DECK & DOCTOR SCORE: {passed}/{total} ({(passed/total)*100:.0f}%)")
    print("=" * 75)
    return passed == total


if __name__ == "__main__":
    success = run_flight_doctor_tests()
    sys.exit(0 if success else 1)
