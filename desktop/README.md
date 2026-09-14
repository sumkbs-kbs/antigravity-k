# Ssak-Ai Desktop Shell (Phase 2 scaffold)

Thin **Electron** wrapper around the Ssak-Ai **Host** SPA on loopback.

- **Does:** single-instance lock, `BrowserWindow` → Host URL, tray Open/Settings/logs/Quit, Host ready status, hide-on-close.
- **Does not:** transplant DSH/Cordis, expose Electron APIs to the page, or (this turn) spawn/stop Host.

See plan: `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` (Phase 2) and progress: `docs/packaging/notes/phase2_progress.md`.

## Prerequisites

**Host must already be running** on the configured URL (default `http://127.0.0.1:8000`).

Examples:

```bash
# from repo root
uv run agk serve --host 127.0.0.1 --port 8000
# or your usual make/serve launcher
```

This scaffold **does not** start or stop Host, so it will not disturb an existing soak on `:8000`.

Override URL:

```bash
SSAK_HOST_URL=http://127.0.0.1:8000 pnpm --dir desktop start
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

## Layout

```text
desktop/
  package.json
  main.js          # Electron main process
  assets/tray.png  # tray icon (copied from dashboard public)
  README.md
  .gitignore
```

## Phase 2 checklist (this scaffold)

| Item | Status |
|---|---|
| Single-instance lock → focus existing window | **working** |
| Load Host loopback URL | **working** (probe warns if down) |
| Tray Open / Settings / Open logs folder / Quit | **working** |
| Tray Host ready / unreachable label | **working** (soft probe + 120s quiet refresh) |
| Hide-on-close | **working** (stub; Host left running) |
| Quit stops Host | **stubbed** — Quit exits shell only |
| Spawn Host on launch | **deferred** — assume Host running |
| Ready tray “starting…” | **deferred** until Host spawn |
| Manual QA `phase2_shell_qa.md` | **checklist present** — fill Pass/Fail manually |
