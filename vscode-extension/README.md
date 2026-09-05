# Antigravity-K IDE Sync

VS Code extension for syncing workspace file edit and cursor events with the Antigravity-K engine.

## Features

- Real-time IDE synchronization with Antigravity-K local engine
- Debounced editor change events
- Automatic reconnection and offline support

## Extension Settings

This extension contributes the following settings:

* `antigravityK.ideSync.port`: Listener port for sync events (default: `54321`)
* `antigravityK.ideSync.debounceMilliseconds`: Debounce interval in ms (default: `100`)
* `antigravityK.ideSync.requestTimeoutMilliseconds`: Sync request timeout in ms (default: `1000`)
