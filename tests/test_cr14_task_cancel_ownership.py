"""F-35 계약 — **취소도 소유 규칙을 지킨다**(다른 살아 있는 프로세스의 실행은 취소되지 않는다).

무엇을 고정하는가
=================
attempt-027 의 증인(`attempt-027/repro/f35_foreign_cancel_witness.py`)이 실물 두 프로세스로 재현한
결함은 이것이다: `resume` 은 `can_prepare_resume(raw_status, owner_pid)` 로 **소유자**를 보는데
`cancel` 은 보지 않아서, 다른 프로세스가 실행 중인 태스크를 `cancelled` 로 적을 수 있었다 —
그 행은 \"끝났다\"고 말하는데 실행은 계속되고(취소 신호는 프로세스 안의 event 다), 소유자의 마지막
상태 쓰기는 CAS 에 막혀 반영되지 않아 **이력이 거짓**이 됐다(증인 C1·C2·C3).

이 파일은 그 고침을 세 층에서 잰다:

1. **규칙**(`task_process_ownership.can_cancel`) — `resume` 과 **같은** liveness 함수를 쓴다.
2. **저장소**(`TaskStateStore.cancel_if_permitted`) — 거부는 행을 **건드리지 않고**, 허용은 CAS 로만 적는다.
3. **러너**(`BackgroundTaskRunner.cancel_verdict`) — 거부 사유를 이름으로 돌려준다(API 가 409/404 로 가른다).

시험대가 `owner_pid` 를 직접 쓰는 이유
======================================
\"다른 프로세스가 그 행을 실행 중이다\"는 상태는 그 프로세스가 `running` 전이에서 남긴 `owner_pid`
그 자체다(`owner_pid_for_status(\"running\") = os.getpid()`). 그래서 계약은 그 열을 **실제로 살아 있는
다른 pid** 로 세워 놓고 규칙을 잰다 — 프로세스 두 개를 띄우는 일은 증인이 이미 실물로 했다.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from antigravity_k.engine.task_process_ownership import can_cancel
from antigravity_k.engine.task_runner import BackgroundTaskRunner
from antigravity_k.engine.task_state_store import TaskStateStore
from antigravity_k.engine.task_state_types import InvalidTaskTransitionError

_CREATED_AT = "2026-09-14T00:00:00+00:00"


@contextmanager
def _live_process() -> Iterator[int]:
    """우리 프로세스가 **아닌** 실제로 살아 있는 pid(플랫폼 무관: 이 인터프리터로 sleep)."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        yield process.pid
    finally:
        process.kill()
        process.wait(timeout=10)


def _dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait(timeout=10)
    return process.pid


def _force_owner(db_path: str, task_id: str, owner_pid: int | None) -> None:
    """`owner_pid` 열을 직접 세운다 — 그 열을 쓰는 주체는 실행 중인 프로세스다(`owner_pid_for_status`)."""
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            "UPDATE task_history SET owner_pid = ? WHERE task_id = ?",
            (owner_pid, task_id),
        )
        connection.commit()


def _seed_running(store: TaskStateStore, db_path: str, task_id: str, owner_pid: int | None) -> None:
    _ = store.create_task(task_id, "prompt", "pending", _CREATED_AT)
    assert store.transition(task_id, "running") is True
    _force_owner(db_path, task_id, owner_pid)


# --------------------------------------------------------------------------- #
# 1. 규칙
# --------------------------------------------------------------------------- #
def test_can_cancel_allows_this_process_and_orphans_but_refuses_a_live_foreign_owner() -> None:
    with _live_process() as foreign_pid:
        own_pid = os.getpid()
        dead = _dead_pid()

        # 이 프로세스가 소유한 실행은 취소할 수 있다.
        assert can_cancel("running", own_pid) is True
        assert can_cancel("resuming", own_pid) is True
        # 소유자가 없는 행(레거시)과 죽은 소유자(재시작 뒤의 고아)도 취소할 수 있다.
        assert can_cancel("running", None) is True
        assert can_cancel("running", dead) is True
        assert can_cancel("resuming", dead) is True
        # **다른 살아 있는 프로세스**의 실행은 취소할 수 없다 — F-35 가 닫은 자리다.
        assert can_cancel("running", foreign_pid) is False
        assert can_cancel("resuming", foreign_pid) is False


def test_can_cancel_allows_pending_because_the_start_cas_makes_it_real() -> None:
    """`pending` 취소는 소유자가 없어도 **실제로 실행을 막는다** — 그래서 허용한다.

    허용의 근거는 "무해하다"가 아니라 "그 취소가 진짜다"이다: 소유자의 시작 CAS 가 실패한다
    (`test_store_cancel_of_a_pending_task_actually_prevents_the_run` 이 그 사실을 잰다).
    """
    with _live_process() as foreign_pid:
        assert can_cancel("pending", foreign_pid) is True
        assert can_cancel("paused", foreign_pid) is True


def test_can_cancel_refuses_terminal_and_unknown_statuses() -> None:
    with _live_process() as foreign_pid:
        for status in ("done", "failed", "cancelled"):
            assert can_cancel(status, foreign_pid) is False
            assert can_cancel(status, None) is False
    assert can_cancel("not-a-status", 1) is False


# --------------------------------------------------------------------------- #
# 2. 저장소
# --------------------------------------------------------------------------- #
def test_store_refuses_a_cancel_owned_by_a_live_process_and_leaves_the_row_untouched(tmp_path: Path) -> None:
    db_path = str(tmp_path / "tasks.db")
    store = TaskStateStore(db_path)
    with _live_process() as foreign_pid:
        _seed_running(store, db_path, "task-foreign", foreign_pid)
        before = store.get_task("task-foreign")
        assert before is not None

        assert store.cancel_if_permitted("task-foreign") == "owned_elsewhere"

        after = store.get_task("task-foreign")
        assert after is not None
        # 거부는 **아무것도 바꾸지 않는다** — 상태도, 소유자도, version 도.
        assert after["status"] == "running"
        assert after["version"] == before["version"]
        with sqlite3.connect(db_path) as connection:
            owner = connection.execute(
                "SELECT owner_pid FROM task_history WHERE task_id = ?",
                ("task-foreign",),
            ).fetchone()
        assert owner is not None and int(owner[0]) == foreign_pid


def test_store_cancels_the_orphan_of_a_dead_owner(tmp_path: Path) -> None:
    """재시작 뒤의 고아는 **여전히 취소된다** — 고침이 복구 경로를 막지 않았다는 증거다."""
    db_path = str(tmp_path / "tasks.db")
    store = TaskStateStore(db_path)
    dead = _dead_pid()
    _seed_running(store, db_path, "task-orphan", dead)

    assert store.cancel_if_permitted("task-orphan") == "cancelled"

    record = store.get_task("task-orphan")
    assert record is not None
    assert record["status"] == "cancelled"
    assert record["error"] is not None and "cancel" in record["error"].lower()


def test_store_cancel_of_a_pending_task_actually_prevents_the_run(tmp_path: Path) -> None:
    """`pending` 을 다른 프로세스가 취소하면 그 태스크는 **시작하지 못한다**(거짓이 아니라 진짜 취소)."""
    db_path = str(tmp_path / "tasks.db")
    store = TaskStateStore(db_path)
    _ = store.create_task("task-pending", "prompt", "pending", _CREATED_AT)

    assert store.cancel_if_permitted("task-pending") == "cancelled"
    # 소유자의 시작 전이는 이제 허용 전이 밖이다(cancelled 는 터미널이다) → 실행되지 않는다.
    with pytest.raises(InvalidTaskTransitionError):
        _ = store.transition("task-pending", "running")


def test_store_cancel_reports_not_active_for_terminal_or_missing_rows(tmp_path: Path) -> None:
    db_path = str(tmp_path / "tasks.db")
    store = TaskStateStore(db_path)
    _ = store.create_task("task-done", "prompt", "pending", _CREATED_AT)
    assert store.transition("task-done", "running") is True
    assert store.transition("task-done", "done", output="ok") is True

    assert store.cancel_if_permitted("task-done") == "not_active"
    assert store.cancel_if_permitted("task-missing") == "not_active"


# --------------------------------------------------------------------------- #
# 3. 러너 (거부 사유를 이름으로)
# --------------------------------------------------------------------------- #
def test_runner_refuses_a_foreign_cancel_then_allows_it_once_the_owner_is_gone(tmp_path: Path) -> None:
    """이빨: 거부가 \"항상 거부\"가 아님을 **같은 태스크**에서 보인다 — 소유자가 죽으면 취소된다."""
    db_path = str(tmp_path / "tasks.db")
    runner = BackgroundTaskRunner(db_path=db_path)
    # 이 블록을 벗어나면 소유 프로세스가 죽는다 — pid 만 남은 "재시작 뒤의 고아"가 된다.
    with _live_process() as foreign_pid:
        _seed_running(runner.state_store, db_path, "task-live", foreign_pid)

        assert runner.cancel_verdict("task-live") == "owned_elsewhere"
        assert runner.cancel_task("task-live") is False
        record = runner.state_store.get_task("task-live")
        assert record is not None and record["status"] == "running"

        # 죽은 소유자의 고아 — bool API 가 **허용 경로**에서도 True 를 낸다(별도 태스크).
        _seed_running(runner.state_store, db_path, "task-orphan", _dead_pid())
        assert runner.cancel_task("task-orphan") is True

    assert runner.cancel_verdict("task-live") == "cancelled"
    record = runner.state_store.get_task("task-live")
    assert record is not None and record["status"] == "cancelled"


def test_runner_reports_not_active_for_a_task_that_never_existed(tmp_path: Path) -> None:
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))

    assert runner.cancel_verdict("task-nope") == "not_active"
    assert runner.cancel_task("task-nope") is False
