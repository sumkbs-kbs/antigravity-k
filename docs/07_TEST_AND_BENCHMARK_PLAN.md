# 07 Test and Benchmark Plan

## 테스트 피라미드

| 층 | 대상 | 기준 |
|---|---|---|
| Unit | URL quality, cache TTL, ranking, TaskOutcome, permission, CoV | 빠르고 deterministic |
| Integration | Ollama/provider adapter, SQLite state, RAG/vector, HTTP adapters | 실제 wire/store 경계 |
| E2E | API health/chat, dashboard Playwright, approval/resume | 사용자 observable result |
| Live smoke | local Ollama, optional web providers | 비용/네트워크 분리, 결과는 baseline과 구분 |

## 현재 계약

- 전체 기준선: `pytest -q -m 'not benchmark'` 최신 실행은 `3373 passed, 4 skipped, 16 deselected`.
- Quality contract: `make search-quality` runs the default retrieval golden set and citation checks; `make search-quality-extended` validates the six-case human-labeled fixture; `AGK_SEARCH_ENGINE_URL=https://main.search-engine-api.pages.dev make search-live` records a configured self-hosted healthy baseline; `make search-live-extended` records live provider availability; `make claim-quality` runs the deterministic support/unknown/conflict fixture; `make quality-contract` adds both claim and task/long-horizon contracts.
- CI performance: `tests/test_benchmark_performance.py`의 benchmark marker와 env threshold.
- API smoke: 서버 기동 후 `/health` 200, `/openapi.json` 200, 보호 route 401, 인증 `/api/fs/browse` 200, `/api/git/status` 200을 확인했고 E2E smoke `9 passed`를 기록했다. 기존 `/api/memory/export`, `/api/slash`, `/api/agent/tools/shell/run`, `/api/agent/tools/external-brain/list` contract도 회귀 suite에서 통과한다.
- Local model benchmark: `make local-benchmark` 또는 `scripts/run_local_model_benchmark.py`가 빠른 smoke를 기록하고, `make local-benchmark-frontier`는 Fibonacci/BST/최신 조사/기술 비교/long-horizon recovery를 포함한 대표 suite를 기본 target `qwen3.6:latest`로 실행한다. `--repeats N`을 사용하면 반복별 결과와 case별 평균·최솟값·표준편차·excellent 비율을 JSON에 저장한다. 최신 simple 2-case × 2 repeats는 target-aware sampling, 비교 표 출력 계약, 반복 수정 anchoring 보정 후 4개 결과 모두 `excellent`, 평균·최솟값 benchmark/quality `1.000`, benchmark 표준편차 `0.000`, all-excellent run rate `1.000`이었다. 이전 Frontier 5-case × 2 repeats도 10개 결과 모두 `excellent`이었다. 2026-08-11의 새 Qwen3.6 frontier 5-case × 1 repeat는 67.24초에 5개 모두 `excellent`, 평균·최저 benchmark/quality `1.000`, 표준편차 `0.000`, all-excellent run rate `1.000`을 기록했다. QualityGate는 내부 사고·외국어 오염·가독성을 검사하고, benchmark는 현재 타깃으로 최대 2회 재생성한 뒤 최고 종합점수 응답을 보존한다. live factual grounding은 별도 측정한다.
- Routing calibration: `router.quality_calibration`은 위의 simple/frontier artifact를 Pydantic schema로 읽어 모델별 mean/min benchmark score와 excellent rate를 계산한다. artifact에 `stability`가 있으면 마지막 run의 `results`가 아니라 반복 집계, all-excellent run rate, run error count를 우선 사용한다. 명시된 artifact가 기준 미달 또는 error를 포함하면 그 모델만 자동 routing과 confidence evaluator 후보에서 제외하며, 측정 artifact가 없는 기존 모델은 fallback 호환성을 위해 계속 후보로 남긴다. 기본 Qwen 기준은 mean `0.8`, min `0.7`, excellent rate `0.8`, all-excellent run rate `0.8`이다.
- Qwen grounding 연결: `--grounding-responses`는 저장된 full response를, `--grounding-live`는 선택한 로컬 모델을, `--grounding-live-search`는 실제 provider 검색 결과와 선택한 로컬 모델을 사용해 case별 응답을 생성한다. 모든 경로는 citation coverage, unsupported/unknown claim, conflicting claim, unacknowledged conflict를 결과 payload에 추가하고 실패 시 비제로 종료한다. controlled positive와 cache-allowed live search는 각각 6/6 통과했으며, forced-refresh provider outage는 1/2와 비제로 종료로 기록됐다.
- Verified code execution grounding (2026-08-13): `agk run "...sum_to(n) 함수를 작성하고 run_bash_command로 실행해줘" --model qwen3.6:latest`가 실제로 `write_file` → `run_bash_command`를 호출해 코드를 실행하고 STDOUT(예: `5050`)을 그대로 보고하는 것을 checkpoint(`task_checkpoints` step 1 `used_tools=["run_bash_command"]`, `completion_reason="tool_round_completed"`)로 확인했다. 이를 위해 세 가지 정확성 계약을 추가했다. (1) `_explicit_tool_contract`가 한국어 조사(로/으로/을/를)로 명명된 도구를 계약에 포함한다 — 이전에는 "X 도구" 형식만 인식해 실행 의도 프롬프트가 도구 없이 직접 응답으로 빠지고 모델이 실행을 서술만 했다. (2) 사용자가 명시적으로 계약한 도구는 ApprovalGate에서 사전 승인된다 — `_user_contracted_tools()`가 활성 task checkpoint의 `expected_tools`를 읽어 `auto_approved_tools`로 전달하며, `run_bash_command` 계약은 실행에 필요한 `write_file`/`edit_file`/`replace_file_content`까지 확장된다(경로 샌드박스·위험 명령 차단 게이트는 여전히 적용). (3) `_quality_revision`이 `run_bash_command` 실행 증거를 받아 결과 값을 그대로 보존하도록 강제한다 — 표면 점수만 개선하려는 재작성이 검증된 실행 출력을 환각으로 덮어쓰는 것을 막는다. 회귀 suite는 영향받는 영역 982 passed / 2 skipped, frontier 5-case × 1 repeat 72.86초 5/5 `excellent`(quality_revision_count 0)를 유지했다.
- Verified code-execution benchmark (2026-08-13): `BenchmarkCase.expected_output` 필드와 `verified_code` 카테고리를 추가했고, `BenchmarkHarness._verify_executed_code`가 모델 응답의 마지막 Python 코드 블록을 추출해 샌드박스(임시 디렉터리, 10초 타임아웃)에서 실제 실행한 뒤 STDOUT을 기대값과 비교한다. 실행 결과가 정답이면 `verified=True`, `BenchmarkResult.verified_output`에 실제 실행 출력을 기록하고, `benchmark_score`는 키워드가 아닌 실행 정확도로 산정된다(실행이 맞으면 1.0, 틀리면 0.0). 실행 결과가 기대값과 다르면 코드를 고치도록 revision을 유도한 뒤 재검증한다. `verf-001`(sum_to(100)→`5050`), `verf-002`(3의 배수의 합→`63`) 두 case가 `--suite verified_code`로 실행 가능하며 qwen3.6:latest에서 2/2 모두 `verified=True`/score `1.0`을 기록했다. 이 benchmark는 prose 품질(quality_grade)과 기능적 정확성(verified)을 분리한다 — 코드-only 답변은 설명 부재로 grade는 낮아도 실행이 맞으면 benchmark_score는 1.0이 된다. 회귀: benchmark 영역 91 passed, ruff clean.
- Memory recall across Korean particle variation (2026-08-13): `EpisodicMemoryProvider.prefetch`의 키워드 매칭이 한국어 조사 변형을 흡수하지 못해 turn 1의 사실("내 이름은 김철수야")이 turn 2의 질문("내 이름이 뭐야?")에서 회상되지 않았다 — "이름이"가 "이름은"과 substring 매칭되지 않아 score가 0이 되었다. 모듈 수준 `_ko_stems()` 정규화기를 추가해 어미 조사(은/는/이/가/을/를/의/로/으로/에/에서/에게/한테/처럼/까지/부터/보다/마다/와/과/도/만/로/에/께)를 longest-first로 제거한 어간으로 매칭한다. 검증: 같은 `persist_dir`을 쓰는 별개 프로세스(=세션 재시작)에서 저장한 사실이 조사가 바뀐 질문으로 회상된다(`CROSS_INSTANCE_RECALL: True`). 회귀: memory 영역 85 passed / 2 skipped, ruff clean. orchestrator는 이미 `prefetch_all` 결과를 `[Recalled Memory]` 시스템 메시지로 주입하므로, 제공자 수준 회상이 동작하면 모델이 과거 사실을 활용할 수 있다.
- Recovery success-rate metric (2026-08-13): `TaskBenchmarkReport`에 `recovery_success_rate` 속성을 추가했다. 이것은 재시도가 필요했던 작업(`retry_count > 0`) 중 최종 성공한 비율로, `retry_rate`(재시도 발생 빈도)나 `task_success_rate`(전체 성공률)와 구분된다 — "재시도 루프가 실제로 작업을 구제했는가"를 측정한다(spec §F "재시도 성공률"). `to_dict()`에 노출되어 calibration artifact와 리포트에 포함된다. 재시도한 작업이 없으면 0.0이다. 회귀: task benchmark 영역 70 passed, ruff clean.
- Multi-agent routing on local model (2026-08-13): `coding-swarm`/`orchestrator-swarm`/`reasoning-swarm` 세 combo가 모두 `qwen3.6:latest`를 1순위로 포함하며, `ModelRouter.route()`는 세 combo 모두에서 `qwen3.6:latest`를 선택한다(단일 로컬 모델이 모든 역할을 충족). `model_policy`가 parameter cap을 초과한 대형 모델(`qwen3-next-80b` 80B, `nemotron-ultra` 550B)을 폴백 체인에서 자동 제외하므로, 에스컬레이션 체인은 정책 호환 모델만으로 구성된다(coding-swarm 8개 → 가용 7개, orchestrator-swarm 6개 → 가용 5개, reasoning-swarm 6개 → 가용 4개). 사용자의 qwen3.6-first 선호와 일치하며, 로컬 모델이 사용 불가해지면 deepseek-r1:70b → 원격 모델 순으로 폴백이 활성화된다.
- Identity-fact extraction & durable personalization (2026-08-13): `GlobalMemoryProvider.sync_turn`이 명시적 metadata만 저장하고 자동 추출이 없어, "내 이름은 김철수야"가 durable fact로 승격되지 않고 decaying episode로만 존재했다(consolidation 시 사라질 수 있음, 프로젝트 단위). `extract_identity_facts()` 정규화기(한국어 자기소개 "내 이름은 X야/요/입니다", "저는 X라고 합니다", 교정형 "내 이름은 X로 바꿨어"; 영어 "my name is X"/"I am X"/"call me X")를 추가해 high-precision으로 이름을 추출하고 keyed identity fact로 저장한다. `set_identity_fact`는 키별로 latest-wins 충돌 해결(이름 변경 시 교체), `identity.json`에 영속화, `prefetch`는 identity fact를 항상 surface(중요도 우선). 검증: 한 프로세스에서 말한 이름이 별개 프로세스의 무관 질의("오늘 날씨 어때?")에서 회상된다(`CROSS_PROCESS_NAME_RECALL: True`). 회귀: memory 영역 48 passed, 전체 영향 영역 1133 passed / 2 skipped, ruff clean.
- Global identity privacy lifecycle (2026-08-13, spec §3C 개인정보 보호/삭제): keyed identity는 `identity.json`에 영속됐지만 global/all export·redact·clear·retention이 category 배열만 다뤄, 사용자가 전역 메모리를 삭제해도 새 프로세스가 이름을 다시 회상했다. `GlobalMemoryProvider`와 공용 memory contract를 작은 모듈로 분리하고 identity를 네 lifecycle에 포함했다. export는 identity record를 반환해 상위 recursive redactor가 마스킹하고, redact/clear/retention은 디스크까지 반영한다. old/recent identity TTL을 파일 mtime 기준으로 구분한다. 실제 `system_api` lifecycle에서 원문 secret 없는 export, persistent redact, max-age retention, purge 후 restart recall empty, `memory_export/redact/retention/purge` audit event를 확인했다. 영향 회귀 171 passed/2 skipped, 새 모듈 basedpyright 0 errors/0 warnings, Ruff/no-excuse/LSP clean. Vault raw asset은 기본 export에서 제외되며 opt-in도 redacted-only이다.
- Vault active-corpus privacy lifecycle (2026-08-13, spec §3C 개인정보 보호/삭제): 일반 `DELETE /api/memory`는 Vault를 열지 않으며, 원문 변경은 인증된 별도 API와 작업별 정확한 확인 토큰(`REDACT_VAULT_ACTIVE_CORPUS`, `PURGE_VAULT_ACTIVE_CORPUS`, `RESTORE_VAULT_SNAPSHOT`)이 있어야 한다. redact는 선택 Markdown의 명시 문자열만 `<REDACTED>`로 바꾸고, purge는 선택 파일만 현재 활성 코퍼스에서 제거한다. 두 작업은 선택 경로 전용 사전 Git snapshot과 변경 commit을 만들며 실패 시 원문과 RAG/LLM Wiki 파생본을 snapshot 내용으로 되돌린다. restore도 전체 HEAD를 이동하지 않고 선택 경로만 복원해 관련 없는 tracked/untracked 파일을 보존한다. RAG 청크와 `source="vault"` + 정확 `source_url` Wiki mirror를 제거하고 redact/restore 후 안전한 내용만 재색인한다. 응답의 `history_retained_for_rollback=true`가 알리듯 원본은 Git 이력에 복구용으로 남으며, 별도 이력 재작성 동의가 없는 영구 삭제는 제공하지 않는다. 영향 회귀 `53 passed`, 전체 비벤치마크 `3355 passed, 4 skipped, 16 deselected`; 새 모듈 basedpyright 0 errors/0 warnings, Ruff/no-excuse/LSP clean이다.
- Cross-provider identity conflict resolution (2026-08-13, spec §3C 메모리 충돌 해결): `GlobalMemoryProvider` 내부의 latest-wins만으로는 `MemoryManager`가 오래된 episodic 이름과 최신 global identity를 함께 이어 붙이는 문제를 막지 못했다. 공용 `MemoryFact` authority 계약과 provider 순서에 독립적인 resolver를 추가해 현재 사용자 정정(`100`) > durable global identity(`80`) > unstructured recall 순으로 승자를 선택한다. 충돌하는 Q/A·working record 전체를 모델 주입 전에 제거하고, 선택된 source/scope와 억제 건수만 표시해 오래된 값이 metadata로 다시 노출되지 않게 했다. 비충돌 기억은 기존 출력 그대로 보존한다. 별도 프로세스에서 오래된 episodic `김철수`와 최신 global `이영희`를 재로딩한 QA 결과는 최신 값 1회, 오래된 값 0회, conflict marker 1회였다. focused 5 passed, 영향 영역 120 passed, 전체 비벤치마크 `3360 passed, 4 skipped, 16 deselected`; 새 resolver/contracts/global provider는 basedpyright 0 errors/0 warnings, Ruff/no-excuse/LSP clean이다. 이어지는 typed user-preference 단계가 개인 선호 충돌을 해결했으며 project decision/general fact는 후속 범위다.
- Typed user-preference conflict and deduplication (2026-08-13, spec §3C 사용자 프로필/충돌 해결): 기존 `learned_preferences`는 한국어 표시 문자열 배열을 누적해 `한국어 응답 선호`와 `영어 응답 선호`, `간결`과 `상세`가 동시에 남았고, `UserIntentModeler.build_context()`의 별도 통계 프로필도 현재 사용자 정정과 충돌할 수 있었다. `preference_facts.json`에 response language/detail, explanation level, task domain을 keyed Pydantic record로 저장하고 `현재 사용자(100) > durable explicit(70) > inferred profile(40)` authority를 적용한다. orchestrator는 표시 문구 대신 `learned_preference_facts` dict를 전달하며, global recall과 user-profile prompt가 같은 winner를 사용한다. 충돌 record는 `memory_conflict`, 동일 record 중복은 `memory_dedupe`로 구분해 모델 주입 전에 제거한다. export/redact/clear/retention은 새 파일에도 적용되며 legacy 알려진 preference 문자열은 시작 시 typed record로 마이그레이션한다. 영어 extractor는 `answer/response/reply/respond` 대상이 있을 때만 승격해 variable/document style 오탐을 막는다. 별도 프로세스 QA는 durable `concise` 1회, stale `상세하게` 0회, conflict marker 1회를 기록했다. 영향 영역 `152 passed`, 전체 비벤치마크 `3373 passed, 4 skipped, 16 deselected`; 새 모듈은 basedpyright 0 errors/0 warnings, Ruff/no-excuse/LSP clean이다. 이어지는 project-scoped memory 단계가 프로젝트 결정과 일반 사실의 전역 누출도 차단했다.
- Project-scoped decision/fact memory (2026-08-13, spec §3C 범위 분리/충돌/삭제): `ProjectMemoryProvider`가 keyed decision/fact를 `<project>/.antigravity/memory/project_facts.json`에 저장하고 `현재 사용자(100) > durable project decision(60)`으로 latest-wins 충돌을 해결한다. 일반 대화에서는 보수적인 프로젝트 기술 결정과 `프로젝트 결정: key=value`/`프로젝트 사실: key=value` 명시 형식을 지원하며 typed metadata도 같은 경계로 파싱한다. clear/export/redact/retention과 인증 purge audit에 `project` scope를 연결했다. episodic과 Cavemem도 같은 project memory root로 이동했고 manager의 workspace 재바인딩 및 심볼릭 링크 외부 탈출을 fail-closed한다. 별도 두 Python 프로세스 QA에서 project A는 최신 `sqlite`만, project B는 `mysql`만 재호출했으며 영향 영역 `112 passed`, 새 모듈 basedpyright 0 errors/0 warnings, Ruff clean이다.
- Project key canonicalization and tool-free recall (2026-08-13): `db`/`dbms`/`db_engine`/`database_engine`, frontend/backend framework, package manager, test runner, deployment target의 보편적 별칭을 typed canonical key로 수렴한다. 기존 `project_facts.json`도 같은 kind/canonical key 안에서 `observed_at` 최신값만 남기고 즉시 재저장한다. 명시적이고 짧은 프로젝트 결정/사실 조회는 authoritative fact가 정확히 하나일 때 tool schema와 state graph를 건너뛰는 direct-local 경로를 사용하며, 변경/검색/실행 의도가 있으면 기존 agent loop를 유지한다. generic prose QualityGate는 모델 출력이 authoritative 값을 실제 포함한 경우에만 재작성을 생략한다. 실제 `qwen3.6:latest` CLI에서 `db_engine=postgresql` 뒤 `dbms=sqlite`를 기록하고 조회했을 때 최종 출력 `sqlite`, tool call 0, capacity/quality revision 0을 확인했다. 운영자가 정의하지 않은 임의 key 간 semantic dedupe는 남아 있다.
- Operator-defined project memory aliases (2026-08-13): `.antigravity/memory/project_aliases.json`의 typed schema와 `agk memory alias-set|alias-remove|aliases` CLI로 프로젝트 고유 용어를 canonical key에 연결한다. 중복 alias, 내장 key 재정의, alias chain, malformed JSON, workspace 밖 symlink는 시작 시 fail-closed하며 provider 인스턴스마다 불변 snapshot으로 로드한다. 사용자 alias는 입력 저장, legacy migration, 현재 턴 정정, episodic marker canonicalization, typed metadata, read-only authoritative 조회에 동일하게 적용되고 project purge는 값만 지우며 설정 파일은 보존한다. 프로젝트별 동일 alias의 독립 mapping과 재시작 적용을 포함한 focused `21 passed`, CLI subprocess `4 passed`, 영향 영역 `297 passed`, 전체 `3442 passed, 4 skipped`를 통과했다. 실제 `qwen3.6:latest` CLI에서 `primary_store`를 `database`에 연결하고 `postgresql`을 `sqlite`로 정정한 뒤 최종 `sqlite`, 도구 호출 0회, capacity/quality revision 0회를 확인했다. 명시적 schema가 없는 자유 텍스트 key 간 의미 추론은 오병합 방지를 위해 하지 않는다.
- Verified code self-correction on executable feedback (2026-08-13): `_execute_single`의 verify→revise→re-verify 루프가 실행 가능한 피드백 기반 자기교정을 수행한다 — 첫 생성 코드가 실행은 되지만 기대 출력과 다르면, harness가 실행 결과를 근거로 revision을 강제하고 재실행·재검증한다(이전 턴의 도구-루프 증거 보존 계약과 동일한 원리). 단위 테스트(`test_execute_single_self_corrects_when_first_code_runs_wrong`)가 잘못된 `print(1234)` → 교정 후 `print(5050)` → `verified=True`/`revision_count>=1`를 확인한다. 라이브 검증: qwen3.6:latest가 `is_palindrome` 엣지 케이스(빈 문자열=True, 대소문자/공백 무시)를 `run_bash_command`로 1스텝 실행해 3개 assert 모두 통과("All test cases passed successfully!") — checkpoint step 1 `used_tools=["run_bash_command"]`로 확인. 이것이 작은 모델이 "코드를 상상하지 않고 실행으로 검증"하는 프론티어급 거동의 핵심이다.
- Durable-fact importance protection during consolidation (2026-08-13): `EpisodicMemoryProvider._consolidate`의 importance 점수가 `access*0.5 + recency*0.5`라서 한 번 언급된 durable preference("나는 들여쓰기에 탭을 사용해")가 filler episode들에 밀려 감쇠 제거되었다 — durable knowledge임에도 low-recency noise로 취급됨. `_is_durable_fact_statement()` 정규화기(한국어 "나는/내가/저는 X 좋아/싫어/사용/선호/쓰", "항상/보통/주로"; 영어 "i prefer/like/use/hate/always", "my preference/favorite/stack")로 durable-fact episode를 감지하고 consolidation 시 importance에 boost(+10.0, eviction floor 위)를 준다. 검증: max_episodes=4에서 durable fact 2개 + filler 12개를 동기화해 두 번의 consolidation을 유도한 뒤 두 fact 모두 회상 가능(`TAB_RECALL: True`, `PY_RECALL: True`, episode_count=4). access-count 재인덱싱이 감쇠 후에도 정확함을 회상 동작으로 확인. 회귀: memory 영역 67 passed / 2 skipped, ruff clean.
- Verified-code stability metric correctness (2026-08-13): `_summarize_repeats`가 `excellent` 판정을 `quality_grade == "excellent"`로만 하여, verified_code case에서 코드 실행은 정확(verified=True, score 1.0)하지만 prose 부재로 grade "retry"인 결과가 routing calibration에 모델을 과소평가했다(all_excellent_run_rate 0.0). `_is_excellent()` 헬퍼를 추가해 verified 결과를 excellent로 간주 — verified_code에서 실행 결과가 ground truth이므로, 정확하지만 간결한 답이 모델의 기능적 역량을 왜곡하지 않는다. per-case grades는 여전히 prose 품질을 정직하게 보고(verf-002 grade "retry" 유지)하되 stability/routing 메트릭만 보정. 검증: qwen3.6 verified_code suite → excellent_rate 1.0, all_excellent_run_rate 1.0 (수정 전 0.0). 회귀: benchmark 영역 85 passed, ruff clean.
- Deterministic multi-step task decomposition (2026-08-13, spec §3A plan→execute): `PlannerExecutor.decompose_task`가 항상 단일 스텝만 반환하는 no-op 셸이었다(복잡도 무관). `_split_explicit_steps()` 정규화기를 추가해 번호 목록(`1.`/`1)`), 불릿 목록(`-`/`*`)을 감지하면 각 항목을 별도 PlanStep으로 분해한다. LLM 호출 없이 순수 구조적 파싱 — 코드 펜스 내 불릿, 단일 불릿, 산문은 false-positive 없이 분해하지 않는다(`_split_explicit_steps` 검증 완료). `execute_plan`이 다중 스텝을 순차 실행하고 각 결과를 trace에 기록한다. 검증: 3-part 현실적 작업("src 파일 수 세기 / 테스트 파일 수 세기 / 합 구하기")이 3개 step으로 분해되어 모두 `done`으로 실행됨. 라이브 runtime 연결은 별도 작업(orchestrator wiring)으로 남아있으나, planner 자체는 이제 호출 즉시 올바르게 동작한다. 회귀: planning 영역 39 passed / 1 skipped, ruff clean.
- Live orchestrator routing of multi-part prompts (2026-08-13, spec §3A): `_synthesize_explicit_pipeline()`를 `route_decision`에 연결해, CEO가 pipeline을 만들지 않았더라도 사용자 프롬프트에 명시적 단계(번호/불릿 목록, 2개 이상)가 있으면 결정론적으로 pipeline을 합성하고 `PIPELINE_EXECUTE`로 라우팅한다. 각 단계는 `{step, agent, task}` 엔트리로 `ctx.analysis["pipeline"]`에 기록되어 기존 `pipeline_execute_handler`가 순차 실행한다. CEO가 이미 pipeline을 만든 경우는 건드리지 않는다(no-op fallback). 검증: 라이브로 qwen3.6:latest에 "1. 루트 파이썬 파일 수 세기 / 2. tests 파일 수 세기 / 3. 비교" 3-part 작업을 실행해 `run_bash_command`가 단계별로 호출되고(checkpoint step 1 `used_tools=["run_bash_command"]`), 결과가 비교 보고됨. 회귀: 영향 영역 1257 passed / 2 skipped, ruff clean.
- Tool failure exit-code surfacing & classification (2026-08-13, spec §3D 도구 실패 복구): `run_bash_command`가 0이 아닌 종료 코드를 stdout/stderr만 반환하고 exit code를 폐기해, 모델이 stderr 내용으로만 실패를 추론해야 했다(신뢰 불가). subprocess 폴백 경로와 샌드박스 경로 모두 비영구 종료 시 `[exit_code=N]` 마커를 결과 앞에 붙이고, 성공 시 마커 없이 출력만 반환한다. `tool_executor._result_indicates_failure()` 헬퍼가 `Error:` 접두사와 `[exit_code=N]`(N≠0) 마커를 모두 인식해 `_record_tool_call`/`_post_execute`/`tool_loop`/`tool_guardrails`가 동일하게 실패를 분류한다 — 종료 코드 마커가 실패를 가리지 않게 한다. 검증: 라이브로 `python3 -c "exit(7)"` 실행 시 에이전트가 종료 코드 7을 정확히 감지·보고, 회귀 909 passed / 2 skipped, ruff clean. 이것은 이전 턴의 verify→revise 자기교정 루프에 직접 기여한다(실행 실패를 확정적으로 감지해야 revision이 발동).
- Secret redaction at the context-injection boundary (2026-08-13, spec §3H 민감정보 마스킹): `ToolLoopEngine._format_tool_response`가 도구 결과를 `[UNTRUSTED_TOOL_RESULT]` 블록으로 컨텍스트에 주입할 때 raw 결과를 그대로 사용해, `.env` 파일 읽기나 API 키 출력 명령이 시크릿을 모델 컨텍스트 윈도우로 유출했다. `redact_full()`을 evidence에 적용해 주입 전에 마스킹한다 — SHA256 provenance는 원본 기준으로 계산되고, truncation 슬라이싱도 redacted evidence 기준으로 동작해 긴 결과에서도 시크릿이 유출되지 않는다. 검증: 라이브로 `read_file /tmp/secret_probe.env`(sk-proj-TESTSECRET...) 실행 시 도구 출력에는 원문이 보이지만 모델 컨텍스트/응답에는 `FAKE_SECRET=<REDACTED>`로만 도달한다. 회귀: 영향 영역 1155 passed / 2 skipped, ruff clean. 이것은 기존 `secret_scanner.redact_full()`의 존재를 컨텍스트 주입 경로에 실제로 연결한 것이다.
- Reflection lesson persistence to failure memory (2026-08-13, spec §3A 자기 검증 + §3G Learning): `CognitiveLoop.reflect()`가 실패율 기반 교훈(lessons)과 retry 전략을 계산하고 `ReflectionResult`로 반환했지만, 호출자(`tool_loop._post_loop_checks`)가 반환값을 무기해 결과가 폐기됐다 — reflection이 fire-and-forget이어서 동일한 실패 패턴이 반복돼도 학습되지 않았다. `reflect()`가 `self.failure_memory.record(tool, error_text, args_summary, fix_applied)`로 교훈을 영속화하도록 연결했다. 실패한 도구들을 집계해 tool 필드에 넣고, lesson을 error_text로, retry_strategy를 fix_applied로 기록한다. `FailureMemory.find_similar()`/`build_prompt()`가 이미 다음 작업에서 이를 회상·주입하므로, 이 연결로 reflection→memory→recall 학습 루프가 폐쇄된다. 검증: 3개 실패 step history로 reflect 호출 시 `failure_memory.record`가 호출되고 lesson이 존재; 성공만 있는 history에서는 spurious 기록 없음. 회귀: 영향 영역 1393 passed / 2 skipped, ruff clean.
- Safety regression guard: dangerous commands denied despite user-contracted tool pre-approval (2026-08-13, spec §3H 사용자 승인 없는 위험 작업 차단): 사용자가 명시적으로 `run_bash_command`를 계약해 ApprovalGate가 사전 승인되는 경로(이전 턴 추가)가 파괴적 명령(`rm -rf /`) 정책을 우회하지 않음을 회귀 테스트로 고정했다. `PermissionGate.decide()`의 `_is_dangerous_command` 검사는 ApprovalGate와 독립적으로 동작하며, `ALWAYS_REQUIRE_APPROVAL`(deploy/git_push/payment 등) 게이트도 `auto_approved_tools`보다 먼저 평가된다 — 사전 승인은 *어떤 도구*를 허가하지 *어떤 파괴적 페이로드*를 허가하지 않는다. 검증: `rm -rf /` 명령이 user-contracted task에서 실행되어도 `PermissionGate.decide`가 `is_denied` 반환. 회귀: tool/security 영역 148 passed, ruff clean.
- Freshness grounding via current-date injection (2026-08-13, spec §3E 최신 정보 반영 + §3B 컨텍스트 재구성): 검색/분석 답변이 훈련 데이터의 과거 연도(예: "2024년 기준")로 환각되는 것을 관찰했다 — `response_contract`가 "시간 인지 검색"을 지시하지만 실제 현재 날짜를 주입하지 않아 모델이 '오늘'이 언제인지 몰랐다. `response_contract(category, current_time)`가 `_format_current_date()`로 실제 날짜("2026년 08월 13일")를 응답 계약 첫 줄에 주입하고, 검색 결과의 게시일과 비교해 최신성을 판단하도록 지시한다. `_build_tool_prompt`가 이미 이 contract를 호출하므로 라이브 런타임에 즉시 적용된다. 검증: "올해(2026년) 출시 스마트폰" 질의에서 모델이 "2026년 현재(8월 기준)"로 답하고 2026년 검색 결과(갤럭시 Z 폴드8)를 인용. 회귀: prompt 영역 103 passed / 1 skipped, ruff clean.
- Verified-code benchmark expanded with algorithmic difficulty-3 cases (2026-08-13, spec §3F 코딩 에이전트 벤치마크): 기존 `verf-001/002`(난이도 1-2, 단순 print)에 `verf-003`(FizzBuzz, 조건 분기 알고리즘)와 `verf-004`(소수 판별 합계, sqrt 최적화 알고리즘)를 추가했다 — 실제 알고리즘적 추론이 필요한 케이스로 verified_code 벤치마크를 강화. 검증: qwen3.6:latest가 4/4 모두 `verified=True`/score `1.0`/revision 0으로 통과(14.8초) — FizzBuzz 15줄 출력과 소수 합 77이 정확히 매칭. 추가로 라이브 도구 체이닝 검증: `run_bash_command`→`read_file`→`grep_search` 3개 도구가 한 작업에서 순차 체이닝되어 실행됨(checkpoint step 2 `used_tools=["run_bash_command","read_file","grep_search"]`). 회귀: benchmark 영역 38 passed, ruff clean.
- Cognitive failure recovery wiring (2026-08-13, spec §3A 실패 복구 + §3D 도구 실패 복구): `run_bash_command`의 `[exit_code=N]`를 ToolExecutor와 guardrail은 실패로 분류했지만 `CognitiveLoop.verify_tool_result()`는 성공 A등급으로 기록했고, `adapt_strategy()`는 프로덕션 ToolLoop에서 호출되지 않았다. 외부 두뇌 위임도 실행 중 이벤트 루프에서 `run_until_complete()`/`asyncio.run()`을 호출해 라우터 await count 0, 결과 `None`으로 실패했으며, 성공 시에도 `FailureMemory.record(task=..., error_pattern=...)`라는 잘못된 계약을 사용했다. 인지 검증이 공용 `classify_tool_failure()`를 재사용하고, ToolLoop가 실패 검증 뒤 async 적응을 호출해 지침을 모델 가시 도구 결과에 붙이며, 외부 위임은 AnyIO timeout 안에서 직접 await하고 실제 FailureMemory 계약으로 저장하도록 연결했다. 기본 로컬 경로는 외부 라우터 없이 2회 이상 실패 시 전략 변경을 주입하고, 외부 라우터가 명시적으로 주입된 경우 3회 실패 후 조언을 사용한다. 실제 `RunBashCommandTool`로 `exit 7`을 세 번 실행한 QA에서 `failed_steps 3`과 세 번째 결과의 `Cognitive Adapt`를 확인했다. focused 4 passed, 관련 206 passed/2 skipped, 전체 비벤치마크 3329 passed/4 skipped/16 deselected, ruff 및 LSP error clean. 엄격 보조 검사기는 기존 대형 모듈의 asyncio/mutable dataclass/broad-except/557·1064 LOC 부채 28건을 계속 보고한다.
- Structured evidence preservation across long-context compression (2026-08-13, spec §3B 프롬프트 압축/컨텍스트 재구성): 생산 스트림은 `TrajectoryCompressor → ContextCompressor.adaptive_compress → ContextShaper` 순으로 대화를 최대 세 번 압축하며, 오버플로 재시도는 `ContextShaper.shape(force_compact=True)`를 추가 호출한다. 기존 구현은 오래된 `<tool_response>`를 길이 표식이나 앞 100자만으로 대체해 `[TOOL_EVIDENCE]` provenance와 출력 끝의 검증값(예: `VERIFIED_RESULT=5050`)을 잃었다. `tool_evidence_compactor.py`를 추가해 metadata JSON을 파싱하고 각 증거를 최대 640자의 head/tail bounded form으로 줄이며, 한 메시지에 묶인 여러 병렬 tool response도 각각 보존한다. Trajectory/Context의 qwen 요약이 성공해도 compact evidence를 결정론적으로 재부착하고, ContextShaper의 snip/auto-compact/old-tool cleanup은 최대 5개 evidence를 보호한다. 생산 순서 QA에서 메시지 수가 `19→12→9→9`로 줄어든 뒤에도 provenance, `source=verify.py`, `VERIFIED_RESULT=5050`이 최종 컨텍스트에 남았다. 관련 context 79 passed, orchestrator/tool-loop 75 passed, 전체 비벤치마크 3335 passed/4 skipped/16 deselected, ruff/LSP/no-excuse(new module) clean. qwen3.6:latest verified-code 4-case 라이브 재검증은 18.91초, 4/4 `verified=True`, mean/min score 1.0, excellent/all-excellent rate 1.0, revision 0을 기록했다.
- Hard final context budget for oversized objectives (2026-08-13, spec §3B 프롬프트 압축/장기 컨텍스트 재구성): `TrajectoryCompressor`가 10개 이하의 단일 oversized 메시지를 head와 tail에 중복하고, `ContextCompressor.adaptive_compress()`도 최근 메시지 수가 작으면 token limit을 초과한 원문을 그대로 반환했다. 순수 typed `context_budget_enforcer.py`가 caller input을 복제한 뒤 낮은 우선순위·큰 메시지부터 결정론적으로 head/tail compact하고, 마지막 사용자 목표와 system context를 우선 보호하면서 최종 estimator 합계가 모델별 budget을 넘지 않도록 한다. 일반 `compress`와 `adaptive_compress`의 모든 초과 경로에 이 최종 경계를 적용했고 trajectory가 실제로 줄이지 않은 경우 거짓 사용자 알림도 제거했다. 단일 목표, structured tool evidence, input immutability, canonical `run_stream` 전달을 red→green 회귀로 고정했으며 focused `59 passed`, context/orchestrator/tool/runtime 영향 `182 passed`, 전체 `3446 passed, 4 skipped`, 새 모듈 basedpyright 0 errors/0 warnings와 변경 파일 Ruff/LSP clean을 확인했다. 실제 native Ollama `think=false` 경로에서 128-token 압축 후 `BEGIN_OBJECTIVE`/`END_CONSTRAINT`가 모두 남았고 `qwen3.6:latest`가 정확히 `CONTEXT_OK`만 반환했다.
- Task-local context reconstruction across process restart (2026-08-13, spec §3A 멀티스텝 재개 + §3B 장기 작업 컨텍스트 재구성): 기존 `ContextCompressor.long_term_memory.json`은 프로젝트 전역 summary 배열이라 task 격리가 없고 background resume는 원래 prompt와 output tail만 재주입했다. versioned Pydantic `TaskContextSnapshot`을 기존 SQLite execution-event ledger에 append하고, 새 process의 `BackgroundTaskRunner.resume_task()`가 같은 task ID의 최신 valid snapshot만 `[Restored Task Context]`로 주입한다. `[Recalled Memory]`와 이전 restore header는 재영속하지 않아 global/user memory를 task snapshot에 복제하거나 재귀 중첩하지 않으며 provider transport metadata도 제거한다. corrupt latest event는 stale snapshot으로 되돌아가지 않고 fail-closed한다. 이후 direct interactive task도 최초 대화와 실패·일시정지 부분 출력을 checkpoint에 저장하고 `agk task status|output|resume` 및 task API로 재개하도록 확장했다. `developer` 역할과 `AGK_TASK_DB_PATH` 프로세스 공유 경계도 회귀로 고정했다. 실제 `qwen3.6:latest` CLI와 인증된 FastAPI 서버에서 각각 direct task를 재개해 `done`, 부분 출력 누적, alpha/beta 격리, 지정 검증 토큰을 확인했다. 영향 경로 `77 passed`, 전체 `3459 passed, 4 skipped`, 신규 재개 모듈 basedpyright 0 errors/0 warnings와 변경 파일 Ruff/LSP clean을 통과했다.
- Default-agent search quality rescue (2026-08-13, spec §3E 쿼리 재작성/검색 결과 검증/오검색 필터링): 품질 기반 재작성과 authority/query relevance ranking은 async `WebSearchEngine`에만 연결돼 있었지만, 실제 `ToolExecutor`, deterministic worker, chat/system API는 동기 `WebSearchTool`을 등록해 결과가 1건 이상이면 해당 계약을 우회했다. 동기 도구가 tuple 결과를 canonical `SearchResult`로 변환해 공유 `has_query_relevant_result`, `has_authoritative_query_result`, `rank_search_results`를 사용하고, 관련성·권위가 부족하면 fallback query의 self-hosted→Jina→SearXNG→DDG 후보를 합친 뒤 원본 질의 기준으로 재랭킹한다. Qwen3.6은 provider 실패 시 official source registry도 합친다. red/green 회귀 2개와 웹 검색 영역 126개가 통과했다. 실제 `ToolExecutor.register_default_tools()` 드라이버에서 `web_search` 등록, `Qwen3.7 local model official` 재작성 호출, 관련 결과 1위, `[citation:<source_id>]` 출력을 확인했다.
- Runtime grounding contract: `WebSearchEngine.format_for_llm()`의 citation/untrusted evidence context를 `citation_sources_from_context()`가 복원하고 COV_VERIFY가 claim-level coverage를 검증한다. unsupported/unknown/conflict 또는 verifier exception은 validation failure로 남는다. forced-refresh provider availability, 최신성, 다국어 source conflict와 healthy-provider recall은 별도 출시 차단 항목이다.

## 검색 품질 실험

검색 fixture는 질의, 기대 source/domain, graded relevance, freshness window, 허용 citation을 포함한다. 현재 2개 기본 case와 6개 확장 case가 URL canonicalization과 순위 지표를 검증하며, 실행 결과는 다음을 기록한다.

- Precision@K, Recall@K, MRR, nDCG@K
- duplicate ratio, domain diversity, trusted-source ratio
- citation validity, unsupported-claim ratio, unknown citation rate, conflict rate, unacknowledged conflict rate, injection escape rate
- P50/P95/P99 latency, provider error rate, cache hit rate, cost/request

결정론적 fixture 기준선은 Python case P@3 0.667/Recall@3 0.667/MRR 1.000/graded nDCG@3 0.840, local-model case P@3 0.667/Recall@3 0.400/MRR 1.000이다. 2026-08-09 정상 provider live benchmark는 P@3 0.833, Recall@3 0.633, MRR 1.000, nDCG@3 0.883, domain diversity 0.833, provider error 0으로 기록됐으며 SearXNG unavailable에서도 DuckDuckGo 후보 풀과 fallback이 사용됐다. 최신 configured self-hosted provider 2-case run은 `data/benchmarks/live-search.json`에 error_count `0`, P@3 `0.167`, Recall@3 `0.167`, MRR `0.500`, nDCG@3 `0.210`, domain diversity `0.667`을 기록했고, 확장 6-case run은 error_count `0`, P@3 `0.056`, Recall@3 `0.083`, MRR `0.167`, nDCG@3 `0.117`을 기록했다. `make search-load`의 configured self-hosted run은 error_count `0`, P50 `52.2ms`, P95/P99 `1805.8ms`였다. availability는 통과했고 latency budget이 tail을 줄였지만 relevance와 provider variance는 남은 gate다. citation contract는 근거가 맞는 claim, unknown source, unsupported claim을 구분한다.

모델 답변은 문자열 유사도가 아니라 주장 단위로 분해해 source evidence와 비교한다. 검색 evidence가 실행 컨텍스트에 있으면 COV_VERIFY가 citation source를 복원하고 uncited/unsupported claim을 validation failure로 기록한다. live provider 결과는 변동성이 있으므로 deterministic fixture와 별도 report로 보관한다.

`tests/fixtures/claim_grounding_cases.json`은 정상 근거, unsupported/unknown citation, 상충 근거를 인지하지 않은 답변, 상충을 명시한 답변을 각각 검증한다. `ClaimGroundingCase.conflict_sets`는 human-reviewed source pair를 명시하는 입력이며, 자동 evaluator가 source 자체의 진위를 추측하지 않고 충돌을 투명하게 표면화한다.

## 장애/보안 시나리오

- SearXNG/Tavily/Jina/DDG 각각 timeout/5xx/invalid JSON
- 모든 provider 실패 후 fallback query와 부분 결과
- 중복 URL, tracking query, redirect loop, private IP redirect
- robots disallow, rate limit, malformed encoding, PDF/JS-only page
- 악성 웹 문서의 system/tool instruction
- SQLite 중단, duplicate submit, process restart, checkpoint resume
- approval timeout, tool deny, tool execution error, rollback
- Vault 확인 토큰 누락, 선택 경로 이탈/내부 경로, redact/purge commit 실패, 파생 RAG/Wiki rollback, 선택 snapshot restore
- bounded output, memory/process quota, snapshot restore success/failure

## 게이트

1. Unit/integration test와 quality contract는 PR hard gate.
2. Performance benchmark는 지정 threshold 초과 시 hard gate.
3. live web/model smoke는 별도 job이며 실패 원인과 provider availability를 기록한다.
4. 부하/P95 결과가 없으면 상용 readiness를 선언하지 않는다.

## 벤치마크 재현 절차

아래 순서로 실행하면 CI(`.github/workflows/benchmark.yml`)와 동일한 벤치마크를 로컬에서 재현한다.
전제: `uv sync --extra dev --extra rag` 완료, 로컬 Ollama에 `qwen3.6:latest` 로드.

### 1. 로컬 모델 벤치마크 (simple/frontier/verified_code)

```bash
# 기본 simple suite (qwen3.6:latest, 결과: data/benchmarks/local-model.json)
make local-benchmark
# 또는 직접 실행 (모델·suite·반복 지정)
python scripts/run_local_model_benchmark.py \
  --suite frontier --model qwen3.6:latest --repeats 2 \
  --output data/benchmarks/local-model-frontier.json

# frontier suite (Fibonacci/BST/최신 조사/기술 비교/long-horizon recovery 5케이스)
make local-benchmark-frontier

# 코드 실행 검증 suite (verf-001~004: 실행 정확도로 채점)
python scripts/run_local_model_benchmark.py --suite verified_code --repeats 1
```

사용 가능한 suite 이름: `all`, `frontier`, `simple`, `algorithm`, `architecture`, `korean`, `refactor`, `search`, `analysis`, `creative`, `regression`, `long_horizon`, 또는 개별 case id(예: `sim-001`).
`--repeats N`으로 반복 실행 시 case별 평균·최솟값·표준편차·excellent 비율·all-excellent run rate가 JSON에 기록되고, `router.quality_calibration`이 이 artifact를 읽어 routing 후보를 보정한다.

### 2. 성능 회귀 벤치마크 (지연 임계값)

```bash
# pytest benchmark marker 전체
make test-benchmark
# 파이프라인 스테이지별 지연 임계 테스트만
python -m pytest tests/test_benchmark_performance.py -v --tb=short -m "benchmark"
```

CI 임계값(`benchmark.yml` env): `BENCHMARK_THRESHOLD_CONTEXT_ENRICH=500ms`, `BENCHMARK_THRESHOLD_CODE_REVIEW=1000ms`, `BENCHMARK_THRESHOLD_MAX_ENGINE=50ms`. 초과 시 해당 스텝이 실패하고 PR을 막는다.

### 3. 파이프라인 벤치마크 (proactive pipeline)

```bash
# 4개 스테이지(context_enrich/code_review/rag_indexing/max_engine) 반복 측정
python scripts/benchmark_proactive_pipeline.py \
  --iterations 5 --no-warmup --json data/benchmarks/pipeline.json

# 이전 결과와 비교
python scripts/benchmark_proactive_pipeline.py \
  --json data/benchmarks/pipeline.json --compare data/benchmarks/pipeline.prev.json
```

`--skip context_enrich code_review` 등으로 스테이지를 생략할 수 있다. GitHub Actions에서는 PR HEAD와 main 베이스를 각각 측정해 비교한다.

### 4. 시각화 (벤치마크 대시보드)

```bash
python scripts/benchmark_viz.py data/benchmarks/pipeline.json \
  --output-dir docs/benchmark/charts --format png
```

`docs/benchmark/`의 `index.html`·`benchmark_insights_report.md`·PNG 갤러리는 `benchmark.yml` 완료 후 `deploy-benchmark-pages.yml`이 이 스크립트로 재생성해 GitHub Pages에 배포한다.

### 5. 검색 품질·근거 확인 벤치마크

```bash
make search-quality            # 결정론적 golden set + citation 체크
make search-live               # live provider 검색 벤치 (golden set)
make search-live-extended      # 확장 fixture (data/benchmarks/live-search-extended.json)
make search-load               # 반복/동시 부하 지연·가용성 (P50/P95/P99)
make claim-quality             # 결정론적 claim grounding/conflict fixture
make quality-contract          # claim + task/long-horizon 계약 전체
```

### 6. 증폭 A/B 측정

증폭 모드별(cascade/revision/self-consistency/decomposition) A/B 비교는 `docs/AMPLIFICATION_GUIDE.md`의 "A/B 측정 직접 실행" 섹션에 있는 `BenchmarkHarness.compare_amplification()` 스니펫을 그대로 사용한다. 로컬 기준: qwen3.6:latest, `--suite lh-001` 등 개별 case 지정 가능.

### 7. 기준선 재현 확인 방법

- 전체 비벤치마크 기준선: `pytest -q -m 'not benchmark'` — 최신 기록 `3442 passed, 4 skipped` (2026-08-13)
- 벤치마크 결과 artifact는 `data/benchmarks/*.json`에 JSON으로 남으므로, 실행 후 `git diff data/benchmarks/`로 회귀 여부를 바로 확인할 수 있다.
