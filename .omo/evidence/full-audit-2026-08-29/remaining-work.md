---
title: Antigravity-K remaining work inventory
tags: [audit, backlog, ownership, warning-zero]
date: 2026-08-29
---

# 남은 작업 인벤토리

## 현재 기준

- 최신 검증 커밋: `aa8fb2a` (web-search 테스트 fixture 및 실행 입력 경계 기록 포함)
- 전체 `basedpyright`: `0 errors, 31827 warnings, 0 notes`
- 전체 pytest 기준선: `4803 passed, 6 skipped` (최신 소스 단위 회귀는 별도 재실행 기록)
- 대시보드: typecheck, lint, Vitest `42 files / 588 tests`, production build 통과
- 대시보드 `npm audit`: low 1, moderate 3, high 0, critical 0
- 사용자 소유 dirty path: 244개. 생성된 `src/antigravity_k/dashboard_dist/` 산출물도 포함
- codebase-memory MCP: `Transport closed` 상태로 인덱스 영향 분석이 일시 중단됨

## 실행 순서와 완료 조건

1. **tests/scripts/skills 경고 부채 축소**
   - 우선순위: `tests/test_tool_loop.py`, `tests/test_data_extractor.py`, `tests/test_integration_d1_d2_d4.py`, `tests/test_secure_key.py`, `scripts/benchmark_viz.py`, `.agent/skills/**`의 고경고 파일
   - 원칙: fixture/결과 타입을 좁히고 동작은 보존한다. 광범위한 경고 억제 지시문은 사용하지 않는다.
   - 완료: 변경 파일 Ruff/mypy/basedpyright 경고 0, 관련 회귀 테스트 통과, 독립 커밋과 ledger 기록

2. **대시보드 의존성·산출물 결정**
   - 남은 audit은 중첩 Monaco/typed-rest-client 경로이며 breaking/upstream 조정 여부를 확인한다.
   - `dashboard_dist` 해시 산출물은 사용자 변경으로 간주하고 삭제·정리·커밋하지 않는다.
   - 완료: audit 결과와 산출물 처리 결정을 문서화하고, 승인된 범위만 별도 커밋

3. **codebase-memory Transport closed 복구 후 영향 재분석**
   - 복구 전에는 shell/LSP/현재 진단 산출물로 보완하며, transport가 열리면 repository re-index 후 변경 영향과 호출 경로를 재검증한다.
   - 완료: index 상태, 재분석 결과, 실패 시 재현 조건을 기록

4. **244개 사용자 변경사항 파일별 검토**
   - `git status --short` 기준으로 src/tests/dashboard/docs/data/scripts/.tmp 및 단일 파일을 분류한다.
   - 기존 변경은 누가 만들었는지와 무관하게 검토하되, 명시적 소유권 확인 없이는 stage/commit/revert하지 않는다.
   - 완료: 파일별 위험·테스트·커밋 후보 목록과 독립 커밋 정책을 ledger에 기록

5. **최종 게이트**
   - 전체 pytest, dashboard checks, global Ruff, basedpyright, `git diff --check`를 최신 HEAD에서 재실행한다.
   - 잔여 경고/감사/Transport 제한을 숨기지 않고 최종 보고서에 남긴다.

## 최근 완료 단위

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
