---
title: User change file-level review
tags: [audit, user-changes, risk-classification]
date: 2026-08-30
---

# 사용자 변경사항 파일별 검토

- 최신 전체 basedpyright 재측정은 `0 errors, 24985 warnings, 0 notes`이며, clean 파일 `scripts/demo_debate_run.py`의 deprecated `os.system`과 기본 자동 커밋 부작용을 `f6b83a0` 독립 커밋으로 제거했다. `create_git_checkpoint=True`에서만 Git checkpoint를 실행하도록 바꾸고 격리 기본 실행·명시적 checkpoint smoke를 통과했으며, 파일 경고는 `5 → 0`으로 감소했다. 사용자 dirty path는 기존 변경을 포함해 보존했다.

- 최신 전체 basedpyright 재측정은 `0 errors, 25401 warnings, 0 notes`이며, `.agent/skills/k-skill/scripts/ktx_booking.py`의 optional 의존성·JSON 응답 경계를 `54cbcd7` 독립 커밋으로 정리해 해당 파일 경고를 `97 → 0`으로 낮췄다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

- 최신 대시보드 의존성 검증 커밋은 `707a312`이며, `npm audit --omit=dev`가 `0 vulnerabilities`를 보고한다. Monaco `0.56.0`은 유지하고 중첩 `dompurify`만 `3.4.14`로 override했다. 생성된 `dashboard_dist`와 `node_modules` 변경은 사용자 산출물로 보존했다.

- 최신 전체 basedpyright 재측정은 `0 errors, 25498 warnings, 0 notes`이며, `tests/test_max_engine.py`의 보호 메서드·MAX 핸들러 경계를 `9ecfb4e` 독립 커밋으로 정리해 해당 파일 경고를 `45 → 0`으로 낮췄다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

- 최신 전체 basedpyright 재측정은 `0 errors, 25012 warnings, 0 notes`이며, clean 파일 `src/antigravity_k/engine/model_manager.py`의 암시적 문자열 연결 2건과 미사용 반환값 1건을 `1539306` 독립 커밋으로 정리했다. lifecycle/generate/stream 회귀 테스트 83개와 Ruff, Ruff-format, mypy, pre-commit이 통과했다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

- 최신 전체 basedpyright 재측정은 `0 errors, 25007 warnings, 0 notes`이며, clean 파일 `src/antigravity_k/security/lintai_scanner.py`의 실행 파일·JSON 출력 경계를 명시해 `3934a78` 독립 커밋으로 정리했다. 해당 3개 테스트와 Ruff, Ruff-format, mypy, pre-commit이 통과했고 파일 경고는 `5 → 0`으로 감소했다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

- 최신 전체 basedpyright 재측정은 `0 errors, 25001 warnings, 0 notes`이며, clean 파일 `src/antigravity_k/engine/call_hierarchy_graph.py`의 AST visitor override·속성·미사용 결과를 `852224f` 독립 커밋으로 정리했다. 해당 테스트 1개와 Ruff, Ruff-format, mypy, pre-commit이 통과했고 파일 경고는 `6 → 0`으로 감소했다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

- 최신 전체 basedpyright 재측정은 `0 errors, 24995 warnings, 0 notes`이며, clean 파일 `src/antigravity_k/engine/code_intel/impact_analyzer.py`의 graph·JSON 반환 경계와 미사용 입력을 `d8e1be7` 독립 커밋으로 정리했다. 해당 테스트 2개와 Ruff, Ruff-format, mypy, pre-commit이 통과했고 파일 경고는 `6 → 0`으로 감소했다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

- 최신 전체 basedpyright 재측정은 `0 errors, 24990 warnings, 0 notes`이며, clean 파일 `demo_service/token_bucket.py`의 limiter 상태·lock 속성을 `e233b06` 독립 커밋으로 정리했다. `tests/test_live_gateway.py` 4개와 Ruff, Ruff-format, mypy, pre-commit이 통과했고 파일 경고는 `5 → 0`으로 감소했다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.

## 범위

- `git status --short` 기준 244개 dirty path를 작성자와 관계없이 재분류했다.
- 집계는 `src` 148, `tests` 60, `dashboard` 19, `scripts` 3, `.tmp` 2, 기타 12다.
- 상태는 수정 144, 삭제 42, 서브모듈 변경 2, 미추적 56이다.
- 미추적 Python 21개는 전체 정적 진단·pytest 탐색 범위에 포함됐지만 아직 독립 커밋하지 않았다. 미추적 JS/TS 30개는 모두 `src/antigravity_k/dashboard_dist/assets` 빌드 산출물이며, 대시보드 typecheck/lint/Vitest/build로 검증하고 소스 커밋에서는 제외한다.
- 현재 Git tracked+untracked Python 871개를 AST 문법 검사했다. 현존 파일의 문법 오류는 0건이며, 삭제 상태라 읽을 수 없는 tracked 경로 12개(`src/antigravity_k/agents/{commands,coordinator,team_manager}.py`, `src/antigravity_k/engine/{json_logger,logging_util,memory_hygiene}.py`, `src/antigravity_k/integrations/{discord_bot,slack_bot}.py`, `src/antigravity_k/knowledge/artifact_service.py`, `src/antigravity_k/scripts/ingest_obsidian.py`, `tests/test_{commands,multi_agent}.py`)는 외부 호환성 검토 잔여 항목으로 분리했다.
- 최종 게이트에서 전체 pytest `4806 passed, 6 skipped`, 대시보드 588개 테스트·typecheck·lint·build, 전역 Ruff가 통과했다. 사용자 dirty path 244개는 stage/revert하지 않았고, 생성된 dashboard_dist trailing whitespace 4건만 보류 위험으로 남겼다. production `npm audit --omit=dev`는 `0 vulnerabilities`다.
- 앱 재시작 뒤에도 codebase-memory MCP `list_projects`가 `Transport closed`로 실패했다. 소스 `src/antigravity_k/engine/tool_loop.py` 경고는 `369 → 13`으로 축소했으며, 남은 보호 멤버·동적 외부 경계는 사용자 변경 소유권 확인 후 처리한다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25015 warnings, 0 notes`이며, provider stream 경계 보강(`8b3a26a`)과 `tests/test_tool_loop.py`의 direct-response·context-compression 및 공용 fixture 경계(`8211882`)를 통해 해당 테스트 파일 경고를 `119 → 0`, 소스 tool-loop 파일 경고를 `369 → 13`, provider 파일 경고를 `276 → 247`로 낮췄다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25662 warnings, 0 notes`이며, 장학금 필터 구현의 JSON·argparse 경계를 `eec4dec` 독립 커밋으로 정리해 해당 파일 경고를 `210 → 0`으로 낮췄다. 사용자 dirty path 244개는 계속 stage/revert하지 않았다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25872 warnings, 0 notes`이며, durable resume/quality failure fixture 정리는 사용자 dirty path를 건드리지 않고 `0bfba41` 독립 커밋으로 분리했다. 해당 파일 경고는 `133 → 119`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25886 warnings, 0 notes`이며, Qwen scratchpad 실행 fixture 정리는 사용자 dirty path를 건드리지 않고 `dfbc1e8` 독립 커밋으로 분리했다. 해당 파일 경고는 `156 → 133`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25909 warnings, 0 notes`이며, native-tool follow-up fixture 정리는 사용자 dirty path를 건드리지 않고 `c5a947d` 독립 커밋으로 분리했다. 해당 파일 경고는 `176 → 156`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25929 warnings, 0 notes`이며, tool-loop outcome/citation fixture 정리는 사용자 dirty path를 건드리지 않고 `247ee90` 독립 커밋으로 분리했다. 해당 파일 경고는 `196 → 176`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25949 warnings, 0 notes`이며, tool-loop guardrail/step-limit fixture 정리는 사용자 dirty path를 건드리지 않고 `de084f2` 독립 커밋으로 분리했다. 해당 파일 경고는 `227 → 196`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25980 warnings, 0 notes`이며, tool-loop tool-call/스트림 오류 fixture 정리는 사용자 dirty path를 건드리지 않고 `cf4c4b2` 독립 커밋으로 분리했다. 해당 파일 경고는 `238 → 227`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 25991 warnings, 0 notes`이며, run_loop 테스트 경계 정리는 사용자 dirty path를 건드리지 않고 `c815f09` 독립 커밋으로 분리했다. 해당 파일 경고는 `396 → 238`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 26149 warnings, 0 notes`이며, tool-loop 비동기 실행 테스트 정리는 사용자 dirty path를 건드리지 않고 `953cff5` 독립 커밋으로 분리했다. 해당 파일 경고는 `425 → 396`으로 감소했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 26955 warnings, 0 notes`이며, 이번 CI 도구 테스트 정리는 사용자 dirty path를 건드리지 않고 독립 커밋으로 분리했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 26862 warnings, 0 notes`이며, config editor 테스트 정리도 사용자 dirty path를 건드리지 않고 독립 커밋으로 분리했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 26770 warnings, 0 notes`이며, tiptap 패턴 테스트 정리도 사용자 dirty path를 건드리지 않고 독립 커밋으로 분리했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 26677 warnings, 0 notes`이며, task state 테스트 정리도 사용자 dirty path를 건드리지 않고 독립 커밋으로 분리했다.
- 최신 전체 basedpyright 재측정은 `0 errors, 26228 warnings, 0 notes`이며, tool-loop quality-gate 테스트 정리도 사용자 dirty path를 건드리지 않고 독립 커밋으로 분리했다.

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

- 전체 pytest 최종 게이트: `4806 passed, 6 skipped`.
- 최신 전체 basedpyright: `0 errors, 24982 warnings, 0 notes`.
- 대시보드 typecheck/lint/Vitest/build 통과.
- 대시보드 `npm audit --omit=dev`: `0 vulnerabilities`. 중첩 `monaco-editor → dompurify`는 `707a312`의 `3.4.14` override로 해소했고 Monaco major 변경은 하지 않았다.
- `git diff --check`는 생성된 `dashboard_dist/assets/api-client-CWhh0G02.js`의 기존 trailing whitespace 4건을 제외한 사용자 코드 경로에서 통과한다.

## 커밋 정책

1. 사용자 dirty path는 기본적으로 stage/revert하지 않는다.
2. 결함 수정과 새 회귀 테스트만 독립 커밋하며, 혼합 파일은 `git apply --cached`로 해당 hunk만 stage한다.
3. 생성물·lockfile·대규모 데이터는 별도 승인 없이는 커밋하지 않는다.
4. 각 단위는 focused test, Ruff, basedpyright, pre-commit 결과와 제한사항을 ledger에 기록한다.
