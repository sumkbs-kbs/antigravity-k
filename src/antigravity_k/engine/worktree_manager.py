"""Worktree Manager module."""

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)


def _stderr_text(error: subprocess.CalledProcessError) -> str:
    raw_stderr: object = error.__dict__.get("stderr")
    if isinstance(raw_stderr, str):
        return raw_stderr
    if isinstance(raw_stderr, bytes):
        return raw_stderr.decode(errors="replace")
    return str(error)


class WorktreeManager:
    """Git Worktree 기반의 샌드박스 격리 매니저.

    Ssak-Ai 에이전트가 본래의 디렉토리를 오염시키지 않고,
    격리된 환경(Worktree)에서 작업할 수 있도록 지원합니다.
    """

    def __init__(self, base_repo_path: str = ".", worktrees_dir: str = ".ag_worktrees") -> None:
        """Initialize the WorktreeManager.

        Args:
            base_repo_path (str): str base repo path.
            worktrees_dir (str): str worktrees dir.

        """
        self.base_repo_path: str = base_repo_path
        self.worktrees_dir: str = os.path.join(base_repo_path, worktrees_dir)

        if not os.path.exists(self.worktrees_dir):
            os.makedirs(self.worktrees_dir)

    def create_worktree(self, branch_name: str, base_branch: str = "main") -> str:
        """주어진 branch_name으로 새로운 Git Worktree를 생성합니다."""
        worktree_path = os.path.join(self.worktrees_dir, branch_name)

        # Check if worktree already exists
        if os.path.exists(worktree_path):
            logger.info("Worktree for %s already exists at %s", branch_name, worktree_path)
            return worktree_path

        # git worktree add -b <new_branch> <path> <base_branch>
        cmd = [
            "git",
            "-C",
            self.base_repo_path,
            "worktree",
            "add",
            "-b",
            branch_name,
            worktree_path,
            base_branch,
        ]

        try:
            _ = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(
                "[Worktree] Created isolated sandbox at %s on branch %s",
                worktree_path,
                branch_name,
            )
            return worktree_path
        except subprocess.CalledProcessError as e:
            # If branch already exists, we might need to just checkout
            logger.warning(
                "[Worktree] Failed to create worktree via branch creation. Retrying with existing branch. Err: %s",
                _stderr_text(e),
            )
            cmd_fallback = [
                "git",
                "-C",
                self.base_repo_path,
                "worktree",
                "add",
                worktree_path,
                branch_name,
            ]
            try:
                _ = subprocess.run(cmd_fallback, check=True, capture_output=True, text=True)
                logger.info(
                    "[Worktree] Created sandbox at %s using existing branch %s",
                    worktree_path,
                    branch_name,
                )
                return worktree_path
            except subprocess.CalledProcessError as e2:
                logger.error("[Worktree] Completely failed to create worktree: %s", _stderr_text(e2))
                raise RuntimeError(f"Worktree creation failed: {_stderr_text(e2)}") from e2

    def remove_worktree(self, worktree_path: str, force: bool = False) -> None:
        """사용이 끝난 Git Worktree를 삭제합니다."""
        cmd = ["git", "-C", self.base_repo_path, "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(worktree_path)

        try:
            _ = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("[Worktree] Removed sandbox at %s", worktree_path)
        except subprocess.CalledProcessError as e:
            logger.error("[Worktree] Failed to remove worktree: %s", _stderr_text(e))
            # Fallback: force remove dir if git command fails
            if force and os.path.exists(worktree_path):
                shutil.rmtree(worktree_path)
                logger.warning(
                    "[Worktree] Force deleted directory %s due to git failure.",
                    worktree_path,
                )

    def get_worktree_path(self, branch_name: str) -> str | None:
        """주어진 branch_name에 해당하는 worktree 경로를 반환합니다.

        worktree가 존재하면 경로를, 없으면 None을 반환합니다.
        task API 등에서 task_id로 worktree를 조회할 때 사용됩니다.

        Args:
            branch_name: 브랜치명 (또는 task_id)

        Returns:
            worktree 경로 (존재 시), None (미존재 시)
        """
        worktree_path = os.path.join(self.worktrees_dir, branch_name)
        if os.path.exists(worktree_path):
            return worktree_path

        # git worktree list로 실제 등록된 worktree 확인 (브랜치명이 경로와 다를 수 있음)
        try:
            result = subprocess.run(
                ["git", "-C", self.base_repo_path, "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    path = line[len("worktree ") :]
                    if branch_name in path:
                        return path
        except (OSError, RuntimeError, subprocess.SubprocessError):
            logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)

        return None
