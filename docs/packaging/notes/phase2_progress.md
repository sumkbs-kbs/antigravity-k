# Phase 2 progress — Desktop shell UX scaffold

**Date:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Status:** IN_PROGRESS (Host owned-child lifecycle wired; formal QA Pass/Fail still manual)  
**Decision:** D-01 = A (Electron); path = `desktop/` (see plan §5 / D-06)

## What landed

Thin Electron package at repo `desktop/`:

| Path | Role |
|---|---|
| `desktop/package.json` | `electron` as **devDependency**; scripts `start`/`dev` |
| `desktop/main.js` | Main process: single-instance, window, tray, hide-on-close, Settings/logs, Host lifecycle |
| `desktop/hostLifecycle.js` | Soft-probe + owned spawn/stop helpers (no Electron; smoke-reusable) |
| `desktop/assets/tray.png` | Tray icon (from `dashboard/public/icon-180.png`) |
| `desktop/README.md` | How to run + spawn policy |
| `desktop/.gitignore` | `node_modules/`, build outs |
| `docs/packaging/notes/phase2_shell_qa.md` | Manual QA checklist |

## Host lifecycle (owned child only)

| Rule | Behavior |
|---|---|
| Soft-probe `SSAK_HOST_URL` (default `http://127.0.0.1:8000`) | On launch |
| Host already up | Use it; **do not spawn**; `ownedHost=false` |
| Unreachable + `SSAK_SPAWN_HOST` default **1** | Spawn child; tray **Host starting…** until ready or ~45s timeout |
| Unreachable + `SSAK_SPAWN_HOST=0` | Warning dialog Continue/Quit (no spawn) |
| Spawn command (preferred) | `uv run agk serve --host <h> --port <p>` from **repo root** |
| Spawn fallback | `.venv/bin/agk` or `.venv/bin/python -m antigravity_k.cli serve` (DMG launcher family) |
| Hide-on-close | Window hides; owned Host **keeps running** |
| Quit | If `ownedHost` and child alive → SIGTERM then SIGKILL after grace |
| Never | Kill unrelated PIDs; kill `29961`/`29969`; touch `val02_staging.py` soak |

### Smoke (2026-09-15 KST) — no secrets

| Check | Result |
|---|---|
| Spawn command chosen | `uv run agk serve --host 127.0.0.1 --port <from URL>` (uv present on this Mac) |
| `SSAK_SPAWN_HOST=0` against existing `:8000` | Probe sees Host up → no spawn path (shell would set `ownedHost=false`) |
| Alternate-port spawn/quit | **PASS** — `uv run agk serve --host 127.0.0.1 --port 18081` (owned pid 43599) → ready → SIGTERM stop; `:18081` down after; `:8000` still up |
| Soak `29961`/`29969` | **Alive** before and after smoke |
| Electron GUI Quit path | Same `stopOwnedHost` as smoke; full tray Quit not re-run in this turn |

## Tray

| Item | Behavior |
|---|---|
| Open | Show/focus BrowserWindow |
| Settings | Show window + `loadURL` → `{HOST}/settings` |
| Open in Browser | `shell.openExternal(HOST_URL)` |
| Open logs folder | `~/Library/Logs/Ssak-Ai` on macOS; else `~/.antigravity-k/logs` |
| Status label | **Host starting…** / **Host ready** / **Host unreachable** |
| Quit | Shell exit + stop **owned** Host only |

Thin shell: still **no** preload / Electron API into the page.

## Install note

- `pnpm --dir desktop install` may skip Electron postinstall (`ERR_PNPM_IGNORED_BUILDS`).
- `package.json` sets `pnpm.onlyBuiltDependencies: ["electron"]`.
- Fallback: `node desktop/node_modules/electron/install.js` (verified → Electron **v37.10.3** on this Mac).
- `node_modules/` is gitignored; lockfile `desktop/pnpm-lock.yaml` is committed.

## How to run

```bash
# Reuse existing Host (never spawn)
SSAK_SPAWN_HOST=0 pnpm --dir desktop start

# Product default — spawn if unreachable (prefer alternate port for smoke)
SSAK_HOST_URL=http://127.0.0.1:18081 pnpm --dir desktop start
```

## Checklist mapping (plan § Phase 2)

| Plan item | This turn |
|---|---|
| Single-instance → focus / reopen | **Working** |
| Tray: Open / Quit / Settings / Open logs folder | **Working** |
| Close window = hide | **Working** (owned Host stays) |
| Quit = Host graceful shutdown | **Working** for **owned child only** |
| Startup failure UI | **Working** — spawn timeout dialog; or Continue/Quit when spawn disabled |
| Tray “starting…” before ready | **Working** during owned spawn |
| Dock hide policy doc | **Partial** — noted in README; formal Dock policy later |
| `phase2_shell_qa.md` manual QA | Checklist updated — Pass/Fail still blank until full manual GUI run |

## Constraints honored

- C-01: no CR-14 GO claim
- C-02/C-04: no secrets / vault_data
- C-03: soak pids untouched; Quit never kills non-owned Host / `:8000` soak
- C-05: ideas only from plan — no DSH/Cordis code transplant
- C-07: no push
- Thin shell: no preload, no Node in page

## Deferred (next turns)

1. Fill Pass/Fail in `phase2_shell_qa.md` on a dedicated smoke Host (full GUI)
2. Formal Dock hide/show policy doc
3. Optional automated Electron E2E for Quit→owned stop
