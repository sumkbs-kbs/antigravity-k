---
title: Desktop shell Phase 6 progress (ports / origin / mobile Host)
date: 2026-09-15
tz: Asia/Seoul
status: DONE-with-caveat
---

# Phase 6 progress — ports, origin, settings, personal mobile / LAN

## Status

**DONE-with-caveat** (checkpoint 2026-09-15 KST)

Caveats (open, do not block this close):
1. Phone browser LAN/Tailscale E2E smoke **not run**
2. Optional `port: 0` random + last-success memory **not done**
3. Runtime rebind without Host restart **not done**

## Premise
See `mobile_host_premise.md` (D-04/D-05). Default bind remains loopback.

## Done

### Mobile / LAN (earlier)
- [x] `GET /api/network/access-info` — bind posture, LAN IPv4 hints, restart command, `mobile_bind_default: false`
- [x] Settings “모바일·LAN 접속” panel — guide toggle **default OFF** (localStorage `agk_mobile_lan_guide`)
- [x] pytest `tests/test_network_access_api.py` PASS
- [x] Document that actual bind change still requires Host restart with `--host 0.0.0.0` (startup_security requires PIN off-loopback)
- [x] `notes/mobile_host_premise.md`와 Settings 카피 정렬

### Port / origin / Vite harden
- [x] **Product path = single loopback** — Host (`agk serve`) serves API + SPA from `src/antigravity_k/dashboard_dist` (StaticFiles). Electron default `SSAK_HOST_URL=http://127.0.0.1:8000`. No Vite in product.
- [x] **Dev Vite proxy health** — `dashboard/vite.backendHealth.ts` + plugin in `vite.config.ts`: one startup probe of proxy target; **loud warning** if unreachable; **loud warning** if target still uses legacy `:8400`. Default target `http://127.0.0.1:8000`. Does **not** kill Vite on 5173/5174.
- [x] **8400 → 8000 defaults** — `ServerConfig.port` default **8000**; mcp_oauth redirect fallback; agent_bridges example default; `docs/09_OPERATION_GUIDE.md` examples. Vite already defaulted to 8000 (no silent 8400 in `vite.config.ts`).
- [x] **Port-in-use hints** — Phase 4 recovery `suspectPortConflict` + dialog text already present; reinforced in `DIAGNOSTICS.md` Phase 6 port notes.
- [x] **Settings save smoke (doc + existing pytest)** — authenticated `/api/settings/env` **200** path covered by `tests/test_cr05_settings_secret_contract.py` (TestClient + allow gate; no live secrets/vault). See also `tests/test_phase6_settings_env_smoke.py` thin pointer test.

## Caveats / not done (carry forward)
- [ ] Runtime toggle that rebinds without restart (out of scope for now) — **caveat**
- [ ] Phone browser end-to-end smoke on real LAN/Tailscale (needs user network) — **caveat**
- [ ] DMG launcher reading mobile pref (optional later)
- [ ] (optional) `port: 0` random + last-success memory — **caveat**

## Constraints
- No CR-14 GO claim (still NO-GO)
- No push
- Do not kill soak 29961/29969
- No secrets / vault
