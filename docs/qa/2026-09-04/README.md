---
title: QA 세션 기록 — 2026-09-04
tags: [qa, session-index, relay]
date: 2026-09-04
branch: codex/m1-task-events
---

# QA 세션 기록 (2026-09-04)

## 세션 15 — QualityCheck/AgentTurn/AntiPatterns 프론트 소비 (AgentPage 타임라인 + Kanban 보드)

- **기록**: [session-15-kanban-quality-events.md](session-15-kanban-quality-events.md)
- **상태**: 완결 (미커밋)
- **요약**: 세션 14 후속 — 제거됐던 QualityCheck*/AntiPatternsDetected를 **실제 발행자와 함께 재도입**
  (tool_loop QualityGate 최종 등급 → QualityCheckPassed/Failed, cognitive_loop 반복 실패 →
  AntiPatternsDetected). `TRACKED_EVENTS` 14개로 확장. React AgentPage 타임라인(useEventWebSocket
  9→14종, 로그·타임라인·상태 표시)과 Kanban 보드(kanban_api 카드 주석 + vanilla agent.js 배지)에서
  표시. 양쪽 계약 테스트 14종 동기화.

## 세션 14 — 죽은 WS 구독 정리 + AgentTurn* 브릿지 연결

- **기록**: [session-14-dead-ws-subscriptions.md](session-14-dead-ws-subscriptions.md)
- **상태**: 완결 (미커밋)
- **요약**: `TRACKED_EVENTS`의 발행자 없는 죽은 구독 5종(QualityCheck*, FailureRecovered,
  AntiPatternsDetected) 제거. `AgentTurnStarted/Ended`는 실발신자(autonomous_learner hook)와
  실소비자(kanban_api)가 있어 `HOOK_KIND_TO_EVENT_NAME` 브릿지로 plain 발행 연결 + 페이로드 보강.
  죽은 구독 재발 방지 계약 테스트 추가 (16→11개, 전부 실발행자 보유).

## 세션 13 — ApprovalRequired WS 이벤트 (승인 대기 실시간 알림)

- **기록**: [session-13-approval-required-ws-event.md](session-13-approval-required-ws-event.md)
- **상태**: 완결 (미커밋)
- **요약**: 세션 12 후속 — GatePipeline `is_paused`/Permission `PROMPT` 승인 대기 경로에서
  `tool_executor`가 `ApprovalRequired{tool, request_id, reason}`를 발행하도록 확장.
  `TRACKED_EVENTS` 추가, 프론트 `useEventWebSocket`/AgentPage(승인 대기 로그·타임라인) 소비,
  양쪽 계약 테스트 동기화(백엔드 2건 + 프론트 목록/스키마).

## 세션 12 — 프론트엔드-백엔드 정합성 전수 감사 + WS 이벤트 계약 갭 수정

- **기록**: [session-12-fe-be-contract-audit.md](session-12-fe-be-contract-audit.md)
- **상태**: 완결 (미커밋)
- **요약**: FE↔BE 엔드포인트·스키마·WS 이벤트 전수 감사. 대부분 일치하나, 프론트 `useEventWebSocket`이
  소비하는 3개 이벤트(`PlanningModeStarted`/`CognitiveAdaptation`/`FailureDetected`)가 백엔드에서 영구 무음이던 갭을
  발행자 추가(mode_manager/cognitive_loop/tool_executor) + `/v1/ws/events` 구독 보강으로 해결.
  `GET /api/system/access-mode` 응답에 `ok` 추가로 POST와 형태 통일. 양쪽 계약 테스트(백엔드 4건, 프론트 2건) 추가.

## 세션 11 — auth-bootstrap E2E 자급화 + /v1/ws/events shutdown 지연 수정

- **기록**: [session-11-auth-bootstrap-e2e.md](session-11-auth-bootstrap-e2e.md)
- **상태**: 완결 (미커밋)
- **요약**: `docs/FRONTEND_REDESIGN_RELAY_2026-09-03.md` §6.1의 마지막 남은 과제(auth-bootstrap no-auth
  2건, 환경 의존)를 자체 격리 백엔드 스폰으로 해결 → 4/4 통과. 부수 발견으로 `/v1/ws/events` 핸들러의
  disconnect 미감지로 인한 graceful shutdown ~30초 지연 버그를 수정 (SIGTERM→exit 194ms).

## 읽는 순서

1. [릴레이 문서](../FRONTEND_REDESIGN_RELAY_2026-09-03.md) — 이 브랜치의 살아있는 인수인계 계획 (15차 완결 상태)
2. [세션 15 기록](session-15-kanban-quality-events.md) — QualityCheck/AgentTurn/AntiPatterns 프론트 소비 (AgentPage + Kanban 보드)
3. [세션 14 기록](session-14-dead-ws-subscriptions.md) — 죽은 WS 구독 정리 + AgentTurn* 브릿지 연결
4. [세션 13 기록](session-13-approval-required-ws-event.md) — ApprovalRequired WS 이벤트 (승인 대기 실시간 알림)
5. [세션 12 기록](session-12-fe-be-contract-audit.md) — FE↔BE 정합성 감사·갭 수정
6. [세션 11 기록](session-11-auth-bootstrap-e2e.md) — auth-bootstrap E2E 자급화 + WS shutdown 지연 수정
