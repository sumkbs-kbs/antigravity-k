---
title: Desktop shell Phase 0 baseline
date: 2026-09-15
tz: Asia/Seoul
plan: docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md
commit_at_write: 1314d016
cr14_frozen_candidate: b6003205365606407cadfd6cbb1c813110beef0f
---

# Phase 0 baseline (2026-09-15)

## Environment snapshot

| Item | Value |
|---|---|
| Branch | `codex/m1-task-events` |
| Plan commit | `1314d016` (plan introduced) |
| EX-05 soak | **ALIVE** pid `29961`/`29969` · elapsed ~1h23m at measurement · **do not kill** |
| Backend `:8000` | `/api/auth/status` HTTP 200 |
| Vite `:5173` | HTTP 200 (dev-only path; product must not require this) |
| `:8000/` SPA | Returns Korean HTML shell (serves `dashboard_dist`) |

## Production UI path

| Check | Result |
|---|---|
| `src/antigravity_k/dashboard_dist/` exists | **YES** (~19MB) |
| `index.html` present | **YES** |
| Mount point | `src/antigravity_k/api/server.py` ~L728–741 · `StaticFiles(..., html=True)` on `/` |
| Dashboard build command | `pnpm --dir dashboard build` (`tsc -b && vite build`) via Makefile `dashboard-build-provenance` |
| `dashboard` package `dev` script | `vite --port 5174` (note: live process may still use 5173) |

**Conclusion:** Product path can already serve UI **without Vite** when `dashboard_dist` is present and `agk serve` is used. Dev path (5173/5174 + `VITE_BACKEND_URL`) remains fragile (observed earlier: dead `8400` proxy → settings save fail).

## macOS DMG baseline (`scripts/build_mac_dmg.sh`)

| Check | Result |
|---|---|
| `make dmg` target | Exists · calls `scripts/build_mac_dmg.sh` |
| Copies `dashboard_dist` into bundle | **YES** (`cp -R ... dashboard_dist` · missing dist only warns via `|| true`) |
| Bundles site-packages | **Partial** — if `uv` available: `uv export` + `uv pip install --target .../site-packages` |
| Host Python requirement | **YES** — launcher probes many Pythons; fails with alert if no 3.12+ |
| Fixed server port in launcher | `8000` |
| Current `dist/*.dmg` | **ABSENT** (only wheel/sdist under `dist/`) |

**Gaps for Phase 1:**

1. DMG build does **not** fail-closed if `dashboard_dist` missing (`|| true`).
2. DMG build does **not** automatically run `pnpm --dir dashboard build` first.
3. Runtime still depends on finding host Python 3.12+ (not fully closed).
4. No current DMG artifact in tree to smoke.
5. Windows installer not in this baseline.

## Port policy draft (Phase 6 input)

| Mode | Ports | Notes |
|---|---|---|
| **Product** | Single loopback (today launcher uses `8000`) · API+SPA same origin | Must not need 5173 |
| **Dev** | Backend `8000` + Vite `5173`/`5174` with proxy | `VITE_BACKEND_URL` must point at live backend |

## Decisions recorded in plan §9

- **D-01:** Target shell = **Option A (Electron + existing Python closure)** for macOS+Windows tray/update parity.
- **D-01-interim:** Phase 1 **first** hardens existing `build_mac_dmg.sh` closure (fail-closed dist, build dashboard, reduce host-Python fragility) so progress is not blocked on Electron scaffold.
- **D-02:** Prefer closure style **1a** (bundle `site-packages` / nearby interpreter) already partially implemented; evaluate 1b (freeze) only if 1a cannot meet “double-click without Python install”.

## Next agent action

Start **Phase 1** checklist in `DESKTOP_SHELL_REFERENCE_PLAN.md`:

1. Make `build_mac_dmg.sh` fail if `dashboard_dist/index.html` missing.
2. Invoke dashboard production build (or Makefile target) before copy.
3. Document exact closure file list; ensure `.env` never packaged.
4. Produce `dist/Ssak-Ai-<ver>.dmg` + sha256 and attach smoke note here or under `.omo/evidence/desktop-shell/`.
5. **Do not** kill EX-05 soak; **do not** claim CR-14 GO.

## Handoff discipline (user directive 2026-09-15)

Every progress step **must** update:

1. `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` §10 status table + §9 decisions + §12 changelog
2. This notes file or a new `docs/packaging/notes/phaseN_*.md`
3. Prefer a docs commit so the next agent sees state in git history
