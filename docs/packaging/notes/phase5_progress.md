# Phase 5 progress — Update channels (stable / beta)

**Date:** 2026-09-15 (Asia/Seoul)  
**Branch:** `codex/m1-task-events`  
**Status:** **DONE-with-caveat**  
**Plan:** `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` § Phase 5 / §9 D-03 / §10 / §12

## Decision

| ID | Choice | Rationale |
|---|---|---|
| **D-03** | **GitHub Releases stub** (not self-hosted placeholder) | Ssak personal use; existing remote `sumkbs-kbs/antigravity-k`; no live signed CDN yet |

## What landed (minimal slice)

| Path | Role |
|---|---|
| `docs/packaging/UPDATE_CHANNELS.md` | Channel model, Git≠channel, request/response sketch, env, BLOCKED_EXTERNAL |
| `desktop/updateChannels.js` | Soft check + channel echo / cross-channel reject |
| `desktop/fixtures/update_feed_*.json` | Fixture feed shapes |
| `desktop/test_updateChannels.js` | Tiny unit/fixture test (channel-echo) |
| `desktop/main.js` | Tray **업데이트 확인…** |

## Env / behavior

| Item | Behavior |
|---|---|
| **`SSAK_UPDATE_FEED`** | Feed JSON URL |
| Unset / empty | Dialog message **「업데이트 서버 미구성」** — soft info, not a crash |
| Set | Fetch JSON → validate channel echo → show result; **never** auto-download/install |

## Smoke (2026-09-15 KST)

| Check | Result |
|---|---|
| `node desktop/test_updateChannels.js` | **OK** (echo + mismatch reject + unconfigured) |
| Soft check env unset | `status=unconfigured`, message `업데이트 서버 미구성` |
| `node --check desktop/main.js` / `updateChannels.js` | **ok** |
| Soak `29961`/`29969` | **Alive** (untouched) |

## Caveats / deferred (why DONE-with-caveat)

| Item | Status |
|---|---|
| Real GitHub Releases JSON feed / default feed URL | **BLOCKED_EXTERNAL** / deferred (unset feed remains valid soft path) |
| Confirm → download → open DMG/installer UX | **DEFERRED** |
| Code signing / notarization / CDN | **BLOCKED_EXTERNAL** |
| Background silent check | Deferred (tray soft check done) |
| Beta↔stable side-by-side menu | Optional / scope-out later |

## Constraints

- No CR-14 GO claim
- No push
- Do not kill soak 29961/29969
- No secrets
