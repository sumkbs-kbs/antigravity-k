from __future__ import annotations

import os
from typing import assert_never

from pydantic import TypeAdapter, ValidationError

from antigravity_k.engine.task_state_types import TaskStatusName

_status_adapter: TypeAdapter[TaskStatusName] = TypeAdapter(TaskStatusName)


def owner_pid_for_status(status: TaskStatusName) -> int | None:
    match status:
        case "running" | "resuming":
            return os.getpid()
        case "pending" | "paused" | "done" | "failed" | "cancelled":
            return None
    assert_never(status)


def can_prepare_resume(raw_status: str, owner_pid: int | None) -> bool:
    try:
        status = _status_adapter.validate_python(raw_status)
    except ValidationError:
        return False
    match status:
        case "paused" | "failed":
            return True
        case "running" | "resuming":
            return owner_pid is not None and owner_pid != os.getpid() and not _process_is_alive(owner_pid)
        case "pending" | "done" | "cancelled":
            return False
    assert_never(status)


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
