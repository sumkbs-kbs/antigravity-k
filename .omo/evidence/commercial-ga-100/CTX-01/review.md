# CTX-01 Independent Review — REJECT

| Field | Value |
|---|---|
| Reviewer | `ctx_01_verify` |
| Owner | `ctx_01_conversation` |
| Verdict | **REJECT** |
| Tip reviewed | `54fc8f088ae64d8bb736eb8b7b6afaf652a84395` (HEAD confirmed) |
| Impl / Result SHA | `81c957805ab92599ff842b39e1ac124bf842ae43` |
| Branch / worktree | `codex/ctx-01-conversation-revision` / `Ssak-Ai-ctx-01` |
| Reviewed at | 2026-09-06T11:41+09:00 |
| Confidence | 0.93 |

**DONE 금지.** CTX-02 착수 금지 until `ctx_01_verify` re-review **APPROVE**.

## Scope checked

Must-verify from commercial GA CTX-01:

1. Server conversation store is authoritative
2. Client sends new turn + expected revision (not full array as SoT)
3. append/compact CAS; stale → typed 409
4. `/compact` returns summary / retained IDs / new revision
5. Next request tokens decrease after compact (test evidence)
6. Two-tab race: no silent overwrite
7. refresh/reconnect/fork revision consistency
8. Re-run CTX-01 + related tests (reviewer)

## What passes (keep)

- `ConversationStore` thread-safe append/compact/fork with revision CAS; disk persist + reconnect load matches revision.
- HTTP `GET/append/compact/fork` (+ `/compact` alias); stale append → **409** `stale_conversation_revision` with `current_revision`.
- Compact payload includes `summary`, `retained_message_ids`, new `revision`, plus `tokens_before` / `tokens_after` / `tokens_reduced`.
- Chat protocol path: `_apply_authoritative_conversation` replaces client array with store + `new_turn` when protocol on.
- Dashboard: `ChatPage` sends `new_turn` + `conversation_id` + `conversation_revision` (messages not full SoT); mount `fetchConversationHistory` + `applyServerSnapshot`; 409 → refresh + user-facing conflict.
- Store unit tests: two-thread race exactly one conflict; `tokens_after < tokens_before`; fork at rev 0 + stale fork 409.
- Reviewer re-run: pytest CTX-01 + ARC/WS related **39 passed**; vitest related **14 passed** (3 files).

## Blocking findings

### F1 — slash `/compact` falls back to non-authoritative session mutation on CAS failure — BLOCKER (must-verify #1, #3, #6)

`slash_commands_session._cmd_compact` wraps the store path in bare `except Exception` and **falls through** to `context_shaper.shape(session_manager.get_messages())` + `session_manager.save()`.

If `store.compact` raises `StaleConversationRevisionError` (two-tab race), the slash command still reports a successful compact against **session_manager**, leaving `ConversationStore` unchanged. That is a second SoT write path — violates “server conversation store is authoritative” and “압축 결과를 같은 저장소에 원자적으로 반영”.

Evidence: `adversarial-verify.txt` F1; source has no `StaleConversationRevisionError` special-case before fallback.

### F2 — assistant persist soft-swallows stale revision (mid-stream compact race) — BLOCKER (must-verify #6)

`_persist_assistant_to_conversation_store` catches **all** exceptions (including `StaleConversationRevisionError`), logs, and returns the pre-assistant snapshot. Stream still completes with SSE `agk_conversation` at the user-append revision; client keeps assistant text locally; authoritative store never gets the assistant turn.

Adversarial probe: user append → concurrent compact → assistant append with stale expected → conflict; `store_has_assistant=False`. Owner residual note #5 confirmed **blocking** for commercial GA (silent loss / client–server divergence after “successful” stream — not an explicit conflict to the streaming tab).

### F3 — slash compact ignores client `expected_revision` when record exists — BLOCKER (must-verify #3, #6)

```python
expected_revision=ctx.conversation_revision if before is None else before.revision
```

Always CAS against current store head when the conversation exists. Stale client revision never yields 409 on the slash path; weakens two-tab conflict semantics for a surface owned by CTX-01.

### F4 — `auto_restore` can re-inflate chat prompt after compact — RELATED BLOCKER for criterion #5 on live chat path

After authoritative assemble, `chat.py` still runs `session_manager.auto_restore()` when `len(messages) <= 4`. Compact with small `retain_tail` yields ≤4 messages → old system context re-inserted → undermines “다음 chat request의 history token이 실제 감소”. Store `assemble_history_for_request` unit tests remain green and do not cover this injection.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | Server store authoritative | **FAIL** — HTTP/store OK; slash fallback + dual session_manager writes |
| 2 | Client new turn + expected revision | **PASS** |
| 3 | append/compact CAS; stale → 409 | **PARTIAL** — HTTP/store PASS; slash F1/F3 fail |
| 4 | `/compact` summary/retained/new revision | **PASS** (HTTP) |
| 5 | Next request tokens decrease | **PARTIAL** — store/API tests PASS; live chat path F4 risk |
| 6 | Two-tab race, no silent overwrite | **FAIL** — append race OK; F2 soft-fail loss; F1 alternate SoT |
| 7 | refresh/reconnect/fork consistency | **PASS** |
| 8 | Reviewer re-run tests | **PASS** — pytest 39; vitest 14 |

## Precise fixes required (owner)

1. **Slash compact: no legacy success fallback on store CAS failure**
   - On `StaleConversationRevisionError` / store errors: return explicit conflict/error text to the user; **do not** mutate `session_manager` as a success path.
   - Prefer calling HTTP-equivalent store.compact with `expected_revision=ctx.conversation_revision` (client expected), not `before.revision`.
   - After successful store compact only, sync session projection from store (one-way store → session).
   - Test: concurrent slash compact → exactly one success; loser gets conflict string; store unchanged for loser; session_manager not shaped on loser.

2. **Assistant persist must surface stale conflict**
   - Do not swallow `StaleConversationRevisionError` in `_persist_assistant_to_conversation_store`.
   - Emit typed SSE error / conflict frame (or fail the stream trailer) with `current_revision`; client already has 409 refresh UX — reuse it.
   - Optional: retry once after re-read only if product policy allows; never pretend success without assistant CAS.
   - Test: mid-stream compact race → assistant not silently dropped without client conflict signal; store either has assistant under new CAS or client gets explicit stale.

3. **Gate `auto_restore` when revision protocol is on**
   - Skip `session_manager.auto_restore()` injection when `_uses_conversation_revision_protocol(body)` (or when store assembled history).
   - Add regression: compact → next chat assemble tokens still `<` before even with session_manager holding large prior context.

4. **Evidence / checklist**
   - Uncheck failed CTX-01 checklist lines until re-review.
   - Re-submit with new Result SHA; do not self-APPROVE; do not start CTX-02.

## Non-blocking notes

- API compact assertion `tokens_after <= tokens_before` is weaker than plan “실제 감소”; store tests use strict `<` — tighten API test on re-submit.
- `tools` early-return in `chat.py` still skips `_apply_authoritative_conversation` — out of primary dashboard agent_mode path; track if tools clients adopt revision protocol.
- `conv_unspecified` skip of store assert is acceptable legacy gate (owner note).

## Verdict

**REJECT.** Core store + HTTP CAS + dashboard `new_turn` protocol are real progress, but slash compact fallback / expected-revision bypass and soft-fail assistant persist violate authoritative-store and two-tab conflict completion criteria. Fix + re-review before DONE; **CTX-02 not started**.
