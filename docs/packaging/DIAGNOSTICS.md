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

## Deferred (still Phase 4)

- Tray / Settings UI “Export diagnostics…”
- Startup recovery window (open logs / port conflict / export / retry)
