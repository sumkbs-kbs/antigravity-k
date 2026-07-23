"""Tests for the WorktreeManager module.

Covers:
- __init__: directory creation
- create_worktree: new branch, existing branch, fallback, failure
- remove_worktree: success, force, git failure + cleanup
- get_worktree_path: path exists, git worktree list, not found
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from antigravity_k.engine.worktree_manager import WorktreeManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo(tmp_path: Path) -> str:
    """Create a temporary directory to act as a mock repo root."""
    repo = tmp_path / "repo"
    repo.mkdir()
    return str(repo)


@pytest.fixture
def manager(tmp_repo: str) -> WorktreeManager:
    """Create a WorktreeManager pointing at the temp repo."""
    return WorktreeManager(base_repo_path=tmp_repo, worktrees_dir=".ag_worktrees")


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_worktrees_dir(self, tmp_repo: str):
        """The worktrees directory should be created if it doesn't exist."""
        wt_dir = os.path.join(tmp_repo, ".ag_worktrees")
        assert not os.path.exists(wt_dir)

        manager = WorktreeManager(base_repo_path=tmp_repo, worktrees_dir=".ag_worktrees")

        assert os.path.isdir(wt_dir)
        assert manager.base_repo_path == tmp_repo
        assert manager.worktrees_dir == wt_dir

    def test_uses_existing_worktrees_dir(self, tmp_repo: str):
        """If the worktrees directory already exists, it should not fail."""
        wt_dir = os.path.join(tmp_repo, ".ag_worktrees")
        os.makedirs(wt_dir)

        WorktreeManager(base_repo_path=tmp_repo, worktrees_dir=".ag_worktrees")

        assert os.path.isdir(wt_dir)

    def test_default_worktrees_dir(self, tmp_path: Path):
        """The default worktrees directory should be .ag_worktrees under base_repo_path."""
        repo = tmp_path / "default_repo"
        repo.mkdir()
        manager = WorktreeManager(base_repo_path=str(repo))
        assert manager.worktrees_dir == os.path.join(str(repo), ".ag_worktrees")


# ---------------------------------------------------------------------------
# create_worktree
# ---------------------------------------------------------------------------


class TestCreateWorktree:
    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_creates_new_branch(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """A successful 'git worktree add -b' should return the worktree path."""
        mock_run.return_value = mock.MagicMock(returncode=0)

        path = manager.create_worktree(branch_name="feature/test", base_branch="main")

        expected_path = os.path.join(manager.worktrees_dir, "feature/test")
        assert path == expected_path
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:4] == ["git", "-C", manager.base_repo_path, "worktree"]
        assert "add" in args
        assert "-b" in args
        assert "feature/test" in args

    def test_worktree_already_exists(self, manager: WorktreeManager):
        """If the worktree directory already exists, it should return the path without running git."""
        os.makedirs(os.path.join(manager.worktrees_dir, "existing_branch"))

        with mock.patch("antigravity_k.engine.worktree_manager.subprocess.run") as mock_run:
            path = manager.create_worktree(branch_name="existing_branch", base_branch="main")

        expected_path = os.path.join(manager.worktrees_dir, "existing_branch")
        assert path == expected_path
        mock_run.assert_not_called()

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_fallback_to_existing_branch(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """If -b branch creation fails (branch exists), it should retry without -b."""
        # First call fails (CalledProcessError), second call succeeds
        failing_resp = mock.MagicMock()
        failing_resp.returncode = 128
        failing_resp.stderr = "fatal: A branch named 'existing' already exists."

        mock_run.side_effect = [
            subprocess.CalledProcessError(128, ["git"], stderr="branch already exists"),
            mock.MagicMock(returncode=0),
        ]

        path = manager.create_worktree(branch_name="existing", base_branch="main")

        expected_path = os.path.join(manager.worktrees_dir, "existing")
        assert path == expected_path
        assert mock_run.call_count == 2

        # Second call should be without -b
        second_args = mock_run.call_args_list[1].args[0]
        assert "-b" not in second_args

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_complete_failure_raises(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """If both attempts fail, RuntimeError should be raised."""
        mock_run.side_effect = subprocess.CalledProcessError(128, ["git"], stderr="some git error")

        with pytest.raises(RuntimeError, match="Worktree creation failed"):
            manager.create_worktree(branch_name="fail_branch", base_branch="main")

        assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# remove_worktree
# ---------------------------------------------------------------------------


class TestRemoveWorktree:
    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_remove_success(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """A successful 'git worktree remove' should not raise."""
        mock_run.return_value = mock.MagicMock(returncode=0)

        manager.remove_worktree("/some/worktree/path")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:4] == ["git", "-C", manager.base_repo_path, "worktree"]
        assert "remove" in args
        assert "/some/worktree/path" in args

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_force_remove_with_git_flag(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """When force=True, --force should be passed to git worktree remove."""
        mock_run.return_value = mock.MagicMock(returncode=0)

        manager.remove_worktree("/some/worktree/path", force=True)

        args = mock_run.call_args[0][0]
        assert "--force" in args

    @mock.patch("antigravity_k.engine.worktree_manager.os.path.exists", return_value=True)
    @mock.patch("antigravity_k.engine.worktree_manager.shutil.rmtree")
    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_force_remove_fallback_rmtree(
        self,
        mock_run: mock.MagicMock,
        mock_rmtree: mock.MagicMock,
        mock_exists: mock.MagicMock,
        manager: WorktreeManager,  # noqa: ARG002
    ):
        """When force=True and git remove fails, it should fall back to shutil.rmtree."""
        mock_run.side_effect = subprocess.CalledProcessError(128, ["git"], stderr="git error")

        manager.remove_worktree("/some/worktree/path", force=True)

        # Git command should be called first
        assert mock_run.call_count == 1
        # Fallback cleanup via rmtree should be called
        mock_rmtree.assert_called_once_with("/some/worktree/path")

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_remove_failure_without_force_no_cleanup(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """When force=False and git remove fails, no rmtree cleanup happens."""
        mock_run.side_effect = subprocess.CalledProcessError(128, ["git"], stderr="git error")

        with mock.patch("antigravity_k.engine.worktree_manager.shutil.rmtree") as mock_rmtree:
            manager.remove_worktree("/some/worktree/path", force=False)

        assert mock_run.call_count == 1
        mock_rmtree.assert_not_called()


# ---------------------------------------------------------------------------
# get_worktree_path
# ---------------------------------------------------------------------------


class TestGetWorktreePath:
    def test_path_exists(self, manager: WorktreeManager):
        """When the worktree directory exists, the path should be returned directly."""
        os.makedirs(os.path.join(manager.worktrees_dir, "my_branch"))

        path = manager.get_worktree_path("my_branch")

        expected = os.path.join(manager.worktrees_dir, "my_branch")
        assert path == expected

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_path_from_git_list(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """When the directory doesn't exist, it should fall back to git worktree list."""
        # Simulate git worktree list --porcelain output
        porcelain_output = (
            "worktree /path/to/main\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /path/to/feature/x\n"
            "HEAD def456\n"
            "branch refs/heads/feature/x\n"
        )
        mock_run.return_value = mock.MagicMock(stdout=porcelain_output, returncode=0)

        path = manager.get_worktree_path("feature/x")

        assert path == "/path/to/feature/x"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:4] == ["git", "-C", manager.base_repo_path, "worktree"]
        assert "list" in args
        assert "--porcelain" in args

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_path_not_found(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """When the worktree is not found, None should be returned."""
        mock_run.return_value = mock.MagicMock(
            stdout="worktree /some/other/path\nHEAD abc123\nbranch refs/heads/other\n",
            returncode=0,
        )

        path = manager.get_worktree_path("nonexistent_branch")

        assert path is None

    @mock.patch("antigravity_k.engine.worktree_manager.subprocess.run")
    def test_git_command_failure(self, mock_run: mock.MagicMock, manager: WorktreeManager):
        """If the git worktree list command fails, None should be returned."""
        mock_run.side_effect = RuntimeError("git command not found")

        path = manager.get_worktree_path("any_branch")

        assert path is None

    def test_path_exists_takes_precedence(self, manager: WorktreeManager):
        """If the directory exists, it should return it without calling git."""
        os.makedirs(os.path.join(manager.worktrees_dir, "cached_branch"))

        with mock.patch("antigravity_k.engine.worktree_manager.subprocess.run") as mock_run:
            path = manager.get_worktree_path("cached_branch")

        expected = os.path.join(manager.worktrees_dir, "cached_branch")
        assert path == expected
        mock_run.assert_not_called()
