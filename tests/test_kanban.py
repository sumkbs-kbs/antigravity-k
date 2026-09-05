import importlib
import logging
import sqlite3
from pathlib import Path
from typing import cast

import pytest
from _pytest.logging import LogCaptureFixture

from antigravity_k.agents.kanban import KanbanBoard


def test_current_schema_startup_does_not_emit_migration_warning(tmp_path: Path, caplog: LogCaptureFixture) -> None:
    db_path = tmp_path / "kanban.db"
    caplog.set_level(logging.WARNING, logger="antigravity_k.agents.kanban")

    _ = KanbanBoard(str(db_path))

    warnings: list[logging.LogRecord] = [
        record
        for record in caplog.records
        if record.name == "antigravity_k.agents.kanban" and record.levelno >= logging.WARNING
    ]
    assert warnings == []


def test_legacy_schema_migration_adds_worktree_branch_without_warning(
    tmp_path: Path, caplog: LogCaptureFixture
) -> None:
    db_path = tmp_path / "legacy-kanban.db"
    with sqlite3.connect(db_path) as conn:
        schema_sql = (
            "CREATE TABLE tasks ("
            + "id TEXT PRIMARY KEY, description TEXT, status TEXT, assignee TEXT, "
            + "tokens_used INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)"
        )
        _ = conn.execute(schema_sql)
        conn.commit()

    caplog.set_level(logging.WARNING, logger="antigravity_k.agents.kanban")
    _ = KanbanBoard(str(db_path))

    with sqlite3.connect(db_path) as conn:
        table_info_rows = cast(
            list[tuple[object, ...]],
            conn.execute("PRAGMA table_info(tasks)").fetchall(),
        )
        columns = {row[1] for row in table_info_rows}

    assert "worktree_branch" in columns
    assert not [
        record
        for record in caplog.records
        if record.name == "antigravity_k.agents.kanban" and record.levelno >= logging.WARNING
    ]


# ─── WS 이벤트 → Kanban 보드 연동 (QualityCheckFailed / AntiPatternsDetected) ──


def _reset_kanban_state() -> None:
    from antigravity_k.api.routes import kanban_api

    kanban_api.kanban_tasks.clear()


def test_quality_check_failed_annotates_in_progress_task() -> None:
    from antigravity_k.api.routes import kanban_api

    _reset_kanban_state()
    try:
        kanban_api.kanban_tasks.append(
            {
                "id": "T1",
                "role": "WORKER",
                "status": "in_progress",
                "title": "[WORKER] Task",
                "description": "Agent is working on the task...",
            }
        )
        kanban_api._on_quality_check_failed(grade="C", feedback="불명확한 응답", task_type="plan")

        task = kanban_api.kanban_tasks[0]
        assert task["quality_failed"] is True
        assert task["quality_grade"] == "C"
        assert "[품질 실패 C]" in cast(str, task["description"])
        assert "불명확한 응답" in cast(str, task["description"])
    finally:
        _reset_kanban_state()


def test_quality_check_failed_skips_when_no_in_progress_task() -> None:
    from antigravity_k.api.routes import kanban_api

    _reset_kanban_state()
    try:
        kanban_api.kanban_tasks.append(
            {"id": "T1", "role": "WORKER", "status": "completed", "title": "done", "description": "x"}
        )
        kanban_api._on_quality_check_failed(grade="F", feedback="실패")

        assert "quality_failed" not in kanban_api.kanban_tasks[0]
    finally:
        _reset_kanban_state()


def test_anti_patterns_detected_annotates_in_progress_task() -> None:
    from antigravity_k.api.routes import kanban_api

    _reset_kanban_state()
    try:
        kanban_api.kanban_tasks.append(
            {
                "id": "T1",
                "role": "WORKER",
                "status": "in_progress",
                "title": "[WORKER] Task",
                "description": "Agent is working on the task...",
            }
        )
        kanban_api._on_anti_patterns_detected(
            reason="반복 실패 감지",
            tools=["run_bash_command"],
            patterns=["'run_bash_command' 사용 시 timeout 발생"],
        )

        task = kanban_api.kanban_tasks[0]
        assert task["anti_patterns"] is True
        assert "[안티패턴 감지]" in cast(str, task["description"])
        assert "timeout 발생" in cast(str, task["description"])
    finally:
        _reset_kanban_state()


def test_kanban_subscribes_to_quality_and_anti_patterns_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscribed: list[str] = []

    class _FakeBus:
        def subscribe(self, e_name: str, _cb: object) -> None:
            subscribed.append(e_name)

    monkeypatch.setattr("antigravity_k.engine.event_bus.global_event_bus", _FakeBus())
    importlib.reload(importlib.import_module("antigravity_k.api.routes.kanban_api"))

    assert "QualityCheckFailed" in subscribed
    assert "AntiPatternsDetected" in subscribed
    assert "AgentTurnStarted" in subscribed
    assert "AgentTurnEnded" in subscribed
