---
title: "GA support matrix"
status: planning-control
date: 2026-09-06
last_fact_check: 2026-09-16
tags: [ga, gov-01, support, platform, providers]
controlling_adr: docs/adr/0003-ga-product-scope.md
current_status_owner: docs/20_CURRENT_STATUS.md
---

# GA support matrix

This is the `GOV-01` support classification for the scope in
[ADR-0003](../adr/0003-ga-product-scope.md).

## 분류 어휘 (네 단계 — 이 넷 밖의 말을 쓰지 않는다)

| 분류 | 뜻 | 승격 조건 |
|---|---|---|
| **Supported** | GA 지원을 약속한다 | 기록된 release-candidate staging run + 담당자 + 승인. 후보 SHA·artifact·날짜·담당자·승인자가 증거 디렉터리에 있어야 한다. 이전 SHA나 통과한 단위 시험은 부족하다 |
| **Experimental** | 구현이나 설정 근거는 있으나 지원 약속은 없다 | 판매·마케팅은 "평가용으로 제공" 까지만 말할 수 있다 |
| **Unsupported** | GA 대상 범위 밖이다 | 범위를 넓히려면 새 task + 검증 + ADR 갱신 |
| **Not evaluated** | 관측이나 산출물은 있으나 **판정하지 않았다** | 판정에 필요한 검증을 실제로 수행해야 한다. "산출물이 있다"는 판정 근거가 아니다 |

No row below is supported
today; do not convert a configuration entry into a customer claim.

이 문서는 분류와 근거만 소유한다. 현재 상태(판정·soak·열린 축·사람 축)의 단일 소유자는
[현재 상태 요약](../20_CURRENT_STATUS.md)이다.

## Platform and hardware

| Surface | Classification | Current repository evidence | Missing gate / owner |
|---|---|---|---|
| macOS on Apple Silicon, local Ollama | Experimental | README lists macOS Apple Silicon and Ollama; `config.yaml` defaults to Ollama. | VAL-01 staging with the advertised model, install/upgrade/restart evidence; release coordinator. `BLOCKED_EXTERNAL` (external host) |
| macOS on Apple Silicon, direct MLX | Experimental | `pyproject.toml` has an MLX extra; `model_manager.py` only loads direct MLX on Darwin. | VAL-01 MLX hardware run and model-license review; release coordinator. `BLOCKED_EXTERNAL` (Apple Silicon hardware + model terms) |
| Linux x86_64, containerized CPU/local runtime | Experimental | Dockerfile and Kubernetes manifests exist. | VAL-01 clean host install, local provider run, persistence and restore rehearsal; operations owner. `BLOCKED_EXTERNAL` (clean host) |
| Linux x86_64, NVIDIA CUDA | Unsupported | No CUDA runtime support matrix or validated CUDA delivery path is documented. | New scoped CUDA task, hardware/provider validation, then an ADR update. |
| Windows | Unsupported | No Windows installation or release validation evidence; direct MLX rejects non-Darwin. | New Windows support task, clean install/run evidence, then an ADR update. |
| Native packaged desktop application **as a GA-supported distribution** | Unsupported | ADR-0003 keeps the desktop claim to a local operator deployment plus a browser dashboard and says the scope "does not claim a native packaged desktop application". | ADR update, platform validation matrix, signed/notarized update feed. |
| macOS DMG **artifact** (local build — not a distribution) | Not evaluated | The artifact exists in the local working tree: `dist/Ssak-Ai-0.1.0.dmg` (2026-09-15, 85M, sha256 `34f51420444b3930f4f7922c8226ffbd0c52a03039fdd90a05d0237de82e51c4`), `dmg-smoke` PASS with bundled CPython 3.12.13 on `:18080`, `make check-desktop` PASS. `dist/` is gitignored — there is no committed artifact, SBOM, or release feed. Evidence: [packaging checkpoint](../packaging/notes/SESSION_CHECKPOINT_2026-09-15.md). | **미완이라 Not evaluated**: codesign/notarization 검증 · 깨끗한 지원 macOS 실기기 설치 · 업데이트 피드/중단/rollback · phone LAN·Tailscale smoke · Electron 셸→DMG. 담당 release coordinator. Desktop lane **PAUSED** → NX-11 BLOCKED |

## Model-provider boundary

Selecting a cloud provider sends prompts, attached content, and provider
request metadata to that provider under the customer's account. The local
labels below do not authorize a general “private” claim; see
[data-flow requirements](GA_DATA_PRIVACY_OPERATIONS.md#data-flow-and-storage).

| Provider/runtime | Classification | Current implementation/configuration evidence | Missing gate / owner |
|---|---|---|---|
| Ollama loopback runtime | Experimental | Default engine and `http://localhost:11434` profile are configured. | VAL-01 run, selected-model terms review, and local-only egress proof; release + legal owner. `BLOCKED_EXTERNAL` (legal approver) |
| LM Studio local OpenAI-compatible runtime | Experimental | Loopback profile and optional token environment variable are configured. | VAL-01 run and provider/model terms review; release + legal owner. `BLOCKED_EXTERNAL` (legal approver) |
| Direct MLX | Experimental | MLX extra and Darwin-only loader are present. | Apple Silicon staging and model terms review; release + legal owner. `BLOCKED_EXTERNAL` (Apple Silicon hardware + legal approver) |
| OpenRouter | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. `BLOCKED_EXTERNAL` (provider credential + legal approver) |
| NVIDIA NIM | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. `BLOCKED_EXTERNAL` (provider credential + legal approver) |
| OpenAI | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. `BLOCKED_EXTERNAL` (provider credential + legal approver) |
| Google Gemini | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. `BLOCKED_EXTERNAL` (provider credential + legal approver) |
| ZAI / Zhipu | Experimental | Provider endpoint and environment-variable configuration are present. | Credentialed staging, current terms/privacy review, and outbound-data disclosure; legal + release owner. `BLOCKED_EXTERNAL` (provider credential + legal approver) |
| Any unlisted provider, model, accelerator, or deployment | Unsupported | No GOV-01 evidence record. | New scoped validation and ADR update. |


## Concurrent-user capacity (동시 사용자 수)

| Surface | Classification | Current repository evidence | Missing gate / owner |
|---|---|---|---|
| Single interactive operator on one local/self-hosted instance | GA target disposition (not a load certification) | ADR-0003 single-operator boundary; no marketed seat count | Product owner; keep wording as single-operator only |
| Concurrent / simultaneous multi-user interactive sessions on one instance | Experimental — single-operator use remains the GA target | VAL-02 multi-process staging numbers are quoted in this repository (commit `74271a94` — **그 커밋은 현재 `codex/m1-task-events`·`codex/rc-01-gate-done` 에 들어 있고, 이 행이 인용하던 브랜치 `codex/val-02-resilience` 는 존재하지 않는다**): task CAS race 32 tasks × 8 procs 0 contradiction, conversation CAS 6 procs 0 loss, registry flock 5 procs × 40 projects 0 loss, kill -9 recovery PASS, P95 3.14 ms / soak 60 s RSS +0.4 MB. **주의(2차 fact check, 2026-09-16)**: 이 수치는 `docs/qa/**` 어디에도 **원본 아티팩트가 없다** — 문서 간 인용 사슬로만 존재하므로 게이트·판정 근거로 승격하지 않는다(저장소에 있는 VAL-02 원본 JSON 은 이 창의 후속 실행 `nx04/staging-sc2.json`·`staging-sc6.json` 뿐이며, 위 32×8 CAS 경주를 다시 만든 것이 아니다). Multi-seat product claim still requires release-coordinator review. | Release coordinator disposition; RC-01 candidate-SHA gate. `BLOCKED_EXTERNAL` (release-coordinator decision) |
| Multi-tenant or multi-customer concurrent tenancy | Unsupported / excluded | SaaS excluded by ADR-0003 | SaaS expansion gate before `RC-01` |

Do not convert “single tenant” into a concurrent-user capacity number. Any marketed concurrent-user limit requires candidate-SHA `VAL-02` evidence and release-coordinator approval.

## How to use the matrix

`BLOCKED_EXTERNAL` marks a row whose remaining gate depends on something this
repository cannot produce: external hardware, a provider credential, or a named
approver (legal, privacy, security, release coordinator). The implementation work
continues, but the row can never be promoted by editing this file — only the named
external party can clear it. Absence of approval is recorded on purpose; see the
disposition vocabulary in [the claim and review
register](GA_CLAIMS_AND_REVIEW_REGISTER.md#disposition-vocabulary).

- Sales may describe an experimental row only as “available for evaluation”; it
  may not call it supported, certified, secure, private, or production-ready.
- A supported row must name the candidate SHA, test artifact, date, owner, and
  approver in the evidence directory. A prior SHA or a passing unit test is
  insufficient.
- The product is single tenant regardless of provider selection. Cloud-provider
  account sharing does not create tenant isolation in Ssak-Ai.

The required marketing wording and the third-party review state are in the
[claim and review register](GA_CLAIMS_AND_REVIEW_REGISTER.md).

Data-sensitivity classes (데이터 민감도) are not platform rows; they are
frozen in [ADR-0003](../adr/0003-ga-product-scope.md) and
[GA data, privacy, and operations](GA_DATA_PRIVACY_OPERATIONS.md).

## Last fact check (2026-09-16)

- Row evidence was re-read against the working tree. The only row whose evidence
  cell had gone stale was the desktop package row: it claimed no packaging
  artifact existed while `dist/Ssak-Ai-0.1.0.dmg` did. It is now split into a
  scope row (`Unsupported`) and an artifact row (`Not evaluated`).
- No row was promoted. `Supported` is still empty — the classification only
  changes when the named external owner clears the missing gate.

### 2차 fact check (같은 날, NX-10 창 — 주장을 코드·산출물과 대조)

분류는 **바꾸지 않았고**, 낡은 근거·과장된 인용만 바로잡았다. 검증한 것과 방법:

**일치한 것** (검증 방법 → 결과):

- 패키징 산출물 — `shasum -a 256` + `ls -la` + `.gitignore` + 체크포인트 문서를 읽었다. 88,824,912 B(≈85M) 에
  sha256 `34f51420…51c4` 로 **문서값과 동일**하고, `dist/` 는 무시되며,
  `docs/packaging/notes/SESSION_CHECKPOINT_2026-09-15.md` 에 `dmg-smoke`·`check-desktop`·CPython 3.12.13 근거가 있다.
- macOS Apple Silicon + MLX — `pyproject.toml` extras 와 `model_manager.py` 를 읽었다. `mlx` extra 가 플랫폼 마커와 함께
  있고, `_load_mlx_model` 은 `platform.system() != "Darwin"` 에서 거부한다.
- macOS + Ollama(기본) — `config.yaml`(`api_engine: ollama`)과 README 로 확인.
- Linux 컨테이너 — `Dockerfile` 과 `deploy/k8s/*.yaml` 이 존재.
- 클라우드 provider 6종 — `src/antigravity_k/**` 에서 endpoint·env 구성을 검색해 openrouter·nim/NVIDIA·gemini·zai·
  api.openai.com 구성이 있음을 확인.
- 데스크톱 앱 `Unsupported` — ADR-0003 에 “does not claim a native packaged desktop application” 문구 존재.

**정정한 것 2건** (동시 사용자 행):

1. 인용된 브랜치 `codex/val-02-resilience` 는 **존재하지 않는다**. 커밋 `74271a94` 는 있고
   `codex/m1-task-events`·`codex/rc-01-gate-done` 에 들어 있다 — 행의 인용을 커밋 기준으로 고쳤다.
2. 그 행이 인용하는 수치(32×8 CAS 경주·P95 3.14 ms 등)의 **원본 아티팩트가 `docs/qa/**` 에 없다** —
   문서 간 인용 사슬로만 존재한다. 게이트·판정 근거로 승격하지 않는다는 주의를 행에 달았다
   (저장소에 있는 VAL-02 원본 JSON 은 이 창의 후속 실행 `nx04/staging-sc2.json`·`staging-sc6.json` 뿐).

`Supported` 행은 여전히 **0개**다(승격은 이 파일 편집으로 불가능 — 소유자 승인 필요).
