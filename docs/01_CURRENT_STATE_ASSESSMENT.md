# 01 Current State Assessment

기준일: 2026-08-17  
범위: `src/antigravity_k`, `tests`, `config.yaml`, FastAPI 서버, CLI, Dashboard, 웹 검색 도구

## A. 프로젝트 이해

Antigravity-K는 Apple Silicon에서 `qwen3.6:latest`를 우선 사용하는 로컬 중심 범용 에이전트다. 사용자의 요청을 모델 라우팅, 계획/검증 루프, 도구 실행, 메모리/RAG, 장기 작업 상태 저장으로 연결한다. 웹 검색은 SearXNG, Tavily, Jina, DuckDuckGo와 로컬 캐시를 조합한다.

핵심 성공 기준은 다음과 같다.

- 모델을 모를 때 검색·파일·코드·브라우저 도구로 근거를 확보한다.
- 복잡한 요청을 계획 → 실행 → 검증 → 수정 또는 복구로 처리한다.
- 위험한 side effect는 permission/approval 경계를 통과한다.
- 작업과 검색 결과가 재현 가능한 상태, 출처, 비용, latency로 관측된다.
- 로컬 모델을 기본으로 하되 품질 부족 시 검증된 fallback을 사용할 수 있다.

## B. 실행 및 구조

| 영역 | 현재 확인된 구현 | 상태 |
|---|---|---|
| 언어/서버 | Python 3.12+, FastAPI, Uvicorn | [x] 코드와 서버 smoke 확인 |
| 모델 | `ModelRegistry` → `ModelRouter` → `ModelManager` → provider adapter | [x] qwen3.6 local-first와 7B/14B/30B/70B capability metadata 확인 |
| Agent loop | `OrchestratorAgent`, state graph, `ToolLoopEngine`, CoV, QualityGate | [x] 단위/통합 테스트와 품질 재생성 경로 확인 |
| Tool | `ToolRegistry` → permission/guardrail → `ToolExecutor` | [x] side effect permission 경계 보강 |
| 장기 작업 | `BackgroundTaskRunner` + SQLite `TaskStateStore` | [x] resume/idempotency/outcome 계측 |
| 기억/RAG | Session, Vault, GBrain, VectorStore, `RAGIndexer` | [~] 4-tier/export/redaction/retention과 durable purge 통합, Vault 원문 asset 자동 변경 opt-in |
| 웹 검색 | SearXNG/Tavily/Jina/DDG/Lite/선택적 self-hosted + cache + URL quality contract + live benchmark | [~] self-hosted provider availability 확인, SearXNG/DuckDuckGo 변동성과 live relevance가 남음 |
| API/CLI/UI | OpenAI 호환 API, legacy routes, Typer CLI, dashboard | [~] chat/task/slash/CLI/MAX/multiplexer runtime 경로와 shell/Git/web/external-brain/system/filesystem permission 경계 연결, legal policy 코드화됨, 배포 attestation 입력 잔여 |
| 평가 | QualityGate, BenchmarkHarness, TaskOutcome, performance benchmark | [x] 계약 및 CI gate 연결 |

## C. 확인된 실행 결과 (2026-08-17 갱신)

- 최신 전체 회귀: `make test-quick` → **3,642 pass / 0 fail** (코어 6개 모듈 151건 포함)
- 서버 수동 QA: `/health 200`, `/openapi.json 200`, 비인증 보호 route `401`, 인증 `/api/fs/browse 200`, `/api/git/status 200`, E2E smoke `9 passed`
- qwen3.6:latest simple local benchmark: 2회 반복 4개 결과 모두 `excellent`, benchmark/quality `1.0`, 표준편차 `0.000`, all-excellent run rate `1.000`
- qwen3.6:latest frontier 5-case 2회 반복: 10개 결과 모두 `excellent`, 평균·최솟값 benchmark/quality/keyword `1.000`, 표준편차 `0.000`, all-excellent run rate `1.000`, 평균 latency `34.0초`
- lh-001(장기 워크플로, 난이도 5) 재측정: revision_off 평균 **0.727** (0.566·0.615·1.0, excellent 1/3) → revision_on 평균 **1.000** (3/3 excellent) — **delta +0.273**, 기존 기록(+0.29)과 일치
- 메모리 계층 사용 계측: READ 계층 5/10(builtin/episodic/working_memory/global/project, <0.02ms), NO-READ 5/10(durable 5종, prefetch 빈 문자열) — 통폐합 근거 확보
- egress 차단: 5/5 정상(사설 IP·cloud metadata·localhost+allow_local=False·file:// 차단), **차단 로그 부재 확인** (egress_policy.py 로거 없음)
- fallback 체인 결함 수정: `[API Error for ...]` → RuntimeError 변환 → 콤보 폴백 재귀 발동, 회귀 테스트 2건, E2E 404→콤보 폴백→qwen3.6:latest 성공
- 토큰 속도: qwen3.8:latest E2E 13.7 tok/s + qwen3.6:latest lh-001 56~67 tok/s (Out 672~1,485) — 체크리스트 "Out 125~1,568" 완전 커버
- basedpyright 0 errors, ruff legacy/style 712 findings (별도 정리 과제)

## D. 강점

1. 작은 모델의 약점을 검색, RAG provenance, CoV, 품질 게이트, tool loop, multi-model fallback으로 보완하는 방향이 일관되다.
2. 로컬 모델 우선 정책과 상위 fallback을 설정에서 분리해 실험할 수 있다.
3. TaskStateStore와 TaskOutcome으로 long-horizon 작업을 단순 스트림보다 오래 유지할 수 있다.
4. 도구 실행을 permission/guardrail/audit로 연결했고 native function calling과 XML fallback을 함께 지원한다.
5. 테스트 수가 많고, 서버를 실제 기동하는 E2E smoke 경로가 있다.

## E. 주요 격차 (2026-08-17 갱신)

| ID | 문제 | 영향 | 우선순위 | 현재 증거 |
|---|---|---|---|---|
| CORE-01 | 일부 side-effect connector와 subagent 생성 경로가 runtime permission contract 밖에 있을 수 있음 | 같은 요청의 상태·권한·관측이 경로마다 달라질 수 있음 | P0 | shell/Git/web fetch/external-brain/system/filesystem API와 41 HTTP egress call site는 경계 연결, legal 정책 잔여 |
| SEARCH-01 | 외부 provider live 품질의 recall과 평가 범위가 상용 목표에 미달 | authority-rescue와 Qwen source hint로 확장 relevance는 개선됐지만 provider 안정성과 P95 tail이 목표 미달 | P1 | historical DDG baseline P@3 0.833/Recall@3 0.633; current self-hosted 2-case P@3 0.167/Recall@3 0.167, 6-case P@3 0.389/Recall@3 0.667/nDCG@3 0.741, load P95 1805.8ms |
| SEC-01 | 모든 외부 HTTP connector의 공통 egress policy가 아직 아님 | 일부 배포가 legal terms attestation 없이 audit 모드로 남을 수 있음 | P0 | safe_urlopen/HTTPX request hook/robots/legal policy로 41개 call site를 guarded; enforce 입력 잔여 |
| OPS-01 | 저장소 전체 스타일 debt가 남아 있음 | 일관된 lint gate와 유지보수성이 저하됨 | P1 | 전체 basedpyright 0 errors, 전체 Ruff 712 legacy/style findings |
| MEM-01 | 여러 memory store의 충돌 정책과 Vault 원문 자산 변경 정책이 분산됨 | 중복 주입과 개인정보 잔존 위험 | P1 | export/redact/retention API와 provider 계약 완료, Vault 원문은 기본 제외·redacted opt-in |
| UX-01 | 작업 로그/승인/재개 위치가 UI 전반에서 일관되지 않음 | 사용자가 실패 원인과 다음 행동을 이해하기 어려움 | P1 | API·dashboard 변형 공존 |

## F. 현재 판정

현재 수준은 **기능 검증을 통과한 베타 이전의 고기능 프로토타입**이다. Agent core, tool permission, local-first model routing, RAG provenance, task persistence, chat/task/slash/CLI/MAX/multiplexer의 canonical runtime 연결, memory compliance contract, bounded sandbox quota, 실패/취소 rollback, shell side-effect fail-closed 경계는 실제 코드와 테스트로 확인됐다. 상용서비스 수준으로 판단하려면 live 검색 relevance와 claim accuracy 개선, 배포 legal policy enforce 입력, 전체 타입 게이트, 부하/P95/P99와 장애 복구 rehearsal이 추가로 필요하다.
