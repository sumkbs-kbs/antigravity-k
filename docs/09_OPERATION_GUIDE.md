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

- 기본 모델: `config.yaml`의 `model.main_model` 및 `code_model` = `qwen3.6:latest`.
- 기본 inference engine: Ollama.
- LM Studio: `lmstudio/qwen3.6` 프로필을 선택한다. Local Server에서 API 토큰을 활성화한 경우에만 `LM_STUDIO_API_KEY`를 설정한다. `repo` 값은 LM Studio `/v1/models`가 노출하는 실제 model identifier와 같아야 한다.
- Direct MLX: `uv sync --extra mlx --extra dev` 후 `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` 프로필을 선택한다. 가중치를 미리 받으려면 `uv run hf download mlx-community/Qwen2.5-Coder-32B-Instruct-4bit`를 실행한다. 기본 Qwen/Ollama 설정은 바꾸지 않는다.
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
uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 8000
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/openapi.json
make quality-contract
```

Ollama local smoke:

```bash
ollama list
ollama run qwen3.6:latest
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

## 장애 대응

1. `/health`와 server log에서 import/provider 상태를 확인한다.
2. TaskStateStore에서 마지막 checkpoint와 transition을 확인한다.
3. approval/prompt/tool deny는 정책 결과인지 provider 오류인지 분리한다.
4. 재시작은 idempotency key와 checkpoint 이후부터 수행한다.
5. cache/vector/Vault 변경 전 백업하고, rollback은 Git/Vault/worktree 계약을 따른다.

## 현재 운영 제한

DNS-aware SSRF, robots policy, alerting rehearsal, backup restore, load test가 완료되지 않았으므로 공개 인터넷 대상 상용 운영을 승인하지 않는다.
