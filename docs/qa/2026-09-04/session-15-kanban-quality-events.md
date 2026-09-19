---
title: 세션 15 — QualityCheck/AgentTurn/AntiPatterns 이벤트의 프론트 소비 추가 (AgentPage 타임라인 + Kanban 보드) (진행 기록)
tags: [contract-alignment, websocket, event-bus, quality-gate, kanban, session-record]
date: 2026-09-04
branch: codex/m1-task-events
base_sha: 09ac373cd0fabf6460957b66947cac82bd3b2a52
status: completed_uncommitted
---

# 세션 15 진행 기록 — QualityCheck/AgentTurn/AntiPatterns 이벤트 실소비 연결

> 세션 14 후속 과제: "QualityCheck/AgentTurn/AntiPatterns 이벤트를 대시보드 AgentPage 타임라인과
> Kanban 보드에서 실제로 표시되도록 프론트엔드 소비를 추가해줘".
> 다른 에이전트는 [세션 12](session-12-fe-be-contract-audit.md)~(14) 기록과 이 기록을 함께 읽고 이어서 작업한다.

## Issue

- 세션 14에서 발행자 없는 죽은 구독(QualityCheck*, AntiPatternsDetected)은 **제거**하고,
  `AgentTurnStarted/Ended`만 브릿지로 연결했다. 그 결과 대시보드(React AgentPage 타임라인)는
  이 5종 이벤트를 전혀 소비하지 않았고, Kanban 보드도 AgentTurn 태스크 생성/완료만 반영했다.
- 즉 "실제 발행자"가 아예 없던 QualityCheck*/AntiPatternsDetected는 재도입하려면
  **실제 발행 지점**부터 만들어야 했다 (죽은 구독 재발 방지 계약이 발행자 문서화와 대조하므로).

## 근본 원인 (Root cause)

| 이벤트 | 세션 14 이전 발행자 | 실제 발행 지점 (이번 세션) | 소비자 |
|---|---|---|---|
| `QualityCheckPassed` / `QualityCheckFailed` | 없음 (제거됨) | `tool_loop._post_loop_checks` — **QualityGate 최종 평가 결과** (`final_quality`, A/B 통과 / C/F 실패) | AgentPage 타임라인, kanban(실패만) |
| `AntiPatternsDetected` | 없음 (제거됨) | `cognitive_loop.adapt_strategy` — **반복 실패 감지 시** (외부 브레인 위임·전략 변경 두 경로) | AgentPage 타임라인, kanban |
| `AgentTurnStarted/Ended` | 세션 14 브릿지로 plain 발행 (kanban만 소비) | (유지) | **AgentPage 타임라인 추가**, kanban (기존) |

- 조사 결과: `grep -rn "QualityCheckPassed\|AntiPatterns" src --include="*.py"` → 발행자 0건.
  `tool_loop.py`는 `_post_loop_checks`에서 `QualityScore`(grade A/B/C/F)를 이미 계산하므로
  최종 평가 직후 발행이 가장 자연스러운 지점. `cognitive_loop.get_anti_patterns()`도
  `_step_history` 실패 스텝에서 항상 계산 가능.
- Kanban 보드 UI: React `dashboard/`에는 없고 **vanilla 보드 `dashboard-vanilla/src/pages/agent.js`**
  가 `/api/kanban/tasks`를 2초 폴링해 카드(제목/설명/라벨)를 렌더 — 설명/플래그를 주입하면
  다음 폴링 주기에 자동 표시된다.

## Status

- ✅ `tool_loop._publish_quality_event` — QualityGate 최종 등급을 QualityCheckPassed/Failed로 발행
- ✅ `cognitive_loop._publish_anti_patterns` — 반복 실패 감지 시 AntiPatternsDetected 발행 (patterns/tools 포함)
- ✅ `events.py TRACKED_EVENTS` 11→14개: QualityCheckPassed/Failed, AntiPatternsDetected 추가 (전부 실발행자 보유)
- ✅ `kanban_api.py` — QualityCheckFailed/AntiPatternsDetected 구독: 진행 중 카드에 설명 주석 + `quality_failed`/`quality_grade`/`anti_patterns` 플래그
- ✅ React `useEventWebSocket` 9→14종 이벤트 스키마/핸들러, `agentMonitorStore` 타임라인 타입 확장,
  `AgentMonitorPanel` 타임라인 색상 매핑, `AgentPage` 로그·타임라인 표시
- ✅ vanilla kanban 보드 `agent.js` — 품질 실패/안티패턴 배지 렌더
- ✅ 양쪽 계약 테스트 동기화 (백엔드 FRONTEND_WS_EVENTS 14종 / 프론트 FRONTEND_WS_EVENT_NAMES 14종)
- ⏳ 미커밋

## Owner / 변경 파일

| 파일 | 변경 |
|---|---|
| `src/antigravity_k/engine/tool_loop.py` | `_publish_quality_event` 신설, `_post_loop_checks` 최종 평가 직후 발행 |
| `src/antigravity_k/engine/cognitive_loop.py` | `_publish_anti_patterns` 신설, `adapt_strategy` 두 적응 경로에서 발행 |
| `src/antigravity_k/api/routes/events.py` | `TRACKED_EVENTS` 14개 + 발행자 주석 |
| `src/antigravity_k/api/routes/kanban_api.py` | QualityCheckFailed/AntiPatternsDetected 구독 + 카드 주석/플래그 |
| `dashboard/src/hooks/useEventWebSocket.ts` | AgentTurn*/QualityCheck*/AntiPatternsDetected 스키마·핸들러·dispatch |
| `dashboard/src/stores/agentMonitorStore.ts` | `ExecutionEvent.type`에 `agent_turn`/`quality`/`anti_pattern` 추가 |
| `dashboard/src/components/Agent/AgentMonitorPanel.tsx` | 타임라인 이벤트 색상 매핑 (신규 3종) |
| `dashboard/src/pages/AgentPage.tsx` | 신규 5개 핸들러 → 로그/타임라인/상태 표시 |
| `dashboard-vanilla/src/pages/agent.js` | 카드에 품질 실패/안티패턴 배지 (gitignored — 편집 툴 미노출, python으로 패치) |
| `tests/test_events.py` | FRONTEND_WS_EVENTS 14종 + WS_EVENT_PUBLISHERS 전체 문서화 |
| `tests/test_tool_loop.py` | `_publish_quality_event` 매핑 테스트 + 리비전 후 최종 등급 발행 테스트 2건 |
| `tests/test_cognitive_loop_events.py` | AntiPatternsDetected 발행 테스트 |
| `tests/test_kanban.py` | 품질 실패/안티패턴 카드 주석 테스트 3건 + 구독 등록 테스트 (reload) |
| `dashboard/src/api/contractAlignment.test.ts` | wsEventSchema 14종 + payload 예시 + 이름 목록 |
| `dashboard/src/hooks/__tests__/useEventWebSocket.test.tsx` | QualityCheckFailed/AntiPatternsDetected 라우팅 테스트 2건 |

## 구현 및 범위 (Implementation and scope)

### 1) 실제 발행자 (세션 14의 "재도입 시 실제 발행자부터" 지시 이행)

- `tool_loop.py`:
  ```python
  def _publish_quality_event(task_type: str, user_task: str, quality: QualityScore) -> None:
      passed = quality.grade in {QualityGrade.A, QualityGrade.B}
      global_event_bus.publish(
          "QualityCheckPassed" if passed else "QualityCheckFailed",
          task_type=task_type, user_task=user_task[:500],
          score=quality.score, grade=quality.grade.value,
          issues=list(quality.issues or []), feedback=quality.feedback,
      )
  ```
  `_post_loop_checks`에서 `if final_quality is not None:` 직전 발행 — 리비전/분해 복구까지 끝난
  **최종 등급**만 발행 (C→B로 개선되면 Passed 1건, 미개선 C면 Failed 1건).
- `cognitive_loop.py`: `_publish_anti_patterns(reason, tools)` → `AntiPatternsDetected{reason, tools, patterns}`.
  `adapt_strategy`의 외부 브레인 위임·전략 변경 두 경로 모두에서 발행 (CognitiveAdaptation과 나란히).

### 2) 이벤트 포워딩 (`events.py`)

- `TRACKED_EVENTS` 11→**14개** (QualityCheckPassed/Failed, AntiPatternsDetected). 상단 주석에 발행자 문서화.
- 세션 14의 죽은 구독 금지 규칙 유지: 프론트(FRONTEND_WS_EVENTS)가 14종 전부 소비하므로
  `WS_EVENT_PUBLISHERS`는 전체 발행자 문서화 사전으로 보강.

### 3) Kanban 보드 연동 (`kanban_api.py`)

- `_on_quality_check_failed`: 가장 최근 `in_progress` 카드에 `quality_failed=True`, `quality_grade`,
  설명에 `[품질 실패 {grade}] {feedback}` 주석.
- `_on_anti_patterns_detected`: `anti_patterns=True`, 설명에 `[안티패턴 감지] {patterns}` 주석.
- `_on_agent_turn_started/_ended`는 기존 유지. 주석은 다음 폴링(2초)에 vanilla 보드 카드에 표시.
- `global_event_bus.subscribe` 2건 추가.

### 4) React 프론트 소비 (AgentPage 타임라인)

- `useEventWebSocket.ts`: discriminatedUnion 9→14종. `QualityCheckData`는 score(숫자|문자)·grade·issues·feedback,
  `AntiPatternsData`는 reason·tools·patterns, `AgentTurnData`는 role·task_type.
- `AgentPage.tsx` 핸들러: 턴 시작/완료 로그·타임라인, 품질 통과(success)/실패(error·상태 error),
  안티패턴(warn·상태 error) — 타임라인 타입 `agent_turn`/`quality`/`anti_pattern`.
- `AgentMonitorPanel.tsx`: `TIMELINE_EVENT_COLORS`로 신규 3종 색상 지정 (agent_turn=파랑, quality=앰버,
  anti_pattern=빨강) — 기존 includes() 문자열 추론을 명시 매핑으로 교체.

### 5) vanilla Kanban 보드 (`dashboard-vanilla/src/pages/agent.js`)

- `renderCard`에 품질 실패(`🧪 품질 실패 {grade}`) / 안티패턴(`⚠️ 안티패턴`) 배지 추가.
- 주의: `dashboard-vanilla/`는 `.gitignore` 대상이라 편집 툴(str_replace/read)이 접근 불가 —
  `python3`로 정확 문자열 치환 적용, `node --check`로 구문 검증.

## 계약/마이그레이션 결정 (Contract decision)

- **이벤트 이름**: 세션 14에서 제거됐던 `QualityCheckPassed/Failed`, `AntiPatternsDetected`를
  세션 14가 문서화한 "재도입 조건"(실제 발행자 확보)을 충족한 뒤 같은 이름으로 재도입.
- **QualityCheckFailed만 kanban에 주석**: 통과는 카드 상태에 변화를 주지 않음 (진행 중 유지).
- **score 타입**: 프론트 스키마에서 `number | string` 허용 (JSON 직렬화 안전).
- **final_quality 의미론**: 리비전 개선 후에는 최종 등급만 발행 — 중간 실패는 별도 이벤트 없음.
  (원하면 리비전 단계마다 발행하는 방향으로 확장 가능 — 잔여 위험 참조)

## 회귀 시나리오 (Regression scenarios)

- `tool_loop` QualityGate C/F → `QualityCheckFailed` → WS → AgentPage 에러 로그·타임라인 + kanban 카드 주석
- `cognitive_loop` 반복 실패 2/3 → `AntiPatternsDetected` → WS → AgentPage 경고 + kanban 카드 주석
- `autonomous_learner` 턴 시작/종료 → `AgentTurnStarted/Ended` → AgentPage 타임라인 + kanban 태스크 생성/완료 (기존 동작 유지)
- 리비전으로 품질 개선(C→B) → `QualityCheckPassed` 1건만 발행 (Failed 없음)
- 세션 12~14 기존 이벤트(ModeChanged/FailureDetected/ApprovalRequired 등) 무변경

## Before/After 결과

| 항목 | Before | After |
|---|---|---|
| `TRACKED_EVENTS` | 11개 | **14개, 전부 실발행자 + 프론트 소비** |
| AgentPage 타임라인 이벤트 | 9종 | **14종** (턴/품질/안티패턴 로그·타임라인 표시) |
| kanban 카드 | AgentTurn 태스크만 | 품질 실패/안티패턴 주석·배지 추가 |
| 품질/안티패턴 실발행 | 없음 (죽은 구독 제거 상태) | tool_loop/cognitive_loop 실발행 |

## 검증 (Verification)

- `pytest tests/test_events.py tests/test_cognitive_loop_events.py tests/test_kanban.py tests/test_tool_loop.py`
  → **113 passed**
- 관련 스위트 전체 (event_bus/events/mode_manager/tool_executor/cognitive_loop_events/kanban/workspace_websocket)
  → **143 passed**, `tests/test_api_server.py` → **37 passed** (kanban HTTP/WS 무회귀)
- `ruff` 8개 파일 → All checks passed, `mypy` 4개 소스 → Success
- `vitest contractAlignment + useEventWebSocket` → **17 passed**, `agentMonitorStore` → **43 passed**
- `tsc -b` → **0 errors**
- `node --check dashboard-vanilla/src/pages/agent.js` → syntax OK

## 잔여 위험 / 다음 에이전트 지시 (Residual risks / next-agent handoff)

1. **`_post_loop_checks`는 generator**: `_publish_quality_event`는 generator가 소비될 때만 발행.
   `AgentTurnCompleted`와 동일 패턴이므로 실제 런타임과 동일하게 동작.
2. **QualityCheckPassed는 kanban 미구독**: 통과 이벤트로 카드 상태를 바꿀 필요가 없어 생략.
   원하면 `_on_quality_check_passed`로 카드에 등급 표시(예: `🧪 A`) 추가 가능.
3. **vanilla 보드 폴링 기반**: WS가 아니라 2초 폴링이라 이벤트→카드 반영이 최대 2초 지연.
   실시간성이 필요하면 `agent.js`를 `/v1/ws/events`(또는 `/ws/kanban`) 구독으로 전환 검토.
4. **`test_kanban.py`의 reload 테스트**: `importlib.reload`로 구독 등록을 검증. kanban_api가
   이미 import된 상태에서 reload해도 기존 콜백은 실버스에 남아 무해하며, sys.modules의
   새 모듈로 이후 테스트가 동작 (test_api_server는 이보다 먼저 실행되므로 영향 없음 확인).
5. **커밋 시점**: 세션 11~14 파일들과 함께 커밋하되, 다른 작업자 변경을 `git add -A`로 묶지 말 것.
6. **dashboard-vanilla는 gitignore 대상**: 변경이 커밋에 포함되지 않으므로, 필요 시
   `git add -f dashboard-vanilla/src/pages/agent.js` 또는 배포 빌드에 포함 여부를 별도 결정.

## 재검증 명령

```bash
uv run --no-sync python -m pytest tests/test_events.py tests/test_cognitive_loop_events.py tests/test_kanban.py tests/test_tool_loop.py -q
uv run --no-sync ruff check src/antigravity_k/engine/tool_loop.py src/antigravity_k/engine/cognitive_loop.py src/antigravity_k/api/routes/events.py src/antigravity_k/api/routes/kanban_api.py tests/test_tool_loop.py tests/test_cognitive_loop_events.py tests/test_kanban.py tests/test_events.py
uv run --no-sync mypy src/antigravity_k/engine/tool_loop.py src/antigravity_k/engine/cognitive_loop.py src/antigravity_k/api/routes/events.py src/antigravity_k/api/routes/kanban_api.py
cd dashboard && npx vitest run src/api/contractAlignment.test.ts src/hooks/__tests__/useEventWebSocket.test.tsx src/stores/__tests__/agentMonitorStore.test.ts
cd dashboard && npx tsc -b --pretty false
node --check dashboard-vanilla/src/pages/agent.js
```
