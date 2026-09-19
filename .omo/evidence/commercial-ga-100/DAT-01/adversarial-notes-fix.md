# DAT-01 adversarial notes (owner F1/F2 fix probe)

Date: 2026-09-06 (Asia/Seoul)
Owner: `dat_01_persistence`

## F1 — live wiring
- `TaskExecutionView` now resolves `selectedTask` from `tasks` and passes
  `selectedTask?.status` as third arg to `projectTaskExecution`.
- Vitest `TaskExecutionView.test.tsx`: store `cancelled` + late `direct_completed`
  → agent/checklist show `취소됨`; no `완료` / `.task-execution-status-completed`.

## F2 — CAS-gated domain terminals
- `_append_terminal_domain_event(..., cas_won=)` skips append when transition False.
- TOCTOU probe: cancel wins immediately before `done` transition in stream + `run_max`
  → store stays `cancelled`; no `interactive_completed` / `max_execution_completed`.

## Prior store probes (still green)
- Stale version conflict, terminal freeze, thread/process stress unchanged (33 pytest).
