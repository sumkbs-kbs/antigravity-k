"""Authoritative conversation history store with revision CAS (CTX-01).

Server-owned message history. Clients send new turns + expected revision only;
append/compact advance revision via compare-and-set. Two concurrent writers
never silently overwrite — losers get stale_conversation_revision (HTTP 409).

CR-01 identity contract:
- The storage key of a conversation is the full SHA-256 hex digest of the raw
  UTF-8 ``project_id`` / ``conversation_id`` strings (``v2/<sha(project)>/
  <sha(conversation)>.json``). Raw ids are never normalised, substituted, or
  truncated, so ``a.b`` and ``a_b`` — or ``Conv`` and ``conv`` on a
  case-insensitive filesystem — stay distinct conversations.
- Every read verifies that the embedded ids of the stored record exactly match
  the requested ids. Corrupt or mismatched bytes raise
  ``ConversationIntegrityError`` instead of degrading to an empty conversation.
- Until the one-time legacy migration has produced its completion marker
  (``migration_v2.json``), reads and writes fail with
  ``ConversationStorageMigrationRequiredError`` so new writes cannot fork the
  data set before it is verified.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, Mapping

from antigravity_k.api.contracts.conversation import ConversationSnapshot
from antigravity_k.api.contracts.errors import (
    ConversationIntegrityError,
    ConversationNotFoundError,
    ConversationStorageMigrationRequiredError,
    InvalidConversationRevisionError,
    StaleConversationRevisionError,
)
from antigravity_k.engine.context_summary import summarize_messages
from antigravity_k.engine.tokenizer import TokenEstimator

logger = logging.getLogger("antigravity_k.engine.conversation_store")

MessageRole = Literal["user", "assistant", "system", "tool"]

_DEFAULT_RETAIN_TAIL: Final[int] = 6
# EX-05 / Decision A: bound in-memory (and on-disk rewritten) history so long
# chats cannot grow RSS without bound. 0 disables auto-compact.
_DEFAULT_SOFT_MAX_MESSAGES: Final[int] = 64
_SUMMARY_MESSAGE_ID: Final[str] = "msg_summary"


def _soft_max_messages() -> int:
    """Return soft max message count (0 = disable auto-compact on append)."""
    raw = os.environ.get("AGK_CONVERSATION_SOFT_MAX_MESSAGES")
    if raw is None or raw.strip() == "":
        return _DEFAULT_SOFT_MAX_MESSAGES
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_SOFT_MAX_MESSAGES


# CR-01: versioned identity layout + one-time migration marker.
_IDENTITY_SCHEMA_VERSION: Final[str] = "v2"
MIGRATION_MARKER_NAME: Final[str] = "migration_v2.json"
_IGNORED_STORAGE_ENTRIES: Final[frozenset[str]] = frozenset({MIGRATION_MARKER_NAME, ".cas.lock", ".DS_Store"})


def conversation_identity_digest(value: str) -> str:
    """Return the full SHA-256 hex digest of a raw UTF-8 identifier."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def conversation_storage_relative_path(project_id: str, conversation_id: str) -> Path:
    """Return the storage-relative CR-01 v2 path for raw ids.

    ``v2/<sha256(project_id)>/<sha256(conversation_id)>.json``. The digest is
    the key; the raw ids are re-verified from the record body on every read.
    """
    return (
        Path(_IDENTITY_SCHEMA_VERSION)
        / conversation_identity_digest(project_id)
        / f"{conversation_identity_digest(conversation_id)}.json"
    )


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
            storage_dir = os.environ.get("AGK_CONVERSATION_STORE_DIR") or os.path.join(
                os.path.expanduser("~"), ".antigravity", "conversations"
            )
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        # VAL-02: 다중 프로세스 writer 간 원자성 — 프로세스 공유 flock(CTX-01 계약
        # "두 동시 writer는 침묵 중 덮어쓰지 않는다"를 프로세스 경계에서도 유지).
        # 단일 프로세스 스레드 경쟁은 기존 threading.RLock으로 충분하다.
        self._flock_path = self._storage_dir / ".cas.lock"
        self._flock_fd: int | None = None
        # CR-01: legacy layout detection is memoised per process; the operator
        # runs the migration with the service stopped.
        self._layout_checked = False
        self._legacy_paths: tuple[Path, ...] = ()

    # ── CR-01 identity / migration state ────────────────────────────────

    def migration_marker_path(self) -> Path:
        """Path of the one-time migration completion marker."""
        return self._storage_dir / MIGRATION_MARKER_NAME

    def migration_completed(self) -> bool:
        """True when a valid completion marker exists for the v2 layout."""
        marker = self.migration_marker_path()
        if not marker.is_file():
            return False
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return (
            isinstance(data, dict) and data.get("layout") == _IDENTITY_SCHEMA_VERSION and data.get("completed") is True
        )

    def legacy_storage_paths(self) -> tuple[Path, ...]:
        """Return pre-v2 record files still present under the storage root.

        Path names are never used to reconstruct ids; callers must read the
        record body for the authoritative ids. Migration tooling consumes this.
        """
        if not self._storage_dir.is_dir():
            return ()
        found: list[Path] = []
        for entry in sorted(self._storage_dir.iterdir()):
            name = entry.name
            if name in _IGNORED_STORAGE_ENTRIES or name.startswith("."):
                continue
            if entry.is_dir():
                if name == _IDENTITY_SCHEMA_VERSION:
                    continue
                found.extend(sorted(p for p in entry.rglob("*.json") if p.is_file()))
            elif entry.is_file() and entry.suffix == ".json":
                found.append(entry)
        return tuple(found)

    def storage_layout_state(self) -> str:
        """Return ``v2`` or ``legacy_requires_migration`` for this storage root."""
        if not self._layout_checked:
            self._legacy_paths = self.legacy_storage_paths()
            self._layout_checked = True
        if not self._legacy_paths:
            return _IDENTITY_SCHEMA_VERSION
        return _IDENTITY_SCHEMA_VERSION if self.migration_completed() else "legacy_requires_migration"

    def refresh_storage_layout(self) -> str:
        """Drop the memoised layout scan (tests / post-migration reload)."""
        self._layout_checked = False
        self._legacy_paths = ()
        return self.storage_layout_state()

    def _assert_storage_ready(self) -> None:
        """Fail closed while unmigrated legacy records exist."""
        if self.storage_layout_state() == "legacy_requires_migration":
            raise ConversationStorageMigrationRequiredError(
                detail=(
                    "Legacy conversation files require the one-time v2 migration before reads or writes are served"
                ),
                context={
                    "storage_dir": str(self._storage_dir),
                    "legacy_record_count": len(self._legacy_paths),
                    "marker_path": str(self.migration_marker_path()),
                    "migration_script": "scripts/migrate_conversation_storage.py",
                },
            )

    # ── ConversationRevisionStore protocol ──────────────────────────────

    @contextmanager
    def _cross_process_lock(self) -> Generator[None, None, None]:
        """프로세스 간 CAS 원자성을 위한 flock (스레드 락은 self._lock이 담당)."""
        import fcntl

        self._flock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self._flock_path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _refresh_latest(self, project_id: str, conversation_id: str) -> ConversationRecord | None:
        """FR-05/RP-05: 캐시를 디스크 진실 원천과 동기화한 뒤 반환한다.

        ``self._lock``과 ``_cross_process_lock``을 이미 보유한 상태에서만
        호출한다. 파일이 삭제됐으면 캐시도 무효화한다(삭제된 대화를 되살리지
        않는다).

        CR-01: 손상된 JSON이나 다른 식별자의 레코드는 조용히 None/빈 대화로
        낮추지 않고 ``ConversationIntegrityError``로 전파한다.
        """
        key = (project_id, conversation_id)
        disk_record = self._read_record(project_id, conversation_id)
        if disk_record is None:
            self._records.pop(key, None)
            return None
        self._records[key] = disk_record
        return disk_record

    def _read_record(self, project_id: str, conversation_id: str) -> ConversationRecord | None:
        """Read one record and verify its embedded identity against the request.

        Returns None only when no file exists for this identity. Any other
        failure (unreadable bytes, invalid JSON, id mismatch) raises
        ``ConversationIntegrityError``.
        """
        path = self._path_for(project_id, conversation_id)
        if not path.is_file():
            return None
        context: dict[str, Any] = {
            "project_id": project_id,
            "conversation_id": conversation_id,
            "storage_path": str(path),
        }
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConversationIntegrityError(
                detail="Conversation record could not be read from storage",
                context={**context, "reason": type(exc).__name__},
            ) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConversationIntegrityError(
                detail="Conversation record is not valid JSON",
                context={**context, "reason": "json_decode"},
            ) from exc
        if not isinstance(data, dict):
            raise ConversationIntegrityError(
                detail="Conversation record must contain a JSON object",
                context={**context, "reason": "not_an_object"},
            )
        record = ConversationRecord.from_dict(data)
        if record.project_id != project_id or record.conversation_id != conversation_id:
            raise ConversationIntegrityError(
                detail="Conversation record ids do not match the requested identity",
                context={
                    **context,
                    "reason": "identity_mismatch",
                    "record_project_id": record.project_id,
                    "record_conversation_id": record.conversation_id,
                },
            )
        return record

    def get_revision(self, *, project_id: str, conversation_id: str) -> int | None:
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
            return None if record is None else record.revision

    def compare_and_set(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int,
        next_revision: int,
    ) -> bool:
        """Bare revision CAS (no message mutation). Prefer append/compact.

        FR-05/RP-05: CAS 평가와 persist가 프로세스 간 critical section
        안에서 디스크 최신 상태를 대상으로 이뤄진다.
        """
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
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
        # FR-05/RP-05: 모든 공개 읽기는 프로세스 간 lock 아래 디스크 최신
        # 상태로 갱신한다(다른 worker의 append/compact을 즉시 관찰).
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
            return None if record is None else deepcopy(record)

    def get_or_create(
        self,
        *,
        project_id: str,
        conversation_id: str,
        expected_revision: int = 0,
    ) -> ConversationRecord:
        """Return existing record or create at revision 0 when expected is 0.

        FR-05/RP-05: 최신 revision 비교와 신규 persist가 같은 프로세스 간
        critical section 안에서 이뤄진다.
        """
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
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
                return deepcopy(record)
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
            return deepcopy(record)

    def snapshot(self, *, project_id: str, conversation_id: str) -> ConversationSnapshot:
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
            if record is None:
                raise ConversationNotFoundError(
                    detail=f"Conversation not found: {conversation_id}",
                    context={"project_id": project_id, "conversation_id": conversation_id},
                )
            return record.snapshot()

    def _inline_compact_messages(
        self,
        record: ConversationRecord,
        *,
        retain_tail: int = _DEFAULT_RETAIN_TAIL,
        summarize_fn=None,
    ) -> None:
        """Replace older messages with a summary in-place (no revision bump).

        Caller must already hold locks and have advanced revision for the
        triggering mutation. Used by append soft-max bounding (Decision A).
        """
        retain_tail = max(0, int(retain_tail))
        messages = list(record.messages)
        if len(messages) <= retain_tail:
            record.retained_message_ids = tuple(m.id for m in record.messages)
            return
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

        # VAL-02: 다른 프로세스의 append와 경쟁할 수 있으므로 flock 안에서
        # 디스크 최신 상태를 재적재한 뒤 CAS를 평가한다 (stale 메모리 캐시로
        # 인한 침묵 덮어쓰기 방지).
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
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
            soft_max = _soft_max_messages()
            if soft_max > 0 and len(record.messages) > soft_max:
                # Decision A (EX-05): bound RSS for long conversations without an
                # extra client-visible revision bump beyond this append.
                self._inline_compact_messages(record, retain_tail=_DEFAULT_RETAIN_TAIL)
                try:
                    from antigravity_k.engine.operational_metrics import record_compaction

                    record_compaction("success")
                except Exception:  # noqa: BLE001 — metrics must not fail append
                    pass
            else:
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
        # OBS-01: 압축 시도 결과를 운영 metric에 기록 (record/persist 실패 제외).
        from antigravity_k.engine.operational_metrics import record_compaction

        if expected_revision < 0:
            raise InvalidConversationRevisionError(
                detail="conversation_revision must be >= 0",
                context={"conversation_revision": expected_revision},
            )
        retain_tail = max(0, int(retain_tail))

        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            record = self._refresh_latest(project_id, conversation_id)
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
                record_compaction("success")
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
            record_compaction("success")
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
        with self._lock, self._cross_process_lock():
            self._assert_storage_ready()
            source = self._refresh_latest(project_id, source_conversation_id)
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

        current = self.get(project_id=project_id, conversation_id=conversation_id)
        assert current is not None
        return current.prompt_messages(), snap

    # ── Persistence ─────────────────────────────────────────────────────

    def _path_for(self, project_id: str, conversation_id: str) -> Path:
        """CR-01 v2 identity path (full SHA-256 of the raw UTF-8 ids).

        Character substitution / truncation is gone: distinct raw ids always
        produce distinct paths, including on case-insensitive filesystems.
        """
        return self._storage_dir / conversation_storage_relative_path(project_id, conversation_id)

    def _persist(self, record: ConversationRecord) -> None:
        path = self._path_for(record.project_id, record.conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # VAL-02 수정: 결정론적 tmp 파일명(<conv>.tmp)은 동시 writer가 서로의 tmp를
        # 삭제/치환해 FileNotFoundError로 유실을 만든다. 프로세스 고유 tmp + os.replace
        # 로 원자성과 임시파일 격리를 동시에 보장한다.
        tmp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
        payload = json.dumps(record.to_dict(), ensure_ascii=False, indent=2)
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)

    def _load(self, project_id: str, conversation_id: str) -> ConversationRecord | None:
        record = self._read_record(project_id, conversation_id)
        if record is None:
            return None
        self._records[(project_id, conversation_id)] = record
        return record

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


_store_singleton: ConversationStore | None = None
_store_lock = threading.Lock()


def get_conversation_store() -> ConversationStore:
    """Process-wide authoritative conversation store singleton."""
    global _store_singleton
    with _store_lock:
        if _store_singleton is None:
            _store_singleton = ConversationStore()
        return _store_singleton


def reset_conversation_store_for_tests(store: ConversationStore | None = None) -> ConversationStore:
    """Replace the singleton (tests only)."""
    global _store_singleton
    import tempfile

    with _store_lock:
        if store is not None:
            _store_singleton = store
        elif os.environ.get("AGK_CONVERSATION_STORE_DIR"):
            _store_singleton = ConversationStore(storage_dir=Path(os.environ["AGK_CONVERSATION_STORE_DIR"]))
        else:
            _store_singleton = ConversationStore(storage_dir=tempfile.mkdtemp(prefix="agk-conv-"))
        return _store_singleton


__all__ = [
    "ConversationMessage",
    "ConversationRecord",
    "ConversationStore",
    "MIGRATION_MARKER_NAME",
    "conversation_identity_digest",
    "conversation_storage_relative_path",
    "get_conversation_store",
    "reset_conversation_store_for_tests",
]
