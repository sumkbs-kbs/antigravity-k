# CTX-01 Manual QA (owner)

Date: 2026-09-06 (Asia/Seoul)

## Surfaces exercised
1. ConversationStore unit CAS (append/compact/fork/race) — automated
2. HTTP `/v1/conversations/append|compact|fork|GET` — automated TestClient
3. Dashboard chatStore revision projection — vitest
4. ChatPage payload shape: `new_turn` + `conversation_id` + `conversation_revision` (code review)

## Checks
- [x] Server store authoritative; client new turn + expected revision
- [x] append/compact CAS; two-tab race → one conflict, no silent overwrite
- [x] compact response includes summary / retained IDs / new revision
- [x] tokens_after < tokens_before after compact (store + API)
- [x] refresh path: GET conversation + applyServerSnapshot on mount
- [x] fork starts at revision 0 with copied messages; stale fork → 409

## Notes
Full browser two-tab interactive QA deferred to independent reviewer (`ctx_01_verify`).
