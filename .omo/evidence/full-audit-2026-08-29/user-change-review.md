---
title: User change file-level review
tags: [audit, user-changes, risk-classification]
date: 2026-08-30
---

# 사용자 변경사항 파일별 검토

## 범위

- `git status --short` 기준 244개 dirty path를 작성자와 관계없이 재분류했다.
- 집계는 `src` 148, `tests` 60, `dashboard` 19, `scripts` 3, `.tmp` 2, 기타 12다.
- 상태는 수정 144, 삭제 42, 서브모듈 변경 2, 미추적 56이다.
- 미추적 Python 21개와 JS/TS 30개는 전체 정적 진단·pytest/Vitest 탐색 범위에 포함됐지만 아직 독립 커밋하지 않았다.

## 위험도별 판단

### 높음: 동작·데이터 경로

- `src/antigravity_k/engine/rag_indexer.py` (+251/-31): 증분 manifest, 배치 업서트, long-context 검색 변경이 포함됐다. 하위 디렉터리 부분 동기화 시 다른 영역 청크가 삭제되는 결함을 수정하고 회귀 테스트를 추가했다. 관련 RAG/long-context 19개 테스트와 Ruff/mypy/pre-commit을 통과했다.
- `src/antigravity_k/api/routes/system_api.py` (+214/-107): 다수 POST body를 Pydantic strict 모델로 전환하고 시스템 상태 CPU 호출을 thread로 분리했다. API 회귀는 전체 pytest 기준선에 포함되며, 사용자 변경 자체는 독립 커밋하지 않았다.
- `src/antigravity_k/engine/tool_loop.py` (+185/-51): 사용자 변경과 테스트 실행 루프가 겹친다. 90개 tool-loop 테스트는 통과했지만 동적 mock/private API 진단 369건이 남아 별도 소스 경계 정리가 필요하다.
- `src/antigravity_k/api/routes/git_api.py` (+91/-32): Git 요청 body strict 모델과 JSON 오류 처리가 추가됐다. stage/commit/checkout/delete 경로이므로 API 계약·권한 회귀를 별도 승인 전까지 보류한다.

### 중간: 테스트·운영 신뢰성

- `tests/test_tool_sandbox_coverage.py`와 미추적 finetune/agency/RAG/task-process 테스트는 모두 테스트 범위에 포함됐지만, 사용자 추가 테스트와 에이전트가 추가한 회귀 테스트를 커밋 단위로 분리해야 한다.
- `scripts/run_frontier_comparison.py`, `scripts/run_realworld_production_stress_test.py`, 미추적 `scripts/audit_dead_code.py`는 실행·외부 모델·파일 시스템 부작용 여부를 확인한 뒤 운영 스크립트 커밋으로 분리한다.
- `data/benchmark_results.json`(+3513/-3)은 코드가 아닌 결과 데이터로 분류했다. 재현 스크립트와 생성 시점을 확인하기 전에는 수정하지 않는다.

### 낮음 또는 보류: 생성물·삭제·환경

- `dashboard/node_modules/.package-lock.json`과 `.vite/deps/_metadata.json`, `dashboard_dist` 해시 파일은 설치/빌드 churn이다. 소스 검증과 분리하고 승인 없이는 stage·삭제하지 않는다.
- 삭제된 핵심 모듈 10개는 현재 `src/tests/scripts/.agent` 직접 import가 없지만, 문서에는 `team_manager.py` 참조가 남아 있고 외부 패키지/entry-point 호환성은 확인하지 못했다. 삭제 확정 전 import smoke test와 배포 manifest 검증이 필요하다.
- `.tmp/airllm`과 `.tmp/k-skill`은 서브모듈 상태로, 상위 저장소 커밋에서 내부 변경을 흡수하지 않는다.

## 검증 결과

- 전체 pytest 기준선: `4804 passed, 6 skipped`.
- 최신 전체 basedpyright: `0 errors, 27292 warnings, 0 notes`.
- 대시보드 typecheck/lint/Vitest/build 통과.
- 대시보드 `npm audit`: low 1, moderate 3, high 0, critical 0. 중첩 `monaco-editor → dompurify`와 `typed-rest-client → qs` 경로가 남아 있으며, dry-run은 118개 패키지 추가와 Monaco major 변경을 제안했다.
- `git diff --check`는 생성된 `dashboard_dist/assets/api-client-CWhh0G02.js`의 기존 trailing whitespace 4건을 제외한 사용자 코드 경로에서 통과한다.

## 커밋 정책

1. 사용자 dirty path는 기본적으로 stage/revert하지 않는다.
2. 결함 수정과 새 회귀 테스트만 독립 커밋하며, 혼합 파일은 `git apply --cached`로 해당 hunk만 stage한다.
3. 생성물·lockfile·대규모 데이터는 별도 승인 없이는 커밋하지 않는다.
4. 각 단위는 focused test, Ruff, basedpyright, pre-commit 결과와 제한사항을 ledger에 기록한다.
