# Update channels (stable / beta)

**Phase:** 5 (desktop shell)  
**Date:** 2026-09-15 (Asia/Seoul)  
**Decision:** **D-03** — update check source = **GitHub Releases stub** (personal-use default; live signing/CDN = `BLOCKED_EXTERNAL`)

This document defines the product **update channel** model for the thin Electron shell. It is **not** a Cordis/DSH transplant.

## Channel model

| Channel | Meaning | Typical consumers |
|---|---|---|
| `stable` | Default product track | Everyday personal installs |
| `beta` | Pre-release / experimental track | Opt-in testers |

### Git branch ≠ channel

- A Git branch name (`main`, `codex/m1-task-events`, `release/*`) is a **development** axis.
- A product channel (`stable` / `beta`) is a **distribution** axis on the update feed.
- Mapping branch → channel is a **release process** choice (CI/tagging), never an automatic equality in the client.
- Clients must **not** infer channel from `git rev-parse --abbrev-ref HEAD`.

## Client configuration

| Item | Value |
|---|---|
| Feed URL env | **`SSAK_UPDATE_FEED`** |
| Unset / empty | Soft message **「업데이트 서버 미구성」** — **not** a crash / not an error dialog severity for “broken app” |
| Default channel | `stable` (until UI picker exists) |
| Auto-install | **Off by default** — this Phase only soft-checks and displays; download/install requires explicit future UX |

Override for tests: pass an explicit feed URL into `desktop/updateChannels.js` helpers (tray uses env only).

## Request / response contract (sketch)

### Request (client → feed)

Conceptual query (HTTP GET to `SSAK_UPDATE_FEED`):

| Field | Where | Notes |
|---|---|---|
| `channel` | query + header `X-Ssak-Desktop-Channel` | `stable` \| `beta` |
| `current` | query (optional) | Installed app version string |

GitHub Releases stub (D-03): feed may be a static JSON artifact attached to a Release, or a tiny redirector that serves the same shape. The shell does **not** scrape HTML release pages in this slice.

### Response (feed → client)

JSON object. **Channel echo is mandatory.**

```json
{
  "channel": "stable",
  "version": "0.1.1",
  "notes": "optional human summary",
  "url": "optional artifact or release page URL"
}
```

| Rule | Behavior |
|---|---|
| Channel echo | `response.channel` must equal requested channel |
| Cross-channel | **Reject** (`CHANNEL_MISMATCH`) — e.g. client asked `stable`, feed returned `beta` |
| Unknown channel string | Treat as mismatch / invalid |
| Soft check only | Client **never** auto-downloads or auto-installs in this Phase |

Fixture examples: `desktop/fixtures/update_feed_stable.json`, `desktop/fixtures/update_feed_beta.json`.

## Tray UX (this slice)

Menu item: **업데이트 확인…**

1. If `SSAK_UPDATE_FEED` unset → info dialog: **업데이트 서버 미구성**
2. If set → fetch JSON, validate channel echo, show result (ok / no_update / error)
3. No download, no installer launch, no silent background install

## BLOCKED_EXTERNAL

| Topic | Status | Notes |
|---|---|---|
| Code signing / notarization | **BLOCKED_EXTERNAL** | Apple/Windows cert + notarization outside this repo turn |
| CDN / release hosting SLA | **BLOCKED_EXTERNAL** | GitHub Releases is a stub source; production CDN TBD |
| Auto-updater frameworks (e.g. electron-updater full pipeline) | Deferred | Prefer explicit confirm → save → open DMG/installer later |

## Decision pointer

See plan §9 **D-03**: GitHub Releases **stub** for Ssak personal use (vs placeholder self-hosted). Live public feed URL may remain unset until a Release JSON is published; unset continues to show 「업데이트 서버 미구성」.

## Related

- Plan: `docs/packaging/DESKTOP_SHELL_REFERENCE_PLAN.md` § Phase 5 / §9 / §10
- Progress: `docs/packaging/notes/phase5_progress.md`
- Module: `desktop/updateChannels.js`
- Test: `node desktop/test_updateChannels.js`
