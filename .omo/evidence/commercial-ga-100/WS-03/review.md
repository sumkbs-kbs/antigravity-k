# WS-03 Independent Review — REJECT

| Field | Value |
|---|---|
| Reviewer | `ws_03_verify` |
| Owner | `ws_03_runtime` |
| Verdict | **REJECT** |
| Tip reviewed | `b3e48344b8fd9ed27d8090ef8f4817285b6a27a2` (HEAD confirmed) |
| Impl / Result SHA | `4a03e3770f31b49697e0ff23c29e55227808822d` |
| Branch / worktree | `codex/ws-03-project-lifecycle` / `Ssak-Ai-ws-03` |
| Reviewed at | 2026-09-06T10:28+09:00 |
| Confidence | 0.93 |

**DONE 금지. WS-04 이 lane 착수 금지** until fix + independent re-review APPROVE.

## Scope checked

Must-verify from commercial GA WS-03:

1. Orchestrator/runtime caches keyed by `project_id` (no field-patch on switch)
2. memory/RAG/artifact/context persistence per project
3. compressor caches project-keyed
4. A→B→A no cross-project data (adversarial)
5. Restart/eviction isolation
6. Cleanup of watchers/DB/handles
7. Re-run WS-03 tests + relevant regressions

## What passes (keep)

- `ProjectRuntimeRegistry` keys orchestrator + MemoryManager + SessionManager + agent_runtime by `project_id`; root change replaces (no field-patch); concurrent create prefers first; init failure does not insert.
- `get_orchestrator()` / `get_memory_manager()` / `get_agent_runtime()` resolve via `acquire_project_runtime`.
- ProjectMemory + episodic dirs under project root; A→B→A project-memory isolation in unit tests.
- ArtifactEngine rooted per orchestrator `project_root`.
- `context_compressor_for` caches live on project orchestrator; `persistence_dir` under each project root.
- Evict/LRU/shutdown stop AmbientWatchdog, clear compressor caches; `DELETE /api/projects/{id}` calls `evict_project_runtime`.
- Official suite re-run by reviewer: **46 passed** (`test_ws03` 10 + ws01 + project_memory + engine_context_quality). See `tests-verify-rerun.txt`.

## Blocking findings

### F1 / F2 — Session/context DI not project-scoped (must-verify #2, #4) — BLOCKER

`ProjectRuntime.session_manager` is per-`project_id`, but API chat still uses process-global `_get_session_manager()`:

- `api/dependencies.py`: `get_session_manager` → singleton `_session_manager`
- `api/routes/chat.py`: `start_session(resume=True)` **without** `project_path` → `SessionManager` defaults to `os.getcwd()`
- System session routes (`/api/session/*`) same singleton

**Adversarial:** bind A, write turn `SECRET_FROM_PROJECT_A_ONLY_xyz` on global SM, bind B, `start_session(resume=True)` → **same session id + A secret visible**. Evidence: `adversarial-verify.txt` F1/F1c/F2.

Checklist claim “context persistence가 project별” is **false** on the chat surface.

### F3 — `get_slash_registry()` freezes first `agent_runtime` (must-verify #1, #4) — BLOCKER

`dependencies.get_slash_registry()` is a process singleton constructed with `agent_runtime=get_agent_runtime()` at first call. After A→B, registry object is unchanged and still points at **A’s** runtime while `get_agent_runtime()` returns B. Chat slash path uses this singleton.

### F5 — Durable memory clear/export hooks are global / cwd (must-verify #2, #6) — BLOCKER

Every project MemoryManager attaches the same `_durable_memory_hooks()` callables. `clear(scope=all)` on project A clears process-global MemoryService / wiki / gbrain / search_cache and `Path.cwd()/.antigravity/vault_data` (`_clear_project_vector`), not A’s root. Cross-project wipe + wrong vector path.

### F6 — RAG isolation overclaimed (must-verify #2, #4) — BLOCKER

Owner/checklist claim RAG is project-keyed via orchestrator. Production factory leaves `_rag_indexer is None`. All orchestrators share one `get_vault_engine()` / `VaultEngine.vector_store`. Unit test only assigns RAGIndexer manually — does not prove production isolation.

### F7 — `get_scheduled_job_service()` binds first agent_runtime (residual / related)

Process singleton; first `get_agent_runtime()` baked in. Treat as fix-with-F3 unless deferred with explicit residual + SEC/DAT owner — **do not leave silent**.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | Runtime caches keyed by project_id, no field-patch | **PARTIAL** — orch/MM/registry OK; slash/job/session DI still singletons |
| 2 | memory/RAG/artifact/context persistence per project | **FAIL** — project memory/artifact/compressor OK; session/context + RAG + durable hooks FAIL |
| 3 | compressor caches project-keyed | **PASS** |
| 4 | A→B→A zero cross-project data | **FAIL** — session secret leak; slash runtime sticky |
| 5 | restart/eviction isolation | **PASS** (registry/disk project-memory path) |
| 6 | watcher/DB/handle cleanup | **PARTIAL** — orch shutdown OK; durable/vector cwd hooks not project-clean |
| 7 | re-run tests | **PASS** official 46; **FAIL** adversarial coverage gap |

## Precise fixes required (owner)

1. **Session DI wiring**
   - `get_session_manager()` must return `acquire_project_runtime(...).session_manager` when a bound `RequestExecutionContext` / explicit `project_id` exists (same resolution order as orchestrator).
   - `chat.py` (and `/api/session/*`): `start_session(project_path=execution_context.canonical_project_root, resume=...)` — never bare cwd when a project is bound.
   - Add adversarial test: A writes session secret → switch B → B session must not contain A secret; A→B→A restores only A.

2. **Slash / job runtime rebinding**
   - `get_slash_registry()` must not freeze first `agent_runtime`. Either (a) build per-project registry on the ProjectRuntime, or (b) re-`bind_runtime` / refresh session+runtime from `acquire_project_runtime()` on every request.
   - Same for `get_scheduled_job_service()` submit target (or document deferral only with test proving jobs carry project_id — prefer fix).

3. **Durable / vector hooks project-scoped**
   - Stop attaching process-global clear/export that mutate shared stores from a project MemoryManager `clear("all")`, **or** namespace MemoryService/wiki/gbrain/vector paths by `project_id`/`project_root`.
   - `_clear_project_vector` / export / redact must use the **project root**, not `Path.cwd()`.
   - Test: clear A does not delete B’s project-scoped durable/vector data.

4. **RAG honesty + isolation**
   - Either attach a real per-project `RAGIndexer` (vector persist under project root) in `_build_project_runtime` / orchestrator init and prove A/B indexes do not mix, **or** remove RAG from WS-03 DONE claims and open an explicit RAG-01 follow-up — **do not claim green**.
   - Stop counting manually injected `_rag_indexer` as proof.

5. **Evidence / checklist**
   - Uncheck failed checklist lines until re-review.
   - Extend `tests/test_ws03_project_lifecycle.py` (or chat-level tests) for F1–F3/F5; keep eviction/compressor tests.

## Non-blocking notes

- `GlobalMemoryProvider` default `~/.antigravity-k/memory` is intentionally user-global (identity/preferences). Acceptable as residual **if** project decisions stay in ProjectMemory/episodic only; do not route project facts there.
- Shared `ModelManager` is OK for WS-03.
- Browser dashboard switch E2E remains WS-04.

## Verdict

**REJECT.** Core registry work is directionally correct, but chat/session/slash/durable/RAG surfaces still violate project-scoped lifecycle and A→B→A isolation. Re-submit after fixes with new Result SHA; reviewer `ws_03_verify` re-runs adversarial probes.
