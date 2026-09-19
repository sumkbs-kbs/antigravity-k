---
title: "GA marketing claims and third-party review register"
status: planning-control
date: 2026-09-06
tags: [ga, gov-01, marketing, legal, licenses, telemetry]
controlling_adr: docs/adr/0003-ga-product-scope.md
---

# GA marketing claims and third-party review register

This `GOV-01` register maps every market-facing claim to a release gate and
evidence. “Pending” and “blocked” are deliberate outcomes: configuration,
historical reports, and a prior SHA do not substitute for approval.

Scope dimensions from ADR-0003 — including concurrent-user capacity
(동시 사용자 수) and data sensitivity (데이터 민감도) — are claim-gated
in the matrix below. Unverified capacity or sensitivity claims stay blocked.

## Claim-to-gate matrix

| Proposed claim | Current disposition | Required gate/evidence | Owner |
|---|---|---|---|
| “Local-first desktop operator experience” | Allowed only as a target-scope statement | ADR-0003; current candidate scope review | Product owner |
| “Self-hosted single tenant” | Allowed only as a target-scope statement | ADR-0003 plus single-tenant staging/operations evidence | Product + operations |
| “Supported on macOS or Linux” | Blocked | Support-matrix row promoted by candidate-SHA staging, install, restart, and restore evidence | Release coordinator |
| “Supports Windows, CUDA, or native desktop” | Prohibited | New scope ADR and completed platform validation | Product + release |
| “Supports Ollama, LM Studio, MLX, or cloud providers” | Blocked as a support claim | Per-provider candidate-SHA staging and reviewed terms/privacy record | Release + legal |
| “Private,” “local,” or “your data never leaves your device” | Blocked (`BLOCKED_EXTERNAL`: legal approver) | Egress inventory, selected-provider UI disclosure, log/export review, and legal approval | Privacy + security |
| “Secure” or “enterprise-ready” | Blocked (`BLOCKED_EXTERNAL`: security approver) | Security release gate and approval at the same candidate SHA | Security owner |
| “Delete/export your data” | Blocked as an unqualified claim (`BLOCKED_EXTERNAL`: operations rehearsal) | Complete-store delete/export/backup-copy matrix, redaction and restore/delete rehearsal | Data + operations |
| “No telemetry” | Blocked (`BLOCKED_EXTERNAL`: privacy approval) | Outbound inventory, telemetry disclosure, opt-out behavior, and approval | Privacy + security |
| “SLA,” “uptime,” “RPO,” or “RTO” | Prohibited | Approved SLO, monitoring, incident/support runbook, and restore rehearsal | Operations owner |
| “Multi-tenant SaaS” | Prohibited | SaaS expansion gate in ADR-0003 fully implemented and verified before RC-01 | Product + security |
| “Supports N concurrent users” / multi-seat capacity | Prohibited until verified; current disposition is single-operator only | `VAL-02` concurrency/load evidence at candidate SHA plus release-coordinator approval; ADR-0003 concurrent-user boundary | Product + release + security |
| “Approved for regulated / high-sensitivity data” (PHI, PCI, classified, children’s, special-category) | Prohibited | Legal + privacy + security approval and a scoped ADR/SKU update before RC-01 | Legal + privacy + security |
| “PII-ready” / GDPR or PIPA compliance claim | Blocked (`BLOCKED_EXTERNAL`: legal/privacy approver) | Legal/privacy review artifact naming scope, lawful basis, and evidence | Legal/privacy owner |
| “The VS Code IDE sync keeps the editor and the dashboard in step” | Allowed only as the documented context-sync companion scope | Behaviour contract read from `vscode-extension/src/extension.ts` and stated in `vscode-extension/README.md`: one request in flight, errors recorded, retried on the next editor event, **no background reconnection timer and no offline queue**. The narrower scope and the out-of-scope statement are contract, not marketing. | Extension/IDE owner (`CR-12` evidence) |

“Companion”, “syncs context”, and “reads the current file/cursor” are allowed for the
extension only with the same limits. Claims that the extension reconnects, buffers,
or keeps working while the engine is down are **prohibited** until a background retry
contract exists and is verified.

## Third-party license, model, and provider review register

| Subject | Current evidence | Review required | State | Owner / release blocker |
|---|---|---|---|---|
| Project license and bundled notices | `LICENSE`, `NOTICE`, `THIRD_PARTY_PROVENANCE.toml`, and `src/antigravity_k/release/THIRD_PARTY_NOTICES.txt` exist | Confirm shipped artifact notices and any attribution obligations | Pending (`BLOCKED_EXTERNAL`: legal approver) | Release/legal; REL-03 evidence |
| Python and dashboard dependencies | Release policy requires SBOM/notice generation; bundled notices include entries with unavailable license metadata | Resolve unavailable/ambiguous metadata and confirm generated SBOM/NOTICE for candidate artifacts | Pending (`BLOCKED_EXTERNAL`: legal sign-off) | Release/legal; REL-03 evidence |
| Ollama runtime and selected local model | Local endpoint/profile is configured | Review runtime, registry/model, redistribution, and acceptable-use terms for each marketed model | Pending (`BLOCKED_EXTERNAL`) | Legal; provider approval artifact |
| MLX and selected MLX model | MLX extra/profile is configured | Review package/model terms and Apple-Silicon distribution implications | Pending (`BLOCKED_EXTERNAL`) | Legal; provider approval artifact |
| LM Studio runtime and selected model | Loopback compatible profile is configured | Review runtime/model terms and local-server credential handling | Pending (`BLOCKED_EXTERNAL`) | Legal; provider approval artifact |
| OpenRouter | Endpoint/profile is configured | Review current service terms, privacy/data processing, model-routing disclosures, pricing, and acceptable use | Pending (`BLOCKED_EXTERNAL`) | Legal; provider approval artifact |
| NVIDIA NIM | Endpoint/profile is configured | Review current service terms, privacy/data processing, quotas, pricing, and acceptable use | Pending (`BLOCKED_EXTERNAL`) | Legal; provider approval artifact |
| OpenAI, Google Gemini, ZAI | Endpoints/profiles are configured | Review current terms, privacy/data processing, regional/data-use implications, pricing, and acceptable use | Pending (`BLOCKED_EXTERNAL`) | Legal; provider approval artifact |
| Telemetry/analytics destinations | Runtime telemetry/audit signals exist; no GOV-01 outbound inventory or legal approval is recorded | Inventory every destination/field/retention/control and approve disclosure text | Pending (`BLOCKED_EXTERNAL`) | Privacy + security; OBS-01 evidence |

## Disposition vocabulary

| Disposition | Meaning | Who can change it |
|---|---|---|
| `Allowed` | Usable in market-facing copy at the current candidate SHA. | Release coordinator after same-SHA evidence. |
| `Allowed only as a target-scope statement` | May be described with “target”, “planned”, or “evaluation”, never as delivered capability. | Product owner. |
| `Blocked` | Implementation may exist, but no claim until the required gate passes. | Release coordinator. |
| `Prohibited` | Must not appear in copy; the scope is excluded by ADR-0003. | Product + security; scope change needs a new ADR. |
| `Pending` | Review requested, no artifact recorded yet. | Named owner. |
| `BLOCKED_EXTERNAL` | The remaining condition is **outside this repository's control** — an external approver (legal, privacy, security), a credential, hardware, or a provider’s current terms. | Only the named external approver can clear it. |

`BLOCKED_EXTERNAL` is a preserved open blocker, not a soft state. A chat summary, a
configuration entry, an open-source license, or an older review never clears it, and
it must stay visible in the final GO/NO-GO decision. Rows marked
`BLOCKED_EXTERNAL` without a named approver are incomplete and must be fixed rather
than approved. Technical work continues in parallel; the blocker is recorded so the
release decision cannot silently treat it as done.

## Approval rules

- An approval record must identify the reviewer, date, candidate SHA (where
  applicable), scope/provider/model, evidence location, and expiry/review date.
- Legal review cannot be inferred from an open-source license, a provider
  configuration, a README statement, or an older audit.
- The release coordinator must reject marketing copy whose disposition is
  blocked or prohibited. `RC-01` remains controlled by
  [ADR-0003](../adr/0003-ga-product-scope.md).
- Every claim row must keep at least one repository-relative evidence path that
  actually exists (`docs/ga/GA_SUPPORT_MATRIX.md`, `vscode-extension/README.md`).
  `tests/test_cr12_docs_alignment.py` enforces this so a mapping cannot decay into
  prose after the file it cites is renamed.

For storage and responsibility details, see
[GA data, privacy, and operations](GA_DATA_PRIVACY_OPERATIONS.md); for the
platform/provider classifications, see the [GA support matrix](GA_SUPPORT_MATRIX.md).
