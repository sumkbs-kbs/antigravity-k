---
title: Personal use + mobile Host premise
date: 2026-09-15
tz: Asia/Seoul
plan: docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md
---

# Premise (user 2026-09-15)

Ssak-Ai is **primarily for personal use**, but must work **conveniently from mobile** as well.

## Product shape

| Surface | Role |
|---|---|
| **Host (`agk serve`)** | Canonical product: HTTP + WS + SPA (`dashboard_dist`). Mobile and desktop browsers talk here. |
| **Desktop shell** | Thin helper (tray / start-stop / updates). Must **not** trap UI in Electron-only/`file://`. |
| **Mobile** | Same Host URL on LAN or Tailscale (or similar). PIN/token required when not loopback. |
| **Future native app** | Optional; reuse same API — do not fork a second backend. |

## Security defaults (personal + mobile)

1. Default bind: `127.0.0.1` (local desktop).
2. Mobile access: explicit setting to bind LAN / Tailscale interface — never silent `0.0.0.0`.
3. Non-loopback ⇒ credential gate (PIN / bearer) mandatory.
4. Secrets stay in user data dirs; **never** inside DMG/app bundle (`.env` / `auth_hash`).

## Impact on phases

- Phase 1–2: packaging/shell stay Host-serving.
- Phase 6: elevate **mobile bind + auth** checklist (personal LAN/Tailscale first, not multi-tenant SaaS).
- Do not optimize for public internet exposure or multi-user tenancy.
