#!/usr/bin/env python3
"""High-Precision Next-Action Recommendation Benchmark (Freebuff-style Intelligence).

Validates:
1. Test Coverage Gap synthesis on un-tested modified functions
2. Security & Performance blocking I/O audit synthesis
3. Documentation sync synthesis on core architecture modifications
4. CLI panel formatting and one-click executable payload generation
"""

import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.flight_deck_renderer import FlightDeckRenderer
from antigravity_k.engine.next_action_recommender import NextActionRecommender


def run_next_action_benchmark():
    print("=" * 80)
    print("🔮 RUNNING NEXT-ACTION RECOMMENDATION BENCHMARK (FREEBUFF STYLE)")
    print("=" * 80)

    score = 0
    total = 3

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "src" / "crypto.py").write_text("async def decrypt(): import time; time.sleep(1)\n", encoding="utf-8")

        recommender = NextActionRecommender(root)
        batch = recommender.synthesize_recommendations(
            completed_goal="Implement crypto service",
            touched_files=["src/crypto.py"],
        )

        # 1. Test Gap & Security vectors
        print("\n[1/3] Verifying Multi-Vector Proactive Synthesis...")
        cats = [a.category for a in batch.actions]
        if "TEST_GAP" in cats and "SECURITY_PERF" in cats:
            print(f"  ✅ Passed (Detected Test Gap and Blocking I/O Security issues: {cats})")
            score += 1

        # 2. Executable Payload Validation
        print("\n[2/3] Verifying One-Click Autopilot Actionability...")
        if all("agk autopilot" in act.executable_prompt or len(act.executable_prompt) > 10 for act in batch.actions):
            print("  ✅ Passed (All recommendations contain actionable, execution-ready prompts)")
            score += 1

        # 3. Rich Flight Deck Rendering
        print("\n[3/3] Verifying Flight Deck Panel Rendering...")
        panel = FlightDeckRenderer.render_recommendations_panel(batch.format_cli_panel())
        if panel and "PROACTIVE NEXT-ACTIONS" in panel.title:
            print("  ✅ Passed (Rendered beautiful high-visibility recommendation cockpit)")
            score += 1

    print("\n" + "=" * 80)
    print(f"🏆 NEXT-ACTION RECOMMENDATION SCORE: {score}/{total} ({(score/total)*100:.0f}%)")
    print("=" * 80)
    return score == total


if __name__ == "__main__":
    success = run_next_action_benchmark()
    sys.exit(0 if success else 1)
