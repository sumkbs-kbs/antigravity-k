# 05 Master Checklist

기준일: 2026-08-17

상태: `[x]` 완료·검증, `[~]` 일부 구현/추가 검증, `[!]` 문제, `[?]` 자료 부족

## 실행/구조

- [x] Python/FastAPI 서버 import 및 `/health` smoke
- [x] CLI/API/dashboard entrypoint 목록화
- [x] qwen3.6:latest Ollama local-first 설정
- [x] README 설치 명령을 `uv sync` 기반으로 단일화하고 CLI smoke target으로 확인
- [x] canonical Agent Runtime facade connected to chat agent streaming, `/api/stream_agent`, background task submit/resume, slash `/goal`, slash natural-language execution, CLI `run`, MAX, and multiplexer adapters
- [x] shell, Git, PageScraper-backed web fetch, external-brain, system, filesystem, legacy publish/env/vault paths, and 41 HTTP egress call sites use permission/runtime boundaries

## Agent/Model

- [x] 계획·실행·검증·수정 루프 일부 구현
- [x] CoV revise/reverify
- [x] confidence evaluator와 cascade
- [x] TaskStateStore checkpoint/resume/idempotency
- [x] GoalRunner task plan is injected into every canonical background task and persisted at checkpoint step 0; bound ToolLoop runs persist tool steps and approval pauses through `resuming`, bound StateGraph persists MAX/pipeline transitions in a separate execution-event ledger, canonical direct stream/MAX runs create durable task IDs exposed by SSE and CLI, and browser/agent/parallel subagent streams reuse the parent task binding or create a durable standalone task.
- [x] TaskRunner terminal TaskOutcome
- [x] ToolLoop terminal TaskOutcome
- [x] canonical stream의 trajectory/context compression이 단일 oversized 목표도 모델별 최종 token budget 아래로 제한하고 목표의 head/tail 제약과 structured tool provenance를 보존
- [x] process restart/checkpoint resume 시 최신 bounded context snapshot을 작업별 SQLite execution ledger에서 격리 복원하고 transient global recall은 재영속하지 않는 장기 context reconstruction
- [x] canonical direct task가 실패·일시정지 시 부분 출력과 대화 snapshot을 저장하고 반환된 task ID를 CLI/API에서 상태·출력 조회 및 재개
- [x] direct task record는 초안·revision 알림을 제외한 최종 agent output만 저장하고, code review는 현재 턴에서 mutating tool을 실제로 사용한 경우에만 workspace diff를 노출한다. 실전 qwen3.6 코드 질문에서 task done, 최종 코드 블록 AST 통과, 무관 git diff 미노출을 확인했다.
- [x] 7B/14B/30B/70B capability matrix via `ModelProfile.effective_parameter_count_b`, `capability_tier`, `is_local`, and `is_20b_plus`, exposed through `/v1/models` and `agk models`
- [x] configured `ModelRoutingPolicy` applies a known 70B cap, a 20B local minimum, and stable local-first ordering across every ModelRouter strategy and direct selection
- [~] `local-model-stable-simple`·`local-model-frontier` artifact의 반복 stability(mean/min benchmark score, excellent rate, all-excellent run rate, run error count)를 우선 읽어 자동 routing 후보를 제한; 현재 Qwen은 4회 run/14개 결과 집계를 통과했고 Qwen 외 모델·더 넓은 task suite의 calibration은 남음

## Search/RAG

- [x] multi-engine adapter와 category TTL cache
- [x] URL canonicalization/tracking 제거
- [x] URL 중복 제거 및 도메인 다양성
- [x] authority score/source id/citation format
- [x] untrusted web content/tool markup 경계
- [x] literal private URL 및 unsafe redirect 차단
- [x] PageScraper resolves all DNS answers, rejects private addresses, pins the selected public IP at TCP connect, and rechecks redirects
- [~] robots.txt/legal policy and non-PageScraper connector inventory
- [x] 2-case deterministic P@K/Recall/MRR/nDCG golden set and claim-level citation evaluator
- [x] COV_VERIFY citation evidence reconstruction and uncited-claim validation in the canonical orchestrator path
- [x] 후보 수가 출력 한도를 채워도 낮은 relevance 또는 단일 provider면 Jina 후보를 보강하고, fallback self-hosted 결과가 낮은 relevance면 다음 provider를 계속 탐색
- [~] live provider search benchmark and human relevance labels: configured self-hosted authority-rescue plus Qwen source-hint 6-case run reached error_count 0, P@3 0.389/Recall@3 0.667/MRR 0.917/nDCG@3 0.741; provider availability and P95 remain below target
- [~] same-subject conflict detection: temporal and explicitly named metric values are gated with citation pair metadata; publication-time and semantic conflict resolution remain

## Tool/Security

- [x] ToolRegistry permission path
- [x] `ToolSpec -> ToolInvocation -> PermissionDecision` 공용 contract와 `PermissionGate.decide()`를 registry 및 주요 API helper에 연결
- [x] allow/deny/prompt audit
- [x] approval-required flow
- [x] approved tool execution re-checks the permission boundary
- [x] browser action and autonomous QA endpoints deny before side effects
- [x] memory provider scope clear for session/working/project/global/all with persisted session purge
- [x] authenticated `DELETE /api/memory` returns provider counts and audit event
- [x] durable MemoryService/VectorStore/LLMWiki/GBrain/search-cache purge providers
- [x] provider/durable memory export, secret redaction, retention API, and Vault raw-asset exclusion/redacted opt-in policy
- [x] `MemoryFact` authority contract and provider-order-independent identity conflict resolution: current user correction > durable global identity > unstructured recall
- [x] typed user-preference conflict/dedupe for response language/detail, explanation level, and task domain: current explicit request > durable explicit preference > inferred profile > unstructured recall
- [x] project decision/general fact를 typed key와 provenance로 project-local 저장하고 current user > durable project decision 순으로 충돌 해결 및 exact dedupe
- [x] 보편적 project 기술 키 별칭(`db`/`dbms`/`db_engine`, framework/package/deployment 계열)을 canonical key로 수렴하고 legacy store를 관측 시각 latest-wins로 마이그레이션
- [x] project-local operator alias schema와 CLI를 통해 팀 고유 key를 canonical key로 안전하게 통합하고 저장·migration·현재 턴 충돌·직접 조회에 일관 적용
- [~] 명시적 alias schema 없이 자유 텍스트 의미만으로 서로 다른 임의 key를 자동 병합하는 semantic dedupe
- [x] shell tool/API의 permission audit과 project cwd/timeout/output 경계
- [~] 모든 legacy/외부 connector 경로의 단일 permission audit; external-brain list/send are gated before adapter creation
- [x] Python `httpx`/`urllib` raw egress call-site inventory command and JSON artifact
- [x] sandbox CPU/memory/process/output quota 및 task 실패·취소 snapshot rollback
- [~] secret redaction end-to-end 증거

## Evaluation/Operations

- [x] unit/integration/E2E 테스트 구조
- [x] performance benchmark와 CI threshold
- [x] TaskThresholds 계약 및 CI quality contract
- [x] 장기 작업 benchmark case
- [~] 검색 live benchmark와 비용 측정: self-hosted availability/error_count 0, query rewrite, provider cooldown/empty-result failure contract, 1500ms fallback budget, healthy load P95 1805.8ms는 기록했지만 relevance와 cost attribution remains
- [x] P95/P99/concurrency/load benchmark contract; [~] healthy-provider load baseline: 3 repeats x 2 concurrency recorded error_count 0, P50 52.2ms, P95/P99 1805.8ms
- [x] stale-cache fallback is explicitly marked and disabled for realtime queries
- [~] alert, backup, disaster recovery 실제 rehearsal
- [x] basedpyright hard gate: 전체 `src` 진단 0 errors; 저장소 전체 Ruff 712 legacy/style findings는 별도 정리 과제

## UX/배포/문서

- [x] CLI, API, dashboard 존재
- [~] task log/approval/resume dashboard 통합; CLI/API 조회·재개는 완료
- [~] clean installation and package build on supported environments
- [x] current state/quality/architecture/roadmap documents
- [x] security/test/operation/readiness document baseline
- [~] 상용 출시 차단 위험 제거
