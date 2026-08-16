"""Subgoal & Dependency Graph Engine — Deterministic Task DAG for 27B planning.

27B-class models struggle with planning horizons beyond 3-4 steps when managed via
loose text. This module introduces a deterministic Directed Acyclic Graph (DAG)
that enforces dependency checking, topological execution ordering, and step validation.
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class SubgoalNode:
    """A discrete, verifiable unit of work."""

    task_id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    result: Any = None
    verification_rule: str = ""  # e.g., "pytest", "file_exists", "ast_check"


class SubgoalGraph:
    """Manages a DAG of subgoals to keep the 27B model on a strict, structured trajectory."""

    def __init__(self, goal: str):
        self.goal = goal
        self.nodes: dict[str, SubgoalNode] = {}

    def add_subgoal(
        self,
        task_id: str,
        description: str,
        depends_on: list[str] | None = None,
        verification_rule: str = "",
    ) -> SubgoalNode:
        """Add a new task node to the graph."""
        node = SubgoalNode(
            task_id=task_id,
            description=description,
            depends_on=depends_on or [],
            verification_rule=verification_rule,
        )
        self.nodes[task_id] = node
        self._update_readiness()
        return node

    def complete_subgoal(self, task_id: str, result: Any = None) -> bool:
        """Mark a task as completed and propagate readiness to dependents."""
        if task_id not in self.nodes:
            return False
        self.nodes[task_id].state = TaskState.COMPLETED
        self.nodes[task_id].result = result
        self._update_readiness()
        return True

    def fail_subgoal(self, task_id: str, error: str) -> None:
        """Mark a task as failed and block dependent tasks."""
        if task_id in self.nodes:
            self.nodes[task_id].state = TaskState.FAILED
            self.nodes[task_id].result = error
            self._propagate_blocked(task_id)

    def get_ready_subgoals(self) -> list[SubgoalNode]:
        """Return all tasks whose prerequisites are completely satisfied."""
        return [n for n in self.nodes.values() if n.state == TaskState.READY]

    def is_all_completed(self) -> bool:
        """Check if all nodes in the DAG have successfully completed."""
        return bool(self.nodes) and all(n.state == TaskState.COMPLETED for n in self.nodes.values())

    def format_plan_prompt(self) -> str:
        """Format current DAG status into a compact directive block for the LLM."""
        lines = [
            f"📋 **Task DAG Execution Plan for Goal:** {self.goal}",
            "--------------------------------------------------",
        ]
        for node in self.nodes.values():
            icon = {
                TaskState.COMPLETED: "✅",
                TaskState.IN_PROGRESS: "🔄",
                TaskState.READY: "⭐ [NEXT TO EXECUTE]",
                TaskState.PENDING: "⏳",
                TaskState.FAILED: "❌",
                TaskState.BLOCKED: "🚫",
            }.get(node.state, "•")
            deps = f" (Depends on: {', '.join(node.depends_on)})" if node.depends_on else ""
            lines.append(f"{icon} [{node.task_id}] {node.description}{deps} -> {node.state.value}")
        lines.append("--------------------------------------------------")
        return "\n".join(lines)

    def _update_readiness(self) -> None:
        for node in self.nodes.values():
            if node.state == TaskState.PENDING:
                all_deps_done = all(
                    self.nodes.get(dep) and self.nodes[dep].state == TaskState.COMPLETED for dep in node.depends_on
                )
                if all_deps_done:
                    node.state = TaskState.READY

    def _propagate_blocked(self, failed_task_id: str) -> None:
        queue = deque([failed_task_id])
        while queue:
            parent = queue.popleft()
            for node in self.nodes.values():
                if parent in node.depends_on and node.state not in (TaskState.COMPLETED, TaskState.FAILED):
                    node.state = TaskState.BLOCKED
                    queue.append(node.task_id)
