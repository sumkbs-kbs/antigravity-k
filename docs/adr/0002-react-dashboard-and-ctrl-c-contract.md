# ADR 0002: React Dashboard and Ctrl-C Contract

Status: Accepted

Date: 2026-08-22

## Decision

The React + TypeScript + Vite application in `dashboard/` is the only supported web dashboard implementation. A `dashboard-vanilla/` source tree is deprecated and excluded from the release distribution inventory. Historical analysis documents may describe the retired implementation, but runtime, contributor, and product documentation must identify the React dashboard.

The Textual workbench owns Ctrl-C with an ordered contract:

1. A non-empty input is cleared without cancelling work or exiting.
2. With empty input and an active task, the task worker group is cancelled and the app remains open.
3. With empty input and no active task, the app exits.

Ctrl-Q remains the explicit unconditional exit shortcut.

## Consequences

- No second frontend runtime, state store, or build output is introduced.
- Inline dashboard scripts are forbidden by CSP; React bootstrapping remains in `src/main.tsx`.
- Thread workers must observe Textual cancellation before publishing results.
