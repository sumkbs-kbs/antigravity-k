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

- RP-00 DONE · RP-01~09 REVIEW(구현·실측 완료, 독립 검토 이연) · RP-10~13 진행/미착수 · RP-14 미착수
- 재검토 기준 후보 SHA는 아직 고정되지 않았다(RP-12에서 확정).

## 발견 → 작업 → 증거 연결

| 발견 | 작업 | 상태 | 핵심 증거 (원문) | 잔여 |
|---|---|---|---|---|
| FR-01 host 직접 실행 | RP-01 | REVIEW | `.omo/evidence/final-review-remediation/RP-01/attempt-002/` — red(clean HEAD host-secret)/green 원문, 실 seatbelt 7종 manual QA, focused 44 passed | 독립 보안 리뷰(RP-14) |
| FR-02 shell 확장 우회 | RP-02 | REVIEW | `RP-02/attempt-002/` — attached-redirection 토큰화 수정, seatbelt sentinel manual QA, 40 passed; blocker였던 stale site-packages 해소 기록 포함 | 독립 리뷰(RP-14) |
| FR-03 transaction 이탈 | RP-03 | REVIEW | `RP-03/attempt-002/VERIFICATION.md` — no-follow safe-open 구현, TOCTOU 5회 재현, e2e sentinel SHA 불변, 13 passed | 독립 리뷰(RP-14) |
| FR-04 전체 트리 rollback | RP-04 | REVIEW | `RP-04/attempt-002/` — 소유권 기반 복구(`write_owned`), 임시 git repo dirty/untracked 보존, red-proof | SEC 위임 컴포넌트 라우팅 잔여 + 독립 리뷰 |
| FR-05 stale 대화 캐시 | RP-05 | REVIEW | `RP-05/attempt-002/` — aliasing/corrupt/fork red→green 원문, 2-process race 회귀, coordinator 재실행 84 passed | 실 API worker 재생(RP-12) |
| FR-07 Chroma false-green | RP-06 | REVIEW | `RP-06/attempt-002/logs/` — no-op negative control FAIL 확인, 실측 VAL-01 전체 12 passed·exit 0 (Ollama+Chroma+MLX) | RP-12 same-SHA 재실행 |
| FR-10 config 불일치 | RP-07 | REVIEW | `RP-07/attempt-002/` — registry 31 passed, root/bundle 바이트 동일, 격리 venv wheel 설치·`agk --help` exit 0 (코디네이터 재실행) | RP-13 manifest 연결 |
| 폴더→prompt E2E 공백 | RP-08 | REVIEW(1단계) | `RP-08/attempt-001/` — 결정적 double: 바인딩→도구→2차 provider payload marker 포함/배제, in-flight 스냅샷, 8 passed | 실 브라우저 QA + 실 provider(RP-12) |
| 압축 E2E 공백 | RP-09 | REVIEW(1단계) | `RP-09/attempt-001/` — store+API 종단간 43 passed; 제품 결함(초기 제약 누락) 수정 `context_summary.py` | 스트리밍 자동 압축·실 provider(RP-12) |
| FR-06/09 출시 gate·산출물 | RP-11~13 | TODO | — | 후보 SHA 고정 후 전체 gate·28,800초 soak·manifest |
| FR-08 문서 정합성 | RP-10 | IN_PROGRESS | 본 문서 + checklist 갱신 | 최종 동기화는 RP-14 |

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
