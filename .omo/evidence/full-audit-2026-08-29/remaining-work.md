---
title: Antigravity-K remaining work inventory
tags: [audit, backlog, ownership, warning-zero]
date: 2026-08-29
---

# 남은 작업 인벤토리

## 현재 기준

- 최신 검증 코드 커밋: `f6b83a0` (debate demo checkpoint 안전성 정리; 증적 문서 커밋은 `a687e60`)
- 전체 `basedpyright`: `0 errors, 24982 warnings, 0 notes` (provider stream 경계와 model manager·lintai scanner·call hierarchy·impact analyzer·token bucket·debate demo·장학금 필터·tool-loop·MAX 테스트·KTX 구현 파일 경고를 단계적으로 축소; 전체 경고는 사용자 변경 파일과 동적 테스트 경계에 잔존)
- 전체 pytest 기준선: `4806 passed, 6 skipped` (최신 tool-loop·장학금 회귀 포함)
- 대시보드: typecheck, lint, Vitest `42 files / 588 tests`, production build 통과
- 대시보드 `npm audit --omit=dev`: `0 vulnerabilities` (Monaco major 변경 없이 override 적용)
- 사용자 소유 dirty path: 244개. 생성된 `src/antigravity_k/dashboard_dist/` 산출물도 포함
- Git tracked+untracked Python 871개 AST 검사에서 현존 파일 문법 오류 0건을 확인했다. 삭제 상태인 tracked Python 12개는 외부 호환성 검토 대상으로 남아 있다.
- codebase-memory MCP: `Transport closed` 상태로 인덱스 영향 분석이 일시 중단됨
- 앱 재시작 후 `mcp__codebase_memory_mcp__list_projects`와 `index_repository(mode=fast)`를 재시도했지만 모두 `Transport closed`가 재현됐다. 외부 MCP 프로세스/세션 복구 전까지 shell·LSP·회귀 테스트 증빙으로 보완한다.
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

## 다음 우선순위

1. `src/antigravity_k/engine/tool_loop.py` 소스의 orchestrator/manager 동적 경계를 Protocol로 분리해 파일 경고를 `369 → 13`으로 축소했다. 남은 경고는 보호 메서드, 생성자 호환용 동적 경계, JSON decoder·이벤트 버스·state-store의 외부 타입 경계이며, 파일이 사용자 변경과 겹쳐 현재 미커밋이다. 다음 단계는 소유권 확인 후 hunk 단위 독립 커밋이다.
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
