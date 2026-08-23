# 04 Development Roadmap

기준일: 2026-08-17

## 우선순위 작업표

| ID | 작업 | 목적 | 크기 | 위험 | 선행조건 | 완료 기준 |
|---|---|---|---|---|---|---|
| P0-01 | canonical runtime contract | 실행 경로 단일화 | XL | 매우 높음 | TaskStateStore | API/CLI/TaskRunner가 동일 TaskResult를 반환 |
| P0-02 | permission boundary audit | side effect 우회 제거 | L | 높음 | tool inventory | shell/file/git/browser 경로 모두 audit event 보유 |
| P0-03 | DNS-aware SSRF guard | 웹 본문 fetch 보호 | M | 높음 | URL policy | redirect와 resolved address가 public 범위 |
| P1-01 | search golden set | 검색 품질 기준선 | L | 보통 | fixture schema | P@K/Recall/MRR/nDCG 리포트 생성 |
| P1-02 | memory ownership | 중복/삭제/개인정보 해결 | L | 높음 | scope schema | scope isolation/delete/restart 테스트 통과 |
| P1-03 | local model calibration | qwen escalation 안정화 | M | 보통 | TaskOutcome | benchmark artifact의 mean/min/excellent threshold로 자동 routing 후보를 제한 |
| P1-04 | failure/alert operations | 운영 장애 대응 | M | 높음 | correlation id | alert, backup, rollback runbook과 smoke 존재 |
| P2-01 | task log UI | 진행/승인/재개 UX | L | 보통 | runtime events | 실제 browser E2E에서 상태 변화 확인 |
| P2-02 | plugin trust lifecycle | 확장 기능 안전성 | L | 높음 | capability schema | install/enable/disable/audit 정책 검증 |

## Phase별 산출물

### Phase 0: 기준선

실행 명령, dependency lock, server smoke, 현재 상태 문서를 고정한다. `pytest`, API smoke, package build를 모두 재현할 수 있어야 한다.

### Phase 1: Agent Core

TaskRequest/Plan/Step/Result와 durable transition을 도입한다. crash/resume/cancel/approval/idempotency 시나리오를 실제 SQLite로 검증한다.

### Phase 2: Tool System

모든 도구를 capability/risk/cost typed spec으로 등록하고 permission, timeout, retry, audit를 한 경계에 둔다. prompt injection과 도구 결과는 서로 다른 신뢰 영역으로 유지한다.

### Phase 3: Memory/Context

turn/session/task/project/user scope를 분리하고 TTL, 중요도, 삭제, 충돌 해결을 추가한다. context compression은 citation/provenance와 최종 모델 입력 예산을 보존하고, background/direct checkpoint resume는 최신 task-local snapshot과 부분 출력을 재구성한다. direct task ID 조회·재개 CLI/API는 완료됐고 dashboard 통합은 Phase 6 UX 범위다.

### Phase 4: Model Orchestration

qwen3.6 local-first, confidence evaluator, CoV critic, 상위 fallback을 quality/cost/latency threshold로 조정한다. 7B/14B/30B/70B 역할 정책은 실제 모델 capability와 함께 측정한다.

### Phase 5: Search/RAG

검색 source adapter, canonical URL, hybrid retrieval, authority/freshness, cross-validation, citation validator, robots/SSRF를 완성한다.

### Phase 6: Evaluation

coding/research/document/long-horizon/search golden set과 회귀 threshold를 CI에 연결한다. live provider 결과는 비용·법적·네트워크 조건을 별도 smoke job으로 분리한다.

### Phase 7: Productization

task status, approval, memory, model policy, plugin 관리 UI를 canonical API 위에 구현한다. Playwright browser E2E와 접근성 검사를 hard gate로 유지한다.

### Phase 8: Experimental

debate, reflexion, tree search, self-improvement, tool learning은 baseline 대비 quality gain과 cost delta가 측정될 때만 활성화한다.
