# WS-03 re-review request (`ws_03_runtime` → `ws_03_verify`)

**Status:** ready for independent re-review (owner did **not** write APPROVE)
**Date:** 2026-09-06 (Asia/Seoul)

## Prior verdict

- `review.md` — **REJECT** by `ws_03_verify` (left intact)
- Blocking F1/F2: chat/session DI used process-global `get_session_manager()` +
  `start_session(resume=True)` without `project_path` → A→B secret leak via cwd
- Blocking F3: `get_slash_registry()` froze first `agent_runtime`
- Blocking F5: durable clear/vector hooks were process-global / `Path.cwd()`
- Blocking F6: RAG overclaim — `_rag_indexer is None`, shared `VaultEngine`
- Related F7: `get_scheduled_job_service()` froze first agent_runtime

## Fix submitted

| Item | Value |
|---|---|
| Branch / worktree | `codex/ws-03-project-lifecycle` / `Ssak-Ai-ws-03` |
| Fix SHA (result) | *(filled after commit)* |
| Prior impl SHA | `4a03e3770f31b49697e0ff23c29e55227808822d` |
| Prior REJECT tip | `b3e48344b8fd9ed27d8090ef8f4817285b6a27a2` |

### What changed

1. **Session DI (F1/F2):** `get_session_manager()` → `acquire_project_runtime().session_manager`;
   per-project `SessionManager(base_dir=<project>/.antigravity/sessions)`;
   `chat.py` / `/api/session/*` call `start_session(project_path=canonical_root, resume=...)`.
2. **Slash registry (F3):** `get_slash_registry()` returns `ProjectRuntime.slash_registry`
   built per project (no process singleton freeze).
3. **Durable/vector (F5):** `_durable_memory_hooks(project_root)` closures; MemoryService /
   wiki / gbrain / vector / search_cache paths under `<project_root>/.antigravity/...`.
4. **RAG honesty (F6):** `_build_project_runtime` attaches real `RAGIndexer` + project-scoped
   `VaultEngine` under project root (no shared process vault on orchestrator).
5. **Jobs (F7):** `get_scheduled_job_service()` is project-scoped on `ProjectRuntime`.
6. Adversarial tests in `tests/test_ws03_project_lifecycle.py` for F1–F3/F5–F7.

### Owner re-runs (not a substitute for independent review)

- WS-03: **15 passed** `tests/test_ws03_project_lifecycle.py`
- Regression: **51 passed** (ws03 + ws01 + project_memory + engine_context_quality)
- Ruff: clean on touched files
- Owner adversarial probes: `adversarial-verify-owner.txt` — F1–F7 PASS

## Ask

Please re-run must-verify #1–#7 and adversarial A→B session/slash/durable/RAG isolation
independently. Write a new review artifact (e.g. `review-r2.md`) — do **not** erase prior
REJECT in `review.md`. Do **not** start WS-04 until APPROVE.
