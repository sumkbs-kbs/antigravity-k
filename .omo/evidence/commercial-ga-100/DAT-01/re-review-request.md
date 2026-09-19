# DAT-01 re-review request (`dat_01_persistence` → `dat_01_verify`)

**Status:** ready for independent re-review (owner did **not** write APPROVE)
**Date:** 2026-09-06 (Asia/Seoul)

## Prior verdict

- `review.md` — **REJECT** by `dat_01_verify` (left intact; do not erase)
- Blocking **F1**: `TaskExecutionView` never passed `authoritativeStatus` into `projectTaskExecution`
- Blocking **F2**: `direct_task_execution` appended `*_completed` / failed terminals even when CAS lost

## Fix submitted

| Item | Value |
|---|---|
| Branch / worktree | `codex/dat-01-task-cas` / `Ssak-Ai-dat-01` |
| Owner | `dat_01_persistence` |
| Prior impl SHA | `a44e44bfc9f0375c7db439fe50f8a940cedee3ae` |
| Prior REJECT tip | `c2b4adcd609d295ad983d91036d202ac3e756f21` (review commit `ea4cfd5` preserved) |
| Fix SHA (result) | `5aed1a649ac572fb5789cce8da895576855f7aca` |

### What changed

1. **F1 UI SoT wiring:** `TaskExecutionView` resolves `selectedTask` and calls `projectTaskExecution(id, events, selectedTask?.status)`.
2. **F1 regression:** vitest proves cancel store status + late `direct_completed` keeps agent/checklist `취소됨` (not `완료`).
3. **F2 CAS-gated domain events:** `_append_terminal_domain_event` only appends competing terminal domain events when `_safe_task_transition` returns True (stream + `run_max` paths).
4. **F2 regression:** TOCTOU cancel-before-done probes assert no `interactive_completed` / `max_execution_completed`.
5. ADR consequences updated; `task_runner` audited (no competing `*_completed` append after lost CAS).

### Owner re-runs (not a substitute for independent review)

- pytest dat01+store+types: **33 passed** — `tests-fix-f1f2.txt`
- vitest projection + TaskExecutionView: **8 passed** — `ui-vitest-fix.txt`
- ruff touched Python: All checks passed — `ruff-fix.txt`
- Owner adversarial F1/F2 probe — `adversarial-notes-fix.md`, `adversarial-verify-owner-fix.txt`

## Ask

Please re-run must-verify #1–#6 with focus on #5 (UI projection / live wiring) and F2 event gating. Write a new review artifact (e.g. `review-r2.md`) — do **not** erase prior REJECT in `review.md`. Do **not** start DAT-02. Owner will not self-APPROVE.
