---
title: 세션 13 — GatePipeline 승인 대기(APPROVAL REQUIRED) 경로에 ApprovalRequired WS 이벤트 발행 추가 (진행 기록)
tags: [contract-alignment, websocket, approval, event-bus, tool-executor, session-record]
date: 2026-09-04
branch: codex/m1-task-events
base_sha: 09ac373cd0fabf6460957b66947cac82bd3b2a52
status: completed_uncommitted
---

# 세션 13 진행 기록 — ApprovalRequired WS 이벤트 발행

> 세션 12(FE↔BE 정합성 감사)의 후속 과제: "GatePipeline 승인 대기(APPROVAL REQUIRED) 경로에도
> 대시보드용 이벤트가 발행되도록 tool_executor를 확장해줘".
> 다른 에이전트는 [세션 12 기록](session-12-fe-be-contract-audit.md)과 이 기록을 함께 읽고 이어서 작업한다.

## Issue

- 세션 12에서 `FailureDetected` 발행을 `_post_execute` 실패 결과 기준으로 추가했지만,
  **GatePipeline `is_paused`(승인 필요)와 Permission `PROMPT`(승인 필요) 경로는 `_post_execute`를 거치지 않아**
  대시보드가 승인 대기 상태를 실시간으로 알 수 없었다 (ApprovalQueue는 폴링만).
- 승인 대기는 실패가 아니므로 `FailureDetected`로 오발행하지 않고 **전용 `ApprovalRequired` 이벤트**로 발행.

## Status

- ✅ `ApprovalRequired{tool, request_id, reason}` 발행 (GatePipeline pause + Permission PROMPT 두 경로 모두)
- ✅ `/v1/ws/events` 구독 목록(`TRACKED_EVENTS`)에 추가
- ✅ 프론트엔드 소비: `useEventWebSocket` 스키마/핸들러, AgentPage 승인 대기 로그+타임라인(`approval` 타입), 스토어 타입 확장
- ✅ 계약 테스트 양쪽 갱신 (백엔드 `FRONTEND_WS_EVENTS`, 프론트 `FRONTEND_WS_EVENT_NAMES`/스키마/페이로드) + 발행 검증 2건
- ⏳ 미커밋

## Owner / 변경 파일

| 파일 | 변경 |
|---|---|
| `src/antigravity_k/engine/tool_executor.py` | `_broadcast_approval_required()` 신설, `_register_approval_request()`의 일시정지 반환 2경로에서 호출 |
| `src/antigravity_k/api/routes/events.py` | `TRACKED_EVENTS`에 `"ApprovalRequired"` 추가 |
| `dashboard/src/hooks/useEventWebSocket.ts` | `ApprovalRequired` 스키마/타입/핸들러/디스패치 추가 |
| `dashboard/src/stores/agentMonitorStore.ts` | `ExecutionEvent.type` 유니온에 `'approval'` 추가 |
| `dashboard/src/pages/AgentPage.tsx` | `onApprovalRequired` 핸들러 (warn 로그 + 타임라인) |
| `tests/test_tool_executor.py` | 일시정지 시 발행 검증 + ALWAYS_ALLOW 시 미발행 검증 2건 |
| `tests/test_events.py` | `FRONTEND_WS_EVENTS`에 `ApprovalRequired` 추가 |
| `dashboard/src/api/contractAlignment.test.ts` | 이벤트 이름 목록/스키마/페이로드 예시에 `ApprovalRequired` 추가 |

## 구현 및 범위 (Implementation and scope)

- `tool_executor._register_approval_request()`는 두 호출부(GatePipeline `is_paused`, Permission `PROMPT`)가
  공유하는 승인 등록 지점 — 여기서 `(False, request_id)`(일시정지)를 반환하기 직전에
  `global_event_bus.publish("ApprovalRequired", tool=name, request_id=..., reason=description)` 발행.
  - 신규 요청 등록 시 → `request.request_id`
  - 동일 도구 PENDING 재사용 시 → `existing_id`
  - `ALWAYS_ALLOW`/일회성 승인 소비(즉시 실행) 경로와 등록 실패 폴백 경로는 발행하지 않음 (승인 대기 아님).
- `useEventWebSocket.ts`: `approvalRequiredDataSchema {tool?, request_id?, reason?}` + discriminatedUnion 케이스
  + `onApprovalRequired?` 핸들러 + 디스패치. 미등록 페이지에서는 무시(선택 핸들러)되므로 기존 동작 보존.
- `AgentPage.tsx`: `onApprovalRequired` → `🛑 승인 대기: <tool> — <reason>` warn 로그 + 타임라인 `approval` 항목.
- 타임라인 도트 렌더러는 `type.includes(...)` 기반이라 신규 `approval` 타입도 기본 색으로 안전하게 렌더됨.

## 계약/마이그레이션 결정 (Contract decision)

- 새 이벤트 이름 도입이므로 세션 12 규칙에 따라 **양쪽 계약 테스트를 쌍으로 갱신**:
  `tests/test_events.py::FRONTEND_WS_EVENTS` ↔ `dashboard/src/api/contractAlignment.test.ts::FRONTEND_WS_EVENT_NAMES`.
- `ApprovalQueue`(폴링)는 그대로 유지 — WS 이벤트는 실시간 알림 보조이며 상태 소스가 아님.

## 회귀 시나리오 (Regression scenarios)

- GatePipeline pause → `[APPROVAL REQUIRED]` 문자열 + `ApprovalRequired{tool, request_id, reason}` 발행
- Permission PROMPT pause → 동일하게 발행 (같은 `_register_approval_request` 경유)
- ALWAYS_ALLOW/일회성 승인 즉시 실행 → 미발행
- 기존 8개 WS 이벤트 + keepalive 동작 무변경

## Before/After 결과

| 항목 | Before | After |
|---|---|---|
| 승인 대기 실시간 알림 | 없음 (ApprovalQueue 폴링만) | `ApprovalRequired` WS 이벤트 → AgentPage 로그/타임라인 |
| 계약 테스트 | FE 9 / BE 8 이벤트 | FE 10 / BE 9 이벤트 (양쪽 동기화) |

## 검증 (Verification)

- `pytest tests/test_tool_executor.py tests/test_events.py` → **42 passed**
- 관련 스위트 전체 (tool_executor/events/workspace_websocket/approval_manager/mode_manager/cognitive_loop_events) → **115 passed**
- `ruff` 4개 파일 → All checks passed, `mypy` 2개 소스 → Success
- `vitest contractAlignment.test.ts + useEventWebSocket.test.tsx` → **15 passed**
- `tsc -b` → 0 errors

## 잔여 위험 / 다음 에이전트 지시 (Residual risks / next-agent handoff)

1. **ApprovalQueue 실시간 연동 (선택)**: 현재 승인 목록 UI는 폴링. `ApprovalRequired` 이벤트를 받아
   즉시 목록을 refresh하거나 알림 토스트를 띄우는 연동은 미구현 — 필요 시 `features/task-execution/ApprovalQueue.tsx`에서
   `useEventWebSocket` 훅 사용 검토.
2. **계약 테스트 유지**: 신규 WS 이벤트 추가 시 백엔드 `FRONTEND_WS_EVENTS`와 프론트 `FRONTEND_WS_EVENT_NAMES`를
   반드시 함께 갱신할 것 (세션 12 §잔여 위험 3 참조).
3. **커밋 시점**: 세션 11·12 파일들과 함께 커밋하되, 다른 작업자 변경을 `git add -A`로 묶지 말 것.

## 재검증 명령

```bash
uv run --no-sync python -m pytest tests/test_tool_executor.py tests/test_events.py -q
uv run --no-sync ruff check src/antigravity_k/engine/tool_executor.py src/antigravity_k/api/routes/events.py tests/test_tool_executor.py tests/test_events.py
uv run --no-sync mypy src/antigravity_k/engine/tool_executor.py src/antigravity_k/api/routes/events.py
cd dashboard && npx vitest run src/api/contractAlignment.test.ts src/hooks/__tests__/useEventWebSocket.test.tsx
cd dashboard && npx tsc -b --pretty false
```
