# WS-03 Independent Re-Review r2 (`ws_03_verify`)

- **Verdict: APPROVE**
- Reviewer: `ws_03_verify` (Owner≠Reviewer; no implementation commits)
- Tip reviewed: `d6713e7a327d24ff3f7d738effbc81c25087f966` (HEAD confirmed at review start)
- Fix SHA (Result): `bf00b1e2ef153a2c02205d920e327d3519f22e23`
- Prior REJECT tip: `b3e48344b8fd9ed27d8090ef8f4817285b6a27a2` (`review.md` preserved)
- Prior implement SHA: `4a03e3770f31b49697e0ff23c29e55227808822d`
- Branch/worktree: `codex/ws-03-project-lifecycle` · `/Users/mr.k/program/coding/ssak_comp/Ssak-Ai-ws-03`
- Reviewed at: 2026-09-06 10:45 KST (UTC+9)
- AdversarialVerify: **confirmed** (F1–F7 closed; residual global `get_vault_engine` noted non-blocking)
- Confidence: 0.93

## Re-run (reviewer, independent)

```
pytest tests/test_ws03_project_lifecycle.py -q
→ 15 passed

pytest tests/test_ws03_project_lifecycle.py tests/test_ws01_project_binding.py \
  tests/test_project_memory.py tests/test_engine_context_quality.py -q
→ 51 passed

pytest /tmp/ws03_verify_r2_adversarial.py -q
→ 9 passed (reviewer-owned probes)

ruff check <touched WS-03 files>
→ All checks passed!
```

Evidence: `tests-verify-r2.txt`, `tests-regression-verify-r2.txt`,
`adversarial-verify-r2.txt`, `ruff-verify-r2.txt`, `ws03_verify_r2_adversarial.py`.

## Must-verify matrix

| # | Criterion | Result | Notes |
|---|---|---|---|
| 1 | Runtime caches keyed by project_id, no field-patch | **PASS** | Registry + session/slash/job now on `ProjectRuntime`; no first-runtime freeze |
| 2 | memory/RAG/artifact/context persistence per project | **PASS** | Session base_dir under project; durable hooks close over root; factory wires RAGIndexer + project VaultEngine on orch |
| 3 | compressor caches project-keyed | **PASS** | Unchanged; still on project orchestrator |
| 4 | A→B→A zero cross-project data | **PASS** | Session secret isolation; slash/job distinct; durable clear A leaves B |
| 5 | restart/eviction isolation | **PASS** | Evict/LRU/shutdown still project-local |
| 6 | watcher/DB/handle cleanup | **PASS** | Orch shutdown + project-scoped durable/vector paths (no cwd wipe) |
| 7 | re-run tests | **PASS** | 15 + 51 + 9 adversarial |

## Prior blocking findings — closed

### F1 / F2 — Session DI + chat resume (CLOSED)

- `get_session_manager()` → `acquire_project_runtime(...).session_manager`
- Per-project `SessionManager(base_dir=<project>/.antigravity/sessions)`
- `chat.py` / `/api/session/*`: `start_session(project_path=canonical_root, resume=...)`
- Chat resolves via `resolve_project_execution_context(..., bind=True)` before session DI
- Adversarial: A secret `SECRET_FROM_PROJECT_A_ONLY_xyz_VERIFY_R2` not visible on B; A→B→A restores A; session ids distinct; sessions not under repo cwd

### F3 — Slash registry sticky runtime (CLOSED)

- `get_slash_registry()` returns `ProjectRuntime.slash_registry` (built per project)
- A/B registries distinct; each `_agent_runtime` matches that project's agent_runtime; A not overwritten after B

### F5 — Durable/vector cwd wipe (CLOSED)

- `_durable_memory_hooks(project_root)` closures; MemoryService/wiki/gbrain/vector/search_cache under `<project>/.antigravity/...`
- Clear A removes A's search cache; B cache + B RAG vector marker survive
- Extra: repo `vault_data` marker survives A clear (no `Path.cwd()` wipe)

### F6 — RAG overclaim (CLOSED for orchestrator claim)

- Factory `_attach_project_rag_indexer` sets real `RAGIndexer` (not None)
- Distinct per-project `VaultEngine` under `project_vault_dir`; orch.vault_engine matches `ProjectRuntime.vault_engine`
- Vectors under `project_rag_vector_dir`

### F7 — Scheduled jobs sticky runtime (CLOSED)

- `get_scheduled_job_service()` on `ProjectRuntime`; distinct A/B; `submit_agent` matches each project's `agent_runtime.submit_task`
- Job DB under project memory dir

## Residual (non-blocking for WS-03 DONE)

1. **Process-global `get_vault_engine()`** still used by `vault_api` / `vault_privacy` / `evolution_api` / `subagent_spawner` / one `system_api` path. Orchestrator/chat/RAG factory path is project-scoped; do **not** claim vault REST or subagent vault writes are project-isolated. Prefer RAG-01 / vault-API follow-up if those surfaces need project binding.
2. **`_legacy_session_manager()`** bootstrap fallback remains if `acquire_project_runtime` throws (CLI early boot only). Bound chat path does not rely on it.
3. **`GlobalMemoryProvider`** (`~/.antigravity-k/memory`) remains intentionally user-global (r1 non-blocking note stands).
4. Shared **`ModelManager`** OK for WS-03.
5. Browser dashboard switch E2E remains **WS-04**.

## Status

- **WS-03 → DONE.**
- Prior `review.md` REJECT remains intact as historical record.
- **WS-04 may start** from this lane (respect its own prerequisites: ARC-01, WS-01).
