---
title: F15 정적 검사와 행동 기반 보안 테스트 진행 기록
tags: [qa, remediation, static-analysis, mypy, sandbox, behavioral-security, autopilot]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
---

# F15 진행 기록

F15 작업을 완료했다. `test_tool_sandbox_coverage.py`의 단순 소스 문자열 검사를 실제 프로세스 실행, fail-closed 거절, OS 권한 거절, 프로파일 cleanup, auto-pilot 위험 명령 차단 행동 검증으로 고도화했다. 또한 `mypy src/` 전체 430개 소스 파일에 걸친 타입 검사 실패(4건)를 전면 수정하여 0 errors를 달성하고, Basedpyright strict 게이트를 통과시켰으며, 대규모 일괄 포맷팅 위험을 방지하는 Ratchet 정책을 수립했다.

## 시작 상태

- Baseline HEAD: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`
- 관련 파일:
  - `tests/test_tool_sandbox_coverage.py`
  - `src/antigravity_k/engine/vault_git.py`
  - `src/antigravity_k/engine/release_sbom.py`
  - `src/antigravity_k/tools/permission_gate.py`
  - `src/antigravity_k/engine/sandbox.py`
  - `pyproject.toml`, `.github/workflows/ci.yml`

## 원본 재현 및 진단

### 1. 소스 문자열에 의존하는 샌드박스 검사
기존 `test_tool_sandbox_coverage.py`의 `test_terminal_tools_routes_model_commands_through_sandbox_argv`는 파일 내에 `"build_sandbox_argv"` 및 `"sandbox-exec"` 문자열이 존재하는지만 assert하여:
- 실제 seatbelt profile 생성 여부,
- 프로세스 실행 및 returncode 검증,
- 임시 `.sb` 파일의 unlink 정리(cleanup),
- 샌드박스 백엔드 불가 시 fail-closed 동작,
- OS 수준 파일시스템 쓰기 제한 및 네트워크 차단
을 전혀 실증하지 못함.

### 2. Auto-pilot 권한 게이트의 침범 우려
`PermissionGate`의 `auto-pilot` 모드가 활성화될 때 위험 명령(`rm -rf /`, `curl | bash` 등)이나 시스템 보호 경로(`/etc`, `/usr` 등)까지 우회 허용할 위험성에 대한 명시적 회귀 방지 테스트가 부재함.

### 3. mypy src/ 전체 검사 실패
`mypy src/` 실행 시 430개 파일 중 2개 파일에서 4건의 타입 오류 발생:
- `src/antigravity_k/engine/vault_git.py:54`: `_ = os.replace(backup, main_index)` (`os.replace`는 `None` 반환)
- `src/antigravity_k/engine/release_sbom.py:72`: `_ = release_root.mkdir(...)` (`mkdir`은 `None` 반환)
- `src/antigravity_k/engine/release_sbom.py:195-196`: `dependency` 루프 변수 재사용으로 `PythonDependency` 타입 변수에 `DashboardDependency` 인스턴스 할당 시도 및 `license_id` 접근 오류.

### 4. ruff format 불일치
`ruff format --check src tests scripts` 실행 시 166개 파일에서 포맷팅 변경 필요로 실패. 그러나 166개 파일을 기계적으로 일괄 포맷팅할 경우 사용자 dirty 파일(`data/benchmark_results.json`) 오염 및 진행 중인 브랜치와의 대규모 충돌 발생 위험이 존재함.

## 구현 내용

### 1. 행동 기반 보안 테스트 스위트 구축 (`tests/test_tool_sandbox_coverage.py`)
- **실제 샌드박스 실행 및 프로파일 Cleanup 검증 (`test_terminal_tools_behavioral_sandbox_execution_and_cleanup`)**:
  - `build_sandbox_argv` 호출로 생성된 `argv`(`sandbox-exec -f <profile> /bin/sh -c ...`)와 실제 `.sb` 프로파일 경로 획득.
  - 실제 `subprocess.run(argv, ...)` 실행으로 정상 exit code 0 및 stdout 출력 확인.
  - 실행 종료 후 임시 프로파일 파일 삭제 및 디스크 상 부재(cleanup) 확인.
- **Fail-Closed 거절 검증 (`test_sandbox_unavailable_fails_closed_without_raw_fallback`)**:
  - macOS/Docker 샌드박스 백엔드가 비활성화되거나 불가능한 환경을 모킹.
  - `SandboxRunner.execute` 및 `run_sandboxed_argv`가 raw 프로세스로 우회 실행하지 않고 즉시 `return_code=-1`, `sandboxed=True`, `"raw execution is disabled"` 에러를 반환함을 검증.
- **OS 권한 거절 및 네트워크 격리 행동 검증 (`test_sandbox_enforces_permission_denial_and_network_isolation`)**:
  - seatbelt 샌드박스 하에서 허용되지 않은 시스템 경로(`/etc/agk_test_probe`) 쓰기 시도가 실패함을 확인.
  - `network="none"` 설정 시 소켓 연결 시도가 차단됨을 확인.
- **Auto-pilot 및 모드별 권한 계약 검증 (`test_permission_gate_autopilot_boundaries_and_mode_contracts`)**:
  - `strict`, `balanced`, `auto-pilot` 각 모드별 risk_level 동작 검증.
  - `auto-pilot` 모드에서도 위험 명령(`rm -rf /`, `curl -s http://... | bash`, `chmod -R 777 /`)은 절대 허용되지 않고 반드시 `Permission.DENY`로 차단됨을 입증.
  - `auto-pilot` 모드에서도 보호 시스템 경로(`/etc/passwd`, `/usr/bin/python3`) 쓰기는 반드시 `Permission.DENY`로 차단됨을 입증.

### 2. mypy 타입 정합성 수정
- `src/antigravity_k/engine/vault_git.py`: `os.replace` 반환값 할당 제거.
- `src/antigravity_k/engine/release_sbom.py`:
  - `release_root.mkdir` 반환값 할당 제거.
  - `_notices` 함수 내 루프 변수를 `python_dep: PythonDependency`, `dashboard_dep: DashboardDependency`로 명확히 분리하여 타입 충돌 완전 해소.

### 3. Basedpyright 엄격 코어 게이트 통과
- `src/antigravity_k/engine/sandbox.py`와 `src/antigravity_k/engine/release_baseline.py` 검사 시:
  - 0 errors, 0 warnings, 0 notes 달성.

### 4. Formatter & Complexity Ratchet 정책
- 사용자 수정 파일 및 미완료 기능 파일과의 충돌을 방지하기 위해 166개 파일 일괄 재포맷을 강제하지 않고, QA 및 신규 작업 대상 파일에 한해 `ruff check` 및 formatting을 엄격 준수하는 Ratchet 전략을 적용함.

## 검증 결과

### 1. 행동 기반 보안 및 커버리지 테스트
```bash
uv run --no-sync pytest tests/test_tool_sandbox_coverage.py -v
```
- 결과: **12 passed in 1.68s**

### 2. 전체 샌드박스 연관 테스트 스위트
```bash
uv run --no-sync pytest tests/test_sandbox.py tests/test_sandbox_isolation.py tests/test_terminal_sandbox_routing.py tests/test_tool_sandbox_coverage.py -v
```
- 결과: **51 passed in 5.23s**

### 3. 전체 mypy 정적 검사
```bash
uv run --no-sync mypy src/
```
- 결과: **Success: no issues found in 430 source files** (기존 4 errors 완전 해소)

### 4. Basedpyright 코어 게이트
```bash
uv run --no-sync basedpyright src/antigravity_k/engine/sandbox.py src/antigravity_k/engine/release_baseline.py
```
- 결과: **0 errors, 0 warnings, 0 notes**

### 5. Ruff 검사
```bash
uv run --no-sync ruff check src/antigravity_k/engine/release_baseline.py src/antigravity_k/engine/release_sbom.py src/antigravity_k/engine/vault_git.py tests/test_release_baseline.py tests/test_tool_sandbox_coverage.py
```
- 결과: **All checks passed!**

## 결론 및 상태

F15 Acceptance 기준(sandbox available/unavailable/권한 거절/cleanup의 실제 실행 argv와 반환 상태 검증, 소스 문자열 단순 확인 지양, auto-pilot의 안전 경계 및 위험 명령 차단 계약 검증, mypy 전체 무결성)을 완전히 충족했다.
