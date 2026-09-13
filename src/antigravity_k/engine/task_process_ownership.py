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


def can_cancel(raw_status: str, owner_pid: int | None) -> bool:
    """이 프로세스가 그 행을 `cancelled` 로 적어도 되는가 — 소유 규칙은 `can_prepare_resume` 과 같다.

    `resume` 은 소유자를 보는데 `cancel` 은 보지 않았고, 그래서 **살아 있는 다른 프로세스의**
    `running` 태스크를 `cancelled` 로 적을 수 있었다(F-35). 그 행은 "끝났다"고 말하지만
    취소 신호(`cancel_event`)는 그 프로세스 **안에** 있으므로 실행은 계속된다 — 이력이 거짓이 된다.

    - `pending`/`paused`: **허용한다.** `pending` 은 아직 실행 시작 전이라 소유자가 없고, 취소가
      먼저 적히면 소유자의 시작 CAS(`pending → running`)가 실패해 **실행되지 않는다**(거짓이 아니라
      실제로 취소된다). `paused` 는 실행 중이 아니다.
    - `running`/`resuming`: **소유자가 살아 있으면 거부한다** — 이 프로세스이거나,
      소유자가 없거나(레거시 행), 소유자 PID 가 이미 죽었을 때만 허용한다. 그 판정 함수
      (`_process_is_alive`)를 `resume` 과 **공유**하는 것이 요점이다: 두 경로가 다른 규칙을
      쓰면 그 사이가 조용한 자리가 된다.
    - 터미널 상태: 취소할 대상이 아니다.
    """
    try:
        status = _status_adapter.validate_python(raw_status)
    except ValidationError:
        return False
    match status:
        case "pending" | "paused":
            return True
        case "running" | "resuming":
            return owner_pid is None or owner_pid == os.getpid() or not _process_is_alive(owner_pid)
        case "done" | "failed" | "cancelled":
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
