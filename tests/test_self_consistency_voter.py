"""Unit tests for SelfConsistencyVoter."""

from antigravity_k.engine.self_consistency_voter import CandidateHypothesis, SelfConsistencyVoter


def test_self_consistency_consensus():
    c1 = CandidateHypothesis(
        candidate_id="h1",
        rationale="Fix auth token expiration in auth.py",
        target_files=["auth.py"],
        proposed_actions=["modify verify_token"],
        confidence_score=0.9,
    )
    c2 = CandidateHypothesis(
        candidate_id="h2",
        rationale="Update token check in auth.py and add route test",
        target_files=["auth.py", "test_auth.py"],
        proposed_actions=["modify verify_token", "add test"],
        confidence_score=0.95,
    )
    c3 = CandidateHypothesis(
        candidate_id="h3",
        rationale="Re-write database layer in db.py",
        target_files=["db.py"],
        proposed_actions=["drop tables"],
        confidence_score=0.2,
    )

    decision = SelfConsistencyVoter.vote_on_hypotheses([c1, c2, c3])
    assert decision is not None
    assert decision.selected_hypothesis.candidate_id in ("h1", "h2")
    assert "auth.py" in decision.selected_hypothesis.target_files
    assert decision.agreement_ratio >= 0.66
