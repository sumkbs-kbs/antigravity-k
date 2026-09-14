# Phase 2 shell — manual QA checklist

**Date opened:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Shell path:** `desktop/` (Electron thin shell)  
**Plan:** `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` § Phase 2  
**Constraints:** C-01..C-08; no CR-14 GO; do not kill soak `29961`/`29969`; do not disturb unintended Host on `:8000` unless using a dedicated smoke Host.

Fill **Pass / Fail** (and notes) after manual runs. Leave blank until exercised.

## Preconditions

| # | Check | Pass | Fail | Notes |
|---|---|---|---|---|
| P1 | Host reachable at `SSAK_HOST_URL` or `http://127.0.0.1:8000` (dedicated smoke Host preferred) | | | |
| P2 | `pnpm --dir desktop install` (Electron binary present) | | | |
| P3 | Soak pids (if any) left alone; shell does not spawn/stop Host this Phase slice | | | |

## Plan checklist mapping

| Plan item (Phase 2) | How to verify | Pass | Fail | Notes |
|---|---|---|---|---|
| Single-instance: second launch focuses / reopens existing window | Start shell twice; second should focus first window, not a second app | | | |
| Tray: Open | Tray → **Open** shows/focuses BrowserWindow | | | |
| Tray: Settings | Tray → **Settings** navigates window to Host SPA `/settings` | | | |
| Tray: Open in Browser | Opens system browser to Host URL | | | |
| Tray: Open logs folder | Opens `~/Library/Logs/Ssak-Ai` (creates dir if missing) | | | |
| Tray: Quit | Quits **shell only**; Host still listening (spawn/stop deferred) | | | |
| Tray status label | Disabled label **Host ready** / **Host unreachable** matches soft probe (refresh ~120s, no spam) | | | |
| Close window = hide | Window close hides; tray + process remain; Host untouched | | | |
| Quit = Host graceful shutdown | **DEFERRED** — Quit must **not** kill Host this slice (C-03) | | | N/A until Host spawn wired |
| Startup failure UI | Stop Host; launch shell → warning dialog Continue / Quit | | | |
| Tray “starting…” before ready | **DEFERRED** — ready/unreachable label only; no “starting…” until spawn | | | |
| macOS Dock icon policy | Dock visible on launch (README draft); formal policy later | | | |

## Thin-shell security smoke

| # | Check | Pass | Fail | Notes |
|---|---|---|---|---|
| S1 | No preload bridge; page cannot call Electron/Node APIs | | | Inspect `desktop/main.js` `webPreferences` |
| S2 | Default target is loopback Host only | | | |

## Evidence / deferred

| Item | Status |
|---|---|
| Scaffold + tray Settings / logs / status | Code landed — fill Pass/Fail above when QA’d |
| Host spawn on launch | **Deferred** |
| Quit kills Host + child reaping | **Deferred** (C-03 soak/:8000) |
| Automated shell smoke script | Optional / later |
| CR-14 GO | **Out of scope** (C-01) |

## Sign-off

| Role | Name | Date | Result |
|---|---|---|---|
| Runner | | | |
| Reviewer | | | |
