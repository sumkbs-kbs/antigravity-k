"""Unit tests for NextActionRecommender."""

import tempfile
from pathlib import Path

from antigravity_k.engine.next_action_recommender import NextActionRecommender


def test_test_gap_recommendation():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _ = (root / "src").mkdir()
        _ = (root / "src" / "payment.py").write_text("def charge_card(): pass\n", encoding="utf-8")

        recommender = NextActionRecommender(root)
        batch = recommender.synthesize_recommendations(
            completed_goal="Implement payment processing",
            touched_files=["src/payment.py"],
        )

        assert len(batch.actions) >= 1
        test_gap_actions = [a for a in batch.actions if a.category == "TEST_GAP"]
        assert len(test_gap_actions) == 1
        assert "tests/test_payment.py" in test_gap_actions[0].executable_prompt
        assert "agk autopilot" in batch.format_cli_panel()
