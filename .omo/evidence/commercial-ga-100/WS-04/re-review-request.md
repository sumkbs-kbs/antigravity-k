# WS-04 re-review request (`ws_04_frontend` → `ws_04_verify`)

**Status:** ready for independent re-review (owner did **not** write APPROVE)
**Date:** 2026-09-06 (Asia/Seoul)

## Prior verdict

- `review.md` — **REJECT** by `ws_04_verify` (left intact)
- Blocking F1: fileStore no switchEpoch/abort → stale B list merges into C UI
- Blocking F2: editor openFiles + changeStore + tree not cleared on switch
- Blocking F3: `editorStore.saveFile` + ChatPage `/api/fs/read` miss project identity
- Blocking F4: mobile e2e soft-passes when `project_id` missing

## Fix submitted

| Item | Value |
|---|---|
| Branch / worktree | `codex/ws-04-dashboard-project` / `Ssak-Ai-ws-04` |
| Fix SHA (result) | `313c6447dda5cf17537024facba2b78868bbe467` |
| dashboard_dist tip (incl.) | `0b0dad26481389cfede074a22ccd62719eaa3286` |
| Prior impl SHA | `1ca4ae6d37e98dd4f9a1eb884e69fa83ed64a920` |
| Prior REJECT tip | `dd37329165294c1cd6198fd875a530b6f9f52ae6` (review.md tip was `7bac16d…`; docs tip at REJECT handoff `dd37329`) |

### What changed

1. **fileStore epoch/abort (F1):** capture `switchEpoch` in `refreshTree`/`getWorkspace`; AbortController for in-flight list/workspace; abort+clear on `agk:project-switched`; `set` only if `isIdentityCurrent`.
2. **Clear selection on switch (F2):** `editorStore.clearForProjectSwitch`; ChatPage switch effect clears editor + `changeStore.clearChanges` + `fileStore.clearForProjectSwitch`.
3. **Identity on file surfaces (F3):** `saveFile` uses `createProjectIdentityHeaders` + `withProjectIdentityPayload`; ChatPage fs/read uses identity helpers + epoch gate; other raw `/api/fs/read|write|search` call sites aligned.
4. **Mobile e2e hard-fail (F4):** remove soft `if (chatPayload?.project_id)`; real B→C sidebar switch; always assert label↔`project_id` (+ revision).
5. Vitest regressions for F1–F3; suite **86 passed** (6 files).

### Owner re-runs (not a substitute for independent review)

- Vitest related: **86 passed** — `tests.txt`
- Owner adversarial probes: `adversarial-verify-owner.txt` — F1–F4 PASS (owner)
- `vite build` → dashboard_dist tip `0b0dad2`

## Ask

Please re-run must-verify #1–#7 and adversarial file-isolation probes independently. Write a new review artifact (e.g. `review-r2.md`) — do **not** erase prior REJECT in `review.md`. Do **not** start CTX-01 from this handoff.
