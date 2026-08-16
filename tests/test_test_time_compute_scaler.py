"""Unit tests for TestTimeComputeScaler."""

from antigravity_k.engine.test_time_compute_scaler import TestTimeComputeScaler


def test_scaler_simple_task():
    budget = TestTimeComputeScaler.evaluate_budget("view readme", impacted_files_count=1)
    assert budget.complexity_tier == "SIMPLE"
    assert budget.branching_factor == 1
    assert budget.requires_speculative_worktree is False


def test_scaler_complex_refactor_task():
    budget = TestTimeComputeScaler.evaluate_budget(
        "refactor concurrency architecture in auth and database layers",
        impacted_files_count=5,
        cyclomatic_hint=8,
    )
    assert budget.complexity_tier in ("COMPLEX", "EXTREME")
    assert budget.branching_factor >= 3
    assert budget.mcts_depth >= 6
    assert budget.requires_speculative_worktree is True
