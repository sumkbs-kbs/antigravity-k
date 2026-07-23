"""Token-stream multiplexer for merging parallel model outputs."""

import asyncio
import logging
from typing import Any

from antigravity_k.engine.goal_runner import GoalRunner
from antigravity_k.engine.worktree_manager import WorktreeManager

logger = logging.getLogger(__name__)


class Multiplexer:
    """다중 에이전트를 병렬로 스폰(Spawn)하고 관리하는 오케스트레이터입니다.

    각 에이전트는 자신만의 격리된 Git Worktree 샌드박스에서 실행됩니다.
    """

    def __init__(self, project_root: str):
        """Initialize the Multiplexer.

        Args:
            project_root (str): str project root.

        """
        self.project_root = project_root
        self.worktree_manager = WorktreeManager(base_repo_path=project_root)
        self.active_runners: list[GoalRunner] = []

    async def run_parallel_goals(self, goals: list[dict[str, Any]], base_branch: str = "main"):
        """주어진 여러 목표(Goal)들을 각각 독립된 에이전트(GoalRunner)에게 할당하여.

        비동기적으로 동시에 실행합니다.

        goals 예시:
        [
            {"task_id": "feature-ui", "instruction": "Make login page"},
            {"task_id": "feature-api", "instruction": "Write backend logic"}
        ]
        """
        logger.info("[Multiplexer] Spawning %s parallel agents...", len(goals))

        tasks = []
        for goal in goals:
            task_id = goal.get("task_id", f"task-{id(goal)}")
            instruction = goal.get("instruction", "")

            # 1. 샌드박스(Worktree) 생성
            worktree_path = self.worktree_manager.create_worktree(
                branch_name=task_id,
                base_branch=base_branch,
            )

            # 2. 독립된 런너 초기화 (Worktree 경로 주입)
            runner = GoalRunner(instruction=instruction)
            runner.workspace_dir = worktree_path
            self.active_runners.append(runner)

            # 3. 비동기 실행 태스크 추가
            tasks.append(self._run_single_agent(runner, worktree_path))

        # 모든 에이전트 동시 실행 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("[Multiplexer] All parallel agents have completed their tasks.")
        return results

    async def _run_single_agent(self, runner: GoalRunner, worktree_path: str):
        """개별 에이전트 실행 래퍼 로직."""
        try:
            logger.info("[%s] Agent started in %s", runner.task_id, worktree_path)
            # 기존 GoalRunner의 비동기 실행 훅 (예: execute_plan)
            # 현재 GoalRunner 구현체에 맞춰 run() 혹은 execute()를 호출
            await asyncio.to_thread(runner.run, runner.instruction)
            logger.info("[%s] Agent successfully finished.", runner.task_id)
            return {"task_id": runner.task_id, "status": "success"}
        except Exception as e:
            logger.exception("[%s] Agent failed", runner.task_id)
            return {"task_id": runner.task_id, "status": "failed", "error": str(e)}
        finally:
            # 작업이 끝났으므로 해당 워크트리 정리 가능 (옵션에 따라 유지)
            # 여기서는 히스토리 보존을 위해 삭제하지 않거나 옵셔널로 남겨둠
            pass
