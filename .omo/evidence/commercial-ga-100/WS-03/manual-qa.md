# WS-03 Manual QA

Owner: `ws_03_runtime`
Date: 2026-09-06 (KST)

## Surface checks (code-level / API DI)

1. Bound `RequestExecutionContext` for project A then B:
   - `get_orchestrator()` returns distinct instances with matching `project_id` / roots.
2. Project memory sync on A then B then A:
   - A recall has only A decisions; B only B; A instance identity preserved.
3. `context_compressor_for("model-x")` on A vs B:
   - Distinct objects; persistence_dir under each project root.
4. Evict A while B live:
   - watchdog.stop / vector_store.close invoked for A; B orchestrator identity kept;
     A recreated fresh on next acquire.
5. Factory init failure for B:
   - A runtime untouched; B not inserted into registry.

Automated coverage: `tests/test_ws03_project_lifecycle.py` (10 passed).

## Not claimed

- Full browser dashboard project-switch E2E (WS-04 ownership).
- CTX-01 conversation revision CAS.
