from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

from antigravity_k.engine.provider_adapters.unsloth_resource_contracts import (
    ReservationId,
    UnslothReservation,
    UnslothReservationState,
    UnslothResourceOperation,
)

_TABLE_NAME: Final = "unsloth_resource_reservations"
_CREATE_TABLE_SQL: Final = (
    f"CREATE TABLE IF NOT EXISTS {_TABLE_NAME} ("
    "reservation_id TEXT PRIMARY KEY,"
    "idempotency_key TEXT NOT NULL UNIQUE,"
    "request_fingerprint TEXT NOT NULL,"
    "operation TEXT NOT NULL,"
    "device_id TEXT NOT NULL,"
    "estimated_peak_bytes INTEGER NOT NULL,"
    "provenance_fingerprint TEXT NOT NULL,"
    "resource_job_id TEXT,"
    "state TEXT NOT NULL,"
    "created_at TEXT NOT NULL,"
    "released_at TEXT)"
)
_INSERT_SQL: Final = (
    f"INSERT INTO {_TABLE_NAME} ("
    "reservation_id,idempotency_key,request_fingerprint,operation,device_id,"
    "estimated_peak_bytes,provenance_fingerprint,resource_job_id,state,created_at,released_at"
    ") VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)"
)
_RELEASE_SQL: Final = (
    f"UPDATE {_TABLE_NAME} SET state = ?, released_at = COALESCE(released_at, ?) WHERE reservation_id = ? RETURNING *"
)
_BIND_JOB_SQL: Final = (
    f"UPDATE {_TABLE_NAME} SET resource_job_id = COALESCE(resource_job_id, ?) "
    "WHERE reservation_id = ? AND state = ? AND (resource_job_id IS NULL OR resource_job_id = ?) RETURNING *"
)


@dataclass(frozen=True, slots=True)
class RepositoryRowError(RuntimeError):
    column: str
    expected: str

    @override
    def __str__(self) -> str:
        return f"Expected {self.expected} in SQLite column {self.column}."


def _text(row: sqlite3.Row, column: str | int) -> str:
    match row[column]:  # noqa: MATCH_OK
        case str() as value:
            return value
    raise RepositoryRowError(str(column), "text")


def _integer(row: sqlite3.Row, column: str | int) -> int:
    match row[column]:  # noqa: MATCH_OK
        case int() as value:
            return value
    raise RepositoryRowError(str(column), "integer")


def _optional_text(row: sqlite3.Row, column: str) -> str | None:
    match row[column]:  # noqa: MATCH_OK
        case str() as value:
            return value
        case None:
            return None
    raise RepositoryRowError(column, "nullable text")


@dataclass(frozen=True, slots=True)
class StoredAdmission:
    reservation_id: ReservationId
    request_fingerprint: str
    provenance_fingerprint: str
    resource_job_id: str | None
    state: UnslothReservationState


@dataclass(frozen=True, slots=True)
class PendingReservation:
    reservation_id: ReservationId
    idempotency_key: str
    request_fingerprint: str
    operation: UnslothResourceOperation
    device_id: str
    estimated_peak_bytes: int
    provenance_fingerprint: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AdmissionTransaction:
    connection: sqlite3.Connection

    def find_idempotency_key(self, idempotency_key: str) -> StoredAdmission | None:
        match self.connection.execute(  # noqa: MATCH_OK
            f"SELECT * FROM {_TABLE_NAME} WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone():
            case None:
                return None
            case sqlite3.Row() as row:
                return StoredAdmission(
                    reservation_id=ReservationId(_text(row, "reservation_id")),
                    request_fingerprint=_text(row, "request_fingerprint"),
                    provenance_fingerprint=_text(row, "provenance_fingerprint"),
                    resource_job_id=_optional_text(row, "resource_job_id"),
                    state=UnslothReservationState(_text(row, "state")),
                )
        raise RepositoryRowError("idempotency lookup", "SQLite row")

    def active_count(self, device_id: str) -> int:
        match self.connection.execute(  # noqa: MATCH_OK
            f"SELECT COUNT(*) FROM {_TABLE_NAME} WHERE device_id = ? AND state = ?",
            (device_id, UnslothReservationState.ACTIVE.value),
        ).fetchone():
            case sqlite3.Row() as row:
                return _integer(row, 0)
        raise RepositoryRowError("active count", "SQLite row")

    def insert(self, pending: PendingReservation) -> None:
        _ = self.connection.execute(
            _INSERT_SQL,
            (
                pending.reservation_id,
                pending.idempotency_key,
                pending.request_fingerprint,
                pending.operation.value,
                pending.device_id,
                pending.estimated_peak_bytes,
                pending.provenance_fingerprint,
                UnslothReservationState.ACTIVE.value,
                pending.created_at,
            ),
        )


class UnslothResourceRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path: Path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def admission(self) -> Generator[AdmissionTransaction, None, None]:
        with self._connection() as connection:
            _ = connection.execute("BEGIN IMMEDIATE")
            yield AdmissionTransaction(connection)

    def list_active(self) -> tuple[UnslothReservation, ...]:
        with self._connection() as connection:
            cursor = connection.execute(
                f"SELECT * FROM {_TABLE_NAME} WHERE state = ? ORDER BY created_at",
                (UnslothReservationState.ACTIVE.value,),
            )
            reservations: list[UnslothReservation] = []
            while True:
                match cursor.fetchone():  # noqa: MATCH_OK
                    case None:
                        return tuple(reservations)
                    case sqlite3.Row() as row:
                        reservations.append(self._row_to_reservation(row))
                        continue
                raise RepositoryRowError("active reservations", "SQLite row")

    def release(self, reservation_id: ReservationId, released_at: str) -> UnslothReservation | None:
        with self._connection() as connection:
            _ = connection.execute("BEGIN IMMEDIATE")
            match connection.execute(  # noqa: MATCH_OK
                _RELEASE_SQL,
                (UnslothReservationState.RELEASED.value, released_at, reservation_id),
            ).fetchone():
                case None:
                    return None
                case sqlite3.Row() as row:
                    return self._row_to_reservation(row)
            raise RepositoryRowError("released reservation", "SQLite row")

    def bind_job(self, reservation_id: ReservationId, resource_job_id: str) -> UnslothReservation | None:
        with self._connection() as connection:
            _ = connection.execute("BEGIN IMMEDIATE")
            match connection.execute(  # noqa: MATCH_OK
                _BIND_JOB_SQL,
                (
                    resource_job_id,
                    reservation_id,
                    UnslothReservationState.ACTIVE.value,
                    resource_job_id,
                ),
            ).fetchone():
                case None:
                    return None
                case sqlite3.Row() as row:
                    return self._row_to_reservation(row)
            raise RepositoryRowError("bound reservation", "SQLite row")

    @staticmethod
    def _row_to_reservation(row: sqlite3.Row) -> UnslothReservation:
        return UnslothReservation(
            reservation_id=_text(row, "reservation_id"),
            operation=UnslothResourceOperation(_text(row, "operation")),
            device_id=_text(row, "device_id"),
            estimated_peak_bytes=_integer(row, "estimated_peak_bytes"),
            provenance_fingerprint=_text(row, "provenance_fingerprint"),
            resource_job_id=_optional_text(row, "resource_job_id"),
            state=UnslothReservationState(_text(row, "state")),
            created_at=_text(row, "created_at"),
            released_at=_optional_text(row, "released_at"),
        )

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        _ = connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            _ = connection.execute("PRAGMA journal_mode = WAL")
            _ = connection.execute(_CREATE_TABLE_SQL)
            columns = {_text(row, 1) for row in connection.execute(f"PRAGMA table_info({_TABLE_NAME})")}
            if "resource_job_id" not in columns:
                _ = connection.execute(f"ALTER TABLE {_TABLE_NAME} ADD COLUMN resource_job_id TEXT")
