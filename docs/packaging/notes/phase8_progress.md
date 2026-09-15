# Phase 8 — docs / gate / handoff progress

**Status:** **DONE-with-caveat** (2026-09-15 KST)  
**Plan:** [`../DESKTOP_SHELL_REFERENCE_PLAN.md`](../DESKTOP_SHELL_REFERENCE_PLAN.md) Phase 8 / §10 / §12  
**CR-14:** still **NO-GO** (this lane does not claim GO)  
**Soak:** PIDs `29961` / `29969` (`val02_staging` 28800s) — **ALIVE; not touched**

## What landed

| Item | Result |
|---|---|
| Makefile target `check-desktop` | Wired next to `dmg` / `dmg-smoke` |
| Offline update-channel unit test | `node desktop/test_updateChannels.js` (also `pnpm --dir desktop run test:update-channels`) |
| Narrow pytest | `tests/test_diagnostics_export.py`, `tests/test_network_access_api.py`, `tests/test_phase6_settings_env_smoke.py` |
| Key file presence | `desktop/main.js`, `scripts/dmg_smoke.sh`, `scripts/build_mac_dmg.sh` |
| Explicitly **skipped** | Full-repo ruff/mypy; `make dmg` / DMG rebuild; Host start; update-feed network; soak kill |

## Local gate run

```text
$ make check-desktop
── check-desktop: key packaging files ──
── check-desktop: update-channel fixture test (offline) ──
test_updateChannels: OK
── check-desktop: narrow pytest (diagnostics + network access + phase6 settings) ──
13 passed, 1 warning in 1.34s
── check-desktop: PASS (skipped: full-repo ruff/mypy, DMG rebuild, Host start, update feed network) ──
# wall ~1.83s real (2026-09-15 KST); soak 29961/29969 still alive
```

| Check | Result | Notes |
|---|---|---|
| `make check-desktop` | **PASS** | exit 0 |
| Wall time | ~1.8s real | well under 2 min |
| Pytest | 13 passed | 1 Starlette/httpx TestClient deprecation warning (upstream) |
| Secrets in notes | none | no vault / tokens / feed URLs with secrets |
| Soak 29961/29969 | **ALIVE** | verified after gate |

## Caveats (why not plain DONE)

- Windows packaging guide remains **stub-only** (Phase 3 deferred).
- Packaging product caveats still open elsewhere: Electron→DMG, `SSAK_BUNDLE_PYTHON=1` verified rebuild, real update feed (`BLOCKED_EXTERNAL`).
- Gate is a **sanity** gate for local agents — not a substitute for `make dmg` / GUI QA / phone LAN smoke.

## Docs touched

- `Makefile` — `check-desktop`
- `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` — Phase 8 checklist, §8/§10/§12
- `docs/packaging/MACOS_DMG_GUIDE.md` — short developer note
- `desktop/README.md` — short `make check-desktop` pointer
- this file

## Constraints observed

- C-03: soak not killed / not interfered with
- No push; no secrets/vault in commit
- No long Host start; no DMG build in the gate
