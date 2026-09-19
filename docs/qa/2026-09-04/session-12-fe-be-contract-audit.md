---
title: 세션 12 — 프론트엔드-백엔드 정합성 전수 감사 + WS 이벤트 계약 갭 수정 (진행 기록)
tags: [contract-alignment, frontend, backend, websocket, event-bus, session-record]
date: 2026-09-04
branch: codex/m1-task-events
base_sha: 09ac373cd0fabf6460957b66947cac82bd3b2a52
status: completed_uncommitted
---

# 세션 12 진행 기록 — FE↔BE 정합성 감사 및 반영

> 사용자 요청: "프론트엔드와 백엔드 간 정합성을 분석하여 미비한 부분 추가 반영해줘".
> 이 문서는 감사 범위·검증 결과(일치 항목)·발견된 갭·수정 내역·검증·잔여 위험을 기록한다.
> 다른 에이전트는 이 기록과 [릴레이 문서](../FRONTEND_REDESIGN_RELAY_2026-09-03.md)를 함께 읽고 이어서 작업한다.

## Issue

- 프론트엔드(dashboard/)가 호출하는 엔드포인트·페이로드·응답 스키마·WS 이벤트가
  백엔드(src/antigravity_k/)와 어긋나는 부분이 있는지 전수 감사하고, 발견된 미비점을 수정한다.

## Status

- ✅ 감사 완료 (엔드포인트 경로/메서드/요청·응답 계약, WS 이벤트 계약)
- ✅ 갭 수정: WS 이벤트 3종(`PlanningModeStarted`/`CognitiveAdaptation`/`FailureDetected`) 백엔드 발행 추가,
  `/v1/ws/events` 구독 목록 보강, `GET /api/system/access-mode` 응답 형태 통일
- ✅ 계약 회귀 테스트 추가 (백엔드 4건 + 프론트엔드 2건) — 전체 통과
- ⏳ 미커밋 (다른 작업자 변경과 섞이지 않도록 커밋은 별도 진행)

## Base SHA / Verified SHA

- Base: `09ac373cd0fabf6460957b66947cac82bd3b2a52` (HEAD, 커밋 09ac373)
- Verified: 동일 SHA 위 미커밋 작업 트리 상태

## Owner / 변경 파일

| 파일 | 변경 |
|---|---|
| `src/antigravity_k/engine/mode_manager.py` | `switch_to_plan()`에서 `PlanningModeStarted{goal}` 발행 (`_publish_planning_started`) |
| `src/antigravity_k/engine/cognitive_loop.py` | `adapt_strategy()` 적응 발생 시 `CognitiveAdaptation{reason, adaptation}` 발행 (`_publish_cognitive_adaptation`) |
| `src/antigravity_k/engine/tool_executor.py` | 실패한 도구 결과에 `FailureDetected{tool, error, message}` 발행 (`_broadcast_failure_event`) |
| `src/antigravity_k/api/routes/events.py` | 구독 목록을 모듈 상수 `TRACKED_EVENTS`로 승격 + `CognitiveAdaptation`, `PlanningModeStarted` 추가 |
| `src/antigravity_k/api/routes/system_api.py` | `GET /api/system/access-mode` 응답에 `ok: true` 추가 (POST와 형태 통일) |
| `tests/test_events.py` | WS 계약 테스트: 프론트엔드 소비 이벤트 ⊆ `TRACKED_EVENTS` |
| `tests/test_mode_manager.py` | `switch_to_plan` → `PlanningModeStarted` 발행 검증 2건 |
| `tests/test_tool_executor.py` | `_post_execute` 실패 시 `FailureDetected` 발행/미발행 검증 2건 |
| `tests/test_cognitive_loop_events.py` | (신규) `adapt_strategy` → `CognitiveAdaptation` 발행/미발행 검증 2건 |
| `dashboard/src/api/contractAlignment.test.ts` | WS 이벤트 계약 테스트 2건 (발행자 페이로드 파싱 + 이벤트 이름 목록 고정) |

## 감사 범위와 방법 (Audit scope & method)

1. **엔드포인트 목록 수집**: `src/antigravity_k/api/routes/*`의 라우터 31개 + `auth_routes.py` 전수 (prefix 포함 ~220개 라우트).
2. **프론트엔드 호출 수집**: `dashboard/src`의 `fetch`/`ky`/`apiRequest`/`apiRequestPath`/`streamChatCompletion`/`WebSocket` 전수.
3. **대조**: 메서드·경로·요청 본문 필드명·응답 스키마(zod) ↔ 백엔드 Pydantic/핸들러 반환.
4. **WS 계약**: `useEventWebSocket.ts`의 discriminatedUnion 이벤트 이름 ↔ `events.py` 구독 목록 ↔ 실제 EventBus 발행자(`mode_manager`, `tool_loop`, `tool_executor`, `cognitive_loop`).

### 일치 확인된 영역 (문제 없음)

- **Git API** (`/api/git/*`): status/log/diff/branches/graph/add/unstage/commit/checkout/branch-create/delete/file-content — 메서드·본문(`path/count/branch`, `file/staged`, `from` alias)·응답(discriminatedUnion `ok`) 모두 일치.
- **Tasks** (`/api/tasks/*`): submit/fork/cancel/resume/status/list/output/events/events-stream — `Task*Response` 필드 전부 zod와 일치.
- **Jobs** (`/api/jobs/*`): list/health/runs/retry — `ScheduledJob`/`JobRun`/`JobHealthSummary` 필드 일치.
- **Agency** (`/api/agency/*`): objectives/status/pause/resume — `ObjectiveStatus` 값(pending/claimed/done/cancelled) 일치.
- **Approval** (`/api/approval/*`): pending/resolve — `to_dict()`(created_at float, timeout_sec, auto_review) 일치.
- **Models** (`/v1/models`, `/api/models/local`, `/api/models/load`, `/v1/models/operations`, `/v1/health`): 응답·`ProviderCapability` 필드 일치.
- **Chat** (`POST /v1/chat/completions`): SSE 청크 `choices[0].delta.content` 일치, 요청 필드(`model/messages/stream/agent_mode/plan_mode/tdd_mode/web_search/code_mode/mcp_servers`) 일치.
- **Vault/Wiki** (`/api/vault/*`, `/v1/notes/search`): config/tree/read/write/sync + 검색 응답 키 일치.
- **Filesystem** (`/api/fs/*`, `/api/projects*`): 메서드·필드·응답 일치.
- **System** (`/api/session/info`, `/api/workspace/context`, `/api/system/quota`, `/api/mcp/servers`, `/api/system/skills*`, `/api/system/log-level*`, `/api/settings*`): zod 스키마와 전부 일치.
- **기존 WS 이벤트**: `ModeChanged`, `ToolExecutionStarted/Finished`, `FileOpened/Modified` — 발행자 존재 + 페이로드 키 일치.

## 근본 원인 (Root cause) — 발견된 갭

프론트엔드 `useEventWebSocket.ts`가 소비하는 8개 이벤트 중 **3개가 백엔드에서 영구 무음** 상태였다:

| 이벤트 | 프론트 소비처 | 백엔드 상태 |
|---|---|---|
| `FailureDetected` | AgentPage 오류 로그/상태, ChatPage 활동 레일 `recordError` | events.py는 구독하지만 **발행자 없음** → 절대 수신 불가 |
| `CognitiveAdaptation` | AgentPage "🧠 적응" 로그 | events.py 구독 목록에 **조차 없음** + 발행자 없음 |
| `PlanningModeStarted` | AgentPage "📋 계획 모드 시작" 로그/타임라인, ChatPage `recordPlan` | events.py 구독 목록에 **조차 없음** + 발행자 없음 |

`events.py`가 구독하는 나머지(QualityCheck*, FailureRecovered, AgentTurn*, AntiPatternsDetected)는
plain-name 발행자가 없어 죽은 구독이지만, 프론트엔드가 소비하지 않으므로 무해(그대로 유지).
또한 `GET /api/system/access-mode`가 `ok` 키를 반환하지 않아 POST(및 zod 스키마)와 형태가 어긋남(파싱은 통과).

## 구현 및 범위 (Implementation and scope)

### 1) 이벤트 발행자 추가 (백엔드 → 프론트 계약 충족)

- `mode_manager._publish_planning_started(reason)`: `switch_to_plan()` 성공 시 `global_event_bus.publish("PlanningModeStarted", goal=reason or "")`.
  (기존 `_publish_to_eventbus`와 동일한 지연 import + try/except 패턴 — 실패해도 모드 전환 영향 없음.)
- `cognitive_loop._publish_cognitive_adaptation(reason, adaptation)`: `adapt_strategy()`의 두 적응 경로
  (External Brain 자동 위임 / 전략 변경 제안)에서 발행.
- `tool_executor._broadcast_failure_event(name, result)`: `_post_execute()`에서 `result_indicates_failure(result)`일 때
  `publish("FailureDetected", tool=name, error=result[:400], message="'name' 도구 실행 실패")`.

### 2) WS 구독 목록 보강 (`events.py`)

- `events_to_track` 지역 변수를 모듈 상수 **`TRACKED_EVENTS`**로 승격 (계약 테스트가 참조 가능).
- `CognitiveAdaptation`, `PlanningModeStarted` 추가. (이벤트 발행은 선택적 — 구독 대상이 없어도 기존처럼 무해.)

### 3) access-mode 응답 통일

- `GET /api/system/access-mode` → `{"ok": True, "mode": ..., "label": ...}` (POST와 동일 형태).

## 계약/마이그레이션 결정 (Contract decision)

- 프론트엔드 zod 스키마는 수정하지 않음 — 백엔드가 프론트 계약에 맞춤 (기존 스키마가 소비하는 필드만 발행).
- `FailureDetected`는 실패한 도구 호출 1회당 1건 발행 (consecutive-error 집계와 무관하게 단건 이벤트로 브로드캐스트).
- 기존 이벤트(`ModeChanged` 등)와 keepalive 동작은 무변경.

## 회귀 시나리오 (Regression scenarios)

- `switch_to_plan` → `PlanningModeStarted{goal}` 수신 (reason 미지정 시 `goal=""`)
- 반복 실패(≥2회) 시 `CognitiveAdaptation{reason, adaptation}` 수신, 정상 완료 시 미발행
- 실패한 도구 결과(`Error:`/`❌ [`/`[exit_code=N]`) 시 `FailureDetected{tool, error, message}` 수신, 성공 시 미발행
- `/v1/ws/events` 구독 목록이 프론트 소비 이벤트 8종을 모두 포함
- `GET /api/system/access-mode` → `ok: true` 포함

## Before/After 결과

| 항목 | Before | After |
|---|---|---|
| WS 이벤트 발행 | `CognitiveAdaptation`/`PlanningModeStarted`/`FailureDetected` 3종 무음 | 발행자 추가 + 구독 보강 |
| `events.py` 구독 목록 | 함수 지역 변수 (테스트 불가) | 모듈 상수 `TRACKED_EVENTS` + 계약 테스트로 고정 |
| `GET /api/system/access-mode` | `{mode, label}` | `{ok, mode, label}` (POST와 통일) |
| 계약 테스트 | 백엔드 0 / 프론트 0 | 백엔드 4건 + 프론트 2건 추가 |

## 수동/실측 증거 (Manual surface evidence)

- `uv run --no-sync python -m pytest tests/test_events.py tests/test_mode_manager.py tests/test_tool_executor.py tests/test_cognitive_loop_events.py -q` → **72 passed**
- 관련 스위트 전체: `test_cognitive_recovery.py test_system_api_memory_suite.py test_system_api_skills.py test_models_system_api.py test_mode_manager.py test_tool_executor.py test_events.py test_cognitive_loop_events.py` → **160 passed**
- `uv run --no-sync ruff check` (변경 9개 파일) → All checks passed
- `uv run --no-sync mypy` (변경 소스 4개) → Success: no issues found
- `cd dashboard && npx vitest run src/api/contractAlignment.test.ts` → **11 passed** (신규 2건 포함)
- `cd dashboard && npx tsc -b --pretty false` → 0 errors

## 전체 스위트 결과 + 선존 실패 (Full-suite result)

- 본 세션은 백엔드 이벤트 발행·WS 구독·응답 형태만 수정 — 프론트엔드 소스 로직 무변경.
- 선존·환경 의존 실패는 세션 11 기록과 동일 (wheel 빌드 산출물, 타 작업자 미커밋 `test_desktop_context_api.py`,
  unsloth 엔드포인트 미설정, a11y `.folder-sub-preview` 대비, 로컬 모델 캡처) — 본 작업과 무관.

## 정리/보존 (Cleanup and preserved user changes)

- 조사용 임시 파일 없음. 다른 작업자의 미커밋 변경은 건드리지 않음.
- `tests/test_cognitive_loop_events.py`는 신규 파일(untracked) — 커밋 시 포함 필요.
- 커밋/push/배포 수행 안 함.

## 잔여 위험 / 다음 에이전트 지시 (Residual risks / next-agent handoff)

1. **`FailureDetected` 발행 타이밍**: 현재 `_post_execute` 실패 결과 기준 1회/호출 발행. GatePipeline DENY/APPROVAL_REQUIRED
   경로는 `_post_execute`를 거치지 않으므로 발행되지 않음 — 대시보드가 "승인 대기"를 오류로 보여주지 않도록 의도된 동작이나,
   필요 시 `_register_approval_request` 경로에도 이벤트 추가 검토.
2. **죽은 구독 정리**: `QualityCheckStarted/Failed/Passed`, `FailureRecovered`, `AgentTurnStarted/Ended`,
   `AntiPatternsDetected`는 현재 plain-name 발행자가 없음. HookEventBus 브릿지가 `Hook:<kind>`로 발행하므로,
   향후 hook 종류를 plain-name으로 포워딩하고 싶으면 `hook_event_bus.EVENT_KIND_MAP`과 대조해 브릿지에서
   변환 매핑 추가 검토 (현재는 무해).
3. **계약 테스트 유지**: 새 WS 이벤트를 추가할 때는 `tests/test_events.py::FRONTEND_WS_EVENTS`와
   `dashboard/src/api/contractAlignment.test.ts::FRONTEND_WS_EVENT_NAMES` **양쪽**을 함께 갱신할 것 (쌍으로 고정됨).
4. **커밋 시점**: 본 세션 10개 파일(신규 2개 포함) + 세션 11 파일을 함께 커밋하되, 같은 작업 트리의 다른
   작업자 변경을 `git add -A`로 묶지 말 것.

## 재검증 명령

```bash
uv run --no-sync python -m pytest tests/test_events.py tests/test_mode_manager.py tests/test_tool_executor.py tests/test_cognitive_loop_events.py -q
uv run --no-sync ruff check src/antigravity_k/api/routes/events.py src/antigravity_k/api/routes/system_api.py src/antigravity_k/engine/mode_manager.py src/antigravity_k/engine/cognitive_loop.py src/antigravity_k/engine/tool_executor.py tests/test_events.py tests/test_mode_manager.py tests/test_tool_executor.py tests/test_cognitive_loop_events.py
uv run --no-sync mypy src/antigravity_k/api/routes/events.py src/antigravity_k/engine/mode_manager.py src/antigravity_k/engine/cognitive_loop.py src/antigravity_k/engine/tool_executor.py
cd dashboard && npx vitest run src/api/contractAlignment.test.ts
cd dashboard && npx tsc -b --pretty false
```
