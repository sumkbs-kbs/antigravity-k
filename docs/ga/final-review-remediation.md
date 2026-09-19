---
title: 최종 검토 개선(remediation) 증거 인덱스
status: in-review
date: 2026-09-11
reviewed_sha: 8794aaecabf5664a7ee560b104e0115d915aabb7
plan: docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md
checklist: docs/15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md
source_review: docs/qa/2026-09-10/FINAL_REVIEW.md
tags: [ga, remediation, evidence-index, release-gate]
---

# 최종 검토 개선(remediation) 증거 인덱스

`docs/qa/2026-09-10/FINAL_REVIEW.md`(REQUEST CHANGES)에 대응하는 개선 작업의
증거를 한 곳에 연결한다. 구현·실측이 끝난 항목도 **독립 검토(RP-14) 전에는
폐쇄로 간주하지 않는다.** 과거 GA-100 33/33 기록은 구현 완료 이력으로 보존되며
현재 SHA의 출시 승인과는 구분된다.

## 진행 요약 (2026-09-11 기준)

- RP-00/01/02/03/04/05/06/07/08/09/10/11/13 DONE · RP-12 IN_PROGRESS(후보 4b202113 full gate 20/20 PASS, soak-006 진행 중) · RP-14 TODO
- 2026-09-11: RP-03/04 재작업 실측 및 독립 검증 완료(attempt-004, rp03_verify3/rp04_verify3 APPROVE, 68 passed). RP-05 실제 2개 uvicorn API worker + 재시작 실측 및 독립 검증 완료(attempt-004, rp05_verify3 APPROVE, 25 passed). RP-07 격리 설치 및 4-way 바이트 일치 독립 검증 완료(attempt-003, rp07_verify APPROVE). RP-08 결정적 더블(8 passed) 및 Playwright 브라우저 E2E 프로젝트 전환 실측 검증 완료(attempt-002, rp08_verify APPROVE). RP-09 store+API 43 passed(초기 제약 보존 수정) 및 Playwright 브라우저 수동 압축 E2E 실측 검증 완료(attempt-002, rp09_verify APPROVE). RP-10 문서·승인 상태 준비 독립 검증 완료(`RP-10/attempt-001/review.md`, rp10_verify APPROVE). RP-11 gate·증거 수집기 및 crash recovery 독립 검증 완료(`RP-11/attempt-001/review.md`, rp11_verify APPROVE, 18 passed). RP-13 clean-install outside cwd API/auth + 이전 artifact 롤백 DR 5/5 + 11개 아티팩트 매니페스트 결합 및 독립 검증 완료(attempt-002, rp13_verify2 APPROVE, 8 passed).

## 발견 → 작업 → 증거 연결

| 발견 | 작업 | 상태 | 핵심 증거 (원문) | 잔여 |
|---|---|---|---|---|
| FR-01 host 직접 실행 | RP-01 | DONE | `.omo/evidence/final-review-remediation/RP-01/attempt-003/` — rp01_verify2 APPROVE: focused 44, 실 seatbelt 12/12 | 최종 출시 판정(RP-14) |
| FR-02 shell 확장 우회 | RP-02 | DONE | `.omo/evidence/final-review-remediation/RP-02/attempt-003/` — rp02_verify2 APPROVE: source 89, sentinel/root confinement PASS | 최종 출시 판정(RP-14) |
| FR-03 transaction 이탈 | RP-03 | DONE | `RP-03/attempt-004/review.md` — rp03_verify3 APPROVE: write 전 소유권 기록 + commit CAS, driver residue 0, rolled 1→2, 17 focused pass, 68 consumer pass | 최종 출시 판정(RP-14) |
| FR-04 전체 트리 rollback | RP-04 | DONE | `RP-04/attempt-004/review.md` — rp04_verify3 APPROVE: 부재 소유 파일 외부 삭제 보존·충돌 기록, 독립 driver `concurrent_deletion_preserved=true`, 45 focused pass, 68 consumer pass | 최종 출시 판정(RP-14) |
| FR-05 stale 대화 캐시 | RP-05 | DONE | `RP-05/attempt-004/review.md` — rp05_verify3 APPROVE: 2개 실제 uvicorn API worker + 재시작 worker 실측 완료. Worker B rev 1 캐시 후 A가 rev 2 append 시 B가 즉시 rev 2 관찰, stale expected=1은 HTTP 409 거부, cold restart Worker C rev 2/이력 보존. 25 passed | 최종 출시 판정(RP-14) |
| FR-07 Chroma false-green | RP-06 | DONE | `.omo/evidence/final-review-remediation/RP-06/attempt-003/` — rp06_verify2 APPROVE: persistent Chroma/negative/CLI 독립 재현 | RP-12 same-SHA 재실행 |
| FR-10 config 불일치 | RP-07 | DONE | `RP-07/attempt-003/review.md` — rp07_verify APPROVE: 4-way 바이트 동일, registry 31 passed, 격리 venv wheel 설치·`agk --help` exit 0 | 최종 출시 판정(RP-14) |
| 폴더→prompt E2E 공백 | RP-08 | DONE | `RP-08/attempt-002/review.md` — rp08_verify APPROVE: 바인딩→도구→2차 provider payload marker 포함/배제 8 passed + Playwright 브라우저 E2E 프로젝트 전환 2 passed (`ws-04-project-switch.spec.ts`) | 최종 출시 판정(RP-14) |
| 압축 E2E 공백 | RP-09 | DONE | `RP-09/attempt-002/review.md` — rp09_verify APPROVE: store+API 종단간 43 passed(초기 제약 보존 결함 수정) + Playwright 브라우저 수동 압축 E2E 4 passed (`conversation-compaction.spec.ts`) | 최종 출시 판정(RP-14) |
| FR-06/09 출시 gate·산출물 | RP-11~13 | RP-11 DONE, RP-12 IN_PROGRESS, RP-13 DONE | RP-11 `RP-11/attempt-001/review.md` rp11_verify APPROVE (검증기 18 passed, missing required/60s soak/false metric 거부 실측, kill -9 crash recovery SC-4 검증); RP-12 candidate 4b202113 single-shot gate 20/20 PASS, soak-006 진행 중; RP-13 `RP-13/attempt-002/review.md` rp13_verify2 APPROVE (11개 artifacts manifest 결합, 이전 버전 롤백 DR 5/5, clean install API/auth 200 원문 로그) | 28,800초 soak 완료 판정 + 최종 출시 판정(RP-14) |
| FR-08 문서 정합성 | RP-10 | DONE | `RP-10/attempt-001/review.md` — rp10_verify APPROVE: 본 문서 + checklist 갱신 및 증거 인덱스 정합화 완료; 실제 승인 artifact는 BLOCKED_EXTERNAL | 최종 승인 확인(RP-14) |


## 환경 교정 기록

2026-09-10: 저장소 `.venv`에 형제 checkout(`../antigravity-k`)에서 설치된 stale
`antigravity_k` 사본이 소스 트리를 가려 attempt-002 작업자들의 결과가 갈렸다.
editable 재설치로 해소(`RP-00/attempt-003/metadata.json` environment_correction).

## 승인 상태 (BLOCKED_EXTERNAL)

법무/개인정보/모델·공급자 약관/라이선스/운영 승인은 실제 담당자 artifact 인계 전까지
**취득되지 않은 상태**다. 에이전트가 승인자·내용을 대신 작성하지 않는다. 해당 항목은
최종 GO의 blocker로 유지된다(`GA_CLAIMS_AND_REVIEW_REGISTER.md` 참조).

## 지원 범위

`GA_SUPPORT_MATRIX.md` 분류(Supported/Experimental/Unsupported)는 유지된다.
이번 remediation으로 어떤 행도 Supported로 승격하지 않았다 — 승격 요건(기록된
staging run·owner·승인)은 RP-12/14 이후에만 충족될 수 있다.
