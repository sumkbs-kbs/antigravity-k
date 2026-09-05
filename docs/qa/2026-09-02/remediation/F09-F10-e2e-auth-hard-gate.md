---
title: F09/F10 E2E 인증 fixture 및 hard gate 진행 기록
tags: [qa, e2e, authentication, ci, hard-gate, remediation]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: verified_fixed_pending_commit
verification_utc: 2026-09-03T03:18:00Z
---

# F09/F10 진행 기록

F09는 모든 Playwright page helper가 임의 `ag_access_pin=0000`을 몰래 주입하던 fixture를 제거하고, no-auth/legacy PIN/token 상태를 구분했다. F10은 접근성만 통과하면 전체 E2E가 통과한 것처럼 보이던 CI 구조를 전체 Playwright suite hard gate로 바꾸고, shell pipeline이 실패 종료 코드를 보존함을 실제 실패로 검증했다.

## F09 수정 계약

1. `DashboardPage.goto()`는 credential을 discriminated union으로 받는다: `none`, `legacyPin`, `token`. 기본값은 `none`이며 인증이 꺼진 로컬 backend에서 임의 PIN을 주입하지 않는다.
2. 실제 PIN modal 제출은 `submitPin()`에서 명시적으로만 수행한다. 페이지 이동만으로 인증을 시도하거나, helper가 PIN을 대신 제출하지 않는다.
3. `handlePinModal()`을 삭제했다. 각 시나리오가 PIN modal 필요 여부를 직접 검증한다.
4. Command palette는 app 마운트를 기다린 뒤 실제 `ControlOrMeta+k` 키 입력으로 연다. 버튼 클릭 fallback이 키보드 계약 검증을 대신하지 않는다.
5. `auth-bootstrap.spec.ts`는 실제 backend/API/UI만 사용한다:
   - no-auth: `/api/auth/login` 503과 dashboard 정상 부팅
   - invalid legacy PIN: UI 거절, `localStorage`/`sessionStorage` credential 제거
   - valid configured PIN: 임시 auth 서버에서 실제 UI login과 token 저장
   - expired token: TTL 0 서버에서 발급한 token이 PIN dialog로 fallback하고 입력에 focus
6. auth 서버는 매 시나리오가 소유한 임시 상태 디렉터리와 테스트 PIN/secret만 사용한다. 사용자 `data/auth_hash`, `data/token_secret`을 읽지 않는다. worker가 고정 자격 증명을 공유하지 않는다.
7. Chat E2E의 `/v1/chat/completions`는 deterministic SSE route fulfill로 고정한다. UI 상태 계약 검증을 실제 provider 가용성과 분리하되, provider 자체를 성공했다고 주장하지 않는다. stream 중 send button이 “중단”으로 동작하는 실제 제품 계약에 맞춰 다중 메시지는 stream 종료 후 전송한다.

## F10 수정 계약

1. Full Playwright suite step에서 `continue-on-error`를 제거했다. 이제 접근성만 통과한 상태를 전체 E2E green으로 표시할 수 없다.
2. Python smoke, accessibility, full suite 명령 모두 `set -o pipefail`과 함께 `2>&1 | tee`로 실행한다. pytest/Playwright의 nonzero가 tee 뒤에서 사라지지 않는다.
3. Full suite의 임시 출력을 다른 E2E 결과와 분리하기 위해 `PLAYWRIGHT_OUTPUT_DIR=test-results-full`을 유지한다.
4. no-auth backend라도 임시 token secret/pin hash 경로를 지정한다. CI 환경이 사용자/로컬 인증 상태에 우연히 의존하지 않는다.
5. CI 주석에서 더 이상 유효하지 않은 “12 tests” hard gate 설명을 제거했다.
6. Full suite는 실패 전파가 검증된 hard gate라는 주석을 유지한다. 이 주석은 pipeline 실패 조건을 설명하는 실행 계약이다.
7. 로컬 `make audit`도 `pip-audit`/`bandit`의 `|| true`를 제거해 보안 도구 nonzero를 보존한다. `security` target이 이 audit를 포함하므로 로컬 게이트 역시 실패를 전파한다.

## F10 RED → GREEN 증거

수정 전에는 full suite가 `continue-on-error: true`였고 pipeline에 `pipefail`이 없었다. 따라서 접근성 12건만 통과하면 전체 E2E 실패가 job 실패로 전파되지 않았다.

CI 변경 후 의도적으로 실패하는 일시 테스트로 실제 전파를 확인했다:

```bash
set -o pipefail
pnpm --dir dashboard exec playwright test e2e/tests/hard-gate-probe.spec.ts \
  --project=chromium --reporter=list 2>&1 | tee /tmp/agk-f10-hard-gate.log
```

관찰된 결과:

```text
1 failed
PIPELINE_EXIT=1
```

일시 테스트, `/tmp` spec, `dashboard/test-results` probe artifact는 검증 직후 제거했다. 이 실패를 제품 regression으로 보고하지 않는다.

## 검증 결과

전체 실행 환경: baseline HEAD `6d0a24d4e6a0686693ce29a4d13a69443ae5149b` 위의 미커밋 수정, 실제 backend `127.0.0.1:18173`, PIN 없음, 임시 auth state. 사용자 인증 파일 미사용.

| 검사 | 결과 |
|---|---|
| Focused auth/command/chat | 15 passed |
| 기존 page-object/a11y/security/task suite | 44 passed |
| 전체 Playwright | 59 expected, 0 unexpected, 0 skipped, 0 flaky, exit 0 |
| Dashboard TypeScript | exit 0 |
| Dashboard lint | exit 0 |
| CI/release YAML strict parse | duplicate key 없음, parse 성공 |
| `git diff --check` | exit 0 |
| `git status --short dashboard/node_modules` | dirty 0 |
| Hard gate 실패 전파 | 의도적 실패 1건 → pipeline exit 1 |
| `make -n audit` | `pip-audit --strict --desc`, `bandit ...`에 `|| true` 없음 |

전체 Playwright 원문은 pnpm preamble가 JSON 앞에 포함되어 있으므로 `raw.slice(raw.indexOf('{'))`로 파싱해야 한다. 원문과 정규화 통계副本을 evidence에 보존했다.

## 구현 및 지문

변경 파일:

- `dashboard/e2e/pages/DashboardPage.ts`
- `dashboard/e2e/tests/auth-bootstrap.spec.ts`
- `dashboard/e2e/tests/chat.spec.ts`
- `dashboard/e2e/tests/command-palette.spec.ts`
- `dashboard/e2e/tests/file-explorer.spec.ts`
- `dashboard/e2e/tests/git.spec.ts`
- `dashboard/e2e/tests/navigation.spec.ts`
- `.github/workflows/ci.yml`
- `Makefile`

정확한 SHA-256은 [metadata.json](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/metadata.json)에 있다.

Evidence directory: `.omo/evidence/f09-f10-e2e-auth-hard-gate/`

| 자료 | 링크 |
|---|---|
| 전체 Playwright JSON 원문 | [playwright-full-before-ci-cleanup.json](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/playwright-full-before-ci-cleanup.json) |
| 정규화 통계 | [playwright-full-normalized.json](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/playwright-full-normalized.json) |
| 실패 전파 로그 | [hard-gate-failure-propagation.log](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/hard-gate-failure-propagation.log) |
| TypeScript 로그 | [typecheck.log](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/typecheck.log) |
| Lint 로그 | [lint.log](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/lint.log) |
| 파일 지문/환경 메타데이터 | [metadata.json](../../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/metadata.json) |

## 발견한 추가 결함과 수정

CI 검토 중 `Run Full Playwright E2E Suite` step에 `run:` 키가 중복으로 남아 있었다. 임의 YAML loader는 마지막 키를 취할 수 있으므로 실행에서 우연히 통과할 수 있지만, workflow 정합성 오류이다. 중복 블록을 제거하고 unique-key loader로 `ci.yml`/`release.yml`을 다시 파싱해 duplicate key가 없음을 확인했다.

## 정리

- backend uvicorn PID 21978(port 18173)을 Ctrl+C로 정상 종료했다.
- `/tmp/agk-f09-noauth.4mkChE` 임시 상태 디렉터리를 제거했다.
- hard gate probe 테스트와 `/tmp` spec, 실패 context artifact를 제거했다.
- `data/benchmark_results.json` 및 다른 agent/user 변경을 되돌리지 않았다.
- 커밋, push, 배포를 수행하지 않았다.

## 한계 및 다음 에이전트 지시

1. 이 검증은 로컬 Linux/macOS 환경이 아니라 현재 macOS 격리 환경에서 수행했다. GitHub Actions의 실제 runner에서 전체 job이 green/fail로 종료하는지는 workflow 실행 증거가 추가로 필요하다.
2. CI full suite가 backend 기본 API/상태에 의존하는 테스트를 포함한다. CI에서 데이터/파일 경로가 격리되어 있는지 최초 실제 workflow 실행에서 다시 확인해야 한다.
3. 실제 LLM/provider 이중화 및 offline 품질 검증은 이번 범위가 아니다. Chat E2E는 deterministic SSE로 UI contract만 검증한다.
4. 백엔드 종료 로그에 `task_execution_context` ContextVar reset이 서로 다른 Context에서 발생했다는 `ValueError`가 반복 출력됐다. 테스트 결과에는 영향이 없었지만 stream cleanup 경계의 별도 결함 후보로 남는다.
5. CI 주석/step 자체가 아니라 실제 GitHub Actions 상태 전이까지 검증하려면 workflow_dispatch 또는 PR 실행 결과를 evidence로 보존해야 한다. 권한/원격 조작은 사용자가 별도 지시할 때만 수행한다.
6. 이 수정은 커밋하지 않았다. metadata.json의 지문과 baseline HEAD로 대상을 확인한 뒤 커밋해야 한다.
