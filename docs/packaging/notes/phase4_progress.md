# Phase 4 progress — Recovery & diagnostics UX

**Date:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Status:** **IN_PROGRESS** (CLI export + tray “진단 내보내기…”; recovery window still open)  
**Plan:** `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` § Phase 4 / §10

## What landed

| Path | Role |
|---|---|
| `src/antigravity_k/engine/diagnostics_export.py` | Allowlist ZIP builder + path blocklist + scrubbed log tails |
| `src/antigravity_k/cli.py` | `agk diagnostics export` (`--output` optional) |
| `desktop/hostLifecycle.js` | `resolveAgkCliSpec` + `runDiagnosticsExport` (spawn same CLI) |
| `desktop/main.js` | Tray **진단 내보내기…** → dialog + optional `shell.showItemInFolder` |
| `docs/packaging/DIAGNOSTICS.md` | User/support doc (CLI + tray) |
| `tests/test_diagnostics_export.py` | Forbidden-path + CLI dry-run (no secret-looking members) |

## How Electron invokes export

Tray click → `exportDiagnosticsFromTray()` → `lifecycle.runDiagnosticsExport({ outputPath })` →  
`child_process.spawn('uv', ['run', 'agk', 'diagnostics', 'export', '--output', zipPath], { cwd: repoRoot })`  
(with the same venv/`agk` fallbacks as Host spawn). Success dialog offers Reveal in Finder/folder.

## Smoke (2026-09-15 KST)

| Check | Result |
|---|---|
| `agk diagnostics export` | ZIP → `~/Library/Logs/Ssak-Ai/diagnostics-YYYYMMDD-HHMMSS.zip` |
| Members | `manifest.json`, `setting_keys.json`, `error_codes.json`, `logs/*` tails |
| `secret_scanner.scan_for_secrets` on ZIP members | **0** matches |
| Blocklist (`.env` / `vault_data` / `auth_hash`) | Not in namelist or raw bytes |
| Node `runDiagnosticsExport` | **ok** via `uv run agk diagnostics export --output …` |
| Soak `29961`/`29969` | **Alive** (untouched) |

## Still open

- [x] Tray “진단 내보내기…” (Settings button optional / deferred)
- [ ] Startup recovery window (logs / port hint / export / retry) — **next slice**
- [ ] Wire export into Host-fail dialogs (recovery window can own this)

## Constraints

- No CR-14 GO claim
- No vault/secrets committed
- No push in this turn
