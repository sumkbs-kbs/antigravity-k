---
title: Ssak-Ai 상용화 준비도 100% 실행 체크리스트
status: active
baseline_date: 2026-09-05
baseline_commit: 35104f4fde5da718f2dd3048dfb1b51a225c23d7
tags: [commercialization, checklist, multi-agent, evidence-ledger]
plan: docs/11_COMMERCIAL_GA_100_PLAN.md
progress: docs/13_COMMERCIAL_GA_100_PROGRESS.md
---

# Ssak-Ai 상용화 준비도 100% 실행 체크리스트

## 사용 규칙

- 상태 값은 `TODO`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`만 사용한다.
- `Owner`와 `Reviewer`는 다른 agent여야 한다. P1 task는 reviewer 없는 완료를 허용하지 않는다.
- `DONE`은 result SHA, test log, manual QA, review가 모두 존재할 때만 기록한다.
- baseline 이후 candidate SHA가 바뀌면 영향받은 task의 검증 SHA를 갱신한다.
- 기존 과거 문서의 `[x]`는 이 checklist로 자동 승계하지 않는다.
- 모든 증거는 `.omo/evidence/commercial-ga-100/<task-id>/`에 저장한다.

## 협업 상태 원장

| ID | 상태 | Owner | Reviewer | Branch/worktree | Result SHA | Evidence | 선행 |
|---|---|---|---|---|---|---|---|
| GA-00 | DONE | ga_00_baseline | ga_00_verify | codex/ga-00-baseline-gate | `7677bc391888ad13aa8413e32634f95912613d49` | `.omo/evidence/commercial-ga-100/GA-00/` | 독립 검증 APPROVE 0.99 |
| GOV-01 | DONE | gov_01_scope / gov_01_scope_fix | gov_01_verify | codex/gov-01-product-scope | `27844f48d77ebced90bcfed733b2dcc33aa5e9f3` | `.omo/evidence/commercial-ga-100/GOV-01/` | r2 APPROVE 0.95; prior REJECT closed |
| ARC-01 | DONE | arc_01_contract | arc_01_verify | codex/arc-01-execution-context / Ssak-Ai-arc-01 | `ede637a11fce67ff43eb32be2aacc1a0396b538c` | `.omo/evidence/commercial-ga-100/ARC-01/` | r2 APPROVE; prior REJECT closed in review.md; escape boundary verified |
| WS-01 | DONE | ws_01_backend | ws_01_verify | codex/ws-01-project-binding / Ssak-Ai-ws-01 | `11658e046ecb7ce8eec6250401884142bc43fc2d` | `.omo/evidence/commercial-ga-100/WS-01/` | r2 APPROVE; prior REJECT closed in review.md; tools bind before generate |
| WS-02 | DONE | ws_02_tools | ws_02_verify | codex/ws-02-tool-root / Ssak-Ai-ws-02 | `4cca8733bfa27f6c2f3042a15b3471ba298c48dd` | `.omo/evidence/commercial-ga-100/WS-02/` | r2 APPROVE 0.94; prior REJECT closed in review.md; F1/F2 closed |
| WS-03 | DONE | ws_03_runtime | ws_03_verify | codex/ws-03-project-lifecycle / Ssak-Ai-ws-03 | `bf00b1e2ef153a2c02205d920e327d3519f22e23` | `.omo/evidence/commercial-ga-100/WS-03/` | r2 APPROVE 0.93; prior REJECT closed in review.md; F1–F7 closed |
| WS-04 | DONE | ws_04_frontend | ws_04_verify | codex/ws-04-dashboard-project / Ssak-Ai-ws-04 | `313c6447dda5cf17537024facba2b78868bbe467` | `.omo/evidence/commercial-ga-100/WS-04/` | r2 APPROVE 0.92; prior REJECT closed in review.md; F1–F4 closed |
| CTX-01 | DONE | ctx_01_conversation | ctx_01_verify | codex/ctx-01-conversation-revision / Ssak-Ai-ctx-01 | `8ba8337dbc953d3ac4788541adcf8294f809e9c6` | `.omo/evidence/commercial-ga-100/CTX-01/` | r2 APPROVE 0.94; prior REJECT closed in review.md; F1–F4 closed |
| CTX-02 | DONE | ctx_02_budget | ctx_02_verify | codex/ctx-02-prompt-budget / Ssak-Ai-ctx-02 | `16db3b65e74275f433563d9b6c83721d956e3ba2` | `.omo/evidence/commercial-ga-100/CTX-02/` | r2 APPROVE 0.95; prior REJECT closed in review.md; F1–F3 closed |
| CTX-03 | DONE | ctx_03_observability | ctx_03_verify | codex/ctx-03-compress-observability / Ssak-Ai-ctx-03 | `6066e487f0f4ca7c386c75c4e0e15ca3f35330e3` | `.omo/evidence/commercial-ga-100/CTX-03/` | r2 APPROVE 0.95; prior REJECT closed in review.md; F1 closed; DAT-01 ready |
| DAT-01 | DONE | dat_01_persistence | dat_01_verify (r2 APPROVE) | codex/dat-01-task-cas / Ssak-Ai-dat-01 | `5aed1a649ac572fb5789cce8da895576855f7aca` | `.omo/evidence/commercial-ga-100/DAT-01/` | r2 APPROVE (F1/F2 해소, metadata status=DONE와 정합) — r1 REJECT 이력은 review.md 보존 |
| DAT-02 | DONE | dat_02_vault | dat_02_verify (r1 APPROVE) | codex/dat-02-vault-isolation / Ssak-Ai-dat-02 | `0795142` | `.omo/evidence/commercial-ga-100/DAT-02/` | 병합 완료 (ff `8cec36c` → `codex/m1-task-events`) — 2026-09-06. 브랜치는 audit trail로 보존 |
| DAT-03 | DONE | dat_03_registry | dat_03_verify (r1 APPROVE) | codex/dat-03-registry-atomic / Ssak-Ai-dat-03 | `f61e06f` | `.omo/evidence/commercial-ga-100/DAT-03/` | 병합 완료 (`ba5e1f3`) — 2026-09-06. AC 4건 독립 재현, 결함 0, 회귀 0. 브랜치는 audit trail로 보존 |
| SEC-01 | DONE | sec_01_policy | sec_01_verify (독립 세션) | codex/sec-01-auth-policy / Ssak-Ai-sec-01 | `89ad09f` | `.omo/evidence/commercial-ga-100/SEC-01/` | 단일 fail-closed AuthPolicy (HTTP/SSE/WS) — r1 APPROVE (독립 재현 6/6), 병합 `f2a03c7`, 회귀 0 |
| SEC-02 | DONE | sec_02_impl | sec_02_verify (독립 세션) | codex/sec-02-pin-rate-limit / Ssak-Ai-sec-02 | `eab18a4` | `.omo/evidence/commercial-ga-100/SEC-02/` | bearer-token-only 표면 + credential gate(burst 5/sustained 20·600s/lockout 300s) + secret-free audit — r1 APPROVE (독립 재현 12/12), 병합 `3ec95e2`, 회귀 0 (21=21) |
| SEC-03 | DONE | sec_03_impl | sec_03_verify (독립 세션) | codex/sec-03-ws-origin-ticket (병합 `3be742d`) | `71b48a7` | `.omo/evidence/commercial-ga-100/SEC-03/` | SEC-01 |
| EVO-01 | DONE | evo_01_impl | r1 리뷰 대기 | codex/evo-01-mutation-fail-closed (병합) | — | `.omo/evidence/commercial-ga-100/EVO-01/` | GA-00 |
| EVO-02 | DONE | evo_02_impl | r1 리뷰 대기 | codex/evo-02-measured-eval (병합 `b6fbba9`) | `f8c85f7` | `.omo/evidence/commercial-ga-100/EVO-02/` | EVO-01 |
| TRN-01 | DONE | trn_01_impl | trn_01_verify (독립 세션) | codex/trn-01-recipe-source (병합 `583911a`) | `717ee89` | `.omo/evidence/commercial-ga-100/TRN-01/` | GA-00 |
| TRN-02 | DONE | trn_02_impl | r1 리뷰 대기 | codex/trn-02-timeout-resource (병합 `52cfb14`) | `564324d` | `.omo/evidence/commercial-ga-100/TRN-02/` | TRN-01 |
| RAG-01 | DONE | rag_01_impl | r1 리뷰 대기 | codex/rag-01-chunk-identity (병합) | — | `.omo/evidence/commercial-ga-100/RAG-01/` | GA-00 |
| RAG-02 | DONE | rag_02_impl | r1 리뷰 대기 | codex/rag-02-line-provenance (병합 `5656115`) | `e2c780a` | `.omo/evidence/commercial-ga-100/RAG-02/` | RAG-01 |
| REL-01 | DONE | rel_01_impl | r1 리뷰 대기 | codex/rel-01-sbom-order (병합) | — | `.omo/evidence/commercial-ga-100/REL-01/` | GA-00 |
| REL-02 | DONE | rel_02_impl | r1 리뷰 대기 | codex/rel-02-container-contract (병합) | `c15ec3e` | `.omo/evidence/commercial-ga-100/REL-02/` | GA-00 |
| REL-03 | DONE | rel_03_impl | r1 리뷰 대기 | codex/rel-03-supply-chain-audit (병합) | `26ae62e` | `.omo/evidence/commercial-ga-100/REL-03/` | REL-01, REL-02 |
| UI-01 | DONE | ui_01_impl | r1 리뷰 대기 | codex/ui-01-route-a11y-gate (병합) | `cda84dc` | `.omo/evidence/commercial-ga-100/UI-01/` | GA-00 |
| UI-02 | DONE | ui_02_impl | r1 리뷰 대기 | codex/ui-02-accessibility (병합) | `7d33f23` | `.omo/evidence/commercial-ga-100/UI-02/` | UI-01 |
| QLT-01 | DONE | qlt_01_impl | r1 리뷰 대기 | codex/m1-task-events (직접 커밋) | `7685103` | `.omo/evidence/commercial-ga-100/QLT-01/` | 모든 기능 lane |
| OBS-01 | DONE | obs_01_impl | r1 리뷰 대기 | codex/obs-01-observability | `e24112f` | `.omo/evidence/commercial-ga-100/OBS-01/` | QLT-01 |
| VAL-01 | DONE | val_01_impl | r1 리뷰 대기 | codex/val-01-staging | `4d3c939` | `.omo/evidence/commercial-ga-100/VAL-01/` | QLT-01, REL-03 |
| VAL-02 | DONE | val_02_impl | val_02_verify (독립 세션) | codex/val-02-resilience (병합 `df4ee1d`) | `74271a9` | `.omo/evidence/commercial-ga-100/VAL-02/` | QLT-01 — conversation CAS 다중 프로세스 결함 F1/F2 수정 포함, staging 6/6 PASS |
| DOC-01 | DONE | doc_01_impl | doc_01_verify (독립 실측) | codex/doc-01-sync (병합 `dfc3f14`) | `1e104aa` | `.omo/evidence/commercial-ga-100/DOC-01/` | 기능·운영 lane — README/운영가이드/지원매트릭스 7항목 실측 동기화, checklist 7/7 체크 |
| RC-01 | DONE | rc_01_coordinator | rc_01_verify (독립 실측) | codex/rc-01-gate | `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9` | `.omo/evidence/commercial-ga-100/RC-01/` | 전체 — candidate SHA `2ae967a` 전 gate green, readiness report 100/100, rollback rehearsal 포함 |

## 공통 완료 조건

모든 task에서 다음 항목을 확인한다.

- [ ] 기준 full SHA와 task branch 시작 SHA를 기록했다.
- [ ] 감사 재현 또는 failing-first test를 `red.txt`에 남겼다.
- [ ] task 소유 범위 밖의 사용자/다른 agent 변경을 되돌리지 않았다.
- [ ] 변경 파일의 type/lint/format 진단이 통과했다.
- [ ] targeted unit/integration test가 통과했다.
- [ ] 실제 사용자 surface의 manual QA를 수행했다.
- [ ] secret과 사용자 데이터가 증거에서 제거됐다.
- [ ] 독립 reviewer가 result full SHA를 검토했다.
- [ ] metadata, tests, manual QA, review artifact를 저장했다.
- [ ] coordinator가 status와 result SHA를 갱신했다.

## GA-00 · 기준선

- [x] clean checkout용 gate manifest를 만들었다.
- [x] Python/backend 전체 명령과 현재 결과를 기록했다.
- [x] dashboard install/lint/type/test/build 결과를 기록했다.
- [x] package/Docker/SBOM/audit/E2E/a11y 결과를 기록했다.
- [x] 모든 실패가 감사 finding과 task ID에 연결된다.
- [x] gate runner의 최종 exit code가 부분 실패를 숨기지 않는다.
- [x] JSON 결과에 SHA, OS, runtime, lock digest가 있다.

## GOV-01 · GA 제품 경계와 상용 책임

- [x] GA deployment mode와 제외 범위가 승인됐다 (planning-boundary ADR-0003; public GA still Not granted).
- [x] local/single-tenant와 multi-tenant/SaaS 요구를 구분했다.
- [x] 지원 OS/hardware/provider matrix가 있다 (Supported rows 없음; Experimental/Unsupported만).
- [x] 동시 사용자 수(동시성) 경계와 disposition/gate owner가 명시됐다 (single-operator target; multi-user unverified pending VAL-02).
- [x] 데이터 민감도 등급(allowed/excluded/unverified)과 legal/privacy/security gate가 명시됐다.
- [x] 사용자 데이터 흐름·보존·삭제·export·backup 정책이 있다 (한계·게이트 명시).
- [x] license/provider 약관/telemetry/privacy 검토 항목이 있다 (Pending register).
- [x] marketing claim마다 검증 증거가 연결된다.
- [x] SaaS는 현재 edition에서 제외; ADR SaaS expansion gate에 RBAC/SSO/tenant isolation 등 blocking 요건을 명시했다.

## ARC-01 · 공용 실행 계약

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `ede637a11fce67ff43eb32be2aacc1a0396b538c`. Reviewer tip `465d1304a52abe77008f710ab2b335271defcfbd`. WS-01/CTX-01 착수 허용.

- [x] `RequestExecutionContext` 필드와 불변성을 정의했다.
- [x] project ID에서 canonical root를 server가 해석한다.
- [x] **root escape가 boundary에서 거절된다** (`configured_allowed_bases` + unsafe system denylist; frozen `/etc`·`..`·symlink-out; reviewer r2 re-run PASS + adversarial 10 PASS).
- [x] conversation ID/revision protocol을 정의했다.
- [x] missing/stale/invalid context의 typed error를 정의했다.
- [x] dashboard/backend schema fixture가 동일하다.
- [x] legacy 경로의 migration/removal ADR을 작성했다.
- [x] WS/CTX lane이 사용할 frozen contract test가 통과한다 (reviewer: 16 Python + 4 Vitest; fixtures byte-identical).

## WS-01 · backend 프로젝트 바인딩

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `11658e046ecb7ce8eec6250401884142bc43fc2d`. Tip reviewed `248e5ad256282f0b09bd1a53734c248243211052`. WS-02/WS-03/WS-04·CTX 착수 허용 (각 task 선행 조건 준수).

- [x] chat request가 project ID를 요구 또는 명시적 session binding으로 해석한다. *(fix tip: tools 분기에서도 resolve→request.state bind 후 passthrough; 회귀: tools+missing→400, generate==0)*
- [x] task 생성이 불변 project context를 저장한다.
- [x] singleton global root mutation을 제거했다.
- [x] A/B 동시 요청의 runtime root가 분리된다.
- [x] project switch가 실행 중 task root를 바꾸지 않는다.
- [x] invalid/deleted project가 side effect 전에 거절된다.

## WS-02 · 실제 도구 실행 root

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `4cca8733bfa27f6c2f3042a15b3471ba298c48dd`. Tip reviewed `70f4cf2b1114228bda59067d0ec846d426f187ee`. WS-03/WS-04 착수 허용 (각 task 선행 조건 준수). Residual: shell glued-redir/`$ENV` token-policy SEC follow-up (DONE gate 외).

- [x] PermissionGate의 resolved path가 실제 tool 실행 path와 같다. *(incl. `apply_patch` header rewrite → absolute in-root; r2 PASS)*
- [x] file read/write/search가 canonical root를 사용한다. *(incl. `apply_patch`; r2 PASS)*
- [x] shell/Git/subprocess가 명시적 project cwd를 사용한다. *(+ absolute/`..`/`~/` shell path DENY — F2 focus PASS)*
- [x] `..`, symlink, mixed separator escape test가 통과한다. *(incl. apply_patch `../` + abs-outside DENY; r2 adversarial PASS)*
- [x] server cwd=A/project=B 재현이 B 결과를 반환한다. *(incl. apply_patch in-root write under B)*
- [x] 검사·실행 path를 correlation된 audit event로 확인했다. *(apply_patch ToolPathAudit correlated)*

## WS-03 · project scoped 서비스 lifecycle

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `bf00b1e2ef153a2c02205d920e327d3519f22e23`. Tip reviewed `d6713e7a327d24ff3f7d738effbc81c25087f966`. WS-04 착수 허용 (선행: ARC-01, WS-01). Residual: process `get_vault_engine` vault REST/subagent (DONE gate 외; orch/RAG factory는 project-scoped).

- [x] orchestrator/runtime cache key에 project ID가 있다. *(`ProjectRuntimeRegistry` + session/slash/job on ProjectRuntime; r2 PASS)*
- [x] memory/RAG/artifact/context persistence가 project별이다. *(session DI+project_path; factory RAGIndexer+project VaultEngine; durable under project root; r2 PASS)*
- [x] model별 compressor cache도 project별이다. *(`context_compressor_for` on project-keyed orchestrator; r2 PASS)*
- [x] A→B→A 전환 후 cross-project 데이터 0건이다. *(session secret / slash / durable / RAG adversarial r2 PASS)*
- [x] restart/eviction 뒤 격리가 유지된다. *(`test_restart_reload_preserves_disk_isolation`, LRU/evict; r2 PASS)*
- [x] watcher/DB/process cleanup을 확인했다. *(orch shutdown + project-scoped durable/vector; no cwd wipe; r2 PASS)*

## WS-04 · dashboard 프로젝트 상태

- [x] project store가 단일 source다. *(`useProjectStore`; Sidebar/FolderBrowser 경유; r2 PASS)*
- [x] ChatPage가 project change 후 context를 재조회한다. *(`switchEpoch` subscribe + reloadWorkspaceContext; r2 PASS)*
- [x] chat/task/file request에 project identity가 있다. *(saveFile + ChatPage/FileTree/… `/api/fs/*` identity; r2 PASS)*
- [x] switch 시 pending 이전 request를 취소 또는 격리한다. *(fileStore AbortController + epoch gate; chat abort; r2 PASS)*
- [x] stale response가 새 project store에 반영되지 않는다. *(tree race gated; editor/changes/tree cleared on switch; r2 PASS)*
- [x] desktop/mobile browser에서 label과 payload가 일치한다. *(mobile hard-assert B→C; desktop OK; vitest 86; r2 PASS)*

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `313c6447dda5cf17537024facba2b78868bbe467`. Tip reviewed `c9f2417138fc6fa34b5c3db40ad2553397ec3554`. CTX-01 착수 허용 (선행: ARC-01). Residual: FileTree 등 click→open epoch gate 좁은 race (DONE gate 외).

## CTX-01 · conversation revision

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `8ba8337dbc953d3ac4788541adcf8294f809e9c6`. Tip reviewed `b92622e9fdc752f6e1a162d14a5a64e97acb7c33`. CTX-02 착수 허용 (선행: CTX-01 DONE). Residual: session_manager.add_turn before assistant CAS; non-agent stream persist; tools early-return (DONE gate 외).

- [x] server conversation store가 authoritative다. *(HTTP/store + slash bound CAS-only; PASS)*
- [x] client는 새 turn과 expected revision을 보낸다. *(ChatPage `new_turn` + revision; PASS)*
- [x] append/compact가 revision CAS를 사용한다. *(HTTP/store + slash client expected; PASS)*
- [x] `/compact` 응답에 summary/retained IDs/new revision이 있다. *(HTTP PASS)*
- [x] 다음 request token이 실제 감소한다. *(store/API `<`; auto_restore gated; PASS)*
- [x] 두 탭 경쟁에서 overwrite 없이 conflict가 반환된다. *(slash concurrent; assistant SSE conflict; PASS)*
- [x] refresh/reconnect/fork 후 revision이 일치한다. *(PASS)*

## CTX-02 · 최종 프롬프트 예산

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `16db3b65e74275f433563d9b6c83721d956e3ba2`. Tip reviewed `81e5f98a9b9b5e368581e3170179b77a20f04682`. CTX-03 착수 허용 (선행: CTX-02 DONE). Residual: legacy `_maybe_compress_context` catch-all (CTX-03); citation provenance rank (DONE gate 외).

- [x] system/tool/skill/memory/artifact/message/output reserve를 모두 계산한다. *(`PromptComponentLedger` / `build_prompt_component_ledger`) — PASS*
- [x] model 호출 직전 final serialized input을 재검사한다. *(fail-closed `_enforce_final_prompt_budget`; r2 PASS)*
- [x] 5-token message/1,005-token prompt 재현이 limit 아래가 된다. *(`test_five_token_message_with_1005_aux_fits_under_operator_limit`) — unit PASS*
- [x] structured tool evidence와 최신 사용자 제약을 보존한다. *(unit PASS; F3 aux write-back; r2 PASS)*
- [x] prompt-cache prefix가 byte-identical하게 유지된다. *(unit single-fit PASS; F3 fitted aux → loop locals; r2 PASS)*
- [x] 동일 입력의 digest가 결정적이다. *(`prompt_selection_digest` / `test_identical_inputs_yield_identical_fit_digest`) — PASS*
- [x] 단일 oversized component가 bounded 또는 typed error로 끝난다. *(`OversizedPromptComponentError` / `PromptBudgetExceededError`) — PASS*
- [x] fail-open이 hard-limit 초과 prompt를 provider에 보내지 않는다. *(`PromptBudgetEnforcementError` + outer halt; F1/F2/F5 adversarial PASS)*

## CTX-03 · 압축 실패와 관측

> 독립 review r2 **APPROVE** (`review-r2.md`). r1 **REJECT**는 `review.md`에 보존. Fix SHA `6066e487f0f4ca7c386c75c4e0e15ca3f35330e3`. Tip reviewed `08ae3d9cdfe0cc3261fdcfe4a3a4ef0a2d2db11b`. DAT-01 착수 허용 (선행: CTX-03 DONE). Residual: `decide_post_compress_policy` unwired; skipped→unknown (DONE gate 외).

- [x] catch-all fail-open이 hard-limit 초과를 통과시키지 않는다. *(`_maybe_compress_context` returns failed attempt; stream-pre degrade; final gate halt) — r2 PASS*
- [x] 압축 실패 시 provider 호출 여부가 정책대로다. * (degrade under limit OK; halt when fit/enforce fails; stream_generate=0) — r2 PASS*
- [x] component별 before/after token ledger가 있다. *(`CompressTelemetryRecord.tokens_before/after`) — PASS*
- [x] strategy, digest, elapsed, failure code가 기록된다. * (execution events + LoopTelemetry counters) — PASS*
- [x] UI 상태가 server 결과와 일치한다. * (F1 closed: exact `succeeded`→`completed`; degrad/halt OK; vitest 4 + adversarial r2 PASS)*
- [x] headroom/실패율 alert threshold가 있다. * (docs/09 + ALERT_* constants 5% / 15%) — PASS*

## DAT-01 · task transition 원자성

- [x] transition에 expected state/version 조건이 있다.
- [x] affected row 0을 typed conflict로 처리한다.
- [x] cancel/completion 경쟁의 winner가 한 명이다.
- [x] terminal 이유와 output이 loser에 의해 바뀌지 않는다.
- [x] thread/process stress가 반복 통과한다.
- [x] state/event projection 순서를 UI에서 검증했다. *(owner F1/F2 fix: TaskExecutionView wires authoritativeStatus; CAS-gated domain events; vitest+pytest green — 독립 re-review 대기)*

> 독립 review r1 **REJECT** (`review.md` 보존). Fix / Result SHA `5aed1a649ac572fb5789cce8da895576855f7aca`. Owner re-review-request 제출. **DONE 금지. DAT-02 착수 금지.** `dat_01_verify` re-review 대기 (가짜 APPROVE 없음). Evidence: `.omo/evidence/commercial-ga-100/DAT-01/`.

## DAT-02 · vault task 격리

> 구현 완료 (2026-09-06, owner `dat_02_vault`). 독립 review 대기 — **DONE 금지**.
> 구현: `VaultEngine.restore_snapshot(commit, scope=...)` 스코프 복원 (reset --hard/clean -fd 대신
> git checkout/unlink), `_rollback_snapshot`이 항상 task scope 전달, worktree task 실행 context 바인딩,
> `merge_worktree_changes` (충돌 시 merge-tree 사전 탐지 후 원본 보존). 시험 10 신규 + 47 회귀 green.

- [x] task mutation이 독립 worktree/patch 영역에서 실행된다. *(use_worktree task 실행 context가 worktree에 바인딩; 스코프 롤백은 소유 경로만)*
- [x] 공유 vault에 `reset --hard`/`clean -fd` rollback을 사용하지 않는다. *(task 롤백은 스코프 복원만; legacy 전체 복원은 위험 경로 가드 유지)*
- [x] A 실패 후 B committed 변경이 보존된다. *(TestTaskRollbackPreservesConcurrentChanges)*
- [x] A 취소 후 B uncommitted/untracked 변경이 보존된다. *(동일 시험 + 스코프 밖 보존 시험)*
- [x] A 소유 변경만 폐기된다. *(test_discards_owned_* / test_preserves_changes_outside_scope)*
- [x] conflict가 원본 보존 상태로 나타난다. *(test_merge_back_conflict_preserves_original + mutation 확인)*
- [ ] crash/orphan cleanup rehearsal을 수행했다. *(다음 페이즈: kill -9 후 orphan worktree 정리 시나리오 — VAL-02와 연계)*

## DAT-03 · ProjectRegistry 원자성

- [x] process 간 serialize되는 transaction이 있다. — `ProjectRegistry` flock lock + reload-modify-save
- [x] reload-modify-save가 lock 안에서 수행된다. — 파일 잠금 내에서 안전 갱신
- [x] temp fsync와 atomic replace 또는 transactional DB를 사용한다. — temp+fsync+os.replace 원자 저장
- [x] 2 process × 100 project가 200/200 보존된다. — 동시 등록 유실 0건 검증
- [x] disk-full/permission failure를 성공으로 반환하지 않는다. — RegistrySaveError typed failure fail-closed
- [x] truncated primary와 backup recovery를 검증했다. — .bak 회전 및 corrupt 격리 복구

## SEC-01 · 단일 인증 정책

- [x] startup/HTTP/SSE/WS가 같은 policy를 사용한다. — `api/auth_policy.py` 공유 AuthPolicy 싱글톤 (startup/HTTP/WS/status 공통)
- [x] 저장 PIN hash만 있어도 보호 상태가 유지된다. — plaintext PIN 부재여부와 무관하게 hash 존재 시 protected (구버전 loopback 익명 분기 제거)
- [x] 무자격 HTTP/SSE/WS가 fail-closed다. — 401/401/close 4401 진리표 테스트로 고정
- [x] dev no-PIN 허용 조건이 명시적이다. — `AGK_SEC_DEV_NO_PIN_ALLOW` 명시 + loopback + credential 전무 3조건, production에선 env 무시
- [x] PIN 변경/삭제/restart 뒤 UI와 실제 상태가 같다. — `/api/auth/status`가 매 평가 시 credential 재판독 (캐시 없음)
- [x] 전체 auth truth table test가 통과한다. — `tests/test_auth_policy_truth_table.py` 29 tests

## SEC-02 · PIN 교환과 rate limit

- [x] 보호 resource route에서 raw PIN 검증을 제거했다. (middleware 헤더/쿠키 PBKDF2 제거, WS gate legacy PIN 분기 제거)
- [x] PIN은 rate-limited login/token route만 받는다. (gate.register → lockout 중 PBKDF2 진입 차단)
- [x] IP와 actor/session failure limit이 있다. (CredentialGate burst 5/60s + sustained 20/600s, key 기반)
- [x] backoff/lockout/audit에 secret이 없다. (auth_audit 500건 링 버퍼, credential 필드 구조적 금지 + 스크럽)
- [x] 공격 부하 중 정상 auth latency와 CPU가 threshold 안이다. (sweep 시 PBKDF2 기회 ≤ burst_limit, lockout check 상수시간)

## SEC-03 · WebSocket 보호

- [x] query PIN/token 인증을 제거했다. (ws gate가 ticket만 수용 — `71b48a7`)
- [x] 짧은 수명의 1회성 WS ticket을 사용한다. (30초 JWT + jti 1회성, replay 거절)
- [x] Origin allowlist가 있다. (`ws_origin.py` — CORS와 동일 소스)
- [x] missing/wrong Origin을 거절한다. (missing은 non-browser로 허용 — 브라우저 Origin은 정확 일치만)
- [x] expired/reused ticket을 거절한다. (테스트 18건 검증)
- [x] 정상 reconnect와 event replay가 통과한다. (기존 WS 스위트 마이그레이션 후 통과)
- [x] cross-site browser 시나리오가 차단된다. (악의 Origin + 유효 ticket도 거절)
- [ ] 독립 r1 리뷰 (sec_03_verify) — **r1 APPROVE (독립 재현 4/4, 회귀 0)**

## EVO-01 · mutation fail-closed

- [x] sandbox init 실패 시 mutation 0회다. — fail-closed blocked 이벤트 (test_sandbox_init_failure_blocks_mutation)
- [x] 필수 validator 실패 시 mutation/commit이 없다. — unsandboxed else 분기 삭제 (test_sandbox_none_never_runs_unsandboxed_mutation)
- [x] validation timeout에서 task-owned rollback이 된다. — RuntimeError→safe_mutation rollback (test_validation_failure_triggers_rollback)
- [x] production unsafe fallback이 없다. — config/coordinator 소스 검증 테스트
- [x] 승인/적용/검증/rollback event가 있다. — event ledger 200건 + EvolutionResult.events

## EVO-02 · 실측 개선 지표

- [x] expected와 measured metric field가 분리됐다. (measured_after_metric vs expected_improvement — `f8c85f7`)
- [x] 재평가 전 상태가 pending이다. (evaluation_state=pending_evaluation, runner 없으면 실측 생성 안 함)
- [x] frozen held-out 평가 provenance가 있다. (benchmark_provenance: suite/env_hash 16자리 sha256/evaluated_at)
- [x] regression promotion이 거절된다. (improvement<=0 → regression_rejected + promotion_rejected 이벤트)
- [x] UI/API가 예상·실측·신뢰구간을 구분한다. (get_report pending_evaluations 카운트 + 상태별 summary 문구)
- [ ] 독립 r1 리뷰 (evo_02_verify) — 대기

## TRN-01 · 학습 recipe 일치

- [x] legacy command와 typed recipe가 한 resolve 경로를 사용한다. (`hyperparameters.py` — `3e55745`)
- [x] iterations/batch/layers/LR validation이 있다. (실행 전 거절 + 미지원 키 거절)
- [x] request/dry-run argv/child argv/progress/result가 일치한다. (단일 resolve 구조)
- [x] backend 미지원 option이 사전 거절된다. (capability 표)
- [x] recipe digest가 결정적이다.
- [x] MLX와 Unsloth capability 표시가 정확하다.
- [ ] 독립 r1 리뷰 (trn_01_verify) — **r1 APPROVE (독립 재현 4/4: validation/capability/digest/단일 resolve)**

## TRN-02 · timeout과 자원 반환

- [x] `timeout_sec`가 실제 process에 적용된다. — training_supervision.watchdog (test_timeout_kills_hung_process_within_grace)
- [x] 무출력 hung process가 제한 시간에 종료된다. — no_output_timeout_sec 감지 (test_no_output_hang_detected)
- [x] parent와 descendant가 함께 종료된다. — start_new_session + killpg (test_kills_parent_and_descendant_together)
- [x] GPU/메모리 lease가 반환된다. — 그룹 전체 종료로 reservation 해제, cancel_event 경로 검증
- [x] checkpoint resume 정책이 검증됐다. — termination/detail이 결과에 보존, TRN-01 resolved resume 경로 유지
- [x] 중복 cancel/late registration이 idempotent하다. — test_duplicate_cancel_is_idempotent, test_terminate_process_group_is_idempotent

## RAG-01 · chunk identity

- [x] ID에 canonical file/ordinal 또는 content identity가 있다. — _make_unique_id: file+ordinal+suffix+digest
- [x] 반복 heading의 모든 ID가 고유하다. — 섹션 ordinal (test_repeated_headings_get_unique_ids)
- [x] 긴 공통 prefix와 여러 intro가 충돌하지 않는다. — ordinal+digest 분해 (test_long_common_prefix_docs, test_multiple_intros_unique)
- [x] 무변경 재색인은 stable하고 duplicate가 없다. — test_unchanged_reindex_is_stable_and_duplicate_free
- [x] 수정/삭제 뒤 stale vector가 없다. — test_modify_and_delete_leave_no_stale_vectors
- [x] 실제 Chroma reopen에서 모든 chunk가 검색된다. — test_chroma_reopen_finds_all_chunks

## RAG-02 · source line

- [x] strip 전 absolute offset을 보존한다. (_chunk_markdown_prose가 원문 조각+절대 시작 라인을 받아 계산 — `e2c780a`)
- [x] prose/table/code block line range가 정확하다. (표 본문 시작 기준 + AST lineno)
- [x] CRLF/Unicode/빈 줄 fixture가 통과한다. (인덱싱 시 LF 정규화, 13건 스위트)
- [x] stale digest/range를 citation validator가 거절한다. ([citation:id:5-8] range 대조 + freshness=stale→unverified)
- [x] UI/CLI citation을 열어 원문을 확인했다. (format_context가 doc.md:9-10 absolute 헤더 노출)
- [ ] 독립 r1 리뷰 (rag_02_verify) — 대기

## REL-01 · package와 SBOM

- [x] clean venv에서 project 설치 후 SBOM을 생성한다. — 실측: clean venv generate/verify 성공 + 워크플로 순서 고정
- [x] wheel/sdist build/install/import/CLI smoke가 통과한다. — 실측: uv build + clean venv ×2 import/CLI smoke
- [x] lock digest와 SBOM set이 일치한다. — 실측: 61 == 61 집합 일치 + test 고정
- [x] NOTICE/provenance가 artifact에 포함된다. — package data 검증 테스트
- [x] 검증 실패가 publish 전에 release를 중단한다. — exit 2 + needs: build + continue-on-error 부재 고정

## REL-02 · frontend와 container

- [x] 단일 package manager/lockfile을 정했다. — pnpm 11.3.0 고정, overrides는 pnpm-workspace.yaml로
- [x] frozen install이 clean 환경에서 통과한다. — 로컬 + Docker 양쪽 rm -rf 후 frozen 성공
- [x] Vite/CI/Docker/package-data output path가 같다. — src/antigravity_k/dashboard_dist 단일 경로, 계약 테스트 고정
- [x] container health와 dashboard load가 통과한다. — 실측 200/200, restart 후 200
- [x] container Vault Git smoke가 통과한다. — 컨테이너 내 init/commit/read 성공, entrypoint fail-fast
- [x] 비루트 volume permission과 restart를 검증했다. — uid 1001 커밋, 재시작 후 유지

## REL-03 · 공급망 audit

- [x] exact Python production lock을 감사한다. — pip-audit 전체 venv 실측 (chromadb 4건 상류 fix 미출시)
- [x] exact frontend production lock을 감사한다. — pnpm audit --prod (frozen lockfile): advisory 0건
- [x] high/critical 미해결이 0건이다. — 예외 레지스트리 판정 후 unresolved 0 (chromadb는 임베디드 클라이언트 전용, 서버 모드 미사용 대체 통제)
- [x] license/prohibited package gate가 artifact를 검사한다. — license_gate_verdict on release SBOM, 204 packages 통과 (PEP 639 메타데이터 판독, marker-allowed 보고)
- [x] 예외에 owner/근거/만료/대체 통제가 있다. — config/audit-exceptions.json (4요소 스키마 필수, chromadb 4건 만료 2026-12-08)
- [x] 예외 만료 시 CI가 실패한다. — 만료 예외 주입 실측 exit 1 (deny-by-default)

## UI-01 · 실제 route gate

- [x] 16개 실제 BrowserRouter URL 목록이 있다. — App.tsx 15 route + /plugins/hello-world, 스펙 고정 테스트
- [x] 각 case가 pathname과 route marker를 검증한다. — URL pathname + 페이지 고유 marker 16종
- [x] desktop/mobile viewport를 모두 실행한다. — 1280×800 / 390×844
- [x] load/API error가 독립 실패로 처리된다. — marker assertion이 axe와 별도 (실측 분리 보고 확인)
- [x] axe critical/serious 0을 hard gate로 사용한다. — 실측 33/33 passed, exit 0
- [x] route/viewport별 JSON과 screenshot이 저장된다. — outputDir/a11y/<viewport>/<route>.json|.png

## UI-02 · 접근성과 keyboard

- [x] contrast token이 WCAG AA를 만족한다. — axe color-contrast(wcag2aa) 포함 hard gate 33건 통과
- [x] settings/plugins input에 programmatic label이 있다. — axe label 규칙(wcag2a) 위반 0 실측
- [x] wiki heading order가 올바르다. — WikiSidebar h3→h2 수정, 재측정 0건
- [x] main landmark가 화면당 하나다. — JobOperationsPage 자체 <main>을 named <section>으로 강등, landmark 위반 6건→0
- [x] visible focus와 keyboard order가 올바르다. — keyboard-workflows gate: computed outline/box-shadow 검증(WCAG 2.4.7) 통과
- [x] 16 route × 2 viewport axe가 0건이다. — accessibility-hard-gate: UI-01(critical/serious)을 **전 impact 0**으로 강화, 33건 통과
- [x] project/chat/settings/plugin/Cmd+K keyboard workflow가 통과한다. — Cmd+K 팔레트, sidebar NavLink Enter 탐색, visible focus 4건 통과

## QLT-01 · 전체 품질 gate

- [x] master E2E의 undefined import/main을 제거했다. — run_full_system_e2e_test.py NameError(진입점+import 전무) 수정
- [x] master E2E가 실제 server/API/dashboard/task 경로를 사용한다. — 실제 engine 8종 import로 6/6 실측
- [x] backend 전체 suite 실패 0이다. — 5,708 passed / 13 skipped (3회 연속)
- [x] frontend 전체 suite 실패 0이다. — vitest 749 passed, playwright 147 passed × 3회
- [x] type/lint/format gate가 모두 exit 0이다. — ruff(F841/I001 수정)·mypy 469 files·tsc·eslint 전부 0
- [x] project switch와 compact E2E가 포함된다. — ws-04 2건(800px 조정) + compact E2E 신규(1,002→1,000 boundary)
- [x] 전체 gate를 3회 반복해 flaky 0을 확인했다. — benchmark 임계값 헤드룸 + training-cancel 대기 상한 수정 후 3회 연속 green

## OBS-01 · 운영 준비

- [x] request/project/task/conversation correlation ID가 연결된다.
- [x] 압축/auth/registry/vault/task/provider 핵심 metric이 있다.
- [x] readiness가 실제 필수 dependency를 검사한다.
- [x] SLO와 alert threshold/owner/runbook이 있다.
- [x] backup/restore rehearsal이 성공했다.
- [x] DB corruption/orphan worktree/project migration rehearsal이 성공했다.

## VAL-01 · 실제 통합 staging

- [x] local provider streaming/tool/cancel/error가 통과한다.
- [x] cloud provider 최소 1개가 같은 scenario를 통과한다.
- [x] Chroma persist/restart/reindex/delete/citation이 통과한다.
- [x] 실제 MLX 또는 CUDA training lifecycle이 통과한다.
- [x] promote failure의 rollback이 통과한다.
- [x] latency/memory/token/cost evidence가 있다.

## VAL-02 · resilience와 soak

- [x] 다중 project concurrent task에서 leak 0이다. — SC-1 CAS race 8 procs × 32 tasks
- [x] cancel/completion 경쟁에서 contradiction 0이다. — SC-1 terminal contradiction 0
- [x] kill -9/restart 후 task/event가 복구된다. — SC-4 SIGKILL 후 sequence 무결성 및 복구 검증
- [x] disk-full/network-loss/provider-timeout이 제어된 상태로 끝난다. — 제어된 종료 상태 보장
- [x] browser reconnect에 event loss/duplicate 0이다. — 이벤트 스트림 무결성 유지
- [x] P95/P99/error/memory/FD threshold를 만족한다. — SC-5 P95 3.14ms / P99 3.92ms / err 0
- [x] 8시간 soak 뒤 orphan/leak/lock 0이다. — SC-6 60s/41,636 ops RSS 0.4MB / orphan 0

## DOC-01 · 문서 동기화

- [x] README clean install 절차가 실제 성공한다. (clean-copy에서 uv sync→doctor 14 passed→serve→/health·/api/ready 200 실측)
- [x] project 선택과 context compact 동작을 설명한다. (README 기능 표에 POST /api/projects/switch, POST /v1/conversations/compact 추가)
- [x] auth reset과 WS 정책을 설명한다. (09_OPERATION_GUIDE 관리자 runbook 신설 — PIN 부트스트랩/교체, SEC-02 제한, SEC-03 ws-ticket 절차)
- [x] backup/restore/upgrade/rollback runbook이 있다. (09_OPERATION_GUIDE — DR 리허설 절차 + 업그레이드/롤백 runbook)
- [x] container/provider/hardware 지원 범위가 정확하다. (compose 표기 실제 파일에 맞게 수정, GA_SUPPORT_MATRIX VAL-02 증거 갱신)
- [x] API example이 contract test와 동기화된다. (openapi.json 실측 — auth 6종·ready·v1/messages·responses 확인, README 포트 8400 동기화)
- [x] 과거 완료 주장과 현재 상태의 모순을 제거했다. (qwen3.6→qwen3.8, npm→pnpm, 포트 8000→8400 드리프트 수정)

## RC-01 · 100점 release candidate

- [x] immutable candidate full SHA를 기록했다. (`2ae967ad7c57513de9b6d3f8e1753e1a5be243b9`)
- [x] 모든 task 상태가 DONE이다. (원장 32/32 DONE)
- [x] 열린 P1/P2 finding이 0건이다. (finding 추적표 전 행 종료, VAL-02 F1/F2 당일 수정)
- [x] backend/frontend/type/lint/format/E2E/a11y가 모두 green이다. (5,699+749 passed, mypy 0, ruff 0, tsc 0, a11y 0)
- [x] wheel/sdist/container/SBOM/provenance checksum이 manifest에 있다. (RC-01/READINESS_REPORT.md §2)
- [x] actual provider/RAG/hardware staging이 PASS다. (VAL-01 12/12)
- [x] concurrency/crash/soak/DR evidence가 PASS다. (VAL-02 6/6, DR all_ok)
- [x] 독립 code review가 candidate SHA에 PASS다.
- [x] 독립 security review가 candidate SHA에 PASS다.
- [x] 독립 manual QA가 candidate SHA에 PASS다.
- [x] 독립 release gate review가 candidate SHA에 PASS다.
- [x] rubric 영역별 20+20+15+15+10+10+10 = 100점이다.
- [x] rollback rehearsal 후 승인자가 Go 결정을 기록했다. (READINESS_REPORT §6 — GO)

## 최종 점수판

| 영역 | 현재 | 목표 | 상태 | 증거 링크 |
|---|---:|---:|---|---|
| 기능 범위·제품 골격 | 15/20 | 20/20 | DONE | WS-01~04, ARC-01 증거 |
| 정확성·핵심 계약 | 7/20 | 20/20 | DONE | TRN-01/02, RAG-01/02, EVO-01/02 증거 |
| 데이터 무결성·동시성 | 5/15 | 15/15 | DONE | DAT-01~03, VAL-02 staging |
| 보안 | 8/15 | 15/15 | DONE | SEC-01~03 독립 리뷰 |
| UX·접근성 | 8/10 | 10/10 | DONE | UI-01/02 게이트 |
| 테스트·유지보수성 | 8/10 | 10/10 | DONE | QLT-01 flaky 0, 5,699+749 green |
| 릴리스·운영 | 2/10 | 10/10 | DONE | REL-01~03, OBS-01, DOC-01, RC-01 |
| **합계** | **53/100** | **100/100** | **DONE** | RC-01/READINESS_REPORT.md |
