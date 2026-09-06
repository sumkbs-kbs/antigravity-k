"""DAT-01: task transition CAS, terminal winner, stress, projection order."""

from __future__ import annotations

import json
import multiprocessing as mp
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from antigravity_k.engine.task_state_store import TaskStateStore
from antigravity_k.engine.task_state_types import (
    InvalidTaskTransitionError,
    TaskTransitionConflictError,
)


def _running(store: TaskStateStore, task_id: str = "task-1") -> None:
    _ = store.create_task(task_id, "prompt", "pending", "2026-01-01T00:00:00")
    assert store.transition(task_id, "running") is True


def test_transition_cas_increments_version(tmp_path: Path) -> None:
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _running(store)
    record = store.get_task("task-1")
    assert record is not None
    assert record["version"] == 1  # pending→running

    assert store.transition("task-1", "done", output="ok", expected_status="running", expected_version=1) is True
    done = store.get_task("task-1")
    assert done is not None
    assert done["status"] == "done"
    assert done["version"] == 2
    assert done["output"] == "ok"


def test_affected_zero_raises_typed_conflict(tmp_path: Path) -> None:
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _running(store)
    with pytest.raises(TaskTransitionConflictError) as excinfo:
        _ = store.transition(
            "task-1",
            "done",
            output="stale",
            expected_status="running",
            expected_version=0,  # actual is 1 after pending→running
        )
    err = excinfo.value
    assert err.task_id == "task-1"
    assert err.expected_version == 0
    assert err.current_version == 1
    record = store.get_task("task-1")
    assert record is not None
    assert record["status"] == "running"
    assert record["output"] == ""


def test_terminal_freeze_rejects_overwrite(tmp_path: Path) -> None:
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _running(store)
    assert store.transition("task-1", "done", output="winner") is True
    with pytest.raises(InvalidTaskTransitionError):
        _ = store.transition("task-1", "done", output="loser-overwrite")
    with pytest.raises(InvalidTaskTransitionError):
        _ = store.transition("task-1", "cancelled", error="too-late")
    record = store.get_task("task-1")
    assert record is not None
    assert record["status"] == "done"
    assert record["output"] == "winner"
    assert record["error"] is None


def test_cancel_vs_completion_single_winner_threads(tmp_path: Path) -> None:
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _running(store)
    record = store.get_task("task-1")
    assert record is not None
    version = record["version"]

    results: list[str] = []

    def attempt(status: str, payload: str) -> None:
        try:
            kwargs = {"output": payload} if status == "done" else {"error": payload}
            ok = store.transition(
                "task-1",
                status,  # type: ignore[arg-type]
                expected_status="running",
                expected_version=version,
                **kwargs,
            )
            if ok:
                results.append(f"win:{status}:{payload}")
        except TaskTransitionConflictError:
            results.append(f"lose:{status}:{payload}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, "done", "completion-output"),
            pool.submit(attempt, "cancelled", "cancel-reason"),
        ]
        for fut in futures:
            fut.result(timeout=10)

    assert sum(1 for r in results if r.startswith("win:")) == 1
    assert sum(1 for r in results if r.startswith("lose:")) == 1
    final = store.get_task("task-1")
    assert final is not None
    assert final["status"] in {"done", "cancelled"}
    if final["status"] == "done":
        assert final["output"] == "completion-output"
        assert final["error"] is None
    else:
        assert final["error"] == "cancel-reason"
        assert final["output"] == ""


def test_cancel_completion_race_repeated(tmp_path: Path) -> None:
    """Repeat the race to catch flaky last-write-wins regressions."""
    winners: dict[str, int] = {"done": 0, "cancelled": 0}
    for i in range(40):
        store = TaskStateStore(str(tmp_path / f"race-{i}.db"))
        _running(store, "task-race")
        version = store.get_task("task-race")["version"]  # type: ignore[index]
        box: list[str] = []

        def attempt(status: str, payload: str, ver: int = version) -> None:
            try:
                kwargs = {"output": payload} if status == "done" else {"error": payload}
                if store.transition(
                    "task-race",
                    status,  # type: ignore[arg-type]
                    expected_status="running",
                    expected_version=ver,
                    **kwargs,
                ):
                    box.append(status)
            except TaskTransitionConflictError:
                pass

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(attempt, "done", "out")
            f2 = pool.submit(attempt, "cancelled", "err")
            f1.result(timeout=10)
            f2.result(timeout=10)
        assert len(box) == 1
        winners[box[0]] += 1
        final = store.get_task("task-race")
        assert final is not None
        assert final["status"] == box[0]
    assert winners["done"] + winners["cancelled"] == 40


def _process_worker(
    db_path: str,
    task_id: str,
    status: str,
    payload: str,
    version: int,
    q: mp.Queue,
) -> None:
    store = TaskStateStore(db_path)
    try:
        kwargs = {"output": payload} if status == "done" else {"error": payload}
        ok = store.transition(
            task_id,
            status,  # type: ignore[arg-type]
            expected_status="running",
            expected_version=version,
            **kwargs,
        )
        q.put(("win", status) if ok else ("unexpected", status))
    except TaskTransitionConflictError:
        q.put(("lose", status))
    except Exception as exc:  # noqa: BLE001
        q.put(("error", f"{type(exc).__name__}:{exc}"))


def test_multiprocess_cancel_completion_single_winner(tmp_path: Path) -> None:
    db_path = str(tmp_path / "mp.db")
    store = TaskStateStore(db_path)
    _running(store, "task-mp")
    version = store.get_task("task-mp")["version"]  # type: ignore[index]

    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    procs = [
        ctx.Process(target=_process_worker, args=(db_path, "task-mp", "done", "mp-out", version, q)),
        ctx.Process(target=_process_worker, args=(db_path, "task-mp", "cancelled", "mp-err", version, q)),
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0

    outcomes = [q.get(timeout=5) for _ in range(2)]
    wins = [o for o in outcomes if o[0] == "win"]
    losses = [o for o in outcomes if o[0] == "lose"]
    assert len(wins) == 1, outcomes
    assert len(losses) == 1, outcomes
    final = TaskStateStore(db_path).get_task("task-mp")
    assert final is not None
    assert final["status"] == wins[0][1]
    if final["status"] == "done":
        assert final["output"] == "mp-out"
    else:
        assert final["error"] == "mp-err"


def test_multiprocess_stress_no_invalid_double_terminal(tmp_path: Path) -> None:
    """Many processes racing terminals → exactly one terminal, never both fields."""
    for round_i in range(8):
        db_path = str(tmp_path / f"stress-{round_i}.db")
        store = TaskStateStore(db_path)
        _running(store, "task-stress")
        version = store.get_task("task-stress")["version"]  # type: ignore[index]
        ctx = mp.get_context("spawn")
        q: mp.Queue = ctx.Queue()
        procs = [
            ctx.Process(target=_process_worker, args=(db_path, "task-stress", status, payload, version, q))
            for status, payload in (
                ("done", "A"),
                ("cancelled", "B"),
                ("failed", "C"),
                ("done", "D"),
            )
        ]
        # failed also allowed from running
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
            assert p.exitcode == 0
        outcomes = [q.get(timeout=5) for _ in range(len(procs))]
        wins = [o for o in outcomes if o[0] == "win"]
        assert len(wins) == 1, outcomes
        final = TaskStateStore(db_path).get_task("task-stress")
        assert final is not None
        assert final["status"] in {"done", "cancelled", "failed"}
        # loser payloads must not appear as mixed terminal reason/output
        if final["status"] == "done":
            assert final["output"] in {"A", "D"}
            assert final["error"] is None
        elif final["status"] == "cancelled":
            assert final["error"] == "B"
        else:
            assert final["error"] == "C"


def test_task_status_event_emitted_atomically_with_cas(tmp_path: Path) -> None:
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _running(store)
    assert store.transition("task-1", "cancelled", error="user-cancel", record_event=True) is True
    events = store.list_execution_events("task-1")
    status_events = [e for e in events if e["event_type"] == "task.status"]
    assert len(status_events) == 1  # terminal-only by default
    last = json.loads(status_events[-1]["payload_json"])
    assert last["to_status"] == "cancelled"
    assert last["terminal"] is True
    # No contradictory later terminal: store matches last terminal event
    record = store.get_task("task-1")
    assert record is not None
    assert record["status"] == "cancelled"


def test_projection_prefers_store_over_contradictory_events(tmp_path: Path) -> None:
    """Losers must not append a winning terminal event; store remains SoT."""
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _running(store)
    version = store.get_task("task-1")["version"]  # type: ignore[index]
    assert store.transition(
        "task-1",
        "cancelled",
        error="cancel-win",
        expected_status="running",
        expected_version=version,
        record_event=True,
    )
    with pytest.raises(TaskTransitionConflictError):
        _ = store.transition(
            "task-1",
            "done",
            output="late-complete",
            expected_status="running",
            expected_version=version,
        )
    # Even if a buggy caller appends a contradictory event after the fact,
    # authoritative status stays cancelled.
    _ = store.append_execution_event(
        "task-1",
        "direct_completed",
        json.dumps({"output_length": 12}),
    )
    record = store.get_task("task-1")
    assert record is not None
    assert record["status"] == "cancelled"
    assert record["output"] == ""
    assert record["error"] == "cancel-win"

    from antigravity_k.engine.task_state_projection import resolve_display_terminal_status

    events = store.list_execution_events("task-1")
    display = resolve_display_terminal_status(record["status"], events)
    assert display == "cancelled"


def test_legacy_db_migrates_version_column(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        _ = connection.execute(
            "CREATE TABLE task_history ("
            + "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE, prompt TEXT NOT NULL, "
            + "status TEXT NOT NULL, output TEXT, error TEXT, created_at TEXT NOT NULL, completed_at TEXT)",
        )
        _ = connection.execute(
            "INSERT INTO task_history (task_id, prompt, status, created_at) VALUES (?, ?, ?, ?)",
            ("legacy-task", "prompt", "running", "2026-01-01T00:00:00"),
        )
    store = TaskStateStore(str(db_path))
    record = store.get_task("legacy-task")
    assert record is not None
    assert record["version"] == 0
    assert store.transition("legacy-task", "done", output="migrated") is True
    after = store.get_task("legacy-task")
    assert after is not None
    assert after["version"] == 1
