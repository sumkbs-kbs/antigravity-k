---
title: Desktop shell Phase 1 progress
date: 2026-09-15
tz: Asia/Seoul
plan: docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md
---

# Phase 1 progress log

## 2026-09-15 — started after Phase 0 DONE

### Done

- [x] `scripts/build_mac_dmg.sh`: **fail-closed** if `dashboard_dist/index.html` missing
- [x] Auto-attempt `pnpm --dir dashboard build` when dist missing
- [x] Explicit re-copy of `dashboard_dist` (removed silent `|| true`)
- [x] Refuse bundle if `.env` / `.env.*` / `auth_hash` found under app resources

### Not done yet (next agent / next step)

- [ ] Run full `make dmg` and capture `dist/Ssak-Ai-<ver>.dmg` + `.sha256` (long; may be heavy — coordinate with disk/soak machine load)
- [ ] `make dmg-smoke` target (mount → health → quit)
- [ ] Document exact closure file list in MACOS_DMG_GUIDE (Python host still required until deeper 1a/1b work)
- [ ] Windows closure design stub
- [ ] Electron scaffold (Phase 2 / D-01) — **not blocking** Phase 1 packaging harden

### Constraints still active

- Do not kill EX-05 soak
- Do not claim CR-14 GO
- Do not commit `vault_data` / secrets
- Record every step in plan §10 + this file
