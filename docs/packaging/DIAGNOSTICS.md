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

## Deferred (still Phase 4)

- Startup recovery window (open logs / port conflict / export / retry) — **next**
- Settings-page button (tray item is enough for this slice)
