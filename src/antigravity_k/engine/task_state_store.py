from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Iterator, Literal, TypedDict

TaskStatusName = Literal["pending", "running", "resuming", "done", "failed", "paused", "cancelled"]

_STATUSES: Final[frozenset[str]] = frozenset(
    {"pending", "running", "resuming", "done", "failed", "paused", "cancelled"},
)
_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"done", "failed", "cancelled"})
_ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
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


class ExecutionEventRecord(TypedDict):
    sequence: int
    task_id: str
    event_type: str
    payload_json: str
    created_at: str


class InvalidTaskTransitionError(RuntimeError):
    def __init__(self, task_id: str, current: str, requested: str):
        self.task_id = task_id
        self.current = current
        self.requested = requested
        super().__init__(f"Task {task_id} cannot transition from {current} to {requested}")


class InvalidTaskStatusError(ValueError):
    def __init__(self, status: str):
        self.status = status
        super().__init__(f"Unknown task status: {status}")


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
                "created_at TEXT NOT NULL, completed_at TEXT, updated_at TEXT)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS task_checkpoints ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, step INTEGER NOT NULL, "
                "context_json TEXT NOT NULL, output_so_far TEXT NOT NULL, created_at TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS task_idempotency ("
                "idempotency_key TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS task_execution_events ("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, "
                "event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)",
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_execution_events_task_sequence "
                "ON task_execution_events (task_id, sequence)",
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(task_history)").fetchall()}
            if "updated_at" not in columns:
                connection.execute("ALTER TABLE task_history ADD COLUMN updated_at TEXT")
                connection.execute("UPDATE task_history SET updated_at = created_at WHERE updated_at IS NULL")

    def create_task(
        self,
        task_id: str,
        prompt: str,
        status: TaskStatusName,
        created_at: str,
        idempotency_key: str | None = None,
    ) -> str:
        if status not in _STATUSES:
            raise InvalidTaskStatusError(status)

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                row = connection.execute(
                    "SELECT task_id FROM task_idempotency WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if row:
                    return str(row["task_id"])

            connection.execute(
                "INSERT INTO task_history (task_id, prompt, status, created_at, updated_at) " "VALUES (?, ?, ?, ?, ?)",
                (task_id, prompt, status, created_at, created_at),
            )
            if idempotency_key:
                connection.execute(
                    "INSERT INTO task_idempotency (idempotency_key, task_id, created_at) VALUES (?, ?, ?)",
                    (idempotency_key, task_id, created_at),
                )
        return task_id

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT task_id, prompt, status, output, error, created_at, updated_at, completed_at "
                "FROM task_history WHERE task_id = ?",
                (task_id,),
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
        if status not in _STATUSES:
            raise InvalidTaskStatusError(status)

        with self._connection() as connection:
            row = connection.execute(
                "SELECT status, output, error FROM task_history WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if not row:
                return False

            current = str(row["status"])
            if current != status and status not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidTaskTransitionError(task_id, current, status)

            updated_at = datetime.now(UTC).isoformat()
            completed_at = updated_at if status in _TERMINAL_STATUSES else None
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

    def prepare_resume(self, task_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status FROM task_history WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if not row or str(row["status"]) not in {"paused", "failed"}:
                return False

            connection.execute(
                "UPDATE task_history SET status = ?, error = NULL, updated_at = ?, completed_at = NULL "
                "WHERE task_id = ?",
                ("resuming", datetime.now(UTC).isoformat(), task_id),
            )
        return True

    def list_tasks(self, limit: int) -> list[TaskRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT task_id, prompt, status, output, error, created_at, updated_at, completed_at "
                "FROM task_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def save_checkpoint(self, task_id: str, step: int, context_json: str, output: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO task_checkpoints "
                "(task_id, step, context_json, output_so_far, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, step, context_json, output, datetime.now(UTC).isoformat()),
            )

    def get_last_checkpoint(self, task_id: str) -> CheckpointRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT task_id, step, context_json, output_so_far, created_at "
                "FROM task_checkpoints WHERE task_id = ? ORDER BY step DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "task_id": str(row["task_id"]),
            "step": int(row["step"]),
            "context_json": str(row["context_json"]),
            "output_so_far": str(row["output_so_far"]),
            "created_at": str(row["created_at"]),
        }

    def append_execution_event(self, task_id: str, event_type: str, payload_json: str) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO task_execution_events "
                "(task_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (task_id, event_type, payload_json, datetime.now(UTC).isoformat()),
            )
        sequence = cursor.lastrowid
        assert sequence is not None
        return sequence

    def list_execution_events(self, task_id: str) -> list[ExecutionEventRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT sequence, task_id, event_type, payload_json, created_at "
                "FROM task_execution_events WHERE task_id = ? ORDER BY sequence ASC",
                (task_id,),
            ).fetchall()
        return [
            {
                "sequence": int(row["sequence"]),
                "task_id": str(row["task_id"]),
                "event_type": str(row["event_type"]),
                "payload_json": str(row["payload_json"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

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
