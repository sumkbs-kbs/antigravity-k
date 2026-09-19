# DAT-01 Independent Review — REJECT

| Field | Value |
|---|---|
| Reviewer | `dat_01_verify` (Owner≠Reviewer; no implementation commits) |
| Owner | `dat_01_persistence` |
| Verdict | **REJECT** |
| Tip reviewed | `c2b4adcd609d295ad983d91036d202ac3e756f21` (HEAD confirmed) |
| Impl / Result SHA | `a44e44bfc9f0375c7db439fe50f8a940cedee3ae` |
| Branch / worktree | `codex/dat-01-task-cas` / `Ssak-Ai-dat-01` |
| Reviewed at | 2026-09-06T13:20+09:00 |
| Confidence | 0.94 |

**DONE 금지.** Data lane DAT-01 **미완료**. **DAT-02 착수 금지** until `dat_01_verify` re-review **APPROVE**.

## Scope checked

Must-verify from commercial GA DAT-01:

1. Transitions use expected status/version CAS
2. affected 0 → typed conflict
3. cancel/completion race → single winner; loser cannot overwrite terminal
4. Stress/thread tests credible
5. UI projection won't show contradictory terminals
6. Re-run DAT-01 suites; adversarial concurrent cancel+complete probe

## What passes (keep)

- `TaskStateStore.transition` uses `BEGIN IMMEDIATE` + `UPDATE ... WHERE task_id=? AND status=? AND version=?`; version increments on success. ADR documents first-CAS-wins + terminal freeze.
- Stale `expected_version` / mismatched `expected_status` → `TaskTransitionConflictError` with current fields; status/output unchanged (`test_affected_zero_raises_typed_conflict`).
- Terminal freeze: done→done with new output / done→cancelled → `InvalidTaskTransitionError`; winner output/error sticky.
- Thread race (40×) and multiprocess cancel vs done + 4-way stress (done/cancelled/failed/done × 8 rounds) → exactly one win; loser payloads do not mix into winner fields.
- Python `resolve_display_terminal_status` prefers store terminal over contradictory later domain events.
- Callers: `task_runner._update_db_status` and `direct_task_execution._safe_task_transition` catch conflict/freeze and return False (lost-race safe for **store** mutation).
- Legacy DB migrates `version` column default 0.
- Reviewer re-run: pytest dat01+store+types → **31 passed** (`tests-verify.txt`); vitest `taskExecutionProjection.test.ts` → **5 passed** (`ui-vitest-verify.txt`).
- Reviewer adversarial probe 60× concurrent cancel+complete: wins done=46 cancelled=14; overwrite_failures=0; store projection OK (`adversarial-verify.txt`).

## Blocking findings

### F1 — Live UI never passes `authoritativeStatus` (must-verify #5) — BLOCKER

Clamp helper exists and unit-tested, but production view does not wire store SoT:

`dashboard/src/features/task-execution/TaskExecutionView.tsx:55`

```ts
const projection = selectedTaskId === null ? null : projectTaskExecution(selectedTaskId, events);
```

`tasks: TaskSummary[]` already carries authoritative `status`, yet it is unused for projection. Owner vitest itself proves the live default path is unsafe:

```ts
const without = projectTaskExecution(taskA, events);
expect(without.agents[0]?.status).toBe('completed'); // cancel CAS + late direct_completed

const withStore = projectTaskExecution(taskA, events, 'cancelled');
expect(withStore.agents[0]?.status).toBe('cancelled');
```

Plan criterion: UI must not display opposite terminals. Checklist item claiming UI projection order was verified is **false for the wired surface** (queue panel can show `cancelled` while execution blocks show `completed`).

### F2 — Lost-race callers still append contradictory terminal domain events — BLOCKER (feeds F1)

`direct_task_execution` ignores `_safe_task_transition` False and still appends `*_completed` / failed events. Examples (`run_max` success path; stream `else` completion path): transition then unconditional `append_execution_event(..._completed)`. After cancel wins CAS, completion loser can still write `direct_completed` / `max_execution_completed`, which `statusFor` maps to `completed` via substring `complete`. Combined with F1, UI shows contradictory terminals.

ADR note that domain events remain "caller-owned" does **not** satisfy the plan criterion that observation order prevents opposite terminals in UI.

## Non-blocking / residual

- N1: `statusFor('task.status')` returns `unknown` (payload `to_status` ignored). Even CAS-emitted `task.status` cancel does not set agent/checklist to cancelled without authoritative clamp.
- N2: Checklist/owner marked UI verification complete while manual QA deferred browser two-tab QA to reviewer — deferred QA is incomplete; F1 would have been caught by wiring review.
- N3: metadata tip_sha lagged HEAD at handoff (`00bae87` vs tip `c2b4adc`) — docs-only, non-blocking.

## Precise fixes required (re-review gate)

1. **Wire SoT into live projection**: In `TaskExecutionView` (and any other `projectTaskExecution` call sites), pass selected task store status, e.g. `projectTaskExecution(selectedTaskId, events, selectedTask?.status)`. Add a component/integration test that with `tasks=[{status:'cancelled'}]` + contradictory `direct_completed` events, projected agent/checklist statuses are `cancelled` (not `completed`).
2. **Gate domain terminal events on CAS success**: In `direct_task_execution` (and audit `task_runner` completion/cancel append paths), only append `*_completed` / competing terminal domain events when transition returns True; on False, re-read store and either skip or append an event matching the winner status (never opposite terminal). Add regression test: cancel wins → completion path must not leave a later `*_completed` event (or if present, UI+projection still display store terminal — prefer not present).
3. **Re-verify**: pytest DAT-01 suites + vitest projection + new view wiring test + adversarial cancel+complete probe; update evidence; request `dat_01_verify` re-review. Do **not** start DAT-02.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | expected status/version CAS | PASS |
| 2 | affected 0 → typed conflict | PASS |
| 3 | single winner; loser cannot overwrite terminal fields | PASS (store) |
| 4 | stress/thread tests credible | PASS |
| 5 | UI projection no contradictory terminals | **FAIL** (F1+F2) |
| 6 | reviewer re-run + adversarial probe | PASS suites; probe exposes F1/F2 |

## Verdict

**REJECT** — store CAS/terminal winner is solid; commercial GA observation/UI gate is not met. Confidence 0.94.
