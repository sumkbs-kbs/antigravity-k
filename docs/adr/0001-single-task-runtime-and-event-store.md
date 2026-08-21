# ADR 0001: One task runtime and one task event store

## Status

Accepted

## Context

Task execution previously accumulated several streaming and UI-level event
paths. A second task runtime or event database would make resume, replay, and
audit ordering ambiguous: one system could report completion while another still
holds a different event cursor.

## Decision

There is one canonical task runtime and one durable task/event database:
`BackgroundTaskRunner` with `TaskStateStore`, whose task rows, checkpoints, and
`task_execution_events` live in the same SQLite database. SSE, WebSocket, React,
CLI, and audit consumers are projections of that ledger and do not own task
state or event sequence numbers.

Auxiliary domain stores such as audit, resource reservations, wiki, and vector
indexes may exist only when they do not own task status or execution events.
Their IDs may be correlated through event metadata, but task truth remains in
the canonical store.

## Consequences

Adding another task runtime, event broker, or event table requires a new ADR
and a migration that proves old and new replay parity. Client state is
disposable; reconnecting clients replay strictly after the last event sequence.
This also keeps resume and cancel semantics testable against one persistence
boundary.
