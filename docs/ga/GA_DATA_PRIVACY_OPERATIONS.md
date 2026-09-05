---
title: "GA data, privacy, and operations boundary"
status: planning-control
date: 2026-09-06
tags: [ga, gov-01, privacy, retention, operations]
controlling_adr: docs/adr/0003-ga-product-scope.md
---

# GA data, privacy, and operations boundary

This document is the user-data and operating contract for the single-tenant
scope in [ADR-0003](../adr/0003-ga-product-scope.md). It records implemented
storage signals separately from unapproved policy promises. It does not assert
legal approval or that a delete reaches every copy.

## Data flow and storage

| Data class | Flow | Observed/configured locations | Scope limitation |
|---|---|---|---|
| Prompts, responses, tool requests, workspace content | Operator browser/CLI → Ssak-Ai runtime → selected provider/runtime | Runtime memory; local workspace; provider request if a cloud provider is selected | Cloud selection sends data to that provider; provider retention is outside this product's control. |
| Vault notes and RAG persistence | Runtime → Git-first vault / vector store | `vault_data`; default Chroma path `vault_data/.chroma`; Kubernetes mounts `/app/vault_data` | Exact host path is operator configured; project/tenant isolation is not yet a GA verification claim. |
| Logs and audit events | Runtime → local log/audit storage | `.env.example` defaults to `logs/agent_json.log`; Docker creates `/app/logs`; Kubernetes mounts `/app/logs` as ephemeral `emptyDir` | Content, rotation, redaction, and export coverage require release-candidate verification. |
| Application state and credentials | Runtime → application data / operator secret store | Docker creates `/app/data`; Kubernetes mounts `/app/data`; provider keys and PIN are environment/secret inputs | Secrets must not be put in documentation, evidence, logs, or exports. Customer controls its secret store. |
| Project alias/configuration | CLI/runtime → workspace-local metadata | README identifies `.antigravity/memory/project_aliases.json` | Scope, persistence, and deletion coverage must be demonstrated by DAT-01–03. |

## Retention, deletion, export, and backup-copy rules

| Operation | Current state | Customer-facing rule until approval | Blocking evidence / owner |
|---|---|---|---|
| Retention | APIs and provider methods exist, but no approved product schedule or complete-store inventory is evidenced. | Do not promise a default retention period. The operator sets and verifies its own storage lifecycle. | DAT-01–03 complete-store inventory and retention test; data owner. |
| Delete/purge | Memory and vault-privacy routes are implemented, but this is not evidence of every derived store, remote provider copy, or backup copy. | Describe deletion as a request to remove in-scope live local data only after the final policy identifies the stores. Do not promise erasure from backups or cloud providers. | DAT-01–03 delete matrix, provider handling, and restore/delete rehearsal; data + legal owner. |
| Export | Vault/memory export capabilities exist; vault export defaults to redaction and excludes assets unless enabled. | Export must be treated as sensitive data. Operator controls the destination and verifies redaction before transfer. | DAT-01–03 coverage report and manual export/redaction test; data owner. |
| Backups | Docker/Kubernetes persistent volumes make operator backups possible; no product-operated backup service or restore rehearsal is approved. | Customer owns backup selection, encryption, retention, and deletion of backup copies. A delete does not erase prior operator backups. | OPS restore/delete rehearsal, retention policy, and owner sign-off. |

## Required notices and telemetry disclosure

Before GA, the product must disclose on first use and in release notes:

1. The selected inference provider and whether data leaves the operator's
   environment; this must change with provider selection.
2. Categories and locations of stored content, logs, vector data, and
   operator-managed backups.
3. The local retention/delete/export limitations in the table above, including
   that external providers and prior backups have separate controls.
4. Any telemetry destination, fields, purpose, retention, opt-in/opt-out
   behavior, and the method to disable it. “No telemetry” is not marketable
   until an outbound inventory and release-candidate proof are approved.
5. Links to the reviewed provider/model terms and privacy notices for the
   selected provider.

No current GOV-01 legal or privacy approval exists. The [review register](GA_CLAIMS_AND_REVIEW_REGISTER.md)
tracks the required approvals.

## Support and responsibility boundary

Ssak-Ai support has no approved availability or response-time SLO at this
stage. No SLA, uptime percentage, RPO, or RTO may be offered until an
operations owner approves a measured service objective and restore rehearsal.

| Responsibility | Ssak-Ai release/support owner | Customer/operator |
|---|---|---|
| Product release | Publish reviewed artifacts and documented configuration | Choose whether and when to install an eligible release. |
| Host/network/identity | Document requirements and known limits | Secure host, ingress, DNS/TLS, identity, firewall, and provider account. |
| Data and backups | Provide accurate lifecycle limitations and test evidence | Classify data, configure storage and secrets, retain/erase backups, and validate restores. |
| Cloud-provider use | Surface selected provider and disclosure requirement | Accept provider terms, configure credentials, and determine whether data may be sent. |

Operational claims are governed by the [claim matrix](GA_CLAIMS_AND_REVIEW_REGISTER.md)
and platform/provider claims by the [support matrix](GA_SUPPORT_MATRIX.md).
