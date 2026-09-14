# Phase 4 progress — Recovery & diagnostics UX

**Date:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Status:** **IN_PROGRESS** (CLI export + tray export + **Host-fail recovery dialog**; Settings button / optional HTML window deferred)  
**Plan:** `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` § Phase 4 / §10 / §12

## What landed

| Path | Role |
|---|---|
| `src/antigravity_k/engine/diagnostics_export.py` | Allowlist ZIP builder + path blocklist + scrubbed log tails |
| `src/antigravity_k/cli.py` | `agk diagnostics export` (`--output` optional) |
| `desktop/hostLifecycle.js` | `resolveAgkCliSpec` + `runDiagnosticsExport`; `suspectPortConflict` / `tcpPortOpen` |
| `desktop/main.js` | Tray **진단 내보내기…**; Host-fail → **recovery dialog** (logs / export / retry / browser / quit) |
| `docs/packaging/DIAGNOSTICS.md` | User/support doc (CLI + tray + recovery) |
| `tests/test_diagnostics_export.py` | Forbidden-path + CLI dry-run (no secret-looking members) |

## Host-fail recovery (this slice)

Replaces one-shot `showErrorBox` / spawn-off Continue-Quit-only path when Host does not become ready:

1. **Open logs folder** — existing `openLogsFolder()`  
2. **Export diagnostics** — reuses `exportDiagnosticsFromTray()`  
3. **Retry start** — `retryHostStart()`: spawn on → stop owned child + `ensureHost()`; spawn off → re-probe only  
4. **Open in browser** / **Quit**

Port-conflict hint when `suspectPortConflict(SSAK_HOST_URL)` (TCP occupied + HTTP fail, bind `EADDRINUSE`, or stderr/error match).

### Manual trigger

```bash
SSAK_HOST_URL=http://127.0.0.1:18081 SSAK_SPAWN_HOST=0 pnpm --dir desktop start
```

## Smoke (2026-09-15 KST)

| Check | Result |
|---|---|
| `agk diagnostics export` | ZIP → `~/Library/Logs/Ssak-Ai/diagnostics-YYYYMMDD-HHMMSS.zip` |
| Members | `manifest.json`, `setting_keys.json`, `error_codes.json`, `logs/*` tails |
| `secret_scanner.scan_for_secrets` on ZIP members | **0** matches |
| Node `runDiagnosticsExport` | **ok** |
| Node `suspectPortConflict` + `EADDRINUSE` hint | **true** when hint present |
| `node --check desktop/main.js` / `hostLifecycle.js` | **ok** |
| Soak `29961`/`29969` | **Alive** (untouched) |

## Still open

- [x] Tray “진단 내보내기…”
- [x] Startup recovery dialog (logs / port hint / export / retry / browser / quit)
- [ ] Settings-page export button (optional / deferred)
- [ ] Optional `desktop/recovery.html` BrowserWindow (dialog preferred for thinness)

## Constraints

- No CR-14 GO claim
- No vault/secrets committed
- No push in this turn
- Do not kill soak 29961/29969
