from __future__ import annotations

from typing import Final, Literal, TypedDict

TaskStatusName = Literal["pending", "running", "resuming", "done", "failed", "paused", "cancelled"]

TASK_STATUSES: Final[frozenset[str]] = frozenset(
    {"pending", "running", "resuming", "done", "failed", "paused", "cancelled"},
)
TERMINAL_TASK_STATUSES: Final[frozenset[str]] = frozenset({"done", "failed", "cancelled"})
ALLOWED_TASK_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"running", "cancelled"}),
    "running": frozenset({"done", "failed", "paused", "cancelled"}),
    "paused": frozenset({"running", "resuming", "cancelled"}),
    "resuming": frozenset({"running", "failed", "cancelled"}),
    "done": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class TaskRecord(TypedDict):
    task_id: str
    prompt: str
    status: str
    output: str
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class CheckpointRecord(TypedDict):
    task_id: str
    step: int
    context_json: str
    output_so_far: str
    created_at: str


class InvalidTaskTransitionError(RuntimeError):
    def __init__(self, task_id: str, current: str, requested: str) -> None:
        self.task_id: str = task_id
        self.current: str = current
        self.requested: str = requested
        super().__init__(f"Task {task_id} cannot transition from {current} to {requested}")


class InvalidTaskStatusError(ValueError):
    def __init__(self, status: str) -> None:
        self.status: str = status
        super().__init__(f"Unknown task status: {status}")


def parse_task_status(value: str) -> TaskStatusName:
    if value == "pending":
        return "pending"
    if value == "running":
        return "running"
    if value == "resuming":
        return "resuming"
    if value == "done":
        return "done"
    if value == "failed":
        return "failed"
    if value == "paused":
        return "paused"
    if value == "cancelled":
        return "cancelled"
    raise InvalidTaskStatusError(value)


__all__ = [
    "ALLOWED_TASK_TRANSITIONS",
    "CheckpointRecord",
    "InvalidTaskStatusError",
    "InvalidTaskTransitionError",
    "parse_task_status",
    "TASK_STATUSES",
    "TERMINAL_TASK_STATUSES",
    "TaskRecord",
    "TaskStatusName",
]
