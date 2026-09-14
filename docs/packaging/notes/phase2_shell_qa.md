# Phase 2 shell — manual QA checklist

**Date opened:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Shell path:** `desktop/` (Electron thin shell)  
**Plan:** `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` § Phase 2  
**Constraints:** C-01..C-08; no CR-14 GO; do not kill soak `29961`/`29969`; prefer `SSAK_SPAWN_HOST=0` against `:8000` or spawn on alternate port (`:18081`).

Fill **Pass / Fail** (and notes) after manual runs. Leave blank until exercised.

## Preconditions

| # | Check | Pass | Fail | Notes |
|---|---|---|---|---|
| P1 | Host reachable at `SSAK_HOST_URL` or use spawn on alternate port | | | |
| P2 | `pnpm --dir desktop install` (Electron binary present) | | | |
| P3 | Soak pids (if any) left alone; Quit stops **owned child only** | | | |

## Plan checklist mapping

| Plan item (Phase 2) | How to verify | Pass | Fail | Notes |
|---|---|---|---|---|
| Single-instance: second launch focuses / reopens existing window | Start shell twice; second should focus first window, not a second app | | | |
| Tray: Open | Tray → **Open** shows/focuses BrowserWindow | | | |
| Tray: Settings | Tray → **Settings** navigates window to Host SPA `/settings` | | | |
| Tray: Open in Browser | Opens system browser to Host URL | | | |
| Tray: Open logs folder | Opens `~/Library/Logs/Ssak-Ai` (creates dir if missing) | | | |
| Tray: Quit | Quits shell; if owned Host → child stops; if reused Host → Host stays | | | |
| Tray status label | **Host starting…** / **Host ready** / **Host unreachable** | | | |
| Close window = hide | Window close hides; tray + process remain; owned Host stays | | | |
| Quit = Host graceful shutdown | Owned child only: SIGTERM→SIGKILL; never soak/unrelated | | | |
| Startup failure UI | `SSAK_SPAWN_HOST=0` + down Host → warning; spawn timeout → error dialog | | | |
| Tray “starting…” before ready | Spawn path shows starting… until probe OK | | | |
| Soft-probe reuse | Host already up → no spawn (`ownedHost=false`) | | | |
| `SSAK_SPAWN_HOST=0` | Never spawns even if unreachable | | | |
| macOS Dock icon policy | Dock visible on launch (README draft); formal policy later | | | |

## Thin-shell security smoke

| # | Check | Pass | Fail | Notes |
|---|---|---|---|---|
| S1 | No preload bridge; page cannot call Electron/Node APIs | | | Inspect `desktop/main.js` `webPreferences` |
| S2 | Default target is loopback Host only | | | |
| S3 | Stop path never signals non-owned / forbidden pids | | | `hostLifecycle.js` |

## Evidence / deferred

| Item | Status |
|---|---|
| Scaffold + tray Settings / logs / status | Code landed |
| Host owned-child spawn on launch | **Landed** (`SSAK_SPAWN_HOST` default on) |
| Quit kills owned Host + child reaping | **Landed** (owned only) |
| Lifecycle smoke on `:18081` | See `phase2_progress.md` |
| Full GUI Pass/Fail | Manual — fill above |
| CR-14 GO | **Out of scope** (C-01) |

## Sign-off

| Role | Name | Date | Result |
|---|---|---|---|
| Runner | | | |
| Reviewer | | | |
