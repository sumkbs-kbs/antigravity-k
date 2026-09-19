# CTX-01 re-review request (`ctx_01_conversation` → `ctx_01_verify`)

**Status:** ready for independent re-review (owner did **not** write APPROVE)
**Date:** 2026-09-06 (Asia/Seoul)

## Prior verdict

- `review.md` — **REJECT** by `ctx_01_verify` (left intact; do not erase)
- Blocking F1: slash `_cmd_compact` bare-except → session_manager mutate on CAS fail (dual SoT)
- Blocking F2: assistant persist soft-swallows mid-stream compact race (silent loss)
- Blocking F3: slash uses `before.revision` not client `expected_revision`
- Blocking F4: `auto_restore`(≤4) re-inflates tokens after compact when protocol on

## Fix submitted

| Item | Value |
|---|---|
| Branch / worktree | `codex/ctx-01-conversation-revision` / `Ssak-Ai-ctx-01` |
| Fix SHA (result) | `8ba8337dbc953d3ac4788541adcf8294f809e9c6` |
| Prior impl SHA | `81c957805ab92599ff842b39e1ac124bf842ae43` |
| Prior REJECT tip | `6cf353a7f730eeb3f917ce08b19cc2ef5435c5cd` (review.md tip was `54fc8f0…`) |

### What changed

1. **F1 slash compact:** on `StaleConversationRevisionError` / bound-path store errors → explicit conflict/error text; **no** session_manager shape/save success fallback. Session projection synced only after successful store CAS.
2. **F2 assistant persist:** re-raise stale; stream yields `agk_conversation_conflict` SSE; client `emitChatFrame` throws `ConversationRevisionConflictError` (reuses 409 refresh UX). No success `agk_conversation` at pre-assistant revision.
3. **F3 slash expected:** `expected_revision=ctx.conversation_revision` always (client expected).
4. **F4 auto_restore:** skipped when `_uses_conversation_revision_protocol(body)`.
5. Regressions: `tests/test_ctx01_reject_fixes.py` (F1–F4); vitest mid-stream conflict; API compact assert tightened to `tokens_after < tokens_before`.

### Owner re-runs (not a substitute for independent review)

- pytest CTX+ARC/WS related + F1–F4: **66 passed** — `tests-fix-f1f4-pytest.txt`
- vitest related: see `vitest-fix.txt`
- Owner adversarial: `adversarial-notes-fix.md` — F1–F4 PASS (owner)

## Ask

Please re-run must-verify #1–#8 and adversarial slash/assistant/auto_restore probes independently. Write a new review artifact (e.g. `review-r2.md`) — do **not** erase prior REJECT in `review.md`. Do **not** start CTX-02 from this handoff. Owner will not self-APPROVE.
