import os
import subprocess
import logging
import shutil

logger = logging.getLogger(__name__)


class WorktreeManager:
    """
    Git Worktree 기반의 샌드박스 격리 매니저.
    Antigravity-K 에이전트가 본래의 디렉토리를 오염시키지 않고,
    격리된 환경(Worktree)에서 작업할 수 있도록 지원합니다.
    """

    def __init__(self, base_repo_path: str, worktrees_dir: str = ".ag_worktrees"):
        self.base_repo_path = base_repo_path
        self.worktrees_dir = os.path.join(base_repo_path, worktrees_dir)

        if not os.path.exists(self.worktrees_dir):
            os.makedirs(self.worktrees_dir)

    def create_worktree(self, branch_name: str, base_branch: str = "main") -> str:
        """
        주어진 branch_name으로 새로운 Git Worktree를 생성합니다.
        """
        worktree_path = os.path.join(self.worktrees_dir, branch_name)

        # Check if worktree already exists
        if os.path.exists(worktree_path):
            logger.info(f"Worktree for {branch_name} already exists at {worktree_path}")
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
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(
                f"[Worktree] Created isolated sandbox at {worktree_path} on branch {branch_name}"
            )
            return worktree_path
        except subprocess.CalledProcessError as e:
            # If branch already exists, we might need to just checkout
            logger.warning(
                f"[Worktree] Failed to create worktree via branch creation. Retrying with existing branch. Err: {e.stderr}"
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
                subprocess.run(cmd_fallback, check=True, capture_output=True, text=True)
                logger.info(
                    f"[Worktree] Created sandbox at {worktree_path} using existing branch {branch_name}"
                )
                return worktree_path
            except subprocess.CalledProcessError as e2:
                logger.error(
                    f"[Worktree] Completely failed to create worktree: {e2.stderr}"
                )
                raise RuntimeError(f"Worktree creation failed: {e2.stderr}")

    def remove_worktree(self, worktree_path: str, force: bool = False):
        """
        사용이 끝난 Git Worktree를 삭제합니다.
        """
        cmd = ["git", "-C", self.base_repo_path, "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(worktree_path)

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"[Worktree] Removed sandbox at {worktree_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"[Worktree] Failed to remove worktree: {e.stderr}")
            # Fallback: force remove dir if git command fails
            if force and os.path.exists(worktree_path):
                shutil.rmtree(worktree_path)
                logger.warning(
                    f"[Worktree] Force deleted directory {worktree_path} due to git failure."
                )
