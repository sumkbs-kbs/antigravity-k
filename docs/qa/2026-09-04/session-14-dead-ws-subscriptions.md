---
title: 세션 14 — TRACKED_EVENTS 죽은 구독 정리 + HookEventBus 브릿지로 AgentTurn* 실발행 연결 (진행 기록)
tags: [contract-alignment, websocket, event-bus, hook-bus, kanban, session-record]
date: 2026-09-04
branch: codex/m1-task-events
base_sha: 09ac373cd0fabf6460957b66947cac82bd3b2a52
status: completed_uncommitted
---

# 세션 14 진행 기록 — 죽은 WS 구독 정리 + AgentTurn 브릿지 연결

> 세션 12·13의 후속 과제: "events.py TRACKED_EVENTS 중 발행자가 없는 죽은 구독
> (QualityCheck*, AgentTurn*, AntiPatterns 등)을 정리하거나 HookEventBus 브릿지로 실제 발행되게 연결해줘".
> 다른 에이전트는 [세션 12](session-12-fe-be-contract-audit.md)·[세션 13](session-13-approval-required-ws-event.md)
> 기록과 이 기록을 함께 읽고 이어서 작업한다.

## Issue

- `/v1/ws/events`의 `TRACKED_EVENTS` 중 상당수가 **plain-name 발행자가 없어 영구 무음**이었다.
  프론트는 물론 kanban_api 같은 EventBus 직접 구독자에게도 전달되지 않는 죽은 구독.
- 대상: `QualityCheckStarted`, `QualityCheckFailed`, `QualityCheckPassed`, `FailureRecovered`,
  `AgentTurnStarted`, `AgentTurnEnded`, `AntiPatternsDetected`.

## 근본 원인 (Root cause) — 발행자 존재 여부 전수 조사

| 이벤트 | plain-name 발행자 | hook 발신 | 소비자 | 결론 |
|---|---|---|---|---|
| `QualityCheckStarted` | 없음 | 없음 | 없음 | **제거** (죽은 구독) |
| `QualityCheckFailed` | 없음 | 없음 | 없음 | **제거** |
| `QualityCheckPassed` | 없음 | 없음 | 없음 | **제거** |
| `FailureRecovered` | 없음 | 없음 | 없음 | **제거** |
| `AntiPatternsDetected` | 없음 | 없음 | 없음 | **제거** |
| `AgentTurnStarted` | 없음 | ✅ `autonomous_learner`(`kind="agent-turn-start"`) | ✅ `kanban_api` 구독자 | **브릿지로 연결** |
| `AgentTurnEnded` | 없음 | ✅ `autonomous_learner`(`kind="agent-turn-end"`) | ✅ `kanban_api` 구독자 | **브릿지로 연결** |

- 조사 방법: `publish("QualityCheck...`/`FailureRecovered`/`AntiPatternsDetected` 전수 검색 → src 전역 0건.
  `hook_event_bus.EVENT_KIND_MAP`의 "quality-pass"/"failure-recovered" 등 kind는 plain 이벤트가
  `dual_publish`로 hook 파일에 기록될 때 **파생**되는 값일 뿐, 그 plain 이벤트를 발행하는 코드가 없어 실제로 발생하지 않음.
- `AgentTurn*`은 `autonomous_learner._run_vibe_coding_pipeline()`이 hook 버스에 직접 emit하지만,
  브릿지가 `Hook:agent-turn-start` 형태로만 발행해 kanban의 plain-name 구독이 영구 무음이었다.

## Status

- ✅ 죽은 구독 5종 제거 (QualityCheck*, FailureRecovered, AntiPatternsDetected)
- ✅ `HOOK_KIND_TO_EVENT_NAME` 브릿지: `agent-turn-start/end` → `AgentTurnStarted/Ended` plain 발행 (kanban 연동)
- ✅ `autonomous_learner` 턴 이벤트 페이로드에 `role`/`task_type` 추가 (kanban이 의미 있는 태스크 표시)
- ✅ 죽은 구독 재발 방지 계약 테스트 + 브릿지 단위 테스트 추가 — 전체 통과
- ⏳ 미커밋

## Owner / 변경 파일

| 파일 | 변경 |
|---|---|
| `src/antigravity_k/engine/event_bus.py` | `HOOK_KIND_TO_EVENT_NAME` 매핑 신설, `on_hook_event`에서 매핑된 kind를 plain 이름으로도 발행 |
| `src/antigravity_k/api/routes/events.py` | `TRACKED_EVENTS`에서 죽은 구독 5종 제거, 발행자 주석 문서화 (11개 유지) |
| `src/antigravity_k/engine/autonomous_learner.py` | `agent-turn-start/end` 페이로드에 `role`/`task_type` 추가 |
| `tests/test_event_bus.py` | 브릿지 테스트 2건 (plain 발행 / 직접 발행 kind 이중 발행 금지) |
| `tests/test_events.py` | `test_tracked_events_have_no_dead_subscriptions` — 발행자 문서화와 대조 |

## 구현 및 범위 (Implementation and scope)

### 1) 브릿지 확장 (`event_bus.py`)

- `HOOK_KIND_TO_EVENT_NAME: dict[str, str] = {"agent-turn-start": "AgentTurnStarted", "agent-turn-end": "AgentTurnEnded"}`.
- `on_hook_event`에서 기존 `Hook:{kind}` 발행에 더해 매핑된 plain 이름도 `original_publish`로 발행.
- **명시적 allowlist인 이유**: `tool-exec-start`/`tool-exec-finish`/`failure-detected` 등은 직접 발행자
  (tool_loop/tool_executor)가 있어 브릿지까지 발행하면 **이중 발행**이 된다 — 이 목록은 반드시
  "직접 발행자가 없는" 이벤트만 담아야 하며, 추가 시 브릿지 테스트·계약 테스트를 함께 갱신.

### 2) 죽은 구독 제거 (`events.py`)

- `TRACKED_EVENTS` 16개 → **11개**: ToolExecutionStarted/Finished, FailureDetected, AgentTurnStarted/Ended,
  FileOpened/Modified, ModeChanged, CognitiveAdaptation, PlanningModeStarted, ApprovalRequired.
- 상단에 발행자 주석을 문서화해 재발 방지 (계약 테스트가 발행자 문서와 대조).

### 3) 발신자 페이로드 보강 (`autonomous_learner.py`)

- `agent-turn-start/end` payload에 `role="AutoLearner"`, `task_type="Vibe Coding Pipeline"` 추가 —
  kanban `_on_agent_turn_started/_on_agent_turn_ended`가 이 kwargs를 사용해
  `[AutoLearner] Vibe Coding Pipeline` 태스크를 생성/완료 처리.

## 계약/마이그레이션 결정 (Contract decision)

- 프론트엔드가 소비하는 10개 이벤트는 **무변경** (제거 대상은 프론트가 소비하지 않던 이벤트).
- `AgentTurn*`은 프론트 스키마에 없어 WS로 포워딩돼도 조용히 무시됨 — kanban(EventBus 직접 구독)이 실소비자.
- `Hook:{kind}` 발행은 유지 (backward compat — 기존 구독자/파일 로그 영향 없음).

## 회귀 시나리오 (Regression scenarios)

- `autonomous_learner` 턴 시작/종료 → hook emit → 브릿지 → `AgentTurnStarted/Ended` plain 발행 → kanban 태스크 생성/완료
- `tool_loop` 직접 발행 `ToolExecutionStarted` → hook 파일 기록 → watcher 분류 → 브릿지가 plain 재발행 **하지 않음** (이중 발행 방지)
- 기존 10개 프론트 소비 이벤트 + keepalive 동작 무변경

## Before/After 결과

| 항목 | Before | After |
|---|---|---|
| `TRACKED_EVENTS` | 16개 (죽은 구독 5~7개 포함) | **11개, 전부 실발행자 보유** |
| kanban AgentTurn 태스크 | 영구 무음 (Hook: 접두사만 발행) | `AgentTurnStarted/Ended` plain 발행으로 태스크 생성/완료 |
| 죽은 구독 재발 방지 | 없음 | 계약 테스트 `test_tracked_events_have_no_dead_subscriptions` |

## 검증 (Verification)

- `pytest tests/test_event_bus.py tests/test_events.py tests/test_autonomous_learner.py` → **53 passed**
- 관련 스위트 전체 (event_bus/events/tool_executor/mode_manager/cognitive_loop_events/workspace_websocket/autonomous_learner) → **147 passed**
- `ruff` 5개 파일 → All checks passed, `mypy` 3개 소스 → Success
- `vitest contractAlignment.test.ts` → **11 passed** (프론트 변경 없음 — 계약 유지 확인)

## 잔여 위험 / 다음 에이전트 지시 (Residual risks / next-agent handoff)

1. **QualityCheck*/FailureRecovered/AntiPatternsDetected 재도입 시**: 실제 발행자(예: quality_gate 파이프라인)가
   생기면 그때 `TRACKED_EVENTS` + `WS_EVENT_PUBLISHERS`(또는 프론트 목록)에 함께 추가할 것 —
   발행자 없는 상태로 목록만 늘리지 말 것.
2. **브릿지 allowlist 유지**: `HOOK_KIND_TO_EVENT_NAME`에 직접 발행자가 있는 kind를 추가하면 이중 발행.
   추가 전 반드시 `publish("...")` 직접 발행자 존재 여부 확인.
3. **kanban 태스크 시맨틱스**: `autonomous_learner`는 단일 턴(파이프라인 전체)을 시작/종료로 표시하므로
   kanban 태스크는 1건 생성/완료됨. 개별 gap 단위 태스크가 필요하면 `pretool` 발신과 함께
   `task_type`을 gap.topic으로 세분화하는 방안 검토.
4. **커밋 시점**: 세션 11~13 파일들과 함께 커밋하되, 다른 작업자 변경을 `git add -A`로 묶지 말 것.

## 재검증 명령

```bash
uv run --no-sync python -m pytest tests/test_event_bus.py tests/test_events.py tests/test_autonomous_learner.py -q
uv run --no-sync ruff check src/antigravity_k/engine/event_bus.py src/antigravity_k/engine/autonomous_learner.py src/antigravity_k/api/routes/events.py tests/test_event_bus.py tests/test_events.py
uv run --no-sync mypy src/antigravity_k/engine/event_bus.py src/antigravity_k/engine/autonomous_learner.py src/antigravity_k/api/routes/events.py
cd dashboard && npx vitest run src/api/contractAlignment.test.ts
```
