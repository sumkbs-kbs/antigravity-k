---
title: sandbox unavailable 대응 런북 (CR-03/CR-04)
status: draft-runbook-validated-by-tests (CR-03·CR-04 REVIEW)
date: 2026-09-12
plan: ../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md
checklist: ../17_COMMERCIAL_RELIABILITY_CHECKLIST.md
tags: [runbook, sandbox, seatbelt, shell, cr-03, cr-04]
---

# sandbox unavailable 대응 런북

CR-03(읽기 경계)과 CR-04(API shell 실행 경계)는 **raw 폴백 없음**을 계약으로 정했다. sandbox를
만들 수 없으면 호스트 셸로 대체하지 않고 거부한다. 이 문서는 그 거부를 만났을 때 운영자가
확인할 순서를 설명한다.

계약의 전체 정의는 [읽기 경계](CR03_SANDBOX_READ_BOUNDARY.md)와
[실행 경계](CR04_SHELL_EXECUTION_BOUNDARY.md)에 있다.

## 증상 → 의미

| 증상 | 의미 | 해야 할 일 |
|---|---|---|
| 503 `sandbox_unavailable` | 정책 생성 또는 backend 없음. **호스트 셸 실행 0회** | sandbox 활성화/backend 확인 |
| 403 `shell_approval_required` | 권한 모드가 ASK(읽기 전용) | 승인 workflow가 없다 — 모드를 바꾸거나 다른 경로 사용 |
| 403 `shell_policy_denied` | Plan 등 도구 차단 모드, 위험 명령, 경계 밖 `cwd` | 요청 범위/모드를 확인 |
| 504 `shell_timeout` | 제한 시간 초과(자식은 종료됨) | 명령을 나눠 실행 |

`security.sandbox_enabled=false`인 배포에서는 `POST /api/agent/tools/shell/run`이 **설계대로
동작하지 않는다**(503). 이는 결함이 아니라 fail-closed 계약이다.

## 절차

1. **설정 값을 확인한다.**
   ```bash
   grep -n "sandbox_enabled" config.yaml 2>/dev/null || echo "config.yaml 에 sandbox_enabled 없음(기본값 확인 필요)"
   ```
2. **현재 OS에서 backend가 존재하는지 확인한다.** Seatbelt(`sandbox-exec`) 실측은 macOS만이다.
   ```bash
   uname -s
   command -v sandbox-exec || echo "seatbelt 없음 → 이 호스트는 shell 실행 경계를 지원하지 않는다"
   ```
3. **서버 로그에서 거부 이유를 확인한다**(공개 응답에는 내부 원문이 없다).
   ```bash
   # 오류 원문은 서버 로그에만 남는다
   grep -i "sandbox" data/logs/*.log 2>/dev/null | tail -20 || echo "로그 경로를 배포 설정에서 확인"
   ```
4. **거부가 정상임을 사용자/고객에게 설명할 수 있게 정리한다.**
   - macOS: Seatbelt 프로필 생성 실패(예: 손상된 프로필 경로, 권한) → 서버 재시작 후 재시도.
   - Linux/Docker: seatbelt backend가 없다 → 이 호스트에서는 shell 실행을 **사용할 수 없다**.
     Docker의 bind mount를 읽기 경계로 쓰는 경로는 검증 대기다.
5. **우회하려 하지 않는다.** `sandbox_enabled=false`로 두고 호스트 실행을 쓰는 것은 계약 위반이며
   이 저장소는 그 경로를 제공하지 않는다. 필요하면 별도 작업으로 범위를 정한다.
6. **대안 경로를 안내한다.** 파일 읽기/쓰기 작업은 에이전트의 파일 도구(승인 흐름 포함)로
   수행하고, 셸이 꼭 필요하면 macOS 호스트에서 실행한다.

## 확인

- 경계 회귀(macOS):
  ```bash
  uv run --no-sync python -m pytest tests/test_cr03_sandbox_read_boundary.py \
    tests/test_cr04_shell_api_boundary.py -q
  ```
- 503 계약 확인(테스트는 sandbox 비활성 주입으로 검증한다):
  ```bash
  uv run --no-sync python -m pytest tests/test_cr04_shell_api_boundary.py -q -k "unavailable or 503"
  ```
- Linux/Docker에서는 위 테스트가 skip될 수 있다. **skip을 통과로 승격하지 않는다** — 지원
  매트릭스에서 해당 행은 여전히 검증 대기다.

## 롤백

- sandbox를 끄고 호스트 실행으로 되돌리는 롤백은 없다(그 상태가 CR-03/CR-04가 닫은 결함이다).
- 경계가 업무를 막는 경우: 실행할 수 있는 호스트를 macOS로 한정하거나, 승인 workflow를
  신설하는 별도 작업을 연다(계획 CR-04가 별도 명세로 남긴 항목).

## 남은 위험 / 지원 범위

- Seatbelt 실측은 macOS만이다. Linux/Docker backend는 mock/코드 경로로만 검증됐고,
  [지원 매트릭스](GA_SUPPORT_MATRIX.md)에서 `Experimental`이다(BLOCKED_EXTERNAL).
- 조상 디렉터리 이름은 자식에 보일 수 있다(파일 내용·형제 subtree는 열리지 않는다).
- 시간 제한(504)은 자식 종료를 보장하지만, 자식이 만든 외부 부작용(네트워크 호출 등)의
  롤백은 하지 않는다 — egress는 별도 정책으로 차단한다.
