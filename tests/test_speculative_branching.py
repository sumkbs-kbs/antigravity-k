"""Unit tests for SpeculativeBranchingEngine (parallel + worktree isolation)."""

import subprocess
from pathlib import Path

import pytest

from antigravity_k.engine.speculative_branching import SpeculativeBranchingEngine

EXIT_OK = ["python3", "-c", "import sys; sys.exit(0)"]
EXIT_FAIL = ["python3", "-c", "import sys; sys.exit(1)"]


def _always_true(_ws: Path) -> bool:
    return True


def _always_false(_ws: Path) -> bool:
    return False


class TestSequentialMode:
    def test_first_pass_wins_and_stops_early(self):
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())
        res = engine.evaluate_hypotheses(
            hypothesis_names=["a", "b"],
            patch_generators={"a": _always_true, "b": _always_true},
            test_command=EXIT_OK,
            parallel=False,
            use_worktrees=False,
        )
        assert res.success is True
        assert res.winner_branch == "a"
        assert res.evaluated == 2

    def test_failure_lessons_collected(self):
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())
        res = engine.evaluate_hypotheses(
            hypothesis_names=["bad"],
            patch_generators={"bad": _always_false},
            test_command=EXIT_OK,
            parallel=False,
            use_worktrees=False,
        )
        assert res.success is False
        assert res.winner_branch is None
        assert len(res.failure_lessons) == 1
        assert "patch generation" in res.failure_lessons[0]

    def test_test_failure_produces_lesson(self):
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())
        res = engine.evaluate_hypotheses(
            hypothesis_names=["failing"],
            patch_generators={"failing": _always_true},
            test_command=EXIT_FAIL,
            parallel=False,
            use_worktrees=False,
        )
        assert res.success is False
        assert "failed test with" in res.failure_lessons[0]


class TestParallelMode:
    def test_parallel_deterministic_winner_prefers_original_order(self):
        """두 가설 모두 통과 시 원본 순서의 첫 번째가 승자다 (결정론 계약)."""
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())
        res = engine.evaluate_hypotheses(
            hypothesis_names=["zeta", "alpha"],
            patch_generators={"zeta": _always_true, "alpha": _always_true},
            test_command=EXIT_OK,
            parallel=True,
            max_workers=2,
            use_worktrees=False,
        )
        assert res.success is True
        assert res.winner_branch == "zeta"

    def test_parallel_mixed_outcomes(self):
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())

        def slow_pass(_ws: Path) -> bool:
            return True

        res = engine.evaluate_hypotheses(
            hypothesis_names=["fail1", "win", "fail2"],
            patch_generators={
                "fail1": _always_false,
                "win": slow_pass,
                "fail2": _always_true,
            },
            test_command=EXIT_FAIL,
            parallel=True,
            max_workers=3,
            use_worktrees=False,
        )
        # fail2는 테스트가 실패하므로 통과 없음
        assert res.success is False
        assert set(res.discarded_branches) >= {"fail2"}
        assert res.evaluated == 3

    def test_missing_generator_skipped(self):
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())
        res = engine.evaluate_hypotheses(
            hypothesis_names=["ghost"],
            patch_generators={},
            test_command=EXIT_OK,
        )
        assert res.success is False
        assert res.evaluated == 0
        assert res.failure_lessons


class TestWorktreeIsolation:
    @pytest.fixture()
    def tiny_git_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> None:
            _ = subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
            )

        git("init", "-q")
        git("config", "user.email", "t@t.local")
        git("config", "user.name", "t")
        _ = (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "init")
        return repo

    def test_worktree_used_in_git_repo(self, tiny_git_repo: Path):
        engine = SpeculativeBranchingEngine(project_root=tiny_git_repo)

        def patch(ws_dir: Path) -> bool:
            assert (ws_dir / "app.py").exists(), "worktree must contain committed files"
            return True

        res = engine.evaluate_hypotheses(
            hypothesis_names=["wt"],
            patch_generators={"wt": patch},
            test_command=EXIT_OK,
            parallel=False,
            use_worktrees=True,
        )
        assert res.success is True
        assert res.workspace_kinds["wt"] == "worktree"
        wt_lists = subprocess.run(
            ["git", "-C", str(tiny_git_repo), "worktree", "list"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "agk_spec_" not in wt_lists, "worktrees must be cleaned up"

    def test_tempdir_fallback_without_git(self, tmp_path: Path):
        plain = tmp_path / "plain"
        plain.mkdir()
        engine = SpeculativeBranchingEngine(project_root=plain)
        res = engine.evaluate_hypotheses(
            hypothesis_names=["fb"],
            patch_generators={"fb": _always_true},
            test_command=EXIT_OK,
            parallel=False,
            use_worktrees=True,
        )
        assert res.success is True
        assert res.workspace_kinds["fb"] == "tempdir"


class TestTimeoutHandling:
    def test_timeout_becomes_lesson(self):
        engine = SpeculativeBranchingEngine(project_root=Path.cwd())
        res = engine.evaluate_hypotheses(
            hypothesis_names=["hangs"],
            patch_generators={"hangs": _always_true},
            test_command=["python3", "-c", "import time; time.sleep(10)"],
            parallel=False,
            use_worktrees=False,
            timeout_sec=0.5,
        )
        assert res.success is False
        assert "timed out" in res.failure_lessons[0]
