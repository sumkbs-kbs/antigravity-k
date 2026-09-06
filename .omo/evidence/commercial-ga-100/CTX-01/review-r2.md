# CTX-01 Independent Re-Review r2 (`ctx_01_verify`)

| Field | Value |
|---|---|
| Reviewer | `ctx_01_verify` (Owner≠Reviewer; no implementation commits) |
| Owner | `ctx_01_conversation` |
| Verdict | **APPROVE** |
| Tip reviewed | `b92622e9fdc752f6e1a162d14a5a64e97acb7c33` (HEAD confirmed) |
| Fix / Result SHA | `8ba8337dbc953d3ac4788541adcf8294f809e9c6` |
| Prior REJECT | `review.md` preserved (tip `54fc8f0…` / impl `81c9578…`) |
| Branch / worktree | `codex/ctx-01-conversation-revision` / `Ssak-Ai-ctx-01` |
| Reviewed at | 2026-09-06T11:58+09:00 |
| Confidence | 0.94 |

**CTX-01 → DONE.** Prior `review.md` REJECT remains intact. **CTX-02 not started** by this reviewer; CTX-02 may proceed after coordinator handoff (prerequisite CTX-01 DONE).

## Independent re-run

```
pytest CTX+ARC/WS related + F1–F4 → 66 passed
vitest related (3 files) → 32 passed
adversarial dual-SoT + mid-stream probes → ALL PASS
```

Evidence: `tests-verify-r2-pytest.txt`, `vitest-verify-r2.txt`, `adversarial-verify-r2.txt`.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | Server store authoritative | **PASS** — HTTP/store OK; slash bound path CAS-only (no legacy success on CAS/store fail) |
| 2 | Client new turn + expected revision | **PASS** |
| 3 | append/compact CAS; stale → 409/conflict | **PASS** — HTTP/store + slash client expected |
| 4 | `/compact` summary/retained/new revision | **PASS** |
| 5 | Next request tokens decrease | **PASS** — store/API `<`; auto_restore gated on protocol |
| 6 | Two-tab race, no silent overwrite | **PASS** — slash concurrent one winner; assistant stale → typed SSE conflict |
| 7 | refresh/reconnect/fork consistency | **PASS** |
| 8 | Reviewer re-run tests | **PASS** — pytest 66; vitest 32 |

## Prior blocking findings — closed

### F1 — slash `/compact` dual-SoT fallback — **CLOSED**
Bound path: `StaleConversationRevisionError` → explicit conflict; other store errors → `❌ 압축 실패 (authoritative store)`; **no** `session_manager` shape/save success fallback. Legacy shaper only when `ctx is None` (unbound). Concurrent slash: exactly one authoritative success.

### F2 — assistant persist soft-swallow — **CLOSED**
`_persist_assistant_to_conversation_store` re-raises stale. Agent stream yields `agk_conversation_conflict` SSE and returns without success `agk_conversation`. Client throws `ConversationRevisionConflictError`; ChatPage refreshes from store.

### F3 — slash ignored client expected — **CLOSED**
`expected_revision=ctx.conversation_revision` always. Stale client expected conflicts; store head unchanged.

### F4 — `auto_restore` re-inflate — **CLOSED**
Gated: `len(messages) <= 4 and not _uses_conversation_revision_protocol(body)`. Assemble runs first; tokens remain reduced after compact on protocol path.

## Non-blocking residuals

- `session_manager.add_turn` still precedes assistant CAS; on conflict the client refreshes from authoritative store (session projection may briefly diverge).
- Non-agent native stream path still does not CAS-persist assistant (dashboard `agent_mode` path covered).
- `tools` early-return still skips `_apply_authoritative_conversation` (prior note).
- `applyServerSnapshot` keeps local messages if server returns an empty array (edge).

## Verdict

**APPROVE.** F1–F4 closed under adversarial dual-SoT and mid-stream compact probes. Mark CTX-01 **DONE**. Do not erase `review.md`. **CTX-02 not started in this turn.**
