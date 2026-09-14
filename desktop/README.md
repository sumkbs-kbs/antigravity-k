# Ssak-Ai Desktop Shell (Phase 2)

Thin **Electron** wrapper around the Ssak-Ai **Host** SPA on loopback.

- **Does:** single-instance lock, `BrowserWindow` → Host URL, tray Open/Settings/logs/**진단 내보내기…**/**업데이트 확인…**/Quit, Host ready / starting… / unreachable status, hide-on-close, **owned-child Host spawn/stop**, diagnostics export via same `agk diagnostics export` CLI, Phase 5 update soft-check (`SSAK_UPDATE_FEED`).
- **Does not:** transplant DSH/Cordis, expose Electron APIs to the page, or kill Host processes it did not spawn.

See plan: `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` (Phase 2) and progress: `docs/packaging/notes/phase2_progress.md`.

## Host URL & spawn policy

| Env | Default | Meaning |
|---|---|---|
| `SSAK_HOST_URL` | `http://127.0.0.1:8000` | Loopback Host SPA URL (soft-probed on launch) |
| `SSAK_SPAWN_HOST` | `1` (spawn when unreachable) | Set to `0` / `false` / `off` to **never** spawn |

**Launch behavior**

1. Soft-probe `SSAK_HOST_URL`.
2. If Host already responds → use it; **do not spawn**; `ownedHost=false`.
3. If unreachable **and** spawn enabled → spawn Host as a **child** of the shell:
   - Prefer: `uv run agk serve --host <host> --port <port>` from **repo root**
   - Else: `.venv/bin/agk serve …` or `.venv/bin/python -m antigravity_k.cli serve …` (same family as `scripts/build_mac_dmg.sh` launcher)
   - Tray shows **Host starting…** until probe succeeds or timeout (~45s), then an error dialog if still down.
4. If Host fails to become ready (spawn timeout / probe fail / spawn error / spawn-off unreachable) → **Phase 4 recovery dialog**: Open logs folder / Export diagnostics / Retry start / Open in browser / Quit (port-conflict hint when suspected). Manual trigger: `SSAK_HOST_URL=http://127.0.0.1:18081 SSAK_SPAWN_HOST=0 pnpm --dir desktop start`.

**Quit vs hide**

- Window close → **hide** (tray + process stay; owned Host keeps running).
- Tray **Quit** / app quit → if `ownedHost` and the child is still alive → **SIGTERM**, then **SIGKILL** after a short grace. Only that owned PID is signaled — never unrelated processes, never soak pids `29961`/`29969` / `val02_staging.py`.

Disable spawn (safe against an existing soak on `:8000`):

```bash
SSAK_SPAWN_HOST=0 pnpm --dir desktop start
```

Smoke on an alternate port (does not touch `:8000`):

```bash
SSAK_HOST_URL=http://127.0.0.1:18081 pnpm --dir desktop start
# Quit from tray → owned child on 18081 should stop
```

## Install & run

```bash
pnpm --dir desktop install
pnpm --dir desktop start
# alias: pnpm --dir desktop dev
```

`electron` is a **devDependency**. Do not commit `desktop/node_modules/`.

If `pnpm install` skips Electron's download (`ERR_PNPM_IGNORED_BUILDS`), run once:

```bash
pnpm --dir desktop config set onlyBuiltDependencies electron   # or use package.json pnpm.onlyBuiltDependencies
node desktop/node_modules/electron/install.js
```

If install fails (network), keep the source tree and install later — files under `desktop/` are enough to review.

## Security constraints (thin shell)

| Setting | Value |
|---|---|
| `nodeIntegration` | `false` |
| `contextIsolation` | `true` |
| `sandbox` | `true` |
| preload bridge | **none** (no API exposure to page) |
| Default bind target | loopback Host only |
| Host stop | **owned child only** |

## Layout

```text
desktop/
  package.json
  main.js              # Electron main process
  hostLifecycle.js     # soft-probe + owned spawn/stop (no Electron)
  assets/tray.png      # tray icon (copied from dashboard public)
  README.md
  .gitignore
```


## macOS Dock policy

| Action | Dock icon | Process / Host |
|---|---|---|
| Launch | Shown | Shell + tray running |
| Close window (hide) | **Stays** | Process stays; owned Host **keeps running** |
| Dock click / tray Open | Stays | Window shown/focused |
| Tray **Quit** | Removed (app exit) | Quit stops **owned** Host child only |

**Rule:** hide-on-close keeps the process; the Dock icon remains until Quit. Quit owns child shutdown.

## Phase 2 checklist

| Item | Status |
|---|---|
| Single-instance lock → focus existing window | **working** |
| Load Host loopback URL | **working** |
| Tray Open / Settings / Open logs folder / Quit | **working** |
| Tray Host ready / starting… / unreachable | **working** |
| Hide-on-close | **working** (owned Host left running) |
| Soft-probe; reuse existing Host | **working** (`ownedHost=false`) |
| Spawn Host when unreachable (`SSAK_SPAWN_HOST` default on) | **working** (owned child) |
| Quit stops owned Host only | **working** (SIGTERM→SIGKILL; soak/unrelated never killed) |
| macOS Dock policy | **documented** — hide keeps process/Dock; Quit clears Dock |
| Manual QA `phase2_shell_qa.md` | **checklist ready, not executed** |
