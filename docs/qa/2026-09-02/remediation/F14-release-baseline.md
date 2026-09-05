---
title: F14 release-baseline 검증기 사각지대 해소 진행 기록
tags: [qa, remediation, release-baseline, spdx, license, entrypoints]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
---

# F14 진행 기록

F14 작업을 완료했다. release-baseline 검증기(`release_baseline.py`)의 AGPL/GPL SPDX 리터럴 및 대소문자/변형 검사 누락 사각지대를 해소하고, 엔트리포인트(CLI 서브커맨드, HTTP API 라우트, ASGI 서버 앱, Web UI 스크립트)의 계약 무결성 검증을 추가했다. 또한 테스트 실행 시 저장소에 추적되는 원본 벤치마크/정책 파일을 변조하지 않도록 `tmp_path` 격리 픽스처로 전면 개선했다.

## 시작 상태

- Baseline HEAD: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`
- 관련 파일: `src/antigravity_k/engine/release_baseline.py`, `tests/test_release_baseline.py`, `THIRD_PARTY_PROVENANCE.toml`, `docs/RELEASE_POLICY.md`

## 원본 재현

### 1. AGPL SPDX 단독 식별자 미탐지
`tests/fixtures/release_baseline/vendor.py`에 `# SPDX-License-Identifier: AGPL-3.0-only`를 작성하고 검증기를 실행했을 때:
- 기존 검증기는 `spdx.upper().startswith("AGPL")`일 경우 `readable_agpl_marker`("GNU AFFERO GENERAL PUBLIC LICENSE")만 검사하고 SPDX 식별자 자체를 검색 대상에서 제외(`if not spdx.upper().startswith("AGPL")`)하여 거절하지 못하고 통과함.

### 2. 엔트리포인트 커맨드/라우트 누락 미탐지
`THIRD_PARTY_PROVENANCE.toml`의 엔트리포인트 커맨드를 `["agk", "task", "nonexistent"]` 등으로 변조했을 때:
- 소스 파일(`cli.py`)이 디스크에 존재하기만 하면 `path.is_file()` 검사만 수행하므로 커맨드가 실제로 구현되어 있는지 검증하지 못하고 통과함.

## 근본 원인 (Root Cause)

1. **라이선스 텍스트 검사기 사각지대**:
   - `_validate_no_prohibited_source_text`에서 AGPL 항목은 영어 풀네임 문자열만 검사 쌍에 넣고 정작 SPDX 식별자(`AGPL-3.0-only`, `AGPL-3.0-or-later` 등)는 제외함.
   - GPL 항목은 단순 `spdx.upper()` 바이트 검색을 수행하여 소문자 식별자(`gpl-2.0-only`)나 풀네임(`GNU General Public License`)을 놓칠 위험이 있었음.
   - 단순 문자열 검색 시 단어 경계(`\b`)가 없어 `createTrackingPlugin` 같은 정상 식별자에서 거짓 양성(False Positive)이 발생할 위험이 있었음.

2. **엔트리포인트 계약 검증 부재**:
   - `validate_release_baseline`의 엔트리포인트 순회가 파일 존재 여부(`is_file()`)만 검사하여, 함수/커맨드/라우트 삭제 시 탐지 불가.

3. **테스트 내 원본 파일 일시 변조 문제**:
   - 기존 `test_release_baseline.py`가 `PROJECT_ROOT / "data" / "benchmarks" / "held_out_v2.jsonl"` 및 `.freeze.json`을 직접 덮어쓰고 복구하는 방식을 취하여, 병렬 테스트 경합 및 예외 시 저장소 오염 위험이 있었음.

## 구현 내용

### 1. 라이선스 마커 검증기 고도화 (`_build_prohibited_license_matchers`, `_validate_no_prohibited_source_text`)
- 선언된 모든 금지 SPDX 식별자에 대해:
  - 단어 경계(`\b`)를 갖춘 대소문자 무시(case-insensitive) 정규식 생성
  - `SPDX-License-Identifier:\s*<spdx>` 헤더 정규식 생성
- AGPL/GPL 패밀리에 대해:
  - `GNU AFFERO GENERAL PUBLIC LICENSE` / `GNU.AFFERO.GENERAL.PUBLIC.LICENSE`
  - `GNU GENERAL PUBLIC LICENSE` / `GNU.GENERAL.PUBLIC.LICENSE`
  - 대소문자 무시 및 공백/점 변형 지원
- **단일 패스 고속 필터**: 모든 패턴을 결합한 `combined_pattern`으로 1차 고속 스캔(1233개 소스 파일 기준 0.6초 미만) 후, 매칭 발생 시에만 구체적 위반 SPDX를 식별하여 에러 메시지 생성.
- `release_baseline.py` 자체 및 symlink, `validator_path`는 검사에서 제외.

### 2. 엔트리포인트 계약 무결성 검증 (`_validate_entrypoints`)
- **CLI (`kind="cli"`)**:
  - `pyproject.toml`의 `[project.scripts]`에 루트 바이너리(`agk`) 선언 검증.
  - 소스 코드 AST 분석(`_extract_cli_command_paths`): Typer 앱 및 `add_typer` 하위 앱의 커맨드 트리(`("agk", "task", "resume")`, `("agk", "serve")` 등)를 추적하여 실제 등록 여부 검증.
- **Server (`kind="server"`)**:
  - 소스 코드 AST 분석으로 최상위 ASGI `app` 인스턴스 할당 확인.
  - CLI 연동 커맨드(`["agk", "serve"]`)가 CLI 트리에 존재하는지 검증.
- **HTTP API (`kind="http-api"`)**:
  - 소스 코드 AST 분석(`_extract_http_routes`): `@router.get`, `@router.post`, `@router.api_route` 등의 데코레이터에서 HTTP 메서드와 엔드포인트 경로(`("GET", "/api/tasks/{task_id}/events")`) 존재 검증.
- **Web UI (`kind="web-ui"`)**:
  - `package.json`의 `scripts` 필드에서 실행 대상 스크립트(`dev`) 존재 검증.

### 3. 테스트 개선 및 안전성 확보 (`tests/test_release_baseline.py`)
- AGPL/GPL의 다양한 SPDX 표기(`AGPL-3.0-only`, `AGPL-3.0-or-later`, `agpl-3.0-only`, `GPL-2.0-only`, `GPL-3.0-or-later`, 풀네임 등) 거절 테스트 10종 추가.
- `Apache-2.0`, `MIT`, `createTrackingPlugin`, `default_training_platform` 등 정상 허용 코드의 거짓 양성 미발생 검증 테스트 추가.
- CLI/HTTP/Web UI 커맨드/라우트 미구현 시 명확한 `ReleaseBaselineError` 거절 테스트 4종 추가.
- 벤치마크 데이터 변조 테스트 2종을 `tmp_path` 기반 복사본 검증으로 전환하여 저장소 파일 변조 위험 완전 제거.

## 검증 결과

### 1. 테스트 결과
```bash
uv run --no-sync pytest tests/test_release_baseline.py -v
```
- 결과: **23 passed in 2.55s** (기존 8건 -> 23건으로 확대 통과)

### 2. 연관 릴리스 검사 회귀 테스트
```bash
uv run --no-sync pytest tests/test_release_metadata.py tests/test_release_sbom.py -v
```
- 결과: **19 passed in 0.19s**

### 3. 정적 분석 및 린트
```bash
uv run --no-sync ruff check src/antigravity_k/engine/release_baseline.py tests/test_release_baseline.py
uv run --no-sync mypy src/antigravity_k/engine/release_baseline.py
uv run --no-sync basedpyright src/antigravity_k/engine/release_baseline.py tests/test_release_baseline.py
```
- `ruff`: All checks passed.
- `mypy`: Success: no issues found in 1 source file.
- `basedpyright`: 0 errors, 0 warnings, 0 notes.

## 정리 및 사용자 변경 보존

- 사용자 변경 `data/benchmark_results.json` 및 이전 작업자의 작업 결과 보존 확인.
- `tests/fixtures/release_baseline` 잔여 파일 없음.
- 다음 우선순위는 **F15 정적 검사와 행동 기반 보안 테스트**이다.
