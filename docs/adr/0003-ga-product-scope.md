---
title: "ADR-0003: Commercial GA product scope"
status: accepted-for-planning
date: 2026-09-06
owners: [product-owner, security-architect, release-coordinator]
tags: [adr, ga, product-scope, gov-01]
---

# ADR-0003: Commercial GA product scope

## Decision

`GOV-01` controls the GA scope used by `RC-01`. The sellable target is a
**local-first desktop operator experience** and **self-hosted single-tenant
deployment**. “Desktop” describes a local operator deployment and browser
dashboard; it does not claim a native packaged desktop application.

The product is one customer-controlled instance, one organization, and one
operator-controlled data boundary. The customer operates its host, network,
identity controls, backups, provider accounts, and workspace data. This
decision does not approve a public GA release, legal terms, provider terms, or
any platform/provider as supported. Those approvals and evidence are tracked
in the linked documents.

## Included deployment modes

| Mode | Scope status | Boundary | Release condition |
|---|---|---|---|
| Local-first desktop operator | Target | One operator-controlled machine; local services and local workspace | Only claims allowed by the [support matrix](../ga/GA_SUPPORT_MATRIX.md) may be marketed. |
| Self-hosted single tenant | Target | One organization operates one isolated instance and its attached storage | The operator completes the [data and operations requirements](../ga/GA_DATA_PRIVACY_OPERATIONS.md). |
| Docker or Kubernetes single-tenant installation | Delivery mechanism, experimental | The supplied manifests/image do not establish a managed service or tenant boundary | Staging, restore, security, and operations evidence must pass before it is called supported. |

## Concurrent-user boundary (동시 사용자 수)

| Disposition | Boundary | Gate / owner |
|---|---|---|
| GA target | **Single interactive operator** on one customer-controlled instance. The sellable edition assumes one human operator session driving the local/self-hosted deployment. | Product owner; stated by this ADR |
| Unverified / blocked for GA claims | Concurrent or simultaneous multi-user interactive access (shared instance used by multiple operators at once), multi-seat concurrency SLAs, and any marketed concurrent-user capacity number | `VAL-02` load/concurrency evidence at the candidate SHA; release coordinator + security owner |
| Excluded | Multi-tenant shared control planes and SaaS multi-customer concurrency | SaaS expansion gate below; `RC-01` remains blocked |

A “single-tenant” or “one operator-controlled data boundary” statement is **not** a verified multi-user concurrency claim. Marketing must not imply simultaneous multi-user capacity until `VAL-02` evidence and release-coordinator approval exist. Until then, concurrent multi-user use is out of the sellable GA promise and remains experimental/unsupported for support commitments.

## Data-sensitivity scope (데이터 민감도)

| Sensitivity class | GA disposition | Gate / owner |
|---|---|---|
| Operator workspace content (source, notes, tool outputs under customer control) | Allowed for the local-first / self-hosted target **under operator classification and control**; no product privacy certification is implied | Operator; privacy disclosure + DAT lifecycle evidence |
| Application configuration and non-secret operational metadata | Allowed | Operations / data owners via DAT-01–03 inventory |
| Provider API credentials and access PINs | Customer-held secrets only; **must not** appear in docs, evidence, logs, or exports; product does not market certified secret management | Security owner (`SEC-*`); operator secret store |
| Credentials / secrets embedded in prompts, logs, or exports | Prohibited in product surfaces and evidence; treat as a release blocker if found | Security + privacy; log/export redaction proof |
| Ordinary personal data / PII incidental to operator use | Unverified for GA marketing; do not claim GDPR/PIPA “ready” or approved PII processing | Legal/privacy owner; privacy review artifact |
| Regulated or high-sensitivity data (e.g. PHI/health, PCI payment card data, government classified, children’s data, special-category sensitive personal data) | **Excluded** from the sellable GA edition until legal, privacy, and security gates explicitly approve a scoped SKU | Legal + privacy + security; new scope ADR before `RC-01` |
| Customer data sent to a selected cloud provider | Allowed only with selected-provider disclosure; provider retention/sensitivity handling is outside product control | Legal + privacy; provider terms review in the claim register |

This classification freezes the commercial sensitivity boundary for `GOV-01`. Detailed storage locations and deletion limits remain in [GA data, privacy, and operations](../ga/GA_DATA_PRIVACY_OPERATIONS.md).

## Explicit exclusions

- Multi-tenant SaaS, shared tenant data stores, shared control planes, and
  managed hosting operated by Ssak-Ai are excluded.
- No availability, response-time, data-residency, deletion-through-backup,
  hardware compatibility, privacy, security, or provider/model claim is
  implicit in this decision.
- Windows support, NVIDIA CUDA support, and a native desktop package are not
  part of this GA target.

## SaaS expansion gate

If future scope adds SaaS, `RC-01` is blocked until the release checklist
contains, implements, and verifies these tasks: RBAC/SSO; tenant isolation;
administrator audit; data residency; billing; abuse control; and
tenant-scoped backup and deletion. A deployment label, ingress, or multiple
replicas is not evidence of any of those capabilities.

## Scope-control rule

`RC-01` may evaluate only this scope. It must remain blocked when any claim in
the [claim matrix](../ga/GA_CLAIMS_AND_REVIEW_REGISTER.md) is marked blocked,
or when a release markets an excluded mode. A broader SKU requires an updated
ADR, a new checklist task set, and evidence at the candidate SHA.

## Evidence and approval state

| Item | State | Owner | Evidence / gate |
|---|---|---|---|
| Product boundary | Approved for planning | Product owner | Coordinator-approved GOV-01 scope decision; this ADR |
| Legal/privacy approval | Pending | Legal/privacy owner | Review register, signed approval artifact |
| Platform/provider support | Pending | Release coordinator | Staging evidence named in support matrix |
| Operational readiness | Pending | Operations owner | Restore and support rehearsal |
| Public GA authorization | Not granted | Release coordinator | RC-01 on one candidate SHA |
| Concurrent-user capacity | Single-operator target; multi-user unverified/blocked | Product + release + security | VAL-02 evidence before any concurrency claim |
| Data-sensitivity classes | Workspace/ops metadata allowed under operator control; regulated/high-sensitivity excluded; PII unverified | Legal + privacy + security | Sensitivity table in this ADR and data document |

## Consequences

Marketing and sales material must use only the bounded wording and gates in
the [claim matrix](../ga/GA_CLAIMS_AND_REVIEW_REGISTER.md). The operating
contract, user-data flow, and deletion limits are defined in
[GA data, privacy, and operations](../ga/GA_DATA_PRIVACY_OPERATIONS.md).
