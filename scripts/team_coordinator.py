import json
import logging
import time
import uuid
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("team_coordinator")


class AgentRole:
    CEO = "CEO"
    DESIGNER = "Designer"
    DEVELOPER = "Developer"
    QA = "QA"


class TaskStatus:
    BACKLOG = "BACKLOG"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"


class AgentTask:
    def __init__(self, title: str, description: str, assigned_to: str):
        self.id = str(uuid.uuid4())[:8]
        self.title = title
        self.description = description
        self.assigned_to = assigned_to
        self.status = TaskStatus.BACKLOG
        self.history = []
        self.created_at = time.time()
        self.tokens_used = 0

    def update_status(self, new_status: str, message: str = ""):
        self.status = new_status
        self.history.append({"status": new_status, "message": message, "time": time.time()})
        logger.info(f"Task {self.id} status updated to {new_status} - {message}")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "history": self.history,
            "created_at": self.created_at,
            "tokens_used": self.tokens_used,
        }


class TeamCoordinator:
    """gstack 및 claude_agent_teams_ui에서 영감을 받은 멀티 에이전트 코디네이터."""

    def __init__(self):
        self.tasks: Dict[str, AgentTask] = {}
        self.agents = [AgentRole.CEO, AgentRole.DESIGNER, AgentRole.DEVELOPER, AgentRole.QA]

    def create_task(self, title: str, description: str, role: str) -> str:
        if role not in self.agents:
            role = AgentRole.DEVELOPER

        task = AgentTask(title, description, role)
        self.tasks[task.id] = task
        logger.info(f"New task created: {title} assigned to {role}")
        return task.id

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tasks.values()]

    def execute_task_step(self, task_id: str, tokens: int = 150):
        """에이전트가 작업을 수행하는 시뮬레이션 (상태 전이)"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.tokens_used += tokens

        if task.status == TaskStatus.BACKLOG:
            task.update_status(TaskStatus.IN_PROGRESS, f"{task.assigned_to} started working on the task.")
        elif task.status == TaskStatus.IN_PROGRESS:
            task.update_status(
                TaskStatus.REVIEW,
                f"{task.assigned_to} finished the implementation. Pending Peer Review.",
            )
        elif task.status == TaskStatus.REVIEW:
            task.update_status(TaskStatus.DONE, "Review approved. Changes merged.")

        return task.to_dict()


# 싱글톤 인스턴스
coordinator = TeamCoordinator()

if __name__ == "__main__":
    t_id = coordinator.create_task("Implement Authentication", "Add JWT auth using FastAPI", AgentRole.DEVELOPER)
    coordinator.execute_task_step(t_id, 230)
    coordinator.execute_task_step(t_id, 410)
    coordinator.execute_task_step(t_id, 120)
    print(json.dumps(coordinator.get_all_tasks(), indent=2))
