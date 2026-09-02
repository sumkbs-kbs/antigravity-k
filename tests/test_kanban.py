import logging
import sqlite3
from pathlib import Path
from typing import cast

from _pytest.logging import LogCaptureFixture

from antigravity_k.agents.kanban import KanbanBoard


def test_current_schema_startup_does_not_emit_migration_warning(
    tmp_path: Path, caplog: LogCaptureFixture
) -> None:
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
        columns = {
            row[1]
            for row in table_info_rows
        }

    assert "worktree_branch" in columns
    assert not [
        record
        for record in caplog.records
        if record.name == "antigravity_k.agents.kanban" and record.levelno >= logging.WARNING
    ]
