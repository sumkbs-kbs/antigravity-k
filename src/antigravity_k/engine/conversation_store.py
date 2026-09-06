"""Authoritative conversation history store with revision CAS (CTX-01).

Server-owned message history. Clients send new turns + expected revision only;
append/compact advance revision via compare-and-set. Two concurrent writers
never silently overwrite — losers get stale_conversation_revision (HTTP 409).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, Mapping

from antigravity_k.api.contracts.conversation import ConversationSnapshot
from antigravity_k.api.contracts.errors import (
    ConversationNotFoundError,
    InvalidConversationRevisionError,
    StaleConversationRevisionError,
)
from antigravity_k.engine.context_summary import summarize_messages
from antigravity_k.engine.tokenizer import TokenEstimator

logger = logging.getLogger("antigravity_k.engine.conversation_store")

MessageRole = Literal["user", "assistant", "system", "tool"]

_DEFAULT_RETAIN_TAIL: Final[int] = 6
_SUMMARY_MESSAGE_ID: Final[str] = "msg_summary"


@dataclass(frozen=True)
class ConversationMessage:
    """Single stored message with stable id for retained-range tracking."""

    id: str
    role: MessageRole
    content: str
    created_at: float
    provenance: str = "append"  # append | summary | fork | system

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConversationMessage:
        role = str(data.get("role") or "user")
        if role not in ("user", "assistant", "system", "tool"):
            role = "user"
        return cls(
            id=str(data.get("id") or _new_message_id()),
            role=role,  # type: ignore[arg-type]
            content=str(data.get("content") or ""),
            created_at=float(data.get("created_at") or time.time()),
            provenance=str(data.get("provenance") or "append"),
        )

    def as_chat_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content, "id": self.id}


@dataclass
class ConversationRecord:
    conversation_id: str
    project_id: str
    revision: int = 0
    messages: list[ConversationMessage] = field(default_factory=list)
    summary: str | None = None
    retained_message_ids: tuple[str, ...] = ()
    forked_from: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def snapshot(self) -> ConversationSnapshot:
        retained = self.retained_message_ids or tuple(m.id for m in self.messages)
        return ConversationSnapshot(
            conversation_id=self.conversation_id,
            project_id=self.project_id,
            revision=self.revision,
            message_count=len(self.messages),
            summary=self.summary,
            retained_message_ids=retained,
        )

    def prompt_messages(self) -> list[dict[str, str]]:
        """History assembled for the next model call (authoritative)."""
        out: list[dict[str, str]] = []
        for msg in self.messages:
            out.append({"role": msg.role, "content": msg.content})
        return out

    def estimate_tokens(self) -> int:
        return TokenEstimator.estimate_messages(self.prompt_messages())

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "project_id": self.project_id,
            "revision": self.revision,
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "retained_message_ids": list(self.retained_message_ids),
            "forked_from": self.forked_from,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConversationRecord:
        msgs = [ConversationMessage.from_dict(m) for m in (data.get("messages") or []) if isinstance(m, Mapping)]
        retained_raw = data.get("retained_message_ids") or []
        retained = tuple(str(x) for x in retained_raw) if isinstance(retained_raw, list) else ()
        return cls(
            conversation_id=str(data.get("conversation_id") or ""),
            project_id=str(data.get("project_id") or ""),
            revision=int(data.get("revision") or 0),
            messages=msgs,
            summary=data.get("summary") if isinstance(data.get("summary"), str) else None,
            retained_message_ids=retained,
            forked_from=data.get("forked_from") if isinstance(data.get("forked_from"), str) else None,
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
        )


def _new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _new_conversation_id() -> str:
    return f"conv_{uuid.uuid4().hex[:12]}"


class ConversationStore:
    """Thread-safe authoritative conversation store (revision CAS).

    Implements ``ConversationRevisionStore`` protocol used by ARC-01 resolvers.
    """

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._records: dict[tuple[str, str], ConversationRecord] = {}
        if storage_dir is None:
            storage_dir = os.path.join(os.path.expanduser("~"), ".antigravity", "conversations")
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # ── ConversationRevisionStore protocol ──────────────────────────────

    def get_revision(self, *, project_id: str, conversation_id: str) -> int | None:
        with self._lock:
            record = self._records.get((project_id, conversation_id))
            if record is None:
                record = self._load(project_id, conversation_id)
            return None if record is None else record.revision

    def compare_and_set(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int,
        next_revision: int,
    ) -> bool:
        """Bare revision CAS (no message mutation). Prefer append/compact."""
        with self._lock:
            record = self._ensure_loaded(project_id, conversation_id)
            if record is None:
                if expected_revision != 0:
                    return False
                record = ConversationRecord(
                    conversation_id=conversation_id,
                    project_id=project_id,
                    revision=next_revision,
                )
                self._records[(project_id, conversation_id)] = record
                self._persist(record)
                return True
            if record.revision != expected_revision:
                return False
            record.revision = next_revision
            record.updated_at = time.time()
            self._persist(record)
            return True

    # ── Reads ───────────────────────────────────────────────────────────

    def get(self, *, project_id: str, conversation_id: str) -> ConversationRecord | None:
        with self._lock:
            return self._ensure_loaded(project_id, conversation_id)

    def get_or_create(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int = 0,
    ) -> ConversationRecord:
        """Return existing record or create at revision 0 when expected is 0."""
        with self._lock:
            record = self._ensure_loaded(project_id, conversation_id)
            if record is not None:
                if record.revision != expected_revision:
                    raise StaleConversationRevisionError(
                        detail="Conversation revision does not match the authoritative store",
                        context={
                            "project_id": project_id,
                            "conversation_id": conversation_id,
                            "expected_revision": expected_revision,
                            "current_revision": record.revision,
                        },
                    )
                return record
            if expected_revision != 0:
                raise ConversationNotFoundError(
                    detail=f"Conversation not found: {conversation_id}",
                    context={
                        "project_id": project_id,
                        "conversation_id": conversation_id,
                        "expected_revision": expected_revision,
                    },
                )
            record = ConversationRecord(
                conversation_id=conversation_id,
                project_id=project_id,
                revision=0,
            )
            self._records[(project_id, conversation_id)] = record
            self._persist(record)
            return record

    def snapshot(self, *, project_id: str, conversation_id: str) -> ConversationSnapshot:
        with self._lock:
            record = self._ensure_loaded(project_id, conversation_id)
            if record is None:
                raise ConversationNotFoundError(
                    detail=f"Conversation not found: {conversation_id}",
                    context={"project_id": project_id, "conversation_id": conversation_id},
                )
            return record.snapshot()

    # ── Mutations (CAS) ─────────────────────────────────────────────────

    def append(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int,
        role: MessageRole,
        content: str,
        message_id: str | None = None,
        provenance: str = "append",
        create_if_missing: bool = True,
    ) -> ConversationSnapshot:
        """Append one turn under revision CAS. Returns new snapshot."""
        text = (content or "").strip()
        if not text:
            raise InvalidConversationRevisionError(
                detail="append content must not be blank",
                context={"conversation_id": conversation_id},
            )
        if expected_revision < 0:
            raise InvalidConversationRevisionError(
                detail="conversation_revision must be >= 0",
                context={"conversation_revision": expected_revision},
            )

        with self._lock:
            record = self._ensure_loaded(project_id, conversation_id)
            if record is None:
                if not create_if_missing or expected_revision != 0:
                    if expected_revision != 0:
                        raise StaleConversationRevisionError(
                            detail="Conversation does not exist at the expected revision",
                            context={
                                "project_id": project_id,
                                "conversation_id": conversation_id,
                                "expected_revision": expected_revision,
                                "current_revision": 0,
                            },
                        )
                    raise ConversationNotFoundError(
                        detail=f"Conversation not found: {conversation_id}",
                        context={
                            "project_id": project_id,
                            "conversation_id": conversation_id,
                            "expected_revision": expected_revision,
                        },
                    )
                record = ConversationRecord(
                    conversation_id=conversation_id,
                    project_id=project_id,
                    revision=0,
                )
                self._records[(project_id, conversation_id)] = record

            if record.revision != expected_revision:
                raise StaleConversationRevisionError(
                    detail="Conversation revision does not match the authoritative store",
                    context={
                        "project_id": project_id,
                        "conversation_id": conversation_id,
                        "expected_revision": expected_revision,
                        "current_revision": record.revision,
                    },
                )

            msg = ConversationMessage(
                id=message_id or _new_message_id(),
                role=role,
                content=text,
                created_at=time.time(),
                provenance=provenance,
            )
            record.messages.append(msg)
            record.revision = expected_revision + 1
            record.retained_message_ids = tuple(m.id for m in record.messages)
            record.updated_at = time.time()
            self._persist(record)
            return record.snapshot()

    def compact(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int,
        retain_tail: int = _DEFAULT_RETAIN_TAIL,
        summarize_fn=None,
    ) -> ConversationSnapshot:
        """Compact older messages into a summary under revision CAS.

        Returns snapshot with summary, retained_message_ids, and new revision.
        """
        if expected_revision < 0:
            raise InvalidConversationRevisionError(
                detail="conversation_revision must be >= 0",
                context={"conversation_revision": expected_revision},
            )
        retain_tail = max(0, int(retain_tail))

        with self._lock:
            record = self._ensure_loaded(project_id, conversation_id)
            if record is None:
                raise ConversationNotFoundError(
                    detail=f"Conversation not found: {conversation_id}",
                    context={
                        "project_id": project_id,
                        "conversation_id": conversation_id,
                        "expected_revision": expected_revision,
                    },
                )
            if record.revision != expected_revision:
                raise StaleConversationRevisionError(
                    detail="Conversation revision does not match the authoritative store",
                    context={
                        "project_id": project_id,
                        "conversation_id": conversation_id,
                        "expected_revision": expected_revision,
                        "current_revision": record.revision,
                    },
                )

            messages = list(record.messages)
            if len(messages) <= retain_tail:
                # Still bump revision so clients observe a CAS success and
                # receive an explicit snapshot (summary may stay None).
                record.revision = expected_revision + 1
                record.retained_message_ids = tuple(m.id for m in record.messages)
                record.updated_at = time.time()
                self._persist(record)
                return record.snapshot()

            old = messages[:-retain_tail] if retain_tail else messages
            retained = messages[-retain_tail:] if retain_tail else []
            old_as_dicts = [{"role": m.role, "content": m.content} for m in old]
            summary_text = summarize_messages(old_as_dicts, summarize_fn)
            if not summary_text:
                summary_text = f"[대화 요약 — {len(old)}개 메시지 압축]"

            summary_msg = ConversationMessage(
                id=_SUMMARY_MESSAGE_ID if not any(m.id == _SUMMARY_MESSAGE_ID for m in retained) else _new_message_id(),
                role="system",
                content=summary_text,
                created_at=time.time(),
                provenance="summary",
            )
            new_messages = [summary_msg, *retained]
            record.messages = new_messages
            record.summary = summary_text
            record.retained_message_ids = tuple(m.id for m in new_messages)
            record.revision = expected_revision + 1
            record.updated_at = time.time()
            self._persist(record)
            return record.snapshot()

    def fork(
        self,
        *,
        project_id: str,
        source_conversation_id: str,
        expected_revision: int | None = None,
        new_conversation_id: str | None = None,
    ) -> ConversationSnapshot:
        """Fork conversation at current (or expected) revision into a new id at revision 0."""
        with self._lock:
            source = self._ensure_loaded(project_id, source_conversation_id)
            if source is None:
                raise ConversationNotFoundError(
                    detail=f"Conversation not found: {source_conversation_id}",
                    context={
                        "project_id": project_id,
                        "conversation_id": source_conversation_id,
                    },
                )
            if expected_revision is not None and source.revision != expected_revision:
                raise StaleConversationRevisionError(
                    detail="Conversation revision does not match the authoritative store",
                    context={
                        "project_id": project_id,
                        "conversation_id": source_conversation_id,
                        "expected_revision": expected_revision,
                        "current_revision": source.revision,
                    },
                )
            new_id = new_conversation_id or _new_conversation_id()
            forked = ConversationRecord(
                conversation_id=new_id,
                project_id=project_id,
                revision=0,
                messages=[
                    ConversationMessage(
                        id=_new_message_id(),
                        role=m.role,
                        content=m.content,
                        created_at=time.time(),
                        provenance="fork",
                    )
                    for m in source.messages
                ],
                summary=source.summary,
                retained_message_ids=(),
                forked_from=source_conversation_id,
            )
            forked.retained_message_ids = tuple(m.id for m in forked.messages)
            self._records[(project_id, new_id)] = forked
            self._persist(forked)
            return forked.snapshot()

    def assemble_history_for_request(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int,
        new_turn: Mapping[str, Any] | None = None,
        create_if_missing: bool = True,
    ) -> tuple[list[dict[str, str]], ConversationSnapshot]:
        """Authoritative history for a chat request.

        Optionally CAS-appends ``new_turn`` first, then returns prompt messages
        + snapshot. Clients must not treat a client-side full array as SoT.
        """
        if new_turn is not None:
            role = str(new_turn.get("role") or "user")
            if role not in ("user", "assistant", "system", "tool"):
                role = "user"
            snap = self.append(
                project_id=project_id,
                conversation_id=conversation_id,
                expected_revision=expected_revision,
                role=role,  # type: ignore[arg-type]
                content=str(new_turn.get("content") or ""),
                create_if_missing=create_if_missing,
            )
        else:
            record = self.get_or_create(
                project_id=project_id,
                conversation_id=conversation_id,
                expected_revision=expected_revision,
            )
            snap = record.snapshot()

        record = self.get(project_id=project_id, conversation_id=conversation_id)
        assert record is not None
        return record.prompt_messages(), snap

    # ── Persistence ─────────────────────────────────────────────────────

    def _path_for(self, project_id: str, conversation_id: str) -> Path:
        safe_project = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id)[:64]
        safe_conv = "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)[:64]
        return self._storage_dir / safe_project / f"{safe_conv}.json"

    def _persist(self, record: ConversationRecord) -> None:
        path = self._path_for(record.project_id, record.conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        payload = json.dumps(record.to_dict(), ensure_ascii=False, indent=2)
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)

    def _load(self, project_id: str, conversation_id: str) -> ConversationRecord | None:
        path = self._path_for(project_id, conversation_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            record = ConversationRecord.from_dict(data)
            self._records[(project_id, conversation_id)] = record
            return record
        except Exception:
            logger.exception("Failed to load conversation %s/%s", project_id, conversation_id)
            return None

    def _ensure_loaded(self, project_id: str, conversation_id: str) -> ConversationRecord | None:
        key = (project_id, conversation_id)
        record = self._records.get(key)
        if record is not None:
            return record
        return self._load(project_id, conversation_id)

    def clear_memory(self) -> None:
        """Test helper: drop in-memory cache (disk files remain)."""
        with self._lock:
            self._records.clear()


_STORE: ConversationStore | None = None
_STORE_LOCK = threading.Lock()


def get_conversation_store() -> ConversationStore:
    """Process-wide authoritative conversation store singleton."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ConversationStore()
        return _STORE


def reset_conversation_store_for_tests(store: ConversationStore | None = None) -> ConversationStore:
    """Replace the singleton (tests only)."""
    global _STORE
    import tempfile

    with _STORE_LOCK:
        if store is not None:
            _STORE = store
        elif os.environ.get("AGK_CONVERSATION_STORE_DIR"):
            _STORE = ConversationStore(storage_dir=Path(os.environ["AGK_CONVERSATION_STORE_DIR"]) / "conversations")
        else:
            _STORE = ConversationStore(storage_dir=tempfile.mkdtemp(prefix="agk-conv-"))
        return _STORE


__all__ = [
    "ConversationMessage",
    "ConversationRecord",
    "ConversationStore",
    "get_conversation_store",
    "reset_conversation_store_for_tests",
]
