# 09 Operation Guide

기준일: 2026-08-17

## 설치

지원 기준은 macOS Apple Silicon, Python 3.12+다. 프로젝트 정책과 실제 dependency lock이 완전히 정렬되기 전까지 신규 환경에서는 `.venv`와 optional extra를 명시한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,rag]"
```

## 설정

- 기본 모델: `config.yaml`의 `model.main_model` 및 `code_model` = `qwen3.8:latest` (DOC-01 실측 동기화 — 구버전 문서의 `qwen3.6` 표기는 config.yaml과 불일치).
- 기본 inference engine: Ollama.
- LM Studio: `lmstudio/qwen3.6` 프로필을 선택한다. Local Server에서 API 토큰을 활성화한 경우에만 `LM_STUDIO_API_KEY`를 설정한다. `repo` 값은 LM Studio `/v1/models`가 노출하는 실제 model identifier와 같아야 한다.
- Direct MLX: `uv sync --extra mlx --extra dev` 후 `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` 프로필을 선택한다. 가중치를 미리 받으려면 `uv run hf download mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`를 실행한다. 기본 Qwen/Ollama 설정은 바꾸지 않는다. MLX 프로필은 mflux 0.19 계열과 공존할 수 있도록 `mlx>=0.32,<0.33`으로 고정한다.
- 로컬 FLUX 이미지 생성(`generate_image`)까지 사용할 때는 `uv sync --extra mlx --extra mlx-media --extra dev`를 사용한다. `mflux`는 0.19 계열로 맞춰야 MLX 0.32 계열과 의존성이 정렬된다.
- remote provider key는 `.env`에만 두고 저장소/로그에 기록하지 않는다.
- `SEARXNG_URL`, `TAVILY_API_KEY`, `JINA_API_KEY`, `AGK_SEARCH_ENGINE_URL`은 선택적 검색 설정이다.
- `AGK_SEARCH_FALLBACK_BUDGET_MS`는 self-hosted primary가 느릴 때 추가 query fan-out을 생략하는 latency budget이며 기본값은 `1500`이다.
- permission, cost, hourly action limit, native function calling 설정을 운영 환경에 맞게 확인한다.

## 프로젝트 메모리

- 프로젝트 결정과 일반 사실, episodic turn, Cavemem DB는 현재 workspace의 `.antigravity/memory/` 아래에 저장된다. 사용자 전역 선호와 identity는 기존 global memory에 남는다.
- `이 프로젝트에서는 데이터베이스로 PostgreSQL을 사용하기로 했어`처럼 명시적인 기술 결정을 말하면 지원되는 key로 정규화한다.
- 임의 key는 `프로젝트 결정: deployment=kubernetes` 또는 `프로젝트 사실: python_version=3.13` 형식으로 기록한다. 같은 kind/key를 다시 지정하면 최신값 하나만 남는다.
- `db`/`dbms`/`db_engine`/`database_engine`과 framework/package/deployment의 보편적 별칭은 canonical key로 자동 통합한다. legacy 파일에 여러 별칭이 있으면 관측 시각이 가장 최신인 값만 남는다.
- 팀 고유 용어는 `uv run agk memory alias-set database primary_store`로 canonical key에 연결한다. `uv run agk memory aliases`는 현재 프로젝트 설정을 표시하고 `uv run agk memory alias-remove primary_store`는 연결을 제거한다.
- 사용자 별칭은 `.antigravity/memory/project_aliases.json`에 `{"aliases":{"database":["primary_store"]}}` 형태로 저장된다. snake_case만 허용하며 중복 alias, 내장 key 재정의, alias chain, 잘못된 JSON, workspace 밖 symlink는 fail-closed한다.
- “현재 프로젝트 데이터베이스 결정이 뭐야?” 같은 단일 read-only 조회는 저장된 authoritative 값을 로컬 모델에 직접 전달해 불필요한 파일·Git 도구 호출을 피한다. 변경, 검색, 구현, migration 요청은 항상 일반 agent loop를 사용한다.
- memory API의 scope에는 `project`를 사용할 수 있다. export/redact/retention/purge는 해당 workspace의 project provider에만 적용되고 global identity 및 다른 workspace는 변경하지 않는다.
- project purge는 memory 값만 삭제하고 별칭 설정은 보존한다. 별칭은 provider 시작 시 불변 snapshot으로 읽으므로 실행 중인 agent/API에는 재시작 후 적용된다.
- 실행 중인 API process의 memory manager는 최초 workspace에 고정된다. 다른 workspace로 전환하려면 process를 분리하거나 재시작한다.

## 장기 컨텍스트

- 모델 profile의 context length와 `router.context_token_limit` 중 더 작은 운영 한도에서 응답 reserve를 제외한 budget을 사용한다. Qwen3.6의 기본 agent 입력 상한은 `32768` estimated tokens다.
- trajectory 압축 뒤에도 초과하면 `ContextCompressor`가 최종 hard budget을 적용한다. 긴 메시지는 가운데를 생략하고 head/tail을 보존하며 최신 사용자 목표, system context, structured tool provenance를 우선한다.
- 압축 안내는 trajectory가 실제 메시지를 줄였을 때만 출력된다. `Context Compressor` 안내의 전후 percentage가 100%를 넘긴 채 유지되면 provider profile/context 설정과 로그를 확인한다.
- canonical background와 direct interactive task는 versioned snapshot을 같은 SQLite task execution ledger에 저장한다. process restart/checkpoint resume는 동일 task ID의 최신 valid snapshot만 `[Restored Task Context]`로 재주입하며 `system`/`developer`/`user`/`assistant`/도구 역할을 보존한다.
- `[Recalled Memory]`와 이전 restore header는 snapshot에 재영속하지 않고, 손상된 최신 snapshot은 오래된 snapshot으로 자동 fallback하지 않는다. 복원 누락 시 `context_snapshot` execution event와 JSON version을 확인한다.
- `agk run`과 SSE가 반환한 `direct_*` ID는 `agk task status|output|resume <task_id>`로 조회·재개할 수 있다. `resume`은 완료까지 기다려 누적 출력을 표시하며 실패 또는 제한 시간 초과 시 0이 아닌 코드로 종료한다.
- CLI/SSE 화면은 품질 개선 과정(초안→revision)을 그대로 보여줄 수 있지만, direct task record는 최종 agent output만 저장한다. 조회·재개 소비자는 초안 노이즈 없이 최종 답을 받는다.
- Auto code review는 현재 턴에서 mutating tool을 실제로 사용했을 때만 workspace diff를 평가한다. 읽기 전용 코드 질문에 기존 dirty worktree 내역이 노출되지 않는다.
- API는 `GET /api/tasks/{task_id}/status`, `GET /api/tasks/{task_id}/output`, `POST /api/tasks/{task_id}/resume`을 제공한다. 여러 프로세스나 격리 QA에서 같은 저장소를 선택하려면 `AGK_TASK_DB_PATH=/path/to/tasks.db`를 동일하게 설정한다.

## 실행/검증

```bash
# 기본 포트는 8400 (config server.port, AGK_SERVER_PORT로 변경 가능)
uv run agk serve --host 127.0.0.1 --port 8400
curl -fsS http://127.0.0.1:8400/health
curl -fsS http://127.0.0.1:8400/openapi.json
make quality-contract
```

Ollama local smoke:

```bash
ollama list
ollama run qwen3.8:latest
```

로컬 RAG 검색 품질을 측정할 때는 기본적으로 fixture가 참조하는 엔진 코드만 인덱싱해 초기 임베딩 시간을 제한한다. 더 넓은 범위가 필요하면 `--subdir`를 반복 지정한다.

```bash
python scripts/benchmark_local_rag.py --output /tmp/local-rag-quality.json
python scripts/benchmark_local_rag.py --subdir src --subdir docs --output /tmp/local-rag-wide.json
```

검색 provider live smoke를 실행할 때는 선택적 self-hosted endpoint를 명시한다.

```bash
AGK_SEARCH_ENGINE_URL=https://main.search-engine-api.pages.dev make search-live
AGK_SEARCH_ENGINE_URL=https://main.search-engine-api.pages.dev make search-live-extended
AGK_SEARCH_ENGINE_URL=https://main.search-engine-api.pages.dev make search-load
```

## 운영 관측

- task id, checkpoint, outcome, tool permission decision, provider/model, latency, token, cost를 추적한다.
- 활성화된 model policy가 cap/floor 때문에 후보를 제외하는 것은 예상 동작이므로 debug 로그로 기록한다. warning은 calibration 미달이나 라우팅 실패처럼 조사가 필요한 사건에 남는다.
- `/health`는 liveness, 깊은 provider/RAG 상태는 별도 readiness probe로 분리한다.
- 로그에는 API key, cookie, Authorization, 개인 메모리 원문을 남기지 않는다.
- provider 장애는 local fallback과 부분 결과 정책으로 격리한다.


## 컨텍스트 압축 실패·예산 headroom 경보 (CTX-03)

- 압축 시도 실패율(`context.compress.degraded` + `context.compress.halted` / 전체 compress attempt)이 **5%** (`ALERT_COMPRESS_FAILURE_RATE=0.05`)를 넘으면 조사한다.
- 최종 프롬프트 input headroom이 **15% 미만** (`ALERT_BUDGET_HEADROOM_PCT=15`)이면 경고한다. headroom = `(input_budget - input_total) / input_budget`.
- 이벤트 타입: `context.compress.succeeded` / `context.compress.degraded` / `context.compress.halted`. payload에 component tokens before/after, strategy, digest, elapsed_ms, failure_code가 포함된다.
- **정책:** 압축 실패 + hard-limit 미만 → 제한적 degrade(읽기/계속 허용). 압축 실패(또는 fit 실패) + hard-limit 초과 → halt(모델 호출·mutation 중단). catch-all fail-open으로 over-limit prompt를 provider에 보내지 않는다.

## 장애 대응

1. `/health`와 server log에서 import/provider 상태를 확인한다.
2. TaskStateStore에서 마지막 checkpoint와 transition을 확인한다.
3. approval/prompt/tool deny는 정책 결과인지 provider 오류인지 분리한다.
4. 재시작은 idempotency key와 checkpoint 이후부터 수행한다.
5. cache/vector/Vault 변경 전 백업하고, rollback은 Git/Vault/worktree 계약을 따른다.

## OBS-01 · SLO·경보·재해 복구 runbook

### operation correlation (구조화 로그)

- 모든 HTTP 요청은 `X-Request-Id`를 상관 id로 받아(없으면 생성) 로그에 남긴다.
- `antigravity_k.ops` 로거의 `http.request.started` / `http.request.completed` /
  `http.request.failed` 이벤트가 method/path/status/latency_ms/correlation_id를
  JSON 한 줄로 기록한다. 실행 컨텍스트가 바인딩되면 project_id/task_id/
  conversation_id/session_id/model_id가 같은 줄에 주입되어 한 operation의
  project→task→tool→model 흐름을 추적할 수 있다.
- `log_operation_event(event, outcome=..., **fields)`로 도메인 이벤트도 동일
  포맷으로 남긴다 (JSONFormatter 활용).

### 핵심 운영 metric (Prometheus `/metrics`)

| metric | outcome 값 | 수집 지점 |
|---|---|---|
| `ssak_context_compactions_total` | success/degraded/halted/error | conversation_store.compact |
| `ssak_auth_events_total` | success/failed/lockout | auth_routes 로그인·토큰 교환 |
| `ssak_registry_writes_total` | success/save_error/lock_timeout | project_registry 저장 |
| `ssak_vault_commits_total` | success/commit_error | vault _auto_commit |
| `ssak_task_transition_conflicts_total` | conflict/rejected | task_state_store CAS |
| `ssak_provider_failures_total` | timeout/error | model_manager 추론 실패 |

기존 RED 계열(`http_requests_total`, `http_request_duration_seconds`)과
LLM 계열(`llm_calls_total`)은 그대로 유지된다.

### readiness probe (`GET /api/ready`, 공개)

- 검사 항목: `task_db`(SQLite 접근), `registry`(활성 프로젝트),
  `writable_storage`(프로젝트 루트 쓰기 probe), `model_manager`(로드 모델).
- 집계: not_ready ≥1 → `not_ready` + **HTTP 503**, degraded만 있으면
  `degraded` + 200, 전부 ready면 `ready` + 200.
- 개별 검사 실패는 다른 검사에 오염되지 않는다 (격리 실행).
- liveness는 기존 `/health`를 그대로 사용한다.

### SLO와 경보 (owner: 운영 담당자, first-response: 해당 runbook 절차)

| 지표 | SLO | 경보 임계 | runbook 절차 |
|---|---|---|---|
| API 가용성 (readiness 200) | 월 99.5% | `/api/ready` 503 2회 연속 | 아래 ① |
| HTTP 5xx 비율 | < 1% (5분 창) | 1% 초과 5분 지속 | 아래 ② |
| auth lockout 급증 | < 5/min 정상 | `ssak_auth_events_total{outcome="lockout"}` 증가율 5/min 초과 | 아래 ③ |
| 압축 실패율 (CTX-03) | < 5% | `ssak_context_compactions_total` degraded+halted 비율 5% 초과 | 아래 ④ |
| task CAS 충돌 | 정보성 | `conflict` 증가율 10/min 초과 | 아래 ⑤ |
| provider 실패 | 정보성 | `ssak_provider_failures_total{outcome="timeout"}` 3회/5min | 아래 ⑥ |

1. **readiness 503** — `/api/ready` JSON의 checks[].detail에서 실패 컴포넌트를
   확인한다. task_db면 아래 DR 리허설의 DB corruption 절차, registry면 backup
   복구 절차, storage면 디스크/권한을 확인한다.
2. **5xx 급증** — `http.request.failed` 로그의 error_code 분포를 확인하고
   최근 배포/설정 변경을 롤백 검토한다.
3. **lockout 급증** — `get_auth_audit_events()`로 원격 IP 분포를 확인한다.
   단일 IP 다수 실패는 lockout이 정상 동작 중인 것이므로 방화벽 차단을 검토하고,
   분산 다수면 credential 노출/무차별 공격을 가정하고 PIN을 교체한다.
4. **압축 실패율 초과** — `context.compress.*` 이벤트의 failure_code를 모아
   근본 원인(모델 컨텍스트 설정, summarize_fn 실패)을 확인한다.
5. **CAS 충돌 급증** — 같은 task에 다중 worker가 붙었는지 확인한다.
   충돌은 정합성 보호 동작이므로 데이터 조치는 불필요하다.
6. **provider timeout** — 로컬 모델 프로세스(Ollama 등) 상태와 하드웨어
   자원을 확인하고, 콤보 폴백이 정상 동작했는지 `llm_calls_total`로 검증한다.

### 재해 복구 리허설

```bash
uv run --no-sync python scripts/dr_rehearsal.py --output /tmp/dr-rehearsal.json
```

3개 시나리오를 임시 디렉터리에서 실측한다 (프로덕션 데이터 무변경):

1. **backup_restore** — `data/projects.json` 파손 → `.bak`에서 자동 복구,
   손상본은 `.corrupt-<ts>`로 격리 보존.
2. **db_corruption** — task DB SQLite header 파손 → 감지 후 격리(quarantine)
   + 재초기화 + 재기록 검증.
3. **project_migration** — 프로젝트 루트 실제 이동 → registry id 재활성 →
   remove+add로 path 갱신 → 활성 프로젝트 전환 확인.

실제 장애 시 절차: (a) 손상 파일을 quarantine 디렉터리로 이동 (삭제 금지),
(b) 백업이 있으면 복구, 없으면 재초기화, (c) `/api/ready` 200 확인.

## 관리자 runbook — 업그레이드/롤백

### 업그레이드

1. **사전 백업**: 서버 정지 → `data/` 전체(특히 `projects.json`, `.bak`,
   `tasks.db`, `auth_hash`, `token_secret`)와 활성 workspace의
   `.antigravity/`를 백업한다. Vault는 Git 원격에 push 상태를 확인한다.
2. **코드 교체**: `git fetch && git checkout <candidate-SHA>` →
   `uv sync --frozen`(또는 extra 포함 `uv sync --extra dev --extra rag --extra mlx`)
   → `uv run agk doctor`로 14개 진단 통과를 확인한다.
3. **가동**: `uv run agk serve` 후 `/health`(liveness)와 `/api/ready`(readiness,
   task DB/registry/storage/model)가 모두 200인지 확인한다.

### 롤백

1. 서버 정지 → 이전 `data/` 백업 복원 (`projects.json` 파손 시 `.bak` 자동 복구,
   `tasks.db` 파손 시 quarantine 후 재초기화 — 위 DR 리허설 절차와 동일).
2. `git checkout <이전 candidate-SHA>` → `uv sync --frozen` → doctor → 가동 확인.
3. 롤백 후에도 Vault 커밋은 Git 이력으로 보존된다 — 강제 reset 금지,
   `git revert`로만 되돌린다.

## 관리자 runbook — 인증(auth) 운영

### PIN 설정/교체 (auth reset)

1. PIN은 `AGK_SEC_ACCESS_PIN` 환경변수로 부트스트랩한다. 서버 기동 시 최초 1회
   PBKDF2-SHA256으로 해시화되어 `AGK_SEC_PIN_HASH_FILE`(기본 `data/auth_hash`,
   권한 0600)에 저장되며, 이후 plaintext PIN은 저장되지 않는다.
2. **PIN 교체**: 서버 정지 → `data/auth_hash` 삭제(또는 `AGK_SEC_PIN_HASH_FILE`
   경로 변경) → 새 `AGK_SEC_ACCESS_PIN`으로 재기동. 재기동 즉시 새 PIN으로
   `/api/auth/login`해 발급된 Bearer token(기본 12시간)만 유효하다.
3. credential이 존재하면 loopback 개발 환경에서도 보호 상태다(SEC-01 fail-closed).
   익명 허용은 `AGK_SEC_DEV_NO_PIN_ALLOW=true`(dev, 명시 설정)일 때만 가능하며
   `AGK_ENV=production`에서는 절대 허용되지 않는다.
4. 로그인 실패 제한(SEC-02): IP/계정 기준 burst 5회/분, sustained 20회/600초
   초과 시 300초 lockout(403). lockout 급증 시 ⑶ runbook의 credential 유출
   점검 절차를 따른다.

### WebSocket 접속 정책 (SEC-03)

- WS 연결은 query `?token=`/subprotocol credential 채널을 지원하지 않는다.
- 클라이언트는 ① `POST /api/auth/ws-ticket`(Bearer 인증)으로 30초 수명 1회용
  ticket을 발급받고 ② `Origin`이 `AGK_CORS_ORIGINS` 허용 목록에 포함된 상태로
  `ticket`을 handshake에 전달한다(헤더 또는 지정 채널). 재사용·만료 ticket,
  허용 목록 밖 Origin은 거절된다.
- 정상 reconnect는 새 ticket 발급으로 수행한다. 이벤트 replay는 ticket 소비 후
  정상 세션에서 `after_sequence` 커서로 이어받는다.

## 현재 운영 제한

DNS-aware SSRF, robots policy, load test가 완료되지 않았으므로 공개 인터넷 대상 상용 운영을 승인하지 않는다. (alerting rehearsal과 backup restore는 OBS-01에서 리허설 완료 — 위 재해 복구 리허설 절차 참조)
