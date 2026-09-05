---
title: "ADR-0004: RequestExecutionContext and project/conversation authority"
status: accepted
date: 2026-09-06
owners: [architecture, backend-contract]
tags: [adr, arc-01, execution-context, project-registry, conversation-revision]
---

# ADR-0004: RequestExecutionContext and project/conversation authority

## Decision

`ARC-01` freezes an immutable typed `RequestExecutionContext` as the shared
authority for chat, task, tool, memory, and RAG execution. The server resolves
`project_id → canonical_project_root` through the project registry. A
client-supplied filesystem path is **not** execution authority.

Conversation mutations carry `conversation_id` plus an expected
`conversation_revision`. The server conversation store is authoritative and
uses compare-and-set (CAS). Stale revisions return HTTP 409 with typed error
code `stale_conversation_revision`.

## Context fields (frozen)

| Field | Authority |
|---|---|
| `request_id` | Per-request correlation |
| `task_id` | Optional bound task |
| `project_id` | Registry key; sole project identity for execution |
| `canonical_project_root` | Server-resolved absolute realpath from registry |
| `conversation_id` / `conversation_revision` | Authoritative store + CAS expected head |
| `actor_subject` / `session_id` | Operator and session binding |
| `model_id` | Selected model for the request |

Schema version: `RequestExecutionContext.schema_version = 1`.

## Legacy paths: migration and removal

### Legacy behavior (pre-ARC-01)

- `filesystem.WORKSPACE_ROOT` module global mutated by `POST /api/workspace` and
  project switch (`set_workspace`).
- Clients and tools often treated the active global root or a raw path as the
  workspace for chat/file/shell.
- Project switch could change the root observed by an in-flight request.

### Migration rules

1. **New mutating chat/task/tool requests** must include `project_id` (wire type
   `RequestExecutionContextWire`). WS-01 binds routes to
   `resolve_request_execution_context`.
2. **`client_hint_path`** on the wire is optional diagnostics only; resolvers
   must ignore it for authority (`reject_raw_path_authority`).
3. **`POST /api/projects`** may still accept a path to *register* a project.
   After registration, execution uses the issued `project_id` only.
4. **`POST /api/workspace`** and global `WORKSPACE_ROOT` mutation remain
   temporarily for read-compatibility during WS-01, but must not be the source
   of truth for new execution paths. WS-01 removes singleton root mutation from
   the execution hot path.
5. Dashboard stores send `project_id` + conversation revision on every chat/task
   request (WS-04 / CTX-01).

### Removal criteria

Global `WORKSPACE_ROOT` mutation and path-as-authority request fields are
removed when:

- WS-01 integration tests prove A/B concurrent requests never share roots via
  the global.
- WS-02 tools execute only under `canonical_project_root`.
- CTX-01 conversation CAS is live and dashboard no longer depends on
  path-only workspace switches for chat identity.

Until those tasks merge, legacy endpoints may exist but ARC-01 contract tests
forbid treating raw paths as execution authority.

## Typed errors (frozen HTTP mapping)

| Code | HTTP | Meaning |
|---|---|---|
| `missing_execution_context` | 400 | Required context fields absent |
| `invalid_execution_context` | 400 | Wire/validation failure or raw-path authority |
| `invalid_conversation_revision` | 400 | Revision < 0 or malformed |
| `project_not_found` | 404 | Unknown `project_id` |
| `conversation_not_found` | 404 | Unknown conversation under project |
| `project_root_invalid` | 403 | Missing dir, escape, or non-directory root |
| `stale_conversation_revision` | 409 | CAS expected ≠ current |

## Consequences

- WS-01 / WS-02 / WS-04 / CTX-01 consume this contract; they do not redefine
  field names, revision semantics, or error codes.
- Frozen fixtures live under `tests/fixtures/commercial_ga/arc01_request_execution_context.json`
  and are mirrored for the dashboard schema tests.
- This ADR does not implement request-scoped DI or conversation persistence;
  those belong to WS-01 and CTX-01.

## Related

- Plan: `docs/11_COMMERCIAL_GA_100_PLAN.md` · ARC-01
- Checklist: `docs/12_COMMERCIAL_GA_100_CHECKLIST.md` · ARC-01
- Product scope: `docs/adr/0003-ga-product-scope.md`
