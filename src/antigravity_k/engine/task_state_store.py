from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from antigravity_k.engine.task_events import (
    ExecutionEventRecord,
    RunEventMetadata,
    append_execution_event,
    initialize_execution_event_schema,
    list_execution_events,
)
from antigravity_k.engine.task_execution_context import (
    TaskExecutionContext as TaskExecutionContext,
)
from antigravity_k.engine.task_execution_context import (
    bind_task_execution_context as bind_task_execution_context,
)
from antigravity_k.engine.task_execution_context import (
    current_task_execution_context as current_task_execution_context,
)
from antigravity_k.engine.task_process_ownership import can_prepare_resume, owner_pid_for_status
from antigravity_k.engine.task_state_types import (
    ALLOWED_TASK_TRANSITIONS,
    TASK_STATUSES,
    TERMINAL_TASK_STATUSES,
    CheckpointRecord,
    InvalidTaskStatusError,
    InvalidTaskTransitionError,
    TaskRecord,
    TaskStatusName,
)


class TaskStateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS task_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE, "
                "prompt TEXT NOT NULL, status TEXT NOT NULL, output TEXT, error TEXT, "
                "created_at TEXT NOT NULL, completed_at TEXT, updated_at TEXT, owner_pid INTEGER, "
                "owner_subject TEXT NOT NULL DEFAULT 'loopback')",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS task_checkpoints ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, step INTEGER NOT NULL, "
                "context_json TEXT NOT NULL, output_so_far TEXT NOT NULL, created_at TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS task_idempotency ("
                "idempotency_key TEXT NOT NULL, owner_subject TEXT NOT NULL DEFAULT 'loopback', "
                "task_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, "
                "PRIMARY KEY (idempotency_key, owner_subject))",
            )
            initialize_execution_event_schema(connection)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(task_history)").fetchall()}
            if "updated_at" not in columns:
                connection.execute("ALTER TABLE task_history ADD COLUMN updated_at TEXT")
                connection.execute("UPDATE task_history SET updated_at = created_at WHERE updated_at IS NULL")
            if "owner_pid" not in columns:
                connection.execute("ALTER TABLE task_history ADD COLUMN owner_pid INTEGER")
            if "owner_subject" not in columns:
                connection.execute("ALTER TABLE task_history ADD COLUMN owner_subject TEXT NOT NULL DEFAULT 'loopback'")
            idempotency_info = connection.execute("PRAGMA table_info(task_idempotency)").fetchall()
            idempotency_columns = {row["name"] for row in idempotency_info}
            if "owner_subject" not in idempotency_columns:
                connection.execute(
                    "ALTER TABLE task_idempotency ADD COLUMN owner_subject TEXT NOT NULL DEFAULT 'loopback'",
                )
                idempotency_info = connection.execute("PRAGMA table_info(task_idempotency)").fetchall()
            if any(row["name"] == "idempotency_key" and row["pk"] == 1 for row in idempotency_info) and not any(
                row["name"] == "owner_subject" and row["pk"] == 2 for row in idempotency_info
            ):
                connection.execute("ALTER TABLE task_idempotency RENAME TO task_idempotency_legacy")
                connection.execute(
                    "CREATE TABLE task_idempotency ("
                    "idempotency_key TEXT NOT NULL, owner_subject TEXT NOT NULL DEFAULT 'loopback', "
                    "task_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, "
                    "PRIMARY KEY (idempotency_key, owner_subject))",
                )
                connection.execute(
                    "INSERT INTO task_idempotency (idempotency_key, owner_subject, task_id, created_at) "
                    "SELECT idempotency_key, owner_subject, task_id, created_at FROM task_idempotency_legacy",
                )
                connection.execute("DROP TABLE task_idempotency_legacy")

    def create_task(
        self,
        task_id: str,
        prompt: str,
        status: TaskStatusName,
        created_at: str,
        idempotency_key: str | None = None,
        owner_subject: str = "loopback",
    ) -> str:
        if status not in TASK_STATUSES:
            raise InvalidTaskStatusError(status)

        normalized_owner = owner_subject.strip() or "loopback"
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                row = connection.execute(
                    "SELECT task_id FROM task_idempotency WHERE idempotency_key = ? AND owner_subject = ?",
                    (idempotency_key, normalized_owner),
                ).fetchone()
                if row:
                    return str(row["task_id"])

            connection.execute(
                "INSERT INTO task_history (task_id, prompt, status, created_at, updated_at, owner_subject) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, prompt, status, created_at, created_at, normalized_owner),
            )
            if idempotency_key:
                connection.execute(
                    "INSERT INTO task_idempotency (idempotency_key, owner_subject, task_id, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (idempotency_key, normalized_owner, task_id, created_at),
                )
        return task_id

    def get_task(self, task_id: str, owner_subject: str | None = None) -> TaskRecord | None:
        with self._connection() as connection:
            if owner_subject is None:
                row = connection.execute(
                    "SELECT task_id, prompt, status, output, error, created_at, updated_at, completed_at "
                    "FROM task_history WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT task_id, prompt, status, output, error, created_at, updated_at, completed_at "
                    "FROM task_history WHERE task_id = ? AND owner_subject = ?",
                    (task_id, owner_subject),
                ).fetchone()
        if not row:
            return None
        return {
            "task_id": str(row["task_id"]),
            "prompt": str(row["prompt"]),
            "status": str(row["status"]),
            "output": str(row["output"] or ""),
            "error": row["error"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"] or row["created_at"]),
            "completed_at": row["completed_at"],
        }

    def transition(
        self,
        task_id: str,
        status: TaskStatusName,
        output: str | None = None,
        error: str | None = None,
    ) -> bool:
        if status not in TASK_STATUSES:
            raise InvalidTaskStatusError(status)

        with self._connection() as connection:
            row = connection.execute(
                "SELECT status, output, error FROM task_history WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if not row:
                return False

            current = str(row["status"])
            if current != status and status not in ALLOWED_TASK_TRANSITIONS.get(current, frozenset()):
                raise InvalidTaskTransitionError(task_id, current, status)

            updated_at = datetime.now(UTC).isoformat()
            completed_at = updated_at if status in TERMINAL_TASK_STATUSES else None
            connection.execute(
                "UPDATE task_history SET status = ?, output = ?, error = ?, updated_at = ?, completed_at = ? "
                "WHERE task_id = ?",
                (
                    status,
                    output if output is not None else row["output"],
                    error if error is not None else row["error"],
                    updated_at,
                    completed_at,
                    task_id,
                ),
            )
        return True

    def prepare_resume(self, task_id: str, owner_subject: str | None = None) -> bool:
        with self._connection() as connection:
            if owner_subject is None:
                row = connection.execute(
                    "SELECT status, owner_pid FROM task_history WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT status, owner_pid FROM task_history WHERE task_id = ? AND owner_subject = ?",
                    (task_id, owner_subject),
                ).fetchone()
            owner_pid = None if not row or row["owner_pid"] is None else int(row["owner_pid"])
            raw_status = "" if not row else str(row["status"])
            if not row or not can_prepare_resume(raw_status, owner_pid):
                return False

            cursor = connection.execute(
                "UPDATE task_history SET status = ?, error = NULL, updated_at = ?, completed_at = NULL, "
                "owner_pid = ? "
                "WHERE task_id = ? AND status = ? AND owner_pid IS ?"
                + (" AND owner_subject = ?" if owner_subject is not None else ""),
                (
                    "resuming",
                    datetime.now(UTC).isoformat(),
                    owner_pid_for_status("resuming"),
                    task_id,
                    raw_status,
                    owner_pid,
                )
                + ((owner_subject,) if owner_subject is not None else ()),
            )
        return cursor.rowcount == 1

    def list_tasks(self, limit: int, owner_subject: str | None = None) -> list[TaskRecord]:
        with self._connection() as connection:
            if owner_subject is None:
                rows = connection.execute(
                    "SELECT task_id, prompt, status, output, error, created_at, updated_at, completed_at "
                    "FROM task_history ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT task_id, prompt, status, output, error, created_at, updated_at, completed_at "
                    "FROM task_history WHERE owner_subject = ? ORDER BY created_at DESC LIMIT ?",
                    (owner_subject, limit),
                ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def save_checkpoint(self, task_id: str, step: int, context_json: str, output: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO task_checkpoints "
                "(task_id, step, context_json, output_so_far, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, step, context_json, output, datetime.now(UTC).isoformat()),
            )

    def get_last_checkpoint(self, task_id: str, owner_subject: str | None = None) -> CheckpointRecord | None:
        with self._connection() as connection:
            query = (
                "SELECT c.task_id, c.step, c.context_json, c.output_so_far, c.created_at "
                "FROM task_checkpoints c JOIN task_history t ON t.task_id = c.task_id "
                "WHERE c.task_id = ?"
            )
            params: tuple[str, ...] = (task_id,)
            if owner_subject is not None:
                query += " AND t.owner_subject = ?"
                params += (owner_subject,)
            query += " ORDER BY c.step DESC LIMIT 1"
            row = connection.execute(query, params).fetchone()
        if not row:
            return None
        return {
            "task_id": str(row["task_id"]),
            "step": int(row["step"]),
            "context_json": str(row["context_json"]),
            "output_so_far": str(row["output_so_far"]),
            "created_at": str(row["created_at"]),
        }

    def append_execution_event(
        self,
        task_id: str,
        event_type: str,
        payload_json: str,
        metadata: RunEventMetadata | None = None,
    ) -> int:
        with self._connection() as connection:
            return append_execution_event(
                connection,
                task_id,
                event_type,
                payload_json,
                metadata,
            )

    def list_execution_events(
        self,
        task_id: str,
        after_sequence: int = 0,
        limit: int = 1_000,
        owner_subject: str | None = None,
    ) -> list[ExecutionEventRecord]:
        if owner_subject is not None and self.get_task(task_id, owner_subject) is None:
            return []
        with self._connection() as connection:
            return list_execution_events(connection, task_id, after_sequence, limit)

    def _row_to_task(self, row: sqlite3.Row) -> TaskRecord:
        return {
            "task_id": str(row["task_id"]),
            "prompt": str(row["prompt"]),
            "status": str(row["status"]),
            "output": str(row["output"] or ""),
            "error": row["error"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"] or row["created_at"]),
            "completed_at": row["completed_at"],
        }
