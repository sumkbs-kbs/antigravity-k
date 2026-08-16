from __future__ import annotations

import json
import sqlite3
from typing import ClassVar, Final, Literal, final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from antigravity_k.engine.task_state_store import TaskStateStore

CONTEXT_SNAPSHOT_EVENT: Final = "context_snapshot"
_RESTORED_CONTEXT_HEADER: Final = "[Restored Task Context]"
_TRANSIENT_SYSTEM_PREFIXES: Final = ("[Recalled Memory]", _RESTORED_CONTEXT_HEADER)


SnapshotRole = Literal[
    "system",
    "developer",
    "user",
    "assistant",
    "tool",
    "function",
    "tool_result",
]


class SnapshotMessage(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    role: SnapshotRole
    content: str = Field(max_length=1_000_000)
    name: str | None = Field(default=None, max_length=128)


class TaskContextSnapshot(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    target_model: str = Field(min_length=1, max_length=256)
    messages: tuple[SnapshotMessage, ...] = Field(min_length=1, max_length=256)


@final
class ContextSnapshotStoreError(RuntimeError):
    task_id: str
    reason: str

    def __init__(self, task_id: str, reason: str):
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"Context snapshot failed for {task_id}: {reason}")


def save_task_context_snapshot(
    state_store: TaskStateStore,
    task_id: str,
    messages: list[dict[str, str]],
    target_model: str,
) -> int:
    try:
        snapshot = TaskContextSnapshot(
            target_model=target_model,
            messages=tuple(_snapshot_message(message) for message in messages if _is_durable_message(message)),
        )
        payload = json.dumps(
            snapshot.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return state_store.append_execution_event(task_id, CONTEXT_SNAPSHOT_EVENT, payload)
    except (ValidationError, sqlite3.Error) as error:
        raise ContextSnapshotStoreError(task_id, str(error)) from error


def load_task_context_snapshot(
    state_store: TaskStateStore,
    task_id: str,
) -> TaskContextSnapshot | None:
    try:
        events = state_store.list_execution_events(task_id)
    except sqlite3.Error as error:
        raise ContextSnapshotStoreError(task_id, str(error)) from error

    latest = next(
        (event for event in reversed(events) if event["event_type"] == CONTEXT_SNAPSHOT_EVENT),
        None,
    )
    if latest is None:
        return None
    try:
        return TaskContextSnapshot.model_validate_json(latest["payload_json"])
    except ValidationError:
        return None


def restored_task_context_messages(snapshot: TaskContextSnapshot) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": (
                f"{_RESTORED_CONTEXT_HEADER}\n"
                "The following messages are task-local history restored from the latest durable snapshot."
            ),
        },
    ]
    messages.extend(message.model_dump(exclude_none=True) for message in snapshot.messages)
    return messages


def _is_durable_message(message: dict[str, str]) -> bool:
    if message.get("role") != "system":
        return True
    content = message.get("content", "")
    return not content.startswith(_TRANSIENT_SYSTEM_PREFIXES)


def _snapshot_message(message: dict[str, str]) -> SnapshotMessage:
    payload = {key: message[key] for key in ("role", "content", "name") if key in message}
    return SnapshotMessage.model_validate(payload)
