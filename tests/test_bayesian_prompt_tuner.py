"""Unit tests for BayesianPromptTuner."""

import pytest

from antigravity_k.engine.bayesian_prompt_tuner import (
    BayesianPromptTuner,
    NoPromptCandidatesError,
    PromptCandidate,
)


def test_bayesian_prompt_tuner_optimization():
    c1 = PromptCandidate(candidate_id="p1", directive_text="Concise engineer")
    c2 = PromptCandidate(candidate_id="p2", directive_text="Verbose engineer")

    tuner = BayesianPromptTuner([c1, c2])

    # Record evaluations
    tuner.record_evaluation_score("p1", 0.95)
    tuner.record_evaluation_score("p1", 0.98)
    tuner.record_evaluation_score("p2", 0.40)

    best = tuner.get_best_prompt()
    assert best.candidate_id == "p1"
    assert best.mean_score > 0.9


def test_select_next_candidate_reports_empty_configuration() -> None:
    # Given: a tuner with no candidate prompt.
    tuner = BayesianPromptTuner([])

    # When/Then: callers receive the domain-specific configuration error.
    with pytest.raises(NoPromptCandidatesError):
        tuner.select_next_candidate()
