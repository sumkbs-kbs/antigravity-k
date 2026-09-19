"""CR-14 F-36 회귀 — **크래시 뒤 재시작한 서버의 표면은 소유 사실을 말한다.**

발견(F-36, attempt-028 · C14-03 의 `restart` 슬라이스)
=====================================================
`resume` 은 소유자를 보는데(`can_prepare_resume`) **보고**는 보지 않았다. 그래서 서버가 SIGKILL
되고 다시 뜬 뒤, 죽은 소유자의 `running` 행은 표면에서 **살아 있는 실행과 구별되지 않았다**:

    status: "running"          ← 저장된 상태(정책 — 바꾸지 않는다)
    (소유 사실을 말하는 필드 없음)

화면의 행동 규칙(`TaskQueuePanel`)은 그 `running` 을 "실행 중"으로 읽어 **재개 대신 취소만**
제안했고, 정작 서버는 같은 행에 대해 `POST /resume` 을 200 으로 받아줬다(실측: 증인
`attempt-028/repro/f36_orphan_surface_witness.py`, 고침 전 위반 4건).

고침 — 표면이 **파생 사실**을 말한다(저장하지 않고, 정책을 바꾸지 않는다):
  - `execution_owner`: `"live" | "dead" | "none"` — 그 실행 주인이 살아 있는가
    (`execution_owner_of`, `can_*` 와 **같은 liveness 함수**를 쓴다).
  - `resumable`: 이 행에 대해 `POST /resume` 이 성공할 것인가
    (`resumable_task` = 체크포인트 존재 **그리고** `can_prepare_resume`).

이 파일은 그 계약과 **이빨**을 고정한다: 서버가 "재개 가능"이라고 말하면 행동도 성공하고,
말하지 않으면 행동도 거부한다(체크포인트 없는 행). 그리고 **정책 불변** — 투영을 계산해도
저장된 상태는 그대로다(재시작이 고아 행을 자동으로 끝내면 재개 가능성이 사라진다).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from antigravity_k.engine.task_process_ownership import (
    can_prepare_resume,
    execution_owner_of,
    resumable_task,
)
from antigravity_k.engine.task_runner import BackgroundTaskRunner
from antigravity_k.engine.task_state_store import TaskStateStore


def _dead_pid() -> int:
    """확실히 죽은 pid — 실제로 프로세스를 세웠다가 종료시키고 그 pid 를 쓴다.

    "그냥 큰 수"를 쓰면 플랫폼마다 `os.kill(pid, 0)` 의 결과가 달라진다(pid 상한을 넘는 값은
    `OverflowError`). 죽은 pid 만이 이 계약의 전제를 만든다.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=10)
    return proc.pid


def _seed_orphan(store: TaskStateStore, task_id: str, *, owner_pid: int, with_checkpoint: bool) -> None:
    """크래시가 남긴 것과 **같은 모양**의 행: `running` + **죽은** 소유 pid(+체크포인트)."""
    _ = store.create_task(task_id, "F-36 계약용 태스크", "pending", datetime.now(UTC).isoformat())
    assert store.transition(task_id, "running", expected_status="pending", expected_version=0) is True
    if with_checkpoint:
        store.save_checkpoint(task_id, 0, "{}", "")
    # 소유 pid 를 죽은 값으로 바꾼다 — 이 행을 실행하는 살아 있는 프로세스가 없는 상태를 만든다.
    # (공개 API 는 언제나 `os.getpid()` 를 쓴다: 그 사실 자체가 이 결함의 전제다.)
    with store._connection() as connection:
        _ = connection.execute("UPDATE task_history SET owner_pid = ? WHERE task_id = ?", (owner_pid, task_id))


def test_execution_owner_matrix_matches_the_liveness_rule() -> None:
    dead = _dead_pid()

    assert execution_owner_of("running", os.getpid()) == "live"
    assert execution_owner_of("resuming", os.getpid()) == "live"
    assert execution_owner_of("running", dead) == "dead"
    assert execution_owner_of("resuming", dead) == "dead"
    # 소유 pid 가 없는 `running`(레거시 행)은 "살아 있다"고 말할 근거가 없다.
    assert execution_owner_of("running", None) == "none"
    for status in ("pending", "paused", "done", "failed", "cancelled"):
        assert execution_owner_of(status, dead) == "none"
    assert execution_owner_of("not-a-status", dead) == "none"


def test_resumable_requires_both_the_owner_rule_and_a_checkpoint() -> None:
    dead = _dead_pid()

    assert resumable_task("running", dead, has_checkpoint=True) is True
    # 이빨: 체크포인트가 없으면 **행동도 거부한다** — 표면만 `true` 라고 말하면 안 된다.
    assert resumable_task("running", dead, has_checkpoint=False) is False
    # 지금 이 프로세스가 실행 중인 행은 재개할 수 없다(`can_prepare_resume` 이 자기 pid 를 거부한다).
    assert resumable_task("running", os.getpid(), has_checkpoint=True) is False
    assert resumable_task("failed", None, has_checkpoint=True) is True
    assert resumable_task("cancelled", None, has_checkpoint=True) is False
    assert resumable_task("done", None, has_checkpoint=True) is False


@pytest.mark.parametrize(
    ("status", "owner_pid_is_self"),
    [
        ("running", False),
        ("running", True),
        ("resuming", True),
        ("failed", False),
        ("cancelled", False),
        ("pending", True),
    ],
)
def test_resumable_is_exactly_the_action_predicate(status: str, owner_pid_is_self: bool) -> None:
    """표면의 `resumable` 은 행동의 문(`can_prepare_resume`)과 **같은 함수**에서 나온다.

    두 규칙이 복제되면 그 사이가 조용한 자리가 된다(F-27·F-35 계열) — 그래서 값이 아니라
    **동치**를 계약한다.
    """
    owner_pid = os.getpid() if owner_pid_is_self else _dead_pid()

    assert resumable_task(status, owner_pid, has_checkpoint=True) is can_prepare_resume(status, owner_pid)


def test_store_projection_carries_the_owner_and_batches_checkpoints(tmp_path: Path) -> None:
    db = tmp_path / "tasks.db"
    store = TaskStateStore(str(db))
    dead = _dead_pid()
    _seed_orphan(store, "task_orphan_with", owner_pid=dead, with_checkpoint=True)
    _seed_orphan(store, "task_orphan_without", owner_pid=dead, with_checkpoint=False)

    record = store.get_task("task_orphan_with")
    assert record is not None and record["owner_pid"] == dead
    listed = {entry["task_id"]: entry for entry in store.list_tasks(limit=10)}
    assert listed["task_orphan_with"]["owner_pid"] == dead
    assert listed["task_orphan_without"]["owner_pid"] == dead

    steps = store.last_checkpoint_steps(["task_orphan_with", "task_orphan_without", "task_missing"])
    # 없는 태스크와 체크포인트 없는 태스크는 **결과에 없다**(0 단계와 구분된다).
    assert steps == {"task_orphan_with": 0}


def test_runner_surface_reports_the_orphan_truthfully(tmp_path: Path) -> None:
    db = tmp_path / "tasks.db"
    store = TaskStateStore(str(db))
    dead = _dead_pid()
    _seed_orphan(store, "task_orphan_with", owner_pid=dead, with_checkpoint=True)
    _seed_orphan(store, "task_orphan_without", owner_pid=dead, with_checkpoint=False)
    runner = BackgroundTaskRunner(db_path=str(db))

    info = runner.get_status("task_orphan_with")
    assert info is not None
    assert info["status"] == "running"  # 저장된 상태는 그대로다(정책 불변)
    assert info["execution_owner"] == "dead"
    assert info["resumable"] is True

    without = runner.get_status("task_orphan_without")
    assert without is not None
    assert without["execution_owner"] == "dead"
    # 이빨: 체크포인트가 없으면 표면도 `false` 이고, 행동(`resume_task`)도 거부한다.
    assert without["resumable"] is False
    assert runner.resume_task("task_orphan_without") is False

    listed = {entry["task_id"]: entry for entry in runner.list_tasks(limit=10)}
    assert listed["task_orphan_with"]["execution_owner"] == "dead"
    assert listed["task_orphan_with"]["resumable"] is True
    assert listed["task_orphan_without"]["resumable"] is False


def test_live_task_reports_live_and_not_resumable(tmp_path: Path) -> None:
    """거짓 양성 0 — 지금 이 프로세스가 실행 중인 태스크는 `live` 이고 재개 대상이 아니다."""
    db = tmp_path / "tasks.db"
    store = TaskStateStore(str(db))
    store.create_task("task_live", "살아 있는 태스크", "pending", datetime.now(UTC).isoformat())
    assert store.transition("task_live", "running", expected_status="pending", expected_version=0) is True
    store.save_checkpoint("task_live", 0, "{}", "")

    runner = BackgroundTaskRunner(db_path=str(db))
    info = runner.get_status("task_live")
    assert info is not None
    assert info["execution_owner"] == "live"
    assert info["resumable"] is False
    stored = store.get_task("task_live")
    assert stored is not None and stored["owner_pid"] == os.getpid()


def test_projection_never_writes_the_row(tmp_path: Path) -> None:
    """정책 불변 — 투영을 여러 번 계산해도 저장된 행(상태·소유 pid·오류)은 그대로다."""
    db = tmp_path / "tasks.db"
    store = TaskStateStore(str(db))
    dead = _dead_pid()
    _seed_orphan(store, "task_orphan", owner_pid=dead, with_checkpoint=True)
    before = store.get_task("task_orphan")
    runner = BackgroundTaskRunner(db_path=str(db))
    for _ in range(3):
        assert runner.get_status("task_orphan") is not None
        _ = runner.list_tasks(limit=5)
    after = store.get_task("task_orphan")

    assert before is not None and after is not None
    assert before == after
    assert after["status"] == "running" and after["error"] is None and after["owner_pid"] == dead


if __name__ == "__main__":  # pragma: no cover — 직접 실행용
    raise SystemExit(pytest.main([__file__, "-q"]))
