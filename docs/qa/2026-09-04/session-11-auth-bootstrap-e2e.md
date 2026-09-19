---
title: 세션 11 — auth-bootstrap E2E 자급화 + /v1/ws/events graceful shutdown 지연 수정 (진행 기록)
tags: [e2e, auth, websocket, relay, frontend-redesign, session-record]
date: 2026-09-04
branch: codex/m1-task-events
base_sha: 09ac373cd0fabf6460957b66947cac82bd3b2a52
status: completed_uncommitted
---

# 세션 11 진행 기록 — auth-bootstrap E2E + WS shutdown

> 이 문서는 `docs/FRONTEND_REDESIGN_RELAY_2026-09-03.md` §6.1 남은 과제의 완결 기록이다.
> 다른 에이전트는 [릴레이 문서](../FRONTEND_REDESIGN_RELAY_2026-09-03.md)와 이 기록을 함께 읽고 이어서 작업한다.

## Issue

- 릴레이 §6.1: `auth-bootstrap.spec.ts`의 no-auth 시나리오 2건이 **공유 백엔드(8012)의 인증 상태에 의존**하여
  `.env`/`data/auth_hash`에 PIN이 설정된 머신에서 실패. "환경 의존, 코드 결함 아님"으로 방치 상태였다.
- 부수 발견: no-auth 테스트를 자체 서버로 분리하는 과정에서 `/v1/ws/events` 핸들러가
  **클라이언트 disconnect를 감지하지 못해 graceful shutdown이 최대 ~30초 지연**되는 실제 제품 버그 확인.

## Status

- ✅ auth-bootstrap 스펙 4/4 통과 (자체 격리 서버 스폰 방식, 공유 백엔드 불필요)
- ✅ `/v1/ws/events` shutdown 지연 버그 수정 (SIGTERM→exit 194ms)
- ⏳ 미커밋 (다른 작업자 변경과 섞이지 않도록 커밋은 별도 진행)

## Base SHA / Verified SHA

- Base: `09ac373cd0fabf6460957b66947cac82bd3b2a52` (HEAD, 커밋 09ac373)
- Verified: 동일 SHA 위 미커밋 작업 트리 상태

## Owner / 변경 파일

| 파일 | 변경 |
|---|---|
| `dashboard/e2e/tests/auth-bootstrap.spec.ts` | 전면 재작성 — `startBackendServer` 헬퍼로 4개 시나리오 모두 자체 격리 백엔드 스폰 |
| `src/antigravity_k/api/routes/events.py` | `/v1/ws/events` 핸들러: 전용 receive 워처 + `disconnect_event` 레이스로 즉시 종료 |
| `tests/test_events.py` | 회귀 테스트 2건 추가 (즉시 종료 / 이벤트 전달 후 종료) |
| `docs/FRONTEND_REDESIGN_RELAY_2026-09-03.md` | §6.1 완결 처리, §6.2 상태 갱신, status 11차 완결 |

## 원본 재현 (Original reproduction)

1. `data/auth_hash`에 PIN `0000` 해시가 존재하는 머신에서 공유 백엔드 기동 → `/api/auth/login {pin:0000}`가 503이 아닌 200 반환.
2. `npx playwright test e2e/tests/auth-bootstrap.spec.ts` → no-auth 2건 실패, auth 2건 통과 (총 ~33s).
3. 자체 서버 스폰 시도 중: 대시보드가 `/v1/ws/events` WS를 연 뒤 SIGTERM → 서버가 ~28~30초간 종료하지 않음
   (`INFO: Waiting for background tasks to complete. (CTRL+C to force quit)` 후 정지).

## 근본 원인 (Root cause)

1. **auth-bootstrap 환경 의존**: 테스트 1·2가 Playwright `page` fixture(공유 `baseURL` = 8012)를 사용해
   "no-auth 서버"라고 가정했으나, 서버 인증 상태는 머신별 `.env`/`data/auth_hash`에 좌우됨.
2. **WS shutdown 지연**: `events.py`의 `websocket_events`가 `await asyncio.wait_for(queue.get(), timeout=30.0)`로
   큐만 기다리고 `websocket.receive()`를 전혀 호출하지 않음. 서버 종료 시 uvicorn이 transport를 닫아도
   핸들러는 30초 keepalive 타임아웃이 끝나고 나서야(keepalive send 실패) 종료를 인지 → graceful shutdown 최대 ~30초 지연.
   (kanban/task/terminal WS는 `receive()`에 블록하므로 이 문제가 없음 — `/v1/ws/events`가 유일.)

## 구현 및 범위 (Implementation and scope)

### 1) auth-bootstrap 자급화
- `startBackendServer(overrides)` 신설: uvicorn(`--port 0`)을 스폰하고 자식 env를 **명시적으로 고정**:
  - `AGK_SEC_ACCESS_PIN=''`, `AGK_ACCESS_PIN=''` — 빈 문자열은 `load_dotenv(override=False)`로 덮어쓰기 불가
  - `AGK_ENV='development'`, `AGK_ENV_FILE=<임시 빈 파일>` — 머신 `.env` 격리
  - `AGK_SEC_PIN_HASH_FILE=<임시 미존재 경로>` — `data/auth_hash` 미사용 → no-auth면 login 503
  - `AGK_SEC_TOKEN_SECRET_FILE=<임시 랜덤 시크릿>` — `data/token_secret` 미사용
- `startNoAuthServer()` / `startAuthServer(ttl)` 래퍼. 4개 테스트 모두 `browser.newContext({baseURL: server.baseUrl})` 사용.
- 기존 셀렉터·`DashboardPage`·제품 DOM 변경 없음 (F09/F10 계약 유지).

### 2) events.py shutdown 지연 수정
- `_watch_disconnect()` 워처 태스크: `websocket.receive()` 루프로 disconnect(및 서버 종료 시 transport close)를 즉시 감지,
  완료 시 `disconnect_event` set.
- 메인 루프: `asyncio.wait({queue.get(), disconnect_event.wait()}, FIRST_COMPLETED, timeout=30.0)` 레이스.
  - `get_task` 완료 → 이벤트 전송 (send 실패 시 `WebSocketDisconnect`로 즉시 종료)
  - `wait_task` 완료 → 즉시 break
  - 타임아웃 → 기존 keepalive ping 유지
- keepalive 동작은 보존 (`_send_keepalive` 무변경), 구독/해제 균형 유지.

## 계약/마이그레이션 결정 (Contract decision)

- no-auth 시나리오 계약(`/api/auth/login` 503, 대시보드 PIN 모달 없음, legacy PIN 거절 시 credential 제거)은 F09와 동일 유지.
- WS keepalive(30s ping)와 이벤트 전달 순서(큐 우선)는 기존 동작 보존.

## 회귀 시나리오 (Regression scenarios)

- `/v1/ws/events` 정상 구독 → 이벤트 수신/전송
- 30초 idle → keepalive ping
- 클라이언트 정상 종료 → 핸들러 즉시 종료 + 구독 해제
- 서버 SIGTERM (대시보드 연결 중) → 즉시 graceful shutdown
- auth-bootstrap 4개 시나리오 (no-auth 503 / legacy PIN 거절 / PIN 로그인 / 만료 토큰 폴백)

## Before/After 결과

| 항목 | Before | After |
|---|---|---|
| auth-bootstrap 스펙 | 2 failed / 2 passed, ~33s | **4/4 passed, 4.1s** (4 workers) |
| 서버 SIGTERM→exit (대시보드 연결 중) | 28,226ms | **194ms** |
| `tests/test_events.py` | 1 passed | 3 passed (신규 2건) |

## 수동/실측 증거 (Manual surface evidence)

- `NO_PROXY="*" npx playwright test e2e/tests/auth-bootstrap.spec.ts --project=chromium` → 4 passed
- 독립 probe(브라우저로 대시보드 마운트 후 SIGTERM): before 28,226ms → after 194ms (로그: `Shutting down` → 즉시 exit)
- 스크린샷: `test-results/` 내 no-auth-bootstrap.png, invalid-legacy-pin.png, configured-auth.png, expired-token.png

## 전체 스위트 결과 + 선존 실패 (Full-suite result)

- Python: `pytest tests -q` → **4,907 passed / 5 failed / 6 skipped** (선존·환경 의존, 본 작업과 무관):
  - `test_dashboard_wheel_assets.py::test_wheel_...` — `dist/` 빌드 산출물 필요 (미빌드)
  - `test_desktop_context_api.py` 3건 — 타 작업자 미커밋 신규 테스트의 라이브 상태 단언(quota 100 vs 1 등)
  - `test_provider_capabilities.py::test_unsloth_probe_...` — unsloth 엔드포인트 미설정 환경
- WS 관련: `test_events.py` + `test_workspace_websocket*.py` → 31 passed
- Dashboard: `npx tsc --noEmit` → 0 errors
- E2E 전체: **50 passed / 11 failed** — 실패 전수 선존·환경 의존:
  - accessibility 10건: `.folder-sub-preview` color-contrast — 타 작업자의 미커밋 `index.css`/`Sidebar.tsx` 변경에 의한 회귀 (본 작업과 무관, git diff로 신규 추가 라인 확인)
  - `capture-real-local-models.spec.ts` 1건: `orpheus-3b` 모델 실기동 필요 (현재 미실행)

## 정리/보존 (Cleanup and preserved user changes)

- 조사용 임시 파일(`/tmp/probe-*.mjs`, `dashboard/e2e/probe-shutdown.spec.ts`) 삭제 완료.
- 선존 **stale pytest pyc** `tests/__pycache__/test_agent_error_journal.cpython-313-pytest-9.0.3.pyc` 삭제
  (repo rename `antigravity-k`→`Ssak-Ai`로 옛 경로가 박힌 캐시 재사용으로 `test_agent_error_journal`이 가짜 실패 —
  캐시 삭제로 해소, 소스 무변경).
- 다른 작업자의 미커밋 변경(`index.css`, `Sidebar.tsx`, `test_desktop_context_api.py` 등)은 **건드리지 않음**.
- 커밋/push/배포 수행 안 함.

## 잔여 위험 / 다음 에이전트 지시 (Residual risks / next-agent handoff)

1. **a11y 회귀 (선존, 미커밋 프론트엔드 작업)**: `.folder-sub-preview` color-contrast 위반 10건 —
   해당 작업자가 수정하거나, 새 세션에서 `dashboard/src/styles/index.css`의 `.folder-sub-preview` 대비를
   수정한 뒤 a11y 스위트 재실행.
2. **capture-real-local-models**: 로컬 모델(orpheus-3b) 실기동 후에만 통과하는 캡처 유틸 — CI gate로 쓰지 말 것.
3. **auth-bootstrap CI 반영**: 이제 자체 서버 스폰이라 CI 어느 머신에서도 통과 가능.
   `.github/workflows/ci.yml` full-suite step에 포함 여부 확인 필요 (본 세션에서 CI는 미변경).
4. **WS 워처 타임아웃**: disconnect 워처가 없는 다른 long-lived WS(kanban/task/terminal)는 receive 블록 기반이라
   동일 문제 없음을 확인. 터미널 WS(`AGK_ENABLE_TERMINAL_WS`)는 fork/PTY 정리 경로가 별도 — 종료 시
   `ValueError(task_execution_context ...)` 로그(F09 기록의 잔여 관찰)와 무관한지 필요 시 확인.
5. **커밋 시점**: 4개 파일(auth-bootstrap.spec.ts untracked 포함)을 함께 커밋하되, 같은 작업 트리의 다른
   작업자 변경을 `git add -A`로 묶지 말 것.

## 재검증 명령

```bash
cd dashboard && NO_PROXY="*" npx playwright test e2e/tests/auth-bootstrap.spec.ts --project=chromium --reporter=list
uv run --no-sync python -m pytest tests/test_events.py -q
uv run --no-sync ruff check src/antigravity_k/api/routes/events.py tests/test_events.py
uv run --no-sync mypy src/antigravity_k/api/routes/events.py
cd dashboard && npx tsc --noEmit -p tsconfig.json
```
