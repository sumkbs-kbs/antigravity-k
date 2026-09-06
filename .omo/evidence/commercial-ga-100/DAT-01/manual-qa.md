# DAT-01 Manual QA (owner)

Date: 2026-09-06 (Asia/Seoul)

## Surfaces exercised
1. TaskStateStore CAS unit tests (version, conflict, terminal freeze)
2. Thread race cancel vs done (40 repeats)
3. Multiprocess race + 4-way stress (spawn)
4. Projection helper `resolve_display_terminal_status` + dashboard clamp vitest
5. Code review of task_runner cancel/complete paths + direct_task_execution safe transition
6. **F1 fix:** TaskExecutionView authoritativeStatus wiring + view regression vitest
7. **F2 fix:** CAS-gated terminal domain events in direct_task_execution + TOCTOU pytest

## Checks
- [x] expected status/version conditional update
- [x] affected 0 → typed TaskTransitionConflictError
- [x] cancel/completion exactly one winner; loser cannot overwrite reason/output
- [x] thread/process stress repeated pass
- [x] state/event projection order defined (store SoT; UI authoritativeStatus clamp)
- [x] Live UI wires store status into projection (F1 closed in owner tests)
- [x] Lost-race completion does not append opposite `*_completed` (F2 closed)
- [ ] Full browser two-tab cancel-while-complete interactive QA deferred to independent reviewer (`dat_01_verify`)

## Notes
Pre-existing `test_agent_runtime` chat route failures (MissingExecutionContextError / Request.state) reproduce on CTX-03 tip unchanged — out of DAT-01 scope.
Prior `review.md` REJECT preserved. Owner did **not** self-APPROVE.
