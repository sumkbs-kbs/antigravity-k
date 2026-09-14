# Phase 2 progress — Desktop shell UX scaffold

**Date:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Status:** IN_PROGRESS (scaffold + docs this turn; full QA later)  
**Decision:** D-01 = A (Electron); path = `desktop/` (see plan §5 / D-06)

## What landed

Thin Electron package at repo `desktop/`:

| Path | Role |
|---|---|
| `desktop/package.json` | `electron` as **devDependency**; scripts `start`/`dev` |
| `desktop/main.js` | Main process: single-instance, window, tray, hide-on-close |
| `desktop/assets/tray.png` | Tray icon (from `dashboard/public/icon-180.png`) |
| `desktop/README.md` | How to run + constraints |
| `desktop/.gitignore` | `node_modules/`, build outs |

## Host assumption (important)

**This turn does NOT spawn or stop Host.**

- Shell loads `SSAK_HOST_URL` or default `http://127.0.0.1:8000`.
- Soft HTTP probe: if Host unreachable, warning dialog → Continue / Quit.
- Quit exits the **shell only**; Host (and soak on `:8000`) are left alone (C-03).
- Start Host separately, e.g. `uv run agk serve --host 127.0.0.1 --port 8000`.

Do **not** point shell spawn at soak workdirs; do not kill pids `29961`/`29969`.

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
| Tray: Open / Quit | **Working** (Settings / Logs / folder deferred) |
| Close window = hide | **Working** (stub) |
| Quit = Host graceful shutdown | **Stubbed** — shell quit only; Host stop later |
| Startup failure UI | **Partial** — dialog if probe fails; recovery window = Phase 4 |
| Tray “starting…” before ready | **Stubbed** |
| Dock hide policy doc | **Partial** — noted in README; formal Dock policy later |
| `phase2_shell_qa.md` manual QA | **Not this turn** |

## Constraints honored

- C-01: no CR-14 GO claim
- C-02/C-04: no secrets / vault_data
- C-03: soak pids untouched; no Host stop
- C-05: ideas only from plan — no DSH/Cordis code transplant
- C-07: no push
- Thin shell: no preload, no Node in page

## Next (later turns)

1. Optional Host spawn/stop via existing launcher (without touching soak `:8000`)
2. Tray: open logs folder / settings deep-link
3. Manual QA → `phase2_shell_qa.md`
4. Ready-state tray label while waiting for Host
