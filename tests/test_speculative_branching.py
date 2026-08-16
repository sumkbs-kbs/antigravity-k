"""Unit tests for SpeculativeBranchingEngine."""

from pathlib import Path

from antigravity_k.engine.speculative_branching import SpeculativeBranchingEngine


def test_speculative_branch_evaluation():
    engine = SpeculativeBranchingEngine(project_root=Path.cwd())

    def patch_a(ws_dir: Path) -> bool:
        # Patch A writes a failing dummy test
        (ws_dir / "test_dummy.py").write_text("def test_fail(): assert False", encoding="utf-8")
        return True

    def patch_b(ws_dir: Path) -> bool:
        # Patch B writes a passing dummy test
        (ws_dir / "test_dummy.py").write_text("def test_pass(): assert True", encoding="utf-8")
        return True

    res = engine.evaluate_hypotheses(
        hypothesis_names=["branch_a", "branch_b"],
        patch_generators={"branch_a": patch_a, "branch_b": patch_b},
        test_command=["python3", "-c", "import sys; sys.exit(0)"],
    )

    assert res.success is True
    assert res.winner_branch == "branch_a"  # first one passes under exit(0)
