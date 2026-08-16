# 01 Current State Assessment

기준일: 2026-08-10  
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
| 기억/RAG | Session, Vault, GBrain, VectorStore, `RAGIndexer` | [~] 4-tier/export/redaction/retention과 durable purge는 통합됐고 Vault 원문 asset 자동 변경은 opt-in |
| 웹 검색 | SearXNG/Tavily/Jina/DDG/Lite/선택적 self-hosted + cache + URL quality contract + live benchmark | [~] 설정된 self-hosted provider availability는 확인됐지만 SearXNG/DuckDuckGo 변동성과 live relevance가 남음 |
| API/CLI/UI | OpenAI 호환 API, legacy routes, Typer CLI, dashboard | [~] chat/task/slash/CLI/MAX/multiplexer runtime 경로와 shell/Git/web/external-brain/system/filesystem permission 경계 연결, legal policy는 코드화됐지만 배포 attestation 입력이 남음 |
| 평가 | QualityGate, BenchmarkHarness, TaskOutcome, performance benchmark | [x] 계약 및 CI gate 연결 |

## C. 확인된 실행 결과

- 최신 전체 회귀: 정식 `antigravity_k.api.server:app` 서버 기동 상태에서 `3186 passed, 4 skipped, 7 warnings`.
- 서버 수동 QA: `/v1/health 200`, `/openapi.json 200`, 비인증 보호 route `401`, 인증 `/api/fs/browse 200`, `/api/git/status 200`, E2E smoke `9 passed`.
- 서버 기동 후 `/health`, `/openapi.json`, 인증 export/slash/shell/Git HTTP contract: 정상. Git 내부 path는 200, 외부 path는 403, 비인증 요청은 401이었다.
- 인증 `/api/agent/tools/shell/run`은 `200`과 `sandboxed: true`를 반환했고, 비인증 요청은 `401`이었다.
- qwen3.6 Ollama native function call: `read_file` 호출을 provider adapter에서 확인.
- qwen3.6:latest Ollama simple local benchmark는 target-aware sampling, 비교 표 출력 계약, 반복 수정 anchoring 보정 후 2회 반복 4개 결과 모두 `excellent`, benchmark/quality `1.0`, 표준편차 `0.000`, all-excellent run rate `1.000`이었다. 원본 artifact는 `data/benchmarks/local-model-stable-simple.json`이다.
- qwen3.6:latest frontier 5-case benchmark를 2회 반복한 최신 run은 10개 결과 모두 `excellent`, 평균·최솟값 benchmark/quality/keyword `1.000`, benchmark 표준편차 `0.000`, all-excellent run rate `1.000`, 평균 latency `34.0초`였다. 두 번째 반복에서 3회의 품질 재생성이 발생했지만 최종 결과는 모두 통과했다. ToolLoop와 benchmark에 QualityGate 피드백 기반 최대 2회 재생성, 요구사항 coverage, 내부 사고·외국어 오염·가독성 검사를 연결했다.
- `qwen3.6:latest` live grounding mode는 native `think:false`와 JSON schema 응답으로 2개 controlled positive case를 3회 반복했고, 6/6 claim-level 통과(case pass rate/all-pass run rate `1.0`, citation coverage/precision `1.0`, conflict acknowledgement `1.0`)를 기록했다. 별도 simple stability run에서도 2회 반복 모두 `excellent`을 유지했다.
- 실제 DuckDuckGo search evidence를 넣은 Qwen grounding도 cache-allowed 3회에서 `6/6 passed`를 기록했다. forced-refresh 별도 실행은 `1/2 passed`였고 DuckDuckGo `202` 및 PEP query empty result를 artifact에 남겨 provider availability가 별도 출시 차단임을 확인했다.
- 검색 품질 계약: URL 정규화, 결과 다양성, graded relevance/nDCG, citation, 비신뢰 웹 콘텐츠, SSRF redirect guard 테스트를 추가했다. 기본 2-case와 확장 6-case fixture를 분리해 healthy-provider baseline과 outage evidence를 구분한다.
- 정상 provider live search benchmark는 provider error `0`으로 실행됐고 평균 P@3 `0.833`, Recall@3 `0.633`, MRR `1.0`, nDCG@3 `0.883`, domain diversity `0.833`이었다. 같은 날 fresh availability run은 두 케이스 모두 `empty_result`로 감지되어 비제로 종료됐으며, 현재 SearXNG도 실패 상태다.
- 2026-08-10 최신 `AGK_SEARCH_ENGINE_URL` self-hosted 2-case run은 `data/benchmarks/live-search.json`에 provider `error_count=0`, P@3 `0.167`, Recall@3 `0.167`, MRR `0.500`, nDCG@3 `0.210`, domain diversity `0.667`로 기록됐다. query rewrite와 exact-version relevance guard를 적용했지만 relevance 목표는 아직 미달이다.
- 같은 endpoint의 authority-rescue와 Qwen3.6 official source hint 보정 후 확장 6-case run은 `error_count=0`, P@3 `0.389`, Recall@3 `0.667`, MRR `0.917`, nDCG@3 `0.741`, domain diversity `0.722`를 기록했다. RFC·Ollama·MDN 공식 문서와 QwenLM/Ollama Qwen3.6 source가 top-k로 회복됐지만 SearXNG/DuckDuckGo 변동성과 P95 tail 때문에 상용 목표에는 미달이다.
- configured self-hosted healthy load run은 3 repeats x 2 concurrency, 6 samples에서 `error_count=0`, P50 `52.2ms`, P95/P99 `1805.8ms`를 기록했다. `AGK_SEARCH_FALLBACK_BUDGET_MS=1500` latency budget으로 tail은 줄었지만 운영 P95 gate는 아직 미달이다.
- `/api/slash`에서 `/goal`과 자연어 입력이 bound `AgentRuntime`을 통해 실행되고 HTTP 200 contract를 반환하는 것을 확인했다.
- `/api/memory/export`는 미인증 요청 401, 인증 요청 200을 반환하고 Vault asset 기본 정책을 `excluded_by_default`로 표시한다.
- `uvx --from basedpyright basedpyright src --level error` 전체 소스 진단은 현재 0 errors로 통과했다. 저장소 전체 `ruff check src/antigravity_k`는 legacy/style debt 712건을 보고하므로 별도 정리 과제로 남아 있다.

## D. 강점

1. 작은 모델의 약점을 검색, RAG provenance, CoV, 품질 게이트, tool loop, multi-model fallback으로 보완하는 방향이 일관되다.
2. 로컬 모델 우선 정책과 상위 fallback을 설정에서 분리해 실험할 수 있다.
3. TaskStateStore와 TaskOutcome으로 long-horizon 작업을 단순 스트림보다 오래 유지할 수 있다.
4. 도구 실행을 permission/guardrail/audit로 연결했고 native function calling과 XML fallback을 함께 지원한다.
5. 테스트 수가 많고, 서버를 실제 기동하는 E2E smoke 경로가 있다.

## E. 주요 격차

| ID | 문제 | 영향 | 우선순위 | 현재 증거 |
|---|---|---|---|---|
| CORE-01 | 일부 side-effect connector와 subagent 생성 경로가 runtime permission contract 밖에 있을 수 있음 | 같은 요청의 상태·권한·관측이 경로마다 달라질 수 있음 | P0 | shell/Git/web fetch/external-brain/system/filesystem API와 41 HTTP egress call site는 경계 연결, legal 정책 잔여 |
| SEARCH-01 | 외부 provider live 품질의 recall과 평가 범위가 상용 목표에 미달 | authority-rescue와 Qwen source hint로 확장 relevance는 개선됐지만 provider 안정성과 P95 tail이 목표 미달 | P1 | historical DDG baseline P@3 0.833/Recall@3 0.633; current self-hosted 2-case P@3 0.167/Recall@3 0.167, 6-case P@3 0.389/Recall@3 0.667/nDCG@3 0.741, load P95 1805.8ms |
| SEC-01 | 모든 외부 HTTP connector의 공통 egress policy가 아직 아님 | 일부 배포가 legal terms attestation 없이 audit 모드로 남을 수 있음 | P0 | safe_urlopen/HTTPX request hook/robots/legal policy로 41개 call site를 guarded; enforce 입력 잔여 |
| OPS-01 | 저장소 전체 스타일 debt가 남아 있음 | 일관된 lint gate와 유지보수성이 저하됨 | P1 | 전체 basedpyright는 0 errors, 전체 Ruff는 712 legacy/style findings |
| MEM-01 | 여러 memory store의 충돌 정책과 Vault 원문 자산 변경 정책이 분산됨 | 중복 주입과 개인정보 잔존 위험 | P1 | export/redact/retention API와 provider 계약 완료, Vault 원문은 기본 제외·redacted opt-in |
| UX-01 | 작업 로그/승인/재개 위치가 UI 전반에서 일관되지 않음 | 사용자가 실패 원인과 다음 행동을 이해하기 어려움 | P1 | API·dashboard 변형 공존 |

## F. 현재 판정

현재 수준은 **기능 검증을 통과한 베타 이전의 고기능 프로토타입**이다. Agent core, tool permission, local-first model routing, RAG provenance, task persistence, chat/task/slash/CLI/MAX/multiplexer의 canonical runtime 연결, memory compliance contract, bounded sandbox quota, 실패/취소 rollback, shell side-effect fail-closed 경계는 실제 코드와 테스트로 확인됐다. 상용서비스 수준으로 판단하려면 live 검색 relevance와 claim accuracy 개선, 배포 legal policy enforce 입력, 전체 타입 게이트, 부하/P95/P99와 장애 복구 rehearsal이 추가로 필요하다.
