"""Conversation identity and revision CAS protocol (ARC-01).

Authoritative store behavior is implemented by CTX-01. This module freezes the
wire types WS/CTX lanes share: expected revision on write, conflict payload on
409, and snapshot shape after append/compact.
"""

from __future__ import annotations

from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONVERSATION_REVISION_MIN: Final[int] = 0


class ConversationRef(BaseModel):
    """Immutable conversation pointer carried on every mutating request."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    conversation_revision: int = Field(ge=CONVERSATION_REVISION_MIN)


class ConversationAppendRequest(BaseModel):
    """Client write: new turn content plus the revision the client last observed."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=CONVERSATION_REVISION_MIN)
    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str = Field(min_length=1, max_length=512_000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("content must not be blank")
        return text


class ConversationSnapshot(BaseModel):
    """Authoritative conversation head returned after a successful CAS write."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=CONVERSATION_REVISION_MIN)
    message_count: int = Field(ge=0)
    summary: str | None = None
    retained_message_ids: tuple[str, ...] = ()


class ConversationConflictPayload(BaseModel):
    """409 body when expected_revision does not match the store."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[False] = False
    error: Literal["stale_conversation_revision"] = "stale_conversation_revision"
    detail: str = "Conversation revision does not match the authoritative store"
    conversation_id: str
    expected_revision: int = Field(ge=CONVERSATION_REVISION_MIN)
    current_revision: int = Field(ge=CONVERSATION_REVISION_MIN)
    correlation_id: str = ""


__all__ = [
    "CONVERSATION_REVISION_MIN",
    "ConversationAppendRequest",
    "ConversationConflictPayload",
    "ConversationRef",
    "ConversationSnapshot",
]
