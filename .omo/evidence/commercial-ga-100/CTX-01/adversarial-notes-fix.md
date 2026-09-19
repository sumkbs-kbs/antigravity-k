# CTX-01 adversarial notes (owner fix probe; not APPROVE)

Date: 2026-09-06 Asia/Seoul
Owner: `ctx_01_conversation`

## F1 — PASS (owner)

- `_cmd_compact` no longer bare-except → session_manager success on CAS fail.
- `StaleConversationRevisionError` → conflict string; `shaped_calls==0`, `save==0`.
- Concurrent slash compact: exactly one authoritative success, one stale conflict.
- Bound-path other store errors return `❌ 압축 실패` without legacy mutate.

## F2 — PASS (owner)

- `_persist_assistant_to_conversation_store` re-raises `StaleConversationRevisionError`.
- Mid-stream compact race: assistant not in store; SSE emits `agk_conversation_conflict` with `current_revision`.
- Dashboard `emitChatFrame` throws `ConversationRevisionConflictError` → ChatPage 409 refresh UX.

## F3 — PASS (owner)

- Slash CAS uses `expected_revision=ctx.conversation_revision` always (not `before.revision`).
- Stale client expected (rev=0 while head advanced) → conflict; store unchanged.

## F4 — PASS (owner)

- `chat.py` gates `auto_restore` with `not _uses_conversation_revision_protocol(body)`.
- After compact + assemble, tokens_after < tokens_before; bait restore would inflate but protocol skips it.

## Residual / out of scope

- Non-agent native stream path still does not CAS-persist assistant (dashboard agent_mode path covered).
- Owner did **not** write APPROVE. CTX-02 not started.
