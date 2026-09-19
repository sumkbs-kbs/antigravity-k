# RP-05 attempt-002 debug journal

## Environment

- Runtime: CPython via the repository `uv run --no-sync` environment.
- Scope: `conversation_store.py`, the FR-05 regression test, directly necessary conversation tests, and this evidence directory.
- Concurrency surface: process-local `threading.RLock` acquired before the storage-wide `flock` in every authoritative operation.

## Hypotheses

1. A `ConversationRecord` returned by `get()` or `get_or_create()` aliases the private cached record. Caller mutation can therefore change later reads and CAS decisions without any persisted write.
   - Distinguishing evidence: mutate the returned revision/messages, then compare the same instance, a fresh instance, and persisted JSON.
2. `fork()` reads its source with `_ensure_loaded()` under only the thread lock. A worker that cached revision 1 can fork stale history after another worker persists revision 2.
   - Distinguishing evidence: populate source cache, append from another instance, then fork with expected revision 1; correct behavior is a stale conflict and no target file.
3. The attempt-001 refresh logic may otherwise satisfy stale get/revision/CAS and deterministic process races.
   - Distinguishing evidence: run the focused family and deterministic barrier scenarios without timing sleeps.

## Artifacts to clean or retain

- Disposable clean-HEAD worktree: `/tmp/ssak-rp05-clean-head` (remove after red proof).
- Evidence logs under this attempt directory: retain.
- Temporary process/storage roots created by pytest/manual QA: fixtures or driver clean them; verify absent after each run.

## Root cause (confirmed 2026-09-10)

- Mechanism: `get()` and `get_or_create()` returned the mutable record held in `_records`, so caller edits became private cache edits without persistence. `_refresh_latest()` then kept that mutated cache when disk revision was lower, corrupt payloads returned the cached record, and `fork()` bypassed both disk refresh and the process lock.
- Red proof: `red-focused.txt` records both return paths exposing revision 99, corrupt JSON returning revision 1, and stale fork failing to raise.
- Toggle proof: returning detached records, replacing cache from each valid disk read, invalidating cache on invalid disk state, and refreshing fork inside the process lock changes the same selection from four failures to four passes (`green-focused.txt`).
- Fix scope: `src/antigravity_k/engine/conversation_store.py` and behavioral coverage in `tests/test_fr05_conversation_authoritative_reads.py`.
