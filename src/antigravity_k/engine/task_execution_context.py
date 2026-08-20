from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from antigravity_k.engine.task_state_store import TaskStateStore


@dataclass(frozen=True, slots=True)
class TaskExecutionContext:
    task_id: str
    state_store: TaskStateStore


_task_execution_context: ContextVar[TaskExecutionContext | None] = ContextVar(
    "task_execution_context",
    default=None,
)


def current_task_execution_context() -> TaskExecutionContext | None:
    return _task_execution_context.get()


@contextmanager
def bind_task_execution_context(execution_context: TaskExecutionContext) -> Iterator[None]:
    token = _task_execution_context.set(execution_context)
    try:
        yield
    finally:
        _task_execution_context.reset(token)


__all__ = [
    "TaskExecutionContext",
    "bind_task_execution_context",
    "current_task_execution_context",
]
