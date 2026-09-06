# DAT-01 Independent Review r2 — APPROVE

| Field | Value |
|---|---|
| Reviewer | `dat_01_verify` (Owner≠Reviewer; no implementation commits) |
| Owner | `dat_01_persistence` |
| Verdict | **APPROVE** |
| Tip reviewed | `4368d8ead622f8d86a9551c0df3f7e03cfb7da31` (HEAD confirmed) |
| Fix / Result SHA | `5aed1a649ac572fb5789cce8da895576855f7aca` |
| Prior impl SHA | `a44e44bfc9f0375c7db439fe50f8a940cedee3ae` |
| Prior REJECT tip | `c2b4adcd609d295ad983d91036d202ac3e756f21` |
| Branch / worktree | `codex/dat-01-task-cas` / `Ssak-Ai-dat-01` |
| Reviewed at | 2026-09-06T13:43+09:00 |
| Confidence | 0.95 |

**DONE 허용.** Data lane DAT-01 **완료**. **DAT-02 착수 준비됨** (선행 DAT-01 DONE). 본 reviewer는 DAT-02를 시작하지 않음.

Prior r1 **REJECT** remains intact in `review.md`.

## Scope re-checked

Focus from re-review request + commercial GA must-verify:

1. `TaskExecutionView` passes `authoritativeStatus` from `selectedTask.status` — **F1**
2. CAS lose → no terminal domain event append — **F2**
3. cancel + late completed event → UI stays cancelled
4. Prior store CAS acceptance still holds; re-run suites + adversarial probe

## F1 closure (UI SoT wiring)

`TaskExecutionView.tsx` now resolves `selectedTask` and calls:

```ts
projectTaskExecution(selectedTaskId, events, selectedTask?.status);
```

Only live production call site of `projectTaskExecution` (tests aside). Vitest `TaskExecutionView.test.tsx` renders store `cancelled` + late `direct_completed` and asserts:

- queue button `상태 cancelled`
- ≥2× `취소됨` (agent/checklist)
- no `완료` / no `.task-execution-status-completed`

Clamp path in `projectTaskExecution` freezes contradictory event-derived terminals when authoritative store status is terminal (`done`→`completed`, `cancelled`, `failed`).

## F2 closure (CAS-gated domain terminals)

`direct_task_execution._append_terminal_domain_event(..., cas_won=)` returns early when transition returns False. Stream completion/failure/cancel and `run_max` success/failure paths all gate through it.

Regression tests:

- `test_direct_execution_skips_completed_event_when_cancel_wins_cas` — TOCTOU cancel-before-done; no `*_completed`
- `test_run_max_skips_completed_event_when_cancel_wins_cas` — no `max_execution_completed`

`task_runner` audited: completion/cancel use `_update_db_status`; on False they re-read store and **do not** append competing `*_completed` domain events (steering events only). Non-running end-of-stream branch may append winner-aligned `{type}_{status}` (e.g. `interactive_cancelled`) — never opposite terminal.

## Prior store CAS still holds

- `BEGIN IMMEDIATE` + `WHERE status=? AND version=?`; version increments
- affected 0 → `TaskTransitionConflictError`
- terminal freeze sticky; loser cannot overwrite output/error
- thread 40× + multiprocess stress unchanged and green under re-run

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | expected status/version CAS | **PASS** |
| 2 | affected 0 → typed conflict | **PASS** |
| 3 | single winner; loser cannot overwrite terminal fields | **PASS** (store) |
| 4 | stress/thread tests credible | **PASS** |
| 5 | UI projection no contradictory terminals | **PASS** — F1+F2 closed |
| 6 | reviewer re-run + adversarial probe | **PASS** |

## Independent re-runs (this review)

- pytest dat01+store+types: **33 passed** — `tests-verify-r2.txt`
- vitest projection + TaskExecutionView: **8 passed** — `ui-vitest-verify-r2.txt`
- Adversarial 60× cancel+complete: wins done=45 cancelled=15; overwrite_failures=0; F2 stream probes 20× completed_leaks=0 — `adversarial-verify-r2.txt`

## Residual (non-blocking; track after DONE)

- N1: `statusFor('task.status')` still `unknown` (payload `to_status` ignored). Mitigated by F1 authoritative clamp once store status is terminal; without clamp cancel ledger alone would not flip agent/checklist.
- Full browser two-tab cancel-while-complete interactive QA still deferred; F1 component + F2 TOCTOU close the observation gate for GA criterion #5.
- Brief tasks-list refresh lag after cancel: F2 prevents opposite `*_completed` append, so stale non-terminal `authoritativeStatus` cannot resurrect a contradictory completed projection from a lost-race event.

## Evidence

- `.omo/evidence/commercial-ga-100/DAT-01/review.md` (r1 REJECT preserved)
- `.omo/evidence/commercial-ga-100/DAT-01/review-r2.md` (this file)
- `tests-verify-r2.txt`, `ui-vitest-verify-r2.txt`, `adversarial-verify-r2.txt`
- Owner fix: `5aed1a6`, `tests-fix-f1f2.txt`, `ui-vitest-fix.txt`, `adversarial-notes-fix.md`

## Verdict

**APPROVE.** F1 live SoT wiring and F2 CAS-gated terminal domain events close the r1 blockers; store CAS/stress acceptance holds; suites and adversarial probes green. Mark DAT-01 **DONE**. Do not erase `review.md`. **DAT-02 not started in this turn.**
