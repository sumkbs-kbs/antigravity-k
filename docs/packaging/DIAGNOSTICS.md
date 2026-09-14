# Diagnostics export (Phase 4)

Safe support bundle for “Host won’t start” / support tickets.

## CLI

```bash
# Default path (macOS):
#   ~/Library/Logs/Ssak-Ai/diagnostics-YYYYMMDD-HHMMSS.zip
# Other platforms:
#   ~/.antigravity-k/logs/diagnostics-YYYYMMDD-HHMMSS.zip
agk diagnostics export

# Explicit path
agk diagnostics export --output ~/Desktop/diagnostics-smoke.zip
```

Host **does not** need to be running. Prefer a clean `PYTHONPATH` that resolves the repo `src/` tree (or `uv run` from the repo) so the current package is used.

## Desktop tray (Electron)

Tray menu **진단 내보내기…** runs the **same CLI path** (one code path):

1. Main process spawns (non-blocking) via `child_process`:
   - Prefer: `uv run agk diagnostics export --output <zip>`
   - Else: `.venv/bin/agk` / `.venv/bin/python -m antigravity_k.cli` / `agk`
   - Helpers: `desktop/hostLifecycle.js` → `runDiagnosticsExport` / `resolveAgkCliSpec`
2. Output ZIP under `~/Library/Logs/Ssak-Ai/` (same dir as “Open logs folder”).
3. Success → dialog with ZIP path; optional **Show in Finder** / folder via `shell.showItemInFolder`.
4. Failure → error dialog (command label + stderr snippet).

Does **not** require Host to be up. Does not touch soak / unrelated PIDs.

## ZIP allowlist

| Member | Contents |
|---|---|
| `manifest.json` | App/Python versions, OS, bind host/port, build provenance, setting **key names**, allowlist note |
| `setting_keys.json` | Setting **key names only** (`values_included: false`) |
| `error_codes.json` | Recent agent-error journal codes/types (messages scrubbed + truncated) |
| `logs/*` | Recent log tails (`.log` / `.txt` / `.jsonl`), scrubbed with `secret_scanner.redact_full` |

## Never included

- `.env` values (or the `.env` file itself)
- PIN / access_pin
- Bearer / tokens / API key values
- `vault_data/`, `auth_hash`, credentials stores
- Arbitrary env dumps

Path blocklist: `is_forbidden_archive_path()` in `antigravity_k.engine.diagnostics_export` (reuses `secret_scanner` / memory-path segments).

## Verification

```bash
PYTHONPATH=src uv run --no-sync pytest tests/test_diagnostics_export.py -q
```

Smoke: after `agk diagnostics export`, unzip `-l` the ZIP — members must be allowlist-only; `secret_scanner.scan_for_secrets` on each member should be 0.

Node smoke (no Electron UI):

```bash
node -e "require('./desktop/hostLifecycle').runDiagnosticsExport({repoRoot:process.cwd(),outputPath:require('os').homedir()+'/Library/Logs/Ssak-Ai/diagnostics-node-smoke.zip'}).then(r=>console.log(r))"
```

## Startup recovery window (Host-fail)

When the desktop shell cannot get Host ready (spawn timeout, probe fail, spawn error, or `SSAK_SPAWN_HOST=0` + unreachable URL), it shows an Electron **recovery dialog** (not a one-shot alert):

| Button | Action |
|---|---|
| **Open logs folder** | Same as tray → `~/Library/Logs/Ssak-Ai` (or `~/.antigravity-k/logs`) |
| **Export diagnostics** | Same path as tray **진단 내보내기…** (`runDiagnosticsExport` / `agk diagnostics export`) |
| **Retry start** | If spawn allowed: stop owned child (if any) → re-spawn/probe. If `SSAK_SPAWN_HOST=0`: re-probe existing `SSAK_HOST_URL` only |
| **Open in browser** | `shell.openExternal(SSAK_HOST_URL)` then continue to tray/window |
| **Quit** | Quit the shell (owned Host stopped on quit as usual) |

If a **port conflict** is suspected (TCP accept while HTTP probe fails, bind `EADDRINUSE`, or stderr/error mentions address-already-in-use), the dialog detail includes a short Phase 4/6 hint: stop the other listener or change `SSAK_HOST_URL` / `--port`, then Retry.

**Phase 6 port notes (product vs Vite):**

| Mode | Port story |
|---|---|
| **Product** | Single loopback: `agk serve` (default **`:8000`**) serves API + `dashboard_dist` SPA. Electron `SSAK_HOST_URL` default `http://127.0.0.1:8000`. No Vite. |
| **Dev Vite** | Vite `:5173`/`:5174` proxies `/api` `/ws` `/v1` → `VITE_BACKEND_URL` / `AGK_BACKEND_URL` / default `http://127.0.0.1:8000`. Startup probe warns if backend dead or target still uses legacy **`:8400`**. |
| **Conflict** | Host spawn / recovery already hint `EADDRINUSE`; free the listener or pick another `--port` / `SSAK_HOST_URL`. Do not point recovery smoke at soak `:8000`. |


### Manual trigger (dev)

```bash
# Bad port + never spawn → recovery dialog on launch
SSAK_HOST_URL=http://127.0.0.1:18081 SSAK_SPAWN_HOST=0 pnpm --dir desktop start

# Or let spawn try a dead/busy port (timeout → recovery)
SSAK_HOST_URL=http://127.0.0.1:18081 pnpm --dir desktop start
```

Do not point at soak / production `:8000` while validating recovery.

## Deferred (still Phase 4)

- Settings-page diagnostics button (tray + recovery dialog are enough for this slice)
- Optional `desktop/recovery.html` BrowserWindow (dialog path landed first; keep thin)
