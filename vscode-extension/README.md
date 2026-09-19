# Ssak-Ai IDE Sync

VS Code context-sync companion for Ssak-Ai. It **sends editor context to the local Ssak-Ai engine**; it is not a control channel for the engine and it does not replace the dashboard.

## What it actually does

- On editor events, `POST http://127.0.0.1:<port>/update` with `{active_file, cursor_line, open_files}`.
  Events: active editor change, cursor/selection change, document change, and changes to this extension's settings.
- Debounces rapid events into one request (`antigravityK.ideSync.debounceMilliseconds`, default 100 ms, clamped to 5000).
- Keeps **one request in flight**. A newer send destroys the previous request, so an in-flight response for a superseded state is ignored.
- Request timeout `antigravityK.ideSync.requestTimeoutMilliseconds` (default 1000 ms, clamped to 100–30000). On failure it records the error and writes it to the `Ssak-Ai IDE Sync` output channel.

## Retry behaviour (read this before trusting a failure message)

There is **no background reconnection timer and no offline queue**. If the engine is down, the sync fails and is **retried on the next editor event** — the extension does not buffer state and does not replay anything afterwards. So:

- A transient "last error" in the status command does not mean state is lost; the next cursor move or edit re-sends the current context.
- If you open a file while the engine is down and then stop editing, nothing is re-sent until the next event. Start typing or move the cursor once the engine is back, or run the status command to confirm.
- Setting up a reconnect timer or an offline queue is **out of scope here** and would be a separate, explicitly designed task.

## Status

Run **"Ssak-Ai: Show IDE Sync Status"** (`antigravity-k-sync.showStatus`) to see the last synchronized `file:line` or the last error. The same messages go to the `Ssak-Ai IDE Sync` output channel.

## Extension Settings

* `antigravityK.ideSync.port`: Listener port for sync events (default: `54321`)
* `antigravityK.ideSync.debounceMilliseconds`: Debounce interval in ms (default: `100`)
* `antigravityK.ideSync.requestTimeoutMilliseconds`: Sync request timeout in ms (default: `1000`)

## Evidence for these statements

The behaviour above is read directly from `src/extension.ts` (`scheduleSend`, `sendState`, `configuration`, `currentState`, `stop`). Claim-to-evidence mapping and the review status of the extension's marketing surface live in
[`docs/ga/GA_CLAIMS_AND_REVIEW_REGISTER.md`](../docs/ga/GA_CLAIMS_AND_REVIEW_REGISTER.md).
