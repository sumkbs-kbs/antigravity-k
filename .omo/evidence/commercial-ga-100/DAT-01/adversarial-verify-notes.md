# DAT-01 adversarial verify (dat_01_verify)

Date: 2026-09-06 Asia/Seoul

## Concurrent cancel+complete (60 rounds, threads)
- wins: done=46, cancelled=14
- overwrite_failures after lose: 0
- store resolve_display_terminal_status vs late direct_completed: OK (store wins)

## Live wiring audit
- TaskExecutionView: `projectTaskExecution(selectedTaskId, events)` — NO authoritativeStatus (**FAIL**)
- direct_task_execution: ~2 done→append_completed windows without gating on transition success (**FAIL**)

## Suites
- pytest dat01+store+types: 31 passed (tests-verify.txt)
- vitest taskExecutionProjection: 5 passed (ui-vitest-verify.txt) — includes proof that without store arg UI shows completed after cancel+direct_completed
