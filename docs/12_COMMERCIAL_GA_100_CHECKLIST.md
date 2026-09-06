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
| WS-01 | TODO |  |  |  |  |  | ARC-01 |
| WS-02 | TODO |  |  |  |  |  | WS-01 |
| WS-03 | TODO |  |  |  |  |  | WS-01 |
| WS-04 | TODO |  |  |  |  |  | ARC-01, WS-01 |
| CTX-01 | TODO |  |  |  |  |  | ARC-01 |
| CTX-02 | TODO |  |  |  |  |  | CTX-01 |
| CTX-03 | TODO |  |  |  |  |  | CTX-02 |
| DAT-01 | TODO |  |  |  |  |  | GA-00 |
| DAT-02 | TODO |  |  |  |  |  | GA-00 |
| DAT-03 | TODO |  |  |  |  |  | GA-00 |
| SEC-01 | TODO |  |  |  |  |  | GA-00 |
| SEC-02 | TODO |  |  |  |  |  | SEC-01 |
| SEC-03 | TODO |  |  |  |  |  | SEC-01 |
| EVO-01 | TODO |  |  |  |  |  | GA-00 |
| EVO-02 | TODO |  |  |  |  |  | EVO-01 |
| TRN-01 | TODO |  |  |  |  |  | GA-00 |
| TRN-02 | TODO |  |  |  |  |  | TRN-01 |
| RAG-01 | TODO |  |  |  |  |  | GA-00 |
| RAG-02 | TODO |  |  |  |  |  | RAG-01 |
| REL-01 | TODO |  |  |  |  |  | GA-00 |
| REL-02 | TODO |  |  |  |  |  | GA-00 |
| REL-03 | TODO |  |  |  |  |  | REL-01, REL-02 |
| UI-01 | TODO |  |  |  |  |  | GA-00 |
| UI-02 | TODO |  |  |  |  |  | UI-01 |
| QLT-01 | TODO |  |  |  |  |  | 모든 기능 lane |
| OBS-01 | TODO |  |  |  |  |  | QLT-01 |
| VAL-01 | TODO |  |  |  |  |  | QLT-01, REL-03 |
| VAL-02 | TODO |  |  |  |  |  | QLT-01 |
| DOC-01 | TODO |  |  |  |  |  | 기능·운영 lane |
| RC-01 | TODO |  |  |  |  |  | 전체 |

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

- [ ] chat request가 project ID를 요구 또는 명시적 session binding으로 해석한다.
- [ ] task 생성이 불변 project context를 저장한다.
- [ ] singleton global root mutation을 제거했다.
- [ ] A/B 동시 요청의 runtime root가 분리된다.
- [ ] project switch가 실행 중 task root를 바꾸지 않는다.
- [ ] invalid/deleted project가 side effect 전에 거절된다.

## WS-02 · 실제 도구 실행 root

- [ ] PermissionGate의 resolved path가 실제 tool 실행 path와 같다.
- [ ] file read/write/search가 canonical root를 사용한다.
- [ ] shell/Git/subprocess가 명시적 project cwd를 사용한다.
- [ ] `..`, symlink, mixed separator escape test가 통과한다.
- [ ] server cwd=A/project=B 재현이 B 결과를 반환한다.
- [ ] 검사·실행 path를 correlation된 audit event로 확인했다.

## WS-03 · project scoped 서비스 lifecycle

- [ ] orchestrator/runtime cache key에 project ID가 있다.
- [ ] memory/RAG/artifact/context persistence가 project별이다.
- [ ] model별 compressor cache도 project별이다.
- [ ] A→B→A 전환 후 cross-project 데이터 0건이다.
- [ ] restart/eviction 뒤 격리가 유지된다.
- [ ] watcher/DB/process cleanup을 확인했다.

## WS-04 · dashboard 프로젝트 상태

- [ ] project store가 단일 source다.
- [ ] ChatPage가 project change 후 context를 재조회한다.
- [ ] chat/task/file request에 project identity가 있다.
- [ ] switch 시 pending 이전 request를 취소 또는 격리한다.
- [ ] stale response가 새 project store에 반영되지 않는다.
- [ ] desktop/mobile browser에서 label과 payload가 일치한다.

## CTX-01 · conversation revision

- [ ] server conversation store가 authoritative다.
- [ ] client는 새 turn과 expected revision을 보낸다.
- [ ] append/compact가 revision CAS를 사용한다.
- [ ] `/compact` 응답에 summary/retained IDs/new revision이 있다.
- [ ] 다음 request token이 실제 감소한다.
- [ ] 두 탭 경쟁에서 overwrite 없이 conflict가 반환된다.
- [ ] refresh/reconnect/fork 후 revision이 일치한다.

## CTX-02 · 최종 프롬프트 예산

- [ ] system/tool/skill/memory/artifact/message/output reserve를 모두 계산한다.
- [ ] model 호출 직전 final serialized input을 재검사한다.
- [ ] 5-token message/1,005-token prompt 재현이 limit 아래가 된다.
- [ ] structured tool evidence와 최신 사용자 제약을 보존한다.
- [ ] prompt-cache prefix가 byte-identical하게 유지된다.
- [ ] 동일 입력의 digest가 결정적이다.
- [ ] 단일 oversized component가 bounded 또는 typed error로 끝난다.

## CTX-03 · 압축 실패와 관측

- [ ] catch-all fail-open이 hard-limit 초과를 통과시키지 않는다.
- [ ] 압축 실패 시 provider 호출 여부가 정책대로다.
- [ ] component별 before/after token ledger가 있다.
- [ ] strategy, digest, elapsed, failure code가 기록된다.
- [ ] UI 상태가 server 결과와 일치한다.
- [ ] headroom/실패율 alert threshold가 있다.

## DAT-01 · task transition 원자성

- [ ] transition에 expected state/version 조건이 있다.
- [ ] affected row 0을 typed conflict로 처리한다.
- [ ] cancel/completion 경쟁의 winner가 한 명이다.
- [ ] terminal 이유와 output이 loser에 의해 바뀌지 않는다.
- [ ] thread/process stress가 반복 통과한다.
- [ ] state/event projection 순서를 UI에서 검증했다.

## DAT-02 · vault task 격리

- [ ] task mutation이 독립 worktree/patch 영역에서 실행된다.
- [ ] 공유 vault에 `reset --hard`/`clean -fd` rollback을 사용하지 않는다.
- [ ] A 실패 후 B committed 변경이 보존된다.
- [ ] A 취소 후 B uncommitted/untracked 변경이 보존된다.
- [ ] A 소유 변경만 폐기된다.
- [ ] conflict가 원본 보존 상태로 나타난다.
- [ ] crash/orphan cleanup rehearsal을 수행했다.

## DAT-03 · ProjectRegistry 원자성

- [ ] process 간 serialize되는 transaction이 있다.
- [ ] reload-modify-save가 lock 안에서 수행된다.
- [ ] temp fsync와 atomic replace 또는 transactional DB를 사용한다.
- [ ] 2 process × 100 project가 200/200 보존된다.
- [ ] disk-full/permission failure를 성공으로 반환하지 않는다.
- [ ] truncated primary와 backup recovery를 검증했다.

## SEC-01 · 단일 인증 정책

- [ ] startup/HTTP/SSE/WS가 같은 policy를 사용한다.
- [ ] 저장 PIN hash만 있어도 보호 상태가 유지된다.
- [ ] 무자격 HTTP/SSE/WS가 fail-closed다.
- [ ] dev no-PIN 허용 조건이 명시적이다.
- [ ] PIN 변경/삭제/restart 뒤 UI와 실제 상태가 같다.
- [ ] 전체 auth truth table test가 통과한다.

## SEC-02 · PIN 교환과 rate limit

- [ ] 보호 resource route에서 raw PIN 검증을 제거했다.
- [ ] PIN은 rate-limited login/token route만 받는다.
- [ ] IP와 actor/session failure limit이 있다.
- [ ] backoff/lockout/audit에 secret이 없다.
- [ ] 공격 부하 중 정상 auth latency와 CPU가 threshold 안이다.

## SEC-03 · WebSocket 보호

- [ ] query PIN/token 인증을 제거했다.
- [ ] 짧은 수명의 1회성 WS ticket을 사용한다.
- [ ] Origin allowlist가 있다.
- [ ] missing/wrong Origin을 거절한다.
- [ ] expired/reused ticket을 거절한다.
- [ ] 정상 reconnect와 event replay가 통과한다.
- [ ] cross-site browser 시나리오가 차단된다.

## EVO-01 · mutation fail-closed

- [ ] sandbox init 실패 시 mutation 0회다.
- [ ] 필수 validator 실패 시 mutation/commit이 없다.
- [ ] validation timeout에서 task-owned rollback이 된다.
- [ ] production unsafe fallback이 없다.
- [ ] 승인/적용/검증/rollback event가 있다.

## EVO-02 · 실측 개선 지표

- [ ] expected와 measured metric field가 분리됐다.
- [ ] 재평가 전 상태가 pending이다.
- [ ] frozen held-out 평가 provenance가 있다.
- [ ] regression promotion이 거절된다.
- [ ] UI/API가 예상·실측·신뢰구간을 구분한다.

## TRN-01 · 학습 recipe 일치

- [ ] legacy command와 typed recipe가 한 resolve 경로를 사용한다.
- [ ] iterations/batch/layers/LR validation이 있다.
- [ ] request/dry-run argv/child argv/progress/result가 일치한다.
- [ ] backend 미지원 option이 사전 거절된다.
- [ ] recipe digest가 결정적이다.
- [ ] MLX와 Unsloth capability 표시가 정확하다.

## TRN-02 · timeout과 자원 반환

- [ ] `timeout_sec`가 실제 process에 적용된다.
- [ ] 무출력 hung process가 제한 시간에 종료된다.
- [ ] parent와 descendant가 함께 종료된다.
- [ ] GPU/메모리 lease가 반환된다.
- [ ] checkpoint resume 정책이 검증됐다.
- [ ] 중복 cancel/late registration이 idempotent하다.

## RAG-01 · chunk identity

- [ ] ID에 canonical file/ordinal 또는 content identity가 있다.
- [ ] 반복 heading의 모든 ID가 고유하다.
- [ ] 긴 공통 prefix와 여러 intro가 충돌하지 않는다.
- [ ] 무변경 재색인은 stable하고 duplicate가 없다.
- [ ] 수정/삭제 뒤 stale vector가 없다.
- [ ] 실제 Chroma reopen에서 모든 chunk가 검색된다.

## RAG-02 · source line

- [ ] strip 전 absolute offset을 보존한다.
- [ ] prose/table/code block line range가 정확하다.
- [ ] CRLF/Unicode/빈 줄 fixture가 통과한다.
- [ ] stale digest/range를 citation validator가 거절한다.
- [ ] UI/CLI citation을 열어 원문을 확인했다.

## REL-01 · package와 SBOM

- [ ] clean venv에서 project 설치 후 SBOM을 생성한다.
- [ ] wheel/sdist build/install/import/CLI smoke가 통과한다.
- [ ] lock digest와 SBOM set이 일치한다.
- [ ] NOTICE/provenance가 artifact에 포함된다.
- [ ] 검증 실패가 publish 전에 release를 중단한다.

## REL-02 · frontend와 container

- [ ] 단일 package manager/lockfile을 정했다.
- [ ] frozen install이 clean 환경에서 통과한다.
- [ ] Vite/CI/Docker/package-data output path가 같다.
- [ ] container health와 dashboard load가 통과한다.
- [ ] container Vault Git smoke가 통과한다.
- [ ] 비루트 volume permission과 restart를 검증했다.

## REL-03 · 공급망 audit

- [ ] exact Python production lock을 감사한다.
- [ ] exact frontend production lock을 감사한다.
- [ ] high/critical 미해결이 0건이다.
- [ ] license/prohibited package gate가 artifact를 검사한다.
- [ ] 예외에 owner/근거/만료/대체 통제가 있다.
- [ ] 예외 만료 시 CI가 실패한다.

## UI-01 · 실제 route gate

- [ ] 16개 실제 BrowserRouter URL 목록이 있다.
- [ ] 각 case가 pathname과 route marker를 검증한다.
- [ ] desktop/mobile viewport를 모두 실행한다.
- [ ] load/API error가 독립 실패로 처리된다.
- [ ] axe critical/serious 0을 hard gate로 사용한다.
- [ ] route/viewport별 JSON과 screenshot이 저장된다.

## UI-02 · 접근성과 keyboard

- [ ] contrast token이 WCAG AA를 만족한다.
- [ ] settings/plugins input에 programmatic label이 있다.
- [ ] wiki heading order가 올바르다.
- [ ] main landmark가 화면당 하나다.
- [ ] visible focus와 keyboard order가 올바르다.
- [ ] 16 route × 2 viewport axe가 0건이다.
- [ ] project/chat/settings/plugin/Cmd+K keyboard workflow가 통과한다.

## QLT-01 · 전체 품질 gate

- [ ] master E2E의 undefined import/main을 제거했다.
- [ ] master E2E가 실제 server/API/dashboard/task 경로를 사용한다.
- [ ] backend 전체 suite 실패 0이다.
- [ ] frontend 전체 suite 실패 0이다.
- [ ] type/lint/format gate가 모두 exit 0이다.
- [ ] project switch와 compact E2E가 포함된다.
- [ ] 전체 gate를 3회 반복해 flaky 0을 확인했다.

## OBS-01 · 운영 준비

- [ ] request/project/task/conversation correlation ID가 연결된다.
- [ ] 압축/auth/registry/vault/task/provider 핵심 metric이 있다.
- [ ] readiness가 실제 필수 dependency를 검사한다.
- [ ] SLO와 alert threshold/owner/runbook이 있다.
- [ ] backup/restore rehearsal이 성공했다.
- [ ] DB corruption/orphan worktree/project migration rehearsal이 성공했다.

## VAL-01 · 실제 통합 staging

- [ ] local provider streaming/tool/cancel/error가 통과한다.
- [ ] cloud provider 최소 1개가 같은 scenario를 통과한다.
- [ ] Chroma persist/restart/reindex/delete/citation이 통과한다.
- [ ] 실제 MLX 또는 CUDA training lifecycle이 통과한다.
- [ ] promote failure의 rollback이 통과한다.
- [ ] latency/memory/token/cost evidence가 있다.

## VAL-02 · resilience와 soak

- [ ] 다중 project concurrent task에서 leak 0이다.
- [ ] cancel/completion 경쟁에서 contradiction 0이다.
- [ ] kill -9/restart 후 task/event가 복구된다.
- [ ] disk-full/network-loss/provider-timeout이 제어된 상태로 끝난다.
- [ ] browser reconnect에 event loss/duplicate 0이다.
- [ ] P95/P99/error/memory/FD threshold를 만족한다.
- [ ] 8시간 soak 뒤 orphan/leak/lock 0이다.

## DOC-01 · 문서 동기화

- [ ] README clean install 절차가 실제 성공한다.
- [ ] project 선택과 context compact 동작을 설명한다.
- [ ] auth reset과 WS 정책을 설명한다.
- [ ] backup/restore/upgrade/rollback runbook이 있다.
- [ ] container/provider/hardware 지원 범위가 정확하다.
- [ ] API example이 contract test와 동기화된다.
- [ ] 과거 완료 주장과 현재 상태의 모순을 제거했다.

## RC-01 · 100점 release candidate

- [ ] immutable candidate full SHA를 기록했다.
- [ ] 모든 task 상태가 DONE이다.
- [ ] 열린 P1/P2 finding이 0건이다.
- [ ] backend/frontend/type/lint/format/E2E/a11y가 모두 green이다.
- [ ] wheel/sdist/container/SBOM/provenance checksum이 manifest에 있다.
- [ ] actual provider/RAG/hardware staging이 PASS다.
- [ ] concurrency/crash/soak/DR evidence가 PASS다.
- [ ] 독립 code review가 candidate SHA에 PASS다.
- [ ] 독립 security review가 candidate SHA에 PASS다.
- [ ] 독립 manual QA가 candidate SHA에 PASS다.
- [ ] 독립 release gate review가 candidate SHA에 PASS다.
- [ ] rubric 영역별 20+20+15+15+10+10+10 = 100점이다.
- [ ] rollback rehearsal 후 승인자가 Go 결정을 기록했다.

## 최종 점수판

| 영역 | 현재 | 목표 | 상태 | 증거 링크 |
|---|---:|---:|---|---|
| 기능 범위·제품 골격 | 15/20 | 20/20 | TODO |  |
| 정확성·핵심 계약 | 7/20 | 20/20 | TODO |  |
| 데이터 무결성·동시성 | 5/15 | 15/15 | TODO |  |
| 보안 | 8/15 | 15/15 | TODO |  |
| UX·접근성 | 8/10 | 10/10 | TODO |  |
| 테스트·유지보수성 | 8/10 | 10/10 | TODO |  |
| 릴리스·운영 | 2/10 | 10/10 | TODO |  |
| **합계** | **53/100** | **100/100** | **TODO** |  |
