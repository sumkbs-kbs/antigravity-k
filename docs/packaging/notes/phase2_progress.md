# Phase 2 progress — Desktop shell UX scaffold

**Date:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Status:** IN_PROGRESS (tray Settings/logs/status + QA checklist; Host spawn/stop still deferred)  
**Decision:** D-01 = A (Electron); path = `desktop/` (see plan §5 / D-06)

## What landed

Thin Electron package at repo `desktop/`:

| Path | Role |
|---|---|
| `desktop/package.json` | `electron` as **devDependency**; scripts `start`/`dev` |
| `desktop/main.js` | Main process: single-instance, window, tray, hide-on-close, Settings/logs |
| `desktop/assets/tray.png` | Tray icon (from `dashboard/public/icon-180.png`) |
| `desktop/README.md` | How to run + constraints |
| `desktop/.gitignore` | `node_modules/`, build outs |
| `docs/packaging/notes/phase2_shell_qa.md` | Manual QA checklist (Pass/Fail blank) |

## Host assumption (important)

**This turn does NOT spawn or stop Host.**

- Shell loads `SSAK_HOST_URL` or default `http://127.0.0.1:8000`.
- Soft HTTP probe: if Host unreachable, warning dialog → Continue / Quit.
- Tray status label: **Host ready** / **Host unreachable** from the same soft probe; quiet refresh every 120s (no spam).
- Quit exits the **shell only**; Host (and soak on `:8000`) are left alone (C-03).
- Start Host separately, e.g. `uv run agk serve --host 127.0.0.1 --port 8000`.

Do **not** point shell spawn at soak workdirs; do not kill pids `29961`/`29969`.

## Tray (this slice)

| Item | Behavior |
|---|---|
| Open | Show/focus BrowserWindow |
| Settings | Show window + `loadURL` → `{HOST}/settings` (dashboard `App.tsx` route) |
| Open in Browser | `shell.openExternal(HOST_URL)` |
| Open logs folder | `~/Library/Logs/Ssak-Ai` on macOS (MACOS_DMG_GUIDE); create if missing; else `~/.antigravity-k/logs` |
| Status label | Disabled menu row from soft probe |
| Quit | Shell only — Host stop **deferred** |

Thin shell: still **no** preload / Electron API into the page.

## Install note

- `pnpm --dir desktop install` may skip Electron postinstall (`ERR_PNPM_IGNORED_BUILDS`).
- `package.json` sets `pnpm.onlyBuiltDependencies: ["electron"]`.
- Fallback: `node desktop/node_modules/electron/install.js` (verified → Electron **v37.10.3** on this Mac).
- `node_modules/` is gitignored; lockfile `desktop/pnpm-lock.yaml` is committed.

## How to run

```bash
# 1) Host already up on :8000 (or set SSAK_HOST_URL)
pnpm --dir desktop install   # if node_modules missing
pnpm --dir desktop start
```

## Checklist mapping (plan § Phase 2)

| Plan item | This turn |
|---|---|
| Single-instance → focus / reopen | **Working** (`requestSingleInstanceLock` + `second-instance`) |
| Tray: Open / Quit / Settings / Open logs folder | **Working** (status label included) |
| Close window = hide | **Working** (stub) |
| Quit = Host graceful shutdown | **Stubbed** — shell quit only; Host stop later |
| Startup failure UI | **Partial** — dialog if probe fails; recovery window = Phase 4 |
| Tray “starting…” before ready | **Partial** — ready/unreachable label; “starting…” waits on Host spawn |
| Dock hide policy doc | **Partial** — noted in README; formal Dock policy later |
| `phase2_shell_qa.md` manual QA | **Checklist written** — Pass/Fail columns blank until manual run |

## Constraints honored

- C-01: no CR-14 GO claim
- C-02/C-04: no secrets / vault_data
- C-03: soak pids untouched; no Host stop
- C-05: ideas only from plan — no DSH/Cordis code transplant
- C-07: no push
- Thin shell: no preload, no Node in page

## Deferred (next turns)

1. Host spawn/stop via existing launcher (without touching soak `:8000`)
2. Quit = Host graceful shutdown + child reaping
3. Tray “starting…” while spawn in flight
4. Fill Pass/Fail in `phase2_shell_qa.md` on a dedicated smoke Host
5. Formal Dock hide/show policy doc
