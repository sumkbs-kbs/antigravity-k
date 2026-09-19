---
title: Session checkpoint — desktop lane pause + EX-05 soak watch
date: 2026-09-15
tz: Asia/Seoul
branch: codex/m1-task-events
tip_sha: 1754db83bd134599e31c0cd40eb68c62cfed8f23
cr14_candidate: b6003205365606407cadfd6cbb1c813110beef0f
cr14_fingerprint: 02349a8d06945e438bdc60799ed770a87d6bb67d33d27f09b52008d242536ed6
status: DESKTOP_PAUSED_SOAK_WATCH
---

# Session checkpoint (2026-09-15)

## User decisions (this session)

| When | Decision |
|---|---|
| Sequential desktop | Follow `DESKTOP_SHELL_REFERENCE_PLAN.md`; always document for handoff |
| Product premise | Personal use + mobile via Host (`agk serve`); thin desktop shell (D-04/D-05) |
| Priority pick | `SSAK_BUNDLE_PYTHON=1` DMG rebuild + smoke (done) |
| **Pause** | **데스크톱 작업 여기까지. EX-05 soak만 감시** (강병석) |

## Git tip (unpushed)

- Branch: `codex/m1-task-events`
- Tip: `1754db83` — ABI-match `SSAK_BUNDLE_PYTHON` + verified DMG smoke
- **Do not push** unless asked. Do not commit `vault_data` / secrets / `dist/*.dmg`.

### Notable commits (desktop packaging lane)

| SHA | Summary |
|---|---|
| `1314d016` | Desktop shell reference plan |
| `814a4786` | Phase 0 + Phase 1 fail-closed start |
| `39144fc1` | Secret exclude + mobile Host premise |
| `52a02ef0` | dmg-smoke + network access-info + Settings mobile guide |
| `f0d34191` | Phase 1 residual — bundled Python opt-in |
| `5b8690e1` → `2980dc92` → `115c3729` | Phase 2 Electron shell → owned Host lifecycle → DONE-with-caveat |
| `dc7ff9ee` → `97e9f755` → `0816bb1e` | Phase 4 diagnostics + tray + recovery → DONE-with-caveat |
| `918b426a` → (close in `ddcf3599`) | Phase 5 update soft check → DONE-with-caveat |
| `ddcf3599` | Phase 5 close + Phase 6 Vite/port harden (8400→8000 defaults) |
| `1852913d` | Checkpoint handoff — Phase 6 close, defer 3/7 |
| `2457e467` | `make check-desktop` Phase 8 gate PASS |
| `1754db83` | `SSAK_BUNDLE_PYTHON=1` ABI fix + ~85M DMG smoke PASS |

## Phase status (single source: plan §10)

| Phase | Status |
|---|---|
| 0 | DONE |
| 1–2, 4–6, 8 | DONE-with-caveat |
| 3 | STUB-ONLY / DEFERRED |
| 7 | DEFERRED |

## Verified artifacts (local, gitignored binaries)

| Item | Result |
|---|---|
| DMG (no bundle py, earlier) | ~55M sha256 `262b54244a…` |
| DMG (`SSAK_BUNDLE_PYTHON=1`) | **~85M** path `dist/Ssak-Ai-0.1.0.dmg` sha256 `34f51420444b3930f4f7922c8226ffbd0c52a03039fdd90a05d0237de82e51c4` |
| Bundled Python | `Contents/Resources/python/bin/python3` → CPython **3.12.13** |
| `dmg-smoke` | PASS `:18080` auth=200 spa=200 (bundled py) |
| `make check-desktop` | PASS ~1.8s (13 pytest + updateChannels) |

## Explicitly NOT done / deferred

- Phone LAN/Tailscale E2E smoke
- Electron shell → DMG packaging
- Runtime rebind without Host restart; optional `port:0`
- Real update feed / signing (BLOCKED_EXTERNAL)
- Windows installer (Phase 3 deferred)
- CR-14 **GO** (still **NO-GO**)

## CR-14 / EX (separate lane)

| ID | Status |
|---|---|
| EX-01 | PARTIAL (local + NVIDIA + openrouter/free; others fail/partial) |
| EX-02 | PARTIAL (legal BLOCKED_EXTERNAL) |
| EX-03 | DONE — NOT_AVAILABLE |
| EX-04 | DONE (this macOS; matrix not promoted) |
| EX-05 | **IN_PROGRESS** — soak 28800s · pids `29961`/`29969` · workdir `…/run28800c` · output `…/val02_soak_28800.json` |
| EX-06 | DONE — no scope shrink |
| C14-08 / verdict | **NO-GO** — frozen candidate `b6003205` / fingerprint `02349a8d…` |

## Active watch

- EX-05 soak only until JSON lands; do not kill pids; do not restart soak casually.
- Routine `ex-05-8h-soak` (weekdays) remains for monitoring.
- Desktop packaging lane: **paused** until user resumes.

## Next agent (when user un-pauses desktop)

See plan §8.2 / §8.3. Prefer phone smoke **or** Electron→DMG per user priority. Always update this plan + `notes/*` and prefer docs commits.

## EX-05 outcome (added later same day)

- **FAIL** — SC-6 RSS growth 1654.9 MB ≫ 64 MB threshold; SC-1..5 PASS; full 8h completed.
- JSON: `.omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/val02_soak_28800.json`
- Investigation: `docs/ga/notes/EX05_SC6_RSS_INVESTIGATION_2026-09-15.md`
- CR-14 still **NO-GO**. Desktop still paused. Soak watch routine paused.
