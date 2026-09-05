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
| “Private,” “local,” or “your data never leaves your device” | Blocked except for a narrowly qualified, selected-local-provider disclosure | Egress inventory, selected-provider UI disclosure, log/export review, and legal approval | Privacy + security |
| “Secure” or “enterprise-ready” | Blocked | Security release gate and approval at the same candidate SHA | Security owner |
| “Delete/export your data” | Blocked as an unqualified claim | Complete-store delete/export/backup-copy matrix, redaction and restore/delete rehearsal | Data + operations |
| “No telemetry” | Blocked | Outbound inventory, telemetry disclosure, opt-out behavior, and approval | Privacy + security |
| “SLA,” “uptime,” “RPO,” or “RTO” | Prohibited | Approved SLO, monitoring, incident/support runbook, and restore rehearsal | Operations owner |
| “Multi-tenant SaaS” | Prohibited | SaaS expansion gate in ADR-0003 fully implemented and verified before RC-01 | Product + security |
| “Supports N concurrent users” / multi-seat capacity | Prohibited until verified; current disposition is single-operator only | `VAL-02` concurrency/load evidence at candidate SHA plus release-coordinator approval; ADR-0003 concurrent-user boundary | Product + release + security |
| “Approved for regulated / high-sensitivity data” (PHI, PCI, classified, children’s, special-category) | Prohibited | Legal + privacy + security approval and a scoped ADR/SKU update before RC-01 | Legal + privacy + security |
| “PII-ready” / GDPR or PIPA compliance claim | Blocked | Legal/privacy review artifact naming scope, lawful basis, and evidence | Legal/privacy owner |

## Third-party license, model, and provider review register

| Subject | Current evidence | Review required | State | Owner / release blocker |
|---|---|---|---|---|
| Project license and bundled notices | `LICENSE`, `NOTICE`, `THIRD_PARTY_PROVENANCE.toml`, and `src/antigravity_k/release/THIRD_PARTY_NOTICES.txt` exist | Confirm shipped artifact notices and any attribution obligations | Pending | Release/legal; REL-03 evidence |
| Python and dashboard dependencies | Release policy requires SBOM/notice generation; bundled notices include entries with unavailable license metadata | Resolve unavailable/ambiguous metadata and confirm generated SBOM/NOTICE for candidate artifacts | Pending | Release/legal; REL-03 evidence |
| Ollama runtime and selected local model | Local endpoint/profile is configured | Review runtime, registry/model, redistribution, and acceptable-use terms for each marketed model | Pending | Legal; provider approval artifact |
| MLX and selected MLX model | MLX extra/profile is configured | Review package/model terms and Apple-Silicon distribution implications | Pending | Legal; provider approval artifact |
| LM Studio runtime and selected model | Loopback compatible profile is configured | Review runtime/model terms and local-server credential handling | Pending | Legal; provider approval artifact |
| OpenRouter | Endpoint/profile is configured | Review current service terms, privacy/data processing, model-routing disclosures, pricing, and acceptable use | Pending | Legal; provider approval artifact |
| NVIDIA NIM | Endpoint/profile is configured | Review current service terms, privacy/data processing, quotas, pricing, and acceptable use | Pending | Legal; provider approval artifact |
| OpenAI, Google Gemini, ZAI | Endpoints/profiles are configured | Review current terms, privacy/data processing, regional/data-use implications, pricing, and acceptable use | Pending | Legal; provider approval artifact |
| Telemetry/analytics destinations | Runtime telemetry/audit signals exist; no GOV-01 outbound inventory or legal approval is recorded | Inventory every destination/field/retention/control and approve disclosure text | Pending | Privacy + security; OBS-01 evidence |

## Approval rules

- An approval record must identify the reviewer, date, candidate SHA (where
  applicable), scope/provider/model, evidence location, and expiry/review date.
- Legal review cannot be inferred from an open-source license, a provider
  configuration, a README statement, or an older audit.
- The release coordinator must reject marketing copy whose disposition is
  blocked or prohibited. `RC-01` remains controlled by
  [ADR-0003](../adr/0003-ga-product-scope.md).

For storage and responsibility details, see
[GA data, privacy, and operations](GA_DATA_PRIVACY_OPERATIONS.md); for the
platform/provider classifications, see the [GA support matrix](GA_SUPPORT_MATRIX.md).
