---
title: Desktop shell Phase 6 progress (mobile Host)
date: 2026-09-15
tz: Asia/Seoul
---

# Phase 6 progress — personal mobile / LAN

## Premise
See `mobile_host_premise.md` (D-04/D-05). Default bind remains loopback.

## Done
- [x] `GET /api/network/access-info` — bind posture, LAN IPv4 hints, restart command, `mobile_bind_default: false`
- [x] Settings “모바일·LAN 접속” panel — guide toggle **default OFF** (localStorage `agk_mobile_lan_guide`)
- [x] pytest `tests/test_network_access_api.py` PASS
- [x] Document that actual bind change still requires Host restart with `--host 0.0.0.0` (startup_security requires PIN off-loopback)

## Not done
- [ ] Runtime toggle that rebinds without restart (out of scope for now)
- [ ] Phone browser end-to-end smoke on real LAN/Tailscale (needs user network)
- [ ] DMG launcher reading mobile pref (optional later)
