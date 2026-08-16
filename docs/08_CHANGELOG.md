# 08 Changelog

## 2026-08-13

### Project-scoped memory isolation

- 프로젝트 결정과 일반 사실을 typed key로 저장하는 `ProjectMemoryProvider`를 추가했다. 저장 위치는 각 workspace의 `.antigravity/memory/project_facts.json`이며, 현재 사용자의 명시적 정정이 durable project decision보다 우선한다. `프로젝트 결정: key=value`와 `프로젝트 사실: key=value`로 임의의 명시적 항목을 일반 turn에서도 기록할 수 있다.
- `project` scope를 export/redact/clear/retention과 인증 purge audit에 연결했다. 한 `MemoryManager`는 하나의 project root에만 바인딩되며 다른 root로 전환하려 하면 실패한다.
- 기존 process-global episodic 경로와 process-CWD Cavemem 경로를 project-local `.antigravity/memory/`로 이동했다. 공통 경로 검증은 심볼릭 링크가 workspace 밖을 가리킬 때 어떤 memory store도 생성되기 전에 거부한다.
- 별도 두 Python 프로세스에서 project A의 이전 `postgresql`이 최신 `sqlite`로 교체되고 project B의 `mysql`과 서로 노출되지 않는 것을 확인했다. 영향 영역 `112 passed`, 새 provider basedpyright 0 errors/0 warnings, Ruff clean이다.
- 보편적 project key 별칭을 canonical key로 수렴하고 기존 파일의 alias 충돌도 관측 시각 latest-wins로 마이그레이션한다. 명시적인 read-only project fact 질의는 authoritative 값이 하나일 때 도구와 state graph 없이 로컬 모델에 전달한다. 변경·검색·실행 요청은 fast path에서 제외한다.
- 실제 `qwen3.6:latest` CLI에서 alias 두 개로 변경된 database 결정을 조회해 최종 `sqlite`, 도구 호출 0회, capacity/quality rewrite 0회를 확인했다. generic prose QualityGate는 모델이 authoritative 값을 정확히 반환한 경우에만 생략되어 짧은 형식 요청의 정답을 장황한 환각으로 덮지 않는다.
- 프로젝트 고유 용어를 canonical key에 연결하는 typed `project_aliases.json` 스키마와 `agk memory alias-set|alias-remove|aliases` CLI를 추가했다. 중복·내장 key 재정의·alias chain·malformed JSON·workspace 밖 symlink는 fail-closed한다.
- 사용자 별칭을 저장, legacy migration, 현재 턴 충돌, episodic recall, typed metadata, tool-free direct recall에 일관 적용했다. 설정은 provider 시작 시 immutable snapshot으로 로드되며 project memory purge 후에도 보존된다.
- 실제 `qwen3.6:latest` CLI에서 `primary_store -> database` 설정 후 별도 프로세스로 값을 정정하고 조회해 `sqlite`만 반환되는 것을 확인했다. focused `21 passed`, CLI subprocess `4 passed`, 영향 영역 `297 passed`, 전체 `3442 passed, 4 skipped`, 새 engine 모듈 basedpyright 0 errors/0 warnings와 변경 파일 Ruff/LSP clean을 통과했다.

### Hard-bounded long context

- 짧지만 거대한 단일 사용자 목표를 trajectory head/tail에 중복하던 문제와 recent-message fast return이 모델 token budget을 무시하던 문제를 수정했다.
- 새 `context_budget_enforcer.py`가 메시지를 불변 복사하고 우선순위에 따라 head/tail compact해 최종 모델 입력 상한을 강제한다. 최신 사용자 목표, system context, structured tool provenance와 출력 끝의 검증값을 우선 보존한다.
- canonical `run_stream` 통합 회귀와 native Ollama `qwen3.6:latest` QA를 통과했다. 128-token 입력에서 양쪽 제약을 보존하고 모델은 `CONTEXT_OK`만 반환했다. focused `59 passed`, 영향 영역 `182 passed`, 전체 `3446 passed, 4 skipped`, 새 모듈 basedpyright 0 errors/0 warnings와 변경 파일 Ruff/LSP clean이다.
- canonical background task의 bounded context를 versioned `TaskContextSnapshot`으로 SQLite execution ledger에 저장하고 process restart/checkpoint resume 시 동일 task의 최신 snapshot만 복원한다. transient recalled memory와 provider transport metadata는 snapshot에서 제외하며 corrupt latest snapshot은 fail-closed한다.
- 두 process의 같은 DB에 alpha/beta snapshot을 저장한 QA에서 alpha만 복원되고 beta는 비노출이었으며, native `qwen3.6:latest`가 `RESTART_CONTEXT_OK`만 반환했다. 영향 영역 `191 passed`, 전체 `3451 passed, 4 skipped`, 새 모듈 basedpyright 0 errors/0 warnings와 Ruff/LSP clean이다.
- direct interactive 실행도 최초 대화와 실패·일시정지 부분 출력을 checkpoint에 저장한다. `agk task list|status|output|resume`, canonical task API, `AGK_TASK_DB_PATH`를 추가해 반환된 `direct_*` ID를 다른 프로세스에서 조회·재개할 수 있다.
- snapshot은 OpenAI 호환 `developer` 역할을 보존한다. 실제 `qwen3.6:latest` CLI와 인증된 FastAPI 서버에서 direct task resume가 `done`으로 끝나고 부분 출력과 task-local alpha context만 누적되며 beta marker가 섞이지 않는 것을 확인했다.
- direct resume 영향 경로 `77 passed`, 전체 `3459 passed, 4 skipped`, 신규 재개 모듈 basedpyright 0 errors/0 warnings와 변경 파일 Ruff/LSP clean을 통과했다.

## 2026-08-10

### Local quality stability and final verification

- 사용자 응답 언어·상세도·설명 수준·작업 도메인을 `preference_facts.json`의 typed keyed fact로 저장하고, 현재 명시적 요청 > durable explicit preference > inferred profile 순으로 충돌을 해결한다. orchestrator의 자동 학습 metadata와 `UserIntentModeler` prompt도 같은 값을 사용하며, 교차 저장소의 stale record와 동일 중복 record는 각각 `memory_conflict`/`memory_dedupe`로 모델 주입 전에 제거한다.
- 새 preference fact를 global export/redact/clear/retention에 포함하고 알려진 legacy 문자열을 시작 시 마이그레이션했다. cross-process QA는 최신 `concise` 1회, stale 값 0회였고 영향 영역 `152 passed`, 전체 비벤치마크 `3373 passed, 4 skipped, 16 deselected`가 통과했다. 프로젝트 결정은 project-scoped provider가 생길 때까지 전역 메모리에 승격하지 않는다.
- `MemoryFact` authority 계약과 provider 순서에 독립적인 identity conflict resolver를 추가했다. 현재 사용자 정정이 durable global identity보다 우선하고, durable identity가 오래된 episodic/working recall보다 우선한다. 충돌 record는 모델 컨텍스트 주입 전에 제거되며 선택 source/scope와 억제 건수만 남겨 오래된 값의 재노출을 막는다.
- 오래된 episodic 이름과 최신 global identity를 서로 다른 프로세스에서 저장·재로딩한 QA에서 최신 값만 남는 것을 확인했다. conflict focused 5개, memory/orchestrator 영향 120개, 전체 비벤치마크 `3360 passed, 4 skipped, 16 deselected`가 통과했고 새 resolver/contracts/global provider는 Ruff, basedpyright, no-excuse, LSP 검사를 통과했다.
- `BenchmarkHarness`가 `TaskOutcome`을 모델별 task calibration artifact로 export하고 `/benchmark task-export <model>`로 이를 저장한다. `ModelQualityCalibrationStore`는 기존 local generation artifact와 task artifact를 함께 읽어 작업 수, 성공률, tool accuracy, retry rate, 오류 수를 eligibility에 반영한다. Router status에는 측정된 operational metrics를 노출하며, artifact가 없는 모델은 기존 static calibration 동작을 유지한다. 임시 Qwen3.6 artifact 3개 작업은 성공률·tool accuracy `1.0`, retry `0.0`으로 configured gate를 통과했다.
- `LocalProviderCapabilityProbe`가 Ollama `/api/show`, LM Studio `/v1/models`, direct MLX runtime을 읽기 전용으로 확인하고, `/v1/models`, ModelManager 상태, ModelRouter 상태에 native tool calling/runtime 상태를 노출한다. `ToolLoopEngine`은 이 cached capability를 사용해 명시적으로 native tool calling을 지원하지 않는 로컬 모델에는 schema를 보내지 않고 XML 경로를 유지하며, LM Studio의 명시적 지원은 OpenAI schema 경로로 허용한다. LLM trace에는 `native_tool_calling`과 provider runtime 상태가 기록된다. 실제 qwen3.6:latest에서는 `tools` capability를 확인한 뒤 `read_file(README.md)` native tool call을 반환했다.
- Qwen3.6 benchmark sampling을 target-aware하게 조정하고, 비교 요청에는 비교 표를 강제하며, 반복 품질 수정에서는 반복된 기존 응답을 다시 prompt에 고정하지 않도록 보정했다. `data/benchmarks/local-model-stable-simple.json`의 simple 2-case × 2 repeats는 4개 결과 모두 `excellent`, benchmark 표준편차 `0.000`, all-excellent run rate `1.000`을 기록했다.
- 검색 snippet의 untrusted evidence boundary가 중첩되지 않도록 formatter를 단일 wrapper 구조로 정규화하고, 실제 provider evidence → citation source 복원 → Qwen 응답 → strict claim evaluator 경로의 회귀를 추가했다.
- 정식 서버 기동 전체 회귀는 `3186 passed, 4 skipped, 7 warnings`, `make quality-contract`는 `53 passed`, `make search-quality`는 `41 passed`로 확인했다. `make audit-egress`는 41개 call site가 모두 `guarded_endpoint`인 egress inventory를 갱신했다.
- `ModelProfile`에 공통 `effective_parameter_count_b`, `capability_tier`, `is_local`, `is_20b_plus`, `routing_metadata()`를 추가해 qwen3.6 36B를 로컬 `30B` tier로 일관되게 표시한다. `/v1/models`와 `agk models`가 같은 capability matrix를 노출하고, confidence evaluator도 같은 유효 파라미터 계산을 사용한다.
- 중복 등록된 qwen3.6 profile의 reasoning/vision 역할과 defaults의 coding 역할을 병합해 단일 모델이 모든 의도된 역할에서 조회되도록 했다. `ModelManager.get_by_role`, `ModelRegistry.find_by_role`, confidence evaluator candidate selection, API roles metadata가 같은 multi-role 계약을 사용한다.
- `LegalTermsPolicy.from_env(now=...)`에 clock injection을 연결해 만료 시각에 따라 흔들리던 enforce fixture를 결정론적으로 고정했다. 전체 crawler policy와 서버 기동 회귀에서 `policy_attested`/`policy_expired` 계약을 각각 검증한다.
- DuckDuckGo HTML `202`/rate-limit에 DuckDuckGo Lite fallback을 추가하고, `AGK_SEARCH_ENGINE_URL` self-hosted search API를 선택적 provider로 `WebSearchEngine`에 연결했다. configured 2-case live run은 provider `error_count=0`을 기록했지만 P@3 `0.500`, Recall@3 `0.367`로 relevance 개선 과제를 투명하게 남겼다.
- self-hosted provider의 부분 결과에도 대체 쿼리를 재전달하고 회귀 테스트를 추가했다. 확장 6-case live run은 error `0`이지만 P@3 `0.056`, Recall@3 `0.083`, nDCG@3 `0.117`이며, 3 repeats x 2 concurrency load는 error `0`, P50 `28.0ms`, P95/P99 `1868.5ms`로 기록됐다.
- 기술 질의 rewrite(`official docs`, RFC/MDN/Ollama authority hint), self-hosted 최소 `max_results=10`, version-aware query relevance, latency-aware fallback budget을 추가했다. 최신 기본 설정 run은 6-case P@3 `0.056`, Recall@3 `0.083`, nDCG@3 `0.117`, error `0`, load P95/P99 `1805.8ms`를 기록했다. CLI `agk models`는 multi-role capability를 `Roles` 열로 표시한다.
- runtime engine type lane(`context_shaper`, `task_runner`, `agent_runtime`, `agent_archive`, `rag_indexer`, `tool_call_parser`)의 실제 컨테이너·상태·optional 저장소 경계를 명시해 변경 대상 basedpyright를 0 errors로 만들었다. 전체 `src` 진단은 `521`에서 `501 errors`로 감소했고 관련 회귀는 `64 passed`였다.
- 전체 `src` basedpyright hard gate를 `501`에서 `0 errors`로 낮췄다. protocol/model/provider, browser, slash/TUI, RAG/memory, security, orchestration, API/filesystem 경계를 실제 회귀로 확인했으며, 저장소 전체 Ruff는 712 legacy/style findings로 별도 추적한다.
- 검색 결과 중 같은 주제의 상충 연도를 자동 감지해 `[search_conflicts]` citation pair metadata로 LLM 컨텍스트에 전달하고, 인용 검증기가 caller-supplied set 없이도 불일치 미인정 답변을 감지하도록 연결했다. 메타데이터도 context budget에 포함해 작은 모델의 입력 상한을 보존했다.
- 같은 conflict gate를 version, context length, parameter count, memory, price, latency, throughput처럼 명시된 동일 지표의 값 비교까지 확장했다. 이름 없는 숫자는 충돌로 처리하지 않아 검색 결과 간 정상적인 수치 병존을 보수적으로 유지한다.
- Qwen의 실제 grounded 응답처럼 충돌 선언과 citation pair가 이웃 문장으로 분리되는 경우를 evaluator가 오판하지 않도록 했다. 바로 앞 claim의 conflict acknowledgement는 다음 conflicting citation claim에만 적용한다.
- self-hosted provider가 출력 수를 채운 경우에도 단일 provider이거나 질의 relevance가 낮으면 Jina 후보를 추가 수집하도록 보강했다. fallback query에서도 낮은-relevance self-hosted 결과는 Jina를 먼저 탐색하며, 그 결과도 낮은 relevance일 때만 SearXNG와 DuckDuckGo/Lite까지 순차 탐색한다. 결정론적 검색 계약 47개, 비 E2E 전체 3185개, 서버 E2E 9개를 통과했고 이번 환경에는 `AGK_SEARCH_ENGINE_URL`/`SEARXNG_URL`이 없어 새 live relevance 수치는 기록하지 않았다.
- `ModelQualityCalibrationStore`가 local simple/frontier benchmark artifact를 typed schema로 읽어 mean/min benchmark score, excellent rate, error count를 집계하도록 했다. 기준 미달 모델만 자동 routing 및 confidence evaluator에서 제외하고, artifact가 없는 기존 후보는 보수적으로 유지한다. 기본 `qwen3.6:latest`는 실제 artifact 기준 통과 모델로 로드되며, calibration contract 2개·router/registry/confidence 회귀 66개·비 E2E 전체 3187개·서버 E2E 9개가 통과했다.
- calibration이 artifact의 마지막 run만 보고 이전 반복 실패를 놓치지 않도록 `stability`의 result count, mean/min score, excellent rate, 각 run error count를 우선 집계한다. 마지막 run이 성공했어도 반복 최저 점수나 이전 error가 기준 미달이면 자동 routing에서 제외한다. Qwen simple/frontier artifact는 14개 반복 결과에서 `1.0/1.0/1.0`, error `0`으로 확인됐고 새 contract 4개·비 E2E 전체 3189개·서버 E2E 9개가 통과했다.
- all-excellent run rate도 calibration gate에 추가했다. 사례별 성공률이 높아도 완전 성공한 반복 비율이 기준 미달이면 자동 routing에서 제외하며, simple/frontier Qwen은 4회 run/14개 결과에서 all-excellent `1.0`을 기록했다. 새 contract 5개·비 E2E 전체 3190개·서버 E2E 9개가 통과했다.

## 2026-08-09

### Agent runtime/evaluation

- `TaskOutcome`과 `TaskBenchmarkReport`에 success, completion reason, tools, retry, latency, token, cost 지표를 추가했다.
- `BackgroundTaskRunner` 성공/실패/취소 terminal path에 outcome recorder를 연결했다.
- `ToolLoopEngine` 성공, model-not-loaded, capacity halt, error, approval, step-limit 경로에 outcome recorder를 연결했다.
- `BenchmarkHarness.bind_task_runner()`와 `bind_tool_loop()`를 제공했다.
- `long_horizon` checkpoint/recovery benchmark case를 추가했다.
- `TaskThresholds`와 `TaskBenchmarkReport.check_thresholds()`를 추가하고 CI/Make quality contract에 연결했다.
- `ToolLoopEngine`이 turn마다 QualityGate 상태를 초기화하고, C/F 품질 피드백이 나오면 현재 라우팅 타깃으로 수정 응답을 재생성하도록 연결했다. 개선된 응답은 `_last_agent_output`, `AgentTurnCompleted`, `TaskOutcome`에 반영하며 회귀 테스트를 추가했다.
- COV_VERIFY가 검색 evidence의 unsupported/unknown/conflict citation을 validation failure로 처리하고, 검증기 예외도 fail-closed 재시도 상태로 기록하도록 보강했다. `WebSearchEngine.format_for_llm()`의 snippet을 `[untrusted_web_content]` 경계로 감싸 citation context 복원부터 claim evaluation까지 end-to-end 회귀를 추가했다.
- `PromptBuilder`와 local benchmark에 한국어·근거·계획·checkpoint/recovery 출력 계약을 주입하고, benchmark QualityGate가 누락 keyword까지 감지해 현재 타깃으로 최대 2회 재생성한 뒤 최고 응답을 보존하도록 확장했다. 내부 사고 과정, URL/기술 식별자 가독성 오탐, 중국어 간체·번체 혼입 검사를 보강했다. `--repeats` 안정성 artifact를 추가했으며 최신 Qwen frontier 5-case × 2 repeats는 10개 결과 모두 `excellent`, 평균 benchmark/quality/keyword `1.000`, 표준편차 `0.000`을 기록했다.
- `AgentRuntime` facade를 추가해 default model resolution, stream/complete, background submit/resume을 하나의 runtime contract로 제공한다.
- chat agent streaming, `/api/stream_agent`, background task submit/resume을 `AgentRuntime` singleton으로 연결하고 7개 contract/route regression test를 추가했다.
- slash `/goal`과 slash 자연어 실행을 bound `AgentRuntime`으로 연결하고 `GoalRunner` 주입 contract와 route regression test를 추가했다.
- `/api/stream_agent`, CLI `run`, MAX handler, and multiplexer를 canonical runtime adapter로 연결하고 mock/dynamic fallback 경계를 고정했다.
- bound background StateGraph가 MAX/pipeline transition과 checkpoint를 `task_execution_events` append-only ledger에 기록하도록 추가해, resume checkpoint step과 실행 추적 sequence를 분리했다.
- canonical direct stream/MAX도 `direct_*` task와 terminal state를 기록하고, SSE 첫 이벤트 및 CLI가 task ID를 노출하도록 연결했다. bound StateGraph MAX는 기존 task binding을 재사용해 중첩 task를 만들지 않는다.
- browser/agent/parallel subagent의 직접 `run_stream` 호출을 `subagent_execution` adapter로 수렴했다. 부모 task가 있으면 process-local ContextVar를 통해 같은 SQLite event ledger에 lifecycle을 남기고, 단독 호출은 durable `direct_*` task로 기록한다.
- `SubagentSpawner.spawn()`은 deprecated event-loop 조회 대신 `asyncio.run()`으로 동기 작업을 새 loop에서 종료한다. 실행 중인 loop에서는 coroutine을 만들기 전에 `spawn_parallel()` await를 요구해 미await coroutine 경고를 막는다.
- `TestHarness`, `TestStatus`, `TestIntent`, `TestResult`를 pytest test class가 아닌 도메인 타입으로 명시해 수집 경고를 제거했다. 전체 collection은 `PytestCollectionWarning`을 오류로 승격한 상태에서 3,243개를 수집한다.
- `ModelManager.stream_generate()`를 non-stream과 같은 usage/LLM trace 기록 경로로 수렴했다. 각 span은 선택 모델, combo, fallback depth, provider, local 여부와 유효 파라미터 수를 남겨 Qwen3.6 local-first 선택을 실행 단위에서 관측할 수 있다.
- `MemoryProvider`와 durable provider에 export/redact/retention contract를 추가하고, 인증된 `/api/memory/export`, `/api/memory/redact`, `/api/memory/retention`을 연결했다.
- Vault export는 원문 asset을 기본 제외하고 명시적 opt-in에서도 redacted content만 반환하도록 고정했다.
- `ToolRegistry.execute_approved()`가 permission/capability gate를 재검증하도록 수정했다.
- browser action과 autonomous QA endpoint가 Playwright/QA engine 시작 전에 permission deny를 적용하도록 고정했다.
- `SessionManager`와 builtin/episodic/working/global memory provider에 `session`/`working`/`global`/`all` scoped clear를 추가하고 재시작 후 빈 상태를 검증했다.
- 인증된 `DELETE /api/memory`가 provider별 삭제 건수와 `memory_purge` 감사 이벤트를 반환하도록 연결했다.
- API dependency, Orchestrator, EngineContext, legacy/system memory routes가 하나의 4-tier `MemoryManager`를 공유하도록 통합했다.
- 과거 session JSON과 활성 세션 없는 재기동 상태까지 `all` purge가 제거하도록 강화했다.
- MemoryService, VectorStore, LLMWiki, GBrain, search-cache를 lazy durable purge provider로 연결하고 provider별 삭제 건수를 audit report에 포함했다.

### Search/security

- tracking parameter/fragment/default port를 제거하는 URL canonicalization을 추가했다.
- stable source id, authority score, ranking score, domain diversity와 duplicate winner selection을 추가했다.
- 검색 결과를 `[citation:<source_id>]`와 `[untrusted_web_content]` 경계로 포맷했다.
- tool/system/action markup을 `[blocked_tool_markup]`로 중화했다.
- private/local URL과 unsafe redirect를 PageScraper 및 top-1 sync fetch에서 차단했다.
- DNS 결과의 모든 address를 검증하고 PageScraper transport의 TCP 연결을 public IP에 pin하며 redirect마다 재검증한다.
- `run_bash_command` 직접 호출을 승인 토큰 경계 뒤로 제한하고, agent shell API를 project `cwd`/timeout 검증과 SandboxRunner로 통합했다. 활성 sandbox backend가 없으면 raw subprocess로 폴백하지 않는다.
- invalid skill YAML frontmatter는 안전한 scalar metadata fallback으로 복구하여 자동 skill 선택이 전체 로드를 중단하지 않도록 했다.
- Git API의 `path`를 realpath 기준 project-root 내부로 제한하고, 상대 경로를 project-root 기준으로 해석하도록 보강했다.
- `defaults.coding`과 설정 fallback의 기본 모델을 `qwen3.6:latest`로 정렬했다.
- 자율 QA, 비전 분석, TDD, Discord 통합의 모델 기본값을 `qwen3.6:latest`로 정렬하고, `deepseek-r1:70b`는 명시적 품질 에스컬레이션 후보로 유지했다.
- external-brain list/send API를 adapter 생성 전에 permission gate로 제한하고 전송 경로 회귀 테스트를 추가했다.
- `scripts/run_local_model_benchmark.py`와 `make local-benchmark`를 추가해 qwen3.6 local quality/latency 결과를 JSON으로 재현 가능하게 기록한다.
- 2개 deterministic search golden case에서 P@K/Recall@K/MRR/nDCG/domain diversity를 계산하는 evaluator를 추가했다.
- canonical source id 기반 claim-level citation evaluator와 `WebSearchEngine.evaluate_response()`를 연결했다.
- `make search-quality`와 CI quality step에서 golden/citation contract를 실행한다.
- 부분 검색 결과에도 대체 쿼리를 적용하고 DuckDuckGo 202 응답을 1회 재시도해 provider 변동성을 흡수한다. deterministic fallback regression과 live benchmark CLI를 추가했다.
- 검색 provider별 출력 한도보다 큰 후보 풀을 수집하고 query-title/snippet overlap과 authority를 함께 반영해 rerank하도록 보강했다. 2026-08-09 live 2-case baseline은 평균 P@3 0.833, Recall@3 0.633, MRR 1.0, nDCG@3 0.883, provider error 0이었다.
- 동기 Jina Reader도 public DNS 해석 결과를 검사한 뒤에만 실행하도록 공통 URL 경계를 확장하고 private DNS 회귀 테스트를 추가했다.
- COV_VERIFY의 severity 계약을 실제 `none/low/medium/high` 값과 일치시키고, 검색 evidence의 citation source를 복원해 uncited/unsupported claim을 validation failure로 기록하도록 연결했다.
- 비동기 `WebSearchEngine` LLM context에도 citation별 untrusted evidence boundary를 추가하고, COV 예외를 validation 성공으로 숨기지 않도록 fail-closed 처리했다. 검색 context → source 복원 → claim-level citation evaluation 경로를 통합 테스트했다.
- SearXNG/Jina/DuckDuckGo/Tavily provider별 30초 cooldown을 추가하고, `make search-load`와 typed P50/P95/P99/concurrency benchmark를 추가했다. 장애 run은 빈 결과를 성공으로 숨기지 않는다.
- provider 장애 시 일반 질의에 한해 7 TTL 이내 stale cache를 사용하되 `stale-cache/<engine>`과 `stale` 필드로 명시하고, realtime 질의에는 적용하지 않는다.
- `scripts/audit_egress.py`와 `make audit-egress`로 Python raw `httpx`/`urllib` call site 40개를 JSON inventory로 기록하고, `safe_urlopen` 및 HTTPX request hook을 모두 `guarded_endpoint`로 검증한다. PageScraper의 robots.txt/crawl-delay/rate-limit과 `LegalTermsPolicy` audit/enforce 계약을 연결했다. 배포별 terms attestation 입력은 남은 차단 항목이다.
- `ClaimGroundingCase`와 `make claim-quality`를 추가해 source support, unknown citation, conflicting source pair, unacknowledged conflict를 deterministic fixture로 측정한다. local benchmark는 full Qwen response JSON을 같은 evaluator에 주입할 수 있다.
- Qwen Ollama 비스트리밍 생성도 native `/api/chat`의 `think:false` 경로를 사용하도록 수정해 plain-text `Thinking Process` 유출을 차단하고, provider 회귀 테스트로 content/tool-call 경계를 고정했다.
- `run_local_model_benchmark.py --grounding-live --grounding-repeats 3`가 JSON schema, 사실 검색용 sampling, citation allowlist를 사용해 선택한 로컬 모델의 grounding 응답을 직접 생성하고 평가한다. `qwen3.6:latest` controlled positive fixture 2개를 3회 반복해 `6/6 passed`, case pass rate `1.0`, all-pass run rate `1.0`, citation coverage/precision `1.0`, conflict acknowledgement `1.0`을 기록했다. 같은 실행의 simple suite는 `0.546`으로 변동해 별도 안정성 과제로 남겼다.
- `--grounding-live-search`가 DuckDuckGo/SearXNG/Jina 결과를 실제로 수집해 formatter → citation source 복원 → Qwen 생성 → strict claim evaluator까지 연결한다. cache-allowed 3회 반복은 `6/6 passed`였고, 별도 forced-refresh artifact는 DuckDuckGo `202`와 PEP query empty result를 `1/2 passed` 및 비제로 종료로 기록해 provider availability를 숨기지 않는다.
- 검색 golden case에 human-labeled graded relevance와 weighted nDCG 계산을 연결하고, FastAPI/Python asyncio/robots/Ollama/HTTP 429/Qwen local runtime 6-case 확장 fixture와 `search-live-extended` target을 추가했다.
- Async HTTPX client가 sync egress hook을 await하다 provider 검색을 중단하던 live 결함을 async hook으로 분리하고, 실제 MockTransport hook test와 6-case live outage report로 검증했다.
- 검색 golden case에 human-labeled graded relevance와 weighted nDCG 계산을 연결하고, FastAPI/Python asyncio/robots/Ollama/HTTP 429/Qwen local runtime 6-case 확장 fixture와 `search-live-extended` target을 추가했다.
- Async HTTPX client가 sync egress hook을 await하다 provider 검색을 중단하던 live 결함을 async hook으로 분리하고, 실제 MockTransport hook test와 6-case live outage report로 검증했다.
- Git `diff`/`file-content` 파일 인자를 realpath 기준 repository 내부로 제한하고, system/legacy/filesystem 변이 route가 publisher/file write/subprocess 시작 전에 permission deny를 반환하도록 보강했다.
- SandboxRunner가 stdout/stderr를 실행 중 bounded reader로 수집하고 CPU/memory/process/output 상한을 적용한다. BackgroundTaskRunner는 task 실패·취소 시 pre-task snapshot rollback을 시도한다.
- qwen3.6:latest를 code/main/vision/browser/TDD/Discord 기본 경로로 정렬하고 live search golden fixture의 canonical Qwen URL을 갱신했다.

### Verification

- 검색/보안 targeted tests: 현재 cycle에서 추가된 contract 포함.
- claim grounding benchmark: 4개 fixture case 모두 통과, support/unknown/conflict/unacknowledged conflict 결과를 JSON으로 기록.
- live Qwen grounding benchmark: `data/benchmarks/local-model-grounding-live.json`에 `qwen3.6:latest` 생성 응답과 2개 positive case의 3회 반복 claim-level 결과를 기록했고, 6개 모두 통과했다.
- live provider grounding benchmark: `data/benchmarks/local-model-grounding-search-live.json`에 실제 DuckDuckGo evidence와 Qwen 응답의 3회 cache-backed 결과(`6/6 passed`)를, `data/benchmarks/local-model-grounding-search-live-refresh.json`에 forced-refresh provider 장애(`1/2 passed`, 비제로 종료)를 기록했다.
- QualityGate/tool-loop revision targeted tests: `207 passed` (benchmark harness, output quality, prompt builder, orchestrator, model router/registry, search, claim grounding, crawler, egress 포함), 변경 대상 core basedpyright `0 errors` 및 ruff 통과.
- 최신 전체 회귀: 서버 기동 상태에서 `3186 passed, 4 skipped, 7 warnings` (E2E smoke 9개 포함). stale-cache/egress/crawler/claim-grounding policy targeted tests를 포함한 변경 검증은 통과했고, provider empty-result rehearsal은 `error_count 2`와 비제로 종료 코드로 기록됐다.
- 서버 수동 smoke: `/v1/health 200`, `/openapi.json 200`, 비인증 보호 route `401`, 인증 filesystem/Git route `200`을 확인했다.
- 배포 산출물 smoke: `uvx --from build python -m build --wheel --sdist`가 `antigravity_k-0.1.0-py3-none-any.whl`과 sdist를 생성하고 종료 코드 0으로 끝났다. 변경 대상 basedpyright는 오류 0건이며, legacy/동적 타입 경고는 hard gate 잔여 항목으로 남겼다.
- 남은 warning: invalid skill YAML recovery, duplicate OpenAPI operation IDs, optional email-validator, Quartz/PyAutoGUI fallback, coroutine resource warning. 변경 대상 basedpyright는 오류 0건이며 legacy/dynamic typing warning은 hard gate 잔여 항목이다.

## 미해결

- 배포 도메인의 legal terms attestation/purpose/expiry policy file 생성 및 enforce 전환
- 실제 provider grounding의 forced-refresh availability, 최신성, 다국어 conflict set과 검색 recall을 확대하고 provider 장애 시 fallback/알림 rehearsal을 강화
- live search relevance 개선: 2-case baseline은 P@3 0.833, Recall@3 0.633, MRR 1.0, nDCG@3 0.883으로 개선됐고 graded 6-case fixture를 추가했지만 healthy-provider 실행과 recall 목표 달성이 남음
- legacy/외부 connector의 공통 permission audit boundary 보강
- basedpyright hard gate와 부하/장시간 운영 rehearsal
- Vault 원문 asset의 삭제/변경 정책과 UI consent flow
