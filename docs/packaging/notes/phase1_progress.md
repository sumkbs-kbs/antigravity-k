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

### Residual / next (updated 2026-09-15 residual closure)

- [x] Run full `make dmg` + sha256 — see attempt #2 PASS (`262b54244a…`)
- [x] `make dmg-smoke` PASS (:18080)
- [x] Document closure inventory + Python requirement in `MACOS_DMG_GUIDE.md`
- [x] Windows closure design stub — `notes/windows_closure_stub.md`
- [x] Decision D-02 confirmed **1a**; launcher prefers `Resources/python` when present; `SSAK_BUNDLE_PYTHON=1` opt-in build (default OFF)
- [~] Clean Mac without host Python — **PARTIAL** until `SSAK_BUNDLE_PYTHON=1` DMG is rebuilt and smoke-verified
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
- **Still open (at time of attempt #2):** was `dmg-smoke` + host Python; **later closed** — see dmg-smoke PASS + residual closure below. Electron = Phase 2. Phase 6 mobile bind progressed separately.
- **Soak:** left running (not killed)

## 2026-09-15 — dmg-smoke PASS

- Added `scripts/dmg_smoke.sh` + Makefile `dmg-smoke`
- Runs bundled Host on `127.0.0.1:18080` (does **not** touch :8000 / soak)
- Result: **PASS** auth=200 spa=200
- Fresh smoke dir has no PIN → login 503 expected; SPA still served

## 2026-09-15 — Phase 1 residual closure (docs + 1a incremental)

- **D-02:** Python 클로저 **1a** 확정 (site-packages + 근접/동봉 인터프리터). 1b는 1a 실패 시에만.
- **Launcher:** `Resources/python/bin/python3` 를 host 탐색 **앞**에 배치. 없으면 기존 host 탐색 → fail-closed 알림.
- **Build:** `SSAK_BUNDLE_PYTHON=1` 일 때만 uv-managed CPython을 `Contents/Resources/python/` 에 복사. **기본 OFF** → 일반 `make dmg` ~55M 유지. 동봉 시 ~50–60M+ 추가(문서화).
- **Docs:** `MACOS_DMG_GUIDE.md` 클로저 인벤토리·Python 요구사항·옵트인 플래그 반영.
- **Windows stub:** `docs/packaging/notes/windows_closure_stub.md` (설계만).
- **SSAK_BUNDLE_PYTHON full rebuild:** 이번 턴에서 전체 DMG 재빌드/스모크는 **미실시** (코드+문서만; 용량·시간). 검증은 후속.
- **Soak:** EX-05 pids 유지 (죽이지 않음). CR-14 GO 주장 없음.
