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

## 2026-09-15 — make dmg attempt #1 FAIL then fix

- **FAIL:** secret guard tripped because `cp -R src` copied **`src/.env`** into the bundle (paths only logged; contents not recorded).
- **FIX:** switch to `rsync` with excludes for `.env`, `.env.*`, `auth_hash`, `auth_hash.*`.
- **Premise:** personal use + mobile Host (see `mobile_host_premise.md`); secrets stay in user data, never in DMG.
- **Next:** re-run `make dmg`, record artifact paths + sha256.

## 2026-09-15 — make dmg attempt #2 PASS

- **Command:** `make dmg` (after rsync secret excludes)
- **Artifact:** `dist/Ssak-Ai-0.1.0.dmg` (~55M)
- **SHA-256:** `262b54244a60419567f3dd14e8be4d28a8409c0649bcfbd263ebff36cbd1c362` (also `dist/Ssak-Ai-0.1.0.dmg.sha256`)
- **site-packages bundle:** ~79M inside app; total app resources ~124M before DMG compress
- **Secret path scan on built `.app`:** 0 hits (`.env` / `auth_hash*`)
- **Mount integrity:** script verified app + Applications symlink + Info.plist
- **Log:** `/tmp/ssak-dmg-logs/make-dmg-2026-09-15b.log` (local machine temp; not committed)
- **Still open:** `dmg-smoke` (launch app → host health); host Python 3.12+ still required by launcher; Electron shell not started; mobile bind UI (Phase 6) not implemented yet
- **Soak:** left running (not killed)
