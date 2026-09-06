"""Conversation revision CAS API (CTX-01).

Authoritative server store endpoints:
- GET  /v1/conversations/{id}           — snapshot + messages (refresh/reconnect)
- POST /v1/conversations/append         — CAS append new turn
- POST /v1/conversations/compact        — CAS compact; summary + retained IDs + revision
- POST /v1/conversations/fork           — fork at consistent revision
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from antigravity_k.api.contracts.conversation import (
    ConversationAppendRequest,
    ConversationCompactRequest,
    ConversationForkRequest,
    ConversationHistoryMessage,
    ConversationHistoryResponse,
)
from antigravity_k.api.contracts.errors import (
    ConversationNotFoundError,
    MissingExecutionContextError,
)
from antigravity_k.api.error_handler import correlation_id_var
from antigravity_k.api.project_binding import (
    SESSION_ID_HEADER,
    extract_project_id_from_payload,
    resolve_project_execution_context,
)
from antigravity_k.engine.conversation_store import get_conversation_store

logger = logging.getLogger("antigravity_k.api.conversation")

router = APIRouter()


def _resolve_project_id(request: Request, body: dict[str, Any] | None, explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    from_body = extract_project_id_from_payload(body)
    if from_body:
        return from_body
    # Fall through to session binding via resolve_project_execution_context.
    ctx = resolve_project_execution_context(
        payload=body,
        header_session_id=request.headers.get(SESSION_ID_HEADER),
        actor_subject=str(getattr(request.state, "auth_subject", None) or "anonymous"),
        model_id="default",
        correlation_id=correlation_id_var.get(""),
        require_existing_conversation=False,
        bind=False,
    )
    return ctx.project_id


def _history_response(project_id: str, conversation_id: str) -> ConversationHistoryResponse:
    store = get_conversation_store()
    record = store.get(project_id=project_id, conversation_id=conversation_id)
    if record is None:
        raise ConversationNotFoundError(
            detail=f"Conversation not found: {conversation_id}",
            context={"project_id": project_id, "conversation_id": conversation_id},
        )
    messages = tuple(
        ConversationHistoryMessage(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            provenance=m.provenance,
        )
        for m in record.messages
    )
    return ConversationHistoryResponse(
        snapshot=record.snapshot(),
        messages=messages,
        token_estimate=record.estimate_tokens(),
    )


@router.get("/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
    project_id = request.query_params.get("project_id")
    if not project_id:
        project_id = _resolve_project_id(request, None, None)
    return _history_response(project_id, conversation_id).model_dump(mode="json")


@router.post("/v1/conversations/append")
async def append_conversation(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise MissingExecutionContextError(detail="JSON object body required")
    req = ConversationAppendRequest.model_validate(body)
    project_id = _resolve_project_id(request, body, req.project_id)
    # Validate project exists via execution context (no conversation require).
    _ = resolve_project_execution_context(
        payload={
            **body,
            "project_id": project_id,
            "conversation_id": req.conversation_id,
            "conversation_revision": req.expected_revision,
        },
        header_session_id=request.headers.get(SESSION_ID_HEADER),
        actor_subject=str(getattr(request.state, "auth_subject", None) or "anonymous"),
        model_id="default",
        correlation_id=correlation_id_var.get(""),
        require_existing_conversation=False,
        bind=False,
    )
    store = get_conversation_store()
    snap = store.append(
        project_id=project_id,
        conversation_id=req.conversation_id,
        expected_revision=req.expected_revision,
        role=req.role,
        content=req.content,
    )
    return snap.model_dump(mode="json")


@router.post("/v1/conversations/compact")
@router.post("/compact")
async def compact_conversation(request: Request) -> dict[str, Any]:
    """CAS compact. Returns summary, retained_message_ids, and new revision."""
    body = await request.json()
    if not isinstance(body, dict):
        raise MissingExecutionContextError(detail="JSON object body required")
    req = ConversationCompactRequest.model_validate(body)
    project_id = _resolve_project_id(request, body, req.project_id)
    _ = resolve_project_execution_context(
        payload={
            **body,
            "project_id": project_id,
            "conversation_id": req.conversation_id,
            "conversation_revision": req.expected_revision,
        },
        header_session_id=request.headers.get(SESSION_ID_HEADER),
        actor_subject=str(getattr(request.state, "auth_subject", None) or "anonymous"),
        model_id="default",
        correlation_id=correlation_id_var.get(""),
        require_existing_conversation=False,
        bind=False,
    )
    store = get_conversation_store()
    before = store.get(project_id=project_id, conversation_id=req.conversation_id)
    tokens_before = before.estimate_tokens() if before else 0
    snap = store.compact(
        project_id=project_id,
        conversation_id=req.conversation_id,
        expected_revision=req.expected_revision,
        retain_tail=req.retain_tail,
    )
    after = store.get(project_id=project_id, conversation_id=req.conversation_id)
    tokens_after = after.estimate_tokens() if after else 0
    payload = snap.model_dump(mode="json")
    payload["tokens_before"] = tokens_before
    payload["tokens_after"] = tokens_after
    payload["tokens_reduced"] = max(0, tokens_before - tokens_after)
    return payload


@router.post("/v1/conversations/fork")
async def fork_conversation(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise MissingExecutionContextError(detail="JSON object body required")
    req = ConversationForkRequest.model_validate(body)
    project_id = _resolve_project_id(request, body, req.project_id)
    _ = resolve_project_execution_context(
        payload={
            **body,
            "project_id": project_id,
            "conversation_id": req.conversation_id,
            "conversation_revision": req.expected_revision or 0,
        },
        header_session_id=request.headers.get(SESSION_ID_HEADER),
        actor_subject=str(getattr(request.state, "auth_subject", None) or "anonymous"),
        model_id="default",
        correlation_id=correlation_id_var.get(""),
        require_existing_conversation=False,
        bind=False,
    )
    store = get_conversation_store()
    snap = store.fork(
        project_id=project_id,
        source_conversation_id=req.conversation_id,
        expected_revision=req.expected_revision,
        new_conversation_id=req.new_conversation_id,
    )
    return snap.model_dump(mode="json")


__all__ = ["router"]
