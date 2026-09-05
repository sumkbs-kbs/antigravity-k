---
title: User change file-level review
tags: [audit, user-changes, risk-classification]
date: 2026-08-30
---

# 사용자 변경사항 파일별 검토

## 현재 기준 (2026-08-30)

작성자와 무관하게 원래 사용자가 제시한 234건을 포함해 현재 working tree의
모든 경로를 범위로 삼았다. 최신 `git status --short`는 285개 경로(생성된
`dashboard/node_modules`·`dashboard_dist` 포함)를 보고하며, codebase-memory
영향 분석은 227개 변경 경로를 확인했다. 아래의 244개/255개 수치는 이전
continuation 당시의 스냅샷이고, 현재 수치와 혼동하지 않는다.

- P0 보안·경로·릴리스 baseline(v1/v2)과 삭제 모듈 호환성 판단은 회귀 검증과
  문서화까지 완료했다.
- `scripts/api_forwarder.py`는 FastAPI `on_event` deprecation을 lifespan으로
  전환했고, 파일 Ruff/LSP/basedpyright 경고가 0이다.
- 전체 Python 회귀 `4818 passed, 6 skipped`, 대시보드 Vitest `589 passed`,
  typecheck/lint/build, production audit 0건을 최신 게이트에서 확인했다.
- 전역 basedpyright는 `864 files, 0 errors, 21,669 warnings`로 오류는 없지만,
  경고 제로는 파일 단위로만 달성된 상태다. 남은 21,669건은 고위험 런타임
  경계부터 단계적으로 축소한다.

- working-tree continuation on `2026-08-30`: `src/antigravity_k/finetune/trainer.py`의 데이터셋 JSON, MLX subprocess, 학습 결과, CLI Namespace 경계를 명시 타입으로 전환했다. 관련 finetune 회귀 61개, CLI `--help` smoke, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), mypy, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 23177 warnings, 0 notes`로 `200`건 감소했다. 사용자 dirty 파일과 겹쳐 변경은 미스테이지 상태로 보존했다.

- working-tree continuation on `2026-08-30`: `tests/test_system_api_memory_suite.py`의 FastAPI 응답 JSON, MagicMock 메서드, 시스템/메모리·보안 입력 경계를 명시 타입으로 전환했다. 53개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), mypy, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 23377 warnings, 0 notes`로 `221`건 감소했다. 사용자 dirty 파일과 겹쳐 변경은 미스테이지 상태로 보존했다.

- working-tree continuation on `2026-08-30`: `tests/test_git_api_endpoints.py`의 Git API HTTP JSON, 임시 저장소 fixture, subprocess, private helper 경계를 타입화했다. 28개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), mypy, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 23598 warnings, 0 notes`로 `281`건 감소했다. 사용자 dirty 파일과 겹쳐 변경은 미스테이지 상태로 보존했다.

- working-tree continuation on `2026-08-30`: `tests/test_system_api_skills.py`의 HTTP JSON/pytest fixture/SkillLoader·Registry·Publisher double 경계를 타입화했다. 20개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), mypy, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 23879 warnings, 0 notes`로 `295`건 감소했다. 사용자 dirty 파일과 겹쳐 변경은 미스테이지 상태로 보존했다.

- 최신 전체 basedpyright 재측정은 `0 errors, 24174 warnings, 0 notes`이며, clean 테스트 파일 `tests/test_agent_fabric_orchestration.py`를 `c1fc1bf`로 정리해 fake agent/orchestrator protocol과 동적 메서드 경계를 0 warnings로 만들었다. 11개 테스트와 Ruff/Ruff-format/mypy/pre-commit이 통과했고, 사용자 dirty path 244개는 그대로 보존했다.

- 최신 전체 basedpyright 재측정은 `0 errors, 24322 warnings, 0 notes`이며, clean 테스트 파일 `tests/test_phase1_e2e.py`와 `tests/test_skill_installer.py`의 private 메서드·JSON·mock·파일 반환 경계를 `9456266`·`49fe488` 독립 커밋으로 정리해 두 파일 모두 0 warnings를 확인했다. 사용자 dirty path 244개는 누가 변경했는지와 무관하게 검토 목록에 포함하되 stage/revert하지 않았다.

- 최신 전체 basedpyright 재측정은 `0 errors, 24970 warnings, 0 notes`이며, clean provider 파일의 `_apply_dynamic_inference_config` 프로필 경계와 Ollama provider 설정 URL 반환값을 `e7262f7`·`e5efbe4` 독립 커밋으로 좁혔다. provider 회귀 93개(추가 inference 테스트 10개)와 Ruff, Ruff-format, mypy, pre-commit이 통과했고 provider 전역 진단은 `247 → 235`로 감소했다. 사용자 dirty path는 계속 보존했다.

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
- 최신 전체 basedpyright: `0 errors, 24970 warnings, 0 notes`.
- 대시보드 typecheck/lint/Vitest/build 통과.
- 대시보드 `npm audit --omit=dev`: `0 vulnerabilities`. 중첩 `monaco-editor → dompurify`는 `707a312`의 `3.4.14` override로 해소했고 Monaco major 변경은 하지 않았다.
- `git diff --check`는 생성된 `dashboard_dist/assets/api-client-CWhh0G02.js`의 기존 trailing whitespace 4건을 제외한 사용자 코드 경로에서 통과한다.

## 커밋 정책

1. 사용자 dirty path는 기본적으로 stage/revert하지 않는다.
2. 결함 수정과 새 회귀 테스트만 독립 커밋하며, 혼합 파일은 `git apply --cached`로 해당 hunk만 stage한다.
3. 생성물·lockfile·대규모 데이터는 별도 승인 없이는 커밋하지 않는다.
4. 각 단위는 focused test, Ruff, basedpyright, pre-commit 결과와 제한사항을 ledger에 기록한다.
- System API/trainer continuation (2026-08-30): `src/antigravity_k/api/routes/system_api.py`의 경고 197건을 JSON/YAML, PTY, 로그·설정, 하네스 경계로 분류해 0건으로 정리했다. 관련 API 회귀 110개가 통과했고 Ruff/Ruff-format/mypy/pre-commit 및 파일 basedpyright 0/0을 확인했다. `trainer.py`는 평가 백엔드 inference callable 계약을 추가해 pre-commit mypy 오류도 해소했으며 파일 basedpyright 0/0이다. 전체 basedpyright는 22,980 warnings, 0 errors이며 사용자 dirty path 244개는 그대로 미스테이지 상태다.
- Model manager continuation (2026-08-30): `src/antigravity_k/engine/model_manager.py` warnings `248 -> 212` through typed configuration/JSON boundaries and mock-safe routing checks. Lifecycle/generate/stream focused suite passed `83`; Ruff, Ruff-format, mypy, pre-commit, and file basedpyright `0 errors/0 warnings` passed. Whole-tree basedpyright is `0 errors, 22944 warnings, 0 notes`; all 244 user-owned dirty paths remain unstaged.
- Model manager hook caveat: the targeted file pre-commit run passed; the repository-wide commit hook reported a pre-existing mypy assignment error in `src/antigravity_k/engine/tool_loop.py:590`, which remains outside this change.
- Inference provider continuation (2026-08-30): removed the redundant provider-config `isinstance` branch in `inference_providers.py`; file basedpyright warnings `235 -> 234`, focused inference-provider suite `10 passed`, and file-level Ruff/Ruff-format/mypy/pre-commit passed. User-owned dirty paths remain unstaged; broad SDK payload typing is deferred to boundary-specific adapters.
- Orchestrator continuation (2026-08-30): committed only `@final` on `OrchestratorAgent` as `2b005ab`; the existing user changes in the same file (long-context shaping, tool phase masking, persistent agency wiring) were restored unstaged. File warnings `191 -> 168`; focused regression `22 passed`; dirty path count is 244.

## 전체 코드 재점검 갱신 (2026-08-30)

- 작성자와 무관하게 현재 `git status --short`의 `255`개 경로를 재검토 범위로 확정했다(`155 modified`, `42 deleted`, `2 submodule`, `56 untracked`). 분류 누락을 방지하기 위해 `src 149`, `tests 65`, `dashboard 19`, `scripts 4`, `.omo 4`, `docs 4`, `data 3`, `.tmp 2`, `vault_data 1`, root/config 및 산출물을 모두 포함한다.
- 최신 전역 basedpyright는 `863 files / 0 errors / 21636 warnings / 0 notes`다. 오류는 0건이며, 경고 제로 목표는 미달이므로 고경고 파일 순회가 잔여 작업이다. `model_manager.py`, `task_runner.py`, `api_forwarder.py`는 파일 단위 0/0을 유지한다.
- dead-code 감사는 405개 모듈 중 30개 unreachable 후보(B 20, B+ 10)를 보고한다. 삭제된 모듈과 후보를 곧바로 제거하지 않고, 외부 import·플러그인·entry-point 호환성 및 패키징을 먼저 검증한다.
- 추가 누락 위험: held-out v2 데이터가 evaluation 코드에는 인식되지만 release baseline/policy/package-data에는 반영되지 않았을 가능성, 삭제된 `agent_api.py`를 언급하는 stale 문서, 삭제된 multi-agent 모듈의 외부 import 계약, abstract/no-op `pass` 분류가 있다.
- 현재 사용자 변경은 어떤 파일도 자동 stage/revert하지 않았다. 생성된 `dashboard_dist`·`node_modules`, 삭제 상태 tracked 파일, benchmark 결과 데이터는 릴리스 정책 결정 전 보류한다.

## 잔여 작업 재정리 (2026-08-30)

- 전체 검토 범위는 현재 dirty path 289개이며, 기존 사용자 변경 234건을 포함해 변경 주체와 무관하게 tracked/untracked/deleted/generated 경로를 모두 점검한다. 소유권이 불명확한 경로는 stage·revert하지 않는다.
- 명령 실행 경계 우선 작업을 완료했다. `terminal_tools.py`의 123개 타입 경고를 0개로 줄이고, sandbox seatbelt 접근을 public API로 통합했으며, 관련 회귀 21개와 persistent/PTY 실행 스모크를 통과했다.
- 전역 기준은 `basedpyright 864 files / 0 errors / 21,395 warnings`이다. 다음 순서는 orchestrator agent(168), ambient watchdog 테스트(161), agent runtime 테스트(157), vision/dom hybrid 테스트(147)이며, 각 파일은 동작 회귀와 함께 처리한다.
- 별도 잔여는 대시보드 HTTP 수동 DOM 게이트, clean export/release 산출물 정책, 삭제 모듈 외부 import 호환성이다. `git diff --check`는 현재 통과했다.

## 오케스트레이터 경계 재정리 (2026-08-30)

- `agent.py`의 모델 매니저 입력을 최소 Protocol과 런타임 생성 계약으로 분리해 실제 구현과 테스트 fake를 함께 수용했다. `max_engine.py`는 내부 속성의 과도한 Protocol 요구를 제거했다.
- 파일 경고 `168 → 97`, 변경 파일 오류 `0`, MAX/오케스트레이터/subagent/planning 회귀 `58 passed, 1 skipped`, Ruff 통과.
- 전역 기준은 `864 files / 0 errors / 21,326 warnings`; 다음 정리 순서는 ambient watchdog 테스트, agent runtime 테스트, vision/dom hybrid 테스트다.
- 증거 문서 갱신 후 dirty path snapshot은 `290`개(`modified 187`, `deleted 43`, `submodule 2`, `untracked 58`)로 재확인했으며, 234건 사용자 변경을 포함한 전체 경로를 계속 검토 대상으로 둔다.

## 보안 HIGH 1차 완료 (2026-08-30)

- `ci_tools.py`의 테스트 실행을 argv/shell=False 경계로 전환하고, `api_forwarder.py`의 비루프백 HTTP·WebSocket 요청에 강한 PIN 검증을 적용했다.
- 보안 회귀 포함 `66 passed`, 정적 보안 게이트 및 Ruff/LSP 통과. PIN 노출·환경 파일 권한·code-intel/deny-rule 정책은 다음 잔여 단위다.

## 런타임 QA 및 readiness 보정 (2026-08-30)

- Deep health 런타임 import 오류를 수정했고 TestClient에서 `/api/health/deep` 200 payload를 확인했다. 관련 시스템·Voice·서버 import 회귀는 `59 passed`다.
- Chat SSE generator는 동일 Context에서 threadpool 경계를 유지하며, agent runtime context 회귀가 통과한다. 과거 수동 증거의 `expected_tools` 및 `different Context` 오류는 최신 경로에서 재현되지 않는다.
- Dashboard health schema가 백엔드의 `backends: []` wire shape를 수용해 readiness false 고정을 해소했다. client/uiStore 테스트 `43 passed`, production build 통과.
- `TaskExecutionContext.state_store`를 명시적 `TaskStateStore` 타입으로 보강했다. 변경 파일 LSP 오류는 0건이다.
- Voice 503은 `AGK_STT_COMMAND_JSON`가 없는 환경에서 의도적으로 반환되는 운영 전제조건 미충족이며, 임의 STT 명령은 추가하지 않았다.
- 최신 전역 기준은 `864 files / 0 errors / 21,354 warnings`로 오류 제로는 유지하지만 경고 제로는 잔여다. 사용자 변경 234건을 포함한 dirty tree는 stage/revert하지 않았다.

## 최종 게이트 갱신 (2026-08-30)

- `TaskExecutionContext.state_store`를 `TaskStateStoreProtocol`로 분리해 순환 import 오류를 해소했다. 관련 변경 파일 LSP 오류 0건, Ruff 및 diff 검사 통과.
- 전체 pytest는 `4821 passed, 6 skipped`로 완료됐고, 핵심 오케스트레이터/task-state/release 묶음은 `63 passed`로 재확인했다.
- Dashboard client/uiStore 43개 테스트와 production build(876 modules)가 통과했다. 백엔드 미설정 시 `backends: []` wire shape를 정상 수용한다.
- TestClient API 스모크에서 `/v1/health`, `/api/system/status`, `/api/health/deep` 모두 200을 확인했다. deep health `degraded`는 모델 매니저 부재를 진단 결과로 노출한다.
- 전역 경고 제로는 아직 미달이며, 전역 억제는 적용하지 않았다. 사용자 변경 234건을 포함한 dirty tree는 stage/revert하지 않았다.
- `file://` 브라우저 DOM 게이트는 도구 정책상 수행할 수 없어 build/API 관찰로 대체했다. Voice 503은 `AGK_STT_COMMAND_JSON` 설정이 필요한 운영 전제조건이다.

## Warning debt continuation (2026-08-30)

- `test_ambient_watchdog.py` fixture·테스트 인자와 미사용 결과를 명시해 파일 경고를 `161 → 51`으로 줄였다. 동작 테스트 `20 passed`, Ruff 통과.
- `tool_loop.py`의 저장소 반환 계약을 `TaskStateStoreProtocol`로 정렬하고 동적 모델 매니저 호환 경계를 보존했다. 관련 회귀 `53 passed`, Ruff 및 diff 검사 통과.
- 최신 전역 basedpyright는 `864 files / 0 errors / 21,176 warnings`다. 다음 정리 대상은 `test_agent_runtime.py`의 fixture·동적 mock 경계이며, 사용자 변경 234건은 계속 stage/revert하지 않는다.

## Warning debt continuation 2 (2026-08-30)

- 작성자와 무관하게 전체 코드 검토 범위를 유지하면서 고경고 테스트 단위의 타입 경계만 축소했다. `test_agent_runtime.py` `156 → 75`, `test_vision_dom_hybrid.py` `147 → 24`, `test_prompt_meta_evolution.py` `145 → 43`, `test_context_shaper.py` `144 → 12`, `test_self_consistency.py` `144 → 36`이다.
- 각 단위의 동작 검증은 각각 `33`, `38`, `17`, `34`, `33`개 테스트가 통과했으며, 변경 파일 Ruff와 `git diff --check`도 통과했다. `test_orchestrator.py`는 fixture·메시지 경계만 보강하고 회귀 `9 passed`를 확인했다.
- `self_consistency.py`의 `collect_samples`/`run`에 `**gen_kwargs: object` 계약을 추가해 호출부의 부분 미지정 경고를 줄였다. API 동작과 keyword 전달 형태는 유지된다.
- 최신 전체 basedpyright는 `0 errors, 20,586 warnings, 0 notes`다. 남은 경고의 큰 비중은 동적 `MagicMock`, protected private API를 검증하는 테스트, 기존 동적 orchestrator/stream 계약에 집중된다. 전역 억제 지시문은 적용하지 않았다.
- 사용자 변경 234건, 생성물, 삭제 상태 tracked 파일, untracked 파일은 모두 계속 미스테이지 상태로 보존한다. 이번 연속 작업에서도 commit·stage·revert를 수행하지 않았다.

## 전체 코드 검토 연속 기록 3 (2026-08-30)

- 작성자와 무관하게 전체 코드 검토 범위를 유지한 채 `tests/test_filesystem_endpoints.py`의 fixture 및 JSON 응답 타입 경계를 정리했다. protected 캐시 멤버는 명시적 typed adapter를 통해서만 접근하도록 격리했다.
- 해당 파일은 LSP/basedpyright `0 errors, 0 warnings`, Ruff, `git diff --check`를 통과했고 Filesystem API 회귀 `15 passed`를 확인했다.
- 전체 basedpyright 기준은 `864 files / 0 errors / 20,448 warnings / 0 notes`이며, 이전 20,586건 대비 138건 감소했다. 다음 대상은 `tests/test_slash_commands_session.py` 138건이다.
- 기존 사용자 변경 234건을 포함한 dirty tree, 생성물, 삭제 상태 tracked 파일은 stage·revert·commit 없이 보존했다.

## 전체 코드 검토 연속 기록 4 (2026-08-30)

- `tests/test_slash_commands_session.py`를 작성자와 무관한 전체 감사 범위에서 정리했다. 세션 Protocol, callback·SQLite 타입, protected 핸들러 호출을 명시적 경계로 보강했다.
- 해당 파일은 LSP/basedpyright `0 errors, 0 warnings`, Ruff, `git diff --check`를 통과했고 슬래시 커맨드 회귀 `20 passed`를 확인했다.
- 전체 basedpyright 기준은 `864 files / 0 errors / 20,310 warnings / 0 notes`이며 이전 20,448건 대비 138건 감소했다. 다음 대상은 `scripts/generate_docstrings.py` 133건이다.
- 기존 사용자 변경 234건을 포함한 dirty tree, 생성물, 삭제 상태 tracked 파일은 stage·revert·commit 없이 보존했다.
