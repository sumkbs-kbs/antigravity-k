# ADR-DAT-02 · Conversation history journal vs bounded prompt view

## Status
Proposed (NX-02 REVIEW) — 2026-09-16

## Context

`ConversationStore` keeps exactly one durable copy of a conversation and uses it
for three different jobs:

1. the history sent to the model (`ConversationRecord.prompt_messages`),
2. the history returned to the client (`GET /v1/conversations/{id}` returns
   `record.messages` — `api/routes/conversation_api.py:62-82`),
3. fork source (`fork()` copies `source.messages`).

EX-05 / Decision A bounded that copy in place: `_inline_compact_messages` (append
soft-max 64) and `compact()` replace older messages with one `role=system`
summary plus a retained tail. The originals are therefore destroyed in the only
durable copy, and every projection inherits the loss:

- the client sees the compacted window as "history" (same endpoint),
- `engine/slash_commands_session.py:311-315` writes `after.prompt_messages()`
  back into the session-manager record and saves it, so a second durable store
  is overwritten with the bounded view too,
- forks made after a compaction cannot recover pre-compaction turns.

Measured workload says this cannot be fixed by keeping everything in one
rewritten JSON: the 8h re-soak appended 12,102,886 turns to one conversation
(`docs/qa/2026-09-16-followup/nx00/independent-parse.txt`). A single-file record
would be rewritten in full on every append (O(n) write amplification per turn)
and read back in full into RSS, contradicting the bounded-RSS decision that
motivated the compaction in the first place.

There is currently no conversation delete or export surface at all
(`conversation_api.py` exposes GET/append/compact/fork only;
`ConversationStore.clear_memory()` drops the in-memory cache only), so
"retention applies to originals and view together" has no implementation yet.

Constraints that must survive: file-first/Git-first (no new database), the
existing v2 identity layout `v2/<sha(project)>/<sha(conversation)>.json`, the
per-conversation flock plus revision CAS, and "one logical append = exactly one
published revision".

## Decision

1. **Journal-first storage.** The original history becomes an append-only
   journal `v2/<sha(project)>/<sha(conversation)>.jsonl` (JSON Lines). The
   existing `<sha(conversation)>.json` file stays as the **materialized view**:
   the bounded prompt view, summary text and structured memory (NX-01
   `memory`). Journal records carry `schema`, `conversation_id`, `message_id`,
   `revision`, `event_type` (`append|compact|fork|delete`), role/content,
   `created_at`, `provenance`.
2. **Commit point is the journal, not the view.** One mutation = append the
   record line + `fsync`, then refresh the view. Only events whose journal line
   is durably committed may appear in the view. If the view refresh fails, the
   journal stays authoritative and the view is rebuilt from it (replay must be
   duplicate- and gap-free; the view carries `journal_seq` and is rebuilt when it
   lags the journal tail).
3. **Revision stays the client contract.** `revision` = number of committed
   journal events; the CAS check reads the journal tail under the existing
   flock. Append still bumps the revision exactly once and inline compaction
   still bumps nothing.
4. **Read surfaces are split.** The existing view endpoint keeps its response
   shape (compatibility) and gains a marker that the payload is a bounded view;
   a separate paged **original history** read plus an export path read the
   journal. `record.messages` is never treated as the original history again.
5. **Missing originals are declared, not invented.** Records migrated from the
   pre-journal layout that only have a summary/tail are exposed as
   `history_incomplete` (with the first/last known ids); summaries are never
   re-expanded into fake originals.
6. **Corruption and interruption are explicit.** A truncated final line (no
   trailing newline / invalid JSON) is an uncommitted tail: dropped from the
   view, reported, and the file is not silently rewritten past it. A corrupt
   middle line is a hard error with the line offset and a quarantine copy — it
   is never skipped (`_quarantine_session_file`-style, never deleted).
7. **Deletion/retention apply to journal + view together**, under the same
   per-conversation lock, with the deletion recorded as a journal `delete`
   event so replay cannot resurrect the data. Post-delete export/history reads
   return nothing. Documentation must not claim that Git history or backups of
   the data are deleted too.
8. **Retention/quota defaults are decided before the journal is enabled**
   (explicit byte/age limits and a user-visible notice when a prune happens);
   silent pruning is not allowed. Until those defaults exist the journal is
   written but never pruned automatically.
   **Decided 2026-09-16 (owner):** explicit byte caps, **no automatic prune at
   all** — soft cap 64 MiB per conversation logs a warning (visible, once per
   conversation), hard cap 512 MiB refuses the append with 507
   `conversation_history_quota_exceeded` and never deletes anything; both are
   env-overridable (`AGK_CONVERSATION_JOURNAL_{SOFT,HARD}_CAP_MB`, `0` disables)
   and `ConversationStore.store_usage()` reports the largest journals for
   operator reclamation. Rationale and evidence:
   `docs/qa/2026-09-16-followup/nx02/retention-decision.md`.
9. **Migration mirrors `scripts/migrate_conversation_storage.py`**: dry-run
   report, immutable backup + SHA256, idempotent re-run, resume after
   interruption, `history_incomplete` marking, and a completion marker.
10. **No downgrade without a verified backfill.** An older binary that ignores
    the journal must not be pointed at a journal-backed store automatically
    (same reasoning as NX-01/NX-03 rollback rules).

## Consequences

- Originals survive compaction, so user-visible history, export and recovery are
  no longer bounded by the prompt window; prompt cost stays bounded by the view.
- Two files per conversation must be kept consistent; the view is explicitly
  derived and rebuildable, so a lost view is a performance event, not data loss.
- Disk usage now tracks total turns instead of the bounded window — the
  retention/quota decision (item 8) becomes a release blocker for long-running
  deployments, and must be reported in user-facing docs.
- `GET /v1/conversations/{id}` consumers (dashboard, `rp05` workers, tests) keep
  working on the view; new original-history reads need their own pagination and
  authorization path.
- Dashboards/tests that assume "messages == everything" must be revisited in
  NX-09 (product flows) and NX-10 (candidate gate).
- Verification required before this can move past REVIEW: 1,000+ message exact
  id/order round-trip, view bound, idempotent migration, crash injection at each
  write step, disk-full/permission failure, two-process race, delete-then-export
  returning nothing, truncated tail and corrupt middle record handling.
