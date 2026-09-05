---
title: "GA support matrix"
status: planning-control
date: 2026-09-06
tags: [ga, gov-01, support, platform, providers]
controlling_adr: docs/adr/0003-ga-product-scope.md
---

# GA support matrix

This is the `GOV-01` support classification for the scope in
[ADR-0003](../adr/0003-ga-product-scope.md). **Supported** requires a recorded
release-candidate staging run, an owner, and approval. **Experimental** means
there is implementation or configuration evidence but no GA support promise.
**Unsupported** means it is outside the GA target. No row below is supported
today; do not convert a configuration entry into a customer claim.

## Platform and hardware

| Surface | Classification | Current repository evidence | Missing gate / owner |
|---|---|---|---|
| macOS on Apple Silicon, local Ollama | Experimental | README lists macOS Apple Silicon and Ollama; `config.yaml` defaults to Ollama. | VAL-01 staging with the advertised model, install/upgrade/restart evidence; release coordinator. |
| macOS on Apple Silicon, direct MLX | Experimental | `pyproject.toml` has an MLX extra; `model_manager.py` only loads direct MLX on Darwin. | VAL-01 MLX hardware run and model-license review; release coordinator. |
| Linux x86_64, containerized CPU/local runtime | Experimental | Dockerfile and Kubernetes manifests exist. | VAL-01 clean host install, local provider run, persistence and restore rehearsal; operations owner. |
| Linux x86_64, NVIDIA CUDA | Unsupported | No CUDA runtime support matrix or validated CUDA delivery path is documented. | New scoped CUDA task, hardware/provider validation, then an ADR update. |
| Windows | Unsupported | No Windows installation or release validation evidence; direct MLX rejects non-Darwin. | New Windows support task, clean install/run evidence, then an ADR update. |
| Native packaged desktop application | Unsupported | Repository provides a web dashboard; no package/distribution evidence establishes a native desktop app. | Packaging task and platform validation, then an ADR update. |

## Model-provider boundary

Selecting a cloud provider sends prompts, attached content, and provider
request metadata to that provider under the customer's account. The local
labels below do not authorize a general “private” claim; see
[data-flow requirements](GA_DATA_PRIVACY_OPERATIONS.md#data-flow-and-storage).

| Provider/runtime | Classification | Current implementation/configuration evidence | Missing gate / owner |
|---|---|---|---|
| Ollama loopback runtime | Experimental | Default engine and `http://localhost:11434` profile are configured. | VAL-01 run, selected-model terms review, and local-only egress proof; release + legal owner. |
| LM Studio local OpenAI-compatible runtime | Experimental | Loopback profile and optional token environment variable are configured. | VAL-01 run and provider/model terms review; release + legal owner. |
| Direct MLX | Experimental | MLX extra and Darwin-only loader are present. | Apple Silicon staging and model terms review; release + legal owner. |
| OpenRouter | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. |
| NVIDIA NIM | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. |
| OpenAI | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. |
| Google Gemini | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. |
| ZAI / Zhipu | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. |
| Any unlisted provider, model, accelerator, or deployment | Unsupported | No GOV-01 evidence record. | New scoped validation and ADR update. |

## How to use the matrix

- Sales may describe an experimental row only as “available for evaluation”; it
  may not call it supported, certified, secure, private, or production-ready.
- A supported row must name the candidate SHA, test artifact, date, owner, and
  approver in the evidence directory. A prior SHA or a passing unit test is
  insufficient.
- The product is single tenant regardless of provider selection. Cloud-provider
  account sharing does not create tenant isolation in Ssak-Ai.

The required marketing wording and the third-party review state are in the
[claim and review register](GA_CLAIMS_AND_REVIEW_REGISTER.md).
