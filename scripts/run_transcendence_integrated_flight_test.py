#!/usr/bin/env python3
"""Comprehensive Flight Integration Verification for Transcendence Suite (Qwen3.8-27B).

Validates that AutonomousFlightController successfully allocates dynamic compute budgets,
leverages DeepCodeIndexer, and wraps steps safely in AtomicTransactionEngine.
"""

import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.flight_controller import AutonomousFlightController


def run_transcendence_integrated_flight():
    print("=" * 80)
    print("🛸 TRANSCENDENCE INTEGRATED FLIGHT TEST (Qwen3.8-27B vs GPT-5 Tier)")
    print("=" * 80)

    score = 0
    total = 3

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "kernel.py").write_text(
            "def ignite_thruster(psi: float) -> bool:\n    '''Ignite engine.'''\n    return True\n", encoding="utf-8"
        )

        controller = AutonomousFlightController(project_root=root, max_flight_turns=5)

        # 1. Test Deep Signature Indexing inside Flight Controller
        print("\n[1/3] Verifying Deep Signature Grounding in Flight Controller...")
        sig = controller.indexer.get_signature_summary("ignite_thruster")
        if "ignite_thruster(psi: float) -> bool" in sig:
            print("  ✅ Passed (Deep code signatures available to flight engine)")
            score += 1

        # 2. Test Atomic Transaction Staging inside Flight Controller
        print("\n[2/3] Verifying Atomic Transaction Engine inside Flight Controller...")
        controller.transaction_engine.stage_file_patch("stage2.py", "def stage_sep(): return True\n")
        tx_res = controller.transaction_engine.commit_transaction()
        if tx_res.committed and (root / "stage2.py").exists():
            print("  ✅ Passed (Multi-file ACID transaction successfully committed)")
            score += 1

        # 3. Test High-Complexity Flight Mission with Dynamic Budget Scaling
        print("\n[3/3] Launching Autonomous Mission with Dynamic o-series Compute Scaling...")
        mission = controller.launch_mission(
            goal="Refactor concurrency and telemetry architecture across all engine stages",
            initial_subgoals=[
                {"id": "s1", "desc": "Audit AST callers"},
                {"id": "s2", "desc": "Apply ACID patches", "depends_on": ["s1"]},
                {"id": "s3", "desc": "Run TDD assertions", "depends_on": ["s2"]},
            ],
            step_executor=lambda s_id, desc: True,
        )

        if (
            mission.is_success
            and mission.compute_budget
            and mission.compute_budget.complexity_tier in ("COMPLEX", "EXTREME")
        ):
            print(f"  ✅ Passed (Mission completed with scaled budget: {mission.compute_budget.complexity_tier})")
            score += 1

    print("\n" + "=" * 80)
    print(f"🏆 TRANSCENDENCE INTEGRATION SCORE: {score}/{total} ({(score/total)*100:.0f}%)")
    print("=" * 80)
    return score == total


if __name__ == "__main__":
    success = run_transcendence_integrated_flight()
    sys.exit(0 if success else 1)
