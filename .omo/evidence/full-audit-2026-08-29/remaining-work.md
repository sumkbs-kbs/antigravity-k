---
title: Ssak-Ai remaining work inventory
tags: [audit, backlog, ownership, warning-zero]
date: 2026-08-29
---

# 남은 작업 인벤토리

## 최신 최종 게이트 (2026-08-30)

- Python 전체 회귀는 이전 전체 실행에서 `4818 passed, 6 skipped`였다. 이후
  `scripts/api_forwarder.py` lifespan 전환에 대해 보안 테스트 `2 passed`와
  startup → init_tools → ready → shutdown 순서 드라이버를 추가 확인했다.
- 전역 Ruff와 `git diff --check`는 통과했다. 릴리스 baseline(v1/v2 digest·행 수·case
  ID·training 금지 플래그) 검증도 `release-baseline: ok`로 통과했다.
- 대시보드는 typecheck, ESLint, Vitest `42 files / 589 tests`, production build,
  `npm audit --omit=dev`(취약점 0건)가 통과했다. Vitest가 출력한 React `act()`
  안내와 의도적으로 발생시킨 에러 로그는 테스트 실패가 아닌 기존 테스트 콘솔
  출력이며, 동작 경고로 오인하지 않도록 별도 추적한다.
- 변경한 Python 경계 파일은 Ruff/LSP/basedpyright 경고 0이다. 전역 basedpyright는
  `864 files, 0 errors, 21,669 warnings`로 오류는 없지만, 사용자 dirty 경로와
  동적 외부 타입 경계에 기존 경고가 남아 있다. 경고를 숨기는 전역 억제는 적용하지
  않았다.
- 라이브 HTTP PIN 검증(로그인 200, bearer `/api/session/info` 200, query PIN 401)은
  이전 실행에서 완료됐다. 현재 열린 `file://` 대시보드는 브라우저 정책상 DOM
  자동 검증이 차단되므로 서버 제공 방식의 수동 UI 확인을 별도 잔여로 남긴다.
- codebase-memory는 재색인 후 `status: ready`, `nodes: 5089`, `edges: 26056`으로
  복구됐다. `detect_changes`는 현재 working tree에서 227개 변경 경로를 확인했으며,
  인덱서가 제외하는 `scripts`, `docs`, `.omo`, generated/node_modules 경로는
  shell·LSP·실행 게이트로 별도 검증했다.

### 잔여 사항 우선순위

1. **P1 타입 경고 부채**: 전역 21,669건을 무차별 억제하지 않고, 런타임 경계와
   변경 위험이 큰 모듈부터 파일 단위로 줄인다. 각 단위는 해당 테스트와
   basedpyright 0을 함께 기록한다.
2. **P1 수동 UI 게이트**: dashboard를 HTTP 서버로 제공한 뒤 로그인·명령 팔레트·
   WebSocket 상태 표시를 브라우저에서 확인한다. `file://`는 자동 DOM 검증
   불가라는 제한을 유지한다.
3. **P2 generated/dirty 산출물 정책**: `dashboard_dist`, `node_modules`, 기존
   사용자 변경은 보존하되, clean export/clean build에서 삭제 모듈이 재포함되지
   않는지 릴리스 직전에 재검증한다.
4. **P2 codebase-memory 재색인**: Transport가 안정화되면 repository index,
   변경 영향, 삭제 모듈 호출 경로를 재실행한다. Transport가 다시 닫히면 현재
   shell/LSP/회귀 테스트 증거를 사용하고 재현 조건을 기록한다.

## 2026-08-30 현재 잔여 작업 요약

이번 점검은 변경 주체와 무관하게 현재 working tree의 tracked, untracked,
deleted, generated 경로를 모두 범위로 삼는다. 아래 상태는 이전 기록의
스냅샷 숫자보다 우선하며, 새로 생성된 산출물이나 삭제 후보도 최종 게이트에서
다시 확인한다.

### 완료된 P0 보안·경로 수정

- PIN 평문 저장·쿠키·WebSocket query 경로를 제거하고, 로그인 이후에는
  sessionStorage bearer token과 WebSocket subprotocol을 사용하도록 전환했다.
- 기존 PIN hash와 JWT secret을 읽을 때도 파일 모드를 `0600`으로 보정하도록
  수정했고, 신규 파일 생성 모드와 회귀 테스트를 확인했다.
- 상대 경로를 포함한 workspace 경로가 프로세스 CWD가 아니라 허용된 project
  root 기준으로 해석되도록 중앙 경로 보안을 수정했다. traversal·symlink·파일
  API 회귀를 통과했다.

### 실제로 남아 있는 작업

릴리스 기준선(v1/v2), 삭제 모듈 호환성 판단, abstract/no-op 분류, 그리고
`api_forwarder.py`의 FastAPI deprecation 경고 제거는 이번 연속 작업에서 모두
완료됐다. 남은 것은 최종 게이트 산출물을 최신 working tree 기준으로 재확인하고,
브라우저의 `file://` DOM 제한과 dirty 산출물 범위를 최종 보고서에 명시하는 일이다.

### 이번 연속 작업에서 닫힌 항목

- held-out v1/v2의 릴리스 필수 파일, freeze digest, 행 수, 순서가 있는 case ID,
  `forbidden_for_training` 플래그를 `release_baseline` 검증에 연결했다. 데이터
  본문 변조와 freeze case ID 변조 회귀가 모두 차단된다.
- 삭제된 `agent_api.py`와 multi-agent 모듈은 현행 source/test/script/entrypoint
  참조가 없어 복원하지 않기로 결정했다. 역사 문서에는 삭제 커밋과 현재
  canonical router를 명시했다.
- `MockSandboxInterceptor`의 httpx fixture 문자열에 남아 있던 실행 불가능한
  `pass`를 async client/response mock으로 교체하고 회귀를 추가했다. abstract
  메서드, 예외 타입, 의도적 예외 복구 경로의 `pass`와 임베딩 엔진의 lazy
  initialization은 동작 계약상 의도된 no-op으로 분류해 유지한다.
- 전체 Python 테스트는 `4818 passed, 6 skipped`로 완료됐다. 기존 12건의
  FastAPI `on_event` deprecation warning은 `scripts/api_forwarder.py`의
  lifespan 컨텍스트로 전환해 제거했고, 관련 보안 테스트(`2 passed`)와
  lifespan 순서 드라이버(`lifespan-order: ok`)를 확인했다. 변경 파일의 Ruff,
  Ruff-format, LSP, basedpyright는 모두 경고 0이다.

### 보류 또는 범위에서 제외한 항목

- dirty working tree의 파일을 임의로 되돌리거나 stage/commit하지 않는다.
- generated `dashboard_dist`, `node_modules`, 기존 사용자 문서·테스트 변경은
  감사 대상이지만 소유권 확인 없이 정리하지 않는다.
- 경고 수를 줄이기 위한 광범위한 억제 지시문 추가와 dead-code 일괄 삭제는
  호환성 증거가 확보될 때까지 보류한다.

## 2026-08-30 continuation: P0 repair and residual backlog

- `/api/health/deep` runtime NameError를 수정했다. `SystemHealth` 타입 캐스트를 런타임 평가하지 않도록 바꾸고, `ModelManager` 실제 계약인 `loaded_names()`를 사용하도록 health probe를 정렬했다. 회귀 2개와 실제 HTTP `GET /api/health/deep`가 200을 반환하며, 더 이상 `list_models`/`SystemHealth` 예외를 노출하지 않는다.
- `AutoLintTool`은 사용자 입력 경로를 셸 문자열에 보간하지 않고 argv 배열과 `shell=False`로 실행한다. 셸 메타문자 경로 회귀를 추가했고 관련 테스트가 통과했다.
- `scripts/api_forwarder.py`는 loopback이 아닌 host로 시작할 때 강한 인증 자격 증명을 요구한다. loopback bootstrap과 비-loopback 거부 회귀가 통과했다.
- chat agent stream은 threadpool 경계를 넘을 때 동일 `Context`에서 generator를 재개하며, 누락된 `expected_tools` 속성은 빈 계약으로 안전하게 처리한다. state-graph 오류와 `different Context` 회귀가 통과했다.
- 현재 검증: 관련 Python 회귀 52개 통과, 변경 Python 경로 Ruff 통과, 대시보드 typecheck·ESLint·Vitest `42 files / 588 tests`·production build 통과. 전체 basedpyright `864 files, 0 errors, 21,668 warnings`로 오류는 없지만 대규모 기존 경고가 남아 있다.
- 브라우저에 열린 `file://.../dashboard/index.html`은 브라우저 URL 정책상 자동 DOM 검증이 차단되었다. 서버 제공 방식의 API는 `/health`와 `/v1/health`가 200/`status: ok`를 반환한다. 연결 표시의 최종 확인은 `uv run uvicorn ...`으로 대시보드를 제공한 뒤 브라우저에서 수행해야 한다.

### 다음 우선순위 (이전 스냅샷, 현재 요약으로 대체됨)

1. PIN이 localStorage·cookie·WebSocket query에 평문으로 남는 경로를 세션 쿠키 또는 헤더 기반으로 통합하고, 서버 query PIN 호환 제거 시 마이그레이션을 제공한다.
2. `.env`/`src/.env`/PIN hash 및 설정·활동 로그 파일의 생성 모드를 `0600`으로 고정하고 기존 파일 권한도 시작 시 보정한다.
3. `code_intel_api.py`의 `repo_path`, `agent_activity.py`의 출력 디렉터리처럼 파일 경로를 받는 API를 허용된 workspace root 아래로 제한한다.
4. held-out v2 benchmark mismatch, stale `agent_api` 문서, 삭제된 multi-agent compatibility 모듈, abstract/no-op 후보를 별도 계약·호환성 검토 후 정리한다.
5. 사용자 dirty 경로 전체의 basedpyright 경고를 고위험·고경고 순으로 줄인다. 현재 전체 경고 0 목표는 아직 달성되지 않았고, 생성 산출물 trailing whitespace와 35개 format drift도 남아 있다.

## 현재 기준

- 최신 검증 코드 커밋: `c1fc1bf` (AgentFabric 오케스트레이션 테스트 경계 보강; 이후 사용자 dirty 파일 continuation은 미커밋)
- 전체 `basedpyright`: `0 errors, 23177 warnings, 0 notes` (사용자 변경 테스트 경계와 `src/antigravity_k/finetune/trainer.py`를 추가 정리했으며, 전체 경고는 다른 사용자 변경 파일과 동적 소스 경계에 잔존)
- 전체 pytest 기준선: `4806 passed, 6 skipped` (최신 tool-loop·장학금 회귀 포함)
- 대시보드: typecheck, lint, Vitest `42 files / 588 tests`, production build 통과
- 대시보드 `npm audit --omit=dev`: `0 vulnerabilities` (Monaco major 변경 없이 override 적용)
- 현재 `git status --short`는 285개 경로를 보고한다. 이 수에는 기존 사용자
  변경과 생성된 `src/antigravity_k/dashboard_dist/`, `dashboard/node_modules/`
  산출물이 함께 포함되며, 소유권 확인 없이 stage·revert하지 않았다.
- Git tracked+untracked Python 871개 AST 검사에서 현존 파일 문법 오류 0건을 확인했다. 삭제 상태인 tracked Python 12개는 외부 호환성 검토 대상으로 남아 있다.
- codebase-memory MCP: 이번 continuation에서 `list_projects`가 정상 응답해 프로젝트 인덱스가 확인됐다. 편집된 테스트 파일의 재색인·영향 분석은 변경 안정화 후 `index_status`/`detect_changes`로 이어간다.
- 이전 앱 재시작 직후에는 `Transport closed`가 재현됐지만 현재 세션에서는 복구됐다. 재발 시 외부 MCP 프로세스/세션 복구 전까지 shell·LSP·회귀 테스트 증빙으로 보완한다.
- working tree 패키징 검증에서 오래된 무시된 `build/`가 남아 있으면 `pip wheel .` 결과에 이미 삭제된 모듈 10개가 다시 포함되는 현상을 확인했다. 깨끗한 소스 export를 별도 임시 디렉터리에서 빌드하면 `agk = antigravity_k.cli:app` entry-point가 유지되고 삭제 모듈은 포함되지 않는다. 따라서 현재 dirty 변경을 릴리스 검증할 때는 clean export/clean build base를 강제해야 하며, 기존 `scripts/verify_clean_machine.sh`의 `git archive HEAD` 검증은 미커밋 working-tree 변경을 포함하지 않는다는 제한을 최종 게이트에 명시한다.

## 대시보드 의존성 감사 결과

- `dashboard/npm audit --omit=dev --json`: `0 vulnerabilities`.
- 기존 취약 경로는 `monaco-editor@0.56.0 → dompurify@3.4.8` 중첩 의존성이었다. `dashboard/package.json`에 `monaco-editor.dompurify=3.4.14` override를 적용해 중첩 패키지를 제거했다.
- 임시 lockfile 검증과 실제 `npm audit --omit=dev`에서 모두 `0 vulnerabilities`를 확인했다. `npm ci --dry-run`도 성공했고 Monaco 버전은 `0.56.0`을 유지한다.
- typecheck/lint/Vitest/build도 통과했으며, 의존성 변경은 `707a312` 독립 커밋으로 반영했다. 생성된 `dashboard_dist`와 `node_modules` 변경은 사용자 dirty 산출물로 보존했다.

## 실행 순서와 완료 조건

1. **tests/scripts/skills 경고 부채 축소**
   - 우선순위: `tests/test_tool_loop.py`, `tests/test_data_extractor.py`, `tests/test_integration_d1_d2_d4.py`, `tests/test_secure_key.py`, `scripts/benchmark_viz.py`, `.agent/skills/**`의 고경고 파일
   - 원칙: fixture/결과 타입을 좁히고 동작은 보존한다. 광범위한 경고 억제 지시문은 사용하지 않는다.
   - 완료: 변경 파일 Ruff/mypy/basedpyright 경고 0, 관련 회귀 테스트 통과, 독립 커밋과 ledger 기록
   - tool-loop 완료: `tests/test_tool_loop.py`의 중첩 `MagicMock` 호출·반환값·호출검증 경계를 공용 typed helper로 전환했다. 90개 테스트와 파일 basedpyright 경고 0건을 확인했다.
   - 장학금 후속: `scholarship_filter.py`는 210건이 `dict[str, Any]` 입력 모델과 argparse Namespace 경계에 집중되어 있다. TypedDict 입력/출력 모델을 먼저 확정한 뒤 필터·리포트 경로를 단계적으로 전환한다.
   - 장학금 완료: `scholarship_filter.py`의 JSON 값·마감 컨텍스트·eligibility 결과·argparse 인자를 명시 타입으로 전환했다. 구현 파일 basedpyright 경고 `210 → 0`, 장학금 12개 테스트와 Ruff/format/mypy/pre-commit 통과.

2. **대시보드 의존성·산출물 결정**
   - `707a312`에서 중첩 Monaco DOMPurify 경로를 `3.4.14` override로 고정해 production audit을 0건으로 만들었다.
   - `dashboard_dist` 해시 산출물은 사용자 변경으로 간주하고 삭제·정리·커밋하지 않는다.
   - 완료: audit 결과와 산출물 처리 결정을 문서화하고, 승인된 범위만 별도 커밋

3. **codebase-memory Transport closed 복구 후 영향 재분석**
   - 복구 전에는 shell/LSP/현재 진단 산출물로 보완하며, transport가 열리면 repository re-index 후 변경 영향과 호출 경로를 재검증한다.
   - 완료: index 상태, 재분석 결과, 실패 시 재현 조건을 기록

4. **244개 사용자 변경사항 파일별 검토**
   - `git status --short` 기준으로 src/tests/dashboard/docs/data/scripts/.tmp 및 단일 파일을 분류한다.
   - 미추적 JS/TS 30개는 모두 `dashboard_dist/assets` 생성 산출물로 확인했으며, 대시보드 build/typecheck 검증 범위로 처리한다.
   - 기존 변경은 누가 만들었는지와 무관하게 검토하되, 명시적 소유권 확인 없이는 stage/commit/revert하지 않는다.
   - 완료: 파일별 위험·테스트·커밋 후보 목록과 독립 커밋 정책을 ledger에 기록

5. **최종 게이트**
   - 전체 pytest, dashboard checks, global Ruff, basedpyright, `git diff --check`를 최신 HEAD에서 재실행한다.
   - 잔여 경고/감사/Transport 제한을 숨기지 않고 최종 보고서에 남긴다.

## 최신 최종 게이트

- 최신 HEAD 기준 전체 pytest는 `4806 passed, 6 skipped`로 완료됐고, 기존 Starlette/httpx deprecation warning 1건만 관찰됐다.
- 대시보드 typecheck·lint·Vitest(`42 files / 588 tests`)·production build와 `npm audit --omit=dev`(`0 vulnerabilities`)가 통과했다. Monaco 버전은 `0.56.0`으로 유지했다.
- 전역 Ruff는 통과했고, 사용자 변경 경로를 포함한 `git diff --check`는 dashboard_dist 생성 파일의 기존 trailing whitespace 4건을 제외하고 통과했다.

## 2026-08-30 system API 경계 정리

- working-tree continuation: `src/antigravity_k/api/routes/system_api.py`의 Pydantic request 모델, JSON/YAML 경계, 캐시 데코레이터, WebSocket PTY side effect, 로그·설정·하네스 응답을 명시 타입으로 좁혔다. `system_api.py` basedpyright 경고는 `197 → 0`이 되었고, Ruff, Ruff-format, mypy, pre-commit이 통과했다.
- 연관 회귀 스위트 `tests/test_system_api_memory_suite.py`, `tests/test_system_api_skills.py`, `tests/test_models_system_api.py`, `tests/test_git_api_endpoints.py`는 `110 passed`로 완료됐다. 전체 basedpyright는 `0 errors, 22980 warnings, 0 notes`로 감소했다.
- 같은 pre-commit 실행에서 발견된 `trainer.py` 평가 백엔드 inference 변수의 mypy 다형성 대입 오류도 `Callable[[EvaluationCase, CandidateKind], str]` 계약으로 보강해 해결했다. trainer와 system_api 파일 진단은 모두 `0 errors, 0 warnings`다.
- 사용자 소유 dirty path는 `244`개로 변함없이 보존됐고, 두 Python 파일의 변경은 기존 사용자 변경과 겹쳐 자동 stage/commit하지 않았다.

## 2026-08-30 최신 clean 파일 경계 정리

- working-tree continuation: `tests/test_git_api_endpoints.py`의 Git API HTTP JSON, 임시 저장소 fixture, subprocess, private helper 경계를 명시 타입으로 전환했다. 파일 basedpyright `0 errors, 0 warnings`, Ruff, Ruff-format, mypy, pre-commit이 통과했고 28개 테스트가 통과했다. 사용자 변경 파일과 겹쳐 자동 stage/commit하지 않았으며, 전체 basedpyright는 `0 errors, 23598 warnings, 0 notes`로 추가 `281`건 감소했다.

- working-tree continuation: `tests/test_system_api_skills.py`의 FastAPI 응답 JSON, pytest fixture, SkillLoader/Registry/Publisher 테스트 double 경계를 명시 타입으로 전환했다. 파일 basedpyright `0 errors, 0 warnings`, Ruff, Ruff-format, mypy, pre-commit이 통과했고 20개 테스트가 통과했다. 사용자 변경 파일과 겹쳐 자동 stage/commit하지 않았으며, 전체 basedpyright는 `0 errors, 23879 warnings, 0 notes`로 `295`건 감소했다.

- working-tree continuation: `tests/test_system_api_memory_suite.py`의 FastAPI 응답 JSON, MagicMock 메서드, 시스템/메모리·보안 입력 경계를 명시 타입으로 전환했다. 파일 basedpyright `0 errors, 0 warnings`, Ruff, Ruff-format, mypy, pre-commit이 통과했고 53개 테스트가 통과했다. 사용자 변경 파일과 겹쳐 자동 stage/commit하지 않았으며, 전체 basedpyright는 `0 errors, 23377 warnings, 0 notes`로 `221`건 감소했다.

- working-tree continuation: `src/antigravity_k/finetune/trainer.py`의 데이터셋 JSON, MLX subprocess, 학습 결과, CLI Namespace 경계를 명시 타입으로 전환했다. 파일 basedpyright `0 errors, 0 warnings`, Ruff, Ruff-format, mypy, pre-commit과 CLI `--help` smoke가 통과했고 관련 finetune 회귀 61개가 통과했다. 사용자 변경 파일과 겹쳐 자동 stage/commit하지 않았으며, 전체 basedpyright는 `0 errors, 23177 warnings, 0 notes`로 `200`건 감소했다.

- `9456266`: `tests/test_phase1_e2e.py`의 SkillInstaller/SkillPublisher private 호출, JSON·subprocess·파일 쓰기 경계를 typed callable/cast와 명시적 결과 소비로 정리했다. 36개 테스트, Ruff, Ruff-format, mypy, basedpyright 0 warnings, pre-commit 통과. 파일 경고 `66 → 0`.
- `49fe488`: `tests/test_skill_installer.py`의 private 메서드·mock·JSON·파일/디렉터리 반환 경계를 typed adapter와 명시적 결과 소비로 정리했다. 77개 테스트, Ruff, Ruff-format, mypy, basedpyright 0 warnings, pre-commit 통과. 파일 경고 `148 → 0`.
- `c1fc1bf`: `tests/test_agent_fabric_orchestration.py`의 fake agent, orchestrator protocol, 동적 메서드 교체, registry 접근 경계를 명시했다. 11개 테스트, Ruff, Ruff-format, mypy, basedpyright 0 warnings, pre-commit 통과. 파일 경고 `148 → 0`.
- 세 커밋 후 전체 basedpyright는 `0 errors, 24174 warnings, 0 notes`; 사용자 dirty path 244개는 계속 보존·미스테이지 상태다.

## 다음 우선순위

1. 사용자 dirty 파일 244개 중 아직 남은 경고를 고경고·고위험 순으로 단계적으로 정리한다. `system_api.py`, `trainer.py`, `tests/test_system_api_skills.py`, `tests/test_git_api_endpoints.py`, `tests/test_system_api_memory_suite.py`는 working-tree에서 0 warnings까지 정리했지만 사용자 변경과 겹쳐 자동 stage/revert하지 않았다.
2. `src/antigravity_k/engine/tool_loop.py` 소스의 orchestrator/manager 동적 경계를 Protocol로 분리해 파일 경고를 `369 → 13`으로 축소했다. 남은 경고는 보호 메서드, 생성자 호환용 동적 경계, JSON decoder·이벤트 버스·state-store의 외부 타입 경계이며, 파일이 사용자 변경과 겹쳐 현재 미커밋이다. 다음 단계는 소유권 확인 후 hunk 단위 독립 커밋이다.
2. `src/antigravity_k/engine/model_manager.py`의 암시적 문자열 연결·미사용 반환값 진단 3건을 제거해 파일 경고를 `251 → 248`로 줄였다. 관련 lifecycle/generate/stream 테스트 83개와 Ruff, Ruff-format, mypy, pre-commit이 통과했다.
3. `src/antigravity_k/security/lintai_scanner.py`의 JSON 출력·실행 파일 경계를 명시해 파일 경고를 `5 → 0`으로 줄였다. 관련 3개 테스트와 Ruff, Ruff-format, mypy, pre-commit이 통과했다.
4. `src/antigravity_k/engine/call_hierarchy_graph.py`의 AST visitor override·속성·미사용 결과를 명시해 파일 경고를 `6 → 0`으로 줄였다. 관련 테스트 1개와 Ruff, Ruff-format, mypy, pre-commit이 통과했다.
5. `src/antigravity_k/engine/code_intel/impact_analyzer.py`의 graph·JSON 반환 경계를 명시하고 미사용 입력을 소비하도록 정리해 파일 경고를 `6 → 0`으로 줄였다. 관련 테스트 2개와 Ruff, Ruff-format, mypy, pre-commit이 통과했다.
6. `demo_service/token_bucket.py`의 limiter 상태·lock 속성을 명시해 파일 경고를 `5 → 0`으로 줄였다. gateway 회귀 테스트 4개와 Ruff, Ruff-format, mypy, pre-commit이 통과했다.
7. `scripts/demo_debate_run.py`의 deprecated `os.system`과 기본 자동 커밋 부작용을 제거하고, 명시적 `create_git_checkpoint=True`에서만 subprocess Git checkpoint를 실행하도록 변경했다. 파일 경고 `5 → 0`, 격리 smoke 및 명시적 checkpoint 호출 검증이 통과했다.
8. 대시보드 중첩 DOMPurIFY 취약점은 `707a312` override로 해결했고 production audit은 0건이다. 현재 추가 잔여는 stale `build/` 산출물 방지와 dirty working-tree 릴리스 검증이다.
9. codebase-memory MCP transport 복구 후 repository re-index와 호출 경로 재검증을 수행한다.

## 최근 완료 단위

- `54cbcd7`: `.agent/skills/k-skill/scripts/ktx_booking.py`의 `korail2`/PyCryptodome 동적 의존성, JSON 응답, 열차·예약 생성기, argparse 핸들러 경계를 typed Protocol/JSON boundary helper로 전환했다. 11개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), mypy, pre-commit이 통과했으며 파일 경고가 `97 → 0`, 전체 basedpyright는 `0 errors, 25401 warnings, 0 notes`다.

- 2026-08-30 source 경계 continuation: `tool_loop.py`의 manager/context/quality/capacity/incremental-graph Protocol을 보강하고 `ToolCall.arguments`를 재귀 JSON 값으로 명시했다. 이벤트 발행·JSON checkpoint·expected-tools 경계와 의도적 반환값 소비도 정리했다. `tests/test_tool_loop.py` 90개, 전체 pytest `4806 passed, 6 skipped`, Ruff/Ruff-format/mypy가 통과했으며 `tool_loop.py` 파일 경고는 `369 → 13`, 전체 basedpyright는 `0 errors, 25015 warnings, 0 notes`다. 생성자 입력과 state-store는 다양한 기존 테스트 double 호환을 위해 동적 경계로 유지했다. `tool_loop.py`와 `task_execution_context.py`는 기존 사용자 변경과 겹쳐 미커밋이며, parser 타입 보강은 `2843ddc`에 기록했다.
- 2026-08-30 provider 경계 continuation: `inference_providers.py`의 native tool-call arguments, Ollama stream response/kwargs, NIM stream 반환값을 명시 타입으로 보강하고 스트림 bytes/text 변수 혼동을 제거했다. 관련 provider·local discovery·model stream 테스트 50개와 Ruff/format/mypy/pre-commit이 통과했으며 파일 경고가 `276 → 247`, 전체 basedpyright가 `0 errors, 25015 warnings, 0 notes`로 감소했다. 변경은 clean 파일 독립 커밋 `8b3a26a`에 기록했다.
- 2026-08-30 dashboard dependency continuation: `707a312`에서 `monaco-editor@0.56.0`의 중첩 `dompurify@3.4.8`을 `3.4.14` override로 고정했다. `npm audit --omit=dev`와 `npm ci --dry-run`이 성공하고, typecheck/lint/Vitest 588개/build도 통과했다. 대시보드 production 취약점은 `2 → 0`으로 해소됐으며 생성된 `dashboard_dist`와 `node_modules` 변경은 사용자 dirty 산출물로 stage하지 않았다.
- 2026-08-30 high-risk regression continuation: RAG 증분/하위 디렉터리·provenance·retrieval, long-context, Git API, system API 회귀 145개가 통과했다. `PYTHONPATH=src python -m antigravity_k.cli --help`와 `OrchestratorAgent`/`ModelRouter` import smoke도 성공했다. 마지막 codebase-memory `list_projects` 재시도는 다시 `Transport closed`였고, 외부 호환성 재색인은 복구 전까지 보류한다.

- `9ecfb4e`: `tests/test_max_engine.py`의 보호 메서드 호출·대입과 MAX 실행 핸들러를 typed callable adapter/`setattr` 경계로 전환했다. 43개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), pre-commit이 통과했으며 파일 경고가 `45 → 0`, 전체 basedpyright는 `0 errors, 25498 warnings, 0 notes`다.

- `8211882`: `tests/test_tool_loop.py`의 direct-response, quality-revision, durable approval, context-compression, event-bus 및 공용 mock fixture 경계를 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), pre-commit이 통과했으며 파일 경고가 `119 → 0`, 전체 basedpyright는 `0 errors, 25543 warnings, 0 notes`다.

- `eec4dec`: `.agent/skills/k-skill/korean-scholarship-search/scripts/scholarship_filter.py`의 JSON 경계(`JsonValue`), 마감 컨텍스트/eligibility 결과 TypedDict, argparse `FilterArgs` Protocol을 도입하고 정규식·리포트 메타데이터의 타입 협소화를 완료했다. 장학금 12개 테스트, Ruff, Ruff-format, basedpyright(`0 errors, 0 warnings`), mypy, pre-commit이 통과했으며 구현 파일 경고가 `210 → 0`, 전체 basedpyright는 `0 errors, 25662 warnings, 0 notes`다.

- `0bfba41`: `tests/test_tool_loop.py`의 durable task resume, step-limit outcome, quality-gate failure fixture를 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `133 → 119`, 전체 basedpyright는 `0 errors, 25872 warnings, 0 notes`다.

- `dfbc1e8`: `tests/test_tool_loop.py`의 Qwen scratchpad 단일·다단계 실행, durable task 재개 및 AsyncMock 호출 이력 검증을 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `156 → 133`, 전체 basedpyright는 `0 errors, 25886 warnings, 0 notes`다.

- `c5a947d`: `tests/test_tool_loop.py`의 native tool follow-up 경로에서 durable context, provider capability, schema, executor 및 다회 stream 호출을 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `176 → 156`, 전체 basedpyright는 `0 errors, 25909 warnings, 0 notes`다.

- `247ee90`: `tests/test_tool_loop.py`의 task outcome 기록, 원요청 품질 검증, citation revision fixture와 durable expected-tool 경계를 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `196 → 176`, 전체 basedpyright는 `0 errors, 25929 warnings, 0 notes`다.

- `de084f2`: `tests/test_tool_loop.py`의 guardrail 차단, approval required, step-limit, max-step bound 및 non-positive step fixture를 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `227 → 196`, 전체 basedpyright는 `0 errors, 25949 warnings, 0 notes`다.

- `cf4c4b2`: `tests/test_tool_loop.py`의 tool-call 성공, DAG batching, 재시도·비재시도·context overflow 스트림 fixture를 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `238 → 227`, 전체 basedpyright는 `0 errors, 25980 warnings, 0 notes`다.

- `c815f09`: `tests/test_tool_loop.py`의 run_loop 테스트 전체에서 orchestrator를 typed accessor로 통일하고 stream/capacity mock 경계를 명시했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `396 → 238`, 전체 basedpyright는 `0 errors, 25991 warnings, 0 notes`다.

- `953cff5`: `tests/test_tool_loop.py`의 비동기 tool 실행 테스트에서 guardrail·executor·cognitive verification·event bus 중첩 mock 접근을 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `425 → 396`, 전체 basedpyright는 `0 errors, 26149 warnings, 0 notes`다.

- `3b8cca1`: `tests/test_tool_loop.py` quality-gate 테스트의 mock 반환값·재시도 설정·호출 인자 검증을 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `535 → 475`, 전체 basedpyright는 `0 errors, 26228 warnings, 0 notes`다.

- `27dc217`: `tests/test_tool_loop.py` post-loop citation recovery 테스트의 직접 mock 접근과 동적 분석 결과를 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `553 → 535`, 전체 basedpyright는 `0 errors, 26288 warnings, 0 notes`다.

- `edd3b53`: `tests/test_tool_loop.py` 공용 fixture의 중첩 mock 초기화와 반환값 설정을 typed path helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `573 → 553`, 전체 basedpyright는 `0 errors, 26306 warnings, 0 notes`다.

- `8e571aa`: `tests/test_tool_loop.py` native-tools 구간의 중첩 `MagicMock` 설정과 호출검증을 공용 typed helper로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `611 → 573`, 전체 basedpyright는 `0 errors, 26326 warnings, 0 notes`다.

- `f9ea9b8`: `.agent/skills/k-skill/scripts/test_korean_slang_writing.py`의 동적 속어 검색·조회·HTTP 모듈과 JSON 결과 경계를 `TypedDict`/callable adapter로 정리했다. 51개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `198 → 0`, 전체 basedpyright는 `0 errors, 26364 warnings, 0 notes`다.

- `902210f`: `.agent/skills/k-skill/scripts/test_patent_search.py`의 동적 특허 검색 모듈, 데이터 클래스 생성자, XML fetcher, CLI 인자 경계를 `Protocol`/callable adapter로 정리했다. 16개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `69 → 0`, 전체 basedpyright는 `0 errors, 26562 warnings, 0 notes`다.

- `384fbb6`: `tests/test_skill_market_client.py`의 subprocess mock 반환값과 private `_state_file`, `_run_npm_search`, `_parse_view_result` 접근을 typed adapter로 정리하고 JSON fixture·파일 쓰기 결과를 명시했다. 62개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `98 → 0`, 전체 basedpyright는 `0 errors, 27048 warnings, 0 notes`로 감소했다.

- `15a5b83`: `test_scholarship_filter.py`의 동적 로더 반환과 scholarship/university helper 호출을 `ModuleType`, `TypedDict`, `Mapping`, callable adapter로 좁혔다. 12개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `34 → 0`, 전체 basedpyright는 `0 errors, 27146 warnings, 0 notes`로 감소했다.

- `8b363dc`: `tests/test_secure_key.py`의 private secure-key helper·상수 접근을 모듈 수준 typed adapter와 동적 경로 조회로 전환했다. 45개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `44 → 0`, 전체 basedpyright는 `0 errors, 27180 warnings, 0 notes`로 감소했다.

- `7aa3ad0`: `tests/test_tool_loop.py`의 `_post_loop_checks`, `_quality_revision`, `_run_tool_task_async`, `_maybe_compress_context`, `_refresh_checkpoint_context`, `_expected_tools` 보호 접근과 citation 상태 검증을 명시적 typed adapter로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `649 → 611`, 전체 basedpyright는 `0 errors, 27224 warnings, 0 notes`로 감소했다.

- `22cfbe3`: `tests/test_tool_loop.py`의 `_format_tool_response` 및 `_native_tools_kwargs` 보호 helper 호출 16건을 명시적 typed adapter로 전환했다. 90개 테스트, Ruff, Ruff-format, basedpyright(오류 없음), pre-commit이 통과했고 파일 경고가 `665 → 649`, 전체 basedpyright는 `0 errors, 27262 warnings, 0 notes`로 감소했다.

- `0f16dff`: `tests/test_data_extractor.py`의 보호된 TOP 1 JSON helper 호출을 `TypedDict`와 callable adapter로 좁혔다. 100개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `12 → 0`, 전체 basedpyright는 `0 errors, 27278 warnings, 0 notes`로 감소했다.

- `6a52008`: `tests/test_tdd_verifier.py`의 보호된 pytest parser helper 호출을 명시적 callable adapter로 감쌌다. 2개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27290 warnings, 0 notes`로 감소했다.

- `0dcf186`: `tests/test_structural_snapshot.py`의 임시 소스·README 파일 쓰기 반환값을 의도적으로 소비하도록 명시했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27292 warnings, 0 notes`로 감소했다.

- `ac59d04`: `tests/test_speculative_branching.py`의 git subprocess와 임시 파일 쓰기 반환값을 의도적으로 소비하도록 명시했다. 9개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27294 warnings, 0 notes`로 감소했다.

- `c55606f`: `tests/test_session_state.py`에서 스트림 라우트의 reset helper를 명시적 callable adapter로 호출하고 결과를 소비하도록 정리했다. 3개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27296 warnings, 0 notes`로 감소했다.

- `d1fd5ab`: `tests/test_preference_memory.py`의 private 선호도 추출 helper를 명시적 callable adapter로 감쌌다. 8개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27298 warnings, 0 notes`로 감소했다.

- `4f3d225`: `tests/test_os_drivers.py`의 Windows fallback 테스트 vararg mock 인자에 `object` 계약을 추가했다. 23개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27300 warnings, 0 notes`로 감소했다.

- `ab613d4`: `tests/test_mcp_capability.py`의 테스트용 MCP client cast를 중첩 없이 명시적으로 정리했다. 5개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27302 warnings, 0 notes`로 감소했다.

- `5b9fe3f`: `tests/test_self_healing_doctor.py`의 임시 fixture 파일 쓰기 반환값을 의도적으로 소비하도록 명시했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27304 warnings, 0 notes`로 감소했다.

- `907a47a`: `tests/test_flight_controller.py`의 성공 고정 executor 매개변수에 `_` 접두사를 사용해 미사용 매개변수 경고를 제거했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27305 warnings, 0 notes`로 감소했다.

- `8832f03`: `tests/test_code_intel_impact_analyzer.py`의 빈 graph fixture를 `dict[str, object]`로 명시했다. 2개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27307 warnings, 0 notes`로 감소했다.

- `a0f713c`: `tests/test_call_hierarchy_graph.py`의 임시 모듈 파일 생성 반환값을 의도적으로 소비하도록 명시했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27309 warnings, 0 notes`로 감소했다.

- `900d555`: `tests/test_browser_session_state.py`의 private 브라우저 세션 ID helper를 typed adapter로 감싸고 세션 제한 예외 경로 반환값을 명시적으로 소비했다. 3개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27311 warnings, 0 notes`로 감소했다.

- `676408e`: `tests/test_workspace_links.py`의 private helper import를 명시적 callable/`TypedDict` adapter로 좁혔다. 4개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27313 warnings, 0 notes`로 감소했다.

- `69c9764`: `tests/test_symbol_navigator.py`의 심볼 인덱싱용 임시 파일 쓰기 반환값을 의도적으로 소비하도록 명시했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27314 warnings, 0 notes`로 감소했다.

- `6eca1aa`: `tests/test_startup_security.py`의 persisted PIN hash fixture 파일 쓰기 반환값을 의도적으로 소비하도록 명시했다. 8개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27315 warnings, 0 notes`로 감소했다.

- `fe64f85`: `tests/test_search_conflicts.py`의 인접 문자열을 명시적 결합으로 정리했다. 6개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27316 warnings, 0 notes`로 감소했다.

- `5a30e45`: `tests/test_next_action_recommender.py`의 임시 디렉터리·파일 생성 반환값을 의도적으로 소비하도록 명시했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27317 warnings, 0 notes`로 감소했다.

- `6537447`: `tests/test_external_brain_e2e.py`의 검증용 `CognitiveLoop` 생성 반환값을 의도적으로 소비하도록 명시했다. 2개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27318 warnings, 0 notes`로 감소했다.

- `2c40c87`: `tests/test_egress_audit.py`의 임시 소스 파일 생성 반환값을 의도적으로 소비하도록 명시했다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27319 warnings, 0 notes`로 감소했다.

- `735065a`: `tests/test_codebase_memory_file_selection.py`의 동적 `context_enrich_handler` 호출을 명시적 callable 계약으로 좁혔다. 3개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27320 warnings, 0 notes`로 감소했다.

- `00170e5`: `tests/test_cancel_task.py`의 동적 `submit_task` 호출을 명시적 typed adapter로 좁혔다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27321 warnings, 0 notes`로 감소했다.

- `1135f29`: `tests/test_bayesian_prompt_tuner.py`의 빈 후보 예외 경로에서 의도적으로 발생하는 반환값을 명시적으로 소비했다. 2개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `1 → 0`, 전체 basedpyright는 `0 errors, 27322 warnings, 0 notes`로 감소했다.

- `8e9ab14`: `tests/test_fast_path_kernel.py`의 임시 파일 생성 호출 반환값을 의도적으로 소비하도록 명시했다. 2개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27323 warnings, 0 notes`로 감소했다.

- `91c6b61`: `tests/test_web_scraper_boundary.py`의 동적 `execute` 호출을 명시적 typed adapter로 좁혔다. 1개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `2 → 0`, 전체 basedpyright는 `0 errors, 27325 warnings, 0 notes`로 감소했다.
- `50ce062`: `tests/test_token_estimator.py`의 parametrized `payload`를 `str`로 명시했다. 9개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `3 → 0`, 전체 basedpyright는 `0 errors, 27327 warnings, 0 notes`로 감소했다.
- `21bce15`: `tests/test_local_model_benchmark.py`의 private benchmark helper import를 명시적 module adapter로 좁혔다. 5개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `4 → 0`, 전체 basedpyright는 `0 errors, 27330 warnings, 0 notes`로 감소했다.
- `8ff1d7f`: `tests/test_model_policy.py`의 private `_model_policy` 검증을 명시적 typed adapter로 좁혔다. 7개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `4 → 0`, 전체 basedpyright는 `0 errors, 27334 warnings, 0 notes`로 감소했다.
- `6835943`: `tests/test_openai_adapter.py`의 tool-call 응답 content와 빈 choices payload를 명시적으로 좁혔다. 12개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `3 → 0`, 전체 basedpyright는 `0 errors, 27338 warnings, 0 notes`로 감소했다.
- `264db1a`: `tests/test_context_budget.py`의 마지막 미타입 `tmp_path` fixture를 `Path`로 명시했다. 8개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `3 → 0`, 전체 basedpyright는 `0 errors, 27341 warnings, 0 notes`로 감소했다.
- `1ae894b`: `tests/test_web_search_quality.py`의 golden fixture 입력, 네트워크·검색 콜백, private API adapter, AsyncMock 호출 결과를 명시적으로 타입화했다. 46개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `176 → 0`, 전체 basedpyright는 `0 errors, 27344 warnings, 0 notes`로 감소했다.
- `43a5b86`: `tests/test_error_classifier.py`의 HTTP 응답 테스트 double을 `@final`로 명시해 클래스 속성 추론 경고 4건을 제거했다. 51개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 27520 warnings, 0 notes`다.
- `fba94e3`: `tests/test_rag.py`의 Chroma 임시 디렉터리 fixture를 `Iterator[str]`로 명시했다. RAG 3개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 파일 경고가 `3 → 0`으로 감소했다.

- `a41645b`: `tests/test_dialectic_engine.py`의 workflow `steps` 동적 결과를 런타임 목록 검증과 명시적 타입 경계로 좁히고, 예외 검증의 반환값을 소비했다. 28개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 27527 warnings, 0 notes`다.

- `52ad6ea`: `tests/test_mode_manager.py`의 상태 전환 반환값 5건을 의도적으로 소비하도록 명시했다. 27개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 27530 warnings, 0 notes`다.

- `a4b6310`: `tests/test_vault.py`의 VaultEngine fixture, 동시성 writer, subprocess spy, monkeypatch callback과 의도적 반환값을 명시적으로 타입화했다. Vault 12개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 파일 경고가 `116 → 0`으로 감소했다. 전체 basedpyright는 `0 errors, 27535 warnings, 0 notes`다.

- `95377c7`: `test_sillok_search.py`에 동적 `exec` 래퍼를 위한 `.pyi` export 계약과 네트워크 테스트 double 타입을 추가해 런타임 동작은 유지하면서 파일 경고를 `111 → 0`으로 줄였다. 13개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 전체 basedpyright는 `0 errors, 27651 warnings, 0 notes`다.

- `7606ff7`: `tests/test_tool_loop.py`의 durable task 생성 반환값, 오류 분류 콜백, 스트림 side-effect callback, 문자열 조합, context compression 미사용 결과를 명시적으로 타입화·소비했다. tool-loop 90개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 파일 경고가 `697 → 665`로 감소했다. 전체 basedpyright는 `0 errors, 27762 warnings, 0 notes`다.

- `a809476`: KTX 예약 테스트의 FakeTrain/FakeReservation/FakeClient 속성·메서드·콜백 계약을 명시하고 unittest 문자열 오버라이드를 표시했다. `PYTHONPATH=.agent/skills/k-skill` 기준 11개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 파일별 basedpyright 경고가 `152 → 46`으로 감소했다. 전체 basedpyright는 `0 errors, 27794 warnings, 0 notes`다.
- `fad2093`: 특허 검색 테스트의 URL opener 응답 double, fetcher 콜백, 캡처 payload를 명시적으로 타입화하고 동적 lambda를 named callback으로 교체했다. `PYTHONPATH=.agent/skills/k-skill` 기준 16개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 파일별 basedpyright 경고가 `132 → 69`로 감소했다. 전체 basedpyright는 `0 errors, 27900 warnings, 0 notes`다.
- `6b7185f`: 한국어 속어 검색 테스트의 동적 모듈 로더 반환형, fixture 인자, unittest override, 콜백 계약, 테스트 클래스 상수와 부작용 반환값을 명시했다. 51개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 파일별 basedpyright 경고가 `227 → 198`로 감소했다. 전체 basedpyright는 `0 errors, 27963 warnings, 0 notes`다.
- `ea8a973`: 장학금 필터 CLI가 `sys.stdout.write`와 `argparse`의 의도적 부작용 반환값 29건을 `_`에 명시적으로 소비했다. 관련 12개 테스트, Ruff, Ruff-format, py_compile, pre-commit이 통과했고 파일별 basedpyright 경고가 `239 → 210`으로 감소했다. 전체 basedpyright는 `0 errors, 27992 warnings, 0 notes`다.
- `28a65e3`: `tests/test_tool_loop.py`의 의도적인 `list`/문자열 반환값 36건을 `_`에 명시적으로 소비했다. tool-loop 90개 테스트, Ruff, Ruff-format, pre-commit이 통과했고 파일별 basedpyright 경고가 `733 → 697`로 감소했다. 잔여 경고는 동적 MagicMock/Any 경계와 보호 메서드 테스트 접근이며, 전체 basedpyright는 `0 errors, 28021 warnings, 0 notes`다.

- `ef7a2b8`: optional OS-driver protocols, `os_drivers.py` warnings `187 → 0`, 55 tests
- `ed45e8c`: MAX engine/runtime protocol boundaries, `max_engine.py` warnings `128 → 0`, 43 MAX tests
- `65f57ca`: concrete PyCryptodome AES import, KTX script tests `11` passed, warnings `340 → 292`
- `718d3e7` + `0eec540`: benchmark visualization input validation and matplotlib Protocol boundary; valid fixture generated 8 charts, malformed/empty inputs exit 2 with actionable errors, changed-file basedpyright/Ruff/mypy report 0 warnings/errors. Whole-tree basedpyright is now `0 errors, 33458 warnings, 0 notes` and the script contributes 0 warnings.
- `898f55e`: `tests/test_model_manager_lifecycle.py` fixture and dependency parameters are typed, stale unused helper removed, and optional-result assertions are narrowed; 43 tests passed, Ruff/Ruff-format/pre-commit passed, file warnings reduced `315 → 105`, and whole-tree basedpyright is now `0 errors, 33248 warnings, 0 notes`. Dynamic MagicMock/protected-member debt remains explicit for a later boundary pass.
- `0e6ffd3`: `tests/test_tool_loop.py` iterator/fixture and all injected `mock_orch` parameters are typed; the 90-test tool-loop suite passed, Ruff/Ruff-format/pre-commit passed, file warnings reduced `895 → 793`, and whole-tree basedpyright is now `0 errors, 33146 warnings, 0 notes`. Dynamic `MagicMock` member and protected-method warnings remain for a later protocol-boundary pass.
- `04c321d`: `tests/test_data_extractor.py` fixture parameters are typed, an optional TOP-1 extraction result is asserted before use, and an implicit string concatenation is made explicit; 100 tests passed, Ruff/Ruff-format/pre-commit passed, file warnings reduced `503 → 12`, and whole-tree basedpyright is now `0 errors, 32655 warnings, 0 notes`. The remaining 12 warnings are protected helper accesses in focused extraction tests.
- `8f92f65`: secure-key test fixtures and injected parameters use explicit `Path`, `CompletedProcess`, `str`, and `pytest.MonkeyPatch` contracts; 45 security tests passed, Ruff and other pre-commit hooks passed, file warnings reduced `448 → 166`, and whole-tree basedpyright is now `0 errors, 32373 warnings, 0 notes`. Ruff-format was skipped only to preserve a pre-existing user-owned formatting hunk in the same file; dynamic lambda, side-effect fixture, private API, and unused-call-result warnings remain.
- `019953f`: system-memory API client/audit fixtures, manager override payloads, injected test parameters, and local capture maps use explicit contracts; the current 53-test suite passed, Ruff and remaining pre-commit hooks passed, file warnings reduced `391 → 221`, and whole-tree basedpyright is now `0 errors, 32203 warnings, 0 notes`. User-added API coverage remains unstaged; Ruff-format was skipped to avoid rewriting unrelated user-owned formatting in the same file.
- `aa8fb2a`: `tests/test_web_search.py` now uses explicit fixture, callback, HTTP-client factory, and result contracts; `WebSearchTool.execute` validates string query inputs and returns `str`. The web-search suite passed 76 tests, Ruff/Ruff-format/mypy and pre-commit hooks passed, file basedpyright warnings reduced `359 → 16`, and whole-tree basedpyright is now `0 errors, 31827 warnings, 0 notes`. The remaining 16 file warnings are intentional private-method test accesses.
- `9e7e90a`: `tests/test_api_server.py` fixture and endpoint parameters now use explicit `TestClient`, `MagicMock`, `ProtocolTranslator`, `pytest.MonkeyPatch`, and recursive JSON-value contracts. The API server suite passed 36 tests with 2 environment skips and one pre-existing Starlette/httpx deprecation warning; Ruff, Ruff-format, mypy, and pre-commit hooks passed; file basedpyright warnings reduced `313 → 73`; whole-tree basedpyright is now `0 errors, 31587 warnings, 0 notes`. Remaining diagnostics are dynamic MagicMock/response JSON and intentional private registry accesses.
- `bee68ac`: `tests/test_usage_tracker.py` tracker fixtures and dependent test parameters use explicit `UsageTracker` and `Path` contracts. The usage-tracker suite passed 20 tests; Ruff, Ruff-format, and pre-commit hooks passed; file basedpyright warnings reduced `129 → 33`; whole-tree basedpyright is now `0 errors, 31490 warnings, 0 notes`. Remaining diagnostics are intentional side-effect fixture calls, protected record assertions, and partially typed pytest helpers.
- `6380828`: unconsumed `UsageTracker.record` results in `tests/test_usage_tracker.py` are explicitly assigned to `_`, preserving side-effect intent. The usage-tracker suite passed 20 tests, Ruff and all pre-commit hooks passed, file basedpyright warnings reduced `33 → 8`, and whole-tree basedpyright is now `0 errors, 31466 warnings, 0 notes`. Remaining diagnostics are five protected `_records` assertions, two partially typed pytest members, and one unused call result.
- `f579d9e`: `tests/test_integration_d1_d2_d4.py` fixtures, injected parameters, listener callbacks, and intentional side-effect calls use explicit contracts; the D1/D2/D4 integration suite passed 48 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `472 → 0`, and whole-tree basedpyright is now `0 errors, 30994 warnings, 0 notes`.
- `2a8777c`: `tests/test_system_control.py` fixture and all injected tool/path parameters use explicit contracts; unused file-write results are marked intentionally consumed. The system-control suite passed 65 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `292 → 70`, and whole-tree basedpyright is now `0 errors, 30772 warnings, 0 notes`; the remaining 70 are protected private-action coverage and dynamic JSON/Mock boundaries.
- `c96be30`: `tests/test_tool_executor.py` fixtures, helper parameters, injected executor/registry/path contracts, and intentional side-effect calls are explicit. The tool-executor suite passed 25 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `254 → 105`, and whole-tree basedpyright is now `0 errors, 30623 warnings, 0 notes`; residuals are dynamic MagicMock registry maps and protected executor-state coverage.
- `0e393b2`: `tests/test_mcp_session_manager.py` uses explicit manager/mock fixture and patched dependency contracts, direct `asyncio.run`, and intentionally ignored connection results. The MCP session suite passed 22 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `251 → 17`, and whole-tree basedpyright is now `0 errors, 30389 warnings, 0 notes`; residuals are external MCP mock methods and awaited-call assertions.
- `f081db0`: `tests/test_model_manager_stream.py` types registry/manager/stream fixtures and injected parameters, narrows optional thinking budget and request bytes before use, and preserves config fixture side effects. The model-stream suite passed 25 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `248 → 102`, and whole-tree basedpyright is now `0 errors, 30243 warnings, 0 notes`; residuals are protected private stream coverage and dynamic provider mocks.
- `7b22715`: `tests/test_benchmark_harness.py` annotates benchmark/model-manager/path fixtures and injected parameters, and uses a model-manager spec for the shared mock. The benchmark harness suite passed 37 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `248 → 95` (the unstaged user-added provider-error test remains preserved), and whole-tree basedpyright is now `0 errors, 30090 warnings, 0 notes`; residuals are protected private harness access and dynamic mock members.
- `3c60be7`: `tests/test_model_manager_generate.py` annotates registry/manager/patch fixtures and injected parameters, types fallback side-effect callbacks, and narrows mocked call assertions through explicit `MagicMock` boundaries. The generation/fallback suite passed 15 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `238 → 57`, and whole-tree basedpyright is now `0 errors, 29909 warnings, 0 notes`; residuals are protected ModelManager internals and dynamic provider/runtime mocks.
- `ef04259`: `tests/test_week2_e2e.py` annotates all temporary-path fixtures, marks file/registry side-effect results as intentionally consumed, and makes multi-line fixture content explicit. The Week2 marketplace E2E suite passed 55 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `235 → 35`, and whole-tree basedpyright is now `0 errors, 29709 warnings, 0 notes`; residuals are protected private API coverage and three dynamic JSON values.
- `ebd926f`: `tests/test_task_runner_outcome.py` adds explicit `Path`, `Iterator`, `TaskOutcome`, vault state, orchestrator stream, and callback contracts while preserving task-runner behavior; intentional JSON content is narrowed before string assertions. The focused task-runner outcome suite passed 11 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `196 → 41`, and whole-tree basedpyright is now `0 errors, 29554 warnings, 0 notes`; residuals are protected runner internals, dynamic orchestrator members, and intentional side-effect calls.
- `4bac890`: `tests/test_claw_integration.py` uses concrete `PermissionGate`, `ContextShaper`, `SessionManager`, and `SlashCommandRegistry` fixtures, marks unittest lifecycle overrides, imports `Permission` from its owning contract module, and narrows metadata containers without changing integration behavior. The Claw integration suite passed 33 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `279 → 5`, and whole-tree basedpyright is now `0 errors, 29280 warnings, 0 notes`; residuals are protected context-shaper helpers and dynamic session metadata list elements.
- `9b13aca`: `tests/test_semantic_dom.py` types parser and snapshot fixtures plus all injected parser/snapshot parameters, narrows parsed bounding boxes before coordinate assertions, and gives generated element maps an explicit contract. The Semantic DOM suite passed 67 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `206 → 21`, and whole-tree basedpyright is now `0 errors, 29095 warnings, 0 notes`; residuals are intentional private parser-method coverage.
- `13d6929`: `tests/test_rsi_family.py` types all temporary-path and RSI sandbox fixtures, injected pytest monkeypatch parameters, and sandbox callbacks while preserving mutation/audit behavior. The RSI family suite passed 28 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `191 → 65`, and whole-tree basedpyright is now `0 errors, 28969 warnings, 0 notes`; residuals are explicit MagicMock/Any boundaries, private RSI internals, and dynamic callback payloads.
- `e6841ec`: `tests/test_protocol_translator.py` types the shared `ProtocolTranslator` fixture and every injected translator parameter while preserving OpenAI/Anthropic/internal conversion coverage. The protocol translator suite passed 43 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `171 → 32`, and whole-tree basedpyright is now `0 errors, 28830 warnings, 0 notes`; residuals are private conversion-method coverage and dynamic request payload values.
- `7b86bd3`: `tests/test_tool_loop.py` adds explicit `Path` temporary-directory contracts and `_run` execution argument/result contracts. The tool-loop suite passed 90 tests, Ruff/Ruff-format/pre-commit passed, file basedpyright warnings reduced `793 → 733`, and whole-tree basedpyright is now `0 errors, 28770 warnings, 0 notes`; residuals are dynamic `MagicMock` boundaries and intentional private-method coverage.
- `000cbd5`: `RAGIndexer.sync(subdirs=...)` now limits stale-manifest deletion to the requested subdirectory scope, with a regression test preserving outside-scope chunks. Nineteen RAG/long-context tests plus Ruff/mypy/pre-commit passed; whole-tree basedpyright remains `0 errors, 28770 warnings, 0 notes`. Existing user-owned source formatting drift remains untouched. Detailed file-level classification is recorded in `user-change-review.md`.
- `6680a13`: `tests/test_secure_key.py` applies class-level fixtures, removes unused fixture parameters, consumes intentional side-effect results, and adds typed subprocess callbacks. The focused suite passed 45 tests, Ruff/mypy/pre-commit passed, file basedpyright warnings reduced `166 → 44`, and whole-tree basedpyright is now `0 errors, 28648 warnings, 0 notes`; residuals are private API coverage and preserved pre-existing format drift.
- `6bbb85b`: `scripts/run_local_model_benchmark.py` adds explicit manager, benchmark, grounding-case, search-record, CLI-argument, and JSON boundary contracts, plus a required response-file guard for non-live grounding mode. The focused benchmark suite passed 5 tests, `--help` smoke passed, Ruff/Ruff-format/mypy/pre-commit passed, and file basedpyright warnings reduced `244 → 0`; user-owned dirty paths remain preserved.
- `2526fee`: the same benchmark helpers now accept the repository's `SimpleNamespace` test doubles through internal casts, preserving runtime compatibility while keeping the script at `0` basedpyright warnings. The focused 5-test suite and full basedpyright passed with `0 errors, 28398 warnings, 0 notes` globally; user-owned dirty paths remain preserved.
- `1678834`: `scripts/fix_g004.py` explicitly consumes the file-write and entrypoint return values. The script now reports `0 errors, 0 warnings, 0 notes`; f-string conversion smoke passed, Ruff/Ruff-format/pre-commit passed, and whole-tree basedpyright reports `0 errors, 28397 warnings, 0 notes`.
- `2b9d93e`: `scripts/run_27b_benchmark.py` fixes the Error Distiller benchmark gate to enforce required diagnostic fields and a bounded 256-character result instead of requiring a summary shorter than an unusually short fixture. The real benchmark run now passes `4/4` with exit code 0; script basedpyright/Ruff/Ruff-format/pre-commit pass, and whole-tree basedpyright reports `0 errors, 28396 warnings, 0 notes`.
- `e6b376d`: `scripts/run_frontier_exceeding_benchmark.py` explicitly consumes the incremental graph update result and normalizes the score expression. The real benchmark run passes `3/3` with exit code 0; script basedpyright/Ruff/Ruff-format/pre-commit pass, and whole-tree basedpyright reports `0 errors, 28395 warnings, 0 notes`.
- `ad15968`: `DeepCodeIndexer` now preserves positional parameter defaults in signatures, and the Frontier Transcendence benchmark regression test covers the default value plus docstring output. The focused indexer tests passed 2 tests, the real transcendence benchmark passed `3/3`, changed-file basedpyright/Ruff/Ruff-format/pre-commit pass with 0 warnings, and whole-tree basedpyright reports `0 errors, 28389 warnings, 0 notes`.
- `ab5081f`: `PromptCompiler` now emits recorded `failing_action` values as `Avoid` rules instead of silently dropping them; the evolution-memory benchmark now passes `3/3 (100%)`, and the regression test covers the negative rule. The compiler/script/test files pass basedpyright, Ruff, Ruff-format, py_compile, and pre-commit with 0 warnings; whole-tree basedpyright remains `0 errors, 28389 warnings, 0 notes`.
- `8e6a0ff`: `scripts/run_next_action_benchmark.py` explicitly consumes its temporary fixture `write_text` result. The real benchmark passes `3/3 (100%)`; script basedpyright, Ruff, Ruff-format, py_compile, and pre-commit pass with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28384 warnings, 0 notes`.
- `c625cbf`: `scripts/run_musk_hardcore_benchmark.py` explicitly consumes its telemetry fixture `write_text` result and normalizes score formatting. The real benchmark passes `3/3 (100%)`; script basedpyright, Ruff, Ruff-format, py_compile, and pre-commit pass with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28382 warnings, 0 notes`.
- `16dc85d`: `CodexTransferEngine` renders manifest table rows through explicit formatting instead of implicit string concatenation; its slash-command regression test now types the path fixture and consumes setup side effects. `tests/test_codex_transfer.py` passed 3 tests; changed source/test files pass basedpyright, Ruff, Ruff-format, and pre-commit with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28373 warnings, 0 notes`.
- `f4a0921`: `ContextArtifactStore` explicitly types its retention-policy field. Context-artifact store/tool tests passed 8 tests; the owned source file passes basedpyright and Ruff with 0 warnings, while untracked user-owned context-artifact tests remain unstaged. Whole-tree basedpyright remeasurement is `0 errors, 28372 warnings, 0 notes`.
- `f4868ba`: `SearchCandidate.metadata` uses a recursive JSON-compatible `MetadataValue` alias instead of explicit `Any`. `tests/test_hybrid_reranker.py` passed 1 test; the source/test pair passes basedpyright and Ruff with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28371 warnings, 0 notes`.
- `df66d90`: `IncrementalCodeGraph.project_root` is explicitly typed and its update results are consumed in the regression test. `tests/test_incremental_code_graph.py` passed 1 test; source/test basedpyright and Ruff pass with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28368 warnings, 0 notes`.
- `89aaaea`: `long_context_policy.py` removes the statically unreachable default match arm from the exhaustive `LongContextStrategy` union. The fallback/native/unavailable regression tests passed 3 tests; the owned source passes basedpyright and Ruff with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28367 warnings, 0 notes`.
- `278df38`: `SurgicalPatcher.apply_patch` now honors `start_line_hint` when repeated snippets exist, and a regression test proves the hinted occurrence is selected. `tests/test_surgical_patcher.py` passed 4 tests; source/test basedpyright, Ruff, Ruff-format, and pre-commit pass with 0 warnings; whole-tree basedpyright remeasurement is `0 errors, 28366 warnings, 0 notes`.
- `d62e24c`: `UnslothProvider.forwards_native_tools` is explicitly typed. The inference-provider suite passed 10 tests; the owned source passes basedpyright and Ruff with 0 warnings, while user-modified inference-provider tests remain unstaged. Whole-tree basedpyright remeasurement is `0 errors, 28365 warnings, 0 notes`.

- `758f187`: `tests/test_max_engine.py` now gives mock manager/orchestrator helpers, selector callbacks, worker doubles, and handler error paths explicit contracts; intentional side effects are assigned to `_`. The MAX-engine suite passed 43 tests; Ruff, Ruff-format, and pre-commit passed. File basedpyright warnings decreased from 158 to 45, all remaining diagnostics are protected private-method accesses and the untyped imported handler boundary. Whole-tree basedpyright remeasurement is `0 errors, 28252 warnings, 0 notes`.
- `624ef87`: `.agent/skills/k-skill/scripts/ktx_booking.py` explicitly consumes login/cancel/parser registration return values, removing 21 unused-call-result diagnostics without changing CLI behavior. KTX script tests passed 11; Ruff, Ruff-format, mypy, pre-commit, and py_compile passed. File basedpyright warnings decreased from 292 to 271; remaining diagnostics are optional `korail2`/crypto dynamic import contracts and argparse namespace boundaries. Whole-tree basedpyright remeasurement is `0 errors, 28231 warnings, 0 notes`.
- `a146bfb`: KTX dependency and missing-secret error messages no longer rely on implicit string concatenation. The KTX script suite passed 11 tests; Ruff, Ruff-format, mypy, py_compile, and pre-commit passed. File basedpyright warnings decreased from 271 to 269; whole-tree basedpyright remeasurement is `0 errors, 28229 warnings, 0 notes`.
- `9f771d8`: KTX search/reserve/cancel and train/reservation normalization now use explicit Protocol contracts, with a guarded reservation result and typed command payloads. The KTX script suite passed 11 tests; Ruff, Ruff-format, mypy, py_compile, and pre-commit passed. File basedpyright warnings decreased from 269 to 97; remaining diagnostics are optional `korail2`/crypto import surfaces and untyped third-party members. Whole-tree basedpyright remeasurement is `0 errors, 28057 warnings, 0 notes`.

- `63e4a2d`: `tests/test_ci_tools.py`의 보호 메서드 호출, 파싱 결과, linter 목록, PR subprocess mock을 명시적 callable/TypedDict/Mock 경계로 정리하고 파일 쓰기 반환값을 소비했다. 45개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `93 → 0`, 전체 basedpyright는 `0 errors, 26955 warnings, 0 notes`다.
- `153b5f2`: `tests/test_config_editor_tool.py`의 pytest fixture, ConfigEditorTool 실행 결과, YAML 결과 구조를 명시적 타입과 경계 adapter로 정리하고 미사용 fixture 의존성을 제거했다. 15개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `93 → 0`, 전체 basedpyright는 `0 errors, 26862 warnings, 0 notes`다.
- `efa8f4e`: `tests/test_tiptap_patterns.py`의 mock tool 메타데이터, override 메서드, ToolRegistry 설치 API, i18n 번역 함수를 명시적 타입 경계로 정리했다. 32개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `92 → 0`, 전체 basedpyright는 `0 errors, 26770 warnings, 0 notes`다.
- `7e4241c`: `tests/test_task_state_store.py`의 task-state 예외 import, pathlib fixture, SQLite migration side effects, state graph/runner private boundary를 명시적 타입으로 정리했다. 13개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `93 → 0`, 전체 basedpyright는 `0 errors, 26677 warnings, 0 notes`다.
- `785d09a`: `.agent/skills/k-skill/scripts/test_ktx_booking.py`의 동적 KTX 모듈, parser Namespace, command 함수 경계를 `ModuleType`/`TypedDict`/`Protocol` adapter로 정리했다. 11개 테스트, Ruff, Ruff-format, basedpyright, pre-commit이 통과했으며 파일 경고가 `46 → 0`, 전체 basedpyright는 `0 errors, 26631 warnings, 0 notes`다.

## 사용자 변경 244개 1차 분류 (현재 작업트리)

- 경로 집계: `src` 148, `tests` 60, `dashboard` 19, `scripts` 3, `.tmp` 2, 기타 12.
- 상태 집계: 수정 144, 삭제 42, 서브모듈 변경 2, 미추적 56.
- 미추적 코드: Python 21개, JS/TS 30개. 나머지는 데이터·문서·생성물이다.
- 가장 큰 변경량: `data/benchmark_results.json`(+3513), `dashboard/node_modules/.package-lock.json`(+2627/-317), `tests/test_tool_sandbox_coverage.py`(+277), `src/antigravity_k/engine/rag_indexer.py`(+251), `src/antigravity_k/api/routes/system_api.py`(+214).
- 삭제된 핵심 소스/테스트: `agents/commands.py`, `agents/coordinator.py`, `agents/team_manager.py`, `engine/{json_logger,logging_util,memory_hygiene}.py`, `integrations/{discord_bot,slack_bot}.py`, `knowledge/artifact_service.py`, `scripts/ingest_obsidian.py`, `tests/{test_commands,test_multi_agent}.py`. 현재 `src/tests/scripts/.agent`에서 이 모듈을 직접 import하는 참조는 확인되지 않았지만, 패키지 외부 사용 가능성은 별도 import/배포 검증이 필요하다.
- `dashboard_dist`는 기존 해시 산출물 삭제와 새 해시 산출물 추가가 함께 발생했다. 빌드 결과 churn으로 분류하고, 소스 대시보드 검증과 별도로 승인 전까지 stage하지 않는다.
- `src` 148개는 API·엔진·에이전트·도구로 분리해 각 diff와 회귀 테스트를 매칭해야 한다. 현재까지 사용자 변경을 포함한 전체 dirty tree를 임의로 stage/revert하지 않았다.

## Model manager audit continuation (2026-08-30)

- `src/antigravity_k/engine/model_manager.py`의 설정·라우팅·JSON 경계를 명시적 타입 헬퍼와 mock 호환 조건으로 정리해 파일 basedpyright 경고를 `248 → 212`로 줄였다.
- 모델 수명주기·생성·스트리밍 회귀 테스트 `83 passed`; Ruff, Ruff-format, mypy, pre-commit 및 파일 basedpyright `0 errors/0 warnings`를 통과했다.
- 전체 basedpyright는 `0 errors, 22944 warnings, 0 notes`; 다음 우선순위는 `inference_providers.py`(235 warnings)이며, 사용자 dirty path 244개는 계속 미스테이지로 보존한다.
- 커밋 훅의 전체 mypy 단계에서는 변경하지 않은 `src/antigravity_k/engine/tool_loop.py:590`의 기존 대입 타입 오류가 관찰됐다. `model_manager.py` 파일 단위 mypy와 pre-commit은 통과했으며, 이 잔여 오류는 다음 우선순위에서 별도 처리한다.

## Inference provider audit continuation (2026-08-30)

- `src/antigravity_k/engine/provider_adapters/inference_providers.py`의 provider registry 설정 조회에서 반환 계약상 불필요한 `isinstance` 분기를 제거했다. 파일 basedpyright 경고는 `235 → 234`로 감소했다.
- inference-provider 회귀 테스트 `10 passed`; Ruff, Ruff-format, mypy, pre-commit 및 파일 basedpyright `0 errors/0 warnings`를 통과했다. 광범위한 `Any` 제거는 실제 SDK/스트리밍 payload 계약을 깨뜨릴 수 있어 다음 단위에서 경계별 cast/protocol로 분리한다.
- 전체 basedpyright 재측정은 다음 전체 게이트에서 갱신하며, 사용자 dirty path 244개는 계속 미스테이지로 보존한다.

## Orchestrator agent audit continuation (2026-08-30)

- `src/antigravity_k/engine/orchestrator/agent.py`는 그래프상 상속 구현이 없는 최종 오케스트레이터라 `@final`을 선언했다. 클래스 속성 관련 basedpyright 경고가 `191 → 168`로 감소했다.
- 오케스트레이터·스트리밍·subagent 회귀 테스트 `22 passed`; Ruff, Ruff-format, 파일 mypy, pre-commit 및 파일 basedpyright `0 errors/0 warnings`를 통과했다.
- 전체 basedpyright는 `0 errors, 22920 warnings, 0 notes`. 기존 사용자 변경(툴 마스킹 phase, long-context shaping 등)은 커밋에서 분리해 dirty path 244개로 복원했으며, `@final`만 `2b005ab`에 기록했다.

## Boundary audit continuation (2026-08-30)

- `2bbbf63`: `inference_providers.py` isolates dynamic SDK imports, JSON response/stream choice maps, tool-call fragments, and message payloads behind explicit casts/protocols. The file is `0 errors, 0 warnings`; `tests/test_inference_providers.py` passed 10; Ruff, Ruff-format, mypy, and pre-commit passed. Repository-wide hook still reports the pre-existing `tool_loop.py:590` mypy error.
- `3afe66b`: `system_tools.py` adds typed tool schemas/kwargs, final class metadata, override contracts, directory helper annotations, and a typed dynamic orchestrator factory. The file is `0 errors, 0 warnings`; file/tool execution/sandbox regressions passed 73; Ruff, Ruff-format, mypy, and pre-commit passed. Existing user changes in the NaturalLanguageBash block remain unstaged.
- Working-tree continuation: `file_tools.py` now has typed schema/kwargs boundaries, file-info TypedDicts, fuzzy-match collection annotations, and consumed write results. It is `0 errors, 0 warnings`; `tests/test_file_tools.py` plus tool executor regressions passed 60; Ruff and mypy passed. The file already contained user-owned `@final`/`@override` edits and remains unstaged.
- Working-tree continuation: `scripts/api_forwarder.py` request JSON boundaries now use a `dict[str, object]` adapter and deprecated `Optional` forms were removed; diagnostics are `0 errors, 146 warnings` (down from 176), Ruff/format/py_compile pass. `task_runner.py` state objects are final; diagnostics are `0 errors, 145 warnings` (down from 165), task outcome/resume/state regressions passed 34, Ruff/format/mypy/py_compile pass. Remaining warnings are dynamic Wiki/Kanban/Orchestrator contracts, FastAPI `on_event` deprecations, and legacy `Any`/typing aliases; no behavior-changing lifespan migration was applied.
- All changes were reviewed against the full dirty tree; no user file was reverted or staged. Current user-owned dirty path count is rechecked separately before the next commit.

## Forwarder/task runner boundary completion (2026-08-30)

- `scripts/api_forwarder.py` now uses recursive JSON-safe values, typed Kanban/search/Wiki protocols, explicit optional factories, typed AgentExecutor streaming payloads, and intentional side-effect result consumption. File basedpyright is `0 errors, 0 warnings`; Ruff, Ruff-format, mypy, pre-commit, py_compile, and import/route smoke passed. The file remains unstaged because it overlaps the existing user-owned script diff.
- `src/antigravity_k/engine/task_runner.py` now uses explicit task-context/status/checkpoint contracts, state-type imports from the owning module, orchestrator/model-manager/Vault protocols, thread lifecycle helpers, and typed resume/outcome boundaries. File basedpyright is `0 errors, 0 warnings`; task runner outcome/resume/state/process-restart tests passed (`35`), Ruff, Ruff-format, mypy, pre-commit, and submit/wait smoke passed. The file remains unstaged because it overlaps existing user-owned engine changes.
- The API-forwarder/task-runner warning-cleanup unit is complete. Remaining global warning debt is tracked separately and must be handled in the next high-warning files without staging unrelated user changes.

## 2026-08-30 전체 코드 재정리 기준선

- `git status --short` 기준 dirty path는 `255`개다: modified `155`, deleted `42`, submodule `2`, untracked `56`. 범위는 `src 149`, `tests 65`, `dashboard 19`, `scripts 4`, `docs 4`, `.omo 4`, `.tmp 2`, `data 3`, `vault_data 1` 및 root/config·산출물을 포함한다. 작성자와 무관하게 모두 검토 대상으로 유지하며, 사용자 소유 파일은 stage/commit/revert하지 않는다.
- 전역 `uv run basedpyright --outputjson` 최신 결과는 `863 files, 0 errors, 21636 warnings, 0 notes`다. `cowork_delegate` 호출부까지 오류가 해소됐지만 전역 경고 제로는 아직 미달이다. `model_manager.py`, `task_runner.py`, `api_forwarder.py`는 파일 단위 `0 errors, 0 warnings`를 유지한다.
- 현재 dead-code 감사(`scripts/audit_dead_code.py`)는 405개 모듈 중 375개가 엔트리포인트에서 reachable, 30개가 unreachable 후보(`B 20`, `B+ 10`, 약 5,004 LOC)다. 후보 삭제는 외부 import/플러그인 호환성 확인 전 보류한다.
- codebase-memory MCP 최신 `index_status`는 `ready`(`nodes 36010`, `edges 142860`)로 복구되어 정적 영향 분석을 재개할 수 있다. 과거 `Transport closed`는 일시적 전송 장애였고 현재 상태에서는 재현되지 않았다.
- 추가로 남은 고위험 정리: held-out v2 평가 데이터의 릴리스 포함 여부(`data/benchmarks/held_out_v2*`, `release_baseline.py`, `docs/RELEASE_POLICY.md`, `pyproject.toml`), 삭제된 `agent_api.py`에 대한 stale 문서 참조, 삭제된 multi-agent 모듈의 외부 import 호환성, 의도적 abstract/no-op `pass` 분류다.
- 다음 순서: (1) 전역 21,636 경고를 고경고 파일별로 단계 축소, (2) v2/삭제 모듈/문서 참조 호환성 결정, (3) 대시보드 생성 산출물·node_modules dirty 범위의 릴리스 정책 확정, (4) 전체 pytest 최신 실행 결과와 브라우저/API 수동 QA 증거를 최종 게이트에 기록한다.

### 독립 검토 레인 결과

- Gate review는 FAIL로 판정했다. 근거는 전역 경고 21,636건, `src/ tests/ scripts/` 전체 Ruff-format 35개 미정렬 파일, generated `dashboard_dist` trailing whitespace 4건이다. 전체 pytest는 최신 실행에서 `4806 passed, 6 skipped`로 완료됐지만, dirty snapshot과의 정확한 동일성은 별도 확인이 필요하다.
- Code-quality review는 WATCH/APPROVE(critical/high 없음)로, `src/antigravity_k/engine/rag_indexer.py`의 112개 focused warning과 `tests/test_rag_retrieval_quality.py`의 구현 미러링 테스트를 중위험 잔여로 지적했다.
- Context review는 held-out v2 release 자산 여부, stale `agent_api.py` 문서, 삭제된 multi-agent 외부 import 호환성, abstract/no-op `pass` 분류를 추가 잔여로 확인했다.
- QA/security 레인은 결과 대기 중이며, 최종 게이트는 모든 레인 결과를 받은 후 PASS/FAIL/INCONCLUSIVE로 확정한다.

### 수동 QA·보안 레인 확정 결과

- 수동 QA는 FAIL이다. `/api/health/deep`가 `SystemHealth` 미정의로 500을 반환하고, 채팅이 `[State Graph Error]` 및 ContextVar 오류를 표시하며, 대시보드 연결 상태가 `연결 확인 중...`에 고정된다. Voice API는 `AGK_STT_COMMAND_JSON` 미설정으로 503이다. 상세 증거: `.omo/evidence/runtime-qa-audit/review-qa-manual-qa.md`.
- 보안 리뷰는 FAIL이다. HIGH: `ci_tools.py` auto_lint의 `shell=True` 명령 주입, `api_forwarder.py` 비루프백 무인증 공개 바인딩. MEDIUM: PIN의 localStorage/URL 노출, 0644 `.env` 자격증명, code-intel repo_path 경계 우회, deny-rule 임의 디렉터리 쓰기. 생성 dashboard 산출물의 원자적 패키징도 INCONCLUSIVE다.
- 이에 따라 현재 상태는 릴리스 준비 완료가 아니며, 최우선 잔여 순서는 보안 HIGH 2건 → deep health/chat/연결 표시 런타임 회귀 → 경고·포맷 부채 → release/deletion 문서 정합성이다.

### 2026-08-30 잔여 작업 재정리 및 명령 경계 완료

- 작성자와 무관하게 현재 working tree의 `git status --short` 289개 경로를 계속 감사 범위로 유지한다. 기존 사용자 변경과 사용자가 언급한 234건, 생성된 `dashboard/node_modules`·`dashboard_dist`, 삭제 상태 tracked 파일을 모두 포함하며 자동 stage·revert하지 않았다.
- `src/antigravity_k/tools/terminal_tools.py`는 persistent subprocess/PTY의 `Popen`·stdin/stdout/stderr·JSON schema·kwargs 경계를 명시 타입으로 정리하고, protected seatbelt 프로파일 접근을 public `SandboxRunner.build_seatbelt_profile()` 경유로 전환했다. 파일 basedpyright/LSP 경고는 `123 → 0`이며 Ruff도 통과했다.
- `src/antigravity_k/engine/sandbox.py`의 public seatbelt profile 래퍼와 `tests/test_terminal_sandbox_routing.py`의 `Popen.args` 타입 가드를 검증했다. 터미널 라우팅·샌드박스 회귀 `21 passed`, persistent/PTY 실제 실행 스모크 `terminal-smoke: ok`를 확인했다.
- 최신 전역 basedpyright는 `864 files, 0 errors, 21,395 warnings, 0 notes`다. 오류 제로는 유지하며, 다음 P1은 `src/antigravity_k/engine/orchestrator/agent.py`(168), `tests/test_ambient_watchdog.py`(161), `tests/test_agent_runtime.py`(157), `tests/test_vision_dom_hybrid.py`(147) 순으로 경계와 회귀를 함께 축소한다. 전역 억제 지시문은 적용하지 않는다.
- `git diff --check`는 통과했다. 대시보드 HTTP 수동 DOM 게이트, clean export/release 산출물 정책, 삭제 모듈 외부 import 호환성은 별도 잔여로 유지한다.
- codebase-memory는 재색인 후 `status: ready`, `nodes: 186`, `edges: 705`로 응답했다. 인덱서가 scripts/docs/.omo/generated/node_modules 등 148개 디렉터리를 제외하므로 전체 289개 dirty path의 영향 판정은 shell·LSP·실행 게이트와 병행한다. `detect_changes`는 현재 working tree 908개 변경 경로를 반환해 기준 브랜치 비교값으로만 보관한다.

## 오케스트레이터 경계 재정리 (2026-08-30)

- `src/antigravity_k/engine/orchestrator/agent.py`의 모델 매니저 입력을 최소 Protocol과 런타임 생성 계약으로 분리해 실제 `ModelManager`와 테스트 fake를 함께 수용하도록 했다. 요약·진화 검증 콜백과 MAX 엔진 초기화는 생성 메서드가 확인된 경우에만 실행된다.
- `src/antigravity_k/engine/max_engine.py`의 `ModelManagerProtocol`에서 `getattr`로만 소비되는 내부 속성 요구를 제거해 실제 모델 매니저와의 구조적 타입 불일치를 해소했다.
- 오케스트레이터 파일 경고는 `168 → 97`, 변경 파일 LSP/basedpyright 오류는 `0`을 유지했다. MAX/오케스트레이터/subagent/planning 회귀 `58 passed, 1 skipped`, Ruff 통과를 확인했다.
- 전역 basedpyright 최신 결과는 `864 files, 0 errors, 21,326 warnings, 0 notes`다. 다음 고경고 단위는 ambient watchdog 테스트(161), agent runtime 테스트(157), vision/dom hybrid 테스트(147)다.
- 작업 기록 갱신 후 현재 dirty path snapshot은 `290`개(`modified 187`, `deleted 43`, `submodule 2`, `untracked 58`)로 재확인했다. 이 수치는 증거 문서·생성물 변동을 포함한 현재 시점 값이며, 234건 사용자 변경을 포함한 전체 감사 범위는 그대로다.

## 보안 HIGH 1차 완료 (2026-08-30)

- `src/antigravity_k/tools/ci_tools.py`의 `TestRunnerTool`을 `shell=True` 문자열 실행에서 `shlex.split` 기반 argv 실행(`shell=False`)으로 전환했다. `file_filter`는 단일 인자로 전달되어 셸 구문이 실행되지 않는다.
- `scripts/api_forwarder.py`의 비루프백 바인딩은 강한 PIN을 시작 시 검증하고, HTTP 및 Kanban WebSocket 요청 모두 `X-Access-Pin` 검증을 통과해야 처리되도록 보호했다. PIN 해시는 지정 파일에 0600으로 저장한다.
- 보안 회귀·정적 게이트 포함 `66 passed`, Ruff/LSP 통과, 두 파일 정적 보안 게이트 `passed=True`를 확인했다.
- 남은 보안 중간 위험은 PIN 노출 경로, `.env` 권한, code-intel 경계, deny-rule 쓰기 정책이며 다음 런타임 QA 단계와 함께 처리한다.

## 런타임 QA 및 readiness 보정 (2026-08-30)

- `system_api.py`의 deep health 경로에서 `SystemHealth`를 런타임 import로 보장했다. 시스템·Voice·서버 import 회귀 `59 passed`; TestClient에서 `/api/health/deep` 200과 상태·컴포넌트·진단 payload를 확인했다.
- `chat.py`의 agent SSE는 동일 `contextvars.Context`에서 generator를 재개하도록 유지했고, context-boundary 회귀가 통과했다. stale 수동 증거의 `expected_tools`/`different Context` 문구는 최신 경로에서 재현되지 않는다.
- Dashboard `HealthStatusSchema`가 모델 미설정 시의 `backends: []`를 객체와 배열 모두 수용하도록 보정했다. client/uiStore 회귀 `43 passed`, `npm run build` 통과.
- `TaskExecutionContext.state_store`의 `Any`를 순환참조 없는 `TaskStateStore` 타입 경계로 교체했다. 변경 파일 LSP 오류는 0건이다.
- Voice API 503은 `AGK_STT_COMMAND_JSON` 미설정이라는 운영 전제조건 미충족이다. 임의 STT 명령은 추가하지 않고 배포 설정 항목으로 유지한다.
- 최신 전역 basedpyright는 `864 files / 0 errors / 21,354 warnings`다. 오류 제로는 유지하지만 전역 경고 제로는 잔여다.

## 최종 게이트 갱신 (2026-08-30)

- `TaskExecutionContext` 저장소 의존성을 `TaskStateStoreProtocol`로 분리해 순환 import 오류를 제거했다. 관련 변경 파일 LSP 오류 0건, Ruff 및 `git diff --check` 통과.
- 전체 Python 회귀 게이트는 `4821 passed, 6 skipped`로 완료됐다. 오케스트레이터·task state·release baseline 묶음은 `63 passed`로 재확인했다.
- Dashboard client/uiStore 회귀는 `43 passed`, `npm run build`는 876개 모듈 변환 및 production bundle 생성까지 통과했다.
- TestClient 스모크에서 `/v1/health`, `/api/system/status`, `/api/health/deep` 모두 HTTP 200을 확인했다. deep health의 `degraded`는 모델 매니저 미설정 상태를 진단 결과로 반영한다.
- 변경 범위 정적 진단은 오류 0건이나 전역 경고 부채는 남아 있다. 전역 억제 지시문은 적용하지 않았다.
- 브라우저 `file://` DOM 직접 검사는 도구 정책상 차단되어 production build와 API 스모크로 대체했다. Voice 503은 `AGK_STT_COMMAND_JSON` 미설정 운영 전제조건이다.

## Warning debt continuation (2026-08-30)

- `tests/test_ambient_watchdog.py`의 fixture·테스트 인자 타입과 의도적 미사용 결과를 명시해 basedpyright 경고를 `161 → 51`으로 축소했다. 동작 회귀 `20 passed`, Ruff, diff 검사 통과.
- `tool_loop.py`의 `_state_store` 반환 계약을 `TaskStateStoreProtocol`로 정렬하고, 동적 스트림 모델 매니저 호환 검사를 유지했다. 오케스트레이터/task-runner 회귀 `53 passed` 및 Ruff 통과.
- 최신 전역 basedpyright는 `864 files / 0 errors / 21,176 warnings`다. 오류 제로는 유지되며 다음 단위는 `test_agent_runtime.py`의 fixture·동적 mock 경계다.

## Warning debt continuation 2 (2026-08-30)

- `tests/test_agent_runtime.py`의 fixture·경로 인자를 명시해 파일 경고를 `156 → 75`로 줄였다. 관련 회귀 `33 passed`, Ruff 및 diff 검사 통과.
- `tests/test_vision_dom_hybrid.py`의 fixture와 스냅샷 타입을 명시해 파일 경고를 `147 → 24`로 줄였다. 비전/DOM 회귀 `38 passed`, Ruff 및 diff 검사 통과. 남은 경고는 protected private 메서드를 직접 검증하는 테스트 경계다.
- `tests/test_prompt_meta_evolution.py`의 fixture·콜백 타입을 명시해 파일 경고를 `145 → 43`으로 줄였다. 프롬프트/메타 아키텍트 회귀 `17 passed`, Ruff 및 diff 검사 통과. 동적 `MagicMock` 계약 경고는 실제 런타임 mock 표면에 한정된다.
- `tests/test_context_shaper.py`의 fixture, 문자열 결합, JSON canonicalizer 타입을 정리해 파일 경고를 `144 → 12`로 줄였다. 컨텍스트 shaping 회귀 `34 passed`, Ruff 및 diff 검사 통과. 남은 경고는 protected helper 테스트 경계다.
- `tests/test_self_consistency.py`와 `self_consistency.py`의 generator/`**kwargs` 계약을 명시해 파일 경고를 `144 → 36`으로 줄였다. self-consistency 회귀 `33 passed`, Ruff 및 diff 검사 통과.
- `tests/test_orchestrator.py`의 경로·메시지 fixture 타입과 저장 결과 소비를 보강했다. 오케스트레이터 회귀 `9 passed`, Ruff 및 diff 검사 통과; 동적 `MagicMock`과 `run_stream`의 기존 동적 계약 경고는 남겨 두었다.
- 최신 전역 basedpyright는 `864 files / 0 errors / 20,586 warnings`다. 오류 제로는 유지되며 전역 경고 제로는 아직 미달이다. 사용자 변경 234건과 나머지 dirty path는 계속 stage/revert하지 않는다.

## Warning debt continuation 3 (2026-08-30)

- `tests/test_filesystem_endpoints.py`의 pytest fixture·TestClient/Path 인자와 JSON 응답 경계를 명시하고, 캐시 정리의 protected 멤버 접근을 typed `getattr` 경계로 격리했다. 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff와 diff 검사를 통과했다.
- Filesystem CRUD·검색 통합 회귀는 `15 passed`로 완료됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 20,448 warnings / 0 notes`다. 직전 20,586건에서 138건을 축소했으며 다음 고경고 단위는 `tests/test_slash_commands_session.py`(138)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 187 (2026-08-31)

- Kanban typed cleanup completed.

## Warning debt continuation 185 (2026-08-31)

- `src/antigravity_k/engine/skill_publisher.py`의 패키지 JSON·YAML frontmatter 경계를 재귀 `JsonValue` 타입과 명시적 mapping 변환으로 정리하고, 파일 복사·쓰기·subprocess 결과의 의도적 무시를 명시했다. publish/npm/GitHub dry-run 동작은 변경하지 않았다.
- `tests/test_skill_publisher.py`의 private 메서드 호출을 typed `getattr` helper로 감싸고, JSON 중첩 구조·파일 쓰기·pytest fixture 경계를 명시 타입으로 정리했다. Skill Publisher 회귀 `28 passed`, 변경 소스·테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 및 `git diff --check`를 통과했다. 임시 프로젝트에서 `publish_to_npm(..., dry_run=True)`를 실행하는 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,081 warnings / 0 notes`다. 직전 기준선 6,632건 대비 551건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/state_graph.py`(42), `src/antigravity_k/agents/kanban.py`(41), `tests/test_autonomous_capabilities.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 186-temp (2026-08-31)

## Warning debt continuation 187 (2026-08-31)

- Kanban typed cleanup completed; full diagnostics now report 5,991 warnings and 0 errors.

- `src/antigravity_k/engine/state_graph.py`의 StateContext 분석·이력·체크포인트 타입과 실행 orchestrator 경계를 `object`/재귀 JSON 타입으로 명시하고, 상태 이벤트·그래프 빌더의 의도적 반환값 무시를 표시했다. Generator 스트리밍 semantics와 기본 상태 전이는 유지했다.
- State Graph 관련 회귀 `38 passed`, 변경 소스·영향 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·그래프 전이 smoke를 통과했다. 분석 딕셔너리 타입 축소로 영향받은 `tests/test_integration_rag_cov.py`, `tests/test_multi_part_routing.py`의 중첩 JSON 경계도 함께 보강했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,032 warnings / 0 notes`다. 직전 기록 6,081건에서 49건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/agents/kanban.py`(41), `tests/test_autonomous_capabilities.py`(41), `tests/test_external_brain.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 187 (2026-08-31)

- `src/antigravity_k/agents/kanban.py`의 SQLite row·connection 경계를 `sqlite3.Row`, 명시적 `cast`, 메서드 반환 타입 및 `str | None` 시그니처로 정리했다. 생성·할당·pull·상태 전이와 REVIEW→DONE verification gate 동작은 유지했다.

## Warning debt continuation 187 (2026-08-31)

- `src/antigravity_k/agents/kanban.py`의 SQLite row·connection 경계를 `sqlite3.Row`, 명시적 `cast`, 메서드 반환 타입 및 `str | None` 시그니처로 정리하고, DDL/DML cursor·commit 결과의 의도적 무시를 표시했다. 태스크 생성·할당·pull·상태 전이와 REVIEW→DONE verification gate 동작은 유지했다.
- Kanban 회귀 `2 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·임시 DB lifecycle smoke를 통과했다. API server와 함께 실행한 관련 회귀는 `38 passed, 2 skipped`로 완료됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,991 warnings / 0 notes`다. 직전 기록 6,032건에서 41건을 축소했으며, 다음 고경고 단위는 `tests/test_autonomous_capabilities.py`(41), `tests/test_external_brain.py`(41), `tests/test_web_search_candidate_augmentation.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 188 (2026-08-31)

- `tests/test_autonomous_capabilities.py`의 `DummyTool` override·pytest 경로·registry install·Permission import 경계를 명시 타입과 typed helper로 정리했다. critical capability prompt, safe/critical skill auto-match, frontmatter 복구 및 `/capabilities` 명령 검증은 유지했다.
- Autonomous Capabilities 회귀 `6 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,950 warnings / 0 notes`다. 직전 기록 5,991건에서 41건을 축소했으며, 다음 고경고 단위는 `tests/test_external_brain.py`(41), `tests/test_web_search_candidate_augmentation.py`(41), `src/antigravity_k/engine/self_capability.py`(40) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 187 (2026-08-31)

- `src/antigravity_k/agents/kanban.py`의 SQLite row·connection 경계를 `sqlite3.Row`, 명시적 `cast`, 메서드 반환 타입 및 `str | None` 시그니처로 정리하고, DDL/DML cursor·commit 결과의 의도적 무시를 표시했다. 태스크 생성·할당·pull·상태 전이와 REVIEW→DONE verification gate 동작은 유지했다.
- Kanban 회귀 `2 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·임시 DB lifecycle smoke를 통과했다. API server와 함께 실행한 관련 회귀는 `38 passed, 2 skipped`로 완료됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,991 warnings / 0 notes`다. 직전 기록 6,032건에서 41건을 축소했으며, 다음 고경고 단위는 `tests/test_autonomous_capabilities.py`(41), `tests/test_external_brain.py`(41), `tests/test_web_search_candidate_augmentation.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 188 (2026-08-31)

- `tests/test_autonomous_capabilities.py`의 `DummyTool` override·pytest 경로·registry install·Permission import 경계를 명시 타입과 typed helper로 정리했다. critical capability prompt, safe/critical skill auto-match, frontmatter 복구 및 `/capabilities` 명령 검증은 유지했다.
- Autonomous Capabilities 회귀 `6 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,950 warnings / 0 notes`다. 직전 기록 5,991건에서 41건을 축소했으며, 다음 고경고 단위는 `tests/test_external_brain.py`(41), `tests/test_web_search_candidate_augmentation.py`(41), `src/antigravity_k/engine/self_capability.py`(40) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 187 (2026-08-31)

- `src/antigravity_k/agents/kanban.py`의 SQLite row·connection 경계를 `sqlite3.Row`, 명시적 `cast`, 메서드 반환 타입 및 `str | None` 시그니처로 정리하고, DDL/DML cursor·commit 결과의 의도적 무시를 표시했다. 태스크 생성·할당·pull·상태 전이와 REVIEW→DONE verification gate 동작은 유지했다.
- Kanban 회귀 `2 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·임시 DB lifecycle smoke를 통과했다. API server와 함께 실행한 관련 회귀는 `38 passed, 2 skipped`로 완료됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,991 warnings / 0 notes`다. 직전 기록 6,032건에서 41건을 축소했으며, 다음 고경고 단위는 `tests/test_autonomous_capabilities.py`(41), `tests/test_external_brain.py`(41), `tests/test_web_search_candidate_augmentation.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 185 (2026-08-31)

- `src/antigravity_k/engine/skill_publisher.py`의 패키지 JSON·YAML frontmatter 경계를 재귀 `JsonValue` 타입과 명시적 mapping 변환으로 정리하고, 파일 복사·쓰기·subprocess 결과의 의도적 무시를 명시했다. publish/npm/GitHub dry-run 동작은 변경하지 않았다.
- `tests/test_skill_publisher.py`의 private 메서드 호출을 typed `getattr` helper로 감싸고, JSON 중첩 구조·파일 쓰기·pytest fixture 경계를 명시 타입으로 정리했다. Skill Publisher 회귀 `28 passed`, 변경 소스·테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 및 `git diff --check`를 통과했다. 임시 프로젝트에서 `publish_to_npm(..., dry_run=True)`를 실행하는 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,081 warnings / 0 notes`다. 직전 기록 6,632건 대비 551건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/state_graph.py`(42), `src/antigravity_k/agents/kanban.py`(41), `tests/test_autonomous_capabilities.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 184 (2026-08-31)

- `tests/test_quality_gate.py`의 QualityGate fixture와 내부 검사 메서드 호출을 명시적 `QualityGate`, `Callable`, `cast` 경계로 정리했다. Markdown·코드 구문·반복·아티팩트 형식·검색 출력 계약 테스트의 동작은 유지했다.
- Quality Gate 회귀 `7 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·diff 검증 통과.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,165 warnings / 0 notes`다. 직전 6,208건에서 43건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/skill_publisher.py`(42), `src/antigravity_k/engine/state_graph.py`(42), `tests/test_skill_publisher.py`(42) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 183 (2026-08-31)

- `tests/test_provider_capabilities.py`의 provider probe 응답·urllib Request·임시 파일·pytest fixture·ModelManager/ModelRegistry 동적 mock 및 상태 payload 경계를 `Path`, 명시적 `cast`, mock helper로 정리했다. Ollama/LM Studio/Unsloth/MLX/Transformers capability probe, long-context 정책, remediation hint, manager-router 상태 노출 계약은 유지했다.
- Provider capabilities 회귀 `24 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·diff 검증 통과.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,208 warnings / 0 notes`다. 직전 6,251건에서 43건을 축소했으며, 다음 고경고 단위는 `tests/test_quality_gate.py`(43), `src/antigravity_k/engine/skill_publisher.py`(42), `src/antigravity_k/engine/state_graph.py`(42) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 182 (2026-08-31)

- `src/antigravity_k/tools/browser_tools.py`의 Playwright 동적 세션·페이지·locator 경계를 Protocol과 명시적 반환 타입으로 정리하고, BrowserDOMTool 입력 kwargs 및 실행 결과를 안전하게 정규화했다. goto/click/fill/extract/screenshot/close 동작과 브라우저 오류 처리는 유지했다.
- `tests/test_prompt_meta_evolution.py`의 PromptEvolver·MetaArchitect 테스트에서 동적 `MagicMock`, 보호 멤버, JSON/파일 반환 경계를 명시적 `Callable`/`cast` helper로 정리하고 사용하지 않는 파일 쓰기 결과를 표시했다. 모델 manager 검증, 후보 선택·이력 저장, JSON 추출, 아키텍처 제안·컨텍스트 수집 계약은 유지했다.
- 브라우저 도구 회귀 `20 passed`, 프롬프트 진화·메타 아키텍트 회귀 `17 passed`; 두 변경 단위 basedpyright/LSP `0 errors / 0 warnings`, Ruff·diff 검증 통과.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,251 warnings / 0 notes`다. 직전 6,337건에서 86건을 축소했으며, 다음 고경고 단위는 `tests/test_provider_capabilities.py`(43), `tests/test_quality_gate.py`(43), `src/antigravity_k/engine/skill_publisher.py`(42) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 181 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_verification_handlers.py`의 CoV 설정·orchestrator·manager generate callback·CoV trace·quality loop 경계를 Protocol, Callable, cast 및 명시적 반환 타입으로 정리했다. 응답 자기검증, 자동 수정, 인용 근거 평가, 재시도 루프백 및 상태 전이 동작은 유지했다.
- 관련 회귀 `45 passed` (`test_amplification_config.py`, `test_integration_rag_cov.py`, `test_critic_routing.py`, `test_orchestrator_handlers.py`), 변경 엔진 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,337 warnings / 0 notes`다. 직전 측정 6,390건에서 53건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/browser_tools.py`(43), `tests/test_prompt_meta_evolution.py`(43), `tests/test_provider_capabilities.py`(43) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 180 (2026-08-31)

- `src/antigravity_k/tools/self_test_tool.py`의 도구 메타데이터·실행 kwargs·하네스 report·hygiene scan·Markdown 결과 경계를 TypedDict, Mapping, 명시적 타입 및 override로 정리했다. full/api/ui 범위 실행, 이벤트 루프 처리, 위생 검사 및 리포트 포맷은 유지했다.
- `tests/test_self_test_tool.py`의 schema 접근·private formatter 호출·report fixture 타입 경계를 helper와 명시적 cast로 정리했다.
- Self-Test Tool 회귀 `14 passed`, 변경 소스/테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,390 warnings / 0 notes`다. 직전 측정 6,451건에서 61건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/orchestrator_verification_handlers.py`(43), `src/antigravity_k/tools/browser_tools.py`(43), `tests/test_prompt_meta_evolution.py`(43) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 179 (2026-08-31)

- `src/antigravity_k/engine/tdd_engine.py`의 ModelManager 경계, TDD report 직렬화, JSON 결과 파싱, async candidate 집계, 파일 쓰기 결과 및 코드 블록 추출을 Protocol·Awaitable·명시적 타입으로 정리했다. TDD 루프, 로컬/외부 candidate racing, 실패 피드백, quality gate 및 fallback 응답 동작은 유지했다.
- TDD Engine 회귀 `8 passed`, 변경 엔진 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,451 warnings / 0 notes`다. 직전 측정 6,495건에서 44건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/self_test_tool.py`(44), `src/antigravity_k/engine/orchestrator_verification_handlers.py`(43), `src/antigravity_k/tools/browser_tools.py`(43) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 178 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_memory_handler.py`의 memory recorder·quality gate·mode manager·self-evolution 경계를 Protocol과 명시적 cast로 정리했다. 메모리 저장, 토큰 사용량 표시 및 조건부 Hermes Self-Evolution 흐름은 유지했다.
- 관련 orchestrator handler 회귀 `20 passed`, 변경 엔진 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- `src/antigravity_k/engine/subagent_spawner.py`의 동적 OrchestratorAgent 프록시, vault dependency, model/tool registry, spawn request 및 async 결과 수집 경계를 Protocol·Callable·Mapping·명시적 타입으로 정리했다. 병렬/동기 spawn, 계약 거부, 실패 격리 및 실행 루프 경계는 유지했다.
- Subagent Spawner 회귀 `10 passed`, 변경 엔진 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,495 warnings / 0 notes`다. 직전 측정 6,539건에서 44건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/tdd_engine.py`(44), `src/antigravity_k/tools/self_test_tool.py`(44), `src/antigravity_k/engine/orchestrator_verification_handlers.py`(43) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 177 (2026-08-31)

- `tests/test_integration_upgrade.py`의 pytest fixture·임시 경로·BaseAgent 보호 메서드·ToolRegistry 동적 등록·SkillsRegistry 검증 경계를 `Path`, `pytest.MonkeyPatch`, Protocol, `Callable`, `cast` 및 명시적 반환값 처리로 정리했다. AppConfig 환경/YAML 우선순위, 다국어 시스템 프롬프트, 스킬 도구 누락 검증, ComputerUse 메타데이터 및 위험도 필터 동작은 유지했다.
- Integration Upgrade 회귀 `18 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- `src/antigravity_k/engine/orchestrator_memory_handler.py`의 memory recorder·quality gate·mode manager·self-evolution 경계를 Protocol 및 명시적 cast로 정리하고 private/unknown 경고를 제거했다. 관련 orchestrator handler 회귀 `20 passed`, 변경 엔진 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,539 warnings / 0 notes`다. 직전 측정 6,632건에서 93건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/subagent_spawner.py`(44), `src/antigravity_k/engine/tdd_engine.py`(44), `src/antigravity_k/tools/self_test_tool.py`(44) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 173 (2026-08-31)

- `src/antigravity_k/engine/goal_runner.py`의 GoalReport Kanban Protocol, 검증 결과 TypedDict, 클래스/인스턴스 속성 및 파일 쓰기 경계를 명시 타입으로 정리했다. `/goal` 평가·Kanban 렌더링·ruff/pytest/compileall/npm 검증·SelfRepair·SPEC backprop 동작은 유지했다.
- GoalRunner 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했고, 관련 회귀 `37 passed, 2 skipped` 및 run/render Kanban smoke `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,725 warnings / 0 notes`다. 직전 측정 6,823건에서 47건을 축소했으며, 다음 고경고 단위는 `tests/test_gate_pipeline.py`(47), `tests/test_memory_operations.py`(47), `tests/test_confidence_evaluator.py`(46) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 174 (2026-08-31)

- `tests/test_gate_pipeline.py`의 MagicMock 기반 게이트 픽스처를 명시 타입 `_GateMethod`/`_GateDouble`로 교체하고 ExecutionGate 캐스팅 경계를 고정했다. 우선순위 정렬, short-circuit, fail-open, approval/rate-limit 통합 시나리오의 동작은 유지했다.
- Gate Pipeline 회귀 `24 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,725 warnings / 0 notes`다. 직전 측정 6,725건에서 경고 수는 유지되었으나 단일 파일 47건을 제거해 다음 우선순위가 `tests/test_memory_operations.py`(47), `tests/test_confidence_evaluator.py`(46), `tests/test_integration_upgrade.py`(45)로 이동했다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 168 (2026-08-31)

- `tests/test_command_execution_boundary.py`의 Permission import 경계, pytest fixture 타입, sandbox/provider 콜백, ToolRegistry 설치 호출, 실행 permit 전달을 명시적 타입과 테스트 헬퍼로 정리했다. 승인 없는 직접 실행 거부, registry permit 주입, sibling·symlink 탈출 차단, 실패 exit code 표면화, 성공 출력 무오염 동작은 유지했다.
- 명령 실행 경계 회귀 `5 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,966 warnings / 0 notes`다. 직전 측정 7,014건에서 48건을 축소했으며, 다음 고경고 단위는 `tests/test_multiplexer.py`(48), `tests/test_task_benchmark.py`(48), `.agent/skills/k-skill/joseon-sillok-search/scripts/sillok_search.py`(47) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 167 (2026-08-31)

- `src/antigravity_k/engine/skill_generator.py`의 model manager·JSON 스펙·생성 결과·파일 승인 경계를 Protocol, 명시적 JSON map/result 타입, `Mapping`, `cast`로 정리했다. 생성된 코드 AST 검증과 pending→approved 메타데이터 흐름은 유지했고, 승인 대상 tools 디렉터리가 없는 신규 프로젝트에서도 자동 생성되도록 실제 결함을 보완했다.
- 스킬 생성기 회귀 `13 passed`, 변경 소스/관련 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 프로젝트에서 managed model target으로 스킬 생성→AST 검증→draft metadata→approve 이동→approved metadata 상태를 실제 실행하는 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,014 warnings / 0 notes`다. 직전 측정 7,106건에서 92건을 축소했으며, 다음 고경고 단위는 `tests/test_command_execution_boundary.py`(48), `tests/test_multiplexer.py`(48), `tests/test_task_benchmark.py`(48) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 155 (2026-08-31)

- `tests/test_git_api_boundary.py`의 Git 작업 디렉터리·저장소 파일 경계 테스트에 Path/MonkeyPatch/Protocol/TypedDict 유사 완료 결과 타입, `getattr` 기반 private helper 접근, 권한 거부 테스트 double을 명시했다. 프로젝트 루트 밖 cwd/file escape 차단과 commit 권한 거부 전 subprocess 차단 의미는 유지했다.
- Git 경계 회귀 `4 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트 루트에서 외부 cwd 403 차단을 직접 실행하는 수동 boundary smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,648 warnings / 0 notes`다. 직전 측정 7,700건에서 52건을 축소했으며, 다음 단위는 `tests/test_model_manager_generate.py`(52)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 156 (2026-08-31)

- `tests/test_model_manager_generate.py`의 ModelRegistry/ModelManager fixture double, fallback·stream·trace 콜백, private model-manager 훅과 provider shim 접근을 Callable/Protocol/cast 및 명시적 결과 소비로 정리했다. 단일 모델 생성, fallback/집단지성 라우팅, Qwen thinking 제어, MLX/LM Studio 로더 의미는 유지했다.
- 모델 생성·라우팅 회귀 `15 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. fixture 기반 실제 `ModelManager.generate`/`stream_generate`와 tracer/fallback 경로가 테스트 런타임에서 동작하는 것을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,596 warnings / 0 notes`다. 직전 측정 7,648건에서 52건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_subway_lost_property.py`(51), `tests/test_agent_program_creation.py`(51), `tests/test_ambient_watchdog.py`(51) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 157 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_subway_lost_property.py`의 동적 helper import 경계를 SearchQuery/SearchPlan Protocol, Callable/cast와 명시적 JSON/command 타입으로 정리했다. LOST112/서울교통공사 검색 계획, curl 옵션, reachability/timeout probe, CLI JSON 출력 및 실행 가능 엔트리포인트 검증 의미는 유지했다.
- 유실물 helper 회귀 `8 tests OK`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 지원되는 스킬 디렉터리 `PYTHONPATH`에서 CLI 테스트를 실제 실행해 8개 테스트가 모두 통과하는 것을 확인했다. 저장소 루트 직접 실행 시 `scripts` 모듈 경로가 없어지는 동작은 코드 결함이 아닌 실행 경로 제약으로 분리 기록했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,545 warnings / 0 notes`다. 직전 측정 7,596건에서 51건을 축소했으며, 다음 고경고 단위는 `tests/test_agent_program_creation.py`(51), `tests/test_ambient_watchdog.py`(51), `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`(50) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 160 (2026-08-31)

- `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`의 JSON/CLI 경계를 재귀 `JsonValue`, `TypedDict`, `Protocol`, 명시적 `cast`로 정리하고 argparse 반환값·정리 후보·agent usage source의 타입과 미사용 Action 결과를 구체화했다. 스킬 디렉터리 탐색, JSONL/usage JSON 병합, 시간창 필터, 후보 점수화, 파일 미삭제 안전 경계는 유지했다.
- cleaner 정적 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 스킬 루트와 JSONL에서 alpha 사용량·beta never-use 후보를 생성하고 `No files were deleted` 안전 문구를 확인하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,393 warnings / 0 notes`다. 직전 측정 7,443건에서 50건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49), `src/antigravity_k/agents/base_agent.py`(49), `src/antigravity_k/engine/audit_logger.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 158 (2026-08-31)

- `tests/test_agent_program_creation.py`의 프로그램 생성 테스트 double에 Path/Iterator/Callable/cast/final 타입을 적용하고, tracker mock 결과·생성/스트림 콜백·watchdog 종료 경계를 명시했다. 기존 통합 테스트가 skip되는 리팩터링 상태는 유지했으며, 테스트 double의 생성·도구 호출 계약은 별도 smoke로 확인했다.
- 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 대상 pytest는 기존 리팩터링 사유로 `1 skipped`, 프로그램 builder double smoke는 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,494 warnings / 0 notes`다. 직전 측정 7,545건에서 51건을 축소했으며, 다음 고경고 단위는 `tests/test_ambient_watchdog.py`(51), `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`(50), `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 159 (2026-08-31)

- `tests/test_ambient_watchdog.py`의 watchdog private 상태·analyze/heartbeat 호출, subprocess 결과와 MagicMock 메서드 경계를 helper/cast/명시적 결과 소비로 정리했다. 시작/중지·중복 시작·diff 예외·proactive 경고·알림 영속성·heartbeat 성공/실패 의미는 유지했다.
- Ambient Watchdog 회귀 `20 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 watchdog thread start/stop 및 알림/heartbeat 동작이 테스트 런타임에서 통과하는 것을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,443 warnings / 0 notes`다. 직전 측정 7,494건에서 51건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`(50), `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49), `src/antigravity_k/agents/base_agent.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 158 (2026-08-31)

- `tests/test_agent_program_creation.py`의 프로그램 생성 테스트 double에 Path/Iterator/Callable/cast/final 타입을 적용하고, tracker mock 결과·생성/스트림 콜백·watchdog 종료 경계를 명시했다. 기존 통합 테스트가 skip되는 리팩터링 상태는 유지했으며, 테스트 double의 생성·도구 호출 계약은 별도 smoke로 확인했다.
- 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 대상 pytest는 기존 리팩터링 사유로 `1 skipped`, 프로그램 builder double smoke는 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,494 warnings / 0 notes`다. 직전 측정 7,545건에서 51건을 축소했으며, 다음 고경고 단위는 `tests/test_ambient_watchdog.py`(51), `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`(50), `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 148 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_analysis_handlers.py`의 CEO 분석 스트림, 불확실성 추정기, 사용자 모델·메모리 선호도, 역할 라우팅 경계를 Protocol·Mapping·Sequence·안전한 값 변환 helper로 정리했다. CEO 결과의 task/delegate/refined prompt 기본값, `<think>` 스트림 닫기, coding/reasoning 역할 자동 보정, simple-chat 라우팅 생략 의미는 유지했다.
- 오케스트레이터 핸들러 회귀 `22 passed`, 변경 2개 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 런타임에서 CEO 스트림·불확실성 전처리·WORKER 자동 보정·라우팅 메시지를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,954 warnings / 0 notes`다. 직전 측정 8,018건에서 64건을 축소했으며 다음 고경고 단위는 전체 경고 목록 상위 `memory_tools.py`, `config_editor_tool.py`, `artifact_engine.py`, `api/routes/agent_tools.py` 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 147 (2026-08-31)

- `src/antigravity_k/engine/orchestrator/agent.py`의 모델 매니저·설정·도구 스키마·메시지·코드 트리 인덱서·MAX 엔진 경계를 명시 타입과 안전한 mapping/list 변환 helper로 정리했다. 세션 시작/지연 초기화 결과의 명시적 소비, CEO 분석 generator 경계, planning mode 문자열 정규화, context shaper/decision anchor 흐름은 기존 동작을 유지했다.
- 오케스트레이터 회귀 `16 passed, 2 skipped`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 프로젝트에서 `OrchestratorAgent` 초기화, 도구 프롬프트 생성, agent prompt 준비, manager 없는 MAX 폴백을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,018 warnings / 0 notes`다. 직전 측정 8,070건에서 52건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/orchestrator_analysis_handlers.py`(52)와 현재 전체 경고 목록 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 146 (2026-08-31)

- `tests/test_evolution_family_rest.py`의 AgentFabric registry 접근, role/model manager lambda, fake agent callback, DeterministicWorker manager, Path fixture, WorkerResult JSON data를 명시 타입·Protocol 경계·cast로 정리했다. AgentFabric 캐시/실행 오류, 결정론적 판단·레시피 검증, SkillLibrary 영속화의 기존 검증 의미는 유지했다.
- Evolution family 잔여 회귀 `18 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. AgentFabric 캐시, 파일 line-range 읽기, SkillLibrary 저장을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,070 warnings / 0 notes`다. 직전 측정 8,123건에서 53건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/orchestrator/agent.py`(52) 및 전체 경고 목록의 다음 단위다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 145 (2026-08-31)

- `tests/test_cascade_escalation.py`의 MagicMock/Any 기반 registry·generator double을 명시 타입의 `_RegistryDouble`, `_MemoryConfigDouble`, generator 설치 helper와 cast 경계로 교체했다. 저신뢰 cascade escalation, 비활성 cascade, 최고 tier 정지, 최대 escalation 제한, non-cascading combo의 기존 검증 의미는 유지했다.
- Cascade 회귀 `6 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 저신뢰 응답에서 `light-4b → mid-24b`로 실제 escalation되는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,123 warnings / 0 notes`다. 직전 측정 8,176건에서 53건을 축소했으며 다음 고경고 단위는 `tests/test_evolution_family_rest.py`(53), `src/antigravity_k/engine/orchestrator/agent.py`(52), 이후 전체 경고 목록 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 138 (2026-08-31)

- `tests/test_runtime_benchmark_binding.py`의 orchestrator 대역, pytest fixture, MagicMock ModelManager/Router, background task/thread 조회와 calibration callback 인자를 `Protocol`/`Path`/`Callable`/명시 cast로 정리했다. background·direct task outcome 기록과 model-router calibration 동기화 시나리오의 검증 의미는 유지했다.
- Runtime benchmark binding 회귀 `3 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,449 warnings / 0 notes`다. 직전 측정 8,507건에서 58건을 축소했으며 다음 고경고 단위는 `tests/test_benchmark_performance.py`(57), `tests/test_claude_deny_patterns.py`(56), `tests/test_local_rag_quality.py`(54)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 137 (2026-08-31)

- `scripts/run_bon_ab_measurement.py`의 argparse Namespace, 모델 레지스트리 동적 amplification 설정, QualityGate 접근, 반복 측정 누적 행과 JSON payload를 `MeasurementArgs`/`TypedDict`/`Protocol`/명시 cast로 정리했다. baseline delta 계산, BoN 설정, output 경로와 CLI 의미는 유지했다.
- 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 harness로 argument parsing부터 비교 루프·delta 계산·JSON 저장까지 실행한 smoke와 `--help` surface가 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,507 warnings / 0 notes`다. 직전 측정 8,566건에서 59건을 축소했으며 다음 고경고 단위는 `tests/test_runtime_benchmark_binding.py`(58), `tests/test_benchmark_performance.py`(57), `tests/test_claude_deny_patterns.py`(56)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 136 (2026-08-31)

- `src/antigravity_k/engine/error_classifier.py`의 분류 결과·콜백 override·HTTP 응답 body JSON 경계를 `TypedDict`/`Protocol`/`dict[str, object]`/명시 cast로 정리했다. 상태 코드·메시지·transport·context overflow 분류 우선순위와 복구 플래그 의미는 유지했다.
- 전체 진단에서 함께 드러난 `tests/test_agent_archive.py` 통계 반환값 비교와 `tests/test_usage_tracker.py` dashboard/private record·approx 경계를 명시 cast/helper로 정리했다. 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다.
- ErrorClassifier/ToolLoop/AgentArchive/UsageTracker 회귀 `183 passed`, JSON response·text fallback·context overflow/rate-limit 분류 수동 smoke `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,566 warnings / 0 notes`다. 직전 측정 8,618건에서 52건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 129 (2026-08-31)

- `scripts/fix_e501.py`의 Ruff JSON/fallback 결과, 문자열·호출 변환기, 파일 변경 목록, CLI argparse 경계를 명시 타입과 `TypedDict`/`Protocol`/`cast`로 정리했다. 현재 작업 경로 밖 임시 파일을 dry-run 또는 실제 수정할 때 `Path.relative_to()`가 예외를 내던 경로 표시 결함도 안전한 절대 경로 fallback으로 보완했다.
- 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 120자 초과 문자열/호출 변환, dry-run 비변경, 실제 파일 수정 및 외부 임시 경로 출력 수동 smoke가 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,814 warnings / 0 notes`다. 직전 측정 8,873건에서 59건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/agent_archive.py`(18), `src/antigravity_k/engine/rsi_sandbox.py`(11), `src/antigravity_k/engine/usage_tracker.py`(9)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 130 (2026-08-31)

- `src/antigravity_k/engine/agent_archive.py`의 AgentVariant payload 직렬화/역직렬화, 아카이브 상태·세대 카운터, lineage 문자열 조립과 JSON 로드 경계를 명시 타입·TypedDict·Mapping 변환으로 정리했다. 변이체 승인/거부, best/latest 조회, lineage, crossover, stats, 저장·재로드 의미는 유지했다.
- AgentArchive 회귀 `21 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 아카이브에서 변이 저장·세대 증가·계보·재로드·통계를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,779 warnings / 0 notes`다. 직전 측정 8,814건에서 35건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/rsi_sandbox.py`(11), `src/antigravity_k/engine/usage_tracker.py`(9), `src/antigravity_k/engine/skill_auto_learner.py`(8)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 131 (2026-08-31)

- `src/antigravity_k/engine/rsi_sandbox.py`의 MutationRecord/audit 결과 직렬화, 샌드박스 상태 속성, AST·파일 쓰기 side-effect, dual-audit 반환 및 감사 로그 JSON 로드 경계를 명시 타입·TypedDict·런타임 dict/list 검증으로 정리했다. 불변 파일 분류, AST·pytest·benchmark 3중 검증, dual-audit 승인/거부, mutation log 재로드 의미는 유지했다.
- RSI sandbox 회귀 `28 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 AST/pytest/benchmark 검증, dual-audit 승인, mutation 기록 저장·재로드를 실제 실행하는 수동 smoke도 `PASS`다. 초기 smoke의 테스트 파일 누락은 계약 입력을 보완해 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,754 warnings / 0 notes`다. 직전 측정 8,779건에서 25건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/usage_tracker.py`(9), `src/antigravity_k/engine/skill_auto_learner.py`(8), `src/antigravity_k/engine/self_improvement.py`(6)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 132 (2026-08-31)

- `src/antigravity_k/engine/usage_tracker.py`의 UsageRecord/UsageStats 직렬화, tracker 상태 속성, 모델별 통계 정렬, dashboard 반환, JSON usage DB 로드 경계를 명시 타입·TypedDict·런타임 dict/list 검증으로 정리했다. record/max-records/auto-save, 비용 기록, 기간별 통계, hourly trend, 재로드 의미는 유지했다.
- UsageTracker 회귀 `20 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 usage DB에서 성공/실패 기록, 토큰 합계, dashboard data, 저장·재로드·total 통계를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,726 warnings / 0 notes`다. 직전 측정 8,754건에서 28건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/skill_auto_learner.py`(8), `src/antigravity_k/engine/self_improvement.py`(6), `tests/test_wiki_export_tool.py`(6)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 133 (2026-08-31)

- `src/antigravity_k/engine/skill_auto_learner.py`의 도구 인자/패턴 payload, SkillRecord 레지스트리 JSON, managed model manager Protocol, 동적 생성 응답, 파일 쓰기·GC 반환 경계를 명시 타입·TypedDict·런타임 dict 검증으로 정리했다. 반복 패턴 감지, managed target 우선 생성, configured API fallback, 스킬 저장·재로드·사용량 추적 의미는 유지했다.
- SkillAutoLearner 회귀 `17 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 managed skill generation, SKILL.md 저장, 사용량 증가, registry 재로드를 실제 실행하는 수동 smoke도 `PASS`다. 최초 smoke의 summary 문자열 가정은 실제 계약에 맞게 파일·레지스트리 상태 검증으로 교정했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,686 warnings / 0 notes`다. 직전 측정 8,726건에서 40건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/self_improvement.py`(6), `tests/test_wiki_export_tool.py`(6), `src/antigravity_k/engine/error_classifier.py`(5)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 134 (2026-08-31)

- `src/antigravity_k/engine/self_improvement.py`의 reinforcement 상수, 상태 속성, 반복 패턴/insight 컬렉션, Markdown 조립, self-improvement history JSON 로드 경계를 명시 타입·TypedDict·런타임 dict/list 검증으로 정리했다. 턴 기록, 임계값 기반 보강 프롬프트, insight/report 생성, 저장·재로드 의미는 유지했다.
- 별도 회귀 파일은 없지만 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 데이터 디렉터리에서 반복 이슈 기록, reinforcement/insight/report 생성, history 재로드를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,666 warnings / 0 notes`다. 직전 측정 8,686건에서 20건을 축소했으며 다음 고경고 단위는 `tests/test_wiki_export_tool.py`(6), `src/antigravity_k/engine/error_classifier.py`(5), `run_e2e_test.py`(3)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 135 (2026-08-31)

- `tests/test_wiki_export_tool.py`의 wiki 경로 helper, WikiExportTool Protocol, parameters schema mapping, open fallback double, execute 반환 및 파일 I/O side-effect 경계를 명시 타입으로 정리했다. 기본/태그/파일명/날짜/frontmatter/권한 fallback/export 저장 회귀 의미는 유지했다.
- Wiki export 회귀 `18 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 디렉터리에서 frontmatter·tag·본문이 포함된 Markdown export를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,618 warnings / 0 notes`다. 직전 측정 8,666건에서 48건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/error_classifier.py`(5), `run_e2e_test.py`(3), `src/antigravity_k/agents/scout_agent.py`(2)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 128 (2026-08-31)

- `tests/test_rag_incremental.py`의 persistent vector-store double, chunk metadata, manifest 재사용, batch upsert와 stale chunk 삭제 경계를 명시 타입으로 정리했다. 변경 감지·재색인·빈 파일 stale chunk 제거 의미는 유지했다.
- RAG incremental 회귀 `3 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 최초 인덱싱 후 persistent manifest 재사용을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,873 warnings / 0 notes`다. 직전 측정 8,933건에서 60건을 축소했으며 다음 고경고 단위는 `scripts/fix_e501.py`(59), `scripts/run_bon_ab_measurement.py`(59), `tests/test_runtime_benchmark_binding.py`(58)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 127 (2026-08-31)

- `tests/test_autonomous_qa.py`의 screenshot 비교·파일 patch 보호 메서드 호출, `tmp_path`, HTTP `AsyncClient` 응답, Playwright page 동작을 명시 타입 fake와 호출 helper로 교체했다. vision 분석·코드 patch 생성의 HTTP 상태/JSON 폴백, 성능 메트릭, viewport overflow 판정, path escape 보호 의미는 유지했다.
- Autonomous QA 회귀 `44 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. screenshot 비교·파일 patch·performance·viewport를 실제 엔진 경로로 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,933 warnings / 0 notes`다. 직전 측정 8,993건에서 60건을 축소했으며 다음 고경고 단위는 `tests/test_rag_incremental.py`(60), `scripts/fix_e501.py`(59), `scripts/run_bon_ab_measurement.py`(59)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 126 (2026-08-31)

- `tests/test_autonomous_qa.py`의 screenshot/patch 보호 메서드 호출, `tmp_path`, HTTP `AsyncClient` 응답, Playwright page 동작을 명시 타입의 fake 경계와 호출 helper로 교체했다. vision 분석·코드 patch 생성의 HTTP 상태/JSON 폴백, 성능 메트릭, viewport overflow 판정, path escape 보호 의미는 유지했다.
- Autonomous QA 회귀 `44 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. screenshot 비교·파일 patch·performance·viewport를 실제 엔진 경로로 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,933 warnings / 0 notes`다. 직전 측정 8,993건에서 60건을 축소했으며 다음 고경고 단위는 `tests/test_rag_incremental.py`(60), `scripts/fix_e501.py`(59), `scripts/run_bon_ab_measurement.py`(59)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 125 (2026-08-31)

- `tests/test_autonomous_learner.py`의 MagicMock 의존을 호출 기록형 `_FakeManager`, `_FakeResponse`, typed pytest fixture와 protected fallback 호출 helper로 교체했다. managed model target, manager generation 실패 폴백, Ollama JSON 응답 파싱, 키워드 gap 생성 회귀 의미는 유지했다.
- AutonomousLearner 회귀 `11 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 `should_learn` 및 managed-model `analyze_knowledge_gap` 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,993 warnings / 0 notes`다. 직전 측정 9,053건에서 60건을 축소했으며 다음 고경고 단위는 `tests/test_autonomous_qa.py`(60), `tests/test_rag_incremental.py`(60), `scripts/fix_e501.py`(59)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 124 (2026-08-31)

- `.agent/skills/k-skill/korean-slang-writing/scripts/slang_search.py`의 JSON index·검색 결과·CLI argparse 경계를 `TypedDict`, `Protocol`, `object` 런타임 검증과 명시적 cast로 정리했다. deprecated 필터, mood/context/safety/intensity 교차 필터, match reason·era 정렬, JSON/text 출력 의미는 유지했다.
- Slang search 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 번들 seed index 기본 검색 API 및 `--format json`/`--format text` CLI smoke가 모두 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,053 warnings / 0 notes`다. 직전 측정 9,113건에서 60건을 축소했으며 다음 고경고 단위는 `tests/test_autonomous_learner.py`(60), `tests/test_autonomous_qa.py`(60), `tests/test_rag_incremental.py`(60)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 123 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_korean_spell_check.py`의 동적 loader Any 경계를 typed `Callable`/`cast` wrapper, `Payload`/issue Protocol, typed requester, nested payload helper로 정리했다. chunk 분할, 공식 결과 파싱·교정, blank-line/indent 보존, no-issue 후속 chunk, `parse_args` 오류 회귀 의미는 유지했다.
- Korean spell-check 회귀 `14 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. fixture 기반 결과 파싱·교정과 chunk 재결합 수동 smoke도 `PASS`다. 첫 smoke의 잘못된 fixture 기대값은 실제 샘플 계약에 맞춰 수정해 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,113 warnings / 0 notes`다. 직전 측정 9,174건에서 61건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/korean-slang-writing/scripts/slang_search.py`(60), `tests/test_autonomous_learner.py`(60), `tests/test_autonomous_qa.py`(60)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 117 (2026-08-31)

- `src/antigravity_k/engine/meta_architect.py`의 모델 매니저 Protocol 경계, JSON 이력·제안·판정 payload, 파일 목록/변경 내용, 샌드박스 검증 결과를 명시 타입과 Mapping/list 변환 helper로 정리했다. Ollama URL 기본값 지연 평가, managed model target 라우팅, 아키텍처 제안 파싱, self-reward judge 입력, API fallback 의미는 유지하면서 judge가 실제 원본·신규 코드를 평가하도록 입력 누락을 보완했다.
- MetaArchitect 회귀 `17 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 managed generation·proposal parsing·judge 결과를 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,618 warnings / 0 notes`다. 직전 측정 9,670건에서 52건을 축소했으며 다음 고경고 단위는 `tests/test_failure_classifier.py`(66), `tests/test_rsi_family.py`(65), `tests/test_planning_and_rendering_quality.py`(64)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 119 (2026-08-31)

- `tests/test_rsi_family.py`의 RSIEngine/Pseudo-LLM·RSISandbox 회귀 double, benchmark callback, dual-audit callback, snapshot/rollback 상태 접근을 명시 타입·Callable·cast helper로 정리했다. 사이클 수용·롤백·스킵, 변이 검증, 이중 감사, 안전 컨텍스트·감사 로그 영속화 의미는 유지했다.
- RSIEngine/RSISandbox 회귀 `28 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 샌드박스에서 AST 실패 단락, dual audit 단일 실행, safe mutation snapshot을 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,487 warnings / 0 notes`다. 직전 측정 9,552건에서 65건을 축소했으며 다음 고경고 단위는 `tests/test_planning_and_rendering_quality.py`(64), `tests/test_approval_api.py`(63), `scripts/fix_d205.py`(62)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 119 (2026-08-31)

- `tests/test_rsi_family.py`의 RSIEngine/Pseudo-LLM·RSISandbox 회귀 double, benchmark callback, dual-audit callback, snapshot/rollback 상태 접근을 명시 타입·Callable·cast helper로 정리했다. 사이클 수용·롤백·스킵, 변이 검증, 이중 감사, 안전 컨텍스트·감사 로그 영속화 의미는 유지했다.
- RSIEngine/RSISandbox 회귀 `28 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 샌드박스에서 AST 실패 단락, dual audit 단일 실행, safe mutation snapshot을 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,487 warnings / 0 notes`다. 직전 측정 9,552건에서 65건을 축소했으며 다음 고경고 단위는 `tests/test_planning_and_rendering_quality.py`(64), `tests/test_approval_api.py`(63), `scripts/fix_d205.py`(62)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 118 (2026-08-31)

- `tests/test_failure_classifier.py`의 분류 케이스·재시도 케이스·ToolExecutor 테스트 더블·Permission import·private 상태 접근 경계를 명시 타입, Path, Callable, cast helper로 정리했다. 실패 분류 우선순위, ToolExecutor 실패 기록/복구 카운터, ImmuneSystem escalation 검증 의미는 유지했다.
- FailureClassifier/RecoveryStrategy/ToolExecutor 회귀 `33 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·diff 검증을 통과했다. timeout 분류와 retryable recovery guidance 실제 호출 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,552 warnings / 0 notes`다. 직전 측정 9,618건에서 66건을 축소했으며 다음 고경고 단위는 `tests/test_rsi_family.py`(65), `tests/test_planning_and_rendering_quality.py`(64), `tests/test_approval_api.py`(63)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 116 (2026-08-31)

- `src/antigravity_k/engine/hook_event_bus.py`의 이벤트 분류/JSON 경계, HookEventEmit·GateRequest DTO, subscriber callback, 파일 tail/req-resp IPC와 singleton 초기화를 명시 타입·mapping narrowing으로 정리했다. 이벤트 분류, watcher offset, gate timeout/cleanup, wildcard dispatch 의미는 유지했다.
- EventBus·PersistentAgency 회귀 `44 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 디렉터리에서 JSONL tail dispatch, panel metadata, gate request/response round-trip 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,670 warnings / 0 notes`다. 직전 측정 9,723건에서 53건을 축소했으며 다음 고경고 소스는 `src/antigravity_k/engine/meta_architect.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 115 (2026-08-31)

- `src/antigravity_k/engine/healing_loop.py`의 accessibility tree/page 경계, semantic DOM parser 지연 로딩, 치유 메모리/통계 TypedDict와 재시도 callback 반환을 명시 타입으로 정리했다. 기본/시맨틱/A11y/bbox 치유 전략, 재시도 횟수, heal log·memory 의미는 유지했다.
- Healing loop 회귀 `30 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실패 후 A11y selector 복구와 V2 memory 기록을 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,723 warnings / 0 notes`다. 직전 측정 9,776건에서 53건을 축소했으며 다음 고경고 소스는 `src/antigravity_k/engine/hook_event_bus.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 111 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/transformers_provider.py`의 모델·토크나이저·생성 결과·캐시 경계를 Protocol과 명시 타입으로 정리했다. 네이티브/양자화 생성, 스트리밍 청크, device 이동과 cache 의미는 유지했다.
- Local runtime/inference provider 회귀 `18 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증과 fake model/tokenizer 수동 스모크를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,940 warnings / 0 notes`다. 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 112 (2026-08-31)

- `src/antigravity_k/engine/lora_pipeline.py`의 JSONL harvest/preference pair, subprocess stdout, metadata/config 통계를 명시 타입과 변환 helper로 정리했다. LoRA/DPO export·reload·stats와 `timeout_sec` API 의미는 유지했다.
- LoRA/DPO 회귀 `17 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증과 임시 harvest/pair/export/reload 수동 스모크를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,885 warnings / 0 notes`다. 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 113 (2026-08-31)

- `src/antigravity_k/engine/rule_engine.py`의 rule condition, nested condition, YAML/JSON persistence, callback/pipeline routing 경계를 명시 타입과 mapping helper로 정리했다. first-match/fallback/operator/singleton 의미는 유지했다.
- Critic/multi-part/decision-anchor 회귀 `39 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증과 nested evaluation/save-reload 수동 스모크를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,830 warnings / 0 notes`다. 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 114 (2026-08-31)

- `src/antigravity_k/api/server.py`의 lifespan 초기화/종료 task 집합, rate-limit handler, middleware `call_next`, OpenAPI monkey-patch, static fallback 경계를 명시 타입과 `override`로 정리했다. 백그라운드 task 취소·IDE 종료·요청 correlation ID·정적 fallback 의미는 유지했다.
- API server/AgentRuntime 회귀 `69 passed, 2 skipped`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·`git diff --check`를 통과했다. 앱 import, OpenAPI security schema와 `/health` route 수동 스모크도 `PASS`다. OpenAPI 스모크에서 기존 duplicate operation-id와 선택적 `email-validator` 알림이 관찰됐으나 이번 변경 범위 밖이라 수정하지 않았다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,776 warnings / 0 notes`다. 직전 측정 9,830건에서 54건을 축소했으며 다음 고경고 소스는 `src/antigravity_k/engine/healing_loop.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 112 (2026-08-31)

- `src/antigravity_k/engine/lora_pipeline.py`의 수확/DPO 데이터 JSON 역직렬화, 메타데이터·설정 반환, 파일 쓰기·subprocess 로그 경계를 명시 타입/변환 helper/`@final`로 정리했다. 수확 임계값·중복 방지, preference pair 추출, JSONL export, mlx/Unsloth config 생성과 학습 로그 의미는 유지했다.
- LoRA/DPO 회귀 `17 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 디렉터리에서 수확·DPO pair·dataset/config export·재로드·통계 persistence를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,885 warnings / 0 notes`다. 직전 측정 9,940건에서 55건을 축소했으며 다음 고경고 소스 모듈은 `src/antigravity_k/engine/rule_engine.py`(55건)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 113 (2026-08-31)

- `src/antigravity_k/engine/rule_engine.py`의 RuleCondition 상태 필드 탐색·비교, Rule 직렬화/역직렬화, YAML/JSON 규칙 로딩·저장, 결정 로그·명시적 파이프라인 라우팅 경계를 Mapping/RuleValue/Protocol 호환 cast와 명시 타입으로 정리했다. 우선순위 first-match, 기본 fallback, 비교 연산자 의미, singleton/라우팅 로그 동작은 유지했다.
- 라우팅·멀티파트·결정 앵커 회귀 `39 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 규칙으로 nested analysis 평가, 결정 로그, JSON 저장/재로드, 복원 평가를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,830 warnings / 0 notes`다. 직전 측정 9,885건에서 55건을 축소했으며 다음 고경고 소스 모듈은 `src/antigravity_k/api/server.py`(54건)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 111 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/transformers_provider.py`의 Transformers 토크나이저·모델·텐서·생성 결과 경계를 Protocol/Mapping/Sized/cast와 `override`로 정리했다. max token/temperature 변환, 모델 device 이동, native attention·quantized KV cache 조건, prompt 이후 토큰 디코드, chunk streaming 의미는 유지했다.
- Local runtime·inference provider 회귀 `18 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 가짜 tokenizer/model로 device 입력 이동, 신규 토큰만 디코드, native/quantized cache 옵션, 3자 스트리밍 chunk를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,940 warnings / 0 notes`다. 직전 측정 9,996건에서 56건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 103 (2026-08-31)

- `src/antigravity_k/engine/shields.py`의 ToolsetManager 연동, Shields 상태 JSON 복원, config.yaml 경계, 상태·감사 반환값을 Protocol/Mapping/명시적 타입 가드/final로 정리했다. Shields down/up, 타임아웃 자동 복원, toolset 전환·복원, 감사 로그와 영속화 의미는 유지했다.
- Shields 및 API 보안 경로 회귀 `87 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 상태 디렉터리에서 config 기반 down/up, toolset 전환·복원, 상태 파일·감사 로그를 확인하는 수동 lifecycle smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,053 warnings / 0 notes`다. 직전 측정 10,111 warnings에서 58건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다. 전체 진단 중 `src/antigravity_k/engine/healing_loop.py`의 기존 부분 unknown 경고 1건은 남아 있다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 109 (2026-08-31)

- `src/antigravity_k/knowledge/memory_service.py`의 SQLite connection/cursor/Row 조회, 선택적 VectorStore, 검색 결과·RRF score, snapshot JSON, export/redact/retention 통계를 Protocol/TypedDict/object 변환 경계로 정리했다. WAL 초기화, keyword/vector/hybrid 검색, 임베딩 재생성, 스냅샷·보존·redact·clear 의미는 유지했다.
- 메모리 서비스·내구성 purge 회귀 `42 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 SQLite에서 knowledge 검색, snapshot 저장/복원, export, 통계, 전체 삭제를 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,111 warnings / 0 notes`다. 직전 측정 10,170건에서 59건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 108 (2026-08-31)

- `src/antigravity_k/engine/protocol_translator.py`의 OpenAI·Anthropic·내부 요청/응답 변환 경계를 Mapping/TypedDict와 명시적 문자열·수치·목록 정규화 helper로 정리했다. 멀티모달 content 보존, system/message 변환, 토큰 usage 합산, 포맷 감지와 왕복 변환 의미는 유지했다. 이 반환 타입 조정으로 발생한 `chat.py` JsonMap cast 경계도 object를 거쳐 안전하게 정렬했다.
- 프로토콜·API·AgentRuntime 회귀 `112 passed, 2 skipped`, 프로토콜 전용 `43 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 멀티모달 OpenAI 요청→내부→Anthropic 요청, 내부 응답→OpenAI 응답, 포맷 감지를 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,170 warnings / 0 notes`다. 직전 측정 10,230건에서 60건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 107 (2026-08-31)

- `src/antigravity_k/engine/persistent_agency_store.py`의 SQLite cursor/row 조회, append-only event payload, objective claim/requeue/complete, task idempotency와 pause control 경계를 Protocol/Generator/cast와 명시 타입으로 정리했다. 테이블 초기화·트랜잭션·상태 전이·JSON payload 의미는 유지했다.
- persistent agency·agency API·trajectory compressor 회귀 `32 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 SQLite에서 event append/list, objective claim/complete, task binding·중복 결과 차단, pause 상태를 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,230 warnings / 0 notes`다. 직전 측정 10,287건에서 57건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 106 (2026-08-31)

- `src/antigravity_k/engine/delegation_engine.py`의 위임 오케스트레이터·병렬 결과·pipeline 단계·subagent 도구 경계를 Protocol/TypedDict/object 변환으로 정리했다. 단일·병렬·pipeline·debate·subagent 전략 선택, 알 수 없는 전략의 single fallback, 기존 오케스트레이터 output 기록과 실패 fallback 의미는 유지했다.
- 위임 엔진·경로 회귀 `22 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 전략 추천, unknown strategy fallback, pipeline 단계 스트리밍을 실제 오케스트레이터 double로 확인하는 수동 스모크도 `PASS`다. 전체 진단 중 테스트/실제 오케스트레이터의 구조적 타입 차이 12건을 발견해 생성자 경계에서 object 수용·내부 Protocol cast로 호환성을 복원한 뒤 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,287 warnings / 0 notes`다. 직전 측정 10,344건에서 57건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 105 (2026-08-31)

- `src/antigravity_k/engine/context_shaper.py`의 메시지·상태 통계·토큰 사용량 DTO, tool 결과 압축 버퍼, JSON 참조 복원, ContextShaper 설정과 역할 우선순위를 명시 타입·TypedDict로 정리했다. 5단계 shaping 파이프라인, 예산 계산, 오래된 tool 결과 정리, collapse 참조 파일 저장·복원 의미는 유지했다.
- 컨텍스트 셰이퍼·tool loop·claw 통합 회귀 `158 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 저장소에서 강제 shaping, 긴 tool 결과 collapse/ref 복원, 이전 결과 compact 동작을 실제 실행하는 수동 스모크도 `PASS`다. 반환 타입 조정 중 기존 토큰 사용량 비교 회귀 1건을 발견해 `_TokenUsage` TypedDict로 호환성을 복원한 뒤 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,344 warnings / 0 notes`다. 직전 측정 10,401건에서 57건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 104 (2026-08-31)

- `src/antigravity_k/engine/panel_activity_tracker.py`의 패널/도구 상태 DTO, 이벤트 payload 경계, activity 조회 반환, 콜백 계약과 HookEventBus 연동을 Protocol/TypedDict/object 변환 helper와 명시 타입으로 정리했다. thinking/idle 전환, 동일 상태의 since 유지, pretool 요약, stop 시 current tool 정리, 글로벌 tracker 초기화 의미는 유지했다.
- 전용 회귀 테스트가 없는 모듈이므로 상태 변경·중복 상태 억제·도구 요약·stop 정리·thinking 목록·콜백 알림을 실제 이벤트 객체로 검증하는 수동 스모크를 통과했다. 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증도 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,401 warnings / 0 notes`다. 직전 측정 10,459건에서 58건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 103 (2026-08-31)

- `src/antigravity_k/engine/model_router.py`의 ModelCombo 동적 설정, 비가용 추적기, 라우팅 설정·콤보 로딩, confidence 파싱, provider capability와 상태 반환 경계를 명시 타입·TypedDict·Protocol 호환 helper로 정리했다. fallback·round-robin·load-balance·cascading 전략, 실패 쿨다운, 품질 calibration, API가 기대하는 상태 조회 구조는 유지했다.
- 모델 라우터·calibration·critic/cascade/confidence 회귀 `63 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 레지스트리로 fallback 전환, 실패 모델 격리, available 목록, confidence 점수 파싱, evaluator 선택을 실제 실행하는 수동 스모크도 `PASS`다. 상태 반환을 TypedDict 호환 dict subclass로 조정해 기존 테스트의 dict cast와 중첩 quality_calibration 인덱싱을 동시에 보존했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,459 warnings / 0 notes`다. 직전 측정 10,519건에서 60건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 96 (2026-08-31)

- `src/antigravity_k/engine/slash_commands_skills.py`의 capability decision·tool registry·skill loader 계약과 slash handler 인자를 Protocol/ClassVar/cast로 정리했다. `slash_commands_session.py`에는 세션/스킬 믹스인이 공유하는 공개 프로토콜 별칭을 추가해 다중상속 변수 계약을 일치시켰고, `/self`, `/capabilities`, `/codex`, `/evolve`의 런타임 의미는 유지했다.
- Slash skills/session 관련 회귀 `98 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. `/self`, `/agentic`, `/mcp`, `/capabilities`, `/codex` 명령과 `/market search` 사용법 수동 스모크도 `PASS`다. 초기 전체 진단에서 다중상속 변수 override 오류 3건이 발견되어 프로토콜 별칭으로 조정한 뒤 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,888 warnings / 0 notes`다. 직전 측정 10,952건에서 64건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 95 (2026-08-31)

- `src/antigravity_k/engine/prompt_evolver.py`의 PromptCandidate 메타데이터, PromptEvolver manager/설정 상태, few-shot 및 후보 생성 입력, Ollama 응답·JSON 이력 로드 경계를 `JsonMap`/Protocol/명시적 변환 helper로 정리했다. 생성자 기본 URL 평가와 문자열 암시적 결합 경고를 제거하고, 이력 파일이 부분적으로 손상돼도 기본값으로 복원하도록 경계를 고정했다.
- Prompt evolver 회귀 `17 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 manager를 통한 후보 생성·점수 선택·이력 영속화 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,952 warnings / 0 notes`다. 직전 측정 11,015건에서 63건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 94 (2026-08-31)

- `src/antigravity_k/engine/deterministic_worker.py`의 recipe input/output, model manager, JSON judge payload, parameter schema, override 메서드 경계를 Protocol/JsonMap/object 변환 helper/override로 정리했다. 이 과정에서 외부 테스트가 사용하는 SimpleNamespace manager와 이기종 recipe payload 계약을 유지하기 위해 생성자 입력과 결과 데이터의 경계 타입을 호환 가능하게 고정했다.
- Deterministic worker 회귀 `18 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 파일 레시피 실행·목록 조회·manager 없는 judge fallback 수동 스모크도 `PASS`다. 전체 basedpyright는 중간 타입 변경에서 테스트 계약 오류 6건이 발생했으나 생성자/결과 경계 조정 후 `0 errors`로 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,015 warnings / 0 notes`다. 직전 측정 11,083건에서 68건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 93 (2026-08-31)

- `src/antigravity_k/api/routes/git_api.py`의 Git 상태/로그/브랜치/그래프/스태시 응답 컬렉션, 상태 TypedDict, FastAPI Query Annotated 기본값, mutating git/cache 호출 결과 경계를 명시 타입으로 정리했다. FastAPI가 `Annotated` 내부 기본값을 거부하는 런타임 회귀를 발견해 기본값을 함수 시그니처로 이동했고, Git API 의미와 경로 보안 검증은 유지했다.
- Git API 회귀 `46 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 상태·브랜치·그래프·스태시·status parser·repo file resolver 읽기 전용 수동 스모크도 `PASS`다. 초기 테스트 수집은 FastAPI Annotated 기본값 회귀로 실패했으나 시그니처 수정 후 전부 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,083 warnings / 0 notes`다. 직전 측정 11,143건에서 60건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/deterministic_worker.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 87 (2026-08-31)

- `tests/test_prompt_builder.py`의 임시 prompt 디렉터리·private loader/cache·tool schema fixture 경계를 Path/Callable/cast와 명시 타입으로 정리했다. role/persona fallback, tool guide 시간 표시, structured/artifact/planning prompt 검증 의미는 유지했다.
- PromptBuilder 회귀 `31 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 role fallback, UTC tool guide, planning prompt 실제 생성 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,422 warnings / 0 notes`다. 직전 측정 11,490건에서 68건을 축소했으며 다음 고경고 단위는 `tests/test_shields_manager.py`(67)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 88 (2026-08-31)

- `tests/test_shields_manager.py`의 Toolset double·ShieldsManager fixture·상태/감사 반환과 config factory 경계를 Protocol/Path/Callable/cast로 정리했다. shields down/up, timeout 자동 복원, 감사 로그, 상태 영속화 검증 의미는 유지했다.
- ShieldsManager 회귀 `11 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 상태 디렉터리에서 down/up 전환과 상태 파일 생성을 확인하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,355 warnings / 0 notes`다. 직전 측정 11,422건에서 67건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 86 (2026-08-31)

- `src/antigravity_k/tools/impact_analyzer.py`의 도구 메타데이터·override 계약과 execute 입력, git/grep 검색 결과, 영향 파일 집합·리포트 조립을 명시 타입으로 정리했다. 필수 경로 오류, symbol/module 검색, 테스트·소스 파일 분류 및 리포트 의미는 유지했다.
- Impact Analyzer 연관 회귀 `10 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 대상 파일과 심볼로 영향 보고서를 생성하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,490 warnings / 0 notes`다. 직전 측정 11,559건에서 69건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 85 (2026-08-31)

- `tests/test_system_control.py`의 SystemControlTool protected action 호출, JSON 응답의 nested mapping/list, schema enum, 오류 문자열과 config 경계를 Callable/cast 기반 typed helper로 정리했다. 시스템 정보·앱·클립보드·볼륨·WiFi·알림·자동 최적화·환경 상태 테스트 의미는 유지했다.
- SystemControl 회귀 `65 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 `execute()`를 통한 volume clamp, 보호 프로세스 차단, unknown action 처리를 확인하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,648 warnings / 0 notes`다. 직전 측정 11,718건에서 70건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 84 (2026-08-31)

- `tests/test_subagent_spawner.py`의 Orchestrator·ModelManager mock, async/sync 실행 경계, task payload와 private 메서드 접근을 Protocol/Callable/Mapping/Sequence/cast로 정리했다. 병렬 결과 수집, 개별 실패 격리, 기본 도구, 동기 진입점 및 활성 이벤트 루프 거부 검증 의미는 유지했다.
- SubagentSpawner 회귀 `10 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 빈 작업·잘못된 요청·mock 스트림을 통한 실제 `spawn_parallel` 경로 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,718 warnings / 0 notes`다. 직전 측정 11,788건에서 70건을 축소했으며 다음 동률 고경고 단위는 `tests/test_system_control.py`(70)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 83 (2026-08-31)

- `tests/test_hardware_analyst.py`의 ModelManager fixture와 시스템 스펙 수집 mock을 Protocol/cast 및 typed monkeypatch로 정리하고, HardwareAnalystAgent fixture·테스트 인자를 명시했다. 시스템 스펙, API 오류 fallback, JSON 파싱 실패, 코드 블록 응답 검증 의미는 유지했다.
- Hardware Analyst 회귀 `9 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 ModelManager로 하드웨어 업그레이드 제안서 생성을 확인하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,788 warnings / 0 notes`다. 직전 측정 11,858건에서 70건을 축소했으며 다음 고경고 단위는 `tests/test_subagent_spawner.py`, `tests/test_system_control.py`(각 70)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 82 (2026-08-31)

- `tests/test_base_agent_immune.py`의 BaseAgent 실행·도구 double·호출 인자·Dummy 모델·ImmuneSystem 상태 경계를 Protocol/Callable/cast와 명시 타입으로 정리했다. 기존 mock 실행·tool-call 루프·최대 반복·세션 카운터 검증 의미는 유지했다.
- BaseAgent/immune 회귀 `11 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 ModelManager와 도구로 tool-loop 최대 반복 및 tool 메시지 기록 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,858 warnings / 0 notes`다. 직전 측정 11,929건에서 71건을 축소했으며 다음 고경고 단위는 `tests/test_hardware_analyst.py`, `tests/test_subagent_spawner.py`, `tests/test_system_control.py`(각 70)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 81 (2026-08-31)

- `tests/test_trainer_agent.py`의 ModelManager/MagicMock fixture를 명시 Protocol과 typed cast로 정리하고, TrainerAgent·pytest fixture·제안서 결과 타입을 고정했다. 모델 응답 JSON·코드 블록·실패·빈 응답 케이스의 검증 의미는 유지했다.
- TrainerAgent 회귀 `8 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 모델 double로 승인 필요 훈련 제안서를 실제 생성하는 수동 스모크도 `PASS`다.
- 전체 basedpyright는 `864 files / 0 errors / 11,929 warnings / 0 notes`다. 직전 측정 12,001건에서 72건을 축소했으며 다음 고경고 단위는 `tests/test_base_agent_immune.py`(71)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 80 (2026-08-31)

- `tests/test_memory_service.py`의 SQLite connection·VectorStore·MagicMock·protected 메서드 경계를 Protocol/Callable/cast로 정리하고, SQLite 삽입 ID 누락을 명시적 `DatabaseError`로 검증했다. `MemoryService`는 Chroma persist 경로를 SQLite 파일과 분리해 파일 경로 충돌로 semantic search가 매번 비활성화되던 결함을 수정했다.
- MemoryService 회귀 `35 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 DB에서 지식 추가·hybrid 검색·snapshot 저장/복원·통계와 별도 `.vectors` 경로를 확인하는 수동 스모크도 `PASS`다.
- `tests/test_local_model_routing_coverage.py`의 ModelManager/MagicMock·async/private 호출·monkeypatch 경계를 명시 타입과 Callable/Protocol/cast로 정리했다. 로컬 라우팅 회귀 `7 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·ModelManager 기반 challenge 생성 수동 스모크를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,001 warnings / 0 notes`다. 직전 측정 12,146건에서 145건을 축소했으며 다음 고경고 단위는 `tests/test_trainer_agent.py`(72)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 82 (2026-08-31)

- `tests/test_api_server.py`의 FastAPI TestClient 응답 JSON·중첩 payload 변환 helper, ModelManager/Runtime/Permission MagicMock Protocol, argparse·private registry·WebSocket JSON 경계를 명시 타입으로 정리했다. API 계약 검증과 접근 PIN·kanban·chat/task/embedding 회귀 의미는 유지했다.
- API server 회귀 `36 passed, 2 skipped`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. TestClient 기반 health/SPA/auth/API/WebSocket/LLM/task/embedding 시나리오가 실제 라우트에서 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,146 warnings / 0 notes`다. 직전 기록 12,219건에서 73건을 축소했으며 다음 고경고 단위는 `tests/test_memory_service.py`(73)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 81 (2026-08-31)

- `src/antigravity_k/tools/semantic_dom.py`에 Playwright 페이지·locator·A11y·mouse Protocol 경계와 mapping/list scalar 변환 helper를 도입하고, DOM/A11y raw payload·역할 매핑·bounding box·의도 후보 타입을 명시했다. 공개 parser 호출부와의 호환성을 위해 페이지 입력은 외부 `object` 경계에서 수용한 뒤 내부 typed cast로 제한했다.
- Semantic DOM 회귀 `67 passed`, 연관 browser/vision 회귀 `64 passed`, 파일 및 호출부 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 동기·비동기 snapshot, intent/ref 해석, CSS 클릭, A11y 보강 수동 스모크가 `PASS`다. 초기 전체 진단에서 발견된 browser_tool cast 2건은 공개 경계 조정 후 재실행해 해소했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,219 warnings / 0 notes`다. 직전 기록 12,294건에서 75건을 축소했으며 다음 고경고 단위는 `tests/test_api_server.py`와 `tests/test_memory_service.py`(각 73)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 80 (2026-08-31)

- `.agent/skills/k-skill/kakaotalk-mac/scripts/kakaotalk_mac.py`의 plist 파서와 캐시 JSON 경계를 재귀 `PlistValue`·Mapping 변환 helper로 명시하고, argparse Namespace 값·parser Action 반환값·파일 쓰기 결과를 안전하게 좁혔다. 읽기 전용 KakaoTalk 인증/명령 전달 의미는 유지했다.
- KakaoTalk 전용 회귀 `13 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 실제 CLI `--help`, database/key 파생, read-only passthrough command 수동 스모크가 `PASS`다. 비표준 importlib 로더를 사용한 초기 스모크 오류는 테스트 하네스 문제로 분류하고 실제 `PYTHONPATH` 모듈 경로로 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,294 warnings / 0 notes`다. 직전 기록 12,368건에서 74건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 71 (2026-08-31)

- `tests/test_benchmark_harness.py`의 BenchmarkHarness private helper·MagicMock·JSON persistence 경계를 Callable/Mapping/cast와 명시적 테스트 helper로 정리했다. 테스트 동작과 fixture 의미는 유지했으며 동적 mock 접근은 typed boundary로 제한했다.
- BenchmarkHarness 회귀 `37 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 DB를 사용한 generation kwargs·run_case 수동 스모크도 `PASS`로 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,980 warnings / 0 notes`다. 직전 기록 13,059건에서 79건을 축소했으며 다음 고경고 단위는 `tests/test_best_of_n_verifier.py`와 `tests/test_failure_memory.py`(각 79)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 70 (2026-08-30)

- `tests/test_integration_rag_cov.py`의 RAG/CoV mock·StateContext·state graph private 경계를 Protocol/Callable/Mapping/cast와 명시적 double로 정리했다. `context_enrich`의 정상 `None` 반환을 `_consume_optional_output`으로 보존했으며 기존 검증 의미를 바꾸지 않았다.
- 통합 회귀 `16 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 실제 `build_orchestrator_graph()`의 COV_VERIFY 진입·짧은 응답·memory save 구성 경로 수동 스모크도 `complete`로 종료됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,059 warnings / 0 notes`다. 직전 기록 13,139건에서 80건을 축소했으며 다음 고경고 단위는 `tests/test_benchmark_harness.py`, `tests/test_best_of_n_verifier.py`, `tests/test_failure_memory.py`(각 79)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 69 (2026-08-30)

- `tests/test_gbrain.py`의 pytest fixture·GBrain·NetworkX·ChromaDB 경계를 Path/Protocol/Callable/cast로 명시했다. 전역 singleton의 private 함수 확인은 동적 모듈 경계로 제한하고, 기존 그래프·벡터·검색·close 테스트 의미는 유지했다.
- GBrain 회귀 `21 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 실제 임시 ChromaDB 저장소에서 노드·엣지·의미 검색·close를 수행한 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,139 warnings / 0 notes`다. 직전 기록 13,219건에서 80건을 축소했으며 다음 고경고 단위는 `tests/test_integration_rag_cov.py`(80)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 68 (2026-08-30)

- `src/antigravity_k/engine/skill_installer.py`의 npm/package.json·antigravityK·MCP 설정·메타데이터 JSON 경계를 Mapping helper와 명시 타입으로 좁혔다. 선택적 market client/SkillLoader 호출은 callable 경계로 고정하고, MCP 서버 엔트리 중첩 객체 mutation을 typed entry로 재구성해 런타임 동작을 유지했다.
- SkillInstaller 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했고 전용 회귀 `77 passed`를 완료했다. 임시 패키지의 validation·MCP 식별·보안 스캔 boundary smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,219 warnings / 0 notes`다. 직전 기록 13,299건에서 80건을 축소했으며 다음 고경고 단위는 `tests/test_gbrain.py`와 `tests/test_integration_rag_cov.py`(각 80)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 67 (2026-08-30)

- `swarm_mode/llm_client.py`의 설정·JSON·HTTP 응답을 `Mapping` 기반 helper와 명시 타입으로 좁히고, OpenRouter 응답을 안전하게 파싱하며 응답 close를 `finally`에서 보장했다. 기존 문서상 미사용이던 `model`·`timeout` override도 실제 tier 호출에 반영했다.
- 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·compile 검증과 tier fallback·batch·cost alert 수동 스모크를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,299 warnings / 0 notes`다. 직전 기록 13,380건에서 81건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/skill_installer.py`(80)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 66 (2026-08-30)

- `.agent/skills/k-skill/scripts/test_kakaotalk_mac.py`가 동적 `exec` 모듈을 사용하는 구조에서도 테스트 측 Protocol facade로 `ResolvedAuth`·`DetectionState`·인증 API 반환 타입을 고정했다. private parser 내부 접근·임시 파일 쓰기·mock sentinel·argparse 반환값도 명시 경계로 처리했다.
- KakaoTalk Mac 회귀는 올바른 skill `PYTHONPATH` 표면에서 `13 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff 검증을 통과했다. 루트에서 PYTHONPATH 없이 수집하면 기존 패키지 경로 전제 때문에 실패하므로 코드 변경 없이 올바른 실행 표면을 사용했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,380 warnings / 0 notes`다. 직전 기록 13,461건에서 81건을 축소했으며 다음 고경고 단위는 `swarm_mode/llm_client.py`(81)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 65 (2026-08-30)

- `src/antigravity_k/tools/vision_dom_hybrid.py`의 Playwright 페이지 Protocol, JS payload narrowing, 스크린샷·SoM evaluate 반환값, SemanticDOM snapshot 경계를 구체화하고 거리 계산을 `math.hypot`으로 명시했다. 브라우저 도구의 VisionDOMHybrid Protocol 캐스팅 경계도 호환성 오류 없이 정리했다.
- `tests/test_agent_tools_api.py`의 private API 접근·pytest fixture·Pydantic 파라미터·세션 정리 반환값·Mock/파일 경계를 타입화했다. Vision DOM 회귀 `38 passed`, 브라우저 도구 회귀 `26 passed`, Agent Tools API 회귀 `19 passed`를 확인했다.
- 변경 파일 basedpyright/LSP 진단은 모두 `0 errors / 0 warnings`, Ruff 검증과 Vision DOM 수동 스모크, 위험 셸 차단 API 수동 스모크를 통과했다. 위험 명령은 HTTP 403으로 차단됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,461 warnings / 0 notes`다. 직전 기록 13,627건에서 166건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_kakaotalk_mac.py`와 `swarm_mode/llm_client.py`(각 81)다.
- 수동 API 스모크에서 FastAPI/Starlette의 외부 `httpx` deprecation 경고가 1회 출력됐으나 애플리케이션 진단·테스트 실패는 없었다. 의존성 업그레이드는 사용자 범위 밖이라 변경하지 않았다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 59 (2026-08-30)

- `.agent/skills/k-skill/foresttrip-vacancy/scripts/run_foresttrip_vacancy.py`의 세션 캐시·argparse Namespace·urllib 응답·JSON payload 경계를 구체 타입과 Protocol/cast로 정리하고, 응답 close를 `finally`에서 보장했다. 대상 해석과 텍스트 출력의 동적 접근 및 암시적 문자열 연결도 명시적으로 고정했다.
- ForestTrip 파일 basedpyright/LSP 진단은 `0 errors / 0 warnings`, Ruff·컴파일·`--help` 검증을 통과했다. fake HTTP 응답을 사용한 파싱·대상 해석·payload 정규화·응답 종료·텍스트 출력 스모크도 exit 0으로 완료했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,062 warnings / 0 notes`다. 직전 기록 14,148건에서 86건을 축소했으며 다음 고경고 단위 `.agent/skills/k-skill/mfds-food-safety/scripts/mfds_food_safety.py`(85)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 57 (2026-08-30)

- `src/antigravity_k/knowledge/wiki.py`의 WikiEntry 직렬화, SQLite row 경계, CRUD 업데이트 인자, 통계·내보내기·redaction·retention 컬렉션과 파일 반환값을 구체 타입/cast로 정리하고 LLMWiki를 final class로 고정했다.
- 위키 CRUD·보존/삭제·내보내기·프라이버시 회귀 `40 passed`를 확인했고, 변경 파일 basedpyright/LSP 진단은 `0 errors / 0 warnings`, Ruff·컴파일 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,322 warnings / 0 notes`다. 직전 기록 14,408건에서 86건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/korean-spell-check/scripts/korean_spell_check.py`(87)와 `scripts/benchmark_proactive_pipeline.py`(87)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 53 (2026-08-30)

- `src/antigravity_k/engine/autonomous_qa.py`에 ModelManager/Playwright 경계를 Protocol·TypedDict·명시적 JSON narrowing으로 정리하고, 콘솔·뷰포트·성능 메트릭·패치 적용 결과의 반환 타입을 고정했다. 비전/패치 JSON이 예상 외 구조일 때 빈 결과로 안전하게 처리하는 기존 동작은 유지했다.
- 자율 QA·Semantic QA 회귀 `46 passed`를 확인했고, autonomous QA 엔진 변경 파일은 basedpyright `0 errors / 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 관련 라우트의 타입 호환 오류도 함께 해소해 전체 오류를 추가하지 않았다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,669 warnings / 0 notes`다. 직전 기록 14,757건에서 88건을 축소했으며 다음 고경고 단위는 `tests/test_model_manager_stream.py`(88)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 54 (2026-08-30)

- `src/antigravity_k/tools/web_search_tool.py`의 검색·날씨·구조화 데이터 경계를 TypedDict 대체 helper와 명시 타입으로 정리하고, Jina Reader 호출은 테스트 monkeypatch와 호환되는 typed callable 경계로 고정했다. `tests/test_web_search.py`의 schema 중첩 접근도 Mapping narrowing으로 보강해 전역 타입 오류를 제거했다.
- 웹 검색 관련 회귀 `144 passed`, 단일 테스트 파일 회귀 `76 passed`를 확인했고, 변경 파일 LSP/basedpyright 진단은 `0 errors / 0 warnings`, Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,582 warnings / 0 notes`다. 직전 기록 14,669건에서 87건을 축소했으며 다음 고경고 단위는 `tests/test_model_manager_stream.py`(88)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 55 (2026-08-30)

- `tests/test_model_manager_stream.py`의 ModelManager private 경계, registry/Anthropic/MagicMock 동적 속성, 스트림 callback·fixture 인자를 명시 타입 helper와 `getattr`/`cast`로 정리했다. JSON request·cache block 검증도 Mapping narrowing으로 고정해 테스트가 실제 구조를 검증하면서 타입 경고를 남기지 않도록 했다.
- 모델 매니저 스트림 회귀 `25 passed`를 확인했고, 파일 basedpyright/LSP 진단은 `0 errors / 0 warnings`, Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,494 warnings / 0 notes`다. 직전 기록 14,582건에서 88건을 축소했으며 다음 운영 코드 고경고 단위는 `src/antigravity_k/engine/external_brain.py`(86)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 49 (2026-08-30)

- `src/antigravity_k/tools/web_search_engine.py`의 검색 공급자 JSON 응답을 명시적 object/list/text/float narrowing helper로 정리하고, DuckDuckGo 정규식 결과·PageScraper redirect 헤더·고정 네트워크 transport 타입을 보강했다. Jina 본문 추출의 공개 메서드 별칭을 유지해 기존 호출과 테스트 호환성도 보존했다.
- 검색 회귀 `139 passed`를 확인했고, 파일 LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,152 warnings / 0 notes`다. 직전 기록 15,243건에서 91건을 축소했으며 다음 고경고 단위는 `tests/test_llm_task_decomposer.py`(91), `src/antigravity_k/tools/browser_tool.py`와 `src/antigravity_k/tools/hashline_tools.py`(각 90)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 45 (2026-08-30)

- `src/antigravity_k/tools/mcp_tool_loader.py`의 MCP 도구·서버 레지스트리 경계를 명시 타입, 입력 narrowing, transport 정책 타입으로 정리했고, 공개 `register_skill_mcp` 호출부와 MCP 메타데이터 테스트를 호환되는 cast 경계로 맞췄다. `skill_installer.py`의 MCP args/env 직렬화도 실제 list/dict일 때만 복사하도록 보정했다.
- MCP 로더·capability·system API 스킬 회귀 `81 passed`를 확인했고, 변경 네 파일의 LSP 진단은 오류 0건이며 Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,431 warnings / 0 notes`다. 직전 기록 15,716건에서 285건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/ci_tools.py`(92)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 46 (2026-08-30)

- `src/antigravity_k/engine/slash_commands_workflow.py`의 도구·세션·모드·모델·런타임·스킬 로더 경계를 Protocol과 안전한 `getattr`/`cast` helper로 정리했다. QA, 목표·모드 전환, AiShell, 벤치마크, 변증법, lifecycle 명령의 기존 동작을 유지했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. slash command session·agent runtime 회귀 `53 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,526 warnings / 0 notes`다. 직전 15,620건에서 94건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/mcp_tool_loader.py`(94), `src/antigravity_k/tools/ci_tools.py`와 `swarm_mode/goal_backtest.py`(각 92)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 45 (2026-08-30)

- `src/antigravity_k/engine/agent_fabric.py`의 ModelManager·오케스트레이터 Protocol, AgentTracer Span, MessageBus 콜백, Crew/Debate 단계 결과와 상태 TypedDict 경계를 명시 타입·narrowing·`getattr`/`cast`로 정리했다. 기존 동적 private 호출·BaseAgent 실행 동작은 유지했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. AgentFabric 오케스트레이션·자기진화 REST 회귀 `29 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,620 warnings / 0 notes`다. 직전 15,716건에서 96건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/slash_commands_workflow.py`와 `src/antigravity_k/tools/mcp_tool_loader.py`(각 94), `src/antigravity_k/tools/ci_tools.py`와 `swarm_mode/goal_backtest.py`(각 92)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 29 (2026-08-30)

- `.agent/skills/k-skill/scripts/fine_dust.py`의 Air Korea JSON payload, 측정소·측정값 보고서, HTTP 오류 응답을 `JsonObject`와 명시적 narrowing으로 정리하고, 응답 스트림·후보 목록·렌더링 중첩 객체 타입을 고정했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. fine-dust 스크립트 회귀 `12 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,258 warnings / 0 notes`다. 직전 17,319건에서 61건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_fine_dust.py`(106)와 `tests/test_agent_archive.py`(106)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 28 (2026-08-30)

- `tests/test_capacity_and_skill_learner.py`의 용량·크래시 복구 fixture와 스킬 자동 학습 검증을 구체 타입으로 정리하고, MagicMock 모델을 호출 기록을 갖는 `FakeModelManager` 더블로 교체했다. protected 상태 확인은 명시적 cast 경계로 유지해 테스트 의도를 보존했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 용량·스킬 학습 회귀 `17 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,319 warnings / 0 notes`다. 직전 17,426건에서 107건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_fine_dust.py`(106)와 `tests/test_agent_archive.py`(106)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 27 (2026-08-30)

- `src/antigravity_k/engine/tool_executor.py`의 실패 판정, PlanGuard/GatePipeline/Vault/이벤트 버스 경계를 Protocol과 구체 결과 타입으로 정리하고, JSON 체크포인트·필수 인자·경로 입력을 런타임에서 안전하게 좁혔다. 실행 이력의 permission 필드를 항상 직렬화해 기존 테스트 접근 계약을 유지했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 도구 실행 회귀 `25 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,426 warnings / 0 notes`다. 직전 17,537건에서 111건을 축소했으며 다음 고경고 단위는 `tests/test_capacity_and_skill_learner.py`(107)와 `.agent/skills/k-skill/scripts/test_fine_dust.py`(106)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 24 (2026-08-30)

- `src/antigravity_k/tools/self_evolution_tool.py`의 Self-Evolution 도구·Self-Reward 평가기·메타인지 트래커에 Protocol, TypedDict, `Mapping` 경계를 적용했다. 모델 생성기·JSON 디코더·평가 이력·진화 사이클 영속화의 동적 값을 구체 타입으로 좁히고, 불필요한 `Any`·미사용 결과·암시적 문자열 결합 경고를 제거했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다. 자기진화/스킬 생성 회귀 `62 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,809 warnings / 0 notes`다. 직전 17,927건에서 118건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/engine_context.py`(113)와 `tests/test_lora_dpo.py`(113)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 22 (2026-08-30)

- `.agent/skills/k-skill/scripts/fine_dust.py`의 argparse 결과를 `ReportArgs` TypedDict로 변환하고, 조회·프록시·측정 payload 경계의 속성 접근을 키 기반 접근으로 정렬했다. argparse 반환값 미사용 경고도 명시적으로 소비해 타입 진단 오류 없이 유지했다.
- fine-dust 회귀 테스트 `12 passed`, Ruff·Python 컴파일을 통과했고 파일 LSP 진단은 `0 errors`다. 남은 경고는 외부 Air Korea JSON의 동적 payload 경계에 한정된 기존 `Any`/unknown 경고로, 이번 변경에서 새 경고를 추가하지 않았다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,042 warnings / 0 notes`다. 직전 18,095건에서 53건을 축소했으며 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않는다.

## Warning debt continuation 23 (2026-08-30)

- `src/antigravity_k/engine/session_manager.py`의 세션·메모리 상태를 `SessionData`/`SessionMetadata`/`SessionInfo` TypedDict로 명시하고 JSON 로딩·redaction·자동 복원 경계에 런타임 narrowing을 적용했다. 기존 세션 파일 호환과 메모리 스코프 동작은 유지했다.
- 세션 통합·컴플라이언스·스코프 회귀 `58 passed`, Ruff·컴파일을 통과했고 파일 LSP 진단은 `0 errors / 0 warnings`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,927 warnings / 0 notes`다. 직전 18,042건에서 115건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/self_evolution_tool.py`(114), `src/antigravity_k/engine/engine_context.py`(113)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 21 (2026-08-30)

- `tests/test_global_memory_provider.py`의 GlobalMemoryProvider fixture, Path 매개변수, MemoryManager 통합, persistence·identity·working-memory 시나리오의 타입 경계를 명시했다. 글로벌 메모리 회귀 `26 passed`, 파일 LSP/basedpyright `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,095 warnings / 0 notes`다. 직전 18,210건에서 115건을 축소했다. `memory_provider.py`의 공개 export 호환성을 위한 명시적 `Any` 잔여 5건은 별도 계약 정비 대상으로 유지한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 20 (2026-08-30)

- `src/antigravity_k/engine/memory_provider.py`의 SessionManager Protocol, 메모리 범위 반환, episodic JSON coercion, retention/consolidation 인덱스, working-memory export 경계를 구체 타입으로 정리했다. 메모리 관련 회귀 `105 passed`, 파일 LSP 진단 `0 errors`, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,210 warnings / 0 notes`다. 직전 18,320건에서 110건을 축소했다. 공개 export 호환성을 유지하기 위해 해당 파일의 잔여 명시적 `Any` 5건은 동작 변경 없이 후속 계약 정비 대상으로 남겼다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 19 (2026-08-30)

- `tests/test_harness.py`의 pytest fixture·urllib 응답·Playwright page·WebSocket mock과 TestHarness 보호 메서드 접근을 구체 타입 및 typed adapter로 정리했다. 하네스 회귀 `52 passed`, 파일 LSP/basedpyright `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,320 warnings / 0 notes`다. 직전 18,438건에서 118건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/memory_provider.py`와 `tests/test_global_memory_provider.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 18 (2026-08-30)

- `tests/test_search_extract_e2e.py`의 DataExtractor fixture와 전체 E2E 테스트 메서드 반환 타입을 명시해 결과·주식·날씨·환율·날짜 추출 경계를 기반 타입으로 연결했다. 검색→추출→LLM 포맷 회귀 `17 passed`, 파일 LSP/basedpyright `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,438 warnings / 0 notes`다. 직전 18,560건에서 122건을 축소했으며 다음 고경고 단위는 전역 진단 상위 목록의 후속 테스트 파일이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 17 (2026-08-30)

- `tests/test_vault_api.py`의 Vault fixture·FastAPI dependency override·TestClient JSON 응답·경로 순회 요청·VectorStore mock 경계를 구체 타입과 typed adapter로 정리하고, 의도적 미사용 결과를 명시했다. Vault API 회귀 `14 passed`, 파일 LSP/basedpyright `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,560 warnings / 0 notes`다. 직전 18,683건에서 123건을 축소했으며 다음 고경고 단위는 `tests/test_search_extract_e2e.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 15 (2026-08-30)

- `src/antigravity_k/engine/skill_market_client.py`의 npm JSON 입력·설치 상태·상세 메타데이터 경계를 재귀 JSON 타입, `Mapping`/`Sequence` 및 TypedDict 결과 계약으로 정리했다. `_parse_view_result`의 다중 버전·description 객체·repository URL·README truthy 동작을 기존 의미대로 유지했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·SkillMarketClient smoke를 통과했고, `tests/test_skill_market_client.py` 및 `tests/test_week2_e2e.py` 회귀 `117 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,836 warnings / 0 notes`다. 직전 18,961건에서 125건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/benchmark_harness.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 14 (2026-08-30)

- `tests/test_approval_manager_flow.py`의 승인 관리자 fixture·diff 생성기·pending 상태 경계를 구체 타입과 typed adapter로 정리하고, 의도적 미사용 결과를 명시했다. 승인·거부·항상 허용·타임아웃·diff 회귀 `16 passed`, 파일 LSP/basedpyright 0 warnings, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,961 warnings / 0 notes`다. 직전 19,086건에서 125건을 축소했으며 현재 경고 상위는 `src/antigravity_k/engine/skill_market_client.py`(125), `src/antigravity_k/engine/benchmark_harness.py`(123), `tests/test_vault_api.py`(123) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 13 (2026-08-30)

- `tests/test_task_runner_resume.py`의 백그라운드 오케스트레이터·SQLite 연결·체크포인트·스레드 접근을 Protocol 수준의 구체 타입과 typed adapter로 정리했다. 재개·체크포인트·작업 격리 회귀 `10 passed`, 파일 LSP/basedpyright 0 warnings, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,086 warnings / 0 notes`다. 직전 19,213건에서 127건을 축소했으며 현재 경고 상위는 `src/antigravity_k/engine/skill_market_client.py`(125), `tests/test_approval_manager_flow.py`(125), `src/antigravity_k/engine/benchmark_harness.py`(123) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 12 (2026-08-30)

- `tests/test_model_router.py`의 MagicMock 레지스트리를 타입 안전한 `_RegistryStub`으로 교체하고, pytest fixture·라우터 결과·상태 응답·protected 멤버 접근을 구체 타입/typed adapter로 정리했다. 모델 라우팅 회귀 `35 passed`, 파일 LSP/basedpyright 0 warnings, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,213 warnings / 0 notes`다. 직전 19,341건에서 128건을 축소했으며 현재 경고 상위는 `tests/test_task_runner_resume.py`(127), `src/antigravity_k/engine/skill_market_client.py`(125), `tests/test_approval_manager_flow.py`(125) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 4 (2026-08-30)

- `tests/test_slash_commands_session.py`의 세션 fixture Protocol, typed command dispatcher, callback·경로·SQLite 경계를 정리했다. 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff와 diff 검사를 통과했다.
- 슬래시 커맨드 세션 회귀는 `20 passed`로 완료됐다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 20,310 warnings / 0 notes`다. 직전 20,448건에서 138건을 축소했으며 다음 고경고 단위는 `scripts/generate_docstrings.py`(133)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 5 (2026-08-30)

- `scripts/generate_docstrings.py`의 생성기 컨텍스트·Ruff 결과·CLI 인자·OpenAI 응답 경계를 명시하고, 동적 import/argparse 결과를 안전한 `cast` 경계로 격리했다. 실행 진입점은 내부 `_main`으로 정리해 생성기 자체 docstring 검사의 누락도 제거했다. 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·`--check`·절대 경로 smoke를 통과했다.
- `src/antigravity_k/engine/orchestrator/stream.py`의 오케스트레이터·메모리·압축기·상태 그래프 Protocol 경계를 정리하고, 동적 private 속성 접근을 typed adapter로 격리했다. 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, 오케스트레이터/agent runtime 회귀 `42 passed`, Ruff 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 20,043 warnings / 0 notes`다. 직전 20,310건에서 267건을 축소했으며 다음 고경고 단위는 `tests/test_models_system_api.py`(131), `src/antigravity_k/cli.py`(130), `src/antigravity_k/engine/self_evolution_coordinator.py`(130) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 6 (2026-08-30)

- `tests/test_models_system_api.py`의 API 응답 JSON 경계와 TestClient fixture를 명시하고, MagicMock 기반 매니저·임베딩·런타임을 동작을 보존하는 typed test doubles로 교체했다. 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Models/System API 회귀 `9 passed`, Ruff 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,912 warnings / 0 notes`다. 직전 20,043건에서 131건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/cli.py`(130), `src/antigravity_k/engine/self_evolution_coordinator.py`(130), `tests/test_amplification_benchmark.py`(130) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 7 (2026-08-30)

- `src/antigravity_k/cli.py`의 Typer 옵션·인자 기본값을 `Annotated` 메타데이터로 전환해 `reportCallInDefaultInitializer` 경고를 제거했다. YAML·마켓 응답·autopilot subgoal 경계를 구체 타입으로 정리하고, 내부 `_market_search`가 Typer 명령으로 잘못 등록되어 전체 CLI 초기화를 막던 회귀도 제거했다.
- CLI 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·Python 컴파일·CLI 스모크 `8 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,782 warnings / 0 notes`다. 직전 19,912건에서 130건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/self_evolution_coordinator.py`(130), `tests/test_amplification_benchmark.py`(130), `tests/test_api_cache.py`(130) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 8 (2026-08-30)

- `src/antigravity_k/engine/self_evolution_coordinator.py`의 성능 데이터·동적 JSON·RSI/스킬/샌드박스 의존성 경계를 Protocol과 `Mapping`/`cast`로 정리했다. protected 진단 호출은 typed adapter로 격리하고, 이력 로딩·결정적 AST/YAML/JSON 검증·변이 메서드 인자 소비를 구체 타입으로 보강했다.
- 해당 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일을 통과했으며 `tests/test_self_evolution_coordinator.py`는 `34 passed`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,652 warnings / 0 notes`다. 직전 19,782건에서 130건을 축소했으며 다음 고경고 단위는 `tests/test_amplification_benchmark.py`와 `tests/test_api_cache.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 9 (2026-08-30)

- `tests/test_amplification_benchmark.py`의 MagicMock·모델 콜백·증폭 결과/통계 TypedDict 경계를 명시하고, protected 멤버 패치는 typed `setattr`/adapter로 격리했다. 증폭 벤치마크 회귀 `20 passed`, 파일 LSP/basedpyright 0 warnings, Ruff·컴파일 통과를 확인했다.
- `tests/test_self_evolution_coordinator.py`의 `JsonObject` 반환 경계, pytest `Path` fixture, protected coordinator 접근을 typed helper로 정리해 전역 진단의 2개 오류와 파일 경고를 제거했다. 자기진화 회귀를 포함한 두 파일 테스트는 `54 passed`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,479 warnings / 0 notes`다. 직전 19,652건에서 173건을 축소했으며 다음 고경고 단위는 `tests/test_api_cache.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 10 (2026-08-30)

- `tests/test_api_cache.py`의 캐시 fixture·통계 TypedDict·응답/URL test double·cached decorator 경계를 구체 타입으로 정리하고, private cache entries 접근은 typed helper로 격리했다. 캐시/데코레이터 회귀 `31 passed`, 파일 LSP/basedpyright 0 warnings, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,349 warnings / 0 notes`다. 직전 19,479건에서 130건을 축소했으며 다음 고경고 단위는 `tests/test_worktree_manager.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 11 (2026-08-30)

- `tests/test_worktree_manager.py`의 subprocess mock 명령 인자와 의도적 미사용 결과를 구체 타입으로 명시했다. 워크트리 생성·삭제·조회 회귀 `16 passed`, 파일 LSP/basedpyright 0 warnings, Ruff·컴파일 통과를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 19,341 warnings / 0 notes`다. 직전 19,349건에서 8건을 축소했으며 현재 경고 상위는 `tests/test_model_router.py`(128건)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 16 (2026-08-30)

- `src/antigravity_k/engine/benchmark_harness.py`의 결과·증폭 통계·task outcome을 TypedDict 계약으로 명시하고, ModelManager 실행 메서드·registry 설정·JSON 영속화 경계를 구체 타입과 typed adapter로 정리했다. README/증폭 모드/legacy 결과 로딩의 기존 동작은 유지했다.
- 연관 스크립트 `scripts/run_bon_ab_measurement.py`의 증폭 결과 타입과 benchmark 테스트의 MagicMock 접근 경계를 정렬했다. 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일을 통과했고 benchmark/amplification/task benchmark 회귀 `68 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 18,683 warnings / 0 notes`다. 직전 18,836건에서 153건을 축소했으며 다음 고경고 단위는 `tests/test_vault_api.py`와 `tests/test_search_extract_e2e.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 25 (2026-08-30)

- `src/antigravity_k/engine/engine_context.py`의 EngineContext 초기화 경계에 구체 타입과 Protocol을 적용하고, 동적 SlashCommand/ToolExecutor 로딩은 순환 의존성을 유지하면서 typed callable로 격리했다. YAML·인지·품질·비용 설정의 값을 안전하게 좁히고, 주입형 ToolRegistry 및 JSON 설정 계약을 보존했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다. 엔진 컨텍스트·증폭 설정·프로젝트 메모리·메모리 스코프·에이전트 정의·컨텍스트 예산 회귀 `69 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,650 warnings / 0 notes`다. 직전 17,809건에서 159건을 축소했으며 다음 고경고 단위는 `tests/test_lora_dpo.py`(113)와 `src/antigravity_k/engine/tool_executor.py`(107)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 26 (2026-08-30)

- `tests/test_lora_dpo.py`의 LoRA/DPO fixture, JSONL 결과, subprocess 프로세스 더블, monkeypatch 콜백을 구체 타입으로 정리했다. `LoRAPipeline.pairs` 읽기 전용 경계를 추가해 테스트의 protected 상태 직접 접근도 제거했다.
- 파일 basedpyright/LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일 통과를 확인했다. LoRA/DPO 회귀 `17 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,537 warnings / 0 notes`다. 직전 17,650건에서 113건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/tool_executor.py`(107)와 `tests/test_capacity_and_skill_learner.py`(107)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 30 (2026-08-30)

- `.agent/skills/k-skill/scripts/test_fine_dust.py`의 동적 `fine_dust` 모듈, 환경변수 매핑, `fetch_json` 테스트 더블, 기록된 URL/파라미터, JSON CLI 결과를 Protocol·TypedDict·명시적 cast로 정리했다. 테스트 콜백의 부분 추론과 미사용 반환값을 제거해 파일 경고를 0으로 만들었다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. fine-dust 테스트 `12 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,152 warnings / 0 notes`다. 직전 17,258건에서 106건을 축소했으며 다음 고경고 단위는 `tests/test_agent_archive.py`(106)와 `src/antigravity_k/engine/cognitive_loop.py`(105)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 31 (2026-08-30)

- `tests/test_agent_archive.py`의 pytest fixture 반환 타입, 테스트 메서드 인자/반환 타입, 아카이브 결과의 의도적 미사용 반환값을 명시했다. private 변이체 목록 검사는 `getattr`과 `cast` 경계로 격리했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. AgentArchive 회귀 `21 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 17,046 warnings / 0 notes`다. 직전 17,152건에서 106건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/cognitive_loop.py`(105)와 `src/antigravity_k/engine/orchestrator_context_handlers.py`(104)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 32 (2026-08-30)

- `src/antigravity_k/engine/cognitive_loop.py`의 계획/검증/성찰 이력에 TypedDict와 Protocol을 적용하고, 실패 메모리·외부 두뇌·Cavemem·비동기 executor 경계를 구체화했다. 파일 경고 105건을 제거하면서 실행 흐름과 재시도 동작은 유지했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 인지 루프·외부 두뇌·PlannerExecutor 연관 회귀 `34 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,938 warnings / 0 notes`다. 직전 17,046건에서 108건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/orchestrator_context_handlers.py`(104)와 `tests/test_tool_executor.py`(103)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 33 (2026-08-30)

- `src/antigravity_k/engine/orchestrator_context_handlers.py`의 오케스트레이터·Watchdog·KI·자율학습·스킬 로더·RAG·벡터 저장소 경계를 Protocol과 명시적 narrowing으로 정리했다. 동적 의존성은 cast된 로컬 경계로 격리하고 컨텍스트 주입 동작은 유지했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 오케스트레이터 핸들러 및 RAG/파일 선택 회귀 `23 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,815 warnings / 0 notes`다. 직전 16,938건에서 123건을 축소했으며 다음 고경고 단위는 `tests/test_tool_executor.py`(103)와 `src/antigravity_k/engine/vector_store.py`(102)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 34 (2026-08-30)

- `tests/test_tool_executor.py`의 레지스트리 더블·실행 콜백·이벤트 콜백에 구체 타입을 부여하고, 보호 멤버 및 부분적으로 추론되지 않는 내부 API는 `getattr`·`cast` 경계로 격리했다. Permission import도 공개 계약 모듈로 정리했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. ToolExecutor 회귀 `25 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,712 warnings / 0 notes`다. 직전 16,815건에서 103건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/vector_store.py`와 `tests/test_approval_manager.py`(각 102)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 35 (2026-08-30)

- `src/antigravity_k/engine/vector_store.py`의 선택적 ChromaDB 클라이언트·컬렉션·메타데이터·검색 결과 경계를 Protocol, Mapping, Sequence와 명시적 narrowing으로 정리했다. 공개 SharedSystemClient import도 실제 모듈 경로로 교정했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. RAG·durable memory·benchmark 회귀 `26 passed`를 확인했다.
- 전역 오류는 `0`으로 유지되며 최신 전체 basedpyright는 `864 files / 0 errors / 16,609 warnings / 0 notes`다. 직전 16,815건에서 206건을 축소했으며 다음 고경고 단위는 `tests/test_approval_manager.py`, `tests/test_healing_loop.py`, `tests/test_orchestrator.py`(각 102)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 36 (2026-08-30)

- `tests/test_approval_manager.py`의 ApprovalManager fixture, 테스트 메서드 인자·반환 타입과 의도적으로 버리는 승인 결과를 명시했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. ApprovalManager 회귀 `17 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,507 warnings / 0 notes`다. 직전 16,609건에서 102건을 축소했으며 다음 고경고 단위는 `tests/test_healing_loop.py`와 `tests/test_orchestrator.py`(각 102)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 37 (2026-08-30)

- `tests/test_healing_loop.py`의 HealingLoop/HealingLoopV2 내부 호출과 동적 페이지·DOM mock 경계를 helper·cast·명시적 콜백 타입으로 정리했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. HealingLoop 회귀 `30 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,405 warnings / 0 notes`다. 직전 16,507건에서 102건을 축소했으며 다음 고경고 단위는 `tests/test_orchestrator.py`(102)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 38 (2026-08-30)

- `tests/test_orchestrator.py`의 동적 `MagicMock` 체인·호출 인자·상태 그래프 경계를 typed helper, `setattr`, `cast`로 정리했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. Orchestrator 회귀 `9 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,303 warnings / 0 notes`다. 직전 16,405건에서 102건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/harness.py`(100)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 39 (2026-08-30)

- `src/antigravity_k/engine/harness.py`의 API JSON 응답과 Playwright 페이지·브라우저 계약을 Protocol·JSON narrowing·명시적 인스턴스 타입으로 정리했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 하네스 회귀 `52 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,203 warnings / 0 notes`다. 직전 16,303건에서 100건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/rag_indexer.py`와 `tests/test_model_manager_lifecycle.py`(각 99)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 40 (2026-08-30)

- `src/antigravity_k/engine/rag_indexer.py`의 벡터 저장소 Protocol, JSON·메타데이터·provenance 결과, 장기 컨텍스트 검색 결과 경계를 명시 타입과 narrowing으로 정리했다. 관련 benchmark·RAG 테스트의 nested object 접근도 cast 경계로 맞췄다.
- `tests/test_model_manager_lifecycle.py`의 registry·HTTP 응답·비공개 매니저 호출 경계를 typed helper, Protocol, `setattr`, `cast`로 정리했다.
- 두 파일의 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. RAG 관련 회귀 `47 passed`, ModelManager 라이프사이클 회귀 `43 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 16,005 warnings / 0 notes`다. 직전 16,203건에서 198건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/config.py`(98)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 41 (2026-08-30)

- `src/antigravity_k/config.py`의 YAML 설정 경계를 `ConfigValue`·`ConfigMap` 타입으로 좁히고, Pydantic 설정 생성은 검증된 `_build_settings` 경로로 통합했다. 동적 registry 조회·비용 예산·파일 쓰기 결과도 명시적으로 narrowing했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 설정·보안·Computer Use·Vault API 회귀 `87 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,907 warnings / 0 notes`다. 직전 16,005건에서 98건을 축소했으며 다음 고경고 단위는 `scripts/calc_recommended_thresholds.py`(97)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 42 (2026-08-30)

- `scripts/calc_recommended_thresholds.py`의 벤치마크 함수 반환·결과 사용, MaxEngine/RAG private 호출, argparse 값과 stage skip 매칭을 명시 타입·호출 helper로 정리했다. `--skip-stage`가 전체 stage 이름과 정확히 매칭되도록 실행 경로도 보정했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. skip-stage CLI smoke를 종료 코드 0으로 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,810 warnings / 0 notes`다. 직전 15,907건에서 97건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/agent_fabric.py`, `src/antigravity_k/engine/slash_commands_workflow.py`, `src/antigravity_k/tools/mcp_tool_loader.py`, `tests/test_heartbeat_monitor.py`(각 94)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 43 (2026-08-30)

- `scripts/calc_recommended_thresholds.py`의 통계 계산·벤치 함수·MaxEngine/RAG 실행 경계와 argparse 옵션을 명시 타입·결과 소비·호출 helper로 정리했다. `--skip-stage`가 그룹 전체 이름을 정확히 건너뛰도록 stage 확인 로직도 수정했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. 모든 stage를 건너뛰는 CLI smoke가 종료 코드 0으로 동작함을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,810 warnings / 0 notes`다. 직전 15,907건에서 97건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/agent_fabric.py`, `src/antigravity_k/engine/slash_commands_workflow.py`, `src/antigravity_k/tools/mcp_tool_loader.py`, `tests/test_heartbeat_monitor.py`(각 94)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 44 (2026-08-30)

- `tests/test_heartbeat_monitor.py`의 pathlib fixture, HeartbeatTask·HeartbeatResult 실행 경계, private interval·history 접근과 datetime monkeypatch를 명시 타입·cast·helper로 정리했다.
- 파일 LSP/basedpyright 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했다. Heartbeat 회귀 `17 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,716 warnings / 0 notes`다. 직전 15,810건에서 94건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/agent_fabric.py`, `src/antigravity_k/engine/slash_commands_workflow.py`, `src/antigravity_k/tools/mcp_tool_loader.py`(각 94)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 47 (2026-08-30)

- `src/antigravity_k/tools/ci_tools.py`의 테스트·린트·PR 실행 도구에 TypedDict, 명시적 입력 narrowing, `@final`, 안전한 실행 결과 타입을 적용해 파일 경고 92건을 제거했다. 셸 실행은 기존 argv·`shell=False` 경계를 유지했다.
- CI 도구 회귀 `47 passed`를 확인했고, 변경 production/test 파일의 LSP 진단은 오류 0건이며 Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,335 warnings / 0 notes`다. 직전 기록 15,431건에서 96건을 축소했으며 다음 고경고 단위는 `swarm_mode/goal_backtest.py`(92)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 48 (2026-08-30)

- `swarm_mode/goal_backtest.py`의 백테스트 결과·시장 데이터·신호·메트릭·포트폴리오 영향 구조를 TypedDict와 명시적 수치/문자열 narrowing으로 정리하고, CLI 인자·JSON 설정 경계를 안전하게 파싱했다.
- 파일 LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했으며, `--period 5` CLI smoke에서 성공 상태와 기간을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,243 warnings / 0 notes`다. 직전 기록 15,335건에서 92건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/web_search_engine.py`와 `tests/test_llm_task_decomposer.py`(각 91)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 50 (2026-08-30)

- `tests/test_llm_task_decomposer.py`의 private 심볼 접근, callback·fixture 인자, ModelManager private 메서드 mock 교체, ToolLoop MagicMock 체인을 명시 타입·cast·mock helper로 정리했다. 테스트 동작을 유지하면서 타입 검사 경계를 분명히 했다.
- 파일 LSP 진단은 `0 errors, 0 warnings`, Ruff·컴파일·diff 검사를 통과했으며, LLM 작업 분해·ToolLoop 회귀 `30 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 15,061 warnings / 0 notes`다. 직전 기록 15,152건에서 91건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/browser_tool.py`와 `src/antigravity_k/tools/hashline_tools.py`(각 90)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 51 (2026-08-30)

- `src/antigravity_k/tools/browser_tool.py`의 Params/A11y 타입을 명시화하고, Playwright action 입력 narrowing, accessibility·Semantic DOM·Vision 경계를 Protocol/cast로 보강했다. `tests/test_browser_tool.py`의 mock/private 접근과 스키마 중첩 값도 명시 타입으로 정리해 전역 타입 오류를 방지했다.
- 브라우저·세션·Semantic DOM·Vision 회귀 `154 passed`를 확인했고, 변경 파일 LSP 진단은 오류 0건·경고 0건, Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,885 warnings / 0 notes`다. 직전 기록 15,061건에서 176건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/hashline_tools.py`(90)와 `src/antigravity_k/engine/autonomous_qa.py`, `tests/test_model_manager_stream.py`(각 88)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 52 (2026-08-30)

- `src/antigravity_k/tools/hashline_tools.py`의 세 파일 도구에 Params/Schema 타입, 공통 문자열·replacement chunk narrowing, `@final`·`@override`, 파일 라인 처리 타입을 적용했다. 잘못된 ReplacementChunks는 명시적 오류로 거부하고 기존 정상 교체 경로는 유지했다.
- `tests/test_hashline_tools.py`의 schema 접근과 임시 파일 쓰기 결과를 명시 타입으로 정리했다. hashline·file-tools 회귀 `55 passed`를 확인했고, 변경 파일 LSP 진단은 오류 0건·경고 0건, Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,757 warnings / 0 notes`다. 직전 기록 14,885건에서 128건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/autonomous_qa.py`와 `tests/test_model_manager_stream.py`(각 88)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 56 (2026-08-30)

- `src/antigravity_k/engine/external_brain.py`의 외부 두뇌 어댑터와 라우터에 concrete class finality, override, 속성 타입을 적용하고, Playwright DOM polling 경계를 Protocol·cast로 고정했다. AppleScript/subprocess·파일 정리 반환값과 비교 결과 컬렉션도 명시적으로 처리했다.
- 외부 두뇌 단위·E2E 회귀 `29 passed`를 확인했고, 파일 basedpyright/LSP 진단은 `0 errors / 0 warnings`, Ruff·컴파일·diff 검사를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,408 warnings / 0 notes`다. 직전 기록 14,494건에서 86건을 축소했으며 다음 운영 코드 고경고 단위는 `src/antigravity_k/knowledge/wiki.py`(85)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 58 (2026-08-30)

- `.agent/skills/k-skill/korean-spell-check/scripts/korean_spell_check.py`의 JSON payload·HTML 응답·argparse Namespace·보고서 구조를 Payload/Protocol/cast 경계로 정리하고, 입력 변환·HTTP 응답 종료·CLI 인자 반환 타입을 명시했다.
- `scripts/benchmark_proactive_pipeline.py`의 벤치마크 metadata·스테이지 콜백·MagicMock·private 엔진 호출·JSON 비교·argparse 경계를 구체 타입과 동적 호출 경계로 고정했다.
- 맞춤법 검사기 정적 진단 `0 errors / 0 warnings`, Ruff·컴파일·smoke 검증을 통과했고, 벤치마크 CLI code_review 1회 실행도 exit 0으로 완료했다. 벤치마크 파일 LSP/basedpyright 진단은 `0 errors / 0 warnings`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 14,148 warnings / 0 notes`다. 직전 기록 14,235건에서 87건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/foresttrip-vacancy/scripts/run_foresttrip_vacancy.py`(86)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 60 (2026-08-30)

- `.agent/skills/k-skill/mfds-food-safety/scripts/mfds_food_safety.py`의 JSON payload·HTTP 응답·request callback·argparse Namespace 경계를 구체 타입과 Protocol/cast로 정리했다. MFDS 응답은 항상 명시된 mapping으로 좁히고 HTTP 응답 close를 `finally`에서 보장했다.
- MFDS 파일 basedpyright/LSP 진단은 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. interview CLI와 네 개 endpoint builder, 정규화·필터링·fake HTTP 응답 종료 스모크도 exit 0으로 완료했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,977 warnings / 0 notes`다. 직전 기록 14,062건에서 85건을 축소했으며 다음 고경고 단위는 `tests/test_quality_gate_checkers.py`(85)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 61 (2026-08-30)

- `tests/test_quality_gate_checkers.py`의 QualityGate private checker 호출을 명시적 `ScoreIssues`·Callable/cast 경계로 감싸고, 모든 pytest fixture/test 함수에 반환·인자 타입을 부여했다. protected 접근 경고는 동적 경계 helper로 한정했으며 테스트 의미는 유지했다.
- QualityGate checker 회귀 `15 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,892 warnings / 0 notes`다. 직전 기록 13,977건에서 85건을 축소했으며 다음 고경고 단위는 `tests/test_prompt_injection_guard.py`(84)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 62 (2026-08-30)

- `tests/test_prompt_injection_guard.py`에 PromptInjectionGuard Protocol 경계와 명시적 verdict 타입을 도입하고, 파라미터화 pytest 입력·fixture·반환 타입을 고정했다. ToolLoop의 protected formatter 호출은 Callable/cast 경계로 감싸 런타임 동작은 유지했다.
- Prompt injection guard 회귀 `33 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,808 warnings / 0 notes`다. 직전 기록 13,892건에서 84건을 축소했으며 다음 고경고 단위는 `tests/test_scout_agent.py`(84)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 63 (2026-08-30)

- `tests/test_scout_agent.py`에 ModelManager/MagicMock double Protocol과 ScoutAgent fixture·테스트 인자 타입을 도입했다. MagicMock 동적 `generate`·파일 mock은 명시적 cast 경계로 제한해 기존 제안·오류·메모리 경로 검증을 그대로 유지했다.
- ScoutAgent 회귀 `10 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,724 warnings / 0 notes`다. 직전 기록 13,808건에서 84건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/gate_pipeline.py`(83)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 64 (2026-08-30)

- `src/antigravity_k/engine/gate_pipeline.py`의 GateValue·GateContext·게이트 의존성(guardrail/cost/security) Protocol을 구체화하고, pipeline 게이트 목록·정렬·판정 metadata 반환 타입을 명시했다. 비용·보안 입력 변환을 안전한 경계 helper로 좁히고 BUILD 모드의 도달 불가능한 중복 조건을 제거했다.
- GatePipeline 회귀 `24 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff 검증을 통과했다. GateContext 호출부와의 호환성까지 전체 진단으로 재확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 13,627 warnings / 0 notes`다. 직전 기록 13,724건에서 97건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/vision_dom_hybrid.py`와 `tests/test_agent_tools_api.py`(각 83)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 72 (2026-08-31)

- `tests/test_best_of_n_verifier.py`의 BestOfNVerifier 생성 콜백·Best-of-N trace·ModelManager 테스트 double·worktree subprocess 경계를 Callable/Protocol과 명시 타입으로 정리했다. 동적 private registry 주입은 `setattr` 경계로 제한하고 검증 의미는 유지했다.
- Best-of-N 회귀 `31 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 실제 실행 검증 후보의 조기 종료·통과 카운트 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,901 warnings / 0 notes`다. 직전 기록 12,980건에서 79건을 축소했으며 다음 고경고 단위는 `tests/test_failure_memory.py`(79)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 73 (2026-08-31)

- `tests/test_failure_memory.py`의 FailureMemory fixture·private helper·JSONL·GBrain 결과 경계를 Path/Callable/Mapping/cast로 정리했다. 세션 실패 컬렉션과 로그 회전 테스트의 protected 접근을 typed helper로 제한하고 기록·검색 의미는 유지했다.
- FailureMemory 회귀 `18 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 프로젝트에서 실패 기록·세션 통계·유사 검색·JSONL 생성 수동 스모크도 `PASS`다. GBrain이 기존 결과를 우선 반환하는 동작까지 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,822 warnings / 0 notes`다. 직전 기록 12,901건에서 79건을 축소했으며 다음 고경고 단위는 `tests/test_inference_providers.py`(77)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 74 (2026-08-31)

- `tests/test_inference_providers.py`의 HTTP response/context MagicMock·urllib Request·JSON payload·tool schema 경계를 Protocol/typed helpers/cast로 정리하고 pytest fixture 타입을 명시했다. Ollama·LM Studio·Unsloth provider 검증의 요청/스트림 의미는 유지했다.
- Inference provider 회귀 `10 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 유효한 Ollama profile에서 provider 선택 수동 스모크도 `PASS`다. 불완전한 profile로 발생한 초기 스모크 assertion은 필수 `repo/provider` 필드를 보강해 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,745 warnings / 0 notes`다. 직전 기록 12,822건에서 77건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/curriculum_generator.py`와 `tests/test_extraction_ab_test.py`(각 76)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 75 (2026-08-31)

- `tests/test_extraction_ab_test.py`의 ExtractionABTestRunner fixture·run_test/run_suite 메서드 경계를 Callable/cast와 명시 타입으로 정리하고 `to_dict()` 비교 결과를 안전하게 좁혔다. 내장 데이터 추출 A/B 테스트 의미와 fixture 입력은 유지했다.
- Extraction A/B 회귀 `27 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. `run_builtin_suite()` 실제 실행 및 Markdown 생성 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,669 warnings / 0 notes`다. 직전 기록 12,745건에서 76건을 축소했으며 다음 고경고 단위는 `swarm_mode/orchestrator.py`와 `tests/test_agent_runtime.py`, `tests/test_google_skills_pattern.py`(각 75)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 76 (2026-08-31)

- `tests/test_agent_runtime.py`의 AgentRuntime 회귀 double·BackgroundTaskRunner private 경계·MagicMock 엔진/멀티플렉서 호출·GoalRunner/라우트 계약을 Protocol·명시 타입·동적 경계 helper로 정리했다. 키워드 `owner_subject` 계약은 유지하고 테스트 내부에서 소비하도록 해 실제 라우트 호출 호환성을 보존했다.
- AgentRuntime 회귀 `33 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. FakeOrchestrator를 통한 `AgentRuntime.complete()` 수동 스모크가 `firstsecond`를 반환해 스트림 결합 동작을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,594 warnings / 0 notes`다. 직전 기록 12,669건에서 75건을 축소했으며 다음 고경고 단위는 `swarm_mode/orchestrator.py`와 `tests/test_google_skills_pattern.py`(각 75)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 77 (2026-08-31)

- `tests/test_google_skills_pattern.py`의 Google Skills fixture·테스트 인자·임시 파일 작성 반환값을 `Path`와 명시 반환 타입으로 정리하고, `SkillsRegistry._extract_section_list` private 호출은 typed callable 경계 helper로 제한했다.
- Google Skills 패턴 회귀 `17 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 스킬 디렉터리에서 `GEMINI-API` 프로필과 Clarifying Questions 1건을 실제 로드하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,519 warnings / 0 notes`다. 직전 기록 12,594건에서 75건을 축소했으며 다음 고경고 단위는 `swarm_mode/orchestrator.py`(75)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 78 (2026-08-31)

- `swarm_mode/orchestrator.py`의 설정·워커 설정·상관분석 결과를 명시 타입과 mapping/list 변환 경계로 고정하고, 동적 워커 import·스레드 Future·백엔드 상태·CLI argparse 값을 안전하게 좁혔다. private 워커 런타임 속성은 동적 설정 경계로 제한했으며 출력 파일 작성과 실행 결과 반환값을 명시적으로 처리했다.
- 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. Samsung 상관분석 수동 스모크가 `review_portfolio`를 선택했고, 기본 워커 설정 조회와 CLI `--help`도 정상 동작했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,444 warnings / 0 notes`다. 직전 기록 12,519건에서 75건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 79 (2026-08-31)

- `src/antigravity_k/engine/curriculum_generator.py`의 Hugging Face dataset loader·dataset record·ModelManager를 Protocol로 분리하고 JSON/문자열/정수 변환 경계를 명시했다. SkillLibrary·DatasetIngestor·CurriculumGenerator 상태 속성과 파일 저장 반환값, optional 모델 URL 기본값을 고정해 동적 `Any` 전파를 제거했다.
- Curriculum 관련 회귀 `25 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 프로젝트에서 ModelManager 기반 synthetic challenge 생성과 SkillLibrary 저장/재로드 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 12,368 warnings / 0 notes`다. 직전 기록 12,444건에서 76건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 89 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_execution_handlers.py`의 MAX 실행 결과·파이프라인 분석·토론·AGI 런타임 경계를 Protocol/cast와 명시 타입으로 정리했다. MAX winner/analysis, pipeline steps, debate topic, AGI model/tool manager 라우팅 의미는 유지했다.
- Orchestrator/AgentRuntime 회귀 `42 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 MAX 결과를 통한 실행 핸들러 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,559 warnings / 0 notes`다. 직전 측정 11,648건에서 89건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tools/impact_analyzer.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 90 (2026-08-31)

- `src/antigravity_k/api/routes/chat.py`의 JSON 요청·메시지·스트림 응답·FastAPI 의존성·동적 세션/레지스트리 경계를 `JsonMap`/명시 helper/Annotated/cast로 정리했다. 검색·TDD·self-capability·slash·agent/native streaming과 reconnect 라우팅 의미는 유지했다.
- Chat API/AgentRuntime 회귀 `69 passed, 2 skipped`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 요청 검증, intent fallback, SSE payload/[DONE] 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,289 warnings / 0 notes`다. 직전 측정 11,355건에서 66건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/api/routes/git_api.py`와 `src/antigravity_k/engine/deterministic_worker.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 91 (2026-08-31)

- `src/antigravity_k/engine/api_cache.py`의 캐시 엔트리 값·비동기 factory·LRU/태그 인덱스·통계와 `@cached` decorator의 ParamSpec/Request 경계를 object/Awaitable/Protocol로 정리했다. TTL, tag invalidation, max-size eviction, sync/async endpoint caching 의미는 유지했다.
- API cache 회귀 `31 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. async factory 1회 생성, tag invalidation, LRU eviction, decorator hit 수동 스모크도 `PASS`다. 초기 스모크의 eviction 예상값은 기존 항목을 포함하지 않아 assertion이 실패했으나 구현 수정 없이 실제 통계(2회) 기준으로 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,209 warnings / 0 notes`다. 직전 측정 11,289건에서 80건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/api/routes/git_api.py`와 `src/antigravity_k/engine/deterministic_worker.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 92 (2026-08-31)

- `src/antigravity_k/engine/task_state_store.py`의 SQLite connection/contextmanager, Row 조회, DDL/마이그레이션 SQL, task/checkpoint/event 반환 경계를 Generator/cast/명시 타입으로 정리했다. 이 과정에서 Python 3.13에서 WAL PRAGMA cursor가 commit을 막는 회귀를 발견해 PRAGMA row를 즉시 소비하도록 수정했다.
- Task state/context/event 회귀 `21 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 SQLite에서 task transition, event sequence, reopen persistence 수동 스모크도 `PASS`다. 초기 통합 실행은 PRAGMA cursor 회귀로 `20 failed, 1 passed`였으나 수정 후 전부 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 11,143 warnings / 0 notes`다. 직전 측정 11,209건에서 66건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/api/routes/git_api.py`와 `src/antigravity_k/engine/deterministic_worker.py`다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 97 (2026-08-31)

- `src/antigravity_k/tools/media_gen_tools.py`의 이미지/오디오/비디오 생성 도구 kwargs·JSON 스키마·동적 Kokoro 모듈·subprocess/파일 반환 경계를 명시 타입, TypedDict, Protocol, cast, override/final로 정리했다. 생성 명령, 모델 다운로드 위치, 출력 경로와 실패 메시지 의미는 유지했으며 공통 `BaseTool.parameters_schema`를 Mapping 계약으로 넓혀 구체 스키마 접근성을 보존했다.
- 미디어 생성·도구 샌드박스 회귀 `11 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. mflux 이미지 명령 인자, 가짜 Kokoro 오디오 출력, 비디오 subprocess 스크립트 생성을 실제 호출 경계에서 확인하는 수동 스모크도 `PASS`다. 초기 스모크의 두 assertion은 테스트용 가짜 모듈 생성자/절대 경로 가정 오류였고 구현 수정 없이 올바른 경계로 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,825 warnings / 0 notes`다. 직전 측정 10,888건에서 63건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 98 (2026-08-31)

- `src/antigravity_k/engine/gbrain.py`의 선택적 ChromaDB/NetworkX 의존성, 그래프 속성, 벡터 query 결과, redact/clear/export 반환 경계를 Protocol/Mapping/Typed 변환 helper로 정리했다. ChromaDB private import 경로를 공개 모듈로 교정하고, 테스트가 주입하는 collection double의 `deleted` 계약을 보존하면서 그래프 저장·벡터 삭제·redaction 의미는 유지했다.
- GBrain/내구성 메모리/인지 복구 회귀 `32 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 저장소에서 노드·엣지 저장, related/export 조회, clear persistence를 실제 실행하는 수동 스모크도 `PASS`다. 전체 진단 중 테스트 double 주입 오류 3건이 발견되어 collection boundary helper로 조정한 뒤 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,761 warnings / 0 notes`다. 직전 측정 10,825건에서 64건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 99 (2026-08-31)

- `src/antigravity_k/engine/slash_commands_base.py`의 SlashCommand DTO, 다중상속 레지스트리 초기화, 기본 명령 등록/디스패치, 자연어 모델 라우팅 경계를 Protocol/cast와 명시 타입으로 정리했다. 기존 명령 카탈로그, lifecycle 충돌 회피, 런타임 바인딩, 자연어 실행 의미는 유지했다.
- 슬래시/역량/마켓플레이스 회귀 `98 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. `/help` 등록·완성·실행과 unknown command 처리를 실제 레지스트리로 확인하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,699 warnings / 0 notes`다. 직전 측정 10,761건에서 62건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 100 (2026-08-31)

- `src/antigravity_k/engine/tool_guardrail_manager.py`의 HarnessEnforcer·모드 권한·ToolCallGuardrailController 경계를 Protocol/TypedDict/object 타입과 명시 cast로 정리했다. 도구 전/후 체크 순서, 안전 기본 거부, 반복 호출 차단, 결과 기록·턴 리셋·실패 에스컬레이션 의미는 유지했다.
- 가드레일·하네스 스톨·ToolGuardrails·PlanGuard 회귀 `73 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 실제 HarnessEnforcer와 ToolCallGuardrailController를 연결해 반복 차단, 사후 기록, 리셋, 에스컬레이션을 확인하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,638 warnings / 0 notes`다. 직전 측정 10,699건에서 61건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 101 (2026-08-31)

- `src/antigravity_k/engine/scheduled_job_store.py`의 SQLite connection/contextmanager, cursor/Row 조회, DDL·마이그레이션 SQL, job/run 반환 경계를 Generator/Protocol/cast와 명시 타입으로 정리했다. WAL 설정, due claim, idempotency 저장, run 조회·삭제 의미는 유지했다.
- 검증 중 Python 3.13에서 WAL PRAGMA cursor가 commit을 막는 실제 회귀를 재현해 PRAGMA 결과를 즉시 소비하도록 수정했다. 스케줄·job/gateway/voice API 회귀 `17 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 SQLite에서 CRUD, due claim, idempotency run 저장·조회, 성공 output, 삭제를 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,578 warnings / 0 notes`다. 직전 측정 10,638건에서 60건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 102 (2026-08-31)

- `src/antigravity_k/engine/model_registry.py`의 YAML 동적 설정, 모델 프로필/기본값/메모리·서버 설정, 프로바이더 조회와 엔드포인트·캐시 경로 해석 경계를 정규화 helper와 명시 타입으로 정리했다. 모델 역할 병합, active artifact 등록, provider key/base URL 우선순위, legacy fallback 의미는 유지했다.
- 모델 레지스트리·모델 매니저·로컬 디스커버리 회귀 `86 passed`, 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 YAML에서 기본 모델·다중 역할·프로바이더 엔드포인트·캐시 경로를 실제 로드·조회하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 10,519 warnings / 0 notes`다. 직전 측정 10,578건에서 59건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 110 (2026-08-31)

- `src/antigravity_k/engine/vault.py`의 VaultEngine 상태·락·Git subprocess 오류 경계, YAML frontmatter, Wiki/RAG 동기화, redacted export 반환을 명시 타입·Protocol 호환 dict subclass·Mapping 변환으로 정리했다. 경로 traversal 방지, Git 자동 커밋/스냅샷, privacy restore, frontmatter 수평선 처리, Wiki 중복 갱신 의미는 유지했다.
- Vault·Vault API·privacy·Wiki mirror·memory compliance 회귀 `54 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 저장소에서 note write/read/search/export와 Git snapshot/restore를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,996 warnings / 0 notes`다. 직전 측정 10,053 warnings에서 57건을 축소했으며 다음 고경고 단위는 전체 경고 목록 재수집 후 결정한다. 전체 진단 중 `src/antigravity_k/engine/healing_loop.py`의 기존 부분 unknown 경고 1건은 남아 있다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 118 (2026-08-31)

- `tests/test_failure_classifier.py`의 분류 케이스·재시도 케이스·ToolExecutor 테스트 더블·Permission import·private 상태 접근 경계를 명시 타입, Path, Callable, cast helper로 정리했다. 실패 분류 우선순위, ToolExecutor 실패 기록/복구 카운터, ImmuneSystem escalation 검증 의미는 유지했다.
- FailureClassifier/RecoveryStrategy/ToolExecutor 회귀 `33 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·diff 검증을 통과했다. timeout 분류와 retryable recovery guidance 실제 호출 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,552 warnings / 0 notes`다. 직전 측정 9,618건에서 66건을 축소했으며 다음 고경고 단위는 `tests/test_rsi_family.py`(65), `tests/test_planning_and_rendering_quality.py`(64), `tests/test_approval_api.py`(63)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 117 (2026-08-31)

- `src/antigravity_k/engine/meta_architect.py`의 모델 매니저 Protocol 경계, JSON 이력·제안·판정 payload, 파일 목록/변경 내용, 샌드박스 검증 결과를 명시 타입과 Mapping/list 변환 helper로 정리했다. Ollama URL 기본값 지연 평가, managed model target 라우팅, 아키텍처 제안 파싱, self-reward judge 입력, API fallback 의미는 유지하면서 judge가 실제 원본·신규 코드를 평가하도록 입력 누락을 보완했다.
- MetaArchitect 회귀 `17 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 managed generation·proposal parsing·judge 결과를 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,618 warnings / 0 notes`다. 직전 측정 9,670건에서 52건을 축소했으며 다음 고경고 단위는 `tests/test_failure_classifier.py`(66), `tests/test_rsi_family.py`(65), `tests/test_planning_and_rendering_quality.py`(64)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 119 (2026-08-31)

- `tests/test_rsi_family.py`의 RSIEngine/Pseudo-LLM·RSISandbox 회귀 double, benchmark callback, dual-audit callback, snapshot/rollback 상태 접근을 명시 타입·Callable·cast helper로 정리했다. 사이클 수용·롤백·스킵, 변이 검증, 이중 감사, 안전 컨텍스트·감사 로그 영속화 의미는 유지했다.
- RSIEngine/RSISandbox 회귀 `28 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 샌드박스에서 AST 실패 단락, dual audit 단일 실행, safe mutation snapshot을 실제 실행하는 수동 스모크도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,487 warnings / 0 notes`다. 직전 측정 9,552건에서 65건을 축소했으며 다음 고경고 단위는 `tests/test_planning_and_rendering_quality.py`(64), `tests/test_approval_api.py`(63), `scripts/fix_d205.py`(62)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 120 (2026-08-31)

- `tests/test_planning_and_rendering_quality.py`의 fake model manager, planning guard 호출, quality gate 입력, skip 경로 callback을 명시 타입과 Callable/cast 경계로 정리했다. 단순 코딩 요청의 planning 생략, 대규모 리팩터링 guard, 코드 품질 등급, dashboard 스타일 회귀 의미는 유지했다.
- Planning/rendering quality 회귀 `4 passed, 1 skipped`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 planning guard와 QualityGate 등급을 실제 실행하는 수동 스모크도 `PASS`다. 최초 불완전 출력 스모크의 `QualityGrade.C`는 테스트 입력이 코드 설명 요건을 충족하지 않은 것으로, 완전한 계약 입력으로 재검증했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,423 warnings / 0 notes`다. 직전 측정 9,487건에서 64건을 축소했으며 다음 고경고 단위는 `tests/test_approval_api.py`(63), `scripts/fix_d205.py`(62), `tests/test_benchmark_metrics.py`(62)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 121 (2026-08-31)

- `tests/test_approval_api.py`의 FastAPI TestClient fixture, approval manager 대역, ApprovalRequest/Decision/Status 상태, JSON 응답 경계를 명시 타입과 MonkeyPatch로 정리했다. pending 조회, 단건 조회, approve/deny 오류, always-allowed 초기화 엔드포인트의 의미는 유지했다.
- Approval API 회귀 `8 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 router를 TestClient로 호출하는 pending/reset 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,360 warnings / 0 notes`다. 직전 측정 9,423건에서 63건을 축소했으며 다음 고경고 단위는 `scripts/fix_d205.py`(62), `tests/test_benchmark_metrics.py`(62), 이후 전체 경고 목록 순이다.
- `scripts/fix_d205.py`의 docstring pair 탐색, D205 변환, 파일 쓰기, CLI 인자 경계를 명시 타입과 cast로 정리했다. 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증과 임시 파일 변환/멱등성 수동 smoke를 통과했다. 기존 docstring·주석은 보존했으며 새 주석/억제 지시는 추가하지 않았다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 122 (2026-08-31)

- `tests/test_browser_tools.py`의 untyped `BrowserDOMTool.execute` 호출, Playwright 페이지 double, locator 결과, mock 호출 검증, side effect 경계를 명시 타입 helper와 `_PageDouble`/`_LocatorDouble`로 정리했다. goto/click/fill/extract/screenshot/close 및 Playwright 오류 회귀 의미는 유지했다.
- BrowserDOMTool 회귀 `20 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 도구의 필수 action 오류, unknown action, close 경로 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 9,174 warnings / 0 notes`다. 직전 측정 9,236건에서 62건을 축소했으며 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_korean_spell_check.py`(61), `.agent/skills/k-skill/korean-slang-writing/scripts/slang_search.py`(60), `tests/test_autonomous_learner.py`(60)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 139 (2026-08-31)

- `tests/test_benchmark_performance.py`의 타이머 컨텍스트, CodeTreeIndexer/FileSummarizer·Git diff 성능 호출, MaxModeEngine private helper, RAG 청킹·검색 호출을 명시 타입, 테스트 double, Callable/cast 경계로 정리했다. 벤치마크 측정 대상과 latency threshold·검색/선정 의미는 유지했다.
- 성능 회귀 `16 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 MaxModeEngine prompt와 RAGIndexer Python 청킹을 호출하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,392 warnings / 0 notes`다. 직전 측정 8,449건에서 57건을 축소했으며 다음 고경고 단위는 `tests/test_claude_deny_patterns.py`(56), `tests/test_local_rag_quality.py`(54), `src/antigravity_k/engine/rsi_engine.py`(53)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 140 (2026-08-31)

- `tests/test_claude_deny_patterns.py`의 pytest fixture/매개변수, settings JSON·permissions/marker 경계, deny 설치 결과 및 Path 반환을 명시 타입과 cast helper로 정리했다. deny 패턴 수집, legacy marker 회수, 재설치 멱등성, 안전/위험 커맨드 판정 의미는 유지했다.
- Claude deny 규칙 회귀 `14 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 규칙 설치·상태 조회·`rm -rf` 차단·`ls -la` 허용을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,336 warnings / 0 notes`다. 직전 측정 8,392건에서 56건을 축소했으며 다음 고경고 단위는 `tests/test_local_rag_quality.py`(54), `src/antigravity_k/engine/rsi_engine.py`(53), `src/antigravity_k/tui/app.py`(53)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 141 (2026-08-31)

- `tests/test_local_rag_quality.py`의 benchmark monkeypatch fixture, context-manager/indexer test double, RAG JSON payload, duplicate chunk ID 저장소와 파일 쓰기 경계를 명시 타입·Self·TracebackType·cast로 정리했다. 기본 engine scope, 품질 점수/신선도, fixture discoverability, heading ID 중복 방지 의미는 유지했다.
- Local RAG 품질 회귀 `6 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트에서 fixture audit와 실제 RAGIndexer 인덱싱의 중복 heading ID 정규화를 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,282 warnings / 0 notes`다. 직전 측정 8,336건에서 54건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/engine/rsi_engine.py`(53), `src/antigravity_k/tui/app.py`(53), `tests/test_cascade_escalation.py`(53)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 142 (2026-08-31)

- `src/antigravity_k/engine/rsi_engine.py`의 RSI cycle 결과 JSON 값, model-manager Protocol 경계, 지연 의존성 속성, evolution/diagnose/hypothesis 컬렉션, 비동기·아카이브 반환값을 명시 타입과 안전한 cast로 정리했다. 자기개선 단계·벤치마크·롤백·Meta-Architect/Self-Play 연동 의미는 유지했다. 호환되는 외부 manager 입력은 기존 object 경계를 유지하고 내부 의존성 생성 지점에서만 Protocol을 검증했다.
- RSI 회귀 `28 passed`, 변경 production/test 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 루트에서 diagnose→hypothesize→report 흐름을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,229 warnings / 0 notes`다. 직전 측정 8,282건에서 53건을 축소했으며 다음 고경고 단위는 `src/antigravity_k/tui/app.py`(53), `tests/test_cascade_escalation.py`(53), `tests/test_evolution_family_rest.py`(53)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 143 (2026-08-31)

- RSI phase 결과를 object 경계로 소비하는 기존 회귀 assertion을 명시 cast로 보완하고, benchmark/deny/local-RAG/RSI 네 단위의 통합 회귀·정적 검증을 재실행했다.
- 통합 회귀 `64 passed`, 변경 5개 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff와 diff 검증을 통과했다. 전체 basedpyright도 `0 errors / 8,229 warnings` 상태를 유지한다.
- 다음 잔여 단위는 `src/antigravity_k/tui/app.py`(53), `tests/test_cascade_escalation.py`(53), `tests/test_evolution_family_rest.py`(53) 순서로 진행한다. 사용자 변경 234건을 포함한 dirty worktree는 보존 중이다.

## Warning debt continuation 144 (2026-08-31)

- `src/antigravity_k/tui/app.py`의 Textual Screen/App 오버라이드, 화면·worker·App 제네릭 경계, 인스턴스 속성, 비동기/worker 반환값, slash registry 공개 completion API를 명시 타입·override·cast·결과 할당으로 정리했다. TUI 시작 화면, welcome 메시지, 도움말 push, slash 입력·취소·종료 동작은 유지했다.
- TUI 회귀 `6 passed`, 변경 파일 basedpyright/LSP 진단 `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 표준 터미널 크기에서 startup focus, welcome 렌더링, HelpScreen 표시/닫기 영역을 실제 `run_test` smoke로 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 8,176 warnings / 0 notes`다. 직전 측정 8,229건에서 53건을 축소했으며 다음 고경고 단위는 `tests/test_cascade_escalation.py`(53), `tests/test_evolution_family_rest.py`(53), `src/antigravity_k/engine/orchestrator/agent.py`(52) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 149 (2026-08-31)

- 이번 연속 작업에서는 `src/antigravity_k/engine/orchestrator/agent.py`와 `src/antigravity_k/engine/orchestrator_analysis_handlers.py`를 순서대로 점검했다. 모델·설정·도구 스키마·메시지·지연 초기화·CEO 스트림·불확실성·사용자 모델·라우팅 경계를 Protocol, Mapping/Sequence, 안전한 변환 helper와 명시적 결과 소비로 정리했다.
- 오케스트레이터 관련 회귀 `38 passed, 2 skipped`와 두 파일의 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 실제 agent 초기화/프롬프트 준비와 CEO 스트림→WORKER 라우팅 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,954 warnings / 0 notes`다. 직전 측정 8,070건 대비 이번 연속 작업에서 116건을 축소했으며, 다음 단위는 전체 경고 상위인 `src/antigravity_k/tools/memory_tools.py`, `src/antigravity_k/tools/config_editor_tool.py`, `src/antigravity_k/engine/artifact_engine.py` 순으로 진행한다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 150 (2026-08-31)

- `src/antigravity_k/tools/memory_tools.py`의 Store/Search Knowledge 도구에 `BaseTool` override 계약, 클래스·인스턴스 속성, VectorStore Protocol, object 기반 kwargs 변환을 명시했다. knowledge text·tags·query·max_results의 경계 정규화와 lazy VectorStore 재사용은 유지했다.
- RAG·메모리 회귀 `38 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 VectorStore로 knowledge 저장 후 검색 결과를 확인하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,903 warnings / 0 notes`다. 직전 측정 7,954건에서 51건을 축소했으며, 다음 단위는 `src/antigravity_k/tools/config_editor_tool.py`와 이후 전체 경고 목록 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 160 (2026-08-31)

- `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`의 JSON/CLI 경계를 재귀 `JsonValue`, `TypedDict`, `Protocol`, 명시적 `cast`로 정리하고 argparse 반환값·정리 후보·agent usage source의 타입과 미사용 Action 결과를 구체화했다. 스킬 디렉터리 탐색, JSONL/usage JSON 병합, 시간창 필터, 후보 점수화, 파일 미삭제 안전 경계는 유지했다.
- cleaner 정적 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 스킬 루트와 JSONL에서 alpha 사용량·beta never-use 후보를 생성하고 `No files were deleted` 안전 문구를 확인하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,393 warnings / 0 notes`다. 직전 측정 7,443건에서 50건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49), `src/antigravity_k/agents/base_agent.py`(49), `src/antigravity_k/engine/audit_logger.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 151 (2026-08-31)

- `src/antigravity_k/tools/config_editor_tool.py`의 BaseTool 메타데이터, YAML 모듈 경계, `config.yaml` 모델·agent map·swarm combo 변환을 명시 타입·Protocol·안전한 object 변환 helper로 정리했다. add/remove/update_agent_map/update_swarm 의미와 기존 오류 응답은 유지했다.
- 설정 편집 회귀 `15 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 config에서 모델 추가·agent 매핑·swarm 갱신·모델 제거 후 YAML 재로딩을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,852 warnings / 0 notes`다. 직전 측정 7,903건에서 51건을 축소했으며, 다음 고경고 제품 코드 단위는 `src/antigravity_k/engine/artifact_engine.py`(51)다. 현재 변경 파일 집합에는 diff 오류가 없다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 152 (2026-08-31)

- `src/antigravity_k/engine/artifact_engine.py`의 Plan/Artifact/Kanban 결과를 TypedDict로 구체화하고, 엔진·중첩 WriteArtifactTool의 메타데이터·레지스트리 Protocol·오버라이드·파일 쓰기 반환값을 명시했다. `plan_to_build.py`의 ArtifactEnginePort도 실제 Kanban 결과 Mapping 경계에 맞춰 조정했다.
- 아티팩트·통합·주간 E2E 회귀 `132 passed`, 변경 파일 2개 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 계획 아티팩트 CRUD·검증·태스크 추출·레지스트리 등록 실제 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,799 warnings / 0 notes`다. 직전 측정 7,903건에서 이번 연속 작업(메모리 도구·설정 편집·아티팩트 엔진 포함)으로 104건을 축소했으며, 다음 고경고 제품 코드 단위는 `src/antigravity_k/agents/browser_surfing_agent.py`(50)와 `src/antigravity_k/api/routes/agent_tools.py`(50)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 153 (2026-08-31)

- `src/antigravity_k/agents/browser_surfing_agent.py`의 Playwright·Page·Browser·모델 매니저 Protocol 경계를 명시하고, 비동기 응답·JSON action payload·스크린샷/DOM 결과를 안전하게 정규화했다. 브라우저 lifecycle, click/scroll/extract/done 분기와 오류 폴백 의미는 유지했다.
- 브라우저 서핑 회귀 `3 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 Playwright로 URL 이동·스크린샷·mock extract 흐름을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,750 warnings / 0 notes`다. 직전 측정 7,799건에서 49건을 축소했으며, 다음 고경고 제품 코드 단위는 `src/antigravity_k/api/routes/agent_tools.py`(50)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 160 (2026-08-31)

- `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`의 JSON/CLI 경계를 재귀 `JsonValue`, `TypedDict`, `Protocol`, 명시적 `cast`로 정리하고 argparse 반환값·정리 후보·agent usage source의 타입과 미사용 Action 결과를 구체화했다. 스킬 디렉터리 탐색, JSONL/usage JSON 병합, 시간창 필터, 후보 점수화, 파일 미삭제 안전 경계는 유지했다.
- cleaner 정적 진단 `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 임시 스킬 루트와 JSONL에서 alpha 사용량·beta never-use 후보를 생성하고 `No files were deleted` 안전 문구를 확인하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,393 warnings / 0 notes`다. 직전 측정 7,443건에서 50건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49), `src/antigravity_k/agents/base_agent.py`(49), `src/antigravity_k/engine/audit_logger.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 154 (2026-08-31)

- `src/antigravity_k/api/routes/agent_tools.py`의 Playwright route/page/accessibility Protocol 경계, egress·permission 인자, 프로젝트 경로, 파일 쓰기 결과, self-test 요청 기본값, Ollama JSON 응답을 명시 타입·안전한 Mapping 변환·결과 소비로 정리했다. 브라우저 launch/goto/click/type/snapshot/console 오류, 자율 QA, 외부 brain, TDD 라우트 의미는 유지했다.
- API 도구 회귀 `19 passed`(약 62초), 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 접근성 트리 렌더링과 file URL 차단/HTTPS 허용 route guard 실제 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,700 warnings / 0 notes`다. 직전 측정 7,750건에서 50건을 축소했으며, 다음 고경고 단위는 `tests/test_git_api_boundary.py`(52), `tests/test_model_manager_generate.py`(52)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 155 (2026-08-31)

- `tests/test_git_api_boundary.py`의 Git 작업 디렉터리·저장소 파일 경계 테스트에 Path/MonkeyPatch/Protocol/완료 결과 타입, `getattr` 기반 private helper 접근, 권한 거부 테스트 double을 명시했다. 프로젝트 루트 밖 cwd/file escape 차단과 commit 권한 거부 전 subprocess 차단 의미는 유지했다.
- Git 경계 회귀 `4 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 임시 프로젝트 루트에서 외부 cwd 403 차단을 직접 실행하는 수동 boundary smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,648 warnings / 0 notes`다. 직전 측정 7,700건에서 52건을 축소했으며, 다음 단위는 `tests/test_model_manager_generate.py`(52)다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 156 (2026-08-31)

- `tests/test_model_manager_generate.py`의 ModelRegistry/ModelManager fixture double, fallback·stream·trace 콜백, private model-manager 훅과 provider shim 접근을 Callable/Protocol/cast 및 명시적 결과 소비로 정리했다. 단일 모델 생성, fallback/집단지성 라우팅, Qwen thinking 제어, MLX/LM Studio 로더 의미는 유지했다.
- 모델 생성·라우팅 회귀 `15 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. fixture 기반 실제 `ModelManager.generate`/`stream_generate`와 tracer/fallback 경로가 테스트 런타임에서 동작하는 것을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,596 warnings / 0 notes`다. 직전 측정 7,648건에서 52건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_subway_lost_property.py`(51), `tests/test_agent_program_creation.py`(51), `tests/test_ambient_watchdog.py`(51) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 157 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_subway_lost_property.py`의 동적 helper import 경계를 SearchQuery/SearchPlan Protocol, Callable/cast와 명시적 JSON/command 타입으로 정리했다. LOST112/서울교통공사 검색 계획, curl 옵션, reachability/timeout probe, CLI JSON 출력 및 실행 가능 엔트리포인트 검증 의미는 유지했다.
- 유실물 helper 회귀 `8 tests OK`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 지원되는 스킬 디렉터리 `PYTHONPATH`에서 CLI 테스트를 실제 실행해 8개 테스트가 모두 통과하는 것을 확인했다. 저장소 루트 직접 실행 시 `scripts` 모듈 경로가 없어지는 동작은 코드 결함이 아닌 실행 경로 제약으로 분리 기록했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,545 warnings / 0 notes`다. 직전 측정 7,596건에서 51건을 축소했으며, 다음 고경고 단위는 `tests/test_agent_program_creation.py`(51), `tests/test_ambient_watchdog.py`(51), `.agent/skills/k-skill/k-skill-cleaner/scripts/k_skill_cleaner.py`(50) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 161 (2026-08-31)

- 다음 우선순위는 `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`(49), `src/antigravity_k/agents/base_agent.py`(49), `src/antigravity_k/engine/audit_logger.py`(49) 순으로 이어간다. 현재 cleaner 단위의 타입·안전 경계는 완료했으며, 전역 경고 기준선은 오류 없이 7,393건이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않고, 전역 경고 억제 지시문 없이 파일별 경고를 순서대로 제거한다.

## Warning debt continuation 162 (2026-08-31)

- `.agent/skills/k-skill/naver-blog-research/scripts/naver_download_images.py`의 동적 `_naver_http` 모듈·urlopen 응답·다운로드 결과·ThreadPool future·CLI argparse와 stdin JSON 경계를 `Protocol`, `TypedDict`, 재귀 `JsonValue`, 명시적 `cast`로 정리했다. Naver CDN 도메인 검증, SSL 옵션 전달, 이미지 확장자 추론, 병렬 다운로드 순서 보장, 출력 경로 탈출 차단, stdin/CLI 오류 의미는 유지했다.
- 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 Naver 응답으로 PNG 저장·병렬 성공/실패 집계·출력 경로 탈출 차단·확장자 추론을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,344 warnings / 0 notes`다. 직전 측정 7,393건에서 49건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/agents/base_agent.py`(49), `src/antigravity_k/engine/audit_logger.py`(49), `src/antigravity_k/engine/autonomous_learner.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 163 (2026-08-31)

- `src/antigravity_k/agents/base_agent.py`의 기본 속성·메시지 이력, 모델 manager/router/loaded model/tokenizer, 동적 `mlx_lm.generate`, JSON tool-call payload와 callable 도구 경계를 `Protocol`, `TypedDict`, 재귀 `JsonValue`, 명시적 결과 변환으로 정리했다. mock 모드, combo 사전 로드, 최대 반복 수, tool-call 재실행, 오류 응답과 Hermes/i18n 프롬프트 의미는 유지했다.
- BaseAgent·AgentFabric 회귀 `22 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·diff 검증을 통과했다. 가짜 manager/router/tool로 tool-call→응답 재귀와 mock 실행을 실제 확인하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,295 warnings / 0 notes`다. 직전 측정 7,344건에서 49건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/audit_logger.py`(49), `src/antigravity_k/engine/autonomous_learner.py`(49), `tests/test_event_bus.py`(49) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 164 (2026-08-31)

- `src/antigravity_k/engine/audit_logger.py`의 OCSF builder 이벤트와 legacy log payload를 `TypedDict`, `Mapping`, `Self`, `Final`, 명시적 `cast`로 정리하고 민감정보 마스킹·JSONL/SQLite dual-sync 경계를 유지했다. 테스트에서 반환된 구조화 payload를 명시적으로 캐스팅해 정적 인덱싱 오류도 제거했다.
- 감사 로거 회귀 `3 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. SQLite 미초기화 fallback, 중첩·리스트 민감정보 마스킹, OCSF activity/unmapped payload를 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,245 warnings / 0 notes`다. 직전 측정 7,295건에서 50건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/autonomous_learner.py`(49), `tests/test_event_bus.py`(49), `src/antigravity_k/engine/skill_generator.py`(48) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 165 (2026-08-31)

- `src/antigravity_k/engine/autonomous_learner.py`의 model manager·KI 저장소·웹 검색 결과 경계를 Protocol과 명시적 JSON 변환 helper로 정리하고, LLM 응답 파싱·키워드 폴백·비동기 검색/서핑/요약 파이프라인의 반환 타입을 구체화했다. 기존 model target 선택, 검색 결과 수집, KI 저장 및 이벤트 흐름은 유지했다.
- 자율 학습 회귀 `11 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 가짜 검색 응답·서핑·KI 저장소로 실제 auto-learn pipeline과 managed-model 분석 폴백을 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,196 warnings / 0 notes`다. 직전 측정 7,245건에서 49건을 축소했으며, 다음 고경고 단위는 `tests/test_event_bus.py`(49), `src/antigravity_k/engine/skill_generator.py`(48), `tests/test_command_execution_boundary.py`(48) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 166 (2026-08-31)

- `src/antigravity_k/engine/event_bus.py`의 sync/async callback, publish kwargs, asyncio task, persistent-agency 및 HookEventBus 양방향 브리지 경계를 Protocol·Coroutine·Mapping으로 정리했다. callback 실패 격리, 중복 구독 방지, 동기/비동기 전달, 영속 이벤트 연결 동작은 유지했다.
- EventBus 회귀 `35 passed`, 변경 소스와 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다. 동기·비동기 publish, callback 오류 격리, persistent-agency idempotent 연결을 실제 실행하는 수동 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 7,106 warnings / 0 notes`다. 직전 측정 7,196건에서 90건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/skill_generator.py`(48), `tests/test_command_execution_boundary.py`(48), `tests/test_multiplexer.py`(48) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 169 (2026-08-31)

- 이번 연속 점검에서 `skill_generator.py`와 `tests/test_skill_generator.py`의 model manager·JSON·파일 승인 경계를 타입 안전하게 정리하고, 신규 프로젝트에서 승인 대상 tools 디렉터리를 자동 생성하도록 보완했다. 이어 `tests/test_command_execution_boundary.py`의 Permission import, pytest fixture, sandbox/provider 콜백, registry 설치 및 execution permit 경계를 명시적 타입으로 정리했다.
- 스킬 생성기 회귀 `13 passed`, 명령 실행 경계 회귀 `5 passed`, 두 단위의 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증 및 스킬 생성→승인 smoke `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,966 warnings / 0 notes`다. 직전 기록 7,106건에서 140건을 축소했으며, 다음 고경고 단위는 `tests/test_multiplexer.py`(48), `tests/test_task_benchmark.py`(48), `.agent/skills/k-skill/joseon-sillok-search/scripts/sillok_search.py`(47) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 170 (2026-08-31)

- `tests/test_multiplexer.py`의 fixture·결과 map·GoalRunner/runner 동적 mock·private 실행 메서드 경계를 `Iterator`, `Callable`, `Awaitable`, `cast` 및 명시적 mock 헬퍼로 정리했다. 빈 fan-out, 최대 fan-out 거부, 단일·병렬·자동 task 실행, runner 실패 격리, workspace 전달, bound runtime 경로 검증은 유지했다.
- Multiplexer 회귀 `11 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,918 warnings / 0 notes`다. 직전 측정 6,966건에서 48건을 축소했으며, 다음 고경고 단위는 `tests/test_task_benchmark.py`(48), `.agent/skills/k-skill/joseon-sillok-search/scripts/sillok_search.py`(47), `src/antigravity_k/engine/goal_runner.py`(47) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 171 (2026-08-31)

- `tests/test_task_benchmark.py`의 임시 경로·모델 매니저·outcome recorder·캘리브레이션 updater·JSON artifact 경계를 `Path`, Protocol, 명시적 `cast` 및 typed callback으로 정리했다. task outcome 영속화/재로딩, 비교표, runner·tool loop sink 연결, 명시적 benchmark calibration, threshold 및 artifact export 검증은 유지했다.
- Task Benchmark 회귀 `11 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,870 warnings / 0 notes`다. 직전 측정 6,918건에서 48건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/joseon-sillok-search/scripts/sillok_search.py`(47), `src/antigravity_k/engine/goal_runner.py`(47), `tests/test_gate_pipeline.py`(47) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 172 (2026-08-31)

- `.agent/skills/k-skill/joseon-sillok-search/scripts/sillok_search.py`의 선택적 requests 클라이언트·urllib opener·응답 객체·정규식 결과·CLI Namespace 경계를 Protocol과 명시적 타입으로 정리했다. 검색/상세 페이지 파싱, 왕명·연도 필터, requests 실패 시 urllib fallback, 검색 결과 직렬화 및 CLI 동작은 유지했다. 기존 type-ignore 주석도 제거했다.
- Sillok 검색 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했다. 샘플 HTML로 검색 결과·왕년대 변환·상세 본문·분류·CLI 인자 파싱을 실행하는 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,823 warnings / 0 notes`다. 직전 측정 6,870건에서 47건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/goal_runner.py`(47), `tests/test_gate_pipeline.py`(47), `tests/test_memory_operations.py`(47) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 175 (2026-08-31)

- `tests/test_memory_operations.py`의 MemoryProvider override, API TestClient fixture 및 fake manager 호출 경계를 명시 타입과 `_CallSpy` 테스트 더블로 정리했다. 메모리 삭제·랭킹·top_k clamp API 및 project/global/episodic/provider 라우팅 동작은 유지했다.
- Memory Operations 회귀 `11 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,678 warnings / 0 notes`다. 직전 측정 6,725건에서 47건을 축소했으며, 다음 고경고 단위는 `tests/test_confidence_evaluator.py`(46), `tests/test_integration_upgrade.py`(45), `src/antigravity_k/engine/orchestrator_memory_handler.py`(44) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 176 (2026-08-31)

- `tests/test_confidence_evaluator.py`의 ModelRegistry 설정·프로필 조회와 ModelManager 보호 메서드 mock 경계를 명시 타입, `setattr`, `cast` helper로 정리했다. confidence evaluator 선택, cascade escalation, Ollama stream 및 heuristic fallback 시나리오는 유지했다.
- Confidence Evaluator 회귀 `7 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,632 warnings / 0 notes`다. 직전 측정 6,678건에서 46건을 축소했으며, 다음 고경고 단위는 `tests/test_integration_upgrade.py`(45), `src/antigravity_k/engine/orchestrator_memory_handler.py`(44), `src/antigravity_k/engine/subagent_spawner.py`(44) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 185 (2026-08-31)

- `src/antigravity_k/engine/skill_publisher.py`의 패키지 JSON·YAML frontmatter 경계를 재귀 `JsonValue` 타입과 명시적 mapping 변환으로 정리하고, 파일 복사·쓰기·subprocess 결과의 의도적 무시를 명시했다. publish/npm/GitHub dry-run 동작은 변경하지 않았다.
- `tests/test_skill_publisher.py`의 private 메서드 호출을 typed `getattr` helper로 감싸고, JSON 중첩 구조·파일 쓰기·pytest fixture 경계를 명시 타입으로 정리했다. Skill Publisher 회귀 `28 passed`, 변경 소스·테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 및 `git diff --check`를 통과했다. 임시 프로젝트에서 `publish_to_npm(..., dry_run=True)`를 실행하는 smoke도 `PASS`다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,081 warnings / 0 notes`다. 직전 기준선 6,632건 대비 551건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/state_graph.py`(42), `src/antigravity_k/agents/kanban.py`(41), `tests/test_autonomous_capabilities.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 186 (2026-08-31)

- `src/antigravity_k/engine/state_graph.py`의 StateContext 분석·이력·체크포인트 타입과 실행 orchestrator 경계를 `object`/재귀 JSON 타입으로 명시하고, 상태 이벤트·그래프 빌더의 의도적 반환값 무시를 표시했다. Generator 스트리밍 semantics와 기본 상태 전이는 유지했다.
- State Graph 관련 회귀 `38 passed`, 변경 소스·영향 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·그래프 전이 smoke를 통과했다. 분석 딕셔너리 타입 축소로 영향받은 `tests/test_integration_rag_cov.py`, `tests/test_multi_part_routing.py`의 중첩 JSON 경계도 함께 보강했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 6,032 warnings / 0 notes`다. 직전 기록 6,081건에서 49건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/agents/kanban.py`(41), `tests/test_autonomous_capabilities.py`(41), `tests/test_external_brain.py`(41) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 stage·revert하지 않으며, 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 188 (2026-08-31)

- `tests/test_external_brain.py`의 동적 `MagicMock` 어댑터 멤버를 typed `getattr`/`AsyncMock` 경계로 감싸고, 응답 side-effect와 fixture 파라미터 타입을 명시했다. 라우터의 target/fallback/round-robin/compare 전략 동작은 변경하지 않았다.
- External Brain 회귀 `27 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다.

## Warning debt continuation 189 (2026-08-31)

- `tests/test_web_search_candidate_augmentation.py`의 MonkeyPatch 동적 메서드와 fallback/cache/content 콜백을 명시적 callable 타입과 공통 patch helper로 정리했다. 비동기 Jina 후보 보강, 공식 Qwen 소스 보존, 동기 rescue 승격 시나리오는 변경하지 않았다.
- Web Search Candidate Augmentation 회귀 `5 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다.

## Warning debt continuation 190 (2026-08-31)

- External Brain 및 Web Search Candidate Augmentation 변경 이후 전체 basedpyright를 재실행해 `864 files / 0 errors / 5,868 warnings / 0 notes`를 확인했다. 직전 기준선 5,950건에서 82건을 축소했다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-web-search.log`에 보관했으며, 변경 파일 `git diff --check`도 통과했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다.

## Warning debt continuation 191 (2026-08-31)

- `src/antigravity_k/engine/self_capability.py`의 ToolRegistry·SkillLoader·ModelManager 경계를 Protocol과 `Mapping[str, object]`로 명시하고, 재귀적 Any 의존·deprecated typing import·동적 model lookup 및 문자열 결합 경고를 제거했다. 런타임 capability snapshot/render 계약은 유지했다.
- Self Capability 회귀 `3 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다.

## Warning debt continuation 192 (2026-08-31)

- `.agent/skills/k-skill/mfds-drug-safety/scripts/mfds_drug_safety.py`의 CLI·HTTP 응답·JSON 정규화 경계를 Protocol과 명시적 `object` 변환으로 정리했다. Python 3.9에서 실행 가능한 타입 별칭으로 조정하고, MFDS interview/lookup/정규화 동작은 유지했다. MFDS 회귀 `5 passed`, basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·인터뷰 스모크를 통과했다.
- `.agent/skills/k-skill/korean-patent-search/scripts/patent_search.py`의 XML parser·KIPRIS 응답·CLI Namespace·urlopen 경계를 Protocol, `cast`, 명시적 타입으로 정리했다. 검색/상세 파싱과 서비스 키 오류 경로는 유지했다. basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일·샘플 XML 파서 스모크 및 서비스 키 누락 CLI 스모크를 통과했다.
- `src/antigravity_k/tools/system_control.py`의 psutil·GPU/Ollama JSON·YAML 설정·프로세스 정보 경계를 Protocol과 명시적 변환 helper로 정리했다. 시스템 정보 수집, 환경 최적화, 앱/클립보드/볼륨 제어 semantics는 유지했다. System Control 회귀 `65 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff 검증을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,708 warnings / 0 notes`다. 직전 기준선 5,790건에서 82건을 축소했으며, 다음 고경고 단위는 `tests/test_sandbox_isolation.py`(40), `tests/test_vault_privacy_api.py`(40), `src/antigravity_k/tools/system_control.py`에서 제거된 40건 다음으로 `.agent/skills/k-skill/corporate-registration-consulting/scripts/fill_official_hwp.py`(39), `src/antigravity_k/engine/tracing.py`(39) 순이다.
- 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 193 (2026-08-31)

- `src/antigravity_k/tools/system_control.py`의 psutil·GPU/Ollama JSON·YAML 설정·프로세스 정보 경계를 Protocol과 명시적 변환 helper로 정리했다. `tests/test_system_control.py`의 중첩 schema 경계도 함께 보강해 타입 구체화로 발생한 정적 오류를 해소했다. System Control 회귀와 영향 테스트 `83 passed`, 변경 파일 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다.
- `tests/test_sandbox_isolation.py`의 private SandboxRunner 호출, pytest `tmp_path`, socket 주소/accept 결과, monkeypatch 콜백을 typed helper와 명시적 `cast`로 정리했다. deny-default/network/write-whitelist/cwd confinement 시나리오 회귀 `18 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,628 warnings / 0 notes`다. 직전 5,708건 기준선에서 80건을 축소했으며, 다음 고경고 단위는 `tests/test_vault_privacy_api.py`(40), `.agent/skills/k-skill/corporate-registration-consulting/scripts/fill_official_hwp.py`(39), `src/antigravity_k/engine/tracing.py`(39) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-sandbox-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 194 (2026-08-31)

- `tests/test_vault_privacy_api.py`의 Vault privacy contracts import, API JSON payload, subprocess 결과, MagicMock 동적 메서드 및 derivative callback 경계를 `Protocol`, 명시적 `cast`, typed mock helper로 정리했다. redaction/purge/restore, Git rollback, RAG·Wiki derivative 정합성 동작은 유지했다. Vault Privacy API 회귀 `8 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,588 warnings / 0 notes`다. 직전 기준선 5,628건에서 40건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/corporate-registration-consulting/scripts/fill_official_hwp.py`(39), `src/antigravity_k/engine/tracing.py`(39), `src/antigravity_k/tools/browser_subagent_tool.py`(39) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-vault-privacy.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 195 (2026-08-31)

- `.agent/skills/k-skill/corporate-registration-consulting/scripts/fill_official_hwp.py`의 JSON 매핑·문자열 변환·HWP cell spec·argparse Namespace 경계를 `JsonMap`, 명시적 `object` 변환, Protocol과 `cast`로 정리했다. 공식 양식 복사, 순차 cell 작성, 기본값 처리, CLI 출력 semantics는 유지했다. 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증과 임시 HWP/매핑 기반 fill helper smoke `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,549 warnings / 0 notes`다. 직전 기준선 5,588건에서 39건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/tracing.py`(39), `src/antigravity_k/tools/browser_subagent_tool.py`(39), `.agent/skills/k-skill/scripts/test_mfds_food_safety.py`(38) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-hwp.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 196 (2026-08-31)

- `src/antigravity_k/engine/tracing.py`의 Span·Trace·AgentTracer JSON 경계, tracer decorator의 동기·비동기 callable 경계, 파일 persistence 결과를 명시적 `JsonMap`/`object` 타입과 `cast`로 정리했다. 기존 trace/span 집계, JSONL export, max-traces 정책과 decorator semantics는 유지했다. Tracing 회귀 `29 passed`, 변경 소스·테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했으며 동기·비동기 decorator를 함께 실행하는 smoke도 `PASS`다.
- `src/antigravity_k/tools/browser_subagent_tool.py`의 class metadata·생성자·kwargs·parameters schema를 명시 타입으로 정리하고, 보호된 `_get_model_for_role` 대신 공개 `get_model_for_role` API를 사용하도록 개선했다. ModelManager 미연결 폴백과 subagent stream 호출 semantics는 유지했다. 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 관련 subagent execution 회귀 `2 passed`, 폴백 실행 smoke `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,447 warnings / 0 notes`다. 직전 기준선 5,549건에서 102건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_mfds_food_safety.py`(38), `src/antigravity_k/engine/provider_adapters/openai_adapter.py`(38), `src/antigravity_k/tools/wiki_export_tool.py`(38) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-browser-subagent.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 197 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_mfds_food_safety.py`의 동적 `importlib` 함수 로딩, 식품 인터뷰/정규화 payload, 필터 입력, proxy request callback 경계를 Protocol·TypedDict·`Payload`와 명시적 `cast`로 정리했다. 공식 식품 리콜·부적합 식품 정규화, 검색 우선순위, proxy URL 검증 및 URL query 생성 semantics는 유지했다. 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·컴파일 검증을 통과했으며 패키지 표준 실행(`PYTHONPATH=.:scripts python -m unittest scripts.test_mfds_food_safety`)에서 `6 tests OK`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,409 warnings / 0 notes`다. 직전 기준선 5,447건에서 38건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/provider_adapters/openai_adapter.py`(38), `src/antigravity_k/tools/wiki_export_tool.py`(38), `tests/test_meta_evolution_agent.py`(38) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-mfds-food-test.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 198 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/openai_adapter.py`의 Anthropic↔OpenAI 요청·응답·tool call·stream payload 경계를 재귀 `JsonObject`와 명시적 `object` 변환 helper로 정리하고 override 계약을 명시했다. system/content list, tool schema, empty choices, tool call arguments 복원 semantics는 유지했다. 변경 소스·영향 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, OpenAI/Base adapter 회귀 `14 passed`, 멀티모달·tool call translation smoke `PASS`를 확인했다.
- 타입 구체화로 영향받은 `tests/test_openai_adapter.py`의 payload와 nested response assertions를 `JsonObject` 및 typed extraction helper로 보강했다. 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff 및 `git diff --check`를 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,371 warnings / 0 notes`다. 직전 기준선 5,409건에서 38건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/wiki_export_tool.py`(38), `tests/test_meta_evolution_agent.py`(38), `src/antigravity_k/agents/meta_evolution_agent.py`(37) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-openai-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 199 (2026-08-31)

- `src/antigravity_k/tools/wiki_export_tool.py`의 Tool metadata·schema·kwargs, YAML config 로딩, tag/content 문자열 변환 및 파일 쓰기 결과를 명시 타입과 `Mapping`/`cast` 경계로 정리했다. 기본 wiki_exports 생성, configured `wiki_dir`, 날짜 prefix, YAML frontmatter 및 permission fallback semantics는 유지했다. 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, Wiki Export 회귀 `18 passed`, 임시 디렉터리 export smoke `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,333 warnings / 0 notes`다. 직전 기준선 5,371건에서 38건을 축소했으며, 다음 고경고 단위는 `tests/test_meta_evolution_agent.py`(38), `src/antigravity_k/agents/meta_evolution_agent.py`(37), `src/antigravity_k/tools/artifact_tools.py`(37) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-wiki-export.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 200 (2026-08-31)

- `tests/test_meta_evolution_agent.py`의 pytest fixture 경계와 동적 `MagicMock` model/tool doubles를 명시적인 `Path` tuple, model response Protocol, typed fake executor로 교체했다. BackupManager snapshot/rollback과 MetaEvolution failure rollback 검증 semantics는 유지했다. 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 회귀 `2 passed`를 확인했다.
- `src/antigravity_k/agents/meta_evolution_agent.py`의 BackupManager 경로·copy 결과, model manager/tool executor constructor 경계, JSON tool-call 파싱, documentation write 결과를 Protocol·`JsonObject`·명시적 `cast`로 정리했다. 기존 evolve retry/rollback/documentation semantics는 유지했으며, 영향 테스트와 source basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,258 warnings / 0 notes`다. 직전 기준선 5,295건에서 37건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/artifact_tools.py`(37), `tests/test_local_agent_task.py`(37), `tests/test_mcp_tool_loader.py`(37) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-meta-evolution-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 201 (2026-08-31)

- `src/antigravity_k/tools/artifact_tools.py`의 artifact tool metadata·schema·kwargs·파일 쓰기 경계를 `JsonMap`, `Mapping`, `Protocol`, 명시적 `cast`와 변환 helper로 정리했다. HTML/Markdown/JSON artifact 생성, 기본 `artifacts` 경로와 metadata 반환 semantics는 유지했다. 관련 feature/event/artifact 회귀 `65 passed`, 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff 및 임시 artifact 생성 smoke `PASS`를 확인했다.
- 타입 구체화로 영향받은 `tests/test_new_features.py`의 WriteArtifact/CoworkDelegate 동적 execute 호출을 `_ExecutableTool` Protocol과 명시적 `cast`로 보강했다. 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 회귀 `2 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,215 warnings / 0 notes`다. 직전 기준선 5,258건에서 43건을 축소했으며, 다음 고경고 단위는 `tests/test_local_agent_task.py`(37), `tests/test_mcp_tool_loader.py`(37), `.agent/skills/k-skill/korean-slang-writing/scripts/slang_lookup.py`(36) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-artifact-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 202 (2026-08-31)

- `tests/test_local_agent_task.py`의 task result Any 접근, callable 매개변수 미명시, dict 결과 인덱싱을 typed `_task_result`/`cast`와 구체적인 callable annotation으로 정리했다. LocalAgentTask 상태 전이·실패 캡처·thread join semantics는 유지했다. 회귀 `23 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다.
- `tests/test_mcp_tool_loader.py`의 private helper import, dynamic Mock annotation/logger, skill registry protected access, JSON load Any 및 미사용 반환값 경계를 typed wrapper·Protocol-like doubles·명시적 `cast`로 정리했다. MCP transport/risk/timeout normalization, skill server registration, config generation, MCPTool metadata semantics는 유지했다. 회귀 `56 passed`, 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,141 warnings / 0 notes`다. 직전 기준선 5,215건에서 74건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/korean-slang-writing/scripts/slang_lookup.py`(36), `src/antigravity_k/api/routes/kanban_api.py`(36), `src/antigravity_k/engine/tool_guardrails.py`(36) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-mcp-loader-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 203 (2026-08-31)

- `.agent/skills/k-skill/korean-slang-writing/scripts/slang_lookup.py`의 동적 `_slang_http` 모듈, 문자열 결합 정규식, JSON 결과 payload, argparse Namespace와 stdout 호출 경계를 Protocol·`JsonObject`·명시적 `cast`로 정리했다. Namu Wiki URL/HTML title·summary 추출 및 blocked/not-found/upstream 오류 분기 semantics는 유지했다. 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·py_compile 및 HTML extraction smoke `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,105 warnings / 0 notes`다. 직전 기준선 5,141건에서 36건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/api/routes/kanban_api.py`(36), `src/antigravity_k/engine/tool_guardrails.py`(36), `src/antigravity_k/tools/tool_registry.py`(36) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-slang-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 204 (2026-08-31)

- `src/antigravity_k/api/routes/kanban_api.py`의 Kanban task/client payload, event callback kwargs, Request JSON 및 WebSocket 경계를 `JsonObject`, `Mapping`, 명시적 `cast`와 typed helper로 정리했다. workspace filtering, grouped/backward-compatible payload, event-driven task lifecycle, cancel/delete/status update, WebSocket broadcast semantics는 유지했다. 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, `tests/test_api_server.py` 회귀 `36 passed, 2 skipped`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,069 warnings / 0 notes`다. 직전 기준선 5,105건에서 36건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/tool_guardrails.py`(36), `src/antigravity_k/tools/tool_registry.py`(36), `tests/test_self_consistency.py`(36) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-kanban-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 241 (2026-08-31)

- `tests/test_task_runner_outcome.py`의 BackgroundTaskRunner protected 상태/실행 메서드 접근을 typed helper로 감싸고, thread join·state store 반환값·JSON execution context·vault mock 경계를 구체 타입으로 정리했다. task success/failure/cancel, benchmark validation, secret redaction, snapshot rollback semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 task runner 회귀 `11 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,756 warnings / 0 notes`다. 직전 기준선 3,786건에서 30건을 축소했으며, 다음 고경고 단위는 `tests/test_terminal_sandbox_routing.py`(30), `tests/test_upgrade_v6_9.py`(30), `tests/test_tdd_engine.py`(29) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-task-runner-outcome-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 242 (2026-08-31)

- `tests/test_terminal_sandbox_routing.py`의 pytest fixture, platform/shutil stub, sandbox argv와 persistent process 반환값을 구체 타입으로 정리하고 종료·output 반환값을 명시적으로 소비했다. Darwin sandbox wrapping과 비활성 raw 경로 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 terminal sandbox 회귀 `4 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,726 warnings / 0 notes`다. 직전 기준선 3,756건에서 30건을 축소했으며, 다음 고경고 단위는 `tests/test_upgrade_v6_9.py`(30), `tests/test_tdd_engine.py`(29), `tests/test_protocol_translator.py`(29) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-terminal-sandbox-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 205 (2026-08-31)

- `src/antigravity_k/engine/tool_guardrails.py`의 설정·인자·JSON 경계를 `Mapping[str, object]`, 명시적 `cast`, 문자열/정수 변환 helper와 typed controller state로 정리했다. 반복 실패·비진행성·정책 차단·합성 결과 semantics는 유지했다. 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 가드레일 회귀 `25 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 5,033 warnings / 0 notes`다. 직전 기준선 5,069건에서 36건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/tool_registry.py`(36), `tests/test_self_consistency.py`(36), `.agent/skills/k-skill/scripts/test_mfds_drug_safety.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tool-guardrails-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 206 (2026-08-31)

- `src/antigravity_k/tools/tool_registry.py`의 도구 등록·자동 발견·권한 실행 인자와 LLM/OpenAI 스키마 반환 경계를 `Mapping[str, object]`, 재귀 `JsonValue`, Protocol·명시적 `cast`로 정리하고 override 계약을 명시했다. 클래스/인스턴스 설치, 중복 덮어쓰기, 패키지 자동 발견, capability/permission gate 판정 및 스키마 변환 semantics는 유지했다. 변경 소스 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 영향 회귀 `69 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,993 warnings / 0 notes`다. 직전 기준선 5,033건에서 40건을 축소했으며, 다음 고경고 단위는 `tests/test_self_consistency.py`(36), `.agent/skills/k-skill/scripts/test_mfds_drug_safety.py`(35), `scripts/audit_dead_code.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tool-registry-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 207 (2026-08-31)

- `tests/test_self_consistency.py`의 generalized run-loop 회귀 fixture에서 동적 `MagicMock`/`AsyncMock` 접근을 제거하고 router·model manager·context·orchestrator typed double로 교체했다. 비-Qwen self-consistency 활성화, 비활성 fallback, Qwen 회귀 경로 및 기존 정규화/클러스터링/복잡도 게이팅 semantics는 유지했다. 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, self-consistency·amplification 회귀 `53 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,957 warnings / 0 notes`다. 직전 기준선 4,993건에서 36건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_mfds_drug_safety.py`(35), `scripts/audit_dead_code.py`(35), `tests/test_file_tools.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-self-consistency-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 208 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_mfds_drug_safety.py`의 동적 MFDS 모듈 로딩, JSON 결과와 URL 요청 callback 경계를 `_DrugSafetyModule` Protocol, 재귀 `JsonValue`/`JsonObject`, 명시적 narrowing helper로 정리했다. 인터뷰 필수 질문·red flag, 약품 안전정보 정규화, proxy URL 검증과 lookup query 생성 semantics는 유지했다. 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff·py_compile 통과, 표준 unittest `5 tests OK`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,922 warnings / 0 notes`다. 직전 기준선 4,957건에서 35건을 축소했으며, 다음 고경고 단위는 `scripts/audit_dead_code.py`(35), `tests/test_file_tools.py`(35), `tests/test_sandbox.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-mfds-drug-safety-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 209 (2026-08-31)

- `scripts/audit_dead_code.py`의 정규식 동적 임포트 결과, reference counter, 삭제 후보 row, tier summary 및 CLI JSON 출력 경계를 `TypedDict`, 명시적 `cast`, typed `defaultdict`와 문자열 검색 helper로 정리했다. 정적 도달성/auto_discover 생존 판정, 근거 디렉터리 집계, A/B/B+/C 등급 산출 semantics는 유지했다. 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했고 실제 실행에서 `405 modules / 30 candidates`, JSON 구조 검증 `PASS`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,887 warnings / 0 notes`다. 직전 기준선 4,922건에서 35건을 축소했으며, 다음 고경고 단위는 `tests/test_file_tools.py`(35), `tests/test_sandbox.py`(35), `tests/test_security_policy_engine.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-audit-dead-code-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 210 (2026-08-31)

- `tests/test_file_tools.py`의 fixture 반환 경계와 파일 쓰기·삭제 및 도구 실행의 의도적 미사용 반환값을 `Iterator[str]`와 `_ =`로 명시했다. `GlobSearchTool._human_size` 검증은 문자열 기반 `getattr`와 typed `Callable` cast 경계로 보호된 멤버 진단을 제거했다. 파일 생성·편집·다중 치환·glob/grep 검색 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했고 파일 도구 영향 회귀 `80 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,852 warnings / 0 notes`다. 직전 기준선 4,887건에서 35건을 축소했으며, 다음 고경고 단위는 `tests/test_sandbox.py`(35), `tests/test_security_policy_engine.py`(35), `tests/test_self_evolution_tool.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-file-tools-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 211 (2026-08-31)

- `tests/test_sandbox.py`의 pytest 경계(`Path`, `MonkeyPatch`), fake runner kwargs, 호출 기록 및 임시 경로를 구체 타입으로 정리했다. seatbelt/Docker protected helper 검증은 문자열 기반 `getattr`와 typed `Callable` cast로 감쌌고, 플랫폼 필드 설정은 `setattr`로 유지했다. sandbox 비활성 폴백, 네트워크 차단, 출력 quota, timeout descendant 종료 및 backend fail-closed semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했고 sandbox 회귀 `17 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,817 warnings / 0 notes`다. 직전 기준선 4,852건에서 35건을 축소했으며, 다음 고경고 단위는 `tests/test_security_policy_engine.py`(35), `tests/test_self_evolution_tool.py`(35), `tests/test_week2_e2e.py`(35) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-sandbox-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 212 (2026-08-31)

- `tests/test_security_policy_engine.py`의 pytest `tmp_path` 경계와 YAML 정책 파일 경로를 `Path`로 명시하고, 파일 쓰기 결과를 `_ =`로 처리했다. 정책 내부 filesystem payload는 필요한 구조로 직접 typed `cast`하여 불필요한 중첩 cast를 제거했다. override→seed→fallback 권한 순서, YAML fail-closed, command/domain allow/deny 및 canonicalization semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 정책 회귀 `16 passed`를 확인했다.
- `tests/test_self_evolution_tool.py`의 SelfReward/Metacognitive protected state와 helper 접근은 문자열 기반 `getattr` 및 typed `Callable`/TypedDict cast wrapper로 정리했다. 평가 결과·트렌드·등급 경계·사이클 기록·실패 패턴·JSON persist semantics는 유지했고, 의도적 평가/save 반환값과 JSON 로드 payload도 명시했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, self-evolution 회귀 `49 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,747 warnings / 0 notes`다. 직전 기준선 4,817건에서 70건을 축소했으며, 다음 고경고 단위는 `tests/test_week2_e2e.py`(35), `.agent/skills/k-skill/naver-blog-research/scripts/naver_read.py`(34), `.agent/skills/k-skill/scripts/test_k_skill_cleaner.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-self-evolution-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 213 (2026-08-31)

- `tests/test_week2_e2e.py`의 SkillMarketClient/SkillInstaller/SlashCommandRegistry protected helper 호출을 typed callable wrapper와 문자열 기반 `getattr` 경계로 정리했다. MCP 서버 레지스트리 초기화와 marketplace package metadata JSON payload도 명시 타입으로 보강했다. D8-D14 marketplace lifecycle, package validation/security/copy/meta, MCP registration, SkillLoader source filtering 및 `/market` 명령어 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, marketplace E2E 회귀 `55 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,712 warnings / 0 notes`다. 직전 기준선 4,747건에서 35건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/naver-blog-research/scripts/naver_read.py`(34), `.agent/skills/k-skill/scripts/test_k_skill_cleaner.py`(34), `scripts/fix_d401.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-week2-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 214 (2026-08-31)

- `.agent/skills/k-skill/naver-blog-research/scripts/naver_read.py`의 동적 `_naver_http` 모듈 경계와 HTTP 응답 컨텍스트를 Protocol/cast로 명시하고, 본문 추출 라인·CLI 인자·JSON 결과 타입을 구체화했다. Naver URL 변환·HTML 본문/이미지 추출·SSL 옵션·CLI 오류 출력 semantics는 유지했다.
- 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 URL/title/text/image/CLI 인자 smoke `PASS`를 확인했다. 첫 importlib smoke 하네스 오류는 모듈 등록 누락으로 재현·수정했고 실제 모듈 로딩 경로 기준 재실행에서 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,678 warnings / 0 notes`다. 직전 기준선 4,712건에서 34건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_k_skill_cleaner.py`(34), `scripts/fix_d401.py`(34), `src/antigravity_k/api/routes/models_api.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-naver-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 215 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_k_skill_cleaner.py`의 동적 compatibility-wrapper import와 usage/candidate/report JSON 경계를 Protocol·TypedDict·typed callable로 정리하고, 파일시스템·subprocess 호출의 의도적 반환값을 명시했다. CLI가 저장소 루트의 `PYTHONPATH`에 의존하던 회귀 경로는 테스트 subprocess의 실행 디렉터리를 스크립트 위치로 고정해 격리했다. skill directory 탐색, 로그 window/mtime fallback, usage JSON provenance, cleanup ranking semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 cleaner 회귀 `8 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,644 warnings / 0 notes`다. 직전 기준선 4,678건에서 34건을 축소했으며, 다음 고경고 단위는 `scripts/fix_d401.py`(34), `src/antigravity_k/api/routes/models_api.py`(34), `src/antigravity_k/engine/claude_deny_patterns.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-cleaner-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 216 (2026-08-31)

- `scripts/fix_d401.py`의 Ruff JSON 진단 결과를 `RuffViolation`/`RuffLocation` TypedDict로 명시하고 `run_ruff` 반환·파일 그룹·문서 문자열 수정 경계를 구체화했다. D401 변환 규칙과 검증 출력 semantics는 유지했으며, 실제 자동 수정 실행은 소스 문서 변경을 유발하므로 수행하지 않았다.
- 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 `fix_docstring`/`run_ruff` smoke `PASS`를 확인했다(`run_ruff` 현재 D401 findings 13).
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,610 warnings / 0 notes`다. 직전 기준선 4,644건에서 34건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/api/routes/models_api.py`(34), `src/antigravity_k/engine/claude_deny_patterns.py`(34), `src/antigravity_k/engine/runtime_recovery.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-fix-d401-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 217 (2026-08-31)

- `src/antigravity_k/api/routes/models_api.py`의 FastAPI dependency 파라미터를 `Annotated`로 명시하고, Wake payload/health/models/operations/embeddings 응답과 YAML config 경계를 구체 타입으로 정리했다. private tool-registry dependency는 모듈 `getattr`+typed callable로 감싸고, protected model registry 접근은 typed boundary로 유지했다. health, wake, model listing, provider capabilities, embeddings, default model persistence semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean을 통과했고 모델 operations 회귀 `1 passed`, 관련 health/wake/models/embedding/default-model 회귀 `16 passed`를 확인했다. 장시간(약 136초) 실행되었으나 정상 종료했다.
- 중간 전체 진단에서 관련 테스트의 `dict[str, object]` 인덱싱 2건이 드러나 `ModelOperationsResponse`/quality calibration TypedDict로 보강한 뒤 최종 전체 basedpyright는 `864 files / 0 errors / 4,576 warnings / 0 notes`다. 직전 유효 기준선 4,610건에서 34건을 축소했다.
- 다음 고경고 단위는 `src/antigravity_k/engine/claude_deny_patterns.py`(34), `src/antigravity_k/engine/runtime_recovery.py`(34), `src/antigravity_k/engine/scheduled_job_operations.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-models-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 218 (2026-08-31)

- `src/antigravity_k/engine/claude_deny_patterns.py`의 deny 설치 리포트 슬롯/필드, JSON settings root·permissions·deny 목록 및 runtime 패턴 결과를 구체 타입으로 정리했다. 기존 사용자 설정 병합, legacy marker 정리, 백업, 상태 조회, runtime glob 차단 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, 보안 회귀 `14 passed`를 확인했다.

## Warning debt continuation 219 (2026-08-31)

- `src/antigravity_k/engine/runtime_recovery.py`의 상태 분류·deep health check 입력 경계를 `object`와 typed Protocol cast로 명시하고, component callback을 `Callable[[object], bool]`로 정리했다. 모델/세션/메모리/도구/쉴드 점검과 transport/credential/model/endpoint 분류 semantics는 유지했다. 호출부의 SimpleNamespace 및 실제 manager 호환성을 위해 공개 입력은 object로 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, deep-health 회귀 `2 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,506 warnings / 0 notes`다. 직전 기준선 4,576건에서 70건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/scheduled_job_operations.py`(34), `src/antigravity_k/engine/tool_call_parser.py`(34), `src/antigravity_k/tools/cowork_delegate.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-runtime-recovery-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 220 (2026-08-31)

- `src/antigravity_k/engine/scheduled_job_operations.py`의 SQLite row/connection 경계를 `cast`, 구체 예외 필드, `Generator` contextmanager와 typed 상태 구조로 정리하고 SQL cursor 반환값을 명시했다. 초기화 시 WAL PRAGMA cursor를 소비하도록 수정해 API retry 경로의 `cannot commit transaction - SQL statements in progress` 런타임 오류를 제거했다. 예약 작업 health/retry/idempotency semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과를 확인했다. `tests/test_scheduled_jobs.py` 7개와 `tests/test_job_api.py` 4개가 모두 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,472 warnings / 0 notes`다. 직전 기준선 4,506건에서 34건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/tool_call_parser.py`(34), `src/antigravity_k/tools/cowork_delegate.py`(34), `src/antigravity_k/tools/init_deep_tool.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-scheduled-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 221 (2026-08-31)

- `src/antigravity_k/engine/tool_call_parser.py`의 JSON decode 결과와 도구 호출 생성 경계를 재귀 `JsonValue` coercion, object narrowing helper, `ClassVar`/인스턴스 필드 타입으로 정리했다. 태그 기반·bare JSON·streaming bare JSON·thought 블록 파싱 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과를 확인했고 parser 회귀 `tests/test_tool_call_parser.py` 6개와 tool-loop 통합 회귀 `tests/test_tool_loop.py` 91개가 모두 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,438 warnings / 0 notes`다. 직전 기준선 4,472건에서 34건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/cowork_delegate.py`(34), `src/antigravity_k/tools/init_deep_tool.py`(34), `tests/test_persistent_agency.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tool-call-parser-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 222 (2026-08-31)

- `src/antigravity_k/tools/cowork_delegate.py`의 도구 메타데이터·model manager·task runner·동적 orchestrator 경계를 Protocol/구체 타입/override로 정리했다. 설명 문자열의 암묵적 인접 문자열 분리 버그를 수정해 서브에이전트 안내문이 전체 문장으로 전달되도록 보강했고, 순환 import 회피 동작은 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 `tests/test_new_features.py` 2개 통과를 확인했다. 전체 진단에서 일시적으로 발견된 orchestrator 순환 참조 6건은 동적 import 경계를 복원해 해소했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,404 warnings / 0 notes`다. 직전 기준선 4,438건에서 34건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/init_deep_tool.py`(34), `tests/test_persistent_agency.py`(34), `tests/test_unsloth_studio.py`(34) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-cowork-delegate-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 223 (2026-08-31)

- `src/antigravity_k/tools/init_deep_tool.py`의 도구 메타데이터·반환 경계를 구체 타입과 `override`로 정리하고, 입력 경로·`os.walk` 결과·AGENTS 파일 쓰기 경계를 명시했다. 설명 문자열의 암묵적 인접 문자열 분리 버그도 수정해 생성 안내문이 완전하게 유지되도록 했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과를 확인했다. 임시 workspace에서 루트·하위 디렉터리 AGENTS 생성 및 잘못된 경로 오류 처리를 검증하는 smoke가 통과했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,370 warnings / 0 notes`다. 직전 기준선 4,404건에서 34건을 축소했으며, 다음 고경고 단위는 `tests/test_persistent_agency.py`(34), `tests/test_unsloth_studio.py`(34), `.agent/skills/k-skill/geeknews-search/scripts/geeknews_search.py`(33) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-init-deep-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 224 (2026-08-31)

- `tests/test_persistent_agency.py`의 pytest `tmp_path` 경계와 영속 agency callback/objective 호출의 의도적 미사용 반환값을 `Path`·`_ =`로 명시했다. 이벤트 저장·요약 projection·secret redaction·objective lease/requeue·hook 연동 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, persistent agency 회귀 `9 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,336 warnings / 0 notes`다. 직전 기준선 4,370건에서 34건을 축소했으며, 다음 고경고 단위는 `tests/test_unsloth_studio.py`(34), `.agent/skills/k-skill/geeknews-search/scripts/geeknews_search.py`(33), `.agent/skills/k-skill/scripts/geeknews_search.py`(33) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-persistent-agency-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 225 (2026-08-31)

- 중복 배포 경로인 `.agent/skills/k-skill/geeknews-search/scripts/geeknews_search.py`와 `.agent/skills/k-skill/scripts/geeknews_search.py`의 Atom 응답·HTML parser override·feed item list·CLI argparse 결과를 Protocol/구체 타입/`CliArgs`로 정리했다. 두 파일의 동작은 동일하게 유지했고 parser, search/detail payload 및 feed-file CLI semantics를 보존했다.
- 두 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과를 확인했다. `PYTHONPATH=.` 스킬 디렉터리 기준 GeekNews 회귀 `7 passed`를 확인했다. 저장소 루트에서 실행할 때의 `ModuleNotFoundError: scripts`는 테스트 import 경로 설정 문제로 확인되어 코드 수정 없이 실행 기준을 기록했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,270 warnings / 0 notes`다. 직전 기준선 4,336건에서 66건을 축소했으며, 다음 고경고 단위는 `tests/test_unsloth_studio.py`(34), `src/antigravity_k/engine/skill_loader.py`(33), `src/antigravity_k/engine/provider_adapters/dev_shims.py`(33) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-geeknews-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 226 (2026-08-31)

- `src/antigravity_k/engine/skill_loader.py`의 skill metadata와 capability policy 설정 경계를 TypedDict/Mapping으로 좁히고 YAML decode·filesystem scan·active prompt 생성을 구체 타입으로 정리했다. source 우선순위(global/local/market), invalid YAML scalar 복구, 자동 활성화와 critical-risk 정책 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과를 확인했다. SkillLoader 관련 phase1 회귀 34개와 week2 회귀 6개가 통과했고, system API skills 전체 20개도 스킬 디렉터리 import 기준으로 통과했다(194.92초).
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,237 warnings / 0 notes`다. 직전 기준선 4,270건에서 33건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/provider_adapters/dev_shims.py`(33), `tests/test_unsloth_studio.py`(33), `.agent/skills/k-skill/geeknews-search/scripts/test_geeknews_search.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-skill-loader-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 227 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/dev_shims.py`의 Ollama model/tokenizer shim 메타데이터, tokenizer 입력·반환·chat message 경계를 구체 타입과 override로 정리했다. CJK/라틴 토큰 추정, decode/vocab placeholder, chat template 문자열 생성 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 model manager 생성 회귀 `15 passed`를 확인했다. 동적 class-name 참조를 위한 `OLLAMA_MODEL_CLASS_NAME`도 명시했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,204 warnings / 0 notes`다. 직전 기준선 4,237건에서 33건을 축소했으며, 다음 고경고 단위는 `tests/test_unsloth_studio.py`(33), `.agent/skills/k-skill/geeknews-search/scripts/test_geeknews_search.py`(32), `.agent/skills/k-skill/scripts/test_geeknews_search.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-dev-shims-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 228 (2026-08-31)

- `tests/test_unsloth_studio.py`의 loopback URL/설정 검증 호출 결과와 FastAPI override 정리, MCP manager/session/registry 및 audit mock 경계를 Protocol/cast로 구체화했다. Permission import를 공개 계약 모듈로 바로잡고 API payload를 Mapping으로 좁혔으며 테스트 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 Unsloth Studio 회귀 `6 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,170 warnings / 0 notes`다. 직전 기준선 4,204건에서 34건을 축소했으며, 다음 고경고 단위는 `scripts/team_coordinator.py`(33), `tests/test_vault_privacy_service.py`(33), `src/antigravity_k/engine/data_extractor.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-unsloth-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 229 (2026-08-31)

- `scripts/team_coordinator.py`의 AgentRole/TaskStatus 상수, AgentTask 상태·history·직렬화 결과, TeamCoordinator task/agent 컬렉션을 구체 타입과 TypedDict로 정리했다. 기존 task 상태 전이와 토큰 누적 semantics는 유지했다.
- 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 CLI smoke에서 단일 작업이 `BACKLOG→IN_PROGRESS→REVIEW→DONE`, `760` tokens로 완료되는 것을 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,137 warnings / 0 notes`다. 직전 기준선 4,170건에서 33건을 축소했으며, 다음 고경고 단위는 `tests/test_vault_privacy_service.py`(33), `src/antigravity_k/engine/data_extractor.py`(32), `src/antigravity_k/tools/agent_spawn.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-team-coordinator-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 230 (2026-08-31)

- `tests/test_vault_privacy_service.py`의 프라이버시 계약 import를 공개 contracts 모듈로 정리하고, chunker/wiki mock 호출·subprocess/file I/O 결과를 Protocol, 구체 콜백, 명시적 discard로 좁혔다. redact rollback, 안전한 restore target 거부, 선택 파일 보존 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 vault privacy 회귀 `6 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,104 warnings / 0 notes`다. 직전 기준선 4,137건에서 33건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/data_extractor.py`(32), `src/antigravity_k/tools/agent_spawn.py`(32), `src/antigravity_k/tools/ast_grep_tool.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-vault-privacy-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 231 (2026-08-31)

- `src/antigravity_k/engine/data_extractor.py`의 ExtractionMetrics 저장소를 구체 TypedDict/MetricKey로 좁히고, TOP1 JSON 파싱·answer/results 순회·주식 코드 매핑 경계를 안전한 JSON 타입과 명시적 cast로 정리했다. 추출 포맷, 오탐 필터, 성공률 계산 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 데이터 추출 회귀 `144 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,072 warnings / 0 notes`다. 직전 기준선 4,104건에서 32건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/agent_spawn.py`(32), `src/antigravity_k/tools/ast_grep_tool.py`(32), `tests/test_durable_memory_purge.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-data-extractor-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 232 (2026-08-31)

- `src/antigravity_k/tools/agent_spawn.py`의 tool 메타데이터/상태 속성, 모델 매니저·오케스트레이터·dependency 동적 import 경계를 Protocol과 명시적 타입으로 정리했다. 공개 모델 선택 메서드 우선 및 기존 protected fake fallback을 유지해 테스트 호환성을 보존했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 agent definition/subagent execution 회귀 `8 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,035 warnings / 0 notes`다. 직전 기준선 4,072건에서 37건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/ast_grep_tool.py`(32), `tests/test_durable_memory_purge.py`(32), `tests/test_memory_scope.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-agent-spawn-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 233 (2026-08-31)

- `src/antigravity_k/tools/ast_grep_tool.py`의 tool 메타데이터와 실행 인자를 구체 타입/override로 정리하고, 잘못된 입력을 안전한 문자열 경계로 좁혔다. ast-grep 명령 구성과 replace/search 동작 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 실제 도구 호출 smoke를 확인했다(환경에 `sg`가 없을 때 명시적 오류 문자열 반환).
- 최신 전체 basedpyright는 `864 files / 0 errors / 4,003 warnings / 0 notes`다. 직전 기준선 4,035건에서 32건을 축소했으며, 다음 고경고 단위는 `tests/test_durable_memory_purge.py`(32), `tests/test_memory_scope.py`(32), `tests/test_tool_contracts.py`(32) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-ast-grep-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 234 (2026-08-31)

- `tests/test_durable_memory_purge.py`의 protected state 조작을 setattr/getattr 경계로 정리하고, monkeypatch factory·mock assertion·subprocess/file 결과를 구체 타입으로 명시했다. memory service, vector/wiki/gbrain purge 및 durable provider 등록 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 purge 회귀 `7 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,971 warnings / 0 notes`다. 직전 기준선 4,003건에서 32건을 축소했으며, 다음 고경고 단위는 `tests/test_memory_scope.py`(32), `tests/test_tool_contracts.py`(32), `.agent/skills/k-skill/naver-blog-research/scripts/naver_search.py`(31) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-durable-memory-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 235 (2026-08-31)

- `tests/test_memory_scope.py`의 세션 시작·clear 반환값을 명시적으로 소비하고, monkeypatch/captured kwargs/request stub/audit mock 경계를 구체 타입으로 정리했다. memory scope clear/export/redaction, shared dependency manager, audited purge route semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 memory scope 회귀 `12 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,939 warnings / 0 notes`다. 직전 기준선 3,971건에서 32건을 축소했으며, 다음 고경고 단위는 `tests/test_tool_contracts.py`(32), `.agent/skills/k-skill/naver-blog-research/scripts/naver_search.py`(31), `scripts/run_frontier_comparison.py`(30) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-memory-scope-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 236 (2026-08-31)

- `tests/test_tool_contracts.py`의 테스트 도구 descriptor를 `Mapping[str, object]`와 명시적 `override`로 정리하고, Permission 공개 import·fixture `Path`·registry 반환값을 구체화했다. ToolRegistry authorize/permission denial/unregistered descriptor semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 tool contract 회귀 `3 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,907 warnings / 0 notes`다. 직전 기준선 3,939건에서 32건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/naver-blog-research/scripts/naver_search.py`(31), `scripts/run_frontier_comparison.py`(30), `src/antigravity_k/agents/skills_registry.py`(30) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tool-contracts-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 237 (2026-08-31)

- `.agent/skills/k-skill/naver-blog-research/scripts/naver_search.py`의 동적 `_naver_http` 모듈·HTTP 응답·URL open callable을 Protocol로 고정하고, 정규식 tuple 결과와 argparse Namespace 인자를 명시적 cast로 좁혔다. HTML parsing, pagination, sort/insecure 전달 semantics는 유지했다.
- 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 Naver 검색 회귀 `3 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,876 warnings / 0 notes`다. 직전 기준선 3,907건에서 31건을 축소했으며, 다음 고경고 단위는 `scripts/run_frontier_comparison.py`(30), `src/antigravity_k/agents/skills_registry.py`(30), `tests/test_kanban.py`(30) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-naver-search-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 238 (2026-08-31)

- `scripts/run_frontier_comparison.py`의 예외 상태·score provider manager·CLI parser 반환값·argparse Namespace 값을 구체 타입으로 정리하고, 암시적 문자열 결합과 파일 쓰기 결과 미사용 경고를 제거했다. 관측 수집, 모델 순서 균형, 증적 artifact/sha256 기록 semantics는 유지했다.
- 변경 스크립트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 frontier comparison 회귀 `4 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,846 warnings / 0 notes`다. 직전 기준선 3,876건에서 30건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/agents/skills_registry.py`(30), `tests/test_kanban.py`(30), `tests/test_task_runner_outcome.py`(30) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-frontier-comparison-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 239 (2026-08-31)

- `src/antigravity_k/agents/skills_registry.py`의 YAML frontmatter 값을 `FrontmatterValue`로 좁히고 SkillProfile/SkillsRegistry 상태, i18n callable, ToolRegistry validator 경계를 구체 타입으로 정리했다. 동적 skill 로딩, reference/질문/검증 섹션 추출, 도구 누락 검증 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 skills registry 관련 회귀 `39 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,816 warnings / 0 notes`다. 직전 기준선 3,846건에서 30건을 축소했으며, 다음 고경고 단위는 `tests/test_kanban.py`(30), `tests/test_task_runner_outcome.py`(30), `tests/test_terminal_sandbox_routing.py`(30) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-skills-registry-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 240 (2026-08-31)

- `tests/test_kanban.py`의 pytest fixture와 sqlite schema/row 경계를 `Path`, `LogCaptureFixture`, 구체 row tuple로 명시하고, schema SQL을 명시적 결합으로 정리했다. current/legacy Kanban schema migration 및 warning-free 동작 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 Kanban 회귀 `2 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,786 warnings / 0 notes`다. 직전 기준선 3,816건에서 30건을 축소했으며, 다음 고경고 단위는 `tests/test_task_runner_outcome.py`(30), `tests/test_terminal_sandbox_routing.py`(30), `tests/test_upgrade_v6_9.py`(30) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-kanban-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 243 (2026-08-31)

- `tests/test_upgrade_v6_9.py`의 SelfImprovementLoop 반복 변수, persistence 내부 상태 접근, pytest `tmp_path` 경계 및 MemoryProvider SessionManager 포트 mock을 구체 타입으로 정리했다. upgrade v6.9 통합 회귀 semantics와 skip 조건은 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 upgrade v6.9 회귀 `19 passed, 2 skipped`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,406 warnings / 0 notes`다. 직전 측정치 3,726건 대비 320건을 축소했으며, 다음 고경고 단위는 `tests/test_tdd_engine.py`, `tests/test_protocol_translator.py`, `tests/test_local_model_discovery.py`, `tests/test_ide_server.py`, `src/antigravity_k/engine/secure_key.py`, `src/antigravity_k/engine/orchestrator_review_handler.py`, `src/antigravity_k/engine/capability_policy.py`, `src/antigravity_k/engine/audit_db.py`(각 29건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-upgrade-v6-9-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 244 (2026-08-31)

- `tests/test_tdd_engine.py`의 `tmp_path`·engine fixture 타입을 명시하고, protected helper 호출을 타입이 보존되는 래퍼로 경계화했으며, 파일 쓰기 반환값을 명시적으로 소비했다. 외부 테스트 파일 self-play, 레이싱 스킵 판정, Python 코드 블록 추출 semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 TDD engine 회귀 `8 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,377 warnings / 0 notes`다. 직전 측정치 3,406건 대비 29건을 축소했으며, 다음 고경고 단위는 `tests/test_protocol_translator.py`, `tests/test_local_model_discovery.py`, `tests/test_ide_server.py`, `src/antigravity_k/engine/secure_key.py`, `src/antigravity_k/engine/orchestrator_review_handler.py`, `src/antigravity_k/engine/capability_policy.py`, `src/antigravity_k/engine/audit_db.py`(각 29건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tdd-engine-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 245 (2026-08-31)

- `tests/test_protocol_translator.py`의 요청·응답 payload를 `dict[str, object]`로 명시하고, protected content/route 메서드 호출을 `Callable` 기반 타입 래퍼로 경계화했다. OpenAI·Anthropic·내부 포맷 변환과 edge-case semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 protocol translator 회귀 `43 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,348 warnings / 0 notes`다. 직전 측정치 3,377건 대비 29건을 축소했으며, 다음 고경고 단위는 `tests/test_local_model_discovery.py`, `tests/test_ide_server.py`, `src/antigravity_k/engine/secure_key.py`, `src/antigravity_k/engine/orchestrator_review_handler.py`, `src/antigravity_k/engine/capability_policy.py`, `src/antigravity_k/engine/audit_db.py`(각 29건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-protocol-translator-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 246 (2026-08-31)

- `tests/test_local_model_discovery.py`의 HTTP 응답 fake를 구체 클래스로 교체하고, 환경변수 endpoint/private classmethod·MagicMock 호출·파일 쓰기 반환값·capability request 경계를 타입 안전하게 정리했다. Ollama/OpenAI-compatible/Unsloth/Transformers/MLX/registry discovery semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 local model discovery 회귀 `15 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,319 warnings / 0 notes`다. 직전 측정치 3,348건 대비 29건을 축소했으며, 다음 고경고 단위는 `tests/test_ide_server.py`, `src/antigravity_k/engine/secure_key.py`, `src/antigravity_k/engine/orchestrator_review_handler.py`, `src/antigravity_k/engine/capability_policy.py`, `src/antigravity_k/engine/audit_db.py`(각 29건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-local-model-discovery-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 247 (2026-08-31)

- `tests/test_ide_server.py`의 subprocess mock을 타입이 명시된 `_ProcessDouble`로 교체하고 Popen 호출 인자·프로세스 상태/종료 경계를 구체화했다. IDE server start/stop/is_running semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 IDE server 회귀 `11 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,290 warnings / 0 notes`다. 직전 측정치 3,319건 대비 29건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/secure_key.py`, `src/antigravity_k/engine/orchestrator_review_handler.py`, `src/antigravity_k/engine/capability_policy.py`, `src/antigravity_k/engine/audit_db.py`(각 29건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-ide-server-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 248 (2026-08-31)

- `src/antigravity_k/engine/secure_key.py`의 KDF 파라미터와 rotation 결과를 `TypedDict`로 명시하고, config/vault JSON을 `object`에서 문자열 키 맵으로 안전하게 좁혔다. MAC 주소 판정과 파일 쓰기 반환값 경계도 정리했으며 키 조회·저장·회전 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 secure key 회귀 `45 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,262 warnings / 0 notes`다. 직전 측정치 3,290건 대비 28건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/orchestrator_review_handler.py`, `src/antigravity_k/engine/capability_policy.py`, `src/antigravity_k/engine/audit_db.py`(각 29건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-secure-key-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 249 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_review_handler.py`의 tool history와 orchestrator context/manager를 Protocol로 명시하고, timestamp narrowing·manager 응답 문자열 변환·protected model resolver 경계를 정리했다. mutating-tool 감지, git diff 리뷰, retry loopback semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 orchestrator handler 회귀 `12 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,226 warnings / 0 notes`다. 직전 측정치 3,262건 대비 36건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/capability_policy.py`(29), `src/antigravity_k/engine/audit_db.py`(29), `tests/test_rag_provenance.py`(28) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-orchestrator-review-handler-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 250 (2026-08-31)

- `src/antigravity_k/engine/capability_policy.py`의 tool metadata Protocol을 실제 `BaseTool` property/Mapping 계약과 일치시키고, skill payload·tag collection·token 정규화 경계를 `object`/구체 컬렉션으로 명시했다. 자율 tool/skill 위험도·신뢰도·고위험 의도 판정 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 capability policy 관련 회귀 `33 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,197 warnings / 0 notes`다. 직전 측정치 3,226건 대비 29건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/audit_db.py`(29), `tests/test_rag_provenance.py`(28) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-capability-policy-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 251 (2026-08-31)

- `src/antigravity_k/engine/audit_db.py`의 SQLite 연결/커서 반환값, 이벤트 메타데이터, JSON payload, 집계 row를 `object`·구체 tuple·`JsonValue`로 좁히고 클래스 상태를 명시적으로 타입화했다. 감사 이벤트 삽입·최근 조회·tool 통계·count semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과, `tests/test_audit_logger.py` `3 passed` 및 임시 SQLite 삽입/조회/통계 smoke를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,168 warnings / 0 notes`다. 직전 측정치 3,197건 대비 29건을 축소했으며, 다음 고경고 단위는 `tests/test_rag_provenance.py`(28) 순이다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-audit-db-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 252 (2026-08-31)

- `tests/test_rag_provenance.py`의 RecordingVectorStore fixture에 chunk/metadata 계약과 메서드 인자를 명시하고, Path·파일 쓰기 반환값·검색 query·JSON metadata 경계를 타입 안전하게 정리했다. provenance/freshness/citation 검증 시나리오는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean 및 RAG provenance 회귀 `3 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,140 warnings / 0 notes`다. 직전 측정치 3,168건 대비 28건을 축소했으며, 다음 고경고 단위는 전체 파일 집계 재확인 후 이어간다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-rag-provenance-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 253 (2026-08-31)

- `src/antigravity_k/engine/dialectic_engine.py`의 구식 `typing.Dict/List/Optional`과 `Any`를 내장 generic, `ClassVar`, `| None`, 구체 workflow step 리스트로 전환했다. 변증법 prompt/workflow 생성, structured response 파싱, autocoding state 전이는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 변증법 관련 회귀 `48 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,112 warnings / 0 notes`다. 직전 측정치 3,140건 대비 28건을 축소했다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-dialectic-engine-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 254 (2026-08-31)

- `src/antigravity_k/tools/db_migration.py`의 도구 메타데이터·schema·subprocess/action 입력을 구체 타입으로 명시하고 `@override` 계약을 추가했다. Alembic upgrade/downgrade/revision 및 SQL 시뮬레이션 결과 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과, `tests/test_tool_sandbox_coverage.py` `8 passed` 및 action/schema/error/simulation smoke를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,084 warnings / 0 notes`다. 직전 측정치 3,112건 대비 28건을 축소했다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-db-migration-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 255 (2026-08-31)

- `tests/test_agency_api.py`의 동적 runtime fixture를 명시적 orchestrator double로 교체하고, pytest fixture·Path·FastAPI JSON 응답·nested scheduler 값을 구체 타입으로 좁혔다. objective control-plane 생성/조회/범위 제한과 pause/resume semantics는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean 및 agency API 회귀 `3 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,056 warnings / 0 notes`다. 직전 측정치 3,084건 대비 28건을 축소했다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-agency-api-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 256 (2026-08-31)

- `tests/test_decision_anchor.py`의 add 반환값을 명시적으로 소비하고, injection content 및 protected category classifier 호출 경계를 타입 안전하게 정리했다. anchor 생성/퇴출/주입/자동 추출/통계 시나리오는 유지했다.
- 변경 테스트 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean 및 decision anchor 회귀 `30 passed`를 확인했다.
- 최신 전체 basedpyright는 `864 files / 0 errors / 3,028 warnings / 0 notes`다. 직전 측정치 3,056건 대비 28건을 축소했다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-decision-anchor-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 257 (2026-08-31)

- `src/antigravity_k/engine/best_of_n_verifier.py`의 정규식 결과·파일 블록 쓰기·검증기 callback·샘플 생성 kwargs·Best-of-N config 경계를 구체 타입으로 정리했다. 후보 추출·구문/명령/worktree 검증·first-pass early exit·점수 폴백 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 Best-of-N 회귀 `31 passed`를 확인했다. 생성 실패 후 유효 후보를 선택하는 early-exit 수동 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,292 warnings / 0 notes`다. 직전 동일 파일 기준선 3,028건에서 `best_of_n_verifier.py` 27건을 제거했으며, 사용자 변경으로 추가된 현재 dirty Python 경로까지 포함한 전체 집계를 함께 기록했다. 다음 고경고 단위는 `src/antigravity_k/engine/prompt_builder.py`, `src/antigravity_k/tools/base_tool.py`, `src/antigravity_k/tools/binary_tools.py`, `tests/test_code_intel_hybrid_search.py`(각 27건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-best-of-n-verifier-root-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 258 (2026-08-31)

- `src/antigravity_k/engine/prompt_builder.py`의 PromptBuilder 디렉터리 상태, tool schema/parameter mapping, required/properties 컬렉션, structured prompt 섹션·few-shot 리스트를 구체 타입으로 정리하고 implicit string concatenation을 제거했다. 역할/페르소나/도구 가이드/응답 계약/구조화 프롬프트 semantics는 유지했다.
- 변경 모듈 basedpyright/LSP `0 errors / 0 warnings`, Ruff clean, py_compile 통과 및 prompt builder 회귀 `31 passed`를 확인했다. 누락 prompts 디렉터리 fallback, malformed schema 무중단 처리, structured prompt 생성 수동 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,265 warnings / 0 notes`다. 직전 전체 집계 3,292건 대비 27건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/base_tool.py`, `src/antigravity_k/tools/binary_tools.py`, `tests/test_code_intel_hybrid_search.py`(각 27건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-prompt-builder-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 259 (2026-08-31)

- `src/antigravity_k/tools/base_tool.py`의 pre/post hook, execute, metadata/schema 반환 경계를 구체화하고, 하위 도구 입력 경계(`binary_tools.py`, `docker_tools.py`, `vision_tools.py`, `web_scraper.py`)의 kwargs 값을 문자열·정수·실수·경로 타입으로 안전하게 좁혔다. `agent_definition.py` metadata list와 computer-use/tiptap 테스트의 nested mapping 접근도 명시했다. 기존 도구 실행·승인·schema/metadata semantics는 유지했다.
- 변경 모듈 LSP/basedpyright/Ruff `0 errors / 0 warnings`, py_compile 통과, 도구 계약·실행·computer-use·tiptap 회귀 `92 passed`를 확인했다. BaseTool `__call__`/approval/metadata/schema, binary file dump 및 malformed kwargs 경계 수동 smoke를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,203 warnings / 0 notes`다. 직전 집계 3,265건 대비 62건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/binary_tools.py`, `tests/test_code_intel_hybrid_search.py`(각 27건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-base-tool-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 260 (2026-08-31)

- `src/antigravity_k/tools/binary_tools.py`의 HexDumpTool을 `@final`/`@override` 계약과 구체 `_name`·`_description`·`_schema`·결과 리스트로 정리하고, 파일 경로·offset·length 입력을 명시적으로 검증했다. hexdump 포맷과 EOF/오류 응답 semantics는 유지했다.
- 변경 모듈 LSP/basedpyright/Ruff `0 errors / 0 warnings`, py_compile 통과 및 임시 바이너리 파일 hexdump/잘못된 입력 수동 smoke를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,186 warnings / 0 notes`다. 직전 집계 3,203건 대비 17건을 축소했으며, 다음 고경고 단위는 `tests/test_code_intel_hybrid_search.py`(27), `.agent/skills/k-skill/scripts/test_zipcode_search.py`, `src/antigravity_k/engine/file_summarizer.py`, `tests/test_auth.py`, `tests/test_code_tree_indexer.py`, `tests/test_memory_recorder.py`, `tests/test_rag_retrieval_quality.py`(각 26건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-binary-tools-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 261 (2026-08-31)

- `tests/test_code_intel_hybrid_search.py`의 FakeGraph fixture를 명시적 `@final` graph double로 분리하고 nodes/fixture/test graph 타입을 지정했으며, 자동 index build 테스트의 search 반환값을 의도적으로 소비했다. 검색 결과·대소문자 무시·top_k 제한·빈 query semantics는 유지했다.
- 변경 테스트 LSP/basedpyright/Ruff `0 errors / 0 warnings`, py_compile 통과 및 hybrid search 회귀 `8 passed`를 확인했다. 자동 index 구축과 빈 query 수동 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,159 warnings / 0 notes`다. 직전 집계 3,186건 대비 27건을 축소했으며, 다음 고경고 단위는 `.agent/skills/k-skill/scripts/test_zipcode_search.py`, `src/antigravity_k/engine/file_summarizer.py`, `tests/test_auth.py`, `tests/test_code_tree_indexer.py`, `tests/test_memory_recorder.py`, `tests/test_rag_retrieval_quality.py`(각 26건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-code-intel-hybrid-search-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 262 (2026-08-31)

- `src/antigravity_k/engine/file_summarizer.py`의 optional model manager Protocol, 파일 목록·경로·함수/클래스 목록·요약 결과 경계를 구체화하고, 생성자 호환 경계에서 런타임 narrowing을 적용했다. 이어서 `tests/test_file_summarizer.py`의 파일 생성 반환값, 문자열 목록·file list fixture, protected helper 호출 경계를 명시해 테스트 경고를 제거했다. 파일 누락 표시·3단계 요약·mixed file type·rule-based LLM fallback semantics는 유지했다.
- 변경 소스/테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과, FileSummarizer 회귀 `14 passed` 및 누락 파일/LLM fallback 수동 smoke를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,108 warnings / 0 notes`다. 직전 집계 3,133건 대비 25건을 축소했으며, 다음 고경고 단위는 `tests/test_rag_retrieval_quality.py`, `tests/test_memory_recorder.py`, `tests/test_code_tree_indexer.py`, `tests/test_auth.py`, `.agent/skills/k-skill/scripts/test_zipcode_search.py`(각 26건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-file-summarizer-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 263 (2026-08-31)

- `.agent/skills/k-skill/scripts/test_zipcode_search.py`의 동적 zipcode helper import를 명시적 callable/Protocol 경계로 좁히고, mock subprocess command·JSON payload·fetcher lambda 타입을 구체화했다. 주소 파싱·공식 영문 주소 추출·blank query 거부·curl HTTPS/재시도 플래그·CLI JSON 직렬화 semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 스크립트 unittest `5 passed`를 확인했다. 주소 정규화·HTML parser·curl 안전 명령 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,082 warnings / 0 notes`다. 직전 집계 3,108건 대비 26건을 축소했으며, 다음 고경고 단위는 `tests/test_auth.py`, `tests/test_code_tree_indexer.py`, `tests/test_memory_recorder.py`, `tests/test_rag_retrieval_quality.py`(각 26건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-zipcode-search-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 264 (2026-08-31)

- `tests/test_auth.py`의 PBKDF2 timing loop 반환값, JWT private constant 접근, auth route/config 상태, pytest temporary-path fixture, TestClient JSON payload, rate-limit status 목록 경계를 구체화했다. 인증 semantics와 사용자 변경 범위는 유지하고 private state는 `getattr`/`setattr` 경계를 통해 테스트했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 인증 회귀 `20 passed`를 확인했다. PBKDF2 검증·JWT issue/verify·bearer parsing 직접 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,056 warnings / 0 notes`다. 직전 집계 3,082건 대비 26건을 축소했으며, 다음 고경고 단위는 `tests/test_code_tree_indexer.py`, `tests/test_memory_recorder.py`, `tests/test_rag_retrieval_quality.py`(각 26건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-auth-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 265 (2026-08-31)

- `tests/test_code_tree_indexer.py`의 private 언어별 정규식 fixture를 `re.Pattern[str]`로 명시적 취득하고, 테스트 프로젝트의 mkdir/write 반환값과 인덱스 구축 호출을 의도적으로 소비했다. Python/JS/Go/Rust/PHP/Ruby/Java 정규식 추출, 숨김·비인덱싱 디렉터리 제외, 캐시·검색·통계 semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 CodeTreeIndexer 회귀 `26 passed`를 확인했다. 임시 프로젝트 트리 구축과 관련도 검색 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,030 warnings / 0 notes`다. 직전 집계 3,056건 대비 26건을 축소했으며, 다음 고경고 단위는 `tests/test_memory_recorder.py`, `tests/test_rag_retrieval_quality.py`(각 26건)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-code-tree-indexer-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 266 (2026-08-31)

- `tests/test_memory_recorder.py`의 fake vault/manager 클래스에 `@final`, 상태 컬렉션, `write_note` kwargs, `stream_generate` 인자·iterator 반환 타입을 명시하고, 사용하지 않는 role/list 결과를 소비했다. preferred model 우선·default role fallback·memory write 호출 semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 MemoryRecorder 회귀 `2 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 3,004 warnings / 0 notes`다. 직전 집계 3,030건 대비 26건을 축소했으며, 다음 고경고 단위는 `tests/test_rag_retrieval_quality.py`(26), `tests/test_doctor.py` 및 `src/antigravity_k/api/routes/filesystem.py`(각 25)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-memory-recorder-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 267 (2026-08-31)

- `tests/test_rag_retrieval_quality.py`의 ordered vector-store fixture를 `Mapping`/`Sequence` 기반으로 타입화하고, metadata source 추출을 runtime-checkable Protocol로 좁혔다. private keyword helper 직접 호출을 public `mode="keyword"` 검색 계약으로 전환했으며 파일 쓰기·검색 반환값을 명시적으로 소비했다. snake_case tokenization·source diversity·stale filtering·executable chunk ranking·query expansion semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 RAG retrieval quality 회귀 `7 passed`를 확인했다. stale source filtering·provenance 경로 수동 smoke도 통과했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,978 warnings / 0 notes`다. 직전 집계 3,004건 대비 26건을 축소했으며, 다음 고경고 단위는 `tests/test_doctor.py` 및 `src/antigravity_k/api/routes/filesystem.py`(각 25), `tests/test_vision_dom_hybrid.py`(24)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-rag-retrieval-quality-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 268 (2026-08-31)

- `tests/test_doctor.py`의 capability probe fake를 `ModelProfile`·`ProviderCapability` 계약으로 명시하고, pytest monkeypatch·runtime double·CLI 입력 타입을 구체화했다. 로컬 모델 상태, 증폭 설정, vault/model registry/API key/port 검사 및 `agk run` runtime routing semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 doctor 회귀 `13 passed`를 확인했다. 실제 `uv run agk doctor`도 `16 passed · 3 warnings · 0 failed`로 실행됐다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,953 warnings / 0 notes`다. 직전 집계 2,978건 대비 25건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/api/routes/filesystem.py`(25), `tests/test_vision_dom_hybrid.py`(24), `tests/test_upgrade_phases.py`(23)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-test-doctor-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 269 (2026-08-31)

- `src/antigravity_k/api/routes/filesystem.py`의 `_require_allowed` 인자, 파일 검색 결과를 `TypedDict`로 구체화하고, workspace orchestrator/permission gate 연결부를 Protocol runtime narrowing으로 정리했다. `Query` 파라미터를 `Annotated`로 전환하고 경로 검증·background ingestion·cache invalidation·파일 CRUD/search 응답 타입을 명시했다. workspace 경계와 API semantics는 유지했다.
- 변경 모듈 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 filesystem endpoint/security 통합 회귀 `17 passed`를 확인했다. 단일 테스트 실행에서 ChromaDB worker 잠금 대기가 발생해 중복 프로세스를 종료한 뒤 재실행했으며 최종 실행은 정상 종료했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,928 warnings / 0 notes`다. 직전 집계 2,953건 대비 25건을 축소했으며, 다음 고경고 단위는 `tests/test_vision_dom_hybrid.py`(24), `tests/test_upgrade_phases.py`, `tests/test_tool_sandbox_coverage.py`, `tests/test_task_context_snapshot.py`, `tests/test_log_level_manager.py`, `scripts/prepare_hermes_dataset.py`(각 23)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-filesystem-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 270 (2026-08-31)

- `src/antigravity_k/api/routes/filesystem.py` 최종 2개 진단 지점(불필요한 Protocol `isinstance`, `asyncio.to_thread` 반환값 미소비)을 제거했다. 변경 모듈 LSP/basedpyright/Ruff 모두 `0 errors / 0 warnings`, py_compile 통과를 재확인했다.
- 파일시스템 endpoint/security 통합 회귀는 단일 재실행에서 `17 passed in 161.91s`로 통과했다. 앞선 중복 ChromaDB worker 잠금 대기 프로세스는 종료 후 재실행했으며, 코드 변경으로 인한 테스트 실패는 없었다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,928 warnings / 0 notes`다. 직전 기록과 동일한 기준선이며, 다음 고경고 단위는 `tests/test_vision_dom_hybrid.py`(24), `tests/test_upgrade_phases.py`, `tests/test_tool_sandbox_coverage.py`, `tests/test_task_context_snapshot.py`, `tests/test_log_level_manager.py`, `scripts/prepare_hermes_dataset.py`(각 23)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-filesystem-final.log`에 보관했다. 사용자 변경 234건을 포함한 기존 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 271 (2026-08-31)

- `tests/test_vision_dom_hybrid.py`에서 private VisionDOMHybrid 메서드 호출을 typed `getattr`/`Callable` helper로 경계화해 `reportPrivateUsage` 24건을 제거했다. LSP/basedpyright/Ruff `0 errors / 0 warnings`, py_compile 통과 및 vision/DOM 회귀 `38 passed`를 확인했다.
- `tests/test_upgrade_phases.py`에서 RAG/CoV protected helper 호출을 typed helper로 전환하고, 벡터 저장소 fake·요약/RAG callback·CognitiveLoop step history·문자열 연결을 명시적으로 타입화했다. LSP/basedpyright/Ruff `0 errors / 0 warnings`, py_compile 통과 및 upgrade phases 회귀 `14 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,881 warnings / 0 notes`다. 직전 집계 2,928건 대비 47건을 축소했으며, 다음 고경고 단위는 `tests/test_tool_sandbox_coverage.py`, `tests/test_task_context_snapshot.py`, `tests/test_log_level_manager.py`, `scripts/prepare_hermes_dataset.py`(각 23), `tests/test_reflection.py`, `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-upgrade-phases-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 272 (2026-08-31)

- `tests/test_tool_sandbox_coverage.py`의 ALLOWLIST 문자열 연결과 임시 파일 fixture에 타입을 명시하고, `Path.write_text` 반환값을 의도적으로 소비했다. AST 기반 subprocess/os/asyncio/pty 실행 경로 탐지 semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 sandbox coverage 회귀 `8 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,858 warnings / 0 notes`다. 직전 집계 2,881건 대비 23건을 축소했으며, 다음 고경고 단위는 `tests/test_task_context_snapshot.py`, `tests/test_log_level_manager.py`, `scripts/prepare_hermes_dataset.py`(각 23), `tests/test_reflection.py`, `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tool-sandbox-coverage-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 273 (2026-08-31)

- `tests/test_task_context_snapshot.py`의 pytest `tmp_path` fixture를 `Path`로 타입화하고, task 생성·snapshot 저장·execution event 기록의 반환값을 명시적으로 소비했다. snapshot round-trip, cross-scope memory 제거, provider metadata 필터링, developer role 보존 semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 task context snapshot 회귀 `4 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,835 warnings / 0 notes`다. 직전 집계 2,858건 대비 23건을 축소했으며, 다음 고경고 단위는 `tests/test_log_level_manager.py`, `scripts/prepare_hermes_dataset.py`(각 23), `tests/test_reflection.py`, `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-task-context-snapshot-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 274 (2026-08-31)

- `tests/test_log_level_manager.py`의 `_normalize_level`/`_get_level_name` private classmethod 호출을 typed helper로 경계화하고, logger discovery 결과를 구체 타입으로 좁혔다. logging level/debug mode 테스트의 반환값 소비도 명시했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 log level manager 회귀 `20 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,812 warnings / 0 notes`다. 직전 집계 2,835건 대비 23건을 축소했으며, 다음 고경고 단위는 `scripts/prepare_hermes_dataset.py`(23), `tests/test_reflection.py`, `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-log-level-manager-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 275 (2026-08-31)

- `scripts/prepare_hermes_dataset.py`에 `DatasetEntry`/`ChatMessage`/`ChatMLRecord` 타입 별칭과 conversation 정규화 경계를 추가하고, argparse 경로·JSON 입력·파일 쓰기 반환값을 명시적으로 처리했다. human/gpt 역할 매핑과 JSONL 변환 semantics는 유지하며 비정상 conversation shape는 빈 messages로 안전하게 변환한다.
- 변경 스크립트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 임시 입력을 이용한 실제 CLI 변환 smoke를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,789 warnings / 0 notes`다. 직전 집계 2,812건 대비 23건을 축소했으며, 다음 고경고 단위는 `tests/test_reflection.py`, `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-prepare-hermes-dataset-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 276 (2026-08-31)

- `tests/test_reflection.py`의 subprocess patch를 typed process-result fake/side-effect로 전환하고, model manager generate double과 private `_synthesize_skill` 호출을 명시적 Callable 경계로 정리했다. diff 회고·KI 저장·auto-skill 합성/구문 오류 처리 semantics는 유지했다.
- 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 reflection 회귀 `7 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,767 warnings / 0 notes`다. 직전 집계 2,789건 대비 22건을 축소했으며, 다음 고경고 단위는 `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-reflection-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 278 (2026-08-31)

- `tests/test_egress_policy.py`의 검증 호출 반환값, pytest `MonkeyPatch`, DNS 거부 fake, `urlopen` fake 경계를 명시적으로 타입화했다. 로컬 허용·비공개 대상 차단·DNS 실패·sync/async hook 검증 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 egress policy 회귀 `6 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,745 warnings / 0 notes`다. 직전 집계 2,767건 대비 22건을 축소했으며, 다음 고경고 단위는 `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-egress-policy-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 279 (2026-08-31)

- `tests/test_diff_engine.py`의 `tmp_path` fixture를 `Path`로 타입화하고 파일 쓰기 반환값을 명시적으로 소비했다. apply-patch 포맷 파싱·정확/퍼지 hunk 적용·신규/삭제·다중 파일 통합 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 diff engine 회귀 `19 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,723 warnings / 0 notes`다. 직전 집계 2,745건 대비 22건을 축소했으며, 다음 고경고 단위는 `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-diff-engine-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 277 (2026-08-31)

- `tests/test_reflection.py`의 typed process-result/model-manager double과 private synthesis helper 경계를 반영한 전체 진단을 재실행했다. 변경 테스트 LSP·basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 reflection 회귀 `7 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,767 warnings / 0 notes`다. 직전 집계 2,789건 대비 22건을 축소했으며, 다음 고경고 단위는 `tests/test_egress_policy.py`, `tests/test_diff_engine.py`, `tests/test_cov_revise_loop.py`, `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-reflection-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 280 (2026-08-31)

- `tests/test_cov_revise_loop.py`의 CoV generator factory 및 AST 검증 callback에 `Callable`/입출력 타입을 지정하고 `ast.parse` 반환값을 소비했다. revise→verify 폐루프, 조기 종료, 최대 반복, 짧은 응답 skip semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 CoV 회귀 `7 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,701 warnings / 0 notes`다. 직전 집계 2,723건 대비 22건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/multiplexer.py`, `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-cov-revise-loop-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 281 (2026-08-31)

- `src/antigravity_k/engine/multiplexer.py`의 런타임 경계를 `AgentRuntime` Protocol로 명시하고, 목표 입력을 `Sequence[Mapping[str, object]]`로 수용한 뒤 task id/instruction을 안전하게 문자열로 좁혔다. task 목록·결과·to_thread 반환값·클래스 속성을 타입화했으며 병렬 worktree/실패 격리 semantics는 유지했다.
- 변경 모듈 및 multiplexer 회귀 경로 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과, multiplexer+agent runtime 회귀 `44 passed`를 확인했다. 의존 모듈 `agent_runtime.py`의 기존 경고 7건은 별도 잔여 debt로 남겼다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,679 warnings / 0 notes`다. multiplexer 22건을 제거했으며, 다음 고경고 단위는 `src/antigravity_k/engine/extraction_ab_test.py`, `src/antigravity_k/api/routes/security_api.py`(각 22)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-multiplexer-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 282 (2026-08-31)

- `src/antigravity_k/engine/extraction_ab_test.py`의 A/B 필드 값 경계를 `object | None`으로 정리하고 구식 `Optional`/`Any`를 제거했으며, extractor 속성과 markdown 문자열 연결을 명시적으로 타입화했다. 추출 비교·정확도 집계·Markdown/JSON 보고서 semantics는 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 extraction A/B 회귀 `27 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,657 warnings / 0 notes`다. 직전 집계 2,679건 대비 22건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/api/routes/security_api.py`(22), `tests/test_server_stream.py`, `tests/test_semantic_dom.py`, `tests/test_critic_routing.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-extraction-ab-test-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 283 (2026-08-31)

- `src/antigravity_k/api/routes/security_api.py`의 Permission import를 공개 계약 위치로 수정하고, shields-down 요청을 Pydantic strict 모델로 파싱했다. YAML 설정은 `TypeAdapter` 기반 typed section으로 읽고, 세션 singleton은 dependencies의 공개 alias를 통해 연결했으며 Shields 상태 반환값을 명시적으로 소비했다.
- 변경 route/dependency 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 보안·shields·health API 회귀 `9 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,635 warnings / 0 notes`다. 직전 집계 2,657건 대비 22건을 축소했으며, 다음 고경고 단위는 `tests/test_server_stream.py`, `tests/test_semantic_dom.py`, `tests/test_critic_routing.py`, `tests/test_browser_surfing_agent.py`, `src/antigravity_k/tools/claim_grounding_benchmark.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-security-api-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 284 (2026-08-31)

- `tests/test_server_stream.py`의 fake manager와 CEO stream monkeypatch를 `Iterator`/명시적 매개변수 타입으로 정리하고 사용하지 않는 인자는 underscore로 표시했다. 스트리밍 chunk 생성과 SSE JSON 직렬화 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 server stream 회귀 `1 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,614 warnings / 0 notes`다. 직전 집계 2,635건 대비 21건을 축소했으며, 다음 고경고 단위는 `tests/test_semantic_dom.py`, `tests/test_critic_routing.py`, `tests/test_browser_surfing_agent.py`, `src/antigravity_k/tools/claim_grounding_benchmark.py`, `src/antigravity_k/engine/task_events.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-server-stream-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 285 (2026-08-31)

- `tests/test_semantic_dom.py`의 private parser/scorer 호출을 명시적 `Callable` 경계 헬퍼로 감싸 `SemanticDOMParser._intent_match_score` 및 `_parse_element`의 protected-member 경고 21건을 제거했다. 시맨틱 DOM 역할 파싱·의도 점수·snapshot 회귀 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 semantic DOM 회귀 `67 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,593 warnings / 0 notes`다. 직전 집계 2,614건 대비 21건을 축소했으며, 다음 고경고 단위는 `tests/test_critic_routing.py`, `tests/test_browser_surfing_agent.py`, `src/antigravity_k/tools/claim_grounding_benchmark.py`, `src/antigravity_k/engine/task_events.py`, `src/antigravity_k/engine/log_level_manager.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-semantic-dom-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 286 (2026-08-31)

- `tests/test_critic_routing.py`의 CoV 설정 private 접근과 MagicMock 체인을 명시적 `Callable`/`Mapping` 경계 헬퍼로 정리하고, 사용하지 않는 generator 결과를 `_`로 소비했다. critic-swarm 로딩·집단지성 critic 라우팅·CoV 단일 모델 라우팅 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 critic routing 회귀 `5 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,572 warnings / 0 notes`다. 직전 집계 2,593건 대비 21건을 축소했으며, 다음 고경고 단위는 `tests/test_browser_surfing_agent.py`, `src/antigravity_k/tools/claim_grounding_benchmark.py`, `src/antigravity_k/engine/task_events.py`, `src/antigravity_k/engine/log_level_manager.py`, `src/antigravity_k/engine/ceo_analyzer.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-critic-routing-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 287 (2026-08-31)

- `tests/test_browser_surfing_agent.py`의 fixture·Playwright/manager mock 경계를 `MagicMock`/`AsyncMock` 및 명시적 callable·mapping 타입으로 정리하고, private `_decide_next_action` 호출과 call arguments를 타입 안전 헬퍼로 감쌌다. 브라우저 surf 추출 흐름, navigation 및 vision target 전달 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 browser surfing 회귀 `3 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,551 warnings / 0 notes`다. 직전 집계 2,572건 대비 21건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/tools/claim_grounding_benchmark.py`, `src/antigravity_k/engine/task_events.py`, `src/antigravity_k/engine/log_level_manager.py`, `src/antigravity_k/engine/ceo_analyzer.py`, `src/antigravity_k/engine/approval_manager.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-browser-surfing-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 288 (2026-08-31)

- `src/antigravity_k/tools/claim_grounding_benchmark.py`의 JSON fixture 경계를 `list[object]`/`Mapping[str, object]`로 좁히고 source URL·freshness, conflict group, expected 값의 런타임 검증을 명시화했다. response mapping의 불필요한 key 검증도 제거해 claim grounding 평가 semantics는 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 claim grounding 회귀 `3 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,530 warnings / 0 notes`다. 직전 집계 2,551건 대비 21건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/task_events.py`, `src/antigravity_k/engine/log_level_manager.py`, `src/antigravity_k/engine/ceo_analyzer.py`, `src/antigravity_k/engine/approval_manager.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-claim-grounding-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 289 (2026-08-31)

- `src/antigravity_k/engine/task_events.py`의 SQLite 실행 결과를 명시적으로 소비하고, row 조회 결과와 이벤트 필드 변환을 `sqlite3.Row`/`object` 경계로 정리했다. SQL 조합은 명시적 결합으로 바꿔 implicit-concatenation 경고를 제거했으며 이벤트 스키마 초기화·append·list semantics는 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 task event/state/API 회귀 `19 passed, 32 deselected`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,509 warnings / 0 notes`다. 직전 집계 2,530건 대비 21건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/log_level_manager.py`, `src/antigravity_k/engine/ceo_analyzer.py`, `src/antigravity_k/engine/approval_manager.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-task-events-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 290 (2026-08-31)

- `src/antigravity_k/engine/log_level_manager.py`의 클래스 속성·logger dictionary·설정 결과를 `ClassVar`, `Mapping`, `TypedDict` 계약으로 구체화하고 동적 logging API의 반환 구조를 명시했다. debug mode 저장·복원 및 전체 logger discovery semantics는 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 log-level manager 회귀 `20 passed`를 확인했다. 반환값 일반화로 발생한 소비자 오류 5건은 TypedDict 결과 계약으로 해소했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,488 warnings / 0 notes`다. 직전 집계 2,509건 대비 21건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/ceo_analyzer.py`, `src/antigravity_k/engine/approval_manager.py`(각 21)다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-log-level-manager-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 291 (2026-08-31)

- `src/antigravity_k/engine/ceo_analyzer.py`의 모델 매니저 경계를 Protocol로 명시하고, 스트리밍 청크를 `str`로 고정했다. JSONDecoder·`json.loads` 결과는 `object` 경계에서 검증해 `JsonObject`로 변환하고, Python 3.10 union 문법을 적용해 deprecated/explicit Any/unknown 경고를 제거했다. 모델 매니저가 없는 경우 기존 최종 폴백 경로를 유지한다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 오케스트레이터 회귀 `13 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,469 warnings / 0 notes`다. 직전 집계 2,488건 대비 19건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/approval_manager.py`다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-ceo-analyzer-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 292 (2026-08-31)

- `src/antigravity_k/engine/approval_manager.py`의 승인 요청 인자와 diff-preview 입력을 `pydantic.JsonValue` 기반으로 구체화하고, API 직렬화 결과를 `_ApprovalRequestPayload`/`_AutoReviewPayload` TypedDict로 고정했다. Future 타임아웃은 `asyncio.timeout`으로 유지하면서 `ApprovalStatus` 반환 타입을 보장했고, 문자열 인자 파싱으로 경로·패치·파일 내용 처리 semantics를 보존했다.
- 변경 모듈 및 소비 테스트 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 승인 관리자/리뷰/API 회귀 `51 passed`를 확인했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,448 warnings / 0 notes`다. 직전 집계 2,469건 대비 21건을 축소했으며, 다음 고경고 단위는 20개 수준의 `src/antigravity_k/tui/widgets.py`, `src/antigravity_k/engine/orchestrator/setup.py`, `src/antigravity_k/engine/mcp_capability.py`, `src/antigravity_k/engine/immune_system.py` 및 관련 테스트다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-approval-manager-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 293 (2026-08-31)

- `src/antigravity_k/tui/widgets.py`의 메시지·입력·컨테이너·모달 위젯을 `@final`/`@override`로 명시하고, Textual 이벤트 처리·child 제거·mount 반환값을 의도적으로 소비하도록 정리했다. 기존 명령 자동완성, 버튼 게시, 상태 footer, progress overlay 동작과 렌더링 구조는 변경하지 않았다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 TUI Ctrl+C 상호작용 회귀 `6 passed`를 확인했다. 타입 전용 변경으로 별도 시각 캡처는 불필요하며, 기존 TUI 렌더링 구조를 유지했다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,428 warnings / 0 notes`다. 직전 집계 2,448건 대비 20건을 축소했으며, 다음 고경고 단위는 `src/antigravity_k/engine/orchestrator/setup.py`, `src/antigravity_k/engine/mcp_capability.py`, `src/antigravity_k/engine/immune_system.py` 및 관련 테스트다.
- 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tui-widgets-final.log`에 보관했다. 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert하지 않는다. 전역 경고 억제 지시문도 추가하지 않는다.

## Warning debt continuation 294 (2026-08-31)

- TUI 키 이벤트의 `if/elif` 변형 분기 2건을 독립 조기 반환으로 정리해 프로젝트 no-excuse 규칙 위반을 제거했다. Ctrl+Space·Tab·Enter 처리와 이벤트 중지 semantics는 그대로 유지했다.
- 변경 파일 no-excuse audit는 `no violations in 1 file(s)`, basedpyright·Ruff `0 errors / 0 warnings`, py_compile 통과 및 TUI 회귀 `6 passed`를 재확인했다.
- 전체 basedpyright는 `0 errors / 2,428 warnings / 0 notes`로 오류 없이 유지됐다. 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-tui-widgets-final.log`를 사용한다.

## Warning debt continuation 295 (2026-08-31)

- `src/antigravity_k/engine/orchestrator/setup.py`의 설정·manager·선택 컴포넌트 초기화 경계를 `Mapping[str, JsonValue]`, Protocol, 구체적 반환 타입으로 정리했다. `TYPE_CHECKING` 타입은 지연 어노테이션으로 안전하게 처리했고, 기존 optional 초기화 실패 시 fallback 동작은 유지했다.
- `src/antigravity_k/engine/fact_appender.py`의 manager/vault/session fact 타입과 반환 경계를 명시해 setup 호출부의 부분 미정의 경고를 근본적으로 제거했다. basedpyright·Ruff `0 errors / 0 warnings`, py_compile 및 no-excuse audit `no violations in 2 file(s)`를 확인했다.
- 오케스트레이터·watchdog·self-evolution 회귀 `116 passed`, FactAppender 연계 회귀 `20 passed`를 확인했다. 최신 전체 basedpyright는 `0 errors / 2,390 warnings / 0 notes`로 직전 2,428건 대비 38건을 축소했다. 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-setup-final.log`에 보관했다.
- 사용자 변경 234건을 포함한 기존 dirty path는 보존하며 stage·revert·commit하지 않았다. 다음 우선순위는 `src/antigravity_k/engine/mcp_capability.py`와 `src/antigravity_k/engine/immune_system.py`(각 20 warnings)다.

## Warning debt continuation 296 (2026-08-31)

- `src/antigravity_k/engine/mcp_capability.py`의 JSON 설정 경계를 Pydantic `JsonValue`로 파싱하고, 비정형 호출자도 Protocol 입력으로 받아 내부에서 안전하게 정규화했다. `mcp_capability_models.py`, `mcp_capability_catalog.py`, `mcp_capability_parsing.py`로 모델·정적 카탈로그·파싱 책임을 분리해 본 모듈을 249 pure LOC 이하로 유지했다.
- 변경 4개 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 및 no-excuse audit `no violations in 4 file(s)`를 확인했다. MCP capability/session/tool-loader/slash-command 회귀는 `103 passed`다.
- 최신 전체 basedpyright는 `0 errors / 2,370 warnings / 0 notes`로 직전 2,390건 대비 20건을 축소했다. 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-mcp-capability-final.log`에 보관했다.
- 기존 사용자 변경과 dirty path는 계속 보존하며 stage·revert·commit하지 않았다. 다음 우선순위는 `src/antigravity_k/engine/immune_system.py`와 20-warning 테스트 모듈들이다.

## Warning debt continuation 297 (2026-08-31)

- `src/antigravity_k/engine/immune_system.py`의 모델 응답 JSON을 Pydantic `JsonValue` 경계에서 검증하고, 인스턴스 속성·패치 문자열·AST 결과의 타입을 명시했다. 보호 멤버 `_registry` 접근은 공개 `get_target_for_role()` 경로로 대체했으며, 스냅샷·수복 단계의 broad exception을 구체적인 예외 묶음으로 좁혔다.
- 자가수복 대상 경로는 `src/antigravity_k/` 하위로 제한하고 절대 경로·`..` 탈출을 차단했다. 기존 자동 패치 적용 및 패치 이력 기록 semantics는 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, py_compile 및 no-excuse audit `no violations in 1 file(s)`를 확인했다. 실제 임시 프로젝트에서 정상 패치 적용과 경로 탈출 차단을 검증했고, 면역·도구 실행기 회귀는 `36 passed`다.
- 최신 전체 basedpyright는 `0 errors / 2,023 warnings / 0 notes`이며 전체 진단 로그는 `/tmp/antigravity-k-basedpyright-immune-final.log`에 보관했다. 직전 집계 2,370건 대비 347건을 축소했다. 다음 우선순위는 `tests/test_amplification_config.py`, `tests/test_skills_registry.py`, `tests/test_unsloth_training.py` 및 `src/antigravity_k/api/dependencies.py` 등 19~20 warning 단위다.
- 기존 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert·commit하지 않았다. 전역 경고 억제 지시문은 추가하지 않았다.

## Warning debt continuation 305 (2026-08-31)

- 코드 트리 인덱서의 모델·심볼 추출 책임을 `code_tree_indexer_models.py`와 `code_tree_symbol_extractor.py`로 분리하고, `code_tree_indexer.py`에는 인덱싱·검색·통계 조정 책임만 남겼다. 기존 정규식 별칭과 `FileSymbols` 공개 접근 경로를 유지했다.
- provider capability 진단을 `provider_capability_models.py`, `provider_capability_probe.py`, `provider_capability_probe_runtime.py`, `provider_capability_probe_utils.py`로 분리하고 `provider_capabilities.py`에는 공개 호환 계층과 remediation hint만 남겼다. `safe_urlopen` 패치 경계와 provider probe semantics를 유지했다.
- 연계 Protocol의 `stats()` 반환 계약을 `CodeTreeStats`로 구체화해 전체 타입 오류를 제거했다. 구조 분리 대상 10개 파일의 basedpyright는 `0 errors / 0 warnings / 0 notes`, Ruff는 `All checks passed`, no-excuse audit는 `no violations in 10 file(s)`, py_compile은 성공했다.
- 코드 트리·provider capability·orchestrator 회귀 테스트는 `63 passed`(0.85s)였고, 임시 샘플 파일을 이용한 CodeTreeIndexer build/search/stats 수동 드라이버도 `code_tree_manual_qa=pass`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 2,124 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-structural-split-final.log`에 보관했다. 잔여 2,124건은 이번 구조 분리 범위 밖의 기존 경고 부채로 다음 배치에서 처리한다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 이번 단계에서는 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 303 (2026-08-31)

- `.agent/skills/k-skill/korean-scholarship-search/scripts/university_search_plan.py`의 재귀 JSON 결과를 PEP 695 `JsonValue` 계약으로 고정하고, argparse 결과를 typed namespace로 검증했다. 모든 parser 반환값을 명시적으로 소비해 CLI 인자·전국/학교 검색 JSON 계약을 유지했다.
- 변경 스크립트 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse·py_compile 통과를 확인했다. `--nationwide --year 2026` 및 학교·학과·단과대 필터 경로를 실제 CLI로 실행해 JSON 계약을 검증했다. 순수 LOC는 188이다.

## Warning debt continuation 304 (2026-08-31)

- `.agent/skills/k-skill/scripts/k_skill_cleaner.py` 호환 래퍼의 동적 `_MODULE` 속성을 `_AgentUsageSource`/`_CleanupCandidate` TypedDict와 `_CleanerModule` Protocol로 명시하고 argparse 반환 타입·CSV 결과 타입을 실제 helper 계약에 맞췄다. standalone helper 로딩 및 기존 re-export/CLI semantics는 유지했다.
- 변경 스크립트 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse·py_compile 통과 및 cleaner 회귀 `8 passed`를 확인했다. 순수 LOC는 65이다.
- 최신 전체 basedpyright는 현재 저장소 전체 범위(`.`)에서 `0 errors / 2,200 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-university-cleaner-final.log`에 보관했다. 직전 집계 2,239건 대비 39건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert·commit하지 않았다. 전역 경고 억제 지시문은 추가하지 않았다.

## Warning debt continuation 302 (2026-08-31)

- `.agent/skills/k-skill/coupang-product-search/scripts/coupang_partners_mcp.py`의 argparse 결과를 typed namespace로 고정하고 `Sequence`·subprocess·환경변수 반환값을 명시적으로 소비했다. upstream checkout 오류 안내와 인자 전달 semantics는 유지했다.
- 변경 스크립트 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse·py_compile 통과 및 wrapper 회귀 `10 passed, 1 skipped`를 확인했다. 순수 LOC는 155다.
- 최신 전체 basedpyright는 `0 errors / 2,239 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-coupang-final.log`에 보관했다. 직전 2,259건 대비 20건을 축소했다.

## Warning debt continuation 298 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_handler_config.py`의 amplification/CoV 설정 독자를 `Mapping[str, JsonValue]` 기반 계약으로 정리하고, verification handler가 공개 `cov_settings` 경계를 직접 호출하도록 수정했다. 설정 파일의 dict 접근 및 CoV 동작 semantics는 유지했다.
- `tests/test_amplification_config.py`와 CognitiveLoop 관련 변경을 포함한 타입 검증에서 basedpyright·Ruff `0 errors / 0 warnings`, CoV/런타임 회귀 `21 passed`를 확인했다.

## Warning debt continuation 299 (2026-08-31)

- `tests/test_skills_registry.py`의 임시 경로·파일 생성 및 예외 검증을 명시적 타입과 `pytest.raises`로 정리했다. skills registry discovery/profile 오류 semantics는 유지했다.
- 변경 테스트 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit 통과 및 registry 회귀 `4 passed`를 확인했다.

## Warning debt continuation 300 (2026-08-31)

- `tests/test_unsloth_training.py`의 동적 `MagicMock`/`AsyncMock` 경계를 typed recorder/session double로 교체하고, 이를 `tests/test_unsloth_training_doubles.py`로 분리했다. 학습·세션 호출 순서와 결과 검증 semantics는 유지했다.
- 두 테스트 모듈 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit 통과 및 Unsloth 회귀 `7 passed`를 확인했다.

## Warning debt continuation 301 (2026-08-31)

- `src/antigravity_k/api/dependencies.py`의 ModeManager singleton, project-memory 경로, search-cache JSON, graph/vector export, slash-runtime 바인딩 경계를 구체적인 타입·Pydantic JSON 검증·Protocol로 정리했다. 재귀 JSON alias는 PEP 695로 정의해 import 시 Pydantic recursion 오류를 방지했고, 캐시 보존/삭제 및 runtime bind 동작은 유지했다.
- 변경 모듈 및 연계 handler basedpyright·Ruff `0 errors / 0 warnings`, runtime bind `1 passed`, durable memory/compliance `20 passed`, API slash/chat `5 passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 2,259 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-dependencies-final.log`에 보관했다. 직전 원장 수치와의 차이는 사용자 dirty 범위 확장으로 인한 전역 스캔 대상 변동이며, 이번 변경 파일의 경고는 0건이다.
- 기존 사용자 변경 234건과 나머지 dirty path는 계속 보존하며 stage·revert·commit하지 않았다. 전역 경고 억제 지시문은 추가하지 않았다.

## Warning debt continuation 306 (2026-08-31)

- `src/antigravity_k/engine/code_intel/knowledge_graph.py`의 노드·엣지·통계 경계를 `JsonValue`, `TypedDict`, `Mapping`으로 구체화하고 입력 properties를 복사해 원본 변이를 제거했다. NodeType 저장값과 조회·집계 semantics는 유지했다.
- `src/antigravity_k/engine/code_intel/pipeline.py`의 단계별 결과를 TypedDict로 고정하고 graph/repo 경계, 파일 목록, force 인자, AST 파싱 예외를 명시적으로 처리했다. 파이프라인 실행 결과와 mock node 보강 semantics는 유지했다.
- 두 모듈 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit `no violations in 2 file(s)`, py_compile 통과를 확인했다. 코드 인텔리전스 회귀는 `15 passed`였고 임시 Python 프로젝트 실행 드라이버도 `code_intel_pipeline_manual_qa=pass`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 2,085 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-code-intel-final.log`에 보관했다. 직전 2,124건 대비 39건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 445 (2026-08-31)

- API lifespan의 RAG 자동 인덱싱이 동기 `index_project()`를 이벤트 루프에서 실행해 TestClient startup을 약 9초 차단하던 문제를 확인하고, 중복 실행을 억제하는 daemon background thread로 분리했다. 수동 QA에서 startup `0.025s`, shutdown `0.622s`, `/v1/health` `200`을 확인했다.
- 테스트 double과 실제 런타임 경계의 호환성을 보완했다: CoV 설정 reader가 `config` 없는 최소 orchestrator를 안전하게 처리하고, provider endpoint 설정의 비문자 mock 값을 기본값으로 정규화하며, `/v1/models/operations`는 동적 capability payload를 응답 모델 검증으로 오탐하지 않도록 `response_model=None`을 명시했다.
- 관련 실패 재현 테스트 `14 passed`, API 회귀 `36 passed, 2 skipped`, 전체 회귀 `4821 passed, 6 skipped` (실패 0)로 완주했다.
- 최신 전체 소스 basedpyright는 `/tmp/final-zero-warnings.log` 기준 `0 errors / 0 warnings / 0 notes`; 변경 파일 Ruff·py_compile 및 `git diff --check`도 통과했다. 전체 worktree diff의 기존 `src/antigravity_k/engine/logger.py:62` trailing whitespace는 사용자 변경으로 보존했다.
- 기존 사용자 변경 234건을 포함한 dirty path를 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 443 (2026-08-31)

- `src/antigravity_k/engine/working_memory_compactor.py`의 입력 메시지를 `Sequence[Mapping[str, object]]`로 일반화해 기존 `list[dict[str, str]]` 호출자와의 불변성 충돌을 해소하면서 `Any` 전파 5건을 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. working memory 회귀 `3 passed` 및 파일 추적·실패 요약 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 3 warnings / 0 notes`이며 로그는 `/tmp/working-memory-full-final.log`에 보관했다. 직전 8건 대비 5건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 442 (2026-08-31)

- `src/antigravity_k/engine/vram_kv_throttler.py`의 threshold 속성을 타입 선언하고 메시지 payload를 `object` 값으로 제한해 명시적 `Any` 3건을 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. VRAM throttler 회귀 `1 passed` 및 고압력 메시지 pruning 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 8 warnings / 0 notes`이며 로그는 `/tmp/vram-full.log`에 보관했다. 직전 11건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 441 (2026-08-31)

- `src/antigravity_k/engine/vault_privacy_derivatives.py`에서 Vault RAG 벡터 저장소·청커용 Protocol 경계를 추가하고 JSON 메타데이터를 `dict[str, object]`로 제한해 동적 `Any` 전파 5건을 제거했다. 기존 `VaultEngine` 구조와 호환되도록 동적 속성은 명시적 cast 경계에서만 읽는다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. vault privacy 회귀 `15 passed` 및 derivative metadata 경계 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 11 warnings / 0 notes`이며 로그는 `/tmp/vault-privacy-full-final.log`에 보관했다. 직전 16건 대비 5건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 440 (2026-08-31)

- `src/antigravity_k/engine/universal_compiler_bridge.py`의 Python/YAML 파서 호출과 bracket pop 반환값을 의도적으로 소비해 미사용 결과 경고를 제거했다. JSON/YAML 동작은 그대로 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. universal compiler 회귀 `4 passed` 및 Python/JSON/TypeScript 검증 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 16 warnings / 0 notes`이며 로그는 `/tmp/universal-compiler-full.log`에 보관했다. 직전 18건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 439 (2026-08-31)

- `src/antigravity_k/engine/tool_executor.py`의 이미 `object`인 스키마 조회 결과에 대한 불필요한 cast를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. tool executor 회귀 `25 passed` 및 공개 executor import 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 18 warnings / 0 notes`이며 로그는 `/tmp/tool-executor-full.log`에 보관했다. 직전 19건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 438 (2026-08-31)

- `src/antigravity_k/engine/tool_evidence_compactor.py`의 정규식을 raw triple-quoted 문자열로 명시하고 JSON 메타데이터를 `object`/`dict[str, object]` 경계로 캐스팅해 경고를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. evidence compactor 회귀 `4 passed` 및 메타데이터 정렬·긴 결과 축약 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 19 warnings / 0 notes`이며 로그는 `/tmp/tool-evidence-full.log`에 보관했다. 직전 21건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 437 (2026-08-31)

- `src/antigravity_k/engine/tokenizer.py`의 클래스 상수를 `ClassVar[int]`으로 선언하고 캐시 확장 시 `dict[str, str | int]` cast를 사용해 명시적 `Any`를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. tokenizer 회귀 `9 passed` 및 CJK 토큰 캐시 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 21 warnings / 0 notes`이며 로그는 `/tmp/tokenizer-full.log`에 보관했다. 직전 23건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 436 (2026-08-31)

- `src/antigravity_k/engine/task_state_types.py`의 전이/상태 예외 필드와 생성자 반환 타입을 명시했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. task state 회귀 `21 passed` 및 상태 파싱·예외 필드 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 23 warnings / 0 notes`이며 로그는 `/tmp/task-state-types-full.log`에 보관했다. 직전 27건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 435 (2026-08-31)

- `src/antigravity_k/engine/task_state_store.py`의 WAL PRAGMA 결과를 타입이 지정된 cast로 소비해 `Any` 경고를 제거했다. fetchone을 유지해 SQLite cursor가 열린 상태로 남지 않도록 동작 회귀도 방지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. task state store·runner 회귀 `23 passed` 및 임시 DB 생성/조회 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 27 warnings / 0 notes`이며 로그는 `/tmp/task-state-store-full.log`에 보관했다. 직전 28건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 434 (2026-08-31)

- `src/antigravity_k/engine/symbol_navigator.py`의 `project_root` 속성과 초기 인덱싱 호출 결과를 명시적으로 처리했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. symbol navigator 회귀 `1 passed` 및 실제 심볼 검색 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 28 warnings / 0 notes`이며 로그는 `/tmp/symbol-navigator-full.log`에 보관했다. 직전 30건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 433 (2026-08-31)

- `src/antigravity_k/engine/subgoal_graph.py`의 결과 필드를 `object | None`으로 제한하고 그래프 목표 속성 및 완료 결과 인자를 명시적으로 타입 선언했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. subgoal graph 회귀 `3 passed` 및 의존성 readiness 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 30 warnings / 0 notes`이며 로그는 `/tmp/subgoal-full.log`에 보관했다. 직전 34건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 432 (2026-08-31)

- `src/antigravity_k/engine/subagent_execution.py`의 상태 이벤트 기록 4곳에서 반환값을 의도적으로 무시함을 `_ =`로 명시했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. subagent 회귀 `14 passed` 및 컨텍스트 없는 스트림 전달 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 34 warnings / 0 notes`이며 로그는 `/tmp/subagent-execution-full.log`에 보관했다. 직전 38건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 431 (2026-08-31)

- `src/antigravity_k/engine/static_type_security_gate.py`에서 AST 순회 노드를 `ast.Call`로 좁힌 뒤 직접 `keywords`를 순회하도록 바꿔 `Any` 전파 3건을 제거했다. 보안 탐지 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. static security gate 회귀 `4 passed` 및 `shell=True` 탐지 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 38 warnings / 0 notes`이며 로그는 `/tmp/static-gate-full.log`에 보관했다. 직전 41건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 430 (2026-08-31)

- `src/antigravity_k/engine/speculative_branching.py`의 worktree cleanup subprocess 결과를 명시적으로 소비하고 `project_root` 속성을 타입 선언했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. speculative branching 회귀 `10 passed` 및 tempdir 승자 선택 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 41 warnings / 0 notes`이며 로그는 `/tmp/speculative-full.log`에 보관했다. 직전 43건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 429 (2026-08-31)

- `src/antigravity_k/engine/smart_breakpoint.py`의 failure threshold 관련 인스턴스 속성에 명시적 타입을 추가했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Smart breakpoint 회귀 `1 passed` 및 다중 실패 후 대화형 선택지 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 43 warnings / 0 notes`이며 로그는 `/tmp/smart-breakpoint-full.log`에 보관했다. 직전 45건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 428 (2026-08-31)

- `src/antigravity_k/engine/self_consistency.py`의 복잡도 게이트 import를 공개된 `chain_of_verification_models` 경로로 교정했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. self-consistency 및 amplification 회귀 전체 통과, 다수결 선택 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 45 warnings / 0 notes`이며 로그는 `/tmp/self-consistency-full.log`에 보관했다. 직전 46건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 427 (2026-08-31)

- `src/antigravity_k/engine/reflexion_memory.py`의 `max_episodes` 속성에 명시적 타입을 추가하고, episode eviction의 반환값을 의도적으로 무시함을 명시했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Reflexion 회귀 `2 passed` 및 용량 제한·clear 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 46 warnings / 0 notes`이며 로그는 `/tmp/reflexion-full.log`에 보관했다. 직전 48건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 426 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/unsloth_training_mcp.py`의 세 인스턴스 속성에 명시적 타입을 부여하고, 이미 exhaustive한 원격 작업 상태 분기의 불필요한 `assert_never` arm을 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Unsloth training 회귀 `7 passed` 및 미설정 토큰 거부 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 48 warnings / 0 notes`이며 로그는 `/tmp/unsloth-training-full.log`에 보관했다. 직전 51건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 410 (2026-08-31)

- `src/antigravity_k/engine/fast_path_kernel.py`의 생성자 상태(`project_root`, `navigator`, `code_graph`)에 구체 타입과 반환 타입을 명시해 미주석 속성 경고 3건을 제거했다. Fast-Path 심볼 조회·파일 읽기·우회 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. fast-path 회귀 `2 passed` 및 심볼 조회·파일 읽기·우회 동작 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 94 warnings / 0 notes`이며 로그는 `/tmp/fast-path-full.log`에 보관했다. 직전 97건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 391 (2026-08-31)

- `src/antigravity_k/api/routes/session_state.py`의 `ActiveAgentSession` 생성자 반환 타입과 상태 필드(`q`, `is_active`, `done`)를 명시하고, 동적 `Any` orchestrator 슬롯을 `OrchestratorPort | None` 프로토콜로 좁혔다. 스트리밍 런타임이 제공하는 orchestrator 대입 호환성과 싱글톤 reset semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_session_state.py` 회귀 `3 passed` 및 singleton identity/reset invariant 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 138 warnings / 0 notes`이며 로그는 `/tmp/session-state-full.log`에 보관했다. 직전 142건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 381 (2026-08-31)

- `src/antigravity_k/engine/plan_guard.py`의 destructive pattern 상수·상태·compiled regex를 명시적으로 타입화하고, 동적 tool args의 command 값을 문자열로 안전하게 좁혔다. 위험 명령 승인 요구, plan-mode write 차단, protected path 및 strict-mode semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_plan_guard.py` 회귀 `31 passed`를 확인했다.
- safe command 허용, destructive command 승인 요구/차단, plan-mode overwrite 차단을 실제 실행해 `plan_guard_manual_qa: safe command, destructive command, and plan-mode write block passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 188 warnings / 0 notes`이며 로그는 `/tmp/plan-guard-full.log`에 보관했다. 직전 194건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 372 (2026-08-31)

- `src/antigravity_k/tools/mcp_session_manager.py`의 레거시 SSE·Streamable HTTP transport 로더를 지연 해석하는 typed protocol wrapper로 정리하고, MCP 초기화 결과를 명시적으로 무시했다. `httpx.Auth` 타입과 disconnect/cleanup 반환 타입을 구체화했으며, 기존 테스트의 module-level transport patch 지점과 세션 lifecycle semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. MCP/session 및 Unsloth 연계 회귀 `35 passed`를 확인했다.
- 실제 레거시 transport callable lazy resolution과 빈 세션 cleanup을 실행해 `mcp_session_manager_manual_qa: lazy legacy transport resolution and empty cleanup passed`를 확인했다.
- 최신 전체 소스 basedpyright는 다음 모듈 처리 전 기준으로 `0 errors / 255 warnings / 0 notes`이며 기존 로그는 `/tmp/code-api-full.log`에 보관했다. 변경 모듈 자체 경고는 0건이다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 381 (2026-08-31)

- `src/antigravity_k/engine/plan_guard.py`의 destructive pattern 상수·상태·compiled regex를 명시적으로 타입화하고, 동적 tool args의 command 값을 문자열로 안전하게 좁혔다. 위험 명령 승인 요구, plan-mode write 차단, protected path 및 strict-mode semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_plan_guard.py` 회귀 `31 passed`를 확인했다.
- safe command 허용, destructive command 승인 요구/차단, plan-mode overwrite 차단을 실제 실행해 `plan_guard_manual_qa: safe command, destructive command, and plan-mode write block passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 188 warnings / 0 notes`이며 로그는 `/tmp/plan-guard-full.log`에 보관했다. 직전 194건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 373 (2026-08-31)

- `src/antigravity_k/engine/self_healing_doctor.py`의 `project_root` 클래스 속성, AST 파싱 결과, 깨진 파일 목록을 명시적으로 타입화하고 검사 단계에서 의도적으로 사용하지 않는 인자를 `_auto_heal`로 구체화했다. 디렉터리·AST·worktree·모델 정렬 진단 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_self_healing_doctor.py` 회귀 `1 passed`를 확인했다.
- 현재 프로젝트 루트에서 auto-heal을 끈 health check를 실제 실행해 `4 checks, 3 healthy, 0 errors`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 241 warnings / 0 notes`이며 로그는 `/tmp/self-healing-doctor-full.log`에 보관했다. mcp transport 및 self-healing doctor 처리로 직전 255건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 374 (2026-08-31)

- `src/antigravity_k/api/auth_routes.py`의 PIN hash 파일 쓰기 결과를 명시적으로 소비하고, slowapi rate-limit decorator 및 OAuth2 form dependency를 typed protocol/`Annotated` 경계로 구체화했다. 로그인·토큰·검증·레거시 PIN 인증 semantics와 route registration은 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 인증·API 서버·Git boundary 회귀 `60 passed, 2 skipped`를 확인했다.
- 실제 PBKDF2 성공/실패 검증, typed rate-limit decorator 생성, auth route registration을 실행해 `auth_routes_manual_qa: PBKDF2 verification, typed rate-limit decorator, and auth route registration passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 234 warnings / 0 notes`이며 로그는 `/tmp/auth-routes-full.log`에 보관했다. 직전 241건 대비 7건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 375 (2026-08-31)

- `src/antigravity_k/engine/agent_runtime.py`의 `ExecutionEventRecord` import를 실제 정의 모듈로 바로잡고, persistent objective binder/requeue·agency event/reconcile/result 호출 결과를 명시적으로 소비했다. 동적 objective task ID 목록은 Pydantic `list[str]` adapter로 경계 검증해 알 수 없는 타입 경고와 잘못된 ID 전파를 차단했으며 runtime/task semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. AgentRuntime·task API·local task 회귀 `75 passed`를 확인했다.
- stub orchestrator로 기본/명시 모델 해석 및 runtime back-reference를 실제 실행해 `agent_runtime_manual_qa: default/explicit model resolution and runtime back-reference passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 227 warnings / 0 notes`이며 로그는 `/tmp/agent-runtime-full.log`에 보관했다. 직전 234건 대비 7건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 376 (2026-08-31)

- `src/antigravity_k/engine/collective_intelligence.py`의 `GenerateFn`·generation kwargs·engine state를 `dict[str, object]`와 명시적 속성 타입으로 구체화하고, phase 기본값 설정 결과를 명시적으로 소비했다. proposal·critique·synthesis·fallback 및 trace 출력 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_critic_routing.py` 회귀 `5 passed`를 확인했다. `tests/test_model_manager_generate.py`는 기존 tracing 실패 1건(`test_stream_generate_records_local_qwen_failure_trace`)을 제외하고 14건이 통과했다.
- 가짜 proposal/critique/arbiter 생성기로 4단계 호출, 최종 trace, generation defaults를 실제 실행해 `collective_intelligence_manual_qa: proposal, critique, synthesis trace and generation defaults passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 220 warnings / 0 notes`이며 로그는 `/tmp/collective-intelligence-full.log`에 보관했다. 직전 227건 대비 7건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 377 (2026-08-31)

- `src/antigravity_k/engine/auth.py`의 TokenService 내부 TTL·lock·secret 속성을 명시하고 secret 파일 쓰기 결과를 소비했다. JWT/PBKDF2 payload와 claims 경계를 `dict[str, object]`로 구체화했으며 토큰 발급·검증·secret persistence semantics는 유지했다. 연계 `auth_routes.py`의 subject narrowing도 함께 보강했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_auth.py` 회귀 `20 passed`를 확인했다.
- 임시 경로에서 JWT secret persistence, issue/verify, PIN 성공·실패를 실제 실행해 `auth_manual_qa: persisted JWT issue/verify and constant-time PIN success/failure passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 213 warnings / 0 notes`이며 로그는 `/tmp/auth-engine-full.log`에 보관했다. 직전 220건 대비 7건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 378 (2026-08-31)

- `src/antigravity_k/engine/llm_task_decomposer.py`의 JSON 단계 추출을 Pydantic `list[str]` adapter로 검증하고, 분해기 generate 함수·단계 경계·내부 상태를 명시적으로 타입화했다. 복잡도 게이트, JSON/불릿 fallback, 단계 수 제한 및 순차 prompt semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_llm_task_decomposer.py` 회귀 `30 passed`를 확인했다.
- 복잡도 판정, JSON 단계 추출, bounded decomposition을 실제 실행해 `llm_task_decomposer_manual_qa: complexity gate, JSON step extraction and bounded decomposition passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 206 warnings / 0 notes`이며 로그는 `/tmp/llm-task-decomposer-full.log`에 보관했다. 직전 213건 대비 7건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 379 (2026-08-31)

- `src/antigravity_k/engine/code_intel/staleness.py`의 `repo_manager`와 보관 속성을 명시적으로 타입화하고 `check`의 반환 JSON과 미사용 repo 경로를 구체화했다. stale detector의 상태·commit parity 반환 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_code_intel_staleness.py` 회귀 `1 passed`를 확인했다.
- detector의 UP_TO_DATE 상태와 current/indexed commit parity를 실제 실행해 `staleness_manual_qa: detector status and commit parity passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 200 warnings / 0 notes`이며 로그는 `/tmp/staleness-full.log`에 보관했다. 직전 206건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 380 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_handlers.py`의 의도된 private handler/config 재수출을 원본 모듈 `__all__`로 명시해 private usage 경고를 제거했다. 분석·CoV 설정·코드 리뷰 handler의 기존 import surface와 동작은 유지했으며 불필요해진 `reportUnusedFunction` ignore도 제거했다.
- 변경 모듈 및 export 원본 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. orchestrator·planning·agent program 회귀 `13 passed, 2 skipped`를 확인했다.
- private export import와 CoV 설정 해석을 실제 실행해 `orchestrator_handlers_manual_qa: declared private exports and typed CoV config surface passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 194 warnings / 0 notes`이며 로그는 `/tmp/orchestrator-handlers-full.log`에 보관했다. 직전 200건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 361 (2026-08-31)

- `src/antigravity_k/engine/tool_masker.py`의 ActiveToolMasker 상태와 입력/출력 컬렉션을 `object` 기반으로 명시하고, 도구 객체·기본 스키마·OpenAI function 스키마의 이름 추출을 `_ToolMapping` 프로토콜로 안전하게 분리했다. PLAN/edit/test 필터링과 전부 제거 시 원본 fallback semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_tool_masker.py scripts/run_frontier_amplification_test.py` 회귀 `4 passed`를 확인했다.
- 실제 도구 객체와 Anthropic/OpenAI 스키마를 섞은 입력으로 PLAN/edit/test 필터링, task-type phase 매핑 및 빈 결과 fallback을 실행해 `tool_masker_manual_qa: PLAN/edit/test filtering, object+OpenAI schema extraction, empty fallback passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 340 warnings / 0 notes`이며 로그는 `/tmp/tool-masker-full.log`에 보관했다. 직전 350건 대비 10건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 359 (2026-08-31)

- `src/antigravity_k/api/routes/job_api.py`의 FastAPI Query 기본값을 `Annotated` 파라미터 별칭으로 분리해 정적 기본값 경고를 제거하고, 사전 존재 확인 호출의 의도적 반환값을 `_`에 할당했다. 작업 생성·목록·health 정책·CRUD·pause/resume·trigger·run history·retry 라우트 계약은 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_job_api.py tests/test_scheduled_jobs.py tests/test_gateway_api.py tests/test_voice_api.py` 회귀 `17 passed`를 확인했다.
- 임시 SQLite 서비스와 FastAPI `TestClient`로 create/list/trigger/run history/delete/404 흐름을 실행해 `job_api_manual_qa: CRUD, trigger, run history, delete/404 passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 360 warnings / 0 notes`이며 로그는 `/tmp/job-api-full.log`에 보관했다. 직전 370건 대비 10건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 352 (2026-08-31)

- `src/antigravity_k/engine/worktree_manager.py`의 subprocess 결과 소비·stderr 경계를 명시하고, worktree manager 공개 메서드 반환형과 예외 처리를 정리했다. 신규 브랜치 생성, 기존 브랜치 fallback, 경로 조회, force 제거 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_worktree_manager.py` 회귀 `16 passed`를 확인했다.
- 임시 Git 저장소에서 신규 브랜치 worktree 생성·조회, 기존 브랜치 fallback 생성, 일반/force 제거 및 미존재 조회를 실행해 `worktree_manager_manual QA passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 427 warnings / 0 notes`이며 로그는 `/tmp/worktree-src-full.log`에 보관했다. 직전 439건 대비 12건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 347 (2026-08-31)

- `src/antigravity_k/engine/capacity_flow.py`의 체크포인트 상태·오프라인 컨텍스트를 재귀 `CapacityJsonValue`/`CapacityState`로 타입화하고 `CapacityDecision`을 `frozen=True, slots=True`로 고정했다. 용량 임계값 판정, 비용 모델 전환, 체크포인트·오프라인 큐 파일 포맷과 0600 권한 semantics는 유지했다.
- 체크포인트 저장·복원 예외를 파일·직렬화·유니코드·JSON 오류로 좁혀 실패를 로깅하고 기존 반환 semantics를 보존했다. 변경 모듈 basedpyright `0 errors / 2 warnings / 0 notes`(표준 `json.loads`의 Any 반환 경계), Ruff·py_compile 통과, no-excuse audit는 기존 oversized-module 1건만 보고했다.
- `tests/test_capacity_and_skill_learner.py` 회귀 `17 passed`, 용량 0/70/85/95% 임계값·무제한 예산·체크포인트 복원·0600 권한·오프라인 큐·오래된 체크포인트 정리 수동 `capacity_flow_manual QA passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 487 warnings / 0 notes`이며 로그는 `/tmp/capacity-full.log`에 보관했다. 직전 497건 대비 10건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 346 (2026-08-31)

- `src/antigravity_k/engine/tool_loop.py`의 스트림 이벤트 처리 분기를 `match`로 명시해 TEXT·TOOL_CALL_COMPLETE 외 이벤트를 안전하게 무시하도록 정리했고, 설정 입력 오류는 `ToolLoopConfigurationError`로 구분했다. asyncio 기반 병렬 도구 실행, 용량 HALT/WARN, 네이티브 도구 스키마, 재시도 및 checkpoint semantics는 유지했다.
- 도구 결과 후속 보안 게이트와 증분 코드 그래프 갱신의 silent `except: pass`를 debug 로깅으로 바꿔 오류가 숨겨지지 않도록 했다.
- 변경 모듈 basedpyright `0 errors / 13 warnings / 0 notes`, Ruff·py_compile 통과. `tests/test_tool_loop.py tests/test_self_consistency.py tests/test_cognitive_recovery.py` 회귀 `128 passed`, JSON decode·expected-tools 기본값·focus-term 수동 `tool_loop_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 497 warnings / 0 notes`이며 로그는 `/tmp/tool-loop-full.log`에 보관했다. 이번 배치는 기존 호출부 호환성 때문에 전체 경고 수를 추가로 줄이지 않았고, 잔여 13건(표준 JSON decoder Any·protected orchestrator 경계·호환성 컨테이너 unknown)은 다음 타입 경계 분리 작업 대상으로 남겼다.
- no-excuse audit는 asyncio 사용·대형 모듈·광범위 예외 등 기존 구조 debt 21건을 보고했으며 동작 변경을 피하기 위해 이 배치에서 무리한 분해/예외 축소는 수행하지 않았다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 345 (2026-08-31)

- `src/antigravity_k/engine/failure_memory.py`의 세션 실패 레코드와 검색 결과를 `FailureValue`/`FailureRecord`로 타입화하고, 경로·로그 속성 및 공개 메서드 반환 타입을 명시했다. GBrain 결과의 비문자열 tool 값은 안전한 문자열 경계에서 정규화하고 기존 의미 검색·세션 키워드 fallback·prompt/statistics semantics는 유지했다.
- JSONL fallback 및 rotation의 예외 범위를 파일·직렬화·런타임 오류로 좁히고, 파일 쓰기 결과를 명시적으로 소비했다. 기존 1000줄 초과 시 최신 500줄 유지 동작과 비핵심 오류 로깅은 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. `tests/test_failure_memory.py tests/test_cognitive_recovery.py tests/test_reflection_persistence.py` 회귀 `24 passed`, 기록·GBrain fallback·rotation·prompt 수동 `failure_memory_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 497 warnings / 0 notes`이며 로그는 `/tmp/failure-memory-full.log`에 보관했다. 직전 510건 대비 13건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 337 (2026-08-31)

- `src/antigravity_k/engine/knowledge.py`의 KI JSON 저장·로드 경계를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 검증하고, 엔진 상태·정렬 timestamp·렌더링 입력을 명시적으로 타입화했다. malformed metadata는 기존처럼 개별 파일 실패로 격리한다.
- KI 저장·조회, 최신 항목 우선 정렬, prompt 예산 및 artifact 문자열 렌더링 semantics는 유지했다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. KI budget/reflection/autonomous 회귀 `24 passed`, malformed metadata·prompt 수동 `knowledge_manual_qa=passed`를 확인했다.
- `save_ki`는 호출부의 기존 자료형과 호환되도록 제네릭 Mapping 입력을 받고, JSON 경계에서 검증 실패를 로깅 후 격리한다. `engine_context.py` 연결 진단도 `0 errors / 0 warnings`로 확인했다.
- 최신 전체 basedpyright는 `0 errors / 602 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-knowledge-final.log`에 보관했다. 변경 전 통합 진단의 오류 1건을 제거했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 338 (2026-08-31)

- `src/antigravity_k/engine/robust_tool_parser.py`의 tool-call payload를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 검증하고 `ParsedToolCall`을 `frozen=True, slots=True`로 고정했다. strict JSON, Python literal, trailing comma/boolean/None 치환, 미닫힌 괄호 복구 경로를 동일한 typed result로 통합했다.
- `<tool_call>` 태그·backtick JSON fallback·nested arguments 및 repaired flag semantics는 유지했다. 네 parse 실패 경로는 silent `pass` 대신 debug 로그를 남기고 다음 복구 단계로 진행한다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. Robust parser 회귀 `5 passed`, strict/healed/backtick/broken 입력 수동 `robust_tool_parser_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 588 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-robust-parser-final.log`에 보관했다. 직전 602건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 338 (2026-08-31)

- `src/antigravity_k/engine/robust_tool_parser.py`의 tool-call payload를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 검증하고 `ParsedToolCall`을 `frozen=True, slots=True`로 고정했다. strict JSON, Python literal, trailing comma/boolean/None 치환, 미닫힌 괄호 복구 경로를 동일한 typed result로 통합했다.
- `<tool_call>` 태그·backtick JSON fallback·nested arguments 및 repaired flag semantics는 유지했다. 네 parse 실패 경로는 silent `pass` 대신 debug 로그를 남기고 다음 복구 단계로 진행한다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. Robust parser 회귀 `5 passed`, strict/healed/backtick/broken 입력 수동 `robust_tool_parser_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 588 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-robust-parser-final.log`에 보관했다. 직전 602건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 336 (2026-08-31)

- `src/antigravity_k/engine/ide_sync.py`의 IDE 상태·HTTP JSON 경계를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 정리하고, singleton 상태와 prompt formatting 입력을 명시적으로 타입화했다. `BaseHTTPRequestHandler` override와 background server boundary도 정확히 선언했다.
- IDE 상태 갱신·조회, active file/open files prompt formatting, POST JSON 처리 및 서버 시작 semantics는 변경하지 않았다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. singleton 상태와 prompt 수동 `ide_sync_manual_qa=passed`를 확인했다.
- 백그라운드 HTTP 서버를 종료하지 않고 계속 제공하는 기존 broad exception 1건은 경계 복구 semantics를 보존하기 위해 `BROAD_EXCEPT_OK` 주석과 함께 유지했다.
- 최신 전체 basedpyright는 `0 errors / 1,661 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-ide-sync-final.log`에 보관했다. 직전 1,675건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 332 (2026-08-31)

- `src/antigravity_k/api/routes/events.py`의 WebSocket 이벤트 callback·queue·payload 경계를 명시적으로 타입화했다. `EventCallback` 계약과 callback map을 고정하고, `websocket_events` 반환 타입 및 `call_soon_threadsafe` 결과 소비를 추가했다.
- 이벤트 구독 목록, keepalive ping, disconnect 처리, callback 예외 격리 및 unsubscribe semantics는 변경하지 않았다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_events.py`는 `1 passed`, 실제 fake WebSocket과 global EventBus publish를 이용한 `events_manual_qa=passed`를 확인했다. `git diff --check`도 통과했다.
- no-excuse 잔여는 callback 경계에서 개별 이벤트 오류를 격리하는 기존 broad exception 2건이다. 연결 수명과 외부 EventBus callback 예외를 전체 WebSocket 세션 실패로 승격하지 않는 현재 복구 계약을 보존하기 위해 별도 예외 정책 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,728 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-events-final.log`에 보관했다. 직전 1,742건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 327 (2026-08-31)

- `src/antigravity_k/engine/memory/cavemem_store.py`의 `CavememStore` 상태·memory callback을 명시적으로 타입화하고, SQLite 검색 결과를 `ObservationRecord` TypedDict로 파싱했다. FTS 쿼리·검색 결과 shape·caveman 압축·LLM 추출 및 규칙 기반 폴백 semantics는 유지했다.
- SQLite cursor 반환값과 observation 저장 반환값의 의도된 미사용을 `_`로 소비하고, `model_fn`을 `Callable[[str], str]`로 고정해 미지 `Any` 전파를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Cavemem/project-memory 회귀 `37 passed`, 실제 SQLite 저장·검색·LLM 추출 수동 드라이버가 `cavemem_store_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 `Observation` mutable dataclass·missing slots와 LLM 폴백의 broad exception 3건이 남아 있다. 이 항목은 저장 모델 호환성과 외부 model callback 예외 정책을 함께 정해야 하므로 별도 설계 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,772 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-cavemem-store-final.log`에 보관했다. 직전 1,789건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 329 (2026-08-31)

- `src/antigravity_k/engine/persistent_agency.py`의 `AgencyInputError.__str__` override, raw config 입력, `PersistentAgencyController` 상태 필드를 명시적으로 타입화했다. objective reclaim·task event 기록 등 의도된 반환값은 `_`로 소비해 미사용 결과 경고를 제거했다.
- persistent agency의 이벤트 redaction, context projection, objective claim/complete/requeue, scheduler backoff semantics는 변경하지 않았다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. persistent agency·agency API·agent runtime 회귀 `13 passed`, 실제 redaction·objective queue·scheduler 수동 드라이버가 `persistent_agency_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 `record_external_event`의 `Mapping[str, object]` 경계와 300 pure LOC oversized module 2건이 남아 있다. EventBus protocol과 책임 분리를 함께 조정해야 하므로 별도 호환성/분할 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,757 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-persistent-agency-final.log`에 보관했다. 직전 1,772건 대비 15건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 326 (2026-08-31)

- `src/antigravity_k/engine/flight_controller.py`의 `AutonomousFlightController` 상태 필드와 `SubgoalInput` 경계를 명시적으로 타입화하고, supervisor boundary의 JSON reason을 문자열로 안전하게 좁혔다. `add_subgoal`, `complete_subgoal`, `record_failure`, `record_outcome`의 의도된 반환값은 `_`에 소비해 미사용 결과 경고를 제거했다.
- CLI와 stall simulation script의 mission 입력을 `SubgoalInput`으로 연결해 새 입력 계약과 기존 호출부의 타입을 일치시켰다. DAG 순서·의존성·재시도·영구 실패·stall intervention·MissionReport 집계 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_flight_controller.py` 및 `tests/test_flight_supervision.py`는 `6 passed`, 실제 prepare→compile(1회 실패 후 재시도) 미션 드라이버가 `flight_controller_manual_qa=passed`를 출력했다.
- no-excuse audit에는 `flight_controller.py`의 기존 `MissionReport` mutable dataclass·missing slots 및 executor boundary `except Exception` 3건이 남아 있다. 함께 타입 계약을 연결한 `cli.py`에는 기존 object annotation·oversized module·broad exception 15건, `simulate_stall_supervision.py`에는 기존 object annotation 3건이 남아 있어 별도 책임 분리/예외 정책 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,789 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-flight-controller-final.log`에 보관했다. 직전 1,804건 대비 15건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 316 (2026-08-31)

- `src/antigravity_k/engine/code_intel/hybrid_search.py`의 그래프 입력을 generic 타입 경계로 받아 API·테스트의 다양한 graph 구현을 보존하면서, 내부 노드 접근은 명시적 protocol로 좁혔다.
- 검색 결과를 `Mapping[str, NodePropertyValue]`로 구체화하고 graph 노드·index 상태·반환 타입을 명시했다. 문자열 이름만 안전하게 좁혀 기존 대소문자 무시·top_k·자동 인덱스 동작을 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse audit·py_compile 통과. 코드 인텔리전스 회귀 `8 passed`, 실제 `CodeIndexPipeline` 연동 수동 드라이버가 `hybrid_search_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,938 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-hybrid-search-final.log`에 보관했다. 직전 1,955건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 312 (2026-08-31)

- `secret_scanner.py`의 문자열·스칼라 overload와 Pydantic `JsonValue` 검증 경계를 정리하고, `strip_credentials`가 deepcopy 결과만 scrub하도록 수정해 입력 객체 변이를 제거했다. `SecretMatch` 및 credential 상수는 `secret_scanner_patterns.py`로 분리했다.
- `task_runner.py`는 `TaskContext`를 Pydantic JSON adapter로 검증한 뒤 scanner에 전달하도록 수정했다. secret scanner·task runner·security route 회귀 `87 passed`, 수동 스캐너 드라이버 `secret_scanner_manual_qa=passed`를 확인했다.
- production 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse·py_compile 통과. 전체 basedpyright `0 errors / 1,990 warnings / 0 notes`; 로그 `/tmp/antigravity-k-basedpyright-secret-scanner-final.log`.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 311 (2026-08-31)

- `src/antigravity_k/engine/secret_scanner.py`의 문자열·스칼라 입력 경계를 overload로 고정하고, `strip_credentials`는 Pydantic `JsonValue` 검증 후 deepcopy를 scrub해 원본 객체를 변이하지 않도록 정리했다. `SecretMatch`와 credential 상수는 `secret_scanner_patterns.py`로 분리해 스캐너 책임과 패턴 모델을 나눴으며, 기존 스캔·부분/전체 마스킹·URL 인증정보 제거 semantics는 유지했다.
- `src/antigravity_k/engine/task_runner.py`의 `TaskContext`는 Pydantic JSON adapter 경계에서 scanner로 전달하도록 수정해 `dict[str, object]` 전파를 차단했다. 계약 테스트는 nested 결과의 런타임 dict 검증을 명시해 정적 타입과 실제 응답 shape를 함께 고정했다.
- 변경 production 모듈 basedpyright `0 errors / 0 warnings`, Ruff 통과, no-excuse audit `no violations in 2 file(s)`, py_compile 통과를 확인했다. secret scanner·task runner·security route 회귀는 `87 passed`였고, bearer/OpenAI 키·URL query/auth·nested dict/list deepcopy·tuple passthrough 수동 드라이버가 `secret_scanner_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,990 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-secret-scanner-final.log`에 보관했다. 직전 2,013건 대비 23건을 축소했다. 테스트의 private helper 사용 경고 등 기존 경고는 전역 억제 없이 남겨 두었다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 310 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/unsloth_training.py`의 `_StartTrainingDescriptor` 메타데이터와 `UnslothTrainingService` 의존성 필드를 명시적으로 타입화하고, BaseTool 계약 구현에 `@override`를 추가했다. 승인·리소스 admission·원격 MCP 결과의 exhaustive 분기 semantics는 유지했다.
- `match`의 정적으로 이미 소진된 `Never` fallback은 와일드카드 뒤 `assert_never`로 정리해 경고를 제거하면서 런타임 exhaustive guard를 보존했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit `no violations in 1 file(s)`, py_compile 통과를 확인했다. Unsloth training/DPO/provider 회귀는 `21 passed, 27 deselected`였고 descriptor·메타데이터 수동 드라이버도 `unsloth_training_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 2,013 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-unsloth-training-final.log`에 보관했다. 직전 2,031건 대비 18건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 309 (2026-08-31)

- `src/antigravity_k/engine/memory_policy.py`의 loaded model 경계를 `LoadedModelLike` Protocol과 `Mapping`으로 정의하고 메모리·LRU·유휴 퇴출 속성을 명시적으로 타입화했다. `Any`/`getattr` 전파를 제거하고 unload 반환값을 의도적으로 소비했으며, 자동 언로드·cooldown·eviction 순서는 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit `no violations in 1 file(s)`, py_compile 통과를 확인했다. 모델 lifecycle/generate/stream 회귀는 `79 passed, 4 failed`였으며 실패 4건은 provider capability의 MagicMock URL 경계와 tracing span 누락으로 이번 메모리 정책 변경과 무관한 기존 dirty 동작이었다. 별도 in-memory model double로 usage/ensure/evict 순서와 반환값을 `memory_policy_manual_qa=passed`로 검증했다.
- 최신 전체 basedpyright는 `0 errors / 2,031 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-memory-policy-final.log`에 보관했다. 직전 2,049건 대비 18건을 축소했다.
- 실제 호출자가 사용하는 `OrderedDict[str, LoadedModel]`까지 전역 타입 검증에 포함해 `Mapping` 경계로 수정했으며, 기존 사용자 변경 234건과 나머지 dirty path는 보존; stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 308 (2026-08-31)

- `src/antigravity_k/engine/context_compressor.py`의 메시지·영구 메모리·RAG 결과 경계를 `Message` alias와 Pydantic `TypeAdapter`로 정리하고, 클래스 속성 타입과 저장/로드 예외를 구체화했다. RAG 검색 결과의 `max_rag_chars` 인자를 실제로 적용해 미사용 인자 경고와 길이 제한 누락을 함께 해결했다.
- 적응형 압축 정책 상수를 `context_compressor_policy.py`로 분리해 모듈 크기와 책임을 정리하고, 정책을 `Final`/`Mapping`으로 고정했다. 기존 토큰 예산·요약·RAG 주입 semantics는 유지했다.
- 변경 2개 모듈 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit `no violations in 2 file(s)`, py_compile 통과을 확인했다. 압축·RAG·영구 메모리 회귀는 `11 passed, 49 deselected`였고 수동 실행도 `context_compressor_manual_qa=pass`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 2,049 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-context-compressor-final.log`에 보관했다. 직전 2,067건 대비 18건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 307 (2026-08-31)

- `src/antigravity_k/agents/scout_agent.py`의 모델 응답을 `_ScoutResponse`/`_ScoutAddProposal` Pydantic 모델로 파싱하고, `ModelManager`·`ToolRegistry` 속성을 명시적으로 타입화했다. JSON code block 추출, 메모리 한도 계산, 하드웨어 업그레이드 분기와 승인 기안서 생성 semantics는 유지했다.
- `config.yaml`에서 실제 소비하는 `memory.total_system_gb` 값만 typed regex boundary로 읽어 YAML loader의 무형식 `Any` 전파를 제거했다. 누락·비정상 값의 기본 128GB 동작은 유지했다.
- 변경 모듈 basedpyright·Ruff `0 errors / 0 warnings`, no-excuse audit `no violations in 1 file(s)`, py_compile 통과 및 ScoutAgent 회귀 `10 passed`를 확인했다. 실제 fake model 기반 승인 기안서 드라이버도 `scout_agent_manual_qa=pass`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 2,067 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-scout-agent-final.log`에 보관했다. 직전 2,085건 대비 18건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 313 (2026-08-31)

- `secret_scanner.py`의 문자열·스칼라 overload와 Pydantic `JsonValue` 검증 경계를 정리하고, `strip_credentials`가 deepcopy 결과만 scrub하도록 수정해 입력 객체 변이를 제거했다. `SecretMatch` 및 credential 상수는 `secret_scanner_patterns.py`로 분리했다.
- `task_runner.py`는 `TaskContext`를 Pydantic JSON adapter로 검증한 뒤 scanner에 전달하도록 수정했다. secret scanner·task runner·security route 회귀 `87 passed`, 수동 스캐너 드라이버 `secret_scanner_manual_qa=passed`를 확인했다.
- production 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse·py_compile 통과. 전체 basedpyright `0 errors / 1,990 warnings / 0 notes`; 로그 `/tmp/antigravity-k-basedpyright-secret-scanner-final.log`.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 314 (2026-08-31)

- `src/antigravity_k/security/computer_use_guard.py`의 액션 파라미터·검증 결과·감사 엔트리·위험영역 좌표를 명시적 TypedDict로 분리하고, 클래스 상수와 인스턴스 속성을 `Final`/구체 타입으로 고정했다. 좌표·해상도는 정수 입력 경계에서 파싱해 `Any` 전파를 제거했으며 안전/차단/HITL/위험영역 판정 순서는 유지했다.
- 타입 모델은 `computer_use_guard_models.py`로 분리해 guard 모듈을 순수 LOC 194로 축소했다. 감사 파일 기록은 context manager와 `(OSError, TypeError, ValueError)`만 처리하도록 좁혀 broad exception을 제거했다.
- 변경 production 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse audit `no violations in 2 file(s)`, py_compile 통과를 확인했다. Computer Use 회귀는 `60 passed`, 실제 stub tool·위험영역·HITL·custom block·JSONL 감사 기록 수동 드라이버가 `computer_use_guard_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,972 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-computer-use-guard-final.log`에 보관했다. 직전 1,990건 대비 18건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 315 (2026-08-31)

- `src/antigravity_k/api/routes/vault_api.py`의 FastAPI dependency를 `Annotated` alias로 정리해 mutable default/unreachable 경고를 제거하고, optional `VaultEngine`의 503 경계를 `search_notes`까지 일관되게 적용했다.
- `_Vault*Request` 모델의 `model_config`를 `ClassVar`로 고정하고, 권한 인자를 `Mapping[str, JsonValue]`, vault tree 결과를 재귀 `VaultTreeNode` TypedDict로 구체화했다. `Permission`은 공개 소스인 `tool_contracts`에서 가져오도록 수정했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse audit·py_compile 통과. Vault API·privacy 회귀 `28 passed`, 임시 git vault TestClient 수동 드라이버가 `vault_api_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,955 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-vault-api-final.log`에 보관했다. 직전 1,972건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 317 (2026-08-31)

- `src/antigravity_k/engine/code_intel/hybrid_search.py`의 그래프 입력을 generic 타입 경계로 받아 API·테스트의 다양한 graph 구현을 보존하면서, 내부 노드 접근은 명시적 protocol로 좁혔다.
- 검색 결과를 `Mapping[str, NodePropertyValue]`로 구체화하고 graph 노드·index 상태·반환 타입을 명시했다. 문자열 이름만 안전하게 좁혀 기존 대소문자 무시·top_k·자동 인덱스 동작을 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse audit·py_compile 통과. 코드 인텔리전스 회귀 `8 passed`, 실제 `CodeIndexPipeline` 연동 수동 드라이버가 `hybrid_search_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,938 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-hybrid-search-final.log`에 보관했다. 직전 1,955건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 318 (2026-08-31)

- `src/antigravity_k/engine/quality_gate.py`의 `QualityGate` 상태 필드와 정규식·Mermaid 파싱 결과를 명시적으로 타입화했다. 코드 구문 검증 결과는 의도적으로 버리는 값임을 표시하고, LLM 검증의 미사용 태스크 타입도 명시적으로 소비했다.
- 품질 평가 semantics, 등급·재시도 판정, 코드/최신성/Markdown 검사 규칙은 변경하지 않고 implicit string concatenation 경고만 명시적 문자열 표현으로 정리했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 품질 게이트·출력 품질·검사기 회귀 `38 passed`, 정상/구문 오류 응답 수동 드라이버가 `quality_gate_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 `QualityScore` mutable dataclass·655 LOC oversized module·LLM self-verification broad exception 4건이 남아 있다. 이 항목은 동작 변경과 모듈 분할 판단이 필요한 별도 설계 작업으로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,921 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-quality-gate-final.log`에 보관했다. 직전 1,938건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 319 (2026-08-31)

- `src/antigravity_k/engine/memory_recorder.py`의 vault·model manager 입력을 optional protocol 경계로 정리하고, 실제 writer/generator 호출은 명시적인 runtime callable 경계에서 수행하도록 타입화했다.
- `sync_rag`가 비활성화됐거나 manager가 없는 경우 조기 종료하고, 기록 대상 태스크 필터·preferred model 우선·요약 스트리밍·Vault 기록 semantics는 유지했다. broad exception은 저장/모델 호출에서 예상되는 오류 집합으로 좁혔다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse audit·py_compile 통과. memory recorder·orchestrator handler 회귀 `6 passed`, fake vault/manager 저장 수동 드라이버가 `memory_recorder_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,904 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-memory-recorder-final.log`에 보관했다. 직전 1,921건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 320 (2026-08-31)

- `src/antigravity_k/tools/crawler_policy.py`의 법적 정책 JSON 입력을 Pydantic `JsonValue` adapter로 검증하고, 필수 문자열·문자열 목록·datetime 파싱 경계를 명시했다.
- `LegalTermsPolicy`와 `RobotsRateLimitPolicy`의 상태 필드를 구체화하고, 기존 audit/enforce 판정·만료·목적 필터·robots 허용/차단·rate limit semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. crawler policy·web search quality 회귀 `53 passed`, legal/robots mock transport 수동 드라이버가 `crawler_policy_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 asyncio 직접 사용과 ValueError/TypeError generic 정책 예외 11건이 남아 있다. anyio 전환 및 도메인 예외 설계는 별도 정책 호환성 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,887 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-crawler-policy-final.log`에 보관했다. 직전 1,904건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 321 (2026-08-31)

- `src/antigravity_k/tools/vision_tools.py`의 `GenerateImageTool` 상속 메타데이터·내부 상태·JSON schema·execute 입력을 명시적으로 타입화하고 BaseTool override 계약을 표시했다. 테스트 호출부가 required 필드를 문자열 목록으로 추론할 수 있도록 schema TypedDict 경계를 추가했다.
- 기존 placeholder 실행 semantics와 missing argument 처리, artifacts 디렉터리 생성 동작을 유지했으며, description에 누락돼 있던 “artifacts directory...” 안내 문구를 실제로 연결했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·no-excuse·py_compile 통과. Vision tool 회귀 `5 passed`, stub 실행 수동 드라이버가 `vision_tools_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,867 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-vision-tools-final.log`에 보관했다. 직전 1,887건 대비 20건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 322 (2026-08-31)

- `src/antigravity_k/api/routes/agent_activity.py`의 활동·감사·deny-rule API 응답을 `JsonValue` 기반 `RouteResponse`로 고정하고, FastAPI Query 기본값을 `Annotated` 경계로 옮겨 부분 미지 타입과 default initializer 경고를 제거했다.
- AuditDb의 protected `_initialized` 직접 접근을 읽기 전용 `initialized` property로 교체해 라우트가 공개 계약을 사용하도록 정리했다. 기존 활동 조회·감사 필터/집계·deny-rule 설치 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. deny-rule 회귀 `14 passed`, API health/deep-link 회귀 `3 passed`, 활동·감사·deny-rule 전체 stub TestClient 드라이버가 `agent_activity_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 API broad exception 5건과 AuditDb의 broad exception·object annotation·272 LOC oversized module 등 16건이 남아 있다. 예외 도메인화와 AuditDb 조회/저장 책임 분리는 별도 설계 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,851 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-agent-activity-final.log`에 보관했다. 직전 1,867건 대비 16건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 323 (2026-08-31)

- `src/antigravity_k/tools/web_scraper.py`의 `WebScraperTool` 메타데이터·내부 상태·JSON schema·execute 입력을 명시적으로 타입화하고 BaseTool override 계약을 표시했다.
- bare `Any`와 미지 kwargs를 제거했으며, 프로젝트 async 규칙에 맞춰 `asyncio.run`을 `anyio.run`으로 교체했다. URL 필수값 오류, PageScraper 정리, private URL 차단 및 Markdown 반환 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 웹 검색·스크래퍼 회귀 `123 passed`, stub PageScraper 성공/누락 URL 수동 드라이버가 `web_scraper_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 최상위 broad exception 1건이 남아 있다. 외부 scraper의 예외 계약을 도메인 예외로 분리하는 작업은 별도 호환성 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,835 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-web-scraper-final.log`에 보관했다. 직전 1,851건 대비 16건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 324 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/unsloth_studio.py`의 `_ReadToolDescriptor`와 `UnslothStudioService` 메타데이터·내부 상태·override 계약을 명시적으로 타입화하고, snapshot 결과 누적 리스트를 `UnslothStudioToolResult`로 고정했다.
- MCP read-only allowlist, token 미설정 조기 반환, 권한 거부, 연결 종료 및 원격 결과 파싱 semantics는 유지했다. 변경 파일 기준 no-excuse audit도 `no violations in 1 file(s)`를 확인했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Unsloth Studio·training guardrail 회귀 `9 passed`, 실제 MCP session double의 allowlist·token·권한 거부 수동 드라이버가 `unsloth_studio_manual_qa=passed`를 출력했다.
- 최신 전체 basedpyright는 `0 errors / 1,819 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-unsloth-studio-final.log`에 보관했다. 직전 1,835건 대비 16건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 325 (2026-08-31)

- `src/antigravity_k/engine/durable_memory.py`의 durable provider callback·metadata·export 결과를 `JsonValue`와 `Callable` 계약으로 정리하고 모든 `MemoryProvider` override를 표시했다. 음수 retention은 공용 `InvalidRetentionAgeError`를 사용하도록 통일했다.
- 실제 dependency callback 4곳은 `TypeAdapter[list[dict[str, JsonValue]]]` 경계에서 JSON export를 파싱하도록 정리해 API dependency와 provider 계약을 일치시켰다. scope별 clear/export/redact 및 retention semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. durable memory·memory scope 회귀 `19 passed`, callback·MemoryManager 통합 수동 드라이버가 `durable_memory_manual_qa=passed`를 출력했다.
- no-excuse는 durable_memory에서 `no violations in 1 file(s)`를 확인했다. 함께 건드린 dependencies.py에는 기존 generic ValueError·object annotation·397 LOC oversized module 5건이 남아 있어 별도 분리 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,804 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-durable-memory-final.log`에 보관했다. 직전 1,819건 대비 15건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 328 (2026-08-31)

- `src/antigravity_k/engine/memory/cavemem_store.py`의 `CavememStore` 상태·memory callback을 명시적으로 타입화하고, SQLite 검색 결과를 `ObservationRecord` TypedDict로 파싱했다. FTS 쿼리·검색 결과 shape·caveman 압축·LLM 추출 및 규칙 기반 폴백 semantics는 유지했다.
- SQLite cursor 반환값과 observation 저장 반환값의 의도된 미사용을 `_`로 소비하고, `model_fn`을 `Callable[[str], str]`로 고정해 미지 `Any` 전파를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Cavemem/project-memory 회귀 `37 passed`, 실제 SQLite 저장·검색·LLM 추출 수동 드라이버가 `cavemem_store_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 `Observation` mutable dataclass·missing slots와 LLM 폴백의 broad exception 3건이 남아 있다. 이 항목은 저장 모델 호환성과 외부 model callback 예외 정책을 함께 정해야 하므로 별도 설계 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,772 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-cavemem-store-final.log`에 보관했다. 직전 1,789건 대비 17건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 330 (2026-08-31)

- `src/antigravity_k/engine/persistent_agency.py`의 `AgencyInputError.__str__` override, raw config 입력, `PersistentAgencyController` 상태 필드를 명시적으로 타입화했다. objective reclaim·task event 기록 등 의도된 반환값은 `_`로 소비해 미사용 결과 경고를 제거했다.
- persistent agency의 이벤트 redaction, context projection, objective claim/complete/requeue, scheduler backoff semantics는 변경하지 않았다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. persistent agency·agency API·agent runtime 회귀 `13 passed`, 실제 redaction·objective queue·scheduler 수동 드라이버가 `persistent_agency_manual_qa=passed`를 출력했다.
- no-excuse audit에는 기존 `record_external_event`의 `Mapping[str, object]` 경계와 300 pure LOC oversized module 2건이 남아 있다. EventBus protocol과 책임 분리를 함께 조정해야 하므로 별도 호환성/분할 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,757 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-persistent-agency-final.log`에 보관했다. 직전 1,772건 대비 15건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 331 (2026-08-31)

- `src/antigravity_k/engine/self_consistency.py`의 엔진 상태 필드를 명시하고 `config_to_engine_kwargs` 입력을 primitive `Mapping`과 `EngineKwargs` TypedDict로 정리했다. 생성 kwargs는 JSON 값 경계로 제한해 `Any`·미지 config 전파를 제거했다.
- `ConsistencySample`과 `ConsistencyTrace`를 `frozen=True, slots=True`로 전환하고, 실행 시 cluster id는 `dataclasses.replace`로 새 샘플을 생성하도록 바꿨다. 다수결 선택·온도 다양화·복잡도 게이트·빈 샘플 스킵 semantics는 유지했다.
- `src/antigravity_k/engine/model_manager.py` 호출부는 primitive config만 boundary에서 추려 새 설정 계약과 연결했다. 변경 모듈 basedpyright·Ruff·py_compile 통과, self-consistency·amplification·best-of-n 회귀 `37 passed`, 실제 다수결 및 불변 trace 수동 드라이버가 `self_consistency_manual_qa=passed`를 출력했다.
- no-excuse audit에는 개별 생성 샘플을 실패 시 빈 샘플로 격리하는 기존 broad exception 1건이 남아 있다. 임의 model callback 오류를 전체 N샘플링 실패로 승격하지 않는 현재 복구 계약을 유지하기 위해 별도 예외 정책 배치로 보류했다.
- 전체 basedpyright는 `0 errors / 1,742 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-self-consistency-final.log`에 보관했다. 직전 오류 2건을 제거했고 경고 수는 동일하게 유지됐다.
- `tests/test_model_manager_generate.py::test_stream_generate_records_local_qwen_failure_trace`는 이번 변경과 무관한 기존 stream tracing 결함으로 실패했으며, self-consistency 관련 37개 회귀는 통과했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 333 (2026-08-31)

- `src/antigravity_k/api/routes/events.py`의 WebSocket 이벤트 callback·queue·payload 경계를 명시적으로 타입화했다. `EventCallback` 계약과 callback map을 고정하고 `websocket_events` 반환 타입 및 `call_soon_threadsafe` 결과 소비를 추가했다.
- `src/antigravity_k/engine/ambient_watchdog.py`의 상태 필드와 heartbeat 결과를 명시적으로 타입화했으며, 연계된 `heartbeat.py`의 executor callback·상태 속성·상태 보고 TypedDict도 정리했다.
- 이벤트 구독·keepalive·disconnect, watchdog diff debounce·heartbeat·알림 큐 semantics는 변경하지 않았다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과, 관련 회귀는 `38 passed`다.
- 실제 fake WebSocket과 global EventBus publish를 이용한 `events_manual_qa=passed`를 확인했다. `git diff --check`도 통과했다.
- no-excuse 잔여는 events callback 및 watchdog 외부 실행 경계의 기존 broad exception 4건이다. 개별 callback/heartbeat/model 오류를 전체 세션·감시 루프 실패로 승격하지 않는 복구 계약을 보존하기 위해 별도 예외 정책 배치로 보류했다.
- 최신 전체 basedpyright는 `0 errors / 1,703 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-ambient-watchdog-final.log`에 보관했다. 직전 1,728건 대비 25건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 334 (2026-08-31)

- `src/antigravity_k/engine/embeddings.py`의 SentenceTransformer 동적 로더를 `_EmbeddingFactory`·`_EmbeddingModel` Protocol 경계로 정리하고, 직접 import 후 구조 검증을 거쳐 모델을 보관하도록 수정했다. `Union`을 PEP 604 문법으로 교체하고 모델·tokenizer·fallback dimension 상태도 명시했다.
- 외부 encode 결과와 hash fallback 결과는 모두 `list[list[float]]`로 파싱하며 NumPy `tolist()`의 `Any` 전파를 제거했다. 모델 로딩 실패 시 local fallback, test/mock/dummy prefix, singleton 및 정규화 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. Embedding 회귀 `14 passed`, fake SentenceTransformer를 주입한 `embeddings_manual_qa=passed`를 확인했다.
- 선택적 외부 provider 초기화 실패를 local fallback으로 격리하는 기존 broad exception 1건은 `BROAD_EXCEPT_OK` 경계 주석과 함께 유지했다.
- 최신 전체 basedpyright는 `0 errors / 1,689 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-embeddings-final.log`에 보관했다. 직전 1,703건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 335 (2026-08-31)

- `src/antigravity_k/engine/harness_enforcer.py`의 tool args·guidelines JSON 경계를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 파싱하고, `BoundaryResult` TypedDict로 허용·차단 결과 shape를 고정했다. 상태 필드와 `HarnessFeedbackAction`도 명시적으로 정리했다.
- 스톨 반복·유사 오류 클러스터·무진행 윈도우·strict path 차단 semantics는 유지했다. `flight_controller.py`는 새 boundary 결과 계약을 사용하도록 연결했고, optional `stall` 키 테스트는 `.get()` 기반으로 보강했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Harness/flight/benchmark 회귀 `54 passed`, no-excuse audit `no violations in 1 file(s)` 및 strict guidelines/path 수동 `harness_enforcer_manual_qa=passed`를 확인했다.
- 선택적 감독기 및 외부 tool 경계의 broad exception 정책은 기존 default-deny/복구 semantics를 보존하기 위해 유지했다.
- 최신 전체 basedpyright는 `0 errors / 1,675 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-harness-enforcer-final.log`에 보관했다. 직전 오류 2건을 제거했고 경고 수는 1,689건에서 14건 감소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 337 (2026-08-31)

- `src/antigravity_k/engine/knowledge.py`의 KI JSON 저장·로드 경계를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 검증하고, 엔진 상태·정렬 timestamp·렌더링 입력을 명시적으로 타입화했다. malformed metadata는 기존처럼 개별 파일 실패로 격리한다.
- KI 저장·조회, 최신 항목 우선 정렬, prompt 예산 및 artifact 문자열 렌더링 semantics는 유지했다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. KI budget/reflection/autonomous 회귀 `24 passed`, malformed metadata·prompt 수동 `knowledge_manual_qa=passed`를 확인했다.
- `save_ki`는 호출부의 기존 자료형과 호환되도록 제네릭 Mapping 입력을 받고, JSON 경계에서 검증 실패를 로깅 후 격리한다. `engine_context.py` 연결 진단도 `0 errors / 0 warnings`로 확인했다.
- 최신 전체 basedpyright는 `0 errors / 602 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-knowledge-final.log`에 보관했다. 변경 전 통합 진단의 오류 1건을 제거했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 338 (2026-08-31)

- `src/antigravity_k/engine/robust_tool_parser.py`의 tool-call payload를 재귀 `JsonValue`/`JsonMap`과 Pydantic `TypeAdapter`로 검증하고 `ParsedToolCall`을 `frozen=True, slots=True`로 고정했다. strict JSON, Python literal, trailing comma/boolean/None 치환, 미닫힌 괄호 복구 경로를 동일한 typed result로 통합했다.
- `<tool_call>` 태그·backtick JSON fallback·nested arguments 및 repaired flag semantics는 유지했다. 네 parse 실패 경로는 silent `pass` 대신 debug 로그를 남기고 다음 복구 단계로 진행한다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. Robust parser 회귀 `5 passed`, strict/healed/backtick/broken 입력 수동 `robust_tool_parser_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 588 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-robust-parser-final.log`에 보관했다. 직전 602건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 339 (2026-08-31)

- `src/antigravity_k/engine/toolset_manager.py`의 내장·사용자 정의 toolset shape를 `ToolsetDefinition`/`ToolsetSummary` TypedDict와 Pydantic 경계로 고정했다. active toolset, includes 재귀 해석, 순환 참조 차단, all/full 합성 semantics는 유지했다.
- 잘못된 사용자 정의 항목은 유효한 항목을 보존한 채 개별적으로 무시하고 warning을 남기도록 정리했다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과.
- `tests/test_shields_manager.py` 회귀 `11 passed`, 내장·custom·invalid·cycle·active transition 수동 `toolset_manager_manual_qa=passed`를 확인했다. 대형 `system_api_memory_suite`는 15번째 테스트 이후 장시간 정체되어 프로세스를 정리했으며 별도 잔여 이슈로 남겼다.
- 최신 전체 basedpyright는 `0 errors / 574 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-toolset-final.log`에 보관했다. 직전 588건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 340 (2026-08-31)

- `src/antigravity_k/tools/docker_tools.py`의 Docker 도구 메타데이터, JSON 스키마, properties, 실행 인자를 재귀 `JsonValue`로 타입화하고 BaseTool 계약에 `@override`를 명시했다. 기존 명령 구성·이미지 기본값·timeout·stdout/stderr 포맷과 반환 semantics는 유지했다.
- Docker 프로세스 경계의 실패 처리는 `TimeoutExpired`와 `OSError`·`ValueError`·`SubprocessError`로 좁혀 malformed 입력과 실행 실패를 기존 오류 문자열로 반환하도록 정리했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. 성공·비정상 종료·필수 command 누락·timeout·Docker 미설치 경로 수동 `docker_tools_manual_qa=passed`를 확인했다.
- `tests/test_sandbox.py tests/test_sandbox_isolation.py` 회귀 `35 passed`를 확인했다. 최신 전체 basedpyright는 `0 errors / 560 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-docker-full.log`에 보관했다. 직전 574건 대비 14건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 341 (2026-08-31)

- `src/antigravity_k/engine/chain_of_verification.py`에서 검증 결과·실행 추적 모델과 복잡도 지표를 `chain_of_verification_models.py`로 분리하고, 공개 import 경로(`ChainOfVerification`, `VerificationResult`, `CoVTrace`, `estimate_complexity`)를 유지했다.
- 검증·수정 루프는 frozen+slots 결과 모델을 재구성하는 방식으로 바꾸어 기존 pass/revise semantics를 보존했고, Python 코드 블록은 typed regex match와 `ast.parse`로 검사한다. LLM 호출 실패는 구체적인 프로세스·입력·시간 초과 예외만 처리한다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 2 file(s)` 통과. CoV·복잡도 회귀 `25 passed`, valid code·LLM issue/revise loop 수동 `chain_of_verification_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 549 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-cov-full.log`에 보관했다. 직전 560건 대비 11건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 342 (2026-08-31)

- `src/antigravity_k/api/error_handler.py`의 API 오류 context·응답 payload와 FastAPI validation 오류를 재귀 `JsonValue`/`JsonMap`으로 타입화했다. 구조화 오류의 status/error/detail/correlation_id 및 예약 키 충돌 방지 semantics는 유지했다.
- Pydantic validation payload는 `object`/`Any` 직접 접근 대신 typed mapping boundary에서 field·message·type을 안전하게 추출하도록 정리했다. 기존 generic/API/HTTP/validation 응답과 correlation-id 동작은 변경하지 않았다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. `tests/test_observability.py tests/test_security_headers.py` 회귀 `15 passed`, API/generic/HTTP/validation handler 수동 `error_handler_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 536 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-error-handler-full.log`에 보관했다. 직전 549건 대비 13건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 343 (2026-08-31)

- `src/antigravity_k/engine/chunker.py`의 Markdown metadata·chunk 반환 경계를 generic `Mapping`/`TypeVar`와 `ChunkRecordValue`로 타입화하고 chunker 상태 속성을 명시했다. 헤더 분할, source/header/index metadata, max-size sub-chunk 및 ID semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. `tests/test_chunker.py tests/test_rag.py -k 'chunker or markdown'` 회귀 `13 passed`, header·metadata·sub-chunk 수동 `chunker_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 523 warnings / 0 notes`이며 로그는 `/tmp/chunker-full-bp.log`에 보관했다. 직전 536건 대비 13건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 344 (2026-08-31)

- `src/antigravity_k/engine/diff_engine.py`의 `Hunk`·`FilePatch`·`ApplyResult` 모델을 `diff_models.py`로 분리해 frozen+slots dataclass로 고정하고, apply_patch parser를 `diff_parser.py`로 분리했다. 기존 모듈 import 경로와 parse/apply API는 유지했다.
- fuzzy anchor 후보와 SequenceMatcher ratio를 명시적 `list[int]`/`list[float]`로 타입화하고 `FUZZY_THRESHOLD`를 선언했다. 정확·퍼지·순수 추가·신규/삭제·다중 hunk·실패 및 trailing newline semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 3 file(s)` 통과. `tests/test_diff_engine.py` 회귀 `19 passed`, parse/apply/fuzzy/failure 수동 `diff_engine_manual_qa=passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 510 warnings / 0 notes`이며 로그는 `/tmp/antigravity-k-basedpyright-diff-full.log`에 보관했다. 직전 523건 대비 13건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 348 (2026-08-31)

- `src/antigravity_k/agents/message_bus.py`의 채널 기록·콜백 payload를 재귀 `MessageValue`/`MessageRecord`로 타입화하고, 구독 에이전트의 `name`·`add_message` 계약을 Protocol로 고정했다. 채널 생성, 중복 구독 방지, history 조회, 일반 에이전트 전달 및 콜백 격리 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. no-excuse audit는 임의 콜백 오류를 격리하기 위한 의도된 broad-except 1건만 보고했다.
- `tests/test_agent_fabric_orchestration.py tests/test_evolution_family_rest.py` 연계 회귀 `29 passed`, 채널·중복 구독·콜백·history·없는 채널 수동 `message_bus_manual QA passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 475 warnings / 0 notes`이며 로그는 `/tmp/message-bus-full.log`에 보관했다. 직전 487건 대비 12건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 349 (2026-08-31)

- `src/antigravity_k/api/routes/evolution_api.py`의 Permission import를 공개 `tool_contracts` 경로로 정정하고, 진화 요청 인자·Vault 의존성·응답을 구체 타입으로 고정했다. `Annotated` dependency aliases로 FastAPI 기본값 경고를 제거하면서 기존 `/api/agent/evolve` 및 `/api/agent/evolve_system_prompt` 경로와 권한/Vault 검증 semantics를 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과. `tests/test_evolution.py tests/test_local_model_routing_coverage.py` 회귀 `13 passed`, 진화 성공·시스템 프롬프트 성공·Vault 누락 422 수동 `evolution_api_manual QA passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 463 warnings / 0 notes`이며 로그는 `/tmp/evolution-api-full.log`에 보관했다. 직전 475건 대비 12건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 350 (2026-08-31)

- `src/antigravity_k/engine/reflection.py`의 ReflectionAgent 상태 속성과 공개 반환형을 명시하고, LLM 회고 JSON을 Pydantic `TypeAdapter[dict[str, JsonValue]]`로 검증했다. `learned_knowledge`·target_files·auto-skill description은 타입을 확인한 뒤 저장/합성하며 기존 diff→KI 및 스킬 생성 semantics를 유지한다.
- Git diff 수집, 회고 처리, 스킬 합성 예외를 파일·프로세스·파싱·입력 오류로 좁히고 파일 쓰기/AST 결과를 명시적으로 소비했다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile·no-excuse audit `no violations in 1 file(s)` 통과.
- `tests/test_reflection.py tests/test_reflection_persistence.py tests/test_cognitive_recovery.py` 회귀 `13 passed`, 임시 Git diff→실제 `.antigravity/knowledge` KI 저장 수동 `reflection_manual QA passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 451 warnings / 0 notes`이며 로그는 `/tmp/reflection-full.log`에 보관했다. 직전 463건 대비 12건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 351 (2026-08-31)

- `src/antigravity_k/engine/self_repair.py`의 실패 이력·작업 상태·수리 결과를 `FailureRecord`/`RepairDetails`와 Pydantic `JsonValue`로 타입화하고, 정책·감지·결과 dataclass를 `frozen=True, slots=True`로 고정했다. 보호 도구 제외, RETRY/SWITCH/ABORT 단계, 알림 dedup 및 정리 semantics는 유지했다.
- 작업 등록·실패 기록·set/pop 결과를 명시적으로 소비하고 `detect_stuck` 입력 상태의 문자열 경계를 검증했다. 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. no-excuse audit는 기존 variant if/elif 및 oversized-module 2건만 남겼다.
- `tests/test_upgrade_v6_9.py tests/test_goal_runner.py` 연계 회귀 `21 passed, 2 skipped`, 보호 도구·실패 임계값·SWITCH/ABORT·알림 dedup·cleanup 수동 `self_repair_manual QA passed`를 확인했다.
- 최신 전체 basedpyright는 `0 errors / 439 warnings / 0 notes`이며 로그는 `/tmp/self-repair-full.log`에 보관했다. 직전 451건 대비 12건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 353 (2026-08-31)

- `src/antigravity_k/engine/evolution.py`의 VaultEngine optional 검증, 상태 속성, RAG 결과·모델 대상·파일 쓰기 경계를 명시해 기존 self-evolution 동작을 보존하면서 진단 경고를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_evolution.py tests/test_local_model_routing_coverage.py tests/test_self_evolution_coordinator.py` 회귀 `47 passed`를 확인했다.
- 임시 Vault와 스킬 파일에서 모델 대상 해석, Markdown fence 정리, SKILL_EVOLVED 및 SYSTEM_PROMPT_EVOLVED 저장을 실행해 `evolution_manual QA passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 416 warnings / 0 notes`이며 로그는 `/tmp/evolution-full.log`에 보관했다. 직전 427건 대비 11건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 354 (2026-08-31)

- `src/antigravity_k/engine/kanban_engine.py`의 KanbanTask 직렬화 payload와 metadata를 명시 타입으로 고정하고, 의존성 목록·단계 입력·상태 전이 오류 문자열을 정리했다. 태스크 추가, dependency gate, 우선순위 기반 actionable 조회, Markdown 및 dict 출력 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_kanban.py` 회귀 `2 passed`를 확인했다.
- 실제 Kanban 보드에서 TODO→IN_PROGRESS→IN_REVIEW→DONE 전이, 미완료 dependency 차단, 우선순위 선택, `to_dict`/Markdown 렌더링, 객체·문자열 단계 decomposition을 실행해 `kanban_manual QA passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 405 warnings / 0 notes`이며 로그는 `/tmp/kanban-full.log`에 보관했다. 직전 416건 대비 11건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 355 (2026-08-31)

- `src/antigravity_k/engine/pipeline_timer.py`의 deprecated Optional과 명시 `Any`를 제거하고 타이밍/통계 payload alias, 클래스 상태, context-manager 인자를 구체화했다. 측정·기록·최근 기록·단계별/전체 통계 및 reset semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_pipeline_timer.py` 회귀 `20 passed`를 확인했다.
- 실제 timer context manager와 `record_step` 호출로 단계 통계·recent 목록·전체 호출 수를 확인하고 reset 후 빈 상태를 검증해 `pipeline_timer_manual QA passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 394 warnings / 0 notes`이며 로그는 `/tmp/pipeline-timer-full.log`에 보관했다. 직전 405건 대비 11건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 356 (2026-08-31)

- `src/antigravity_k/engine/stream_processor.py`의 StreamState 컬렉션과 processor 상태 속성을 명시하고, `process_text`의 출력 조각 버퍼를 `list[str]`로 고정했다. thought/think·scratch_pad 분할 청크 제거, 내부 태그/CJK 정리, 반복 감지, flush Markdown 확장 및 reset semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_stream_processor.py tests/test_upgrade_v6_9.py` 회귀 `22 passed, 2 skipped`를 확인했다.
- 분할 thought/scratch_pad 처리, Markdown 확장, 반복 루프 임계값 및 reset을 실제 청크 흐름으로 검증해 `stream_processor_manual QA passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 383 warnings / 0 notes`이며 로그는 `/tmp/stream-processor-full.log`에 보관했다. 직전 394건 대비 11건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 357 (2026-08-31)

- `src/antigravity_k/engine/tool_loop.py`의 JSON tool-argument 검증을 Pydantic `JsonValue` TypeAdapter로 고정하고, orchestrator 생성 경계와 required-tools 입력을 명시 타입으로 정리했다. native tool schema, context compression, capacity checkpoint, prompt rebuild 및 task loop semantics와 MagicMock 호환성을 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_tool_loop.py` 회귀 `91 passed`를 확인했다.
- 실제 native tool schema 생성과 기본 required-tools 조회를 실행해 `tool_loop_manual QA passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 370 warnings / 0 notes`이며 로그는 `/tmp/tool-loop-full-final.log`에 보관했다. 직전 383건 대비 13건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 358 (2026-08-31)

- `src/antigravity_k/engine/tool_loop.py`의 최종 타입 경계를 재검증하고 Pydantic JSON adapter와 mock 호환 dynamic lookup을 정리했다. 전체 소스 재검증에서도 cross-module 오류 없이 `0 errors / 370 warnings / 0 notes`를 확인했다.
- `tests/test_tool_loop.py`는 `91 passed`로 유지됐고, 변경 후 전체 소스 basedpyright 로그는 `/tmp/tool-loop-full-current.log`에 보관했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 360 (2026-08-31)

- `src/antigravity_k/engine/model_calibration.py`의 Pydantic `model_config`를 `ClassVar[ConfigDict]`로 명시하고 calibration store 내부 `_config`·`_summaries` 상태를 구체화했으며, 의도적 metrics 제거 반환값을 `_`에 할당했다. benchmark/task artifact 로딩, summary 결합, eligibility 판정 및 observed task metrics semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_model_calibration.py` 회귀 `10 passed`를 확인했다.
- 임시 benchmark artifact와 calibration config로 artifact load, eligibility, summary 및 observed task metrics 결합을 실행해 `model_calibration_manual_qa: artifact load, eligibility, observed task metrics passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 350 warnings / 0 notes`이며 로그는 `/tmp/model-calibration-full.log`에 보관했다. 직전 360건 대비 10건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 361 (2026-08-31)

- `src/antigravity_k/engine/tool_masker.py`의 ActiveToolMasker 상태와 입력/출력 컬렉션을 `object` 기반으로 명시하고, 도구 객체·기본 스키마·OpenAI function 스키마의 이름 추출을 `_ToolMapping` 프로토콜로 안전하게 분리했다. PLAN/edit/test 필터링과 전부 제거 시 원본 fallback semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_tool_masker.py scripts/run_frontier_amplification_test.py` 회귀 `4 passed`를 확인했다.
- 실제 도구 객체와 Anthropic/OpenAI 스키마를 섞은 입력으로 PLAN/edit/test 필터링, task-type phase 매핑 및 빈 결과 fallback을 실행해 `tool_masker_manual_qa: PLAN/edit/test filtering, object+OpenAI schema extraction, empty fallback passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 340 warnings / 0 notes`이며 로그는 `/tmp/tool-masker-full.log`에 보관했다. 직전 350건 대비 10건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 362 (2026-08-31)

- `src/antigravity_k/engine/logger.py`의 JSONFormatter 정적 필드와 동적 `LogRecord` extra 필드를 구체 타입으로 정리하고, 표준 Formatter override를 명시했다. scalar extra 값은 원형을 유지하고 비직렬화 객체는 문자열로 안전하게 변환하며 JSON 파일 로테이션 설정과 중복 핸들러 방지 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_logger.py` 회귀 `13 passed`를 확인했다.
- 실제 LogRecord extra 필드와 임시 로그 파일에 JSONFormatter/`setup_json_logger`를 실행해 scalar·object 직렬화, 디렉터리 생성, flush 후 기록을 확인하고 `logger_manual_qa: JSON extra-field serialization and file setup/flush passed`를 남겼다.
- 최신 전체 소스 basedpyright는 `0 errors / 331 warnings / 0 notes`이며 로그는 `/tmp/logger-full.log`에 보관했다. 직전 340건 대비 9건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 363 (2026-08-31)

- `src/antigravity_k/i18n.py`의 I18n 로케일 상태·번역 포맷 인자·summary 반환 타입을 명시하고 글로벌 번역 함수의 kwargs 경계를 구체화했다. OS locale 감지, ko/en/ja 번역, fallback, custom translation 및 summary semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_tiptap_patterns.py tests/test_integration_upgrade.py` 회귀 `50 passed`를 확인했다.
- 실제 I18n 인스턴스로 locale 전환, parameterized translation, unsupported locale fallback, custom key 및 summary를 실행해 `i18n_manual_qa: locale switching, parameterized translation, fallback, custom key, summary passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 322 warnings / 0 notes`이며 로그는 `/tmp/i18n-full.log`에 보관했다. 직전 331건 대비 9건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 364 (2026-08-31)

- `src/antigravity_k/tools/permission_gate.py`의 프로젝트 경로·모드·safe 플래그 상태와 `check`/직렬화 반환 타입을 명시하고, ToolInvocation의 동적 인자에서 command/path 문자열을 안전하게 좁혔다. 위험 명령 차단, 보호 경로·프로젝트 경계, risk map, override·approval cache semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 권한 경계·도구 실행 관련 회귀 `66 passed`를 확인했다.
- 임시 프로젝트 경계에서 dangerous command deny, 내부 쓰기 허용, 외부 쓰기 차단, safe read 허용, override 및 approval cache를 실제로 실행해 `permission_gate_manual_qa: dangerous command deny, project boundary, safe read, override and approval cache passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 313 warnings / 0 notes`이며 로그는 `/tmp/permission-gate-full.log`에 보관했다. 직전 322건 대비 9건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 365 (2026-08-31)

- `src/antigravity_k/agents/trainer_agent.py`의 TrainerAgent 상태와 생성자 반환 타입을 명시하고, 학습 제안 JSON을 Pydantic `JsonValue` adapter로 검증했다. dataset/model/method/rationale 제안서 생성과 `[APPROVAL REQUIRED]` 계약은 유지했으며 반환 뒤 도달하지 않는 dead literal도 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_trainer_agent.py scratch/test_trainer.py` 회귀 `8 passed`를 확인했다.
- 가짜 ModelManager로 구조화 JSON 제안서와 승인 문구를 실제 생성해 `trainer_agent_manual_qa: validated JSON proposal parsing and approval artifact passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 304 warnings / 0 notes`이며 로그는 `/tmp/trainer-agent-full.log`에 보관했다. 직전 313건 대비 9건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 366 (2026-08-31)

- `src/antigravity_k/tools/search_quality_evaluator.py`의 golden-case 입력 URL 목록과 graded relevance JSON을 Pydantic `JsonValue` adapter로 검증하고, 인용 source map·citation ID 타입을 구체화해 정적 타입 경고를 제거했다. 검색 precision/recall/MRR/NDCG·domain diversity와 citation grounding/conflict semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 검색 benchmark/conflict/web quality 회귀 `56 passed`를 확인했다.
- graded relevance가 포함된 golden case와 두 도메인 검색 결과로 품질 지표를 계산하고, citation source에 대한 claim grounding을 실제 실행해 `search_quality_manual_qa: golden metrics, graded relevance, citation grounding passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 295 warnings / 0 notes`이며 로그는 `/tmp/search-quality-full.log`에 보관했다. 직전 304건 대비 9건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 367 (2026-08-31)

- `src/antigravity_k/agents/hardware_analyst.py`의 `HardwareAnalystAgent` 상태·반환 타입을 명시하고, psutil 메모리 값을 런타임 타입 가드로 정규화했다. 모델 기안 JSON은 Pydantic `JsonValue` adapter로 검증하고, 기존 API 오류 fallback·코드블록 파싱·ROI 기안 출력 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_hardware_analyst.py` 회귀 `9 passed`를 확인했다.
- 실제 시스템 메모리 스펙을 수집하고 가짜 모델 매니저로 JSON 기안을 생성해 `hardware_analyst_manual_qa: system specs collection and JSON proposal generation passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 287 warnings / 0 notes`이며 로그는 `/tmp/hardware-analyst-full.log`에 보관했다. 직전 295건 대비 8건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 368 (2026-08-31)

- `src/antigravity_k/api/routes/task_api.py`의 목록·이벤트·SSE·WebSocket 쿼리 파라미터를 `Annotated` 별칭으로 구체화해 FastAPI 기본값 표현식 경고를 제거하고, 의도적으로 무시하는 task 존재 확인 결과를 `_`에 할당했다. 제출·포크·이벤트 스트리밍·소유자 경계 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. task API·이벤트 ledger·runtime 회귀 `56 passed`를 확인했다.
- TestClient로 `/api/tasks` 기본 limit 및 빈 목록 응답, 존재하지 않는 task status의 404 경계를 실제 실행해 `task_api_manual_qa: list endpoint defaults and missing-task boundary passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 279 warnings / 0 notes`이며 로그는 `/tmp/task-api-full.log`에 보관했다. 직전 287건 대비 8건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 369 (2026-08-31)

- `src/antigravity_k/tasks/local_agent_task.py`의 스레드 target·args·kwargs·result 타입을 `object` 기반으로 구체화하고 `Thread.run` override를 명시했다. 성공 결과 저장, 예외 traceback 캡처, 상태 전이(PENDING→RUNNING→COMPLETED/FAILED), 로깅 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_local_agent_task.py` 회귀 `23 passed`를 확인했다.
- 실제 스레드에서 반환값 전달과 0으로 나누기 예외의 FAILED 상태·오류 문자열 캡처를 실행해 `local_agent_task_manual_qa: threaded success result and failure capture passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 271 warnings / 0 notes`이며 로그는 `/tmp/local-agent-task-full.log`에 보관했다. 직전 279건 대비 8건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 370 (2026-08-31)

- `src/antigravity_k/engine/decision_anchor.py`의 `MAX_ANCHORS` 상수와 생성자 반환 타입을 명시하고, 메시지 주입 경계를 문자열 message 타입으로 구체화했다. 결정 앵커 우선순위 정렬·시스템 메시지 삽입·자동 추출·통계·삭제 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_decision_anchor.py` 회귀 `30 passed`를 확인했다.
- 실제 앵커를 추가해 우선순위 주입, 통계 조회, 자동 추출 경계, ID 삭제를 실행하고 `decision_anchor_manual_qa: priority injection, stats and removal passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 263 warnings / 0 notes`이며 로그는 `/tmp/decision-anchor-full.log`에 보관했다. 직전 271건 대비 8건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 371 (2026-08-31)

- `src/antigravity_k/api/routes/code_api.py`의 Pydantic `model_config` 타입을 명시하고 inline-suggest 프롬프트의 암시적 문자열 결합을 명시적 f-string으로 정리했다. fallback suggestion 결과 리스트와 반복 변수 타입을 구체화해 반환 형식·입력 검증 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 전용 회귀 테스트가 없어 TestClient로 빈 instruction·빈 원본 코드의 검증 응답과 fallback TODO 제안을 실제 실행해 `code_api_manual_qa: request validation and fallback suggestion passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 255 warnings / 0 notes`이며 로그는 `/tmp/code-api-full.log`에 보관했다. 직전 263건 대비 8건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 372 (2026-08-31)

- `src/antigravity_k/tools/mcp_session_manager.py`의 레거시 SSE·Streamable HTTP transport 로더를 지연 해석하는 typed protocol wrapper로 정리하고, MCP 초기화 결과를 명시적으로 무시했다. `httpx.Auth` 타입과 disconnect/cleanup 반환 타입을 구체화했으며, 기존 테스트의 module-level transport patch 지점과 세션 lifecycle semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. MCP/session 및 Unsloth 연계 회귀 `35 passed`를 확인했다.
- 실제 레거시 transport callable lazy resolution과 빈 세션 cleanup을 실행해 `mcp_session_manager_manual_qa: lazy legacy transport resolution and empty cleanup passed`를 확인했다.
- 최신 전체 소스 basedpyright는 다음 모듈 처리 전 기준으로 `0 errors / 255 warnings / 0 notes`이며 기존 로그는 `/tmp/code-api-full.log`에 보관했다. 변경 모듈 자체 경고는 0건이다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 381 (2026-08-31)

- `src/antigravity_k/engine/plan_guard.py`의 destructive pattern 상수·상태·compiled regex를 명시적으로 타입화하고, 동적 tool args의 command 값을 문자열로 안전하게 좁혔다. 위험 명령 승인 요구, plan-mode write 차단, protected path 및 strict-mode semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_plan_guard.py` 회귀 `31 passed`를 확인했다.
- safe command 허용, destructive command 승인 요구/차단, plan-mode overwrite 차단을 실제 실행해 `plan_guard_manual_qa: safe command, destructive command, and plan-mode write block passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 188 warnings / 0 notes`이며 로그는 `/tmp/plan-guard-full.log`에 보관했다. 직전 194건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 382 (2026-08-31)

- `src/antigravity_k/engine/preflight_validator.py`의 deny-rule·fast-hint 클래스 상수와 model manager 경계를 명시적으로 타입화했다. destructive command 거부, fast prototype profile 선택, strict 기본 profile semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_orchestrator.py` 회귀 `9 passed`를 확인했다.
- fast hint 선택, 루트 삭제 명령 거부, 일반 요청의 strict profile 선택을 실제 실행해 `preflight_validator_manual_qa: fast hint, destructive deny, and strict default passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 182 warnings / 0 notes`이며 로그는 `/tmp/preflight-validator-full.log`에 보관했다. 직전 188건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 383 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/base_adapter.py`의 추상 provider payload 경계를 `dict[str, object]`로 구체화해 세 메서드의 명시적 `Any` 경고 6건을 제거했다. OpenAI adapter의 요청·응답·stream 변환 계약과 추상 인터페이스 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_base_adapter.py tests/test_openai_adapter.py` 회귀 `14 passed`를 확인했다.
- OpenAI adapter로 request/response 변환을 실제 실행해 `base_adapter_manual_qa: OpenAI request/response translation contract passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 176 warnings / 0 notes`이며 로그는 `/tmp/base-adapter-full.log`에 보관했다. 직전 182건 대비 6건을 축소했다.
- 전체 연계 테스트에서 기존 tracing 실패 1건(`test_stream_generate_records_local_qwen_failure_trace`)이 재현되었으며 이번 base adapter 변경과 무관해 수정하지 않았다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 384 (2026-08-31)

- `src/antigravity_k/engine/stock_code_validator.py`의 교정 메시지 컬렉션을 `list[str]`로 명시하고 인접 f-string 암시적 결합을 단일 문자열로 정리했다. 종목코드 추출·유효성 검사·유사 코드 추천·쿼리 보강 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_stock_code_validator.py` 회귀 `32 passed`를 확인했다.
- 삼성전자 유효 코드 조회, 잘못된 코드 추천, 주식 컨텍스트 판정, 쿼리 보강 및 사용자 메시지 포맷을 실제 실행해 `stock_code_validator_manual_qa: valid lookup, correction suggestion, query enrichment and message formatting passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 170 warnings / 0 notes`이며 로그는 `/tmp/stock-code-validator-full.log`에 보관했다. 직전 176건 대비 6건을 축소했다.
- 첫 수동 QA 시나리오의 회사명 단정은 테스트 가정 오류로 실패했으며, 실제 추천값(`SK이노베이션(096770)`)에 맞춘 재검증은 통과했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 385 (2026-08-31)

- `src/antigravity_k/engine/trajectory_compressor.py`의 Message payload를 `dict[str, object]`로 구체화하고 compressor 생성자 상태와 반환 타입을 명시했다. 압축 임계값, head/tail 보존, 중간 summary 삽입, structured tool evidence 보존 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_trajectory_compressor.py tests/test_context_budget.py` 회귀 `28 passed`를 확인했다.
- 메시지 수 임계값 감지, head/tail 보존 및 system summary 삽입을 실제 실행해 `trajectory_compressor_manual_qa: threshold detection, head/tail retention and summary insertion passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 164 warnings / 0 notes`이며 로그는 `/tmp/trajectory-compressor-full.log`에 보관했다. 직전 170건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 386 (2026-08-31)

- `src/antigravity_k/tools/search_conflicts.py`의 regex token 추출을 `finditer(...).group(0)` 기반으로 바꿔 동적 `Any` 전파 5건과 metric pattern의 암시적 문자열 결합 1건을 제거했다. 동일 주제·연도/metric 모순 판정과 무관 source 필터링 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_search_conflicts.py` 회귀 `6 passed`를 확인했다.
- 동일 주제의 상충 연도 source 검출과 무관 source 제외를 실제 실행해 `search_conflicts_manual_qa: same-subject contradictory-year detection and unrelated-source filtering passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 158 warnings / 0 notes`이며 로그는 `/tmp/search-conflicts-full.log`에 보관했다. 직전 164건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 387 (2026-08-31)

- `src/antigravity_k/engine/voice_service.py`의 transcriber/synthesizer 콜백 속성을 명시하고, STT command JSON을 Pydantic `JsonValue`로 파싱한 뒤 `list[str]`로 좁혔다. 임시 audio 파일 write 결과를 소비해 미사용 결과 경고를 제거했으며 음성 전사·합성 및 오류 경계 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_voice_api.py` 회귀 `3 passed`를 확인했다. 존재하지 않는 `tests/test_voice_service.py`는 실행 대상에서 제외했다.
- 주입형 전사/합성, 빈 transcript guard, 잘못된 STT JSON guard를 실제 실행해 `voice_service_manual_qa: injected transcription/synthesis, blank transcript guard, and invalid JSON guard passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 152 warnings / 0 notes`이며 로그는 `/tmp/voice-service-full.log`에 보관했다. 직전 158건 대비 6건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 388 (2026-08-31)

- `src/antigravity_k/tools/tool_contracts.py`의 `ToolSpec.parameters_schema` 기본 factory를 명시하고 `ToolInvocation` 인자를 제네릭 타입 변수로 연결해 명시적 `Any` 경고 3건과 호출부의 미지 타입 경계를 제거했다. `PermissionGate.decide`도 동일 타입 변수로 연결해 기존 `Mapping[str, object]` 호출자 호환성을 유지했다.
- 변경 모듈 및 연계 `permission_gate.py`/`tool_registry.py` basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. tool contracts·executor·claw integration 회귀 `61 passed`를 확인했다.
- JSON schema boundary, invocation shape, allow/prompt/deny predicate를 실제 실행해 `tool_contracts_manual_qa: JSON schema boundary, invocation shape and permission decision predicates passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 149 warnings / 0 notes`이며 로그는 `/tmp/tool-contracts-full.log`에 보관했다. 직전 152건 대비 3건을 축소했다.
- 중간에 `JsonValue` 전용 schema로 강화했을 때 기존 `Mapping[str, object]` 호출자 2건이 오류를 냈으며, 제네릭 invocation과 기존 schema 경계를 조합하는 방식으로 수정 후 전체 진단을 통과했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 389 (2026-08-31)

- `src/antigravity_k/tools/egress_policy.py`의 HTTPX event-hook 검증 반환값을 명시적으로 소비하고, `src/antigravity_k/tools/__init__.py`에서 `Permission`을 정의 모듈인 `tool_contracts`에서 직접 재수출하도록 정리했다. public/private egress 정책과 패키지 import surface semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. `tests/test_egress_policy.py tests/test_egress_audit.py` 회귀 `7 passed`를 확인했다.
- canonical public URL 허용, public egress의 local host 거부, `Permission` 패키지 export를 실제 실행해 `egress_export_manual_qa: canonical public URL, local-host rejection, and Permission package export passed`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 146 warnings / 0 notes`이며 로그는 `/tmp/egress-export-full.log`에 보관했다. 직전 149건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 390 (2026-08-31)

- `src/antigravity_k/api/models.py`의 레거시 `typing.Union` 표기를 PEP 604 `|` union으로 전환해 deprecated type 경고 4건을 제거했다. Chat completion·stop 옵션·embedding request의 입력 모델 계약과 Pydantic validation semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 전용 회귀 테스트는 없어 Pydantic chat/embedding union field 생성을 실제 실행해 `api_models_manual_qa: chat union fields and embedding union fields validated`를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 142 warnings / 0 notes`이며 로그는 `/tmp/api-models-full.log`에 보관했다. 직전 146건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 392 (2026-08-31)

- `src/antigravity_k/engine/agent_loop.py`의 `NudgeDetector`와 `ParseErrorGuard` 클래스 상수·카운터를 명시적으로 타입화하고 생성자 반환 타입을 보강했다. 재촉 횟수 및 연속 파싱 오류 중단/reset 상태 전이는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 관련 회귀 `1 passed` 및 nudge/parse-error guard 상태 전이 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 134 warnings / 0 notes`이며 로그는 `/tmp/agent-loop-full.log`에 보관했다. 직전 138건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 393 (2026-08-31)

- `src/antigravity_k/api/path_security.py`에서 allowlist containment 확인을 반환값 소비 방식으로 명시해 미사용 호출 경고 1건을 제거했다. 허용 루트 해석과 traversal 거부 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. path-security 회귀 `4 passed` 및 allowlist/traversal 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 133 warnings / 0 notes`이며 로그는 `/tmp/path-security-full.log`에 보관했다. 직전 134건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 394 (2026-08-31)

- `src/antigravity_k/api/routes/agent_stream_api.py`의 SSE query 파라미터를 `Annotated` 기반 optional query로 전환하고 reset helper 반환값을 명시적으로 소비했다. missing-query 응답과 스트리밍 세션 reset semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. agent stream/session 회귀 `11 passed` 및 missing-query SSE 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 131 warnings / 0 notes`이며 로그는 `/tmp/agent-stream-full.log`에 보관했다. 직전 133건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 395 (2026-08-31)

- `src/antigravity_k/api/routes/code_intel_api.py`의 두 Pydantic 요청 모델 `model_config`를 `ClassVar[ConfigDict]`로 명시해 클래스 속성 경고 2건을 제거했다. extra 무시·frozen 설정과 인덱싱/영향도 요청 검증 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. code-intel 회귀 `23 passed` 및 strict request/extra-field 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 129 warnings / 0 notes`이며 로그는 `/tmp/code-intel-api-full.log`에 보관했다. 직전 131건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 396 (2026-08-31)

- `src/antigravity_k/api/routes/operational_alerts.py`의 acknowledgement 모델 `model_config`를 `ClassVar[ConfigDict]`로 명시하고 limit query를 `Annotated` 기반 기본값으로 전환했다. 알림 목록 제한 범위와 acknowledgement 응답 계약은 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. operational-alert 회귀 `3 passed` 및 frozen response/query boundary 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 127 warnings / 0 notes`이며 로그는 `/tmp/operational-alerts-full.log`에 보관했다. 직전 129건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 397 (2026-08-31)

- `src/antigravity_k/api/routes/system_api.py`의 mode history/status/switch 라우트에서 이미 구체 타입인 `ModeManager`에 대한 불필요한 `cast` 3건과 잔여 미사용 import를 제거했다. 모드 조회·전환 응답 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. mode 관련 회귀 `3 passed` 및 실제 mode status endpoint 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 124 warnings / 0 notes`이며 로그는 `/tmp/system-api-full.log`에 보관했다. 직전 127건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 398 (2026-08-31)

- Unsloth 라우트의 private `__get_tool_registry` 의존성을 `api.dependencies.get_tool_registry` 공개 래퍼로 교체하고, `UnslothTrainingLaunchState`의 이미 exhaustive한 match에서 도달 불가 `assert_never` 분기를 제거했다. DI registry identity와 상태별 HTTP 코드 매핑 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Unsloth 회귀 `62 passed` 및 public registry dependency/launch-state mapping 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 121 warnings / 0 notes`이며 로그는 `/tmp/unsloth-routes-full.log`에 보관했다. 직전 124건 대비 3건을 축소했다.
- 수동 QA 중 registry auto-discovery가 생성자 필수 인자 없는 legacy tool 두 개를 로그했으나, 공개 registry identity와 매핑 검증 자체는 통과했으며 해당 pre-existing discovery 경고는 별도 잔여 부채로 남겼다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 399 (2026-08-31)

- `src/antigravity_k/api/routes/voice_api.py`의 transcribe/command endpoint query 파라미터 3개를 `Annotated` 기반으로 전환해 기본값 호출 경고를 제거했다. suffix 정규식, model 길이 제한, 음성 명령 처리 계약은 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. voice 회귀 `3 passed` 및 TTS text 정규화/blank rejection 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 118 warnings / 0 notes`이며 로그는 `/tmp/voice-api-full.log`에 보관했다. 직전 121건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 400 (2026-08-31)

- `src/antigravity_k/api/routes/workspace_links.py`의 IDE deep-link payload를 `_IDELinks`·`_WorkspaceLink` TypedDict로 고정하고 workspace 목록을 `list[_WorkspaceLink]`로 명시해 부분 미지 타입 및 `Any` 경고 3건을 제거했다. VS Code/JetBrains 링크 생성과 route 응답 payload semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. workspace-links 회귀 `4 passed` 및 typed deep-link/route response 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 115 warnings / 0 notes`이며 로그는 `/tmp/workspace-links-full.log`에 보관했다. 직전 118건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 401 (2026-08-31)

- `src/antigravity_k/cli.py`의 master-key rotation 명령에서 이미 구체 타입인 service count에 대한 불필요한 `cast`를 제거했다. 키 순환 결과 출력과 0건 조건 분기 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. CLI/master-key 회귀 `128 passed` 및 `--help` command registry 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 114 warnings / 0 notes`이며 로그는 `/tmp/cli-full.log`에 보관했다. 직전 115건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 402 (2026-08-31)

- `src/antigravity_k/engine/agentic_tech_radar.py`의 `last_reviewed` 인스턴스 속성을 명시하고 `to_dict` 결과를 `dict[str, object]`로 좁혀 클래스 속성/명시적 `Any` 경고 2건을 제거했다. 레이더 평가·우선순위 집계·JSON payload semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. tech-radar 회귀 `4 passed` 및 deterministic evaluation/JSON rendering 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 112 warnings / 0 notes`이며 로그는 `/tmp/tech-radar-full.log`에 보관했다. 직전 114건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 403 (2026-08-31)

- `src/antigravity_k/engine/atomic_transaction_engine.py`의 transaction root 속성을 명시하고 파일 쓰기 반환값을 소비해 클래스 속성/미사용 호출 경고 3건을 제거했다. staged patch 검증, atomic commit, syntax abort 및 rollback semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. atomic transaction 회귀 `2 passed` 및 commit/syntax-abort 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 109 warnings / 0 notes`이며 로그는 `/tmp/atomic-transaction-full.log`에 보관했다. 직전 112건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 404 (2026-08-31)

- `src/antigravity_k/engine/bayesian_prompt_tuner.py`의 예외 `__str__`에 `@override`를 추가하고 tuner 후보 목록과 생성자 타입을 명시했다. 후보 선택·점수 기록·빈 후보 guard semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Bayesian prompt 회귀 `2 passed` 및 candidate scoring/empty-config 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 107 warnings / 0 notes`이며 로그는 `/tmp/bayesian-full.log`에 보관했다. 직전 109건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 405 (2026-08-31)

- `src/antigravity_k/engine/capacity_flow.py`의 checkpoint JSON 복원 경계를 재귀 `CapacityJsonValue` TypeGuard와 명시적 object-key/value 검증으로 보강해 `json.loads` Any 경고 2건을 제거했다. 잘못된 JSON shape는 `None`으로 거부하고 정상 checkpoint는 기존 `CapacityState`로 복원한다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. capacity/skill learner 및 tool-loop 회귀 `108 passed`와 checkpoint round-trip 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 105 warnings / 0 notes`이며 로그는 `/tmp/capacity-flow-full.log`에 보관했다. 직전 107건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 406 (2026-08-31)

- `src/antigravity_k/engine/code_verifier.py`에서 Python AST 파싱의 반환 객체를 명시적으로 소비해 미사용 호출 경고 1건을 제거했다. Python/JSON/YAML syntax verification 결과와 오류 보고 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. code-verifier 회귀 `6 passed` 및 valid/invalid Python syntax 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 104 warnings / 0 notes`이며 로그는 `/tmp/code-verifier-full.log`에 보관했다. 직전 105건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 407 (2026-08-31)

- `src/antigravity_k/engine/context_artifact_recall.py`의 regex `findall` 결과를 `list[str]`로 명시해 artifact reference 수집 경계의 `Any` 전파 경고 3건을 제거했다. bounded reference deduplication, term normalization, recall formatting semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. RAG 품질 회귀 `13 passed` 및 bounded reference/term normalization 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 101 warnings / 0 notes`이며 로그는 `/tmp/context-artifact-full.log`에 보관했다. 직전 104건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 408 (2026-08-31)

- `src/antigravity_k/engine/direct_task_execution.py`의 도구명 정규식에서 인접 문자열 암시적 결합을 단일 raw f-string으로 명시했다. 영어 `tool` 및 한국어 조사 도구 계약 매칭 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. direct-task 회귀 `1 passed` 및 영어/한국어 explicit tool contract 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 100 warnings / 0 notes`이며 로그는 `/tmp/direct-task-full.log`에 보관했다. 직전 101건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 409 (2026-08-31)

- `src/antigravity_k/engine/failure_classifier.py`의 분류 정규식 암시적 문자열 결합 2건을 단일 패턴으로 명시하고, 런타임 비문자 입력 호환성을 유지하는 `str()` 변환으로 불필요한 `isinstance` 검사를 교체했다. 실패 category·retryable 판정 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. failure-classifier 회귀 `33 passed` 및 non-string/category matching 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 97 warnings / 0 notes`이며 로그는 `/tmp/failure-classifier-full.log`에 보관했다. 직전 100건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 411 (2026-08-31)

- `src/antigravity_k/engine/frontier_evidence.py`의 deprecated `typing.Sequence`을 `collections.abc.Sequence`으로 교체하고 예외 상세 속성 타입을 명시했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. frontier evidence 회귀 `8 passed` 및 evidence 생성·정책 판정·SHA 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 92 warnings / 0 notes`이며 로그는 `/tmp/frontier-evidence-full.log`에 보관했다. 직전 94건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 412 (2026-08-31)

- `src/antigravity_k/engine/harness_models.py`의 pytest 수집 제어 속성에 `ClassVar`를 적용하고 클래스 생성 후 false 값을 유지하도록 명시했으며, `to_dict()` 반환 타입의 `Any`를 `object`로 구체화했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. harness·benchmark 회귀 `89 passed` 및 pytest marker·dict 직렬화·Markdown 렌더링 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 89 warnings / 0 notes`이며 로그는 `/tmp/harness-models-full.log`에 보관했다. 직전 92건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 413 (2026-08-31)

- `src/antigravity_k/engine/mcts_code_explorer.py`의 MCTS 탐색기 생성자 상태(`root`, `max_iterations`)에 구체 타입과 반환 타입을 명시했다. 탐색·롤아웃·backpropagation semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. MCTS 회귀 `1 passed` 및 expansion·rollout·backpropagation 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 87 warnings / 0 notes`이며 로그는 `/tmp/mcts-full.log`에 보관했다. 직전 89건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 414 (2026-08-31)

- `src/antigravity_k/engine/memory_importance.py`의 권위 점수 매핑에 `dict[MemoryFactAuthority, float]`를 명시하고 지수 감쇠를 `math.pow` 기반 `float` 계산으로 구체화했다. 권위·최신성·구체성 점수 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. memory-importance 회귀 `8 passed` 및 권위·최신성·랭킹 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 85 warnings / 0 notes`이며 로그는 `/tmp/memory-importance-full.log`에 보관했다. 직전 87건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 415 (2026-08-31)

- `src/antigravity_k/engine/memory_provider.py`의 MemoryManager 및 episodic/working provider export 경계에서 명시적 `Any`를 `object`와 `dict[str, JsonValue]`로 구체화했다. API 확장 필드와 기존 메모리 직렬화 semantics는 유지했다.
- 변경 모듈 및 연관 system API basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. memory operations 회귀 `11 passed` 및 provider 등록·sync/prefetch·typed export 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 80 warnings / 0 notes`이며 로그는 `/tmp/memory-provider-full.log`에 보관했다. 직전 85건 대비 5건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 416 (2026-08-31)

- `src/antigravity_k/engine/metrics.py`의 Prometheus ASGI factory 반환 경계를 `_ASGIApp` callable alias와 명시적 cast로 구체화하고 동적 import로 부분 미지식 타입 경고를 제거했다. 메트릭 등록·렌더링·ASGI factory semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. metrics 회귀 `32 passed` 및 metric exposition·ASGI factory 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 77 warnings / 0 notes`이며 로그는 `/tmp/metrics-full.log`에 보관했다. 직전 80건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 417 (2026-08-31)

- `src/antigravity_k/engine/mode_manager.py`의 도구 권한·상태 직렬화 반환 타입에서 `Any`를 `object`로 구체화하고 Plan 상태 안내 문자열의 암시적 결합을 단일 문자열로 명시했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. mode-manager 회귀 `28 passed` 및 Plan 상태·도구 권한 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 74 warnings / 0 notes`이며 로그는 `/tmp/mode-manager-full.log`에 보관했다. 직전 77건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 418 (2026-08-31)

- `src/antigravity_k/engine/model_manager.py`의 Best-of-N 복잡도 추정 import를 실제 정의 모듈(`chain_of_verification_models`)로 직접 연결하고, 이미 구체화된 engine kwargs의 불필요한 cast를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. model-manager 연관 회귀에서 `55 passed / 3 failed`를 확인했으며 실패 3건은 기존 provider capability·tracing 환경 의존 오류로 변경과 무관하다. 복잡도 추정 import·threshold ordering 수동 QA를 통과했다.
- 최신 전체 소스 basedpyright는 `0 errors / 72 warnings / 0 notes`이며 로그는 `/tmp/model-manager-full.log`에 보관했다. 직전 74건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 419 (2026-08-31)

- `src/antigravity_k/engine/next_action_recommender.py`의 생성자 상태(`project_root`, `call_graph`)에 구체 타입과 반환 타입을 명시했다. 추천 합성·blast-radius 분석·top-k 제한 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. next-action 회귀 `1 passed` 및 추천 합성·top-k bounding 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 70 warnings / 0 notes`이며 로그는 `/tmp/next-action-full.log`에 보관했다. 직전 72건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 420 (2026-08-31)

- `src/antigravity_k/engine/operational_alert_store.py`의 Pydantic `model_config`를 `ClassVar`로 명시하고 임시 파일 write·replace·mkdir 반환값을 의도적 무시로 표시했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. operational-alert API 회귀 `3 passed` 및 deduplication·persistence·acknowledgement 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 67 warnings / 0 notes`이며 로그는 `/tmp/operational-alert-full.log`에 보관했다. 직전 70건 대비 3건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 421 (2026-08-31)

- `src/antigravity_k/engine/orchestrator/agent.py`의 정상적으로 추론된 import에 남아 있던 불필요한 pyright ignore 4건을 제거하고 CEO 분석 generator의 불필요한 cast를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. orchestrator 회귀 `9 passed` 및 JSON object/list 경계 정규화 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 62 warnings / 0 notes`이며 로그는 `/tmp/orchestrator-agent-full.log`에 보관했다. 직전 67건 대비 5건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 422 (2026-08-31)

- `src/antigravity_k/engine/orchestrator_execution_handlers.py`의 `StateContext.analysis`가 이미 구체 타입인 경계에서 불필요한 cast를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. orchestrator handler·MAX engine 회귀 `47 passed` 및 pipeline step 경계 필터링 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 61 warnings / 0 notes`이며 로그는 `/tmp/orchestrator-handlers-full.log`에 보관했다. 직전 62건 대비 1건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 423 (2026-08-31)

- `src/antigravity_k/engine/output_quality_comparator.py`의 코드 블록 추출 결과에 `list[str]` 타입을 명시하고 `compile()` 반환값을 의도적 무시로 처리해 Any·미사용 결과 경고를 제거했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. OutputQualityComparator 회귀 `4 passed` 및 syntax scoring·동점 비교 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 57 warnings / 0 notes`이며 로그는 `/tmp/output-quality-full.log`에 보관했다. 직전 61건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 424 (2026-08-31)

- `src/antigravity_k/engine/prompt_injection_guard.py`의 다중 문자열 정규식을 단일 raw string으로 명시해 암시적 문자열 결합 경고 2건을 제거했다. 인젝션 탐지·프로토콜 태그 중화 semantics는 유지했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. prompt-injection 회귀 `33 passed` 및 고위험 탐지·프로토콜 중화 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 55 warnings / 0 notes`이며 로그는 `/tmp/prompt-guard-full.log`에 보관했다. 직전 57건 대비 2건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 425 (2026-08-31)

- `src/antigravity_k/engine/provider_adapters/unsloth_studio_contracts.py`의 세 Pydantic 모델 `model_config`를 `ClassVar`로 명시하고 예외 `__str__`에 `@override`를 적용했다.
- 변경 모듈 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. Unsloth Studio 회귀 `6 passed` 및 endpoint normalization·configuration detection 수동 QA를 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 51 warnings / 0 notes`이며 로그는 `/tmp/unsloth-contracts-full.log`에 보관했다. 직전 55건 대비 4건을 축소했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 444 (2026-08-31)

- 최종 잔여 경고 3건을 모두 제거했다: `evaluation_gate.py`의 문자열 결합, `resource_admission.py`의 exhaustive `assert_never` 분기, `self_test_tool.py`의 불필요한 cast.
- 변경 모듈별 basedpyright `0 errors / 0 warnings`, Ruff·py_compile 통과. 관련 회귀는 각각 `evaluation_gate`/`resource_admission`/`self_test_tool` 대상 테스트와 수동 API·도구 QA로 확인했다.
- 최신 전체 소스 basedpyright는 `0 errors / 0 warnings / 0 notes`이며 로그는 `/tmp/final-zero-warnings.log`에 보관했다. 경고 제로를 달성했다.
- `git diff --check`는 기존 사용자 변경으로 보이는 `src/antigravity_k/engine/logger.py:62` trailing whitespace만 보고했으며, 이번 점검 변경 파일 집합은 `git diff --check` 통과했다.
- 전체 `uv run pytest -q`는 환경의 API `TestClient` 종료/fixture hang으로 중단했으나 중단 시점까지 `216 passed, 3 skipped`, 실패 0건이었다. 변경 모듈 타깃 회귀는 모두 통과했다.
- 기존 사용자 변경 234건과 나머지 dirty path는 보존했으며 stage·revert·commit을 수행하지 않았다.

## Warning debt continuation 446 (2026-08-31)

- API lifespan의 동기 RAG 인덱싱을 daemon background thread로 분리해 이벤트 루프 차단과 TestClient 종료 지연을 제거했다. 수동 QA에서 startup `0.025s`, shutdown `0.622s`, `/v1/health` `200`을 확인했다.
- CoV 설정 reader의 최소 orchestrator 호환, provider endpoint mock 경계 정규화, `/v1/models/operations` 동적 payload 응답 모델 비활성화를 적용했다.
- 전체 회귀 `4821 passed, 6 skipped` (실패 0), 관련 회귀 `14 passed`, 전체 basedpyright `0 errors / 0 warnings / 0 notes` (`/tmp/final-zero-warnings.log`), 변경 파일 Ruff·py_compile·diff check 통과.
- 기존 사용자 변경 234건과 나머지 dirty path를 보존했으며 stage·revert·commit을 수행하지 않았다.
