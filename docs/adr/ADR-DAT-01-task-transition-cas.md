# ADR-DAT-01 · Task transition CAS and terminal observation order

## Status
Proposed (DAT-01 REVIEW)

## Context
Cancel and completion can race while a task is `running`. A non-conditional
UPDATE allowed both writers to succeed and overwrite terminal reason/output.
UI event projection could then show contradictory terminals.

## Decision
1. `task_history.version` starts at 0 and increments on every successful transition.
2. `TaskStateStore.transition` performs `BEGIN IMMEDIATE` +
   `UPDATE ... WHERE task_id=? AND status=? AND version=?`.
3. Affected row 0 raises `TaskTransitionConflictError` (typed conflict).
4. Terminal statuses (`done`/`failed`/`cancelled`) freeze fields: first CAS winner
   wins; further mutations raise `InvalidTaskTransitionError`.
5. Priority among cancel / completion / timeout(failed) / crash-recovery while
   racing from the same expected status+version is **first successful CAS wins**
   (no special ordering). Crash recovery exits terminals only via `prepare_resume`
   CAS from failed/paused with dead `owner_pid`.
6. Observation order: **store status is authoritative**. UI may pass
   `authoritativeStatus` into `projectTaskExecution` to clamp contradictory
   event-derived terminals. Optional `record_event=True` appends `task.status`
   in the same write transaction as the CAS winner.

## Consequences
- Callers treat conflict / terminal freeze as lost race (false / catch).
- Domain completion events remain caller-owned; DAT-01 does not rewrite every
  event stream by default (`record_event=False`).
