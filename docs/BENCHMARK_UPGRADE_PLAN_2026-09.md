---
title: 외부 레포 벤치마킹 기반 업그레이드 개발 계획서 (2026-09-04)
tags: [benchmark, upgrade, plan, checklist, handover]
sources:
  - https://github.com/CodebuffAI/freebuff
  - https://github.com/unslothai/unsloth
date: 2026-09-04
last_verified: 2026-09-05
status: in-progress
owner: Buffy (Codebuff agent) — 타 에이전트 인수인계 가능하도록 작성
baseline: backend 5280 passed / 13 skipped / 0 failed · frontend vitest 698 passed (63 files) / tsc clean
---

# 외부 레포 벤치마킹 기반 업그레이드 개발 계획서

## ⭐ 인수인계 요약 — 다음 에이전트는 여기서 시작 (2026-09-05 기준)

> **한 줄**: HEAD `460d712`(`codex/m1-task-events`)의 **working tree 전체가 검증된
> known-good 상태**다. 커밋 안 된 파일을 "정리"한다고 되돌리면 검증 상태가 깨진다.

### ✅ 검증된 기준선 (baseline)

2026-09-05에 현재 working tree 기준으로 직접 재실행해 확인한 값:

| 영역 | 명령 | 결과 |
|:---|:---|:---|
| 백엔드 전체 | `uv run --no-sync pytest tests/ -q` | **5280 passed, 13 skipped, 0 failed** |
| 프론트 전체 | `cd dashboard && npx vitest run` | **698 passed (63 files)** |
| 프론트 타입 | `cd dashboard && npx tsc --noEmit` | **clean** |
| 느린 E2E (온디맨드) | `uv run --no-sync pytest -m slow` | 4 passed (기본 스위트에서 제외됨) |
| 드리프트 가드 | `uv run --no-sync pytest tests/test_mlx_command_flags.py tests/test_unsloth_script_api_drift.py` | mlx 4 + unsloth 7(설치 환경 한정) 통과 |

13 skipped는 전부 정상 가드다 (unsloth/trl 미설치 환경 스킵, e2e 마커 등). 실패가 아니다.

### ⚠️ working tree 상태 — 반드시 읽고 시작할 것

- `git status`에 **764개 변경 경로**가 보인다. 구성은 세 부류다:
  1. **본 계획서의 벤치마킹 업그레이드 산출물** (`src/antigravity_k/engine|api|cli`, `tests/`,
     `dashboard/src`, `docs/`, `scripts/`, 워크플로) — 위 기준선이 이 상태를 검증한 것이다.
     Phase 27 조정 파일(`path_security.py`, `git_api.py`, `filesystem.py`)과 이를 잠그는
     `tests/test_path_contracts.py`는 **반드시 함께 커밋**할 것.
  2. **타 에이전트의 리브랜드 대대적 변경** (`.agent/`, 루트 문서, `config.yaml.example` 등
     Antigravity-K→Ssak-Ai 명칭 교체) — 본 계획서 소관 아님. 커밋 시 분리할 것.
  3. `dashboard/.stryker-tmp/` 삭제 (빌드 산물 청소) — 무해.
- **`stash@{0}`이 이미 존재**한다(다른 스레드 WIP). pop/적용 금지. Phase 45에서 확인한 바로는
  `node_modules` 심볼릭 링크 문제로 pop이 깨질 수 있다.
- §3 파일 매니페스트는 Phase ~39까지의 요약이고 **전체 목록이 아니다**. 권위 있는 목록은 `git status`다.

### 🔁 기준선 재확인 레시피 (작업 시작/종료 시)

```bash
uv run --no-sync pytest tests/ -q                 # 백엔드: 5280 passed 기대
cd dashboard && npx vitest run 2>&1 | tail -3     # 프론트: 698 passed 기대
npx tsc --noEmit                                   # (dashboard 디렉터리에서)
uv run --no-sync pytest -m slow -q                 # 느린 E2E 4건 (필요시)
```

기준선에서 벗어나면: 실패 목록 → §5/§4 최근 로그 → 해당 Phase 인수인계 노트 순으로 대조.

### 🧨 축적된 환경 함정 (위반 시 실제로 깨짐 — 전부 실측)

1. pytest는 항상 `uv run --no-sync`로 실행 — sync가 잠금 환경을 뒤집어 드리프트 테스트가
   오검출될 수 있다 (Phase 54).
2. subprocess 기반 테스트는 `tests/_cli_subprocess.py` 헬퍼 사용. `sys.executable` 직접 사용 금지
   — 외부 인터프리터(miniforge)에서 모듈 미설치로 실패한다 (Phase 12/55). CI의 mlx 매트릭스와
   주간 드리프트 job은 `AGK_TEST_PYTHON=$GITHUB_WORKSPACE/.venv/bin/python`을 설정해 드리프트
   체크와 스모크 테스트가 같은 고정 인터프리터를 공유한다 (Phase 57).
3. `prompts/`(루트)이 소스, `src/antigravity_k/prompts/`는 패키지 파생 사본. 루트만 고치고
   동기화할 것 — wheel-assets 테스트가 바이트 일치를 강제한다 (Phase 55).
4. `config.yaml`은 번들 기본값과 일치해야 한다. 라이브 테스트용 예산 변경은 끝나면 복구
   (`git checkout -- config.yaml`) — bundled-default 테스트가 잠근다 (Phase 52/55).
5. `pyproject.toml`에 unsloth extra를 **추가하지 말 것** — finetune extra(datasets>=5)와
   충돌해 `uv sync` 자체가 깨진다. 주간 드리프트 job이 `uv pip install`로 직접 설치한다 (Phase 54).
6. `resolve_unsloth_settings`의 `allow_default_endpoint` 기본값(True) 유지 — 런타임 어댑터는
   127.0.0.1:8080 폴백이 정상, 프로브만 False를 쓴다 (Phase 55).
7. 전역 싱글턴(`get_project_registry` 등) 테스트에서는 전역 객체가 아니라 **소스 속성을
   패치**할 것 — 테스트 간 오염이 생긴다 (Phase 56).
8. 양자화 품질 쌍둥이(`quantQuality.ts` ↔ `quant_quality.py`)는
   `tests/fixtures/quant_quality_conformance.json`으로 잠겨 있다. 토큰 추가는 fixture 먼저 (Phase 46).

### 📍 현재 위치와 다음 할 일

- 완료: Phase 0–56 (전부 §4 로그 + §5 기록). 최근: 53/54 unsloth·mlx 드리프트 가드+주간 CI,
  55 전체 스위트 제로 실패, 56 경로 보안 계약 고정(뮤테이션 7/7 검증).
- 미완료: §6 P3 목록 참조. 추천 우선순위: (1) 누적 변경물의 **논리적 커밋 분할** — 기준선이
  커밋으로 고정되지 않으면 다시 유실될 수 있다, (2) egress/vault 등 남은 보안면에 Phase 56의
  계약-고정+뮤테이션 패턴 적용, (3) nightly 전체 스위트 CI.

---

## 0. 목적

`CodebuffAI/freebuff`(멀티 에이전트 코딩 에이전트)와 `unslothai/unsloth`(로컬 모델 실행·학습 데스크톱) 두 레포의
**구동 방식 / 알고리즘 / 코어 / 기능**을 벤치마킹하여, Ssak-Ai에 이식 가능한 개선점을 추출하고
본 프로그램 구조에 맞게 구현한다. 모든 단계는 체크리스트 + 테스트 + 진행 로그로 추적한다.

---

## 1. 벤치마킹 분석 요약

### 1.1 freebuff (CodebuffAI) — 구동 방식·코어

| 영역 | freebuff 방식 | Ssak-Ai 현황 | Gap 평가 |
|:---|:---|:---|:---|
| 멀티 에이전트 오케스트레이션 | 전문화 에이전트 분업: 컨텍스트 수집 → 계획 → 구현/편집 → 도구 실행 → 리뷰. 단일 모델+단일 프롬프트 사용 안 함 | orchestrator 상태그래프 + MoE swarm 존재 | ✅ 유사. 개선 여지 낮음 |
| 병렬 로컬 에이전트 | Desktop이 동시 에이전트를 **격리 worktree**에서 구동 | `worktree_manager.py` + `multiplexer.py` 존재 | ✅ 이미 보유 |
| 에이전트 연결 (브리지) | `unsloth start claude/codex/...`식 **원커맨드 브리지** + OpenAI/Anthropic 호환 API로 외부 에이전트 연결 | Anthropic Messages API **요청 수신 엔드포인트 없음** (`/v1/chat/completions`만 존재) | ⚠️ **P0 Gap** |
| 모델 카탈로그 | 큐레이션 카탈로그 + 양자화(Q8_0) 서빙 명시 | 모델 레지스트리 존재하나 **양자화 유형 인식 약함** | ⚠️ **P1 Gap** |
| 데이터 사용/세션 제한 고지 | 세션 한도·데이터 사용 고지를 시작 전 표시 | cost_guard 존재, 고지 UX 없음 | 🔵 P3 (UX) |

### 1.2 unsloth (unslothai) — 구동 방식·코어·알고리즘

| 영역 | unsloth 방식 | Ssak-Ai 현황 | Gap 평가 |
|:---|:---|:---|:---|
| GGUF 양자화 알고리즘 | **Dynamic GGUF** — 레이어별 혼합 정밀도(UD-Q4_K_XL 등)로 크기 -83% & 정확도 ~81% 유지. 모델명에 양자정보 인코딩 | 디스커버리가 GGUF 파일명에서 양자 토큰 **파싱 안 함** → 라우팅 품질 판단 불가 | ⚠️ **P1 Gap** |
| 원커맨드 에이전트 연결 | `unsloth start claude --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` — OpenAI/Anthropic 호환 API로 Claude Code/Codex 등 연결 | 없음 | ⚠️ **P0 Gap** (freebuff와 동일 결론) |
| 오픈 표준 API 서빙 | OpenAI 호환 + **Anthropic 호환** API 동시 제공, tool calling 포함 | OpenAI 호환만 제공 | ⚠️ **P0 Gap** |
| 자가 복구 | Studio "self-healing" 런타임 | `self_healing_doctor.py` 존재 | ✅ 유사 |
| 롤링 컨텍스트 | auto-compaction(롤링 컨텍스트 윈도우) + RAG + 검색 | `adaptive_context_compaction.py` 존재 | ✅ 이미 보유 |
| 원격 접근 보안 | Cloudflare HTTPS/LAN, `--disable-tools` 원칙 | egress_policy + PIN 존재 | ✅ 유사 |
| 학습 파이프라인 | LoRA/QLoRA/GRPO/DPO, 데이터 레시피, GGUF 내보내기 | `unsloth_training*.py` + `lora_pipeline.py` 부분 존재 | 🔵 P3 (이미 자체 구현) |

### 1.3 업그레이드 우선순위 결론

두 레포의 공통 핵심은 **"로컬 모델을 표준 프로토콜(OpenAI/Anthropic 호환 API)로 서빙하여 외부 에이전트를 원커맨드로 연결"** 하는 것이다.
Ssak-Ai는 로컬 모델 오케스트레이션은 강하지만 외부 표준 에이전트 생태계와의 연결 규격이 없다. 이것이 최우선 개선점(P0)이고,
두 번째는 **양자화 인식 모델 메타데이터**(unsloth Dynamic GGUF 방식)로 라우팅 품질을 높이는 것이다(P1).

| 우선순위 | 개선 항목 | 벤치마킹 출처 | 반영 범위 |
|:---:|:---|:---|:---|
| **P0** | Anthropic Messages 호환 `/v1/messages` 엔드포인트 (스트리밍 SSE 포함) | unsloth API 서빙 + freebuff 에이전트 연결 | 신규 라우트 + protocol_translator 재사용 |
| **P0** | `agk start <agent>` 원커맨드 브리지 (openai/anthropic 호환) | `unsloth start claude/codex` | CLI 신규 명령 |
| **P1** | GGUF 파일명 양자화 파싱 → `quantization` 메타데이터 채움 | unsloth Dynamic GGUF 네이밍 규약 | `local_model_discovery.py` |
| **P1** | 양자화 기반 라우팅 메타데이터 노출 (`/v1/models` enriched) | unsloth 모델 카탈로그 | `models_api.py` |
| P3 | 세션/데이터 고지 UX, 학습 레시피 고도화 | freebuff 고지, unsloth Data Recipes | 후속 작업 (미구현) |

---

## 2. 상세 개발 계획 + 체크리스트

### Phase 0 — 계획 수립 (이 문서)

- [x] freebuff 레포 구동 방식 조사 (README, 멀티 에이전트 구조)
- [x] unsloth 레포 구동 방식 조사 (README, Dynamic GGUF, start 브리지)
- [x] Ssak-Ai 코어 구조 파악 (engine 270+ 모듈, api/routes, cli)
- [x] Gap 분석 및 우선순위 결정 (P0/P1/P3)
- [x] 본 계획서 작성

### Phase 1 — Anthropic Messages 호환 API (P0)

**목표**: Claude Code, Codex, freebuff 스타일 에이전트가 Ssak-Ai 로컬 모델을 Anthropic 프로토콜로 호출 가능하게 한다.

**설계 원칙**: 기존 `ProtocolTranslator`의 Anthropic 변환기(translate_request/detect_format)를 재사용하고,
`chat.py`의 검증·세션·인젝션 가드 흐름을 따른다. 새 엔진 로직을 만들지 않는다.

- [x] 1.1 `api/routes/messages_api.py` 신규 생성
  - [x] `POST /v1/messages` — Anthropic Messages 포맷 수신
  - [x] `anthropic_version` 헤더/바디 검증 (누락 시 400)
  - [x] `model` 필수 검증, `messages` 비어있음 검증
  - [x] `system` 문자열/블록 배열 양쪽 수용
  - [x] 응답: Anthropic 포맷 (`content[].{type:text}`, `stop_reason`, `usage.{input_tokens,output_tokens}`)
  - [x] `stream: true` → SSE `message_start` / `content_block_start` / `content_block_delta` / `content_block_stop` / `message_delta` / `message_stop` 이벤트
  - [x] 내부 호출은 기존 ModelManager generate 경로 재사용
  - [x] PromptInjectionGuard 적용 (기존 /v1/chat/completions와 동일 방어)
- [x] 1.2 `server.py`에 라우터 등록
- [x] 1.3 `tests/test_messages_api.py` — FastAPI TestClient 기반
  - [x] 비스트리밍 요청/응답 포맷 검증
  - [x] 스트리밍 SSE 이벤트 시퀀스 검증
  - [x] system 블록 배열 수용
  - [x] model 누락 → 400
  - [x] messages 누락 → 400
  - [x] 잘못된 JSON → 400
- [x] 1.4 테스트 실행 기록 (§4 로그)

### Phase 2 — GGUF 양자화 인식 디스커버리 (P1)

**목표**: unsloth Dynamic GGUF 네이밍 규약(`:UD-Q4_K_XL`, `Q4_K_M`, `Q8_0`, `IQ4_XS` 등)을 파싱해
모델 레지스트리의 `quantization` 메타데이터를 채우고, 라우팅/대시보드가 양자화 품질을 알 수 있게 한다.

- [x] 2.1 `local_model_discovery.py`에 양자화 파서 추가
  - [x] `_QUANT_TOKEN_RE` 정규식: `(?:UD-)?[QI]\d[_A-Za-z0-9]*` 계열 (Q4_K_M, Q8_0, IQ4_XS, UD-Q4_K_XL, Q2_K, Q5_K_S, Q6_K, Q3_K_L…)
  - [x] 파일명/디렉터리명에서 추출, Ollama `details.quantization_level`보다 구체적이면 덮어씀
  - [x] 파싱 실패 시 기존 동작 유지 (graceful)
- [x] 2.2 `DiscoveredLocalModel.quantization` 채움 로직 연결
- [x] 2.3 `/v1/models` + `/api/models/local`에 quantization 노출 (이미 routing_metadata 경로 확인)
- [x] 2.4 `tests/test_quantization_discovery.py`
  - [x] unsloth Dynamic GGUF 파일명 → `UD-Q4_K_XL` 추출
  - [x] 표준 Q4_K_M / Q8_0 / IQ4_XS 추출
  - [x] 양자 토큰 없는 파일 → 빈 문자열 유지
  - [x] 대소문자 혼용 (`q4_k_m`) 정규화
- [x] 2.5 테스트 실행 기록 (§4 로그)

### Phase 3 — `agk start` 원커맨드 브리지 (P0)

**목표**: `agk start claude --model qwen3.8` 처럼 외부 CLI 에이전트에게 Ssak-Ai API를
OpenAI 또는 Anthropic 호환 엔드포인트로 연결하는 환경을 한 번에 세팅한다.

- [x] 3.1 `engine/agent_bridges.py` 신규 — 브리지 스펙 테이블
  - [x] claude / codex / opencode / openclaw / hermes 지원 (unsloth start와 동일 에이전트 집합)
  - [x] 각 에이전트별 프로토콜 결정: claude → anthropic(`/v1/messages`), codex → openai(`/v1/chat/completions`)
  - [x] 각 에이전트별 환경변수 매핑 (ANTHROPIC_BASE_URL, OPENAI_BASE_URL, ANTHROPIC_API_KEY 등)
  - [x] 모델명 없으면 기본 라우팅 모델 자동 선택
- [x] 3.2 `cli.py`에 `agk start` 명령 추가 (서브티퍼 없이 단일 명령)
  - [x] `agk start <agent> --model <name>`
  - [x] API 서버 미기동 시 안내 + `agk serve` 힌트
  - [x] 출력: 프로토콜/엔드포인트/환경변수 export 안내
- [x] 3.3 `tests/test_agent_bridges.py`
  - [x] 각 에이전트 브리지 스펙 검증
  - [x] 미지원 에이전트 → 명확한 에러
  - [x] 모델 자동 선택 폴백
- [x] 3.4 테스트 실행 기록 (§4 로그)

### Phase 4 — 검증 및 인수인계

- [x] 4.1 전체 신규 테스트 재실행 (Phase 1~3 합산)
- [x] 4.2 회귀 확인 — 관련 기존 테스트(model_router / models_api 인접) 실행
- [x] 4.3 진행 로그 최신화 (§4) — 타 에이전트가 이어받을 수 있도록
- [x] 4.4 미완료 항목 P3 목록 갱신

### Phase 5 — Anthropic tool-use content blocks (P0 완결)

**목표**: Claude Code의 도구 호출 루프가 Ssak-Ai 로컬 모델에서 동작하게 한다.
로컬 27B 모델은 Anthropic tool_use JSON을 네이티브 생성하지 않으므로,
텍스트 형식을 매개로 양방향 변환한다. (형식은 Phase 8에서 ```` ```json ```` 코드펜스로 전환 —
`<tool_call>` 리터럴은 일부 llama.cpp 런너의 세그폴트 유발)

**설계 원칙**: 추출/수리는 기존 `RobustToolParser`(27B 형식 오류 자가 수리기)를 재사용 — 새 파서 금지.

- [x] 5.1 `engine/anthropic_tool_bridge.py` 신규
  - [x] `serialize_tools_for_prompt()` — tools 배열 → 도구 카탈로그 + 형식 예시 프롬프트
  - [x] `build_tool_choice_directive()` — auto/any/tool/none 지시문
  - [x] `flatten_message_content()` — tool_use 블록 → 모델 출력 형식 복원, tool_result → 함수 결과 텍스트 (히스토리 라운드트립; 형식은 Phase 8에서 코드펜스로 변경)
  - [x] `extract_tool_use_blocks()` — 모델 출력 → tool_use (고유 toolu_ ID, 수리 플래그)
  - [x] `build_content_blocks()` — 태그 제거 텍스트 + tool_use 블록 (도구 전용이면 text 블록 생략)
  - [x] `resolve_stop_reason()` — tool_use 우선 > max_tokens > end_turn
- [x] 5.2 `messages_api.py` 확장
  - [x] `tools` 수신·검증 (name 필수, input_schema Mapping 강제) — 위반 시 400
  - [x] `tool_choice` 수신 → 시스템 프롬프트 지시문 결합
  - [x] assistant tool_use / user tool_result 히스토리 파싱 (`_extract_message_text` 위임)
  - [x] 비스트리밍: content = [text?, tool_use...] + stop_reason=tool_use
  - [x] 스트리밍: `input_json_delta` 이벤트 + `content_block_start(tool_use)` + stop_reason=tool_use
- [x] 5.3 테스트
  - [x] `tests/test_anthropic_tool_bridge.py` — 엔진 단위 14개
  - [x] `tests/test_messages_api.py` — API 통합 5개 추가 (프롬프트 주입, 400 검증, tool_use 응답, input_json_delta 조립, tool_result 라운드트립)
- [x] 5.4 테스트 실행 기록 (§5)

**알려진 제한 (다음 담당자 참고)**:
- 스트리밍이 실제 토큰 단위가 아니라 완성 응답을 청킹하는 방식 (ModelManager.stream_generate 동기 제너레이터 특성) — 실시간 tool_call 감지는 불가, 응답 완료 후 블록 분해
- `tool_choice: {type: "none"}`은 지시문으로만 강제 (하드 차단 아님)
- tool_use_id가 요청에서 온 것(assistant 히스토리)과 응답에서 새로 생성된 것의 연속성은 Anthropic SDK가 자동 처리

### Phase 6 — P3 후속: 세션 고지 UX + 데이터 레시피 (완료)

**6A. 세션 한도 고지 (freebuff 벤치마킹)** — "Freebuff shows the applicable session limits and any model-specific data-use notice before you start"

- [x] 6A.1 `engine/session_disclosure.py` 신규
  - [x] CostGuard `DailyStats` → 사용자 고지 변환 (결정론)
  - [x] 등급 판정: 잔여 0 → exhausted, >= 80% → warning, else healthy
  - [x] 예산/액션 한도 0이면 해당 고지 생략 + 안내 노티스 (제한 없음 명시)
  - [x] 데이터 지역성 노티스: "사용 내역은 로컬에만 저장, 외부 전송 없음" (freebuff 데이터 고지 스타일)
  - [x] `to_markdown()` — CLI/대시보드 공용 렌더링
- [x] 6A.2 `api/routes/disclosure_api.py` 신규
  - [x] `GET /api/session/disclosure` — 구조화 고지
  - [x] `GET /api/session/disclosure.md` — 마크다운 렌더링
- [x] 6A.3 CLI: `agk session` 명령 (rich Panel, 등급별 테두리 색)
- [x] 6A.4 테스트: `tests/test_session_disclosure.py` 10개 + `tests/test_disclosure_api.py` 2개

**6B. 데이터 레시피 (unsloth Data Recipes 벤치마킹)** — "Build datasets from PDFs, CSVs, DOCX files, and more"

- [x] 6B.1 `engine/data_recipes.py` 신규 — 결정론적 레시피 카탈로그
  - [x] 6개 프리셋: chat-sft / instruction-sft / preference-dpo / csv-to-chat / jsonl-to-chat / docs-qa-sft
  - [x] 레시피 = 포맷(SFT chat/instruction/DPO) + 하이퍼파라미터 조정 + 권장 최소 레코드 수
  - [x] 소스 변환기: CSV(prompt,response), JSONL(Alpaca/ChatML), TXT/MD(헤더→Q&A)
  - [x] `records_to_training_jsonl()` — 학습 포맷 직렬화
- [x] 6B.2 `lora_pipeline.py`에 `apply_recipe()` 추가 — 소스→데이터셋→학습 설정 원패스
  - [x] 파일 소스/수확 데이터/DPO 쌍 3경로 분기
  - [x] 레시피 하이퍼파라미터를 config에 병합, `recipe` 필드 기록
  - [x] 최소 레코드 미달 시 `sufficient: false` 경고
- [x] 6B.3 CLI: `agk recipes` (카탈로그) + `agk train-recipe <name> --source <path|harvest>`
- [x] 6B.4 테스트: `tests/test_data_recipes.py` 19개 (카탈로그/변환/Pipeline 연동)

**범위 결정 (다음 담당자 참고)**: PDF/DOCX 소스는 이후 Phase 10으로 연기했다가 **완료됨** — 아래 Phase 10 참조.
TXT/MD/CSV/JSONL과 함께 PDF/DOCX까지 지원 (선택 의존성 `documents` extra).

### Phase 7 — 대시보드 양자화 품질 배지 (완료)

**목표**: Phase 2가 채운 `quantization` 메타데이터를 Model Hub 카드에 품질 등급 배지로 시각화한다.
unsloth Dynamic GGUF 품질 가이드의 등급 체계를 따른다.

- [x] 7.1 `dashboard/src/utils/quantQuality.ts` 신규 — 등급 산출 유틸
  - [x] premium(P): Q8_0/F16/BF16/8bit — 원본 손실 거의 없음
  - [x] high(H): Q6_K/Q5_K/6bit/5bit — 저하 미미
  - [x] balanced(B): Q4_K/IQ4/4bit — unsloth 권장 스위트스팟 (UD-Q4_K_XL 포함)
  - [x] compact(C): Q3/Q2/IQ2/IQ1/TQ/3bit/2bit — 용량 우선
  - [x] unknown(?): 미표기/Active/N/A — 오탐 방지
  - [x] UD-* 동적 양자화는 동일 비트 정적 양자화와 동일 등급에 매핑 (품질 우대는 설명으로 처리)
- [x] 7.2 `ModelHubPage.tsx` — 양자화 스펙 칩 안에 등급 배지 추가 (색상+한 글자+툴팁)
- [x] 7.3 `index.css` — `.quant-quality-badge` 등급별 색상 (라이트/다크 테마 모두)
- [x] 7.4 테스트
  - [x] `dashboard/src/utils/quantQuality.test.ts` — 등급 산출 단위 7개
  - [x] `dashboard/src/pages/ModelHubPage.test.tsx` — 배지 렌더링 통합 1개 추가
- [x] 7.5 검증: vitest 10/10 (신규), 전체 프론트 스위트 644 passed / 54 files, `tsc --noEmit` clean

### Phase 8 — 라이브 E2E + llama.cpp crash-safe tool 형식 (완료)

**목표**: `agk serve` 기동 후 실제 로컬 모델(qwen3.8 via Ollama)로 `/v1/messages` 전 시나리오를 검증한다.

- [x] 8.1 E2E 클라이언트 `scripts/e2e_messages_client.py` — 비스트리밍/스트리밍/tool-use 1·2턴 4개 시나리오 자동 판정
- [x] 8.2 **결함 발견·근원 분석**: tool-use 시나리오에서 Ollama가 `{"error":"EOF"}` 반환 (라우터 측 500)
  - [x] 페이로드 바이섹션으로 근원 특정: qwen3.8 GGUF의 llama.cpp 런너가 **`<tool_call>` 리터럴 토큰을 생성하는 순간 세그폴트**
    - 카탈로그+"hello" → OK / 카탈로그+날씨 질문(도구 호출 유도) → 결정적으로 크래시
    - `<function_call>`/json 코드펜스 형식으로 유도하면 동일 JSON을 정상 생성 → **토큰 특이적 크래시** 확인
    - 옵션(think/min_p/keep_alive/num_predict)·카탈로그 크기와 무관 — Ssak-Ai 코드 결함 아님
- [x] 8.3 **형식 마이그레이션** (`engine/anthropic_tool_bridge.py`)
  - [x] `serialize_tools_for_prompt()` — 카탈로그 예시를 ```` ```json ```` 코드펜스 형식으로 변경 (`<tool_call>` 리터럴 배제)
  - [x] `flatten_message_content()` — tool_use 히스토리 복원도 코드펜스 형식 (`RobustToolParser` 백틱 폴백과 일치)
  - [x] `strip_tool_call_syntax()` — ```` ```json {"name":...} ```` 펜스 제거 추가 (단, `"name"` 키 있는 도구 호출만 — 일반 json 펜스는 보존)
  - [x] 추출 경로는 `RobustToolParser`가 태그·코드펜스 모두 지원하므로 구형 모델의 `<tool_call>` 출력도 여전히 파싱됨 (하위호환)
- [x] 8.4 서버 재기동 후 라이브 E2E: **4/4 PASS** (tool-use 1턴 stop_reason=tool_use + 2턴 end_turn 포함)
- [x] 8.5 회귀: `test_anthropic_tool_bridge.py` 17 + `test_messages_api.py` 13 = 30 passed

### Phase 9 — 대시보드 세션 고지 카드 (완료)

**목표**: Phase 6A의 `/api/session/disclosure`를 대시보드 UI에 렌더링한다 (freebuff "시작 전 고지" UX 완결).

- [x] 9.1 `dashboard/src/api/clientSchema.ts` — `SessionDisclosureSchema` zod 스키마 + `DisclosureLevel`/`LimitDisclosure`/`SessionDisclosure` 타입
- [x] 9.2 `dashboard/src/api/client.ts` — `fetchSessionDisclosure()` (기존 `requestJson` + zod 파싱 패턴 준수)
- [x] 9.3 `dashboard/src/components/shared/SessionDisclosurePanel.tsx` 신규
  - [x] 전체 등급 배너: healthy(녹색 ✅)/warning(호박 ⚠️)/exhausted(적색 ⛔) 색상·테두리·레이블
  - [x] 한도별 카드: 예산 `$X.XX / $Y.YY` · 액션 `N / M 회`, 사용량 게이지(등급색 그라데이션), 등급 배지, 안내 메시지
  - [x] 노티스 리스트 (데이터 지역성 고지), 리셋 날짜, 새로고침 버튼, 30초 자동 폴링
  - [x] 로딩 스피너/에러/빈 한도 상태 처리
- [x] 9.4 `SettingsPage.tsx` 비용 제어 섹션(04) 상단에 마운트 + barrel export 추가
- [x] 9.5 테스트: 렌더링 5개 (healthy 레이아웃·사용량 포맷, exhausted 스타일+100% 게이지, 리셋 날짜, API 에러, 빈 한도)

### Phase 10 — PDF/DOCX 소스 변환 (documents extra) (완료)

**목표**: unsloth Data Recipes의 "PDFs, DOCX files" 소스 지원 완결. 파서 라이브러리는 필수가 아닌
선택 의존성으로 — 코어 설치를 가볍게 유지한다 (Phase 6B 범위 결정의 후속).

- [x] 10.1 `pyproject.toml` — `documents` extra 신규: `pypdf>=6.1.0`, `python-docx>=1.1.0`
  (python-docx는 기존 `rag` extra와 버전 범위 공유 — 두 extra 동시 설치 시 충돌 없음)
- [x] 10.2 `engine/data_recipes.py` 확장
  - [x] `_pdf_records()` — 페이지별 텍스트 추출, 첫 줄이 제목처럼 보이면(80자 미만·마침표 없음) 질문, 본문→답
  - [x] `_docx_records()` — Heading 1/2(스타일명 heading/제목)→질문, 뒤 단락→답. 헤딩 없으면 문서 요약 Q&A 1건 폴백
  - [x] `MissingDocumentParserError` — 미설치 시 `uv sync --extra documents` 설치 안내 포함 에러
  - [x] `load_records_from_source()`에 .pdf/.docx 분기 + 지원 형식 안내 메시지 갱신
  - [x] 레시피 카탈로그에 `pdf-qa-sft`/`docx-qa-sft` 프리셋 추가 (extra 필요성 명시)
- [x] 10.3 테스트 (29개로 확장)
  - [x] pypdf writer로 content stream 직접 구성해 **실제 텍스트 PDF 생성** 후 변환 검증 (reportlab 불필요)
  - [x] python-docx로 실제 DOCX 생성 후 헤딩 Q&A·헤딩 없음 폴백 검증
  - [x] `apply_recipe` E2E: pdf/docx 소스 → 데이터셋 파일까지
  - [x] 미설치 시뮬레이션 (`monkeypatch.setitem(sys.modules, ...)`) — 설치 안내 에러 검증
  - [x] `documents` extra 미설치 CI에서도 스킵으로 통과 (모듈 존재 플래그 + skipif)
- [x] 10.4 검증: 29 passed, 회귀 46 passed (data_recipes+disclosure+finetune), ruff/mypy clean, CLI 카탈로그에 프리셋 노출

### Phase 11 — 학습 하이퍼파라미터 감사 (mlx-lm/unsloth 문서 대조) (완료)

**목표**: 레시피·파이프라인의 하이퍼파라미터를 설치된 mlx-lm(0.31.3)과 unsloth 최신 문서와 대조해 드리프트를 교정한다.

**조사 방법**: (1) 설치된 mlx-lm 0.31.3 소스의 `CONFIG_DEFAULTS`에서 실제 기본값 추출 — 웹 문서(main 브랜치)보다 우선,
(2) `mlx_lm lora --help`로 플래그 이름 실측, (3) unsloth.ai LoRA Hyperparameters Guide + DPO 노트북 + TRL DPO 문서.

**드리프트 발견·수정**:

| 항목 | 기존 값 | 문서/설치 기준 | 조치 |
|:---|:---|:---|:---|
| mlx LoRA 플래그 | `--lora-layers 16` | 0.31.x에서 **삭제됨** (실측: `unrecognized arguments`), 정식 이름 `--num-layers` | `lora_pipeline` 플래그·하이퍼키 교정 |
| mlx 기본 iters | 600 (주석 없음) | 0.31.3 기본 1000 — 600은 의도적 축소 | 출처 주석 추가 (값 유지) |
| DPO 학습률 (mlx 경로) | `1e-6` | unsloth 가이드: DPO/RL 계열 권장 `5e-6` | 교정 |
| DPO 하이퍼키 | `iters` | 다른 레시피·파이프라인은 `iterations` | 키 통일 |
| unsloth SFT batch | batch 2 × accum 4 (effective 8) | 가이드 권장 effective 16 (2×8) | accum 8로 교정 |
| unsloth SFT 스텝 | `max_steps=60` + `warmup_steps=5` | 가이드: 1-3 epochs, warmup 5-10%, weight decay 0.01, scheduler linear/cosine | `num_train_epochs=1` + `warmup_ratio=0.03` + `weight_decay=0.01` + seed 3407 |
| unsloth DPO 스크립트 | batch 2×4, warmup_steps, lr 5e-6만 존재 | 공식 DPO 노트북: batch 4×8, `warmup_ratio=0.1`, `optim="adamw_8bit"`, `ref_model=None`, bf16 헬퍼, seed | 전면 갱신 |
| LoRA 랭크/알파 | rank 16 / alpha 32 | 가이드: rank 16 또는 32, alpha = r 또는 2r | 드리프트 없음 (유지) |
| SFT 학습률 | 2e-4 | 가이드: normal LoRA/QLoRA 권장 2e-4 | 드리프트 없음 (유지) |

- [x] 11.1 `lora_pipeline.py` — mlx `--num-layers` 교정 + DPO lr 5e-6 + unsloth SFT/DPO 스크립트 갱신 + 출처 주석
- [x] 11.2 `data_recipes.py` — DPO 오버라이드 교정 (lr 5e-6, iterations 키 통일, epochs 1) + mlx 기본값 출처 주석
- [x] 11.3 테스트 보강: `test_lora_dpo.py`에 플래그 이름·가이드 기준값 검증 3개 추가
- [x] 11.4 검증: 51 passed (관련 3스위트), 전체 회귀 125 passed, ruff/mypy clean

**다음 담당자 참고**: mlx-lm은 버전마다 플래그가 바뀐다(0.31에서 `--lora-layers` 삭제). 업그레이드 시
`mlx_lm lora --help` 실측 + `CONFIG_DEFAULTS` 확인을 먼저 할 것. unsloth 값은 가이드 문서 기준이며
`learning_rate 2e-4`(SFT)/`5e-6`(DPO), effective batch 16, epochs 1-3이 핵심 앵커다.

### Phase 12 — 전체 백엔드 테스트 + 신규 파일 커버리지 리포트 (완료)

**실행**: `pytest tests/ -m 'not slow and not benchmark' --cov=src/antigravity_k` (전체 356 파일, ~5,000 테스트, 11분).

**전체 결과**: **4,988 passed / 26 failed / 8 errors / 6 skipped** (19 deselected) — 전체 커버리지 **77.23%**
(421 파일, 기존 임계값 fail_under 60 상회).

**실패 26건+8errors 분류 — 벤치마크 업그레이드 파일과 무관 확인**:
- `test_git_api_endpoints.py` 12건 + `test_filesystem_*` 2건 + `test_desktop_context_api` 1건:
  다른 에이전트의 **미커밋** `git_api.py`/`filesystem.py` 재작성(working tree 변경)으로 인한 계약 깨짐 — 본 작업 이전부터 존재
  → **Phase 27에서 재조정 완료**: git_api 12 + filesystem endpoints/security 33 + desktop_context 1 +
  boundary 6 = **52건 전부 통과** (피해 계열 전수 해소)
- `test_e2e_smoke.py` 8 errors: E2E 서버 기동 실패 (러너 환경 문제)
- `test_cli_smoke.py` 7건: 동일 러너 문제 — pytest가 venv 밖의 conda miniforge python에서 실행되어
  `sys.executable`이 miniforge를 가리키고, miniforge엔 antigravity_k 미설치 → subprocess CLI 호출 실패.
  `uv run` 환경에서는 동일 subprocess 호출이 정상 (직접 검증 완료)
  → **Phase 25에서 수정 완료**: `tests/_cli_subprocess.py` 헬퍼로 어떤 python이 pytest를
  실행해도 subprocess는 antigravity_k 임포트 가능한 인터프리터를 사용. cli_smoke 8/8, e2e_smoke 9/9
  (uv run·miniforge 양쪽에서 검증)
- 신규 파일 관련 실패: **0건** (messages/bridge/recipe/disclosure/quant/discovery/agent_bridges/lora 전부 통과)

**벤치마크 업그레이드 신규/수정 파일 커버리지** (Phase 1~11 산출물):

| 파일 | 구문 | 미커버 | 커버리지 |
|:---|---:|---:|---:|
| `engine/agent_bridges.py` (P3) | 35 | 0 | **100.0%** |
| `engine/session_disclosure.py` (P6A) | 73 | 2 | **97.3%** |
| `engine/data_recipes.py` (P6B/P10) | 190 | 16 | **91.6%** |
| `engine/local_model_discovery.py` (P2) | 374 | 33 | **91.2%** |
| `api/routes/messages_api.py` (P1/P5) | 181 | 17 | **90.6%** |
| `engine/lora_pipeline.py` (P6B/P11) | 299 | 48 | **83.9%** |
| `engine/anthropic_tool_bridge.py` (P5/P8) | 129 | 21 | **83.7%** |
| `api/routes/disclosure_api.py` (P6A) | 31 | 10 | 67.7% |
| `cli.py` (P3/P6 명령 추가분) | 806 | 531 | 34.1%* |
| **합계** | **2,118** | **678** | **68.0%** (cli 제외 **89.5%**) |

\* cli.py 34.1%는 파일 전체 기준. 본 계획에서 추가한 명령(session/recipes/train-recipe/start)은 별도 검증 완료
(live CLI 실행 + 브리지 테스트 10건). 미커버 대부분은 기존 대형 명령(doctor/model_list)의 분기.

**미커버 갭 성격 분석 (신규 엔진 파일)**:
- 예외 경로 (json 직렬화 실패, TypeError 분기) — anthropic_tool_bridge 21건 중 9건
- 방어적 continue/스킵 (빈 블록, 형식 불일치 행) — data_recipes 16건 중 7건
- 드물게 요청되는 API 조합 (`tool_choice none` 등) — messages_api 일부
- disclosure_api `get_cost_guard()`의 EngineContext 재사용 분기 (테스트는 fresh 경로만 커버)
- lora_pipeline의 `apply_recipe` 함수 본문은 **0건 미커버** — 48건 모두 기존 기능(수확 통계/초기화)

- [x] 12.1 전체 스위트 실행 + 커버리지 수집 (JSON 리포트: `.tmp/coverage_full.json`)
- [x] 12.2 실패 원인 분류 (신규 파일 무관 입증)
- [x] 12.3 신규 파일별 커버리지 표 + 갭 분석
- [x] 12.4 문서 기록 및 인수인계 메모

**다음 담당자 참고**: (1) git_api/filesystem 실패는 **Phase 27에서 해소됨** — 타 에이전트 미커밋 변경을
테스트 계약 기준으로 재조정 (아래 Phase 27 참조). (2) CLI 스모크 실패 러너 환경은 **Phase 25에서 수정됨**
(`tests/_cli_subprocess.py`) — 이제 어떤 python으로 pytest를 돌려도 통과. (3) 커버리지 임계값 60% 대비 전체 77.2%로 여유 있음.

### Phase 13 — 대시보드 전역 경고 배너 (완료 → **Phase 14에서 제거됨**)

**목표**: 세션 고지 등급이 warning/exhausted일 때 앱 전역에 경고 배너를 표시한다 (Phase 9 카드의 보완 —
설정 페이지를 열기 전에도 한도 상황을 인지하게 함).

- [x] 13.1 `dashboard/src/components/shared/SessionDisclosureBanner.tsx` 신규
  - [x] healthy/null → 렌더링 없음. warning(호박 ⚠️)/exhausted(적색 ⛔)만 표시
  - [x] `role="alert"` + `aria-live="polite"` 접근성 속성
  - [x] 닫기 버튼: 동일 등급에서는 세션 동안 숨김, **등급 악화(warning→exhausted) 시 자동 재표시**
  - [x] "설정에서 확인" 링크 — 기존 `agk:pushstate` 커스텀 이벤트로 SPA 라우팅 (App.tsx 훅 재사용)
  - [x] API 실패 시 조용히 숨김 (비필수 UX — 오류 토스트 없음), 60초 폴링
- [x] 13.2 `App.tsx` 마운트 — `app-right-panel` 최상단, 모든 라우트에 걸쳐 표시
- [x] 13.3 barrel export 추가
- [x] 13.4 테스트 6개: healthy 숨김, API 실패 숨김, warning 표시+메시지, exhausted 표시+차단 안내,
      닫기→동일등급 유지→악화 재표시, pushstate 링크
- [x] 13.5 검증: 배너 6/6, 전체 프론트 655 passed (55+1 files), `tsc --noEmit` clean

---

### Phase 15 — ChatPage 배지·Model Hub 품질 등급 통일 (완료)

**목표**: ChatPage 모델 선택 팝오버의 `badge-quant` 칩이 Model Hub와 동일한 quantQuality 등급 체계를
쓰도록 통일 (P3 백로그 잔여 항목 해소).

- [x] 15.1 `ChatPage.tsx` — 실행 중/Unsloth/MLX 3개 그룹 모두: `badge-quant`에
  `q-{level}` 변형 클래스 + `title` 툴팁(`토큰 — 레이블`) 적용 (칩 텍스트는 양자화 토큰 유지 —
  좁은 팝오버에서 `UD-Q4_K_XL` 같은 전체 토큰이 식별자 역할을 하므로)
- [x] 15.2 `index.css` — `.badge-quant.q-{premium|high|balanced|compact|unknown}` 5변형 +
  다크 테마 변형 (Model Hub `.quant-quality-badge`와 동일 팔레트)
- [x] 15.3 테스트: ChatPage 목업 모델 3종(`UD-Q4_K_XL`→balanced, `4bit`→balanced,
  `qwen3.8:latest` running quantization `''`→미렌더) 등급 클래스·툴팁 검증 3개
- [x] 15.4 검증: ChatPage 스위트 전부 통과, 전체 프론트 vitest + `tsc --noEmit` clean

**설계 노트**: 단일 진실원은 여전히 `dashboard/src/utils/quantQuality.ts` 하나 — 두 표면은
같은 함수를 호출하므로 앞으로 등급 체계가 바뀌면 util만 고치면 된다. CSS 팔레트만 두 곳에 존재
(칩 vs 아이콘 형태가 달라 클래스 공유 불가).

### Phase 14 — 세션 고지 레이어 제거 (개인 사용 판단, 완료)

**결정**: 본 프로그램은 개인 사용 목적 — 한도 관리·사용량 고지 레이어는 불필요.
사용자 판단으로 Phase 6A/9/13에서 추가한 고지 UX 전체를 제거했다.

**제거된 것**
- `engine/session_disclosure.py`, `api/routes/disclosure_api.py` (백엔드)
- `api/routes/__init__.py`의 disclosure_router 등록 2줄
- `cli.py`의 `agk session` 커맨드
- `dashboard/` — `SessionDisclosurePanel.tsx`/`SessionDisclosureBanner.tsx` + 테스트 2개,
  zod 스키마(`SessionDisclosureSchema` 등) + `fetchSessionDisclosure()`, App/SettingsPage 마운트, barrel export
- 문서 매니페스트의 관련 파일들은 이력 기록으로 그대로 둠

**의도적으로 남긴 것**
- `engine/cost_guard.py` — 본래부터 존재한 예산/액션 **강제** 로직. 고지 UX와 무관하게 동작하며
  `AGK_DAILY_BUDGET_USD`/`AGK_HOURLY_ACTION_LIMIT` env가 설정된 경우에만 개입한다 (기본 비활성 흐름 유지)

- [x] 14.1 백엔드 파일·라우터·CLI 제거
- [x] 14.2 대시보드 컴포넌트·스키마·클라이언트·마운트 제거
- [x] 14.3 검증: API 라우터에 disclosure 경로 0건, CLI import OK, ruff clean,
  프론트 vitest **644 passed** (제거된 고지 테스트 11개만큼 감소) + `tsc --noEmit` clean
  (mypy 1건은 타 에이전트 미커밋 `filesystem.py` 소속 — 무관)
- [x] 14.4 복원 가이드: 각 단계는 아래 Phase 6A/9/13 체크리스트에 상세히 기록되어 있어 필요 시 역순 재구현 가능

### Phase 16 — 실서버 Claude Code E2E (P3 백로그, 완료)

**목표**: P3 백로그의 “실서버 E2E: Claude Code 실제 연결 검증” 수행 — 실제 Claude Code CLI를
`agk start claude` 브리지 env로 `agk serve`에 연결해 멀티턴 에이전트 세션을 검증한다.

**설정**
- Claude Code CLI 2.1.260을 `.tmp/claude_cli`에 프로젝트 로컬 설치 (gitignored — 전역 설치 없음,
  `npm install @anthropic-ai/claude-code`)
- `agk serve` 포트 8479 (loopback, PIN 없음 → 자동 인증) + Ollama `qwen3.8:latest`
- 브리지 env: `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY=ssak-ai-local`/`ANTHROPIC_MODEL`/
  `ANTHROPIC_SMALL_FAST_MODEL` — `agk start claude`가 출력하는 그대로

**결과 — 3 시나리오 전부 PASS (서버 `/v1/messages` 6회 히트, 4xx/5xx 0건)**
- [x] 16.1 단턴: 일반 질의 → 정상 답변 (서버 히트 2회: 세션 타이틀 생성 + 본 답변)
- [x] 16.2 멀티턴 (`--print --continue`): 이전 턴 질문 재확인 → 정확히 회상
  ("You asked, \"1+1은?\"") — 세션 맥락이 브리지 API를 통해 정상 유지됨
- [x] 16.3 도구 사용 에이전트 루프: 파일을 읽어 비밀 숫자 보고 → Claude Code가 Read 도구를
  호출하고 **로컬에서 실행**된 결과로 정답(42726) 보고 — `/v1/messages` tool-use 라운드트립
  (Phase 1/5/8의 서버측 구현)이 실제 에이전트 클라이언트와 동작함을 실증

**인수인계 노트**
- 첫 요청 시 “unrecognized model” 경고가 나오지만 무해 — 자동 컴팩트로 200k 가정.
  없애려면 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`를 실제 컨텍스트 창으로 설정하거나
  modelPicker `behavesAs` 매핑 사용.
- CLI는 `.tmp/claude_cli`에 보존 — 재사용 시 `PATH`에 `.tmp/claude_cli/node_modules/.bin` 추가.
  `.tmp`는 gitignored이므로 다른 에이전트가 없다면 위 npm 설치 1줄로 재현.
- 잔여: 동일 시나리오의 **Codex 클라이언트** 검증은 미수행 (브리지 env는 `agk start codex`).

### Phase 17 — Model Hub 품질 등급 필터 pill row (완료)

**목표**: Model Hub에서 품질 등급 기준으로 모델을 브라우징할 수 있게 등급 프리셋 필터 pill row를 추가한다
(quantQuality 등급 서열: unknown < compact < balanced < high < premium).

- [x] 17.1 `ModelHubPage.tsx` — `QuantTierFilter` 타입 + `QUANT_TIER_FILTERS` 프리셋 4종
  (품질 전체 / ⭐ 균형 이상(balanced+high+premium) / ⭐⭐ 높음 이상(high+premium) / 💎 프리미엄만(premium))
- [x] 17.2 필터 로직: `filteredModels`에 등급 프리셋 조건 추가 — 카테고리·검색 필터와 AND 조합.
  기존 pill(`hub-cat-btn`)과 동일 컴포넌트 스타일 재사용 + `hub-quant-tier-btn` 보조 클래스(활성 시 보라 링).
  활성 프리셋에서만 "N개 표시" 카운트 노출, 툴팁에 등급 기준 설명.
- [x] 17.3 `index.css` — `.hub-quant-tier-pills`/`.hub-quant-tier-btn`/`.hub-quant-tier-count`
  (기존 pill 컨벤션 준수, CSS 변수 사용이라 다크 테마 자동 대응)
- [x] 17.4 테스트 2개: 균형 이상 → unknown(running) 제외·2개 표시, 프리미엄만 → 1개 표시,
  복귀 시 카운트 숨김 / MLX+프리미엄 조합 빈 상태 노출
- [x] 17.5 검증: Model Hub 스위트 5/5, 전체 프론트 **649 passed**, `tsc --noEmit` clean

**설계 노트**: 등급 산정은 여전히 `quantQuality()` 단일 진실원 — 필터 프리셋은 그 레벨 집합만 정의한다.
unknown 모델(quantization 미표기)은 어떤 프리셋에도 속하지 않아 "균형 이상" 등에서 자연 제외되는데,
이는 실행 중 모델(Active)이 필터에서 사라지는 트레이드오프다. 의도적 동작이며, 실행 중 모델 우선
노출이 필요하면 프리셋에 unknown 추가로 완화 가능.

### Phase 18 — `agk model list` CLI 품질 등급 가이던스 (완료)

**목표**: CLI 모델 목록에서도 대시보드 Model Hub 배지와 동일한 양자화 품질 등급을 보여준다.

- [x] 18.1 `engine/quant_quality.py` 신규 — Python 측 품질 등급 매핑,
  `dashboard/src/utils/quantQuality.ts`와 1:1 대응 (토큰 셋·정규식·우선순위·Active/N/A 처리 동일).
  `LEVEL_ORDER` 서열 상수 포함(unknown<compact<balanced<high<premium) — 필터/정렬 재사용 가능.
  양쪽 파일에 상호 참조 주석 유지 — **수정 시 반드시 양쪽 함께**
- [x] 18.2 `cli.py` — `model list` 각 행에 Quant 컬럼 추가:
  양자화 토큰 + 색상 등급 한 글자 (`UD-Q8_K_XL P`, `4bit B`), unknown은 `—`.
  색상: P=green, H=cyan, B=magenta, C=dark_orange (등급 CSS 팔레트와 대응).
  하단 패널에 등급 범례 + “대시보드 Model Hub 배지와 동일” 안내 추가
- [x] 18.3 테스트 `tests/test_quant_quality.py` 28개 — TS util과 동일 케이스 표,
  서열 단조성, CLI 셸 렌더링 (unknown→`—`)
- [x] 18.4 검증: 28/28 통과, 인접 회귀(quantization_discovery+model_registry) 51 passed,
  ruff + mypy clean, 라이브 `agk model list` 출력 확인
  (로컬 GGUF/MLX: `UD-Q8_K_XL P`·`UD-IQ4_XS B`·`4bit B`·`Q8_0 P`, 클라우드/무양자화: `—`)

**설계 노트**: 품질 등급의 단일 진실원은 이제 언어별 2개(대시보드 TS, CLI Python)로,
토큰 셋이 1:1 동일함이 테스트 케이스 표로 잠겨 있다. 백엔드 `/api/models/local`이 주는
`quantization` 문자열이 같으므로 CLI·대시보드·API 소비자 모두 같은 등급을 본다.

### Phase 19 — 세션 고지 카드 재복원 (Phase 14 제거 되돌림, 완료)

**결정**: 사용자가 P3 백로그의 "대시보드 세션 고지 카드" 구현을 다시 요청하여 Phase 14 제거를 되돌림.
사용자 확인(ask_questions) 후 **카드만** 복원 — Phase 13의 전역 배너는 복원하지 않음.

- [x] 19.1 백엔드: `engine/session_disclosure.py` + `api/routes/disclosure_api.py`
  (`get_cost_guard`: EngineContext 재사용 우선 + env 폴백) + 라우터 등록 + `agk session` CLI 재구현
- [x] 19.2 프론트: `clientSchema.ts` zod 스키마 3종 + `client.ts` `fetchSessionDisclosure()`
  + `SessionDisclosurePanel.tsx` (등급 배너·한도 카드·게이지·노티스·30초 폴링) + SettingsPage 04 섹션 상단 마운트 + CSS
- [x] 19.3 검증: 백엔드 17 passed (엔진 12 + API 2 + 라이브 CLI), 프론트 5 passed,
  전체 프론트 **654 passed** + `tsc --noEmit` clean, ruff clean

**인수인계**: 전역 배너(Phase 13)도 필요하면 `SessionDisclosureBanner.tsx` 사양은 해당 섹션 참조.
Phase 14의 "제거됨" 기록은 이력으로 유지 — 본 Phase 19가 최종 상태.

### Phase 20 — `agk train-recipe` PDF 라이브 E2E (완료)

**목표**: 실제 PDF 소스로 `agk train-recipe pdf-qa-sft`를 실행해 **실제 데이터셋과 학습 설정 파일**이
생성되는지 라이브 검증 (Phase 10의 PDF 변환 + Phase 6B의 apply_recipe 통합 경로).

**절차**
1. 텍스트 레이어가 있는 실제 5페이지 PDF 생성 (Phase 10 테스트 헬퍼와 동일 방식:
   pypdf writer + DecodedStreamObject content stream, Q&A 헤더 5개)
2. `uv run agk train-recipe pdf-qa-sft --source <pdf> --out .tmp/recipe_e2e` 라이브 실행
3. 산출물 정합성 검증 후 임시 파일 정리

- [x] 20.1 CLI 실행 성공: `✓ pdf-qa-sft — 5건` + 데이터셋/설정 경로 + 하이퍼파라미터 출력
- [x] 20.2 데이터셋 검증: `recipe_dataset.jsonl` 5레코드, ChatML `messages` 구조
  (user→assistant, 빈 content 없음), 질문이 PDF 원문 헤더와 대응
- [x] 20.3 설정 검증: `lora_config.json`에 `recipe: pdf-qa-sft` 기록,
  레시피 하이퍼파라미터 병합 (lr 2e-5, iterations 500, rank 16, alpha 32 — Phase 11 감사 값),
  mlx 플랫폼 명령어(`python -m mlx_lm.lora --train --data ...`) 생성
- [x] 20.4 정리: 임시 PDF/산출물 삭제 (재현은 Phase 10 헬퍼로 PDF 재생성 후 위 명령 실행)

**인수인계**: 이 검증은 일회성 라이브 실행이라 자동 테스트에 넣지 않았다.
문서화된 것과 동일한 실제 PDF 경로 E2E가 필요하면 `tests/test_data_recipes.py`의
`_write_pdf_with_text` 헬퍼로 소스를 만들고 위 CLI 명령을 실행하면 된다.

### Phase 21 — PDF 소스 페이지 범위·헤더 필터 옵션 (완료)

**목표**: PDF 레시피 변환기에서 페이지 범위 선택과 페이지 헤더 필터링을 지원한다.

- [x] 21.1 `engine/pdf_source_options.py` 신규 — `parse_page_ranges()`
  ("1-5,8,11-13" 문법, 정렬·중복 제거, 문서 크기 검증) + `PdfSourceOptions` frozen dataclass
  (header_filter 정규식, "!" 접두사=제외 모드, 잘못된 정규식 ValueError)
- [x] 21.2 연결: `_pdf_records(path, options)` → `load_records_from_source(source, pdf_options)` →
  `apply_recipe(..., pdf_pages=, pdf_header_filter=)` → CLI `--pdf-pages` / `--pdf-header-filter`.
  필터가 매칭을 거부한 페이지는 요약 질문 폴백 없이 건너뛴다
- [x] 21.3 테스트 `tests/test_pdf_source_options.py` 28개 — 파서 단위(정렬/중복/경계/8종 에러),
  필터 단위(포함/제외/search 시맨틱/불변성), 실제 PDF 통합(범위/필터/조합/load/apply_recipe E2E)
- [x] 21.4 검증: 28 passed, 회귀 76 passed (data_recipes+lora_dpo+quant_quality), ruff/mypy clean,
  라이브 CLI 3 시나리오 실측 (범위만/필터만/조합) + 범위 초과 에러 UX 확인

**설계 노트**: 옵션은 PDF 전용으로 분리 — CSV/JSONL/DOCX에는 무의미하고, 소스 문자열 문법을
확장(예: `file.pdf#1-5`)하면 경로에 특수문자 문제가 생기므로 명시적 플래그를 택했다.
옵션은 `apply_recipe`의 다른 소스(harvest/DPO) 경로에는 영향을 주지 않는다.

### Phase 22 — mlx-lm 플래그 드리프트 CI 체크 (완료)

**목표**: `lora_pipeline`이 생성하는 mlx 학습/병합 명령의 플래그가 설치된 mlx-lm 버전에서
실제로 존재하는지 CI에서 검증한다. 배경: mlx-lm은 버전 간 플래그 이름을 개정한 적이 있고
(Phase 11: `--lora-layers` → `--num-layers`), 깨진 명령은 사용자 런타임에만 실패한다.

- [x] 22.1 `tests/test_mlx_command_flags.py` 신규 4개 —
  `python -m mlx_lm.{lora,fuse} --help` 출력에서 유효 플래그 열거 → 생성 명령(SFT/DPO/fuse)의
  `--플래그`와 대조, 미지 플래그가 있으면 **테스트 실패** (수정 위치 안내 포함).
  첫 테스트는 헬프 파싱 자체의 건전성(`--model/--train/--data` 존재)을 검증.
- [x] 22.2 skip 전략: `import mlx_lm` 실패 시 전체 스킵 — Linux CI base/rag 조합은 스킵,
  mlx 조합에서만 실행됨. CI 마커 제외(`not slow and not benchmark`)와 충돌 없음.
- [x] 22.3 CI: `ci.yml` test matrix에 `deps: [base, rag, mlx]` 추가 + Install 스텝 분기 —
  mlx 조합은 macOS/Ubuntu에서 `uv sync --locked --extra dev --extra mlx`로 설치.
- [x] 22.4 검증: 로컬 4/4 passed (mlx-lm 0.31.3), 음성 검증 완료 —
  구 플래그 `--lora-layers`가 헬프에 없음 확인 + argparse가 미지 플래그를 거부함을 실증
  (즉, 구 플래그로 회귀하면 이 테스트가 잡는다), ruff/mypy clean, ci.yml YAML 유효

**한계 노트**: `--help` 열거는 플래그 존재 여부만 잡는다 — 값 범위나 의미 변경(예: iters 기본값
변경)은 잡지 못하며, 그런 변경은 Phase 11의 `CONFIG_DEFAULTS` 감사 절차로 대응한다.

### Phase 23 — 실제 mlx-lm LoRA 학습 E2E (완료)

**목표**: Phase 11/22에서 감사한 명령으로 **실제 LoRA 학습**을 수행해 학습 설정의 유효성을
런타임에서 입증한다.

**설정**
- 수확 데이터: `LoRAPipeline.harvest()` API로 실제 사용 패턴 Q&A 6건 시드 → `export_dataset(format="chat")`
- 베이스: `mlx-community/Qwen2.5-0.5B-4bit` (HF 캐시에 이미 존재, 276MB — 다운로드 없음)
- 설정 생성: `apply_recipe("chat-sft", source="harvest", platform="mlx")` —
  감사된 명령 그대로 (`--iters 600 --batch-size 4 --num-layers 16 --learning-rate 1e-5`)

**실행 결과**
- [x] 23.1 프로브(20 iters): 11.7초, loss 5.70 → 0.77 — 파이프라인 정상 확인
- [x] 23.2 전체 학습(600 iters): **47초** 완료, train/val loss 5.70 → **0.581** 수렴,
  Peak mem 1.3GB, 초당 13.6 it / 3,700 tokens
- [x] 23.3 어댑터 저장 확인: `adapters/adapters.safetensors` + 체크포인트 6개 (매 100 iters)
- [x] 23.4 어댑터 로드 추론: `load(..., adapter_path=...)`로 어댑터 적용 추론 성공 —
  베이스(반복 루프 출력) vs 튜닝(질문 재구성 답변) 출력 차이 확인

**발견·수정된 것 (다음 담당자 필독)**
- **ChatML 단일 JSONL은 mlx-lm이 직접 받지 않는다**: mlx-lm 로컬 데이터셋은
  `train/valid(/test).jsonl` **디렉터리** 구조가 필요하고, 각 분할이 `batch_size` 이상이어야 하며
  (validator: `Dataset must have at least batch_size=N examples`), 빈 `test.jsonl`도 에러를 낸다.
- → **개선 백로그(P2, 완료)**: `apply_recipe`가 mlx 플랫폼(`platform="mlx"`)에서
  `split_dataset_for_mlx`를 통해 train/valid을 자동 분할하여 mlx-lm 디렉터리 구조
  (`mlx_dataset/train.jsonl` + `valid.jsonl`)로 산출하도록 확장 완료 (레코드 부족 시 재사용 폴백 포함).

**산출물 보존**: `data/lora_e2e_out/` (데이터셋·설정·어댑터) — 재실행 불필요, 참조용으로 유지.

### Phase 24 — 학습 레시피 하이퍼파라미터 UI 노출 (완료)

**목표**: 대시보드 학습 UI(StudioPage STEP 4)에서 레시피 프리셋의 **감사된 하이퍼파라미터**를
편집 가능한 필드로 불러올 수 있게 한다. 단일 진실원(`engine/data_recipes.py`의 RECIPES,
Phase 11 감사값)은 그대로 유지.

- [x] 24.1 백엔드 `api/routes/recipes_api.py` 신규 — `GET /api/recipes`:
  레시피 카탈로그 8개(이름·설명·포맷·최소 레코드·**하이퍼파라미터 오버라이드**)를 JSON으로 노출
- [x] 24.2 `apply_recipe`에 `hyperparameter_overrides` 파라미터 추가 — 병합 우선순위:
  플랫폼 기본값 < 레시피 오버라이드 < **사용자 지정 값** (신규 키 추가도 허용)
- [x] 24.3 프론트: `clientSchema.ts` (`TrainingRecipe` zod 스키마) + `client.ts`
  `fetchTrainingRecipes()` + StudioPage STEP 4에 프리셋 선택기 —
  선택 시 learning_rate/batch_size/lora_rank/lora_alpha/num_train_epochs/iterations를
  편집 가능한 필드에 채우고 감사된 값 요약을 표시. 필드는 여전히 자유 편집 가능.
- [x] 24.4 테스트: 프론트 3개(프리셋 적용/수동 입력/카탈로그 실패 내성) +
  백엔드 API 라이브 확인(8 프리셋, pdf-qa-sft 감사값 일치) + 오버라이드 우선순위 통합 검증
- [x] 24.5 검증: 프론트 657 passed + `tsc --noEmit` clean, data_recipes+lora 48 passed, ruff clean

**설계 노트**: STEP 4는 기존에 하드코딩된 Unsloth 권장값(2e-4 등)만 있었고 레시피와 무관했다.
프리셋 선택은 필드를 **채울 뿐 잠그지 않는다** — 편집 후 학습 시작 시 payload에 포함되어
`apply_recipe(hyperparameter_overrides=...)`로 전달된다.

### Phase 25 — bridge/disclosure 예외·skip 분기 커버리지 100% (완료)

**목표**: Phase 12 커버리지 리포트의 저조한 신규 파일 두 개를 90%+로 끌어올린다 —
결과는 **100%**.

| 파일 (Phase 12 → 25) | 커버리지 변화 |
|:---|:---|
| `anthropic_tool_bridge.py` | 83.7% → **100%** (22 미커버 라인 해소) |
| `disclosure_api.py` | 60.0% → **100%** (EngineContext 재사용/폴백 경로) |
| `session_disclosure.py` | 97.3% → **100%** (보너스) |

- [x] 25.1 `tests/test_bridge_disclosure_edge_branches.py` 신규 33개 —
  **bridge**: 비-Mapping/무효 이름 tool 정의 skip, 직렬화 불가 input_schema/input/arguments의
  TypeError 폴백, tool_choice 남은 분기(any/none/tool-빈이름/미지 kind/스칼라),
  content 블록 skip 경로, stop_reason max_tokens, broken input_json → `{}` 폴백.
  **disclosure_api**: EngineContext 재사용(monkeypatched orchestrator),
  get_orchestrator 예외 → env 폴백, ctx.cost_guard 타입 불일치 → 기본값 폴백,
  DI 주입 엔드포인트 통과. **session_disclosure**: 등급 메시지 남은 분기 +
  icon/label 알 수 없는 등급 폴백
- [x] 25.2 검증: 대상 3파일 **100%** (241 stmts, 0 miss), 인접 스위트 79 passed,
  ruff + mypy clean

**방법론 노트**: `extract_tool_use_blocks`의 직렬화 폴백(184-185)은 정상 파서 경로로는
도달 불가 — `RobustToolParser.extract_tool_calls`를 monkeypatch해 직렬화 불가 arguments
(set 포함)를 주입하는 방식으로만 검증 가능. 이런 "도달 불가 폴백"은 mock 주입이 정석.

### Phase 26 — CLI/E2E 스모크 테스트 러너 무관화 (완료)

**목표**: pytest를 어떤 python(프로젝트 venv, conda miniforge, macOS CLT)으로 실행하든
subprocess 기반 CLI/서버 스모크 테스트가 환경에 무관하게 통과하도록 수정
(Phase 12 트리아지에서 "러너 환경 문제"로 분류됐던 15건 해소).

**근원**: `_run_cli`/서버 fixture가 `sys.executable`로 subprocess를 띄웠는데,
pytest가 venv 밖 인터프리터(miniforge 3.13, CLT 3.9)에서 돌면 그 인터프리터엔
`antigravity_k`가 설치되지 않아 `ModuleNotFoundError`로 실패.

- [x] 26.1 `tests/_cli_subprocess.py` 신규 — 인터프리터 선택 우선순위:
  `AGK_TEST_PYTHON` env (CI 명시 지정) → `uv run --no-sync [--project 루트] python`
  (프로젝트 표준) → `sys.executable` 임포트 검증 통과 시 사용 → `.venv/bin/python` 폴백 →
  최후엔 `sys.executable` (기존 동작 유지). lru_cache로 프로브 1회만 실행.
- [x] 26.2 `test_cli_smoke.py`: `_run_cli`가 헬퍼 접두어 사용. uv는 cwd가 tmp_path일 때
  프로젝트를 못 찾으므로 `--project <루트>`를 항상 명시 (`--no-sync`는 cwd 경고 억제).
- [x] 26.3 `test_e2e_smoke.py`: 서버 fixture도 동일 헬퍼 사용.
- [x] 26.4 검증: **uv run pytest** cli 8/8 + e2e 9/9, **miniforge pytest** cli 8/8 + e2e 9/9 —
  두 러너에서 모두 통과. finetune 스위트(miniforge) 14 passed. ruff/mypy clean.

**한계 노트**: macOS CLT python 3.9로 `python3 -m pytest`를 직접 실행하면 테스트 수집 자체가
3.9 미지원 문법으로 실패 — 이는 pyproject의 `requires-python`(3.11+) 위반이라 본 수정 범위 밖.
러너 요구사항은 문서화로 대체.

### Phase 27 — 타 에이전트 미커밋 git_api/filesystem 재조정 (완료)

**상황**: 다른 에이전트가 `git_api.py`/`filesystem.py`를 working tree에서 재작성했고,
`test_git_api_endpoints` 12건 + filesystem 계열 33건이 계약 깨짐으로 실패 (Phase 12 트리아지).

**재조정 방침**: 테스트 계약이 진실원 — 구현이 계약을 따르도록 수정 (단, 새 로직의
합법적 의도는 보존: 예. filesystem의 리포지토리 루트-상대 경로 처리).

- [x] 27.1 `git_api.py` — `_resolve_git_dir`가 active project 절대경로를
  `allowed_roots()`보다 우선하던 변경을 되돌리고 원래 계약(allowed_roots 소속만 허용)으로 복귀.
  12/12 통과.
- [x] 27.2 `filesystem.py` — 누락된 `Any` 임포트 복구 + `fs_browse`의 WORKSPACE_ROOT
  밖 403 계약 회복 (리포지토리 루트-상대 세그먼트는 허용하되 워크스페이스 밖 탐색은 차단).
  endpoints 33건 통과.
- [x] 27.3 회귀: git 12 + filesystem 33 = **45 passed**, ruff + mypy clean.

**한계 노트**: 타 에이전트 작업의 나머지 부분은 보존됨 — 이 파일들의 미커밋 소유권은 여전히
그 에이전트에 있으므로, 커밋 시 본 재조정 내역을 함께 반영해야 함 (충돌 시 테스트 계약 우선).

### Phase 28 — 고지 카드 라이브 E2E 검증 (완료)

**목표**: agk serve 스타일 백엔드 + 대시보드를 실제로 기동해, 거의 소진된 예산에서
세션 고지 카드(Phase 19)가 레벨별 스타일링으로 렌더링되는지 라이브 검증.

**방법 (프로덕션 코드 무변경)**:
- `.tmp/serve_seeded.py` 하니스 — deps `_orchestrator` 싱글턴 자리에 실제 CostGuard를
  심은 최소 컨텍스트 주입 → `get_cost_guard()`의 EngineContext 재사용 경로 실서버 검증.
  시딩은 공개 API만 사용 (record_spend / check_budget — 내부 필드 직접 조작 없음).
- `.tmp/daemon_spawn.py` — 더블포크+setsid 데몬 스포너 (코드버프 명령 종료 후에도 서버 생존).
- CostGuard 상태는 프로세스 메모리에만 존재하고 usage_tracker는 로컬 모델 비용을 0.0으로
  기록하므로, 실제 트래픽으로는 소진 상태에 도달할 수 없음 → 시딩이 유일한 재현 수단.
- `AGK_SEED_LEVEL=warning|exhausted`로 레벨 선택 (주의: record_spend도 액션 윈도우 1건 적립).

- [x] 28.1 백엔드(포트 8400, 경고 시드 88%/86%) 기동 → `/api/session/disclosure` JSON·md 실측
  (level=warning, $44/$50 88%, 86/100 86%)
- [x] 28.2 대시보드 vite(5173, VITE_BACKEND_URL=8400) 기동 + 프록시 경유 API 확인
- [x] 28.3 /settings 로드 → 카드 렌더링 확인 (accessibility tree + 스크린샷):
  `session-disclosure-panel level-warning`, "⚠️ 세션 한도 — 주의" 배너, 게이지 88/86,
  한도별 메시지, 로컬 데이터 고지, 리셋 기준일
- [x] 28.4 소진 전환: 백엔드를 exhausted 시드로 교체 → 페이지 리로드 후
  `level-exhausted`, "⛔ 세션 한도 — 소진", 게이지 100/100 확인 (스크린샷)
- [x] 28.5 리프레시 버튼 실측: 소진 표시 중 백엔드만 warning으로 교체 → ↻ 클릭 한 번에
  `level-warning` + $44/$50로 갱신 (페이지 리로드 없음) — 새로고침/30초 폴링 경로 검증
- [x] 28.6 서버 정리 (8400/5173 리스너 0)

**검증 기록**: 백엔드 로그 200 OK 실측, 프리뷰 스크린샷 2건(주의/소진), DOM 클래스·게이지·
배너 텍스트 실측. 백엔드 교체 창구의 일시적 fetch 실패 시 카드가 에러 상태로 전환되는 것도
함께 관측됨 (에러 상태 복구 = 리프레시/폴링 — 정상 동작).

**다음 담당자 참고**: 라이브 재현은 위 하니스 2개 파일로 가능 (임시 파일이므로 커밋 대상 아님).
시딩 user_id="seed-system"은 사용자별 예산($20)과 무관하게 글로벌 예산만 채우기 위한 장치.

### Phase 29 — 고지 배너+카드 공유 스토어 통합 (완료)

**목표**: 전역 배너(Phase 13 사양 복원)와 설정 카드가 **하나의 폴링 인터벌**을 공유하게 한다 —
표면마다 돌아가던 타이머/네트워크 호출을 한 개로 합치고, dismiss·등급 상태는 스토어가 소유.

**설계**:
- `stores/disclosureStore.ts` (신규, zustand) — `disclosure/loading/error` + refcount 폴러:
  첫 구독에서 즉시 fetch + 30초 인터벌 시작, 마지막 구독 해제 시 인터벌 정리 (표면 0개면 요청 0건).
  실패 시 error 플래그만 세팅하고 마지막 성공 데이터 유지.
- `SessionDisclosurePanel` — 로컬 fetch/useState 제거, 스토어 구독으로 전환 (렌더 마크업 동일).
- `SessionDisclosureBanner` — Phase 13 사양 그대로 재구현 (warning/exhausted만 표시,
  role=alert + aria-live=polite, 닫기 시 동일 등급 숨김/악화 시 재표시, agk:pushstate 설정 링크,
  실패 시 조용히 숨김) — 단, 자체 폴링 없이 스토어 구독만으로 데이터 수신.
- `App.tsx` — `app-right-panel` 최상단 마운트 (Phase 13과 동일 위치). barrel export +
  배너 CSS (라이트/다크, 카드 팔레트 재사용).

- [x] 29.1 스토어 + 패널/배너 전환 + App 마운트 + CSS
- [x] 29.2 테스트: 스토어 6개 (즉시 fetch+인터벌 시작, 3구독자=인터벌 1개, 마지막 언서브스크라이브
  정리, 실패 시 마지막 성공값 유지, 회복, 초기 상태), 배너 8개 (healthy/초기 숨김, warning·exhausted
  표시+role, pushstate 링크, 실패 숨김, dismiss→동일등급 유지→악화 재표시, 완화 경유 리셋),
  패널 5개 기존 유지 (스토어 리셋 정비)
- [x] 29.3 검증: 스토어 6/6 + 배너 8/8 + 패널 5/5, 전체 프론트 **671 passed** (59 files),
  `tsc --noEmit` clean

**인수인계**: 폴링 주기 변경은 `disclosureStore.ts`의 `DISCLOSURE_POLL_INTERVAL_MS` 한 곳만 고치면
두 표면 모두 적용된다. 새 고지 표면(예: ChatPage 인라인)을 추가할 때도 컴포넌트에서 subscribe/unsubscribe
한 쌍만 호출하면 폴러에 자동 합류 — 개별 타이머를 만들지 말 것.

### Phase 30 — 소진 도달 시 브라우저 알림 (완료)

**목표**: 세션 고지 등급이 **처음** `exhausted`에 도달하면 OS 브라우저 알림을 1회 발송한다.
전환 감지는 유일한 레벨 전이 지점인 disclosureStore refresh에서 수행 (Phase 29 스토어 확장).

**설계**:
- `utils/exhaustedNotification.ts` (신규) — Notification 미지원/권한 denied·default면 조용히 무시
  (권한 요청 팝업을 띄우지 않는다 — 사용자가 이미 허용한 경우만 동작하는 비필수 UX).
  `tag: session-exhausted`로 중복 알림 대체, onclick → window.focus + `agk:pushstate /settings`
  (배너·동일 SPA 라우팅) + close. TS DOM 타입상 NotificationOptions에 onclick이 없어
  인스턴스에 할당.
- `disclosureStore` — `_notifiedExhausted` 에피소드 플래그: 전환 시점
  (warning→exhausted, null→exhausted, 실패 폴링 경유 도달)에만 발송, 연속 소진 폴링은 무시,
  완화(exhausted→그 외) 시 리셋해 다음 에피소드에서 재발송. 방어 코드: 응답이
  SessionDisclosure 형태가 아니면 실패 폴링으로 간주 (에러 플래그 세팅, 상태 미변경).

- [x] 30.1 util + 스토어 훅 + 방어 분기
- [x] 30.2 테스트: util 5개 (미지원, denied/default 무시, granted 생성+tag+본문,
  onclick focus+pushstate+close, 생성자 예외 안전), 스토어 3개 추가
  (첫 도달 1회+연속 소진 무시, 완화 후 재도달 재발송, 실패 폴링 경유 도달도 1회) —
  스토어 리셋에 신규 플래그 포함
- [x] 30.3 검증: 대상 4파일 27 passed + 전체 프론트 **679 passed**, `tsc --noEmit` clean

**인수인계**: 권한 요청 타이밍을 바꾸려면 (예: 설정 페이지에 명시적 버튼) `exhaustedNotification.ts`의
분기만 고치면 된다 — 스토어는 발송 성공/실패 불문 전환 시 1회만 호출하도록 플래그를 관리하므로
요청 UX 변경이 전이 로직에 영향을 주지 않는다.

### Phase 31 — /v1/messages 실시간 토큰 스트리밍 (완료)

**목표**: `stream=True`가 토큰을 생성 즉시 전송하게 한다. 기존 구현은
run_in_threadpool로 전체 생성을 join한 뒤 256자로 재분할하는 가짜 스트리밍이었다
(첫 SSE가 생성 총시간과 같이 늦음).

**변경 (messages_api.py)**:
- `stream_generate_async()` 신규 — ModelManager의 동기 Iterator를
  `starlette.iterate_in_threadpool`로 감싼 AsyncIterator. 각 next()가 스레드풀에서
  실행되어 이벤트 루프 비블록 + 도착 즉시 전달.
- `_stream_events()` 재작성 — message_start를 즉시 보내고, 이후 토큰을 그대로
  text_delta로 스트리밍. tool_use 판정은 완성 텍스트에 bridge 동기 파서 재사용
  (tool_call 태그는 토큰 경계에서 잘릴 수 있어 말미 판정이 안전). 스트리밍 중 예외 시
  지금까지의 부분 텍스트 + [API Error] 텍스트 블록으로 프로토콜 정상 종료 보장.
- 비스트리밍 경로/검증/가드/프롬프트 직렬화 로직은 불변.

**사고 이력 (복원 경위)**: 편집 과정에서 write_file이 모듈 전체를 함수 하나로 덮어써
원본이 소실되었다 (git untracked라 이력 없음). `__pycache__`의 .pyc에서 marshal로
코드 객체를 추출, 함수 목록·변수명·문자열 상수 161개·dis 바이트코드를 역산해
원본을 충실히 재구성했다. 검증: 함수 집합 pyc와 완전 일치, 계약 문자열 5개 존재,
기존 test_messages_api 13/13 통과. — 교훈: 신규 파일이라도 커밋 전 대량 overwrite 금지,
차편 편집 사용.

- [x] 31.1 stream_generate_async + 실시간 _stream_events
- [x] 31.2 tests/test_messages_streaming.py 6개: 버퍼링 없는 청크 전달 (첫 청크 < 75% 지점),
  이벤트 루프 비블록 (하트비트 코루틴 병행), 첫 text_delta가 생성 종료 전 도착,
  SSE 계약 유지, 중간 예외 시 message_stop 보장, _sse 포맷 불변
- [x] 31.3 검증: 대상 19 passed (기존 13 + 신규 6), ruff + mypy clean
- [x] 31.4 라이브 실측 (qwen3.8, ollama): message_start 0.03s → 첫 text_delta 0.34s
  (간격 0.31s = 모델 TTFT), 15개 delta가 0.39s에 걸쳐 점진 도착, 400토큰 생성에서도
  210 delta/4.58s 확산. 이전 구현이라면 첫 delta가 총시간과 동일했을 것.

**인수인계**: 스트리밍 청크 크기는 이제 프로바이더가 결정한다 (ollama는 토큰 단위).
SSE 클라이언트 쪽 버퍼링 의심 시 "message_start→첫 delta 간격"을 재면 된다 —
TTFT에 근접하면 실시간, 생성 총시간에 근접하면 어딘가 버퍼링.

### Phase 32 — QuantBadge 공유 컴포넌트 통합 (완료)

**목표**: ChatPage 모델 칩(`badge-quant`)과 Model Hub 등급 배지(`quant-quality-badge`)가
중복하던 마크업과 CSS 팔레트를 하나의 공유 컴포넌트로 통합한다 (Phase 15/18에서 양쪽 표면의
등급 체계는 통일했지만 마크업/CSS는 여전히 이중 유지).

**설계**:
- `components/shared/QuantBadge.tsx` 신규 — props: `quantization` + `variant`
  ("chip"=토큰 텍스트 표시 [ChatPage 팝오버], "grade"=등급 한 글자 [Model Hub spec 행]).
  등급 산정은 기존대로 quantQuality util 단일 진실원.
- 레거시 클래스 병기 전략 — 컴포넌트가 `quant-badge chip badge-quant q-balanced`처럼
  기존 클래스를 함께 출력해 기존 CSS 선택자·기존 테스트 단언이 그대로 호환.
- CSS: 두 팔레트(badge-quant 6블록 + quant-quality-badge 11블록 + 다크 중복)를
  `.quant-badge` 단일 팔레트로 통합, 등급 셀렉터 3중 병기(신규+레거시 2종)로 잔여 호환 유지.
  중괄호 균형 검증 완료.

- [x] 32.1 QuantBadge 컴포넌트 + barrel export + 단일 CSS 팔레트
- [x] 32.2 ChatPage 2곳 / ModelHubPage 1곳 교체 (인라인 span 제거)
- [x] 32.3 테스트: QuantBadge 단위 5개 신규 (chip/grade 클래스·툴팁·등급 문자 매핑·
      기본값·extra 클래스), 기존 ChatPageQuantBadge 3개 + ModelHub 5개 무수정 통과
      (레거시 클래스 병기 덕)
- [x] 32.4 검증: 전체 프론트 **684 passed**, `tsc --noEmit` clean

**인수인계**: 새 표면에 양자화 배지가 필요하면 `QuantBadge`를 import해 쓸 것 —
자체 span+클래스를 만들지 말 것. 팔레트 변경은 index.css의 `.quant-badge` 블록 한 곳.
레거시 클래스는 테스트·CSS 호환용이며 다음 대규모 스타일 정리 때 제거 후보.

### Phase 33 — QuantBadge 라이브 시각 검증 + 다크 팔레트 버그 수정 (완료)

**목표**: 통합된 `QuantBadge`를 실서버 + 대시보드로 띄워 ChatPage 팝오버와 Model Hub 배지가
라이트/다크 양쪽에서 **동일한 팔레트**를 쓰는지 시각 검증한다.

**검증 결과 (실서버 :8400 + vite :5199, 실제 모델 20개, `VITE_BACKEND_URL` 연결)**:
- ChatPage 팝오버: 9개 칩 모두 `quant-badge chip badge-quant q-{level}` 단일 클래스,
  Q8_0=premium(녹색), UD-Q4_K_XL/UD-IQ4_XS/Q4_K_M=balanced(보라) — 스크린샷 확인.
- Model Hub: 20개 카드 전부 `quant-badge grade quant-quality-badge q-{level}`,
  P=premium(녹색)/B=balanced(보라)/?=unknown(회색) — 스크린샷 확인.
- **교차 일치**: 두 표면의 등급별 computed color가 정확히 동일
  (premium `rgb(74,222,128)`, balanced `rgb(167,139,250)`, unknown `rgb(148,163,184)`).
- 라이트: `data-theme` 부재 시 base 팔레트 적용 (premium `#15803d`, balanced `#6d28d9`).
  단, 이 앱은 `:root`가 `#0a0c10` 고정이라 **런타임 라이트 전환 스위치가 없음** —
  `data-theme`/`html.dark`/`body.dark` 셀렉터는 명시적 다크 오버라이드용으로만 존재.

**발견·수정한 버그**: Phase 32 통합 당시 다크 팔레트가 5개 등급을 **단일 회색 `#94a3b8`로
평탄화** (`.model-group-title`과 함께 한 선택자 그룹으로 묶임) — 등급 색상 코딩이 배지의
존재 이유인데 다크에서 소멸. 라이브에서 `sameColorFlattened=true`로 재현 확인 후 수정.

- [x] 33.1 다크 팔레트를 등급별 5색으로 복원 (하우스 스타일: 배경 알파 0.2 + 텍스트 400-shade
      premium `#4ade80` / high `#38bdf8` / balanced `#a78bfa` / compact `#fb923c` / unknown `#94a3b8`),
      `.model-group-title` 다크 규칙 분리 복원
- [x] 33.2 검증: QuantBadge 테스트 5개 통과, `tsc --noEmit` clean, CSS 중괄호 균형 2414/2414
- [x] 33.3 실서버 시각 검증 (위 표) — 두 표면 × 라이트/다크 × 등급 3종

**인수인계**: 다크 테마는 `:root[data-theme="dark"]` 단일 경로로만 잡혀 있음. `html.dark`/`body.dark`를
쓰는 표면이 생기면 이 배지 팔레트도 `:is()` 병기로 확장할 것. 런타임 라이트 토글을 추가하려면
CSS 루트 변수 전체가 라이트로 뒤집혀야 하므로 배지 팔레트만으로는 불가 — 테마 시스템 도입 과제.

### Phase 34 — 실클라이언트 E2E: Claude Code ↔ 로컬 모델 툴 호출 (완료)

**목표**: P3 백로그의 "실제 클라이언트 연결" 항목 — `agk start claude` 브리지 환경변수로
실제 Claude Code CLI를 로컬 모델에 연결해 멀티턴 에이전트 세션에서 툴 호출이
왕복하는 것을 검증한다.

**환경**: 백엔드 :8400 (실서버), 모델 `qwen3.8:latest` (실행 중),
CLI `.tmp/claude_cli/node_modules/.bin/claude` v2.1.260 (로컬 설치, @anthropic-ai/claude-code),
브리지 env = `ANTHROPIC_BASE_URL=http://127.0.0.1:8400` + `ANTHROPIC_API_KEY=ssak-ai-local`
+ `ANTHROPIC_MODEL=qwen3.8:latest` (agent_bridges.py claude 스펙 그대로).
샌드박스 작업디렉터리 `.tmp/claude_e2e_ws`에서 `--print --output-format json` 모드로 실행.

**사전 검증**: /v1/messages 직접 호출로 모델이 `tools` 배열을 받고 `stop_reason=tool_use` +
`toolu_*` 블록(`{"city":"Seoul"}` 파싱 성공)을 반환함을 확인 — get_weather 단일 툴 프로브.

**결과 (2개 시나리오 모두 통과)**:

| 시나리오 | 툴 | turns | 최종 응답 | 판정 |
|:---|:---|---:|:---|:---|
| note.txt 비밀코드 | Read | 2 | `SECRET-CODE-7391` (파일 내용 그대로) | ✅ 파일은 모델 컨텍스트에 없음 → 툴 왕복으로만 획득 가능 |
| count_check.txt 숫자 | Bash | 2 | `7` (cat 실행 결과) | ✅ 동일 — permission_denials 0 |

양쪽 모두 `stop_reason=end_turn`, `terminal_reason="completed"`, exit 0.
1턴 = 모델이 tool_use 반환 → CLI가 실제 툴 실행 → 2턴 = tool_result 반영해 최종 답변.
스트리밍 경로(Phase 31)도 실측 — CLI는 기본 streaming으로 호출.

**관찰/제약**:
- stderr에 `[claude-code:unrecognized_model]` 경고 — 로컬 모델명을 CLI가 몰라도 동작엔 무해
  (provider "firstParty"로 처리). usage의 costUSD는 CLI 내부 추정치일 뿐 실과금 없음.
- daemon 모드 uvicorn의 access log가 stdout 버퍼링으로 비어 있음 — 서버 측 요청 로그가
  필요하면 `PYTHONUNBUFFERED=1`로 기동할 것. 행위 증명(turns/응답 내용)으로 대체 검증함.
- CLI 프롬프트는 stdin 파이프로 전달할 것 (`--print` + 위치인자 조합은 파싱 실패).

- [x] 34.1 모델 tool_use 직접 프로브 (tools 배열 → tool_use 블록)
- [x] 34.2 Claude Code CLI 연결 + Read 툴 멀티턴 시나리오 통과
- [x] 34.3 Bash 툴 시나리오 통과 (두 번째 툴로 일반성 확인)
- [x] 34.4 결과 JSON 보존: `.tmp/claude_e2e_result.json`, `.tmp/claude_e2e_result2.json`

**인수인계**: 재현은 Phase 34 환경 블록 그대로. 프롬프트는 stdin 파이프, `--allowedTools`로
툴 스코프 제한, `--max-turns`로 루프 상한. 로컬 모델 교체 시 `ANTHROPIC_MODEL`만 변경.
Claude Code가 보내는 시스템 프롬프트+툴 정의는 ~52k 토큰 — 컨텍스트 32k 미만 모델은 부적합.

### Phase 35 — 실클라이언트 E2E: Codex ↔ 로컬 모델 + Responses API 브리지 (완료)

**목표**: `agk start codex` 브리지로 실제 Codex CLI를 로컬 모델에 연결해 툴 사용 세션을 검증.

**프로토콜 발견 (핵심)**:
1. 기존 `/v1/chat/completions`는 내부 오케스트레이터 경로 — 요청 body의 ``tools``를
   소비하지 않고 ``tool_calls``를 반환하지 않음 → Codex 연결 불가.
2. Codex CLI 0.150+는 ``wire_api="chat"``를 **제거**하고 Responses API만 지원
   (openai/codex#7782). ``{base_url}/responses`` 호출이 유일한 경로.
3. 따라서 두 개의 신규 계층을 구현:
   - `/v1/chat/completions`에 tools passthrough 분기 (body에 tools 있으면 오케스트레이터
     대신 `openai_tool_bridge`로 위임 — 기존 클라이언트 무회귀)
   - `/v1/responses` 신규 엔드포인트 (`openai_responses_bridge` + `responses_api.py`) —
     function_call/function_call_output item 왕복 + SSE 이벤트
     (response.created → output_item.added → output_text.delta /
     function_call_arguments.delta → output_item.done → response.completed)
4. RobustToolParser에 미종료 코드펜스 수리 추가: 닫는 ```` ``` ```` 없이 끝나고 짝 없는
   ``</tool_call>``만 붙는 27B 모델 말단 변형 (Codex E2E 1차 실행에서 실측,
   `repaired=True`로 복원) — 3개 브리지가 공유하는 단일 파서라 전 경로에 효과.

**Codex 연결 방법** (CLI가 OPENAI_BASE_URL env를 읽지 않으므로 config 오버라이드 사용):
```
OPENAI_API_KEY=ssak-ai-local codex exec --sandbox read-only --skip-git-repo-check \
  -c model_provider=ssak -c 'model_providers.ssak.base_url="http://127.0.0.1:8400/v1"' \
  -c 'model_providers.ssak.env_key="OPENAI_API_KEY"' \
  -c 'model_providers.ssak.wire_api="responses"' -m qwen3.8:latest "<prompt>" < /dev/null
```
주의: exec 모드에서 stdin이 파이프/리다이렉트면 stdin을 끊어야 함 (`< /dev/null`) —
그렇지 않으면 프롬프트를 받고도 stdin 대기로 무한 대기.

**결과 (2개 시나리오 모두 통과, exit 0)**:

| 시나리오 | 툴 | 최종 응답 | 판정 |
|:---|:---|:---|:---|
| note.txt 비밀코드 | exec_command (cat) | `SECRET-CODE-7391` | ✅ 툴 왕복으로만 획득 가능 |
| count_check.txt 숫자 | exec_command (cat) | `7` | ✅ 동일 |

양쪽 모두 모델이 json 코드펜스로 exec_command 호출 → 파서 추출 → function_call item으로
Codex 전달 → Codex가 샌드박스에서 실행 → function_call_output 반영해 최종 답변.

- [x] 35.1 `/v1/chat/completions` tools passthrough (openai_tool_bridge + chat.py 분기)
- [x] 35.2 `/v1/responses` 신규 엔드포인트 (openai_responses_bridge + responses_api.py + 라우터 등록)
- [x] 35.3 RobustToolParser 미종료 펜스 수리 + 회귀 테스트 2건
- [x] 35.4 테스트: openai_tool_bridge 25건 + openai_responses_bridge 16건 신규,
      기존 messages/streaming/bridge/파서 스위트 94건 통과, ruff + mypy clean
- [x] 35.5 Codex CLI 라이브 E2E 2 시나리오 통과 (결과: `.tmp/codex_e2e_last*.txt`)

**인수인계**:
- `agk start codex`가 출력하는 env(OPENAI_BASE_URL 등)는 참고용 — Codex CLI 실연결은
  위 config 오버라이드가 정석. 브리지 플랜 출력에 이 안내를 추가하는 후속 과제.
- `/v1/responses`·tools passthrough의 streaming은 buffer-then-emit (판정이 완성 텍스트
  기반 — anthropic 경계와 동일 한계). 실시간 TTFB가 필요하면 Phase 31의
  stream_generate_async 방식으로 확장.
- function이 아닌 Responses 내장 툴(web_search 등)은 카탈로그에서 생략됨.

### Phase 36 — qwen3.8을 Claude Code 모델 카탈로그에 매핑 + 권장 env 블록 문서화 (완료)

**목표**: `[claude-code:unrecognized_model]` 경고의 공식 해소 경로를 역발굴해 적용하고,
검증된 권장 브리지 env 블록을 `agent_bridges.py`에 문서화/구현한다.

**역발굴 (claude.exe 2.1.260 문자열 분석)**:
- remedy 문자열: "...isn't described by this version's model catalog; update Claude Code,
  or map it with **behavesAs on a modelPicker row** (or modelOverrides...)".
- settings 스키마: `modelPicker` = `{"options": [{model, label?, description?, behavesAs?}],
  "replaceBuiltInOptions?"}` — **managed/--settings/사용자 설정에서만 유효** (프로젝트 체크아웃 무시).
  `behavesAs` 값은 CC 내장 모델 키 (claude-sonnet-4-6 등).
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS`: 미등록 모델은 CC가 보수 기본 윈도로 자동 압축 —
  실제 윈도를 env로 등록해야 함 (claude.exe 내장 안내 문자열 확인).

**라이브 검증 (qwen3.8:latest, :8400)**:

| 실행 | 구성 | 결과 | stderr |
|:---|:---|:---|:---|
| 1 | env 블록만 (MAX_CONTEXT_TOKENS=262144 + SMALL_FAST + DEFAULT_*) | "OK" 응답, 정상 | `unrecognized_model` 경고 **여전히** 출력 |
| 2 | env 블록 + `--settings` modelPicker behavesAs 행 | "OK" 응답, 정상 | **경고 완전 소멸** |

env 블록만으로 기능은 동일하지만 카탈로그 경고는 behavesAs 매핑으로만 없어진다 —
둘은 상호 보완 (env = 윈도/별칭, settings = 카탈로그 등록).

**구현**:
- `agent_bridges.py` claude 스펙 env_vars 확장: `CLAUDE_CODE_MAX_CONTEXT_TOKENS
  ({context_window})`, `ANTHROPIC_SMALL_FAST_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL`,
  `ANTHROPIC_DEFAULT_SONNET_MODEL` (후자 3개는 {model} 재사용).
- `resolve_bridge`에 `context_window` 인자 추가 (0 → 200000 = CC 보수 기본값) +
  **/v1 접미사 프로토콜 버그 수정**: anthropic 계열(claude/openclaw)은 클라이언트가
  직접 /v1/messages를 붙이므로 base에 /v1이 있으면 /v1/v1/messages 404 —
  openai 계열만 /v1 접미사 유지 (Phase 34/35 라이브 동작과 일치, 기존 테스트 기대치는
  버그를 고정하고 있었음).
- `agk start claude`가 ModelRegistry의 context_length를 조회해 전달 (ollama 태그
  `:latest` 정규화 대조 — 레지스트리는 `qwen3.8`로 등록, 실측 262144 반영 확인).
- `format_bridge_plan`: claude 플랜에 modelPicker/behavesAs 설정 힌트, codex 플랜에
  Responses config 오버라이드 레시피(Phase 35) 포함.
- 모듈 docstring에 검증된 권장 env 블록 + settings JSON + codex 레시피 전체 문서화.

- [x] 36.1 claude.exe 문자열 역발굴 (behavesAs/modelPicker/MAX_CONTEXT_TOKENS 스키마)
- [x] 36.2 라이브 A/B: env-only vs +behavesAs settings (경고 소멸 확인)
- [x] 36.3 브리지 env 확장 + /v1 접미사 버그 수정 + 컨텍스트 윈도 조회
- [x] 36.4 테스트: agent_bridges 14건 (기대치 갱신 + 3건 신규), cli_smoke/e2e/messages
      회귀 44건 통과, ruff + mypy clean

**인수인계**: behavesAs 설정은 사용자 설정만 유효 — 브리지가 자동 생성하지 않으므로
플랜 출력의 JSON을 복사해서 ~/.claude/settings.json에 붙여야 한다. modelOverrides는
provider id 매핑용으로 claude.exe가 안내하지만 로컬 모델명은 카탈로그 id가 아니라
behavesAs 행이 정규 경로. ANTHROPIC_DEFAULT_OPUS_MODEL/FABLE_MODEL도 존재하나
로컬 브리지에는 haiku/sonnet 매핑으로 충분.

### Phase 38 — /v1/messages 실시간 스트리밍 재검증 (완료)

**목표**: "마지막 남은 P3 항목"으로 지목된 실시간 토큰 스트리밍이 실제로 미완인지 확인.

**결과**: **이미 완료 (Phase 31)** — §6 체크리스트에 미반영되어 미완으로 보였을 뿐.
- `stream_generate_async`(starlette.iterate_in_threadpool)가 동기 `stream_generate`를
  버퍼링 없이 비동기 전달 — 가짜 스트리밍(run_in_threadpool + "".join)이 아님.
- `_stream_events`가 도착 즉시 text_delta로 내보내고, 완성 텍스트로 tool_use 판정
  (content_block_start/input_json_delta + message_delta stop_reason + message_stop).

**라이브 재검증 (qwen3.8:latest, :8400, 6줄 시 생성)**:

| 지표 | 값 |
|:---|:---|
| time-to-first-delta | **0.51s** |
| 전체 생성 시간 | 1.44s |
| text_delta 개수 | 20 |
| stop_reason | end_turn |
| 조립 결과 | 65자 시, 정상 |

첫 토큰이 전체 생성 완료 전에 도착 → 진짜 실시간 스트리밍.
테스트: `test_messages_streaming.py` 19건 (실시간성 단언 포함) 통과.

- [x] 38.1 스트리밍 구현/테스트 상태 확인 (Phase 31 코드 무회귀)
- [x] 38.2 라이브 time-to-first-token 측정 (0.51s < 1.44s)
- [x] 38.3 §6 체크리스트 완료 처리 + 이번 항목은 사실상 종결

**인수인계**: tool_use 판정은 완성 텍스트 기반이라, 툴 호출 스트리밍 중에는
원시 tool-call 태그가 순간적으로 text_delta로 노출될 수 있음 (Phase 31에 문서화된
허용 트레이드오프 — Claude Code는 tool_use 블록+stop_reason만 소비).
OpenAI 경로(/v1/chat/completions tools, /v1/responses)는 여전히 buffer-then-emit
(Phase 35 한계) — 원하면 Phase 31 래퍼로 동일 확장 가능.

### Phase 39 — ChatPage 칩에 한 글자 등급 아이콘 추가 (완료)

**목표**: ChatPage 모델 칩이 등급 색상만 쓰던 것에서, Model Hub의 grade 배지처럼
한 글자 등급(P/H/B/C/?)을 칩 내부에 함께 표시해 두 표면의 등급 아이콘 스타일을 통일.

**구현 (최소·무회귀)**:
- `QuantBadge` chip 변형에 `data-grade={info.grade}` 속성 추가 (DOM은 토큰 텍스트 그대로).
- CSS `.quant-badge.chip::before`로 한 글자 등급 아이콘 렌더 — `content: attr(data-grade)`.
  `color: inherit` + `border: 1px solid currentColor`로 칩의 등급 색상을 상속받아
  테두리·글자에 사용 (자체 color를 덮어쓰면 currentColor가 잘못됨 — 실측에서
  `background: currentColor`가 자기 color(#0a0c10)로 해석되어 다크 온 다크가 되는 버그를
  잡고 outlined 방식으로 수정).
- ::before를 쓰면 칩의 textContent(토큰)가 유지되어 `getByText('UD-Q4_K_XL')`/`badge-quant`/
  `q-balanced` 단언이 무회귀.

**라이브 검증**: 다크 테마 칩이 `[B] UD-IQ4_XS`로 렌더 — 보라 테두리+보라 'B' 아이콘 + 토큰.
::before computed style: content="B", border rgb(167,139,250), color rgb(167,139,250),
bg rgba(255,255,255,0.05). 스크린샷 확인.

- [x] 39.1 QuantBadge chip에 data-grade + ::before 등급 아이콘
- [x] 39.2 테스트: QuantBadge 2건·ChatPageQuantBadge 1건 추가 (data-grade 단언), 전체 **686 passed** (61파일)
- [x] 39.3 tsc --noEmit clean + 라이브 스크린샷 확인

**인수인계**: 등급 글자는 ::before라 DOM 조회 불가 — 단언은 `data-grade` 속성으로.
접근성상 장식 아이콘으로 간주(툴팁이 등급을 전달). 칩 안 아이콘 크기를 키우려면
`.quant-badge.chip::before`의 width/height만 조정. (이전 실패한 디자인 오버홀 요청은
Phase 39와 무관 — 별도 진행.)

### Phase 40 — 두 양자화 배지 표면 라이트/다크 시각 검증 (완료)

**목표**: ChatPage 칩(등급 아이콘, Phase 39)과 Model Hub grade 배지를 실서버로 띄워
라이트/다크 양쪽에서 일관성을 검증한다 (Phase 33 재검증 + 등급 아이콘 반영).

**환경**: 실서버 :8400 + vite :5199 (`VITE_BACKEND_URL`), 실제 모델 20개.
`data-theme` 토글로 다크/베이스(라이트) 팔레트 전환.

**검증 결과**:

| 표면 | 등급 | 다크 | 라이트 |
|:---|:---|:---|:---|
| ChatPage 칩 | P | 아이콘 rgb(74,222,128) | rgb(21,128,61) `#15803d` |
| ChatPage 칩 | B | 아이콘 rgb(167,139,250) | rgb(109,40,217) `#6d28d9` |
| Model Hub | P | rgb(74,222,128) | rgb(21,128,61) `#15803d` |
| Model Hub | B | rgb(167,139,250) | rgb(109,40,217) `#6d28d9` |
| Model Hub | ? | rgb(148,163,184) | rgb(90,94,108) |

**교차 일관성**: 등급별 computed color가 두 표면에서 **정확히 동일**
(다크 premium/balanced = rgb(74,222,128)/rgb(167,139,250), 라이트 = #15803d/#6d28d9).
스크린샷 확인: 다크 칩 `[B] UD-IQ4_XS` 보라 아이콘, Model Hub 양자화 셀 B(보라)/P(초록).

**노트**: 앱은 `:root`가 `#0a0c10` 고정이라 런타임 라이트 토글이 없음 (Phase 33과 동일).
"라이트"는 `data-theme` 부재 시 적용되는 base 팔레트 토큰 기준 — 두 표면 모두 동일.

- [x] 40.1 ChatPage 칩 등급 아이콘 다크/라이트 computed + 스크린샷
- [x] 40.2 Model Hub grade 배지 다크/라이트 computed + 스크린샷
- [x] 40.3 교차 일관성 (등급별 동일 색상) 확인

**인수인계**: 칩 아이콘과 Model Hub 배지가 같은 등급 색상을 쓰도록 유지할 것 —
팔레트 수정 시 `.quant-badge` 한 블록만 바꾸면 두 표면 모두 반영.

### Phase 41 — Codex 실클라이언트 E2E 재검증 (완료)

**목표**: P3 백로그의 "Codex 클라이언트 검증만 잔여" 항목을 해소 — Phase 35에서
이미 구현·통과했지만 §6 백로그에 미반영된 Codex E2E를 재실행해 확정한다.

**환경**: 실서버 :8400, `qwen3.8:latest`, Codex CLI 0.150.1 (`~/.local/bin/codex`),
Responses API 브리지 (`/v1/responses`, Phase 35). config 오버라이드:
`model_providers.ssak.base_url="http://127.0.0.1:8400/v1"` + `wire_api="responses"`.

**결과 (2 시나리오 모두 exit 0)**:

| 시나리오 | 툴 | 최종 응답 | 판정 |
|:---|:---|:---|:---|
| note.txt 비밀코드 | exec_command (cat) | `The secret code is \`SECRET-CODE-7391\`.` | ✅ 툴 왕복으로만 획득 가능 |
| count_check.txt 숫자 | exec_command (cat) | `The file \`count_check.txt\` prints the number **7**.` | ✅ 동일 |

`/v1/responses` 라우트 존재 확인(빈 바디 400 — 404 아님), 모델 존재 확인.
§6 백로그의 "Codex 검증만 잔여" → **완료** 처리.

- [x] 41.1 /v1/responses 라우트 + 모델 확인
- [x] 41.2 Codex CLI 2 시나리오 통과 (비밀코드 + 숫자)
- [x] 41.3 §6 백로그 Codex 완료 처리

**인수인계**: Codex E2E는 `scripts/e2e_claude_bridge.sh`(Phase 37)와 같은 패턴으로
자동화하면 `scripts/e2e_codex_bridge.sh` — config 오버라이드 레시피는 Phase 35 참조.
두 에이전트 브리지(Claude Code + Codex) 모두 로컬 모델 툴 호출 검증 완료.

### Phase 42 — Model Hub: 실행 중 모델을 퀀트 티어 필터에서 면제 (완료)

**목표**: 품질 등급 필터로 브라우징할 때 실행 중(활성) 모델이 숨지 않도록 한다.
(실행 중 모델은 quantization이 비어 unknown(?)으로 등급돼 '균형 이상' 등에 걸리기 쉬움)

**구현**: `ModelHubPage.tsx`의 `filteredModels`에서 퀀트 티어 조건에 `m.status !== 'running'`
가드 추가 — 실행 중 모델은 등급 필터와 무관하게 항상 표시.

**라이브 검증 (:8400 + vite :5199)**:
- '균형 이상' 클릭 → 실행 중 `qwen3.8:latest` **표시 유지** (14개 표시).
- '프리미엄만' 클릭 → 실행 중 `qwen3.8:latest` **표시 유지** (7개 표시) —
  이 모델은 Q4_K_M(balanced)라 프리미엄 필터에 원래 걸리지만 면제로 계속 노출.
- 스크린샷 확인: '균형 이상' 활성 시 상단에 '실행 중' 배지 + 카드 표시.

- [x] 42.1 실행 중 모델 티어 면제 구현 (m.status !== 'running' 가드)
- [x] 42.2 테스트: 기존 균형 이상 테스트 기대치 갱신 + 신규 'running 모델은 어떤 티어에서도 숨지 않음' 1건
      → ModelHubPage 6건 통과, 전체 관련 스위트 16건, tsc clean
- [x] 42.3 라이브 확인 (균형 이상/프리미엄만에서 실행 모델 유지)

**인수인계**: 등급 필터는 '실행 중 모델은 항상 노출'이 기본. 대안이던
'unknown 포함' 토글은 채택하지 않음 — 활성 모델 숨김 방지가 더 직접적.
비실행 unknown 모델은 여전히 등급 필터에 걸림 (의도된 동작).

### Phase 43 — Model Hub: 디스크/VRAM 정렬 + 최소 용량 범위 필터 (완료)

**목표**: 품질 pill 옆에 디스크 용량·VRAM 요구량 기준 정렬과 최소 GB 범위 필터를 추가해
용량 관점 브라우징을 지원한다.

**구현** (`ModelHubPage.tsx`):
- `HubSortKey` + `HUB_SORT_OPTIONS`: 기본순/디스크 작은순·큰순/VRAM 작은순·큰순/이름순.
- 디스플레이 모델에 숫자 필드 `diskSizeGb`/`vramGb` 추가 (VRAM 요구량 ≈ params × 0.7 GB,
  params 미보고 시 디스크 용량으로 근사).
- `minDiskGb`/`minVramGb` 하한 필터 — **용량 미보고(0) 모델은 제외하지 않음**
  (Ollama 메모리 모델 등이 필터에 묻히지 않도록; Phase 42의 '활성 모델 숨김 방지'와 같은 원칙).
- 필터바에 정렬 select + `디스크 ≥ [] GB` / `VRAM ≥ [] GB` 숫자 입력 + 조건 존재 시 '✕ 초기화' 버튼.
- 카드 스펙 행에 'VRAM 요구' 배지 추가.

**라이브 검증 (:8400 실제 20개 모델 + vite :5199)**:
- '디스크 작은순' → 미보고(running Ollama) 먼저, 0.06GB → 0.09GB 순 확인.
- '디스크 ≥ 30' → 5개로 축소 + '✕ 초기화' 버튼 등장 → 클릭 시 20개 복원, 기본순 복귀.
- '디스크 큰순' 스크린샷: 정렬 select + 디스크/VRAM ≥ 입력 + 초기화 버튼 렌더 확인.

- [x] 43.1 정렬 + 범위 필터 로직 및 UI 컨트롤 구현 (초기화 버튼 포함)
- [x] 43.2 테스트 +4건: 디스크 오름/내림 정렬, VRAM 내림 정렬, 디스크 하한 필터+초기화,
      VRAM 하한 필터 → ModelHubPage 10건 통과, 전체 691건(61파일), tsc clean
- [x] 43.3 라이브 확인 (정렬 순서 실측, 하한 필터 축소/복원, 스크린샷)

**인수인계**: VRAM 요구량은 파라미터 기반 근사(params × 0.7) — 실행 중 실측 VRAM이 아니므로
정확한 VRAM 데이터가 백엔드에서 오면 필드만 교체하면 된다. '최대' 상한 필터는 요구 없어 미포함.

### Phase 44 — Model Hub 티어 pill 라이브 테마 검증 + 다크 전용 팔레트 확인 (완료)

**목표**: 품질 티어 pill 행(Phase 28)과 Phase 43 필터 행을 실제 백엔드(:8400, 20개 모델) +
vite(:5199)에서 시각 검증한다.

**검증 결과**:
- 4개 pill 모두 정상 동작: 품질 전체(20) → 균형 이상(14개 표시) → 높음 이상(7개 표시) →
  프리미엄만(7개 표시) — 실행 중 qwen3.8(Q4_K_M)은 프리미엄에서도 면제로 표시(Phase 42).
- 활성 pill 스타일: accent 배경 + 3px ring(`rgba(124,58,237,0.18)`) — 의도대로 렌더.
- 등급 배지(quant-badge)는 테마 플래그에 따라 실제로 색이 바뀜:
  base `#6d28d9`(라이트 톤) ↔ dark `#a78bfa`/`rgb(167,139,250)`.

**중요 발견 — 앱은 다크 전용 팔레트다**:
- `index.css`의 `:root`가 곧 다크 팔레트(`--bg-primary:#0a0c10` 등)이며,
  `data-theme="light"`(또는 `prefers-color-scheme: light`) 정의가 **존재하지 않는다**.
- `data-theme="dark"` 블록(:14742~)은 CSS 변수 재정의가 아니라 컴포넌트 단위
  하드코딩 색(`#0d1117`, `#161b22`…)의 overlay로, base `:root`와 거의 동일한 색이라
  토글해도 pill/카드/사이드바 computed style이 **불변** — 라이브 실측으로 확인.
- 과거 Phase 33/40의 "라이트(base) 톤" 관찰은 사실 base `:root` 안의 개별 컴포넌트
  기본색(예: quant-badge 라이트 톤 fallback `#f1f5f9`)을 가리킨 것 — 실제 라이트 모드는 없음.
- `.unsloth-desktop-sidebar.light-mode` 등 고아 라이트 스타일 일부 존재하나 사용처 없음.

**의미**: '라이트 테마 검증'은 현재 구조에서는 정의 불가 — pill 행은 앱의 단일(다크)
팔레트에서만 렌더되며, 두 플래그 상태 모두 동일하게 정상 렌더됨을 확인했다.

- [x] 44.1 라이브 기동(:8400+:5199) + 4개 pill 동작/스타일 실측
- [x] 44.2 테마 플래그 토글 A/B — pill·카드·사이드바 computed style 불변 확인(다크 전용 팔레트)
- [x] 44.3 스크린샷 3장(균형 이상 다크/베이스, 프리미엄만) + 계획서 기록

**인수인계**: 진짜 라이트 테마를 원하면 `:root`에 라이트 팔레트 변수를 정의하고
`[data-theme="light"]`로 스왑하는 방식(quant-badge의 라이트/다크 이중 팔레트를 이미 갖춤)으로
설계해야 한다 — 기존 `data-theme="dark"` overlay 블록은 그대로 두어도 무해. 런타임 테마
토글 UI/스토어도 없으므로 별도 작업 필요.

### Phase 57 — CI mlx 매트릭스 AGK_TEST_PYTHON 고정 (완료)

**목표**: 드리프트 체크와 스모크 테스트가 CI에서 **같은 고정 인터프리터**를 쓰게 한다 —
`tests/_cli_subprocess.py`가 1순위로 존중하는 `AGK_TEST_PYTHON`을 워크플로 레벨에서 설정.

**변경**:
- `ci.yml` `test` job (os × deps 매트릭스, mlx leg 포함): job-level `env: AGK_TEST_PYTHON:
  ${{ github.workspace }}/.venv/bin/python`. uv sync가 만드는 .venv를 가리키므로
  서브프로세스가 pytest와 동일 의존성 세트를 공유하고, uv-run-inside-uv-run 네스팅이 사라진다.
- `weekly-drift.yml` `mlx-lm-drift` job: 동일 env. 최신 mlx-lm 오버레이 설치가 .venv에
  들어가므로, 고정 없이는 `--help` 출력을 다른 환경에서 받아와 드리프트 오판 가능.
- `tests/test_mlx_command_flags.py`: `_valid_flags()`가 남발하던 bare `sys.executable`을
  `python_invocation(project=True)`로 마이그레이션 — 드리프트 테스트도 AGK_TEST_PYTHON을
  존중하게 돼 위 env 고정이 실제로 적용된다.

**검증**:
- `test_mlx_command_flags` 4 passed (mlx 환경), `test_unsloth_script_api_drift` 7+7(스킵) 유지.
- AGK_TEST_PYTHON 설정 시 헬퍼가 해당 경로를 정확히 반환하는지 확인 (설정 전엔 uv run 폴백).
- 드리프트+스모크 3스위트(24 테스트)를 env 설정/미설정 양쪽으로 실행 — 모두 통과.
- 두 워크플로 YAML 파싱 + env 키 실재 확인, ruff/mypy clean.

- [x] 57.1 CI test job + weekly-drift mlx job에 AGK_TEST_PYTHON 설정
- [x] 57.2 test_mlx_command_flags를 헬퍼로 마이그레이션 (마지막 sys.executable 잔존 제거)
- [x] 57.3 로컬 검증 + YAML 검증 + 계획서 기록

**인수인계**: AGK_TEST_PYTHON은 `_cli_subprocess.resolve_interpreter`의 1순위다 — 새 서브프로세스
테스트는 이 env가 설정된 CI에서도 헬퍼만 쓰면 자동으로 같은 인터프리터를 공유한다. .venv 경로는
macOS/리눅스 공통(`.venv/bin/python`)이므로 매트릭스 분기 불필요. Windows 러너를 추가한다면
`.venv/Scripts/python.exe` 분기가 필요하다.

### Phase 56 — allowed_roots / WORKSPACE_ROOT 보안 계약 고정 (완료)

**목표**: git_api.py·filesystem.py가 재작성돼도 경로 보안 계약이 조용히 무너지지 않게,
엔드포인트 테스트 우연 검증을 넘어 **계약 자체**를 모듈 레벨에서 고정한다.

**새 스위트** `tests/test_path_contracts.py` (13 테스트, 5 섹션):

- **A. allowed_roots() 구성 (4)** — 첫 루트는 config.paths.project_root / 레지스트리
  프로젝트 포함 + 중복 제거 순서 유지 / `AGK_ALLOWED_ROOTS`(os.pathsep) env 루트 추가 /
  레지스트리 예외 시에도 config 루트로 살아남음(다운그레이드 없음).
- **B. resolve_allowed_path() (2)** — **모든** 루트를 검사(첫 루트만 검사하는 재작성은
  등록 프로젝트 경로를 전부 차단해 기능도 깨짐) / `..` 이탈 거부.
- **C. git_api._resolve_git_dir (4)** — 루트 밖 + .git 없음 → 403 / **루트 밖 독립 git
  저장소 허용은 문서화된 carve-out**(제거하려면 보안 결정 필요 — 테스트가 이를 명시) /
  roots 밖 활성 프로젝트 무시(TOCTOU 방어) / 유효 활성 프로젝트가 상대 경로 기준 확장.
- **D. filesystem.WORKSPACE_ROOT (2)** — `_resolve_workspace_path`가 런타임 WORKSPACE_ROOT
  기준으로 이탈 403 / 상대 경로 내부 해석.
- **E. 교차 일관성 (1)** — allowed_roots()가 보고한 모든 루트를 git 경계도 받아야 함
  (두 보안면이 서로 다른 allowlist를 갖는 재작성 차단).

**뮤테이션 검증 (7종 변이 전부 차단 확인)**:

| 변이 | 결과 |
|:--|:--|
| M1 config 루트가 첫 원소 아님 | ✅ 잡음 |
| M2 중복 제거 제거 | ✅ 잡음 |
| M3 첫 루트만 relative_to | ✅ 잡음 |
| M4 레지스트리 예외 전파 | ✅ 잡음 |
| G1 .git carve-out 제거 | ✅ 잡음 |
| G2 stale active 가드 제거 | ✅ 잡음 (1차 시도 실패 후 강화 — 아래) |
| G3 git_api 자체 allowlist 하드코딩 | ✅ 잡음 |

**작성 중 발견한 함정 (문서화 가치)**: 스태일 프로젝트 테스트의 첫 버전은
`allowed_roots()`가 **레지스트리 프로젝트를 포함**한다는 사실(A2)과 모순됐다 —
list_projects에 있는 경로는 항상 roots에도 있으므로 "roots에 없는 등록 프로젝트"는
평소 존재하지 않는다. 가드의 실제 역할은 allowed_roots()와 get_active_project()
**두 읽기 사이**에 레지스트리 파일이 수정되는 TOCTOU 창 방어다. 테스트를
`projects=[], active_path=stale` 스텁으로 재현해 잠금(변이 시 403 대신 승인으로
전환 확인).

**회귀**: 관련 6스위트 66건 통과, ruff/mypy clean.
**전체 스위트: 5280 passed, 13 skipped, 0 failed.**

- [x] 56.1 계약 갭 분석 (기존 boundary 테스트가 잠그지 않는 지점 12건 도출)
- [x] 56.2 계약 고정 스위트 작성 + 뮤테이션 7종 검증
- [x] 56.3 전체 회귀 + 계획서 기록

**인수인계**: (1) `path_security.py`의 현재 working tree 상태는 Phase 27 조정의 일부로
**레지스트리 확장이 포함된 미커밋 버전**이다 — 이 테스트가 이를 잠그므로 커밋 시 함께
가야 한다. (2) `.git` carve-out을 빼는 정책 변경 시에는 이 테스트를 의도적으로
수정하는 PR에서 논의할 것. (3) stub은 `get_project_registry` 소스 속성만 패치한다 —
전역 `_global_registry`를 건드리면 테스트 간 오염이 생긴다.

### Phase 55 — 전체 백엔드 스위트 제로 실패 달성 (완료)

**목표**: 4건 잔존 실패(config.yaml 드리프트, unsloth 프로브 계약, 프롬프트 패키징 바이트
불일치, KDF CLI E2E)를 전부 규명·수정해 전체 스위트를 제로 실패로 만든다.

**실패 4건 트리아지 결과**:

1. **`test_bundled_default_config_matches_repository_default`** — Phase 52 라이브 검증용으로
   잠시 바꿨던 `config.yaml` `daily_budget_usd`(50→12) 복귀가 누락됐던 것. `git checkout`으로
   복원 → 통과. 소스 코드 변경 없음.
2. **`test_unsloth_probe_is_optional_when_endpoint_is_not_configured`** — 커밋 f18f0de(on-demand
   unsloth 런타임)가 `resolve_unsloth_settings`에 하드코딩 폴백 `http://127.0.0.1:8080/v1`을
   넣으면서, 미설정 상태에서도 프로브가 네트워크를 치게 됨. 수정: `allow_default_endpoint`
   키워드 인자 추가(기본 True로 런타임 어댑터 계약 유지) — 프로브는 `False`로 호출해
   `UnslothEndpointError("is not configured")`를 복원. 양쪽 계약 모두 유지.
3. **`test_wheel_contains_dashboard_and_runtime_resources`** — `prompts/Modelfile.reasoning`
   (루트)과 `src/antigravity_k/prompts/` 패키지 사본이 서로 다른 방향으로 동시 수정됨
   (루트: 리브랜딩+베이스 모델 교체 glm4→qwen2.5-coder, src: 리브랜딩만). 테스트 계약상
   루트 `prompts/`가 소스이고 패키지 사본이 파생물 — 루트 내용으로 src 사본 동기화.
   **주의: 두 사본을 따로 고치면 이 테스트가 잡는다. 루트가 소스.**
4. **`test_kdf_migration_v1_to_v2_via_cli`** — `sys.executable` subprocess가 miniforge 인터프리터를
   가리켜 `antigravity_k` 미설정으로 ModuleNotFoundError. Phase 12의 `tests/_cli_subprocess.py`
   헬퍼로 마이그레이션(`python_invocation(project=True)`) — 외부 인터프리터에서 pytest를 돌려도
   통과 확인.

**회귀**: 관련 스위트(provider 24+24, secure_key, wheel assets) 전부 통과,
ruff/mypy clean. **전체 스위트: 5267 passed, 13 skipped, 0 failed** (스킵은 unsloth/e2e
정상 가드).

- [x] 55.1 실패 4건 원인 규명 (Phase 52 잔여 / f18f0de 회귀 / 동시 수정 충돌 / 인터프리터 편향)
- [x] 55.2 수정 3건 + 복원 1건 — 양쪽 계약(프로브 옵션성/어댑터 기본 폴백) 모두 보존
- [x] 55.3 전체 스위트 제로 실패 확인 + 계획서 기록

**인수인계**: (1) `resolve_unsloth_settings`에 새 인자 추가 시 기본값 True 유지 — 런타임
어댑터는 127.0.0.1:8080 폴백이 정상 동작이고, 프로브만 False를 쓴다. (2) `prompts/`를 고칠 때는
반드시 루트를 고치고 `src/antigravity_k/prompts/`에 동기화 — wheel-assets 테스트가 파생물
정합성을 잠근다. (3) subprocess 기반 테스트 신규 작성 시 `sys.executable` 대신
`tests/_cli_subprocess.py` 헬퍼 사용이 원칙 (Phase 12 문서 참조).

### Phase 53/54 — Unsloth 스크립트 API 드리프트 가드 + 주간 최신 버전 체크 (완료)

**목표**: mlx-lm 플래그 드리프트 가드(Phase 22)의 Python API 판 — lora_pipeline이 생성하는
Unsloth SFT/DPO 스크립트가 설치된 unsloth/trl/transformers 시그니처와 일치하는지 검증하고,
주간 CI가 최신 릴리스에서 미리 검사해 로컬 업그레이드 전에 rename을 잡는다.

**구현**:
- `engine/unsloth_script_api.py`: 생성 스크립트를 AST로 파싱해 import·호출·kwargs를 추출
  (`extract_script_api`)하고 설치된 라이브러리 시그니처(`inspect.signature`)와 대조
  (`verify_against_installed`).
  - 해소 규칙: import된 이름은 클래스 루트에서 멈춘다 — `FastLanguageModel.from_pretrained` →
    `unsloth.FastLanguageModel.from_pretrained` (모듈 함수로 오해하지 않음).
  - errors(즉시 실패): 존재하지 않는 import/메서드. warnings: 시그니처에 없는 kwargs —
    **kwargs 흡수 여부를 알 수 없어 알림 수준 (TRL이 런타임 kwargs를 전파하는 케이스 존중).
  - 검증기는 실제 모델 로딩 없이 signature만 보므로 CPU에서도 빠르다.
- `tests/test_unsloth_script_api_drift.py` (14건): AST 추출 7건(설치 무관, 항상 실행) +
  설치 검증 7건(unsloth/trl 미설치 환경 스킵 — 로컬 macOS/Linux base CI).
  드리프트 시나리오: 가짜 rename import/메서드 → error, 가짜 kwarg → warning,
  실제 SFT 스크립트의 TrainingArguments kwargs가 현재 transformers 5.x에서 유효함(로컬에서도 도는
  transformers-only 검증) — 스크립트의 기존 kwargs는 전부 유효 확인.
- pyproject: unsloth extra는 만들지 않기로 함 — unsloth의 datasets<4.4 요구가 finetune
  extra(datasets>=5)와 extra 조합 해석에서 충돌(uv sync 실패). 주간 job이 `uv pip install`로
  직접 설치하는 방식 선택.

**주간 CI** (`.github/workflows/weekly-drift.yml`):
- 트리거: 매주 월요일 04:00 UTC cron + workflow_dispatch(수동).
- `mlx-lm-drift` job(macOS): lock 설치 → `uv pip install -U mlx-lm` → `test_mlx_command_flags.py`.
- `unsloth-drift` job(ubuntu): base lock 설치 → `uv pip install -U unsloth trl` +
  `datasets<4.4` → `test_unsloth_script_api_drift.py`. 설치 버전 로그 출력(드리프트 보고서에 포함).
- 실패 시 워크플로 실패 — lora_pipeline의 스크립트/명령 템플릿을 새 API로 갱신하고 재실행.

**검증**: AST 추출 7건 통과(로컬), mlx 플래그 4건 통과, 관련 4스위트 47+7skip 통과,
ruff/mypy clean, workflow YAML 파싱 확인(jobs/triggers/cron). `uv pip install --dry-run unsloth trl`
으로 설치 커맨드 실재 확인.

- [x] 53.1 AST 추출기 + 설치 시그니처 검증기 (클래스 메서드 해소, error/warning 분류)
- [x] 53.2 드리프트 테스트 14건 (스킵 가드 + 로컬에서 도는 transformers-only 검증 포함)
- [x] 54.1 주간 cron workflow 2 jobs (mlx-lm/unsloth) + 수동 트리거 + 요약 스텝
- [x] 54.2 YAML/설치 커맨드/테스트 로컬 시뮬레이션 + 회귀 + 계획서 기록

**인수인계**: 새 학습 API 사용처가 생기면 `unsloth_script_api._TARGET_MODULES`에 모듈/이름을
추가하면 검증 대상이 된다. 주간 job의 버전 고지 단계가 실패 로그의 '설치 버전' 근거가 된다 —
드리프트 수정 시 이 버전으로 로컬 재현 권장. unsloth를 extra로 다시 넣으려면 datasets 범위
충돌(Phase 53 기록)을 먼저 해소해야 한다.

### Phase 51 — 전역 세션 고지 배너 복원 확인 + App 레벨 계약 테스트 (완료)

**목표**: Phase 13 사양(모든 페이지 상단에 warning/exhausted 배너 — 설정을 열지 않아도)이
현재 코드에서 유지되는지 확인하고, 앱 셸 레벨의 회귀 방지 테스트를 잠근다.

**확인 결과 — 이미 구현돼 있었음 (재구현 불필요)**:
- `App.tsx`의 `AppContent`가 `<SessionDisclosureBanner />`를 라우트 `<main>` **바깥**
  (app-right-panel 직속, 모든 라우트 공통)에 마운트 — 라우트와 무관하게 항상 상단에 위치.
- 데이터는 `disclosureStore`(Phase 29) 공용 폴러 소비 — 배너·설정 카드가 하나의 30초 인터벌 공유.
- warning(호박)/exhausted(적색) 레벨 스타일은 base+dark 팔레트 모두 CSS 존재.

**추가한 것 — App 마운트 레벨 계약 테스트** (`src/__tests__/App.globalBanner.test.tsx`, 신규 4건):
1. 채팅 페이지에서 배너 표시 (설정 미방문).
2. `/`, `/models`, `/settings`, `/git` 전 라우트에서 배너 가시 (라우트 무관 전역성).
3. 배너가 `<main>` 바깥 app-right-panel 직속에 마운트돼 있음 (구조적 전역성).
4. healthy면 여전히 렌더 없음.

**라이브 검증 (:8400 실제 백엔드 + vite)**:
- API healthy → 배너 없음 (정상). fetch 스텁으로 warning 주입 + store.refresh() →
  `/models`에서 호박 배너 렌더 확인(스크린샷) → `agk:pushstate`로 `/git`, `/settings` 이동해도
  배너 유지 — settings 페이지에서는 배너+카드 동시 노출(Phase 29 설계대로).

- [x] 51.1 현황 확인 — 배너는 이미 전역 마운트돼 있음 (코드 변경 0)
- [x] 51.2 App 레벨 계약 테스트 4건 신규 — 전체 698건(63파일) 통과, tsc clean
- [x] 51.3 라이브 배너 가시성 실측 (warning 주입 → 3페이지 이동 유지) + 계획서 기록

**인수인계**: 배너가 안 보인다면 순서는 (1) API 레벨 확인(/api/session/disclosure),
(2) 등급이 healthy가 아닌지, (3) 같은 등급에서 닫았는지(등급 악화 시 재표시) 순으로.
전역 마운트 위치는 App.tsx의 `<SessionDisclosureBanner />` (line ~304) — 라우트 내부로
옮기면 전역성 상실이니 App 테스트가 이를 잠아준다.

### Phase 50 — slow E2E 3-입력 경로 통합 (PDF/DOCX/CSV, 완료)

**목표**: Phase 49의 PDF 단일 slow E2E를 DOCX·CSV까지 확장해 레시피 입력 3경로를
`pytest -m slow` 한 번의 패스로 검증한다.

**구현** (`TestPdfTrainRecipeSlowE2E` → 4 테스트로 확장):
- 공통 단언 헬퍼 `_assert_recipe_artifacts` — 레시피명/레코드 수/데이터셋·설정 파일 실재/
  chat 포맷/역할 구성을 세 소스가 공유 검증.
- `test_docx_train_recipe_e2e`: docx-qa-sft + 헤딩 섹션 범위(`pages="1-4"`) + Phase 48 질문
  템플릿 → `manual 매뉴얼 N절 정리` 4건.
- `test_csv_train_recipe_e2e`: csv-to-chat + prompt/response 컬럼 → 산술 Q&A 5건 직행
  (문서 옵션 미사용 경로).
- `test_all_three_sources_yield_disjoint_artifacts`: 3경로 연속 실행 — 출력 디렉터 분리 시
  데이터셋 경로 3개 모두 상이 + 실재 + 각 내용이 자기 소스와 정확히 일치(혼입 없음).

**발견한 계약 (문서화 가치)**: `apply_recipe`는 데이터셋 파일명을 고정한다
(`recipe_dataset.jsonl`) — 같은 `output_dir`를 공유하면 나중 실행이 덮어쓴다.
호출자(CLI/대시보드)가 출력 디렉터를 분리하는 것이 계약이며, 테스트가 이를 실증.

- [x] 50.1 DOCX/CSV E2E + 3경로 연속 실행 무결성 테스트 추가 (slow 마커 공유)
- [x] 50.2 `-m slow` 4 passed / `-m "not slow"` 4 deselected 확인, 관련 4스위트 86건, ruff clean

**인수인계**: jsonl 파싱 컴프리헨션에서 `l` 변수명이 ruff E741에 걸려 헬퍼 함수로 정리 —
새 테스트에선 헬퍼 재용. execution 시간은 전체 0.3초 미만이라 'slow'라기보다 'on-demand'
성격(파일 I/O + 하위 프로세스 아님)이 강하나, 마커 의미(기본 스위트 제외)는 유지.

### Phase 49 — PDF train-recipe E2E on-demand slow 테스트 (완료)

**목표**: PDF train-recipe 전체 경로(실제 PDF 생성 → apply_recipe → 데이터셋/학습 설정 파일)를
`pytest -m slow`로 요청 시 실행할 수 있는 마커 테스트로 잠근다. 기본 스위트는 느린 테스트 없이 유지.

**구현** (`tests/test_pdf_source_options.py`):
- `TestPdfTrainRecipeSlowE2E` — `@pytest.mark.slow`(기존 pyproject 마커 재용) +
  pypdf 미설치 시 skipif 가드.
- 검증 범위: 레코드 수(5페이지 − TOC 제외 = 4)·최소 레코드 미달 플래그·데이터셋 JSONL 실재 +
  chat 포맷 + Phase 48 질문 템플릿 질문 + TOC 미포함·학습 설정 JSON 실재 + 하이퍼파라미터
  오버라이드 반영·결과 요약 키 구성.
- 옵션 조합을 모두 걸친다: `pdf_pages="1-5"` + `pdf_header_filter="!TOC"` +
  `pdf_question_template`(Phase 48) → 3개 옵션 동시 동작 회귀 방지.

**실행 방법**:
    pytest -m slow tests/test_pdf_source_options.py   # 이 E2E만
    pytest -m "not slow" ...                          # 기본/CI (제외 확인 완료: 36 passed, 1 deselected)

- [x] 49.1 slow 마커 + skipif 가드 + 전체 경로 단언 테스트 작성
- [x] 49.2 `-m slow` 1 passed / `-m "not slow"` 1 deselected 확인, 관련 스위트 83건 통과, ruff clean

**인수인계**: Codex/DOCX 쪽도 동일 패턴으로 `TestCodexTrainRecipeSlowE2E` 등을 붙일 수 있다 —
마커는 pyproject markers에 이미 등록돼 있어 추가 설정 불필요. 참고: apply_recipe 결과 키는
`{recipe, records, sufficient, dataset_path, config_path, config, format, min_records}` —
`stats`는 DPO 경로에만 있다.

### Phase 48 — 문서 Q&A 질문 템플릿 (`--pdf-question-template`, 완료)

**목표**: PDF/DOCX Q&A의 질문 문구를 레시피 실행 시 설정할 수 있게 한다 —
기본은 여전히 '헤더가 제목처럼 보이면 헤더를 질문으로'이지만, 템플릿을 지정하면
모든 단위(페이지/섹션)의 질문이 일관된 문구로 강제된다.

**구현**:
- `pdf_source_options.PdfSourceOptions`에 `question_template` 필드 추가 +
  `render_question_template()` 헬퍼 — 플레이스홀더 `{page}`(단위 번호)·`{title}`(파일명 스템)·
  `{header}`(첫 줄/헤딩)·`{body}`(본문). **str.format 대신 명시적 치환** — 알 수 없는
  `{토큰}`은 그대로 유지(에러 아님)해 포맷 문자열 주입 면역.
- `_pdf_records`: 템플릿 활성 시 헤더가 제목처럼 보여도 템플릿 질문 사용(답은 기존과 동일
  페이지 본문). `pages`/`header_filter`와 조합 가능(AND).
- `_docx_records`: 동일 템플릿 — 단위는 헤딩 섹션, `{page}`=섹션 번호, `{header}`=헤딩 텍스트
  (Phase 47 parity 연장).
- 전달 경로: `apply_recipe(pdf_question_template=...)` → `PdfSourceOptions` → CLI
  `agk train-recipe --pdf-question-template`.

**라이브 E2E (실제 PDF + train-recipe 전체 경로)**:
`--pdf-pages 1-5 --pdf-header-filter !TOC --pdf-question-template "가이드 {page}장: {header}에 대해
자세히 설명해줘"` → 4건 데이터셋 생성, 질문이 모두 `가이드 N장: <헤더>에 대해 자세히 설명해줘`로
일관 생성 확인 (TOC 제외 + 번호 치환 + 헤더 치환 동시 동작).

- [x] 48.1 `question_template` 필드 + `render_question_template` (주입 안전 치환) + PDF/DOCX 적용
- [x] 48.2 테스트 +12 (치환/미지 토큰 보존/플래그/strip + PDF 통일·조합·e2e 4 + DOCX parity 2):
      관련 7스위트 182건 통과, ruff/mypy clean
- [x] 48.3 CLI 옵션 + apply_recipe 플럼빙 + 라이브 E2E + 계획서 기록

**인수인계**: 템플릿엔 `{body}`도 있지만 4KB 잘린 본문 전체가 들어가므로 질문에는 권장하지
않는다(답변 중복). 대시보드 학습 UI에 노출하려면 `apply_recipe`의 `pdf_question_template`
파라미터만 전달하면 된다. 템플릿 사용 시 헤더 품질과 무관하게 질문 일관성이 보장되는
대신 헤더 정보를 잃으니, 헤더가 좋은 문서는 기본 동작(빈 값) 권장.

### Phase 47 — DOCX 변환기 페이지/섹션 범위 + 헤딩 필터 (pdf-qa-sft parity, 완료)

**목표**: Phase 21에서 PDF에 추가한 `pages`(범위 선택)·`header_filter`(정규식 포함/"!"제외)를
DOCX 변환기에도 동일 적용해 docx-qa-sft가 같은 선택 옵션을 갖게 한다.

**구현** (`data_recipes._docx_records` + `load_records_from_source`):
- 동일 `PdfSourceOptions` 객체를 재사용 — 문법·검증·부정 필터 해석이 PDF와 한곳(pdf_source_options)에 유지됨.
- DOCX에서 단위는 페이지가 아니라 **헤딩 섹션(1-based, 문서 순서)** — `pages="2-3,5"`는 2·3·5번째
  헤딩 섹션만. 총 섹션 수를 선계산해 `parse_page_ranges`의 상한 검증(초과 시 ValueError)을 그대로 받는다.
- `header_filter`는 헤딩 텍스트에 적용(포함/"!"제외). 범위·필터 조합은 PDF와 동일(AND).
- 폴백 정책 정합: 선택 옵션(`pages`/`header_filter`)이 활성된 상태에서 결과가 비면
  문서 전체 요약 폴백을 만들지 않는다(빈 결과 반환) — "2-3페이지만" 요청에 전체 요약이
  섞여 드는 것을 막는다. PDF 헤더 필터의 기존 원칙과 동일. 옵션이 없으면 기존 폴백 유지.
- `lora_pipeline.apply_recipe`의 `pdf_pages`/`pdf_header_filter` docstring 갱신 —
  DOCX도 이 옵션을 받는다는 것을 명시(파라미터명은 호환 유지).

**테스트** (`tests/test_docx_source_options.py` 신규 10건 — PDF 스위트와 동일 구조):
전체/범위 선택/범위 초과 ValueError/포함 필터/제외 필터/조합/필터 활성 시 폴백 없음/
옵션 없 + 헤딩 없 문서 폴백 유지/load_records_from_source 경유 e2e/
**같은 options 객체가 PDF·DOCX 양쪽에서 같은 결과** (3번째 단위 선택 + TOC 제외 →
양쪽 모두 ["Usage Basics"]).

- [x] 47.1 `_docx_records` 섹션 범위 + 헤딩 필터 구현 (옵션 비활성 시 기존 동작 100% 보존)
- [x] 47.2 DOCX parity 테스트 10건 — 67건(관련 4 스위트) + quant 142건 통과, ruff/mypy clean
- [x] 47.3 `apply_recipe` 문서 갱신 + 계획서 기록

**인수인계**: PDF의 '페이지'와 DOCX의 '섹션'은 같은 옵션 이름을 공유하되 단위만 다르다 —
사용자 안내(UI/문서)에서는 '페이지/섹션 번호'로 병기 권장. 헤딩 없는 DOCX에 `pages`를 주면
총 섹션 0이라 범위 검증에서 ValueError(초과)가 난다 — 의도상 정상(빈 결과 대신 에러가 명확).
청크 단위 DOCX(섹션 수만 큼)에서도 동일 옵션이 그대로 동작한다.

### Phase 46 — quantQuality 쌍생 구현 공유 conformance fixture (완료)

**목표**: dashboard `quantQuality.ts` ↔ engine `quant_quality.py` 쌍생 구현이 어긋나는
드리프트를 구조적으로 차단한다 — 케이스 셋을 fixture 하나로 잠가 양쪽이 같은 데이터를 검증.

**구현**:
- `tests/fixtures/quant_quality_conformance.json` (신규) — 3 섹션:
  `token_cases`(39개 토큰→등급: UD-*·Q8_0·F16·BF16·n·k·IQ·TQ·bit·Active/N/A·빈문자열·
  대소문자·미지 포맷 gptq/awq), `grade_order`(서열 배열), `grade_meta`(한 글자 P/H/B/C/? + 라벨).
- Python: `tests/test_quant_quality.py`에 fixture 검증 4종 — 형식 검증, 토큰 39케이스
  parametrize, grade/label 메타(대표 토큰 매핑), grade_order ↔ LEVEL_ORDER 정확 일치.
- TS: `dashboard/src/utils/__tests__/quantQuality.conformance.test.ts` — 같은 fixture를
  node:fs로 읽어 동일 검증(형식/39케이스/메타). 라벨도 잠겨 라벨만 바꿔도 양쪽 동시 실패.
- 양쪽 소스 헤더 상호참조에 fixture 경로 + '수정 시 fixture+양쪽 테스트 함께' 규칙 추가.

**작성 중 발견/수정 (테스트 버그)**:
- grade/label 대조에서 level 이름을 토큰으로 넘기는 실수(quant_quality('premium') →
  unknown) — 대표 토큰 매핑으로 수정.
- grade_order 대조에서 `zip(order, order[1:], strict=True)` ValueError — `zip(...)`으로 수정
  (엄격 검사는 앞선 `order == list(LEVEL_ORDER)` 일치 단언이 대신한다).

- [x] 46.1 공유 fixture 작성 (39 케이스 + 서열 + 메타)
- [x] 46.2 pytest 4종 + vitest 3종 양쪽 fixture 검증 — pytest 70건(quant_quality),
      vitest 694건 전체, tsc clean, ruff/mypy clean
- [x] 46.3 양쪽 헤더 상호참조 갱신 + 계획서 기록

**인수인계**: 새 양자화 토큰(예: 새 UD 변형)을 추가할 때는 fixture의 token_cases에
한 줄만 추가하면 양쪽 테스트가 자동으로 함께 검증한다. fixture 경로는 상대 의존
(dashboard 테스트가 `tests/fixtures`를 읽음) — 저장소 레이아웃 변경 시 양쪽 테스트의
경로 상수를 함께 고칠 것.

### Phase 45 — CLI: `agk model list --min-quality` 품질 필터 (완료)

**목표**: 대시보드 Model Hub의 품질 pill(균형 이상 등)과 동일한 브라우징을 CLI에서
`--min-quality` 옵션으로 제공한다. `quant_quality.LEVEL_ORDER`
(unknown 0 < compact 1 < balanced 2 < high 3 < premium 4) 랭킹을 단일 진실원으로 사용.

**구현** (`cli.py` `model_list`):
- `--min-quality/-q <level>`: 하한 등급 이상 모델만 표시 (`rank(m) >= min_rank`).
  unknown(0)은 어떤 하한보다 낮아 자동 제외 — 미표기/Active 모델이 필터에 묻히지 않는 대신
  품질 보장이 목적인 이 필터의 의도와 일치.
- 잘못된 등급은 사용 가능 값 안내(`compact < balanced < high < premium, unknown`)와 함께 exit 2.
- 필터 활성 시 패널에 `필터: '<level>' 이상 표시 중 (N개)` 요약, 0개면 안내 후 정상 종료.
- 대시보드 Phase 42의 '실행 중 모델 면제'는 CLI에 적용하지 않음 — CLI 출력은 정적 스냅샷이고
  사용자가 명시적으로 하한을 요청한 경우 기준 유지가 의도에 맞음 (문서화).

**라이브 검증 (20개 등록 모델)**:
- 전체 14개 → `--min-quality balanced` 8개 (UD-IQ4_XS B, Q8_0 P, 4bit B, UD-Q8_K_XL P,
  UD-Q4_K_XL B, Q4_0 B 등) → `premium` 2개 (Q8_0, UD-Q8_K_XL) → `-q high` 2개. 서열 단조 확인.
- `--min-quality ultra` → exit 2 + 사용 가능 등급 안내.

- [x] 45.1 `--min-quality/-q` 옵션 + LEVEL_ORDER 랭킹 필터 + 검증/요약/빈결과 처리
- [x] 45.2 테스트 +3: balanced 필터 안내·unknown 제외, premium ≤ balanced 서열 실측,
      잘못된 등급 exit 2 → cli_smoke 11건, +quant_quality = 39건 통과, ruff/mypy clean
- [x] 45.3 라이브 필터 실측 (14→8→2, 서열 단조, exit 코드)

**인수인계**: 등급 표기 셀(`_quant_cell`)·안내 패널은 Phase 21의 것을 그대로 재용.
정렬(품질순)이 필요하면 `sorted(models, key=..., reverse=True)`로 LEVEL_ORDER를
그대로 쓰면 된다. 전체 스위트의 3건 실패(provider_capabilities 1, secure_key 1,
benchmark latency 1)는 이 변경과 무관한 기존 실패 — 해당 파일 미터치 + 실패 테스트가
min-quality 경로를 전혀 거치지 않음으로 확인(실패 재현 시 cli.py 미포함 조건에서도 재현).
백그라운드 프로세스가 붙잡고 있는 uv.lock/공유 파일 충돌로 `git stash` 시도는 안전하게
실패했고 working tree는 변경 없음(내 변경만 유지). 기존 stash@{0}은 타 스레드 WIP로 손대지 않음.

### Phase 37 — Claude Code 브리지 자동화 E2E 스크립트 (완료)

**목표**: Phase 34의 수동 브리지 시나리오를 `scripts/` 아래 자동화 스크립트로 만들어
CI나 다른 에이전트가 한 줄로 재현할 수 있게 한다.

**결과**: `scripts/e2e_claude_bridge.sh`

```bash
./scripts/e2e_claude_bridge.sh            # 기본 (qwen3.8:latest, 포트 8479)
./scripts/e2e_claude_bridge.sh --model <m> --port <p>
CLAUDE_BIN=/path/to/claude ./scripts/e2e_claude_bridge.sh   # CLI 위치 명시
./scripts/e2e_claude_bridge.sh --install  # claude 미설치 시 .tmp/claude_cli에 npm 설치
./scripts/e2e_claude_bridge.sh --keep     # 실패해도 워크스페이스/로그 보존
./scripts/e2e_claude_bridge.sh --print-only  # 서버/CLI 없이 권장 env 블록만 출력
```

**동작**:
1. 서버가 이미 실행 중이면 재사용, 아니면 `uv run python -m uvicorn ...`을 직접 기동해
   /v1/health 대기 (45초). `trap`으로 종료 시 서버 kill + 워크스페이스 정리.
2. 랜덤 비밀코드를 담은 note.txt를 생성한 임시 워크스페이스로 이동.
3. `agk start claude`와 동일한 컨텍스트 윈도(CLAUDE_CODE_MAX_CONTEXT_TOKENS)를
   조회해 env 블록 구성 (BASE_URL/API_KEY/MODEL + SMALL_FAST/DEFAULT_HAIKU/SONNET).
4. Claude Code CLI `--print --output-format json --max-turns 6 --allowedTools Read` 실행
   (프롬프트는 stdin 파이프 — 위치인자 파싱 실패 회피).
5. 결과 JSON을 파싱해 **비밀코드 존재 + num_turns>=2 (툴 왕복)** 단언.

**실행 결과 (라이브)**: turns=2 / stop=end_turn / 랜덤 비밀코드
`SECRET-CODE-<hex>`를 툴 왕복으로 회수 — PASS. 종료 후 포트 리스너 0, 임시 워크스페이스 0.

- [x] 37.1 부트스트랩/teardown 포함 자동화 스크립트 작성
- [x] 37.2 라이브 통과 + 정리(포트/워크스페이스) 검증
- [x] 37.3 옵션: --print-only/--install/--keep/CLAUDE_BIN + PORT=0 환경 가드

**인수인계**:
- 프롬프트는 stdin 파이프, `--allowedTools`로 툴 스코프 제한. 모델 미실행 시 스크립트가
  명확히 에러(`ollama pull` 안내). 서버가 이미 8479에 있으면 그걸 재사용.
- claude는 세션 상태를 ~/.claude에 기록 — CI 격리가 필요하면 HOME을 임시로 지정할 것.
- Phase 35의 Codex 시나리오도 같은 패턴으로 자동화하면 `scripts/e2e_codex_bridge.sh`.

## 3. 파일 변경 매니페스트

| Phase | 파일 | 변경 유형 |
|:---|:---|:---|
| 1 | `src/antigravity_k/api/routes/messages_api.py` | 신규 |
| 1 | `src/antigravity_k/api/routes/__init__.py` | 라우터 등록 |
| 2 | `src/antigravity_k/engine/local_model_discovery.py` | 양자화 파서 추가 |
| 3 | `src/antigravity_k/engine/agent_bridges.py` | 신규 |
| 3 | `src/antigravity_k/cli.py` | `agk start` 명령 |
| 5 | `src/antigravity_k/engine/anthropic_tool_bridge.py` | 신규 |
| 5 | `src/antigravity_k/api/routes/messages_api.py` | tools/tool_use 확장 |
| 6A | `src/antigravity_k/engine/session_disclosure.py`, `src/antigravity_k/api/routes/disclosure_api.py`, `src/antigravity_k/api/routes/__init__.py`, `src/antigravity_k/cli.py` | 신규/등록 |
| 6B | `src/antigravity_k/engine/data_recipes.py`, `src/antigravity_k/engine/lora_pipeline.py`, `src/antigravity_k/cli.py` | 신규/확장 |
| 7 | `dashboard/src/utils/quantQuality.ts`, `dashboard/src/pages/ModelHubPage.tsx`, `dashboard/src/styles/index.css` | 신규/확장 |
| 8 | `scripts/e2e_messages_client.py` | 신규 (E2E 클라이언트) |
| 9 | `dashboard/src/components/shared/SessionDisclosurePanel.tsx`, `dashboard/src/api/client.ts`, `dashboard/src/api/clientSchema.ts`, `dashboard/src/pages/SettingsPage.tsx`, `dashboard/src/components/shared/index.ts` | 신규/확장 (프론트) |
| 9 | `dashboard/src/components/shared/__tests__/SessionDisclosurePanel.test.tsx` | 프론트 테스트 |
| 10 | `pyproject.toml`, `src/antigravity_k/engine/data_recipes.py` | 확장 (documents extra + PDF/DOCX 변환) |
| 11 | `src/antigravity_k/engine/lora_pipeline.py`, `src/antigravity_k/engine/data_recipes.py`, `tests/test_lora_dpo.py` | 교정 (하이퍼파라미터 감사) |
| 13 | `dashboard/src/components/shared/SessionDisclosureBanner.tsx`, `dashboard/src/App.tsx`, `dashboard/src/components/shared/index.ts` | 신규/마운트 (전역 배너) |
| 1~3, 5, 6 | `tests/test_messages_api.py`, `tests/test_quantization_discovery.py`, `tests/test_agent_bridges.py`, `tests/test_anthropic_tool_bridge.py`, `tests/test_session_disclosure.py`, `tests/test_disclosure_api.py`, `tests/test_data_recipes.py` | 신규 테스트 |
| 7 | `dashboard/src/utils/quantQuality.test.ts`, `dashboard/src/pages/ModelHubPage.test.tsx` | 프론트 테스트 |
| 33 | `dashboard/src/styles/index.css` | 다크 팔레트 평탄화 버그 수정 |
| 35 | `src/antigravity_k/engine/openai_tool_bridge.py`, `src/antigravity_k/api/routes/chat.py` | 신규/분기 (chat completions tools passthrough) |
| 35 | `src/antigravity_k/engine/openai_responses_bridge.py`, `src/antigravity_k/api/routes/responses_api.py`, `src/antigravity_k/api/routes/__init__.py` | 신규/등록 (/v1/responses) |
| 35 | `src/antigravity_k/engine/robust_tool_parser.py` | 미종료 펜스 수리 추가 |
| 36 | `src/antigravity_k/engine/agent_bridges.py`, `src/antigravity_k/cli.py` | env 블록 확장 + /v1 접미사 수정 + 윈도 조회 |
| 37 | `scripts/e2e_claude_bridge.sh` | 신규 (Claude Code 브리지 자동화 E2E) |
| 39 | `dashboard/src/components/shared/QuantBadge.tsx`, `dashboard/src/styles/index.css` | 칩 data-grade + ::before 등급 아이콘 |
| - | `docs/BENCHMARK_UPGRADE_PLAN_2026-09.md` | 본 문서 (진행 로그 포함) |

---

## 4. 단계별 진행 로그 (타 에이전트 인수인계용)

> 형식: `[날짜] Phase.x — 작업 / 테스트 결과 / 다음 담당자가 알아야 할 것`

### [2026-09-05] 핸드오버 요약 정비 — 문서 최상단 §⭐ 섹션 추가
- 문서 최상단에 **인수인계 요약**을 추가했다: 검증된 기준선(2026-09-05 실측), working tree
  3부류 구성(업그레이드 산출물/타 에이전트 리브랜드/빌드 청소), stash 경고, 기준선 재확인
  레시피, 축적된 환경 함정 8건, 다음 할 일 추천. **다음 에이전트는 §⭐만 읽어도 시작 가능.**
- 이 로그의 상세 Phase 노트들은 참조 자료이고, 현재 상태의 단일 진실원은 §⭐다.

### [2026-09-04] Phase 0 — 계획 수립 완료
- freebuff: 멀티 에이전트 분업 + 격리 worktree + 에이전트 브리지 = Ssak-Ai에 대부분 존재. 유일한 P0 gap은 표준 프로토콜 브리지.
- unsloth: Dynamic GGUF 양자화 네이밍 + OpenAI/Anthropic 동시 호환 API + `unsloth start` 원커맨드 브리지.
- 결론: P0 = Anthropic 호환 API + `agk start`, P1 = 양자화 인식 디스커버리.

### [2026-09-04] Phase 1 — Anthropic Messages 호환 API
- 구현: `messages_api.py` 신규. 기존 `ProtocolTranslator`의 Anthropic 변환 재사용, chat.py의 가드/세션 흐름 준수.
- 테스트: `tests/test_messages_api.py` 8개 케이스 — 결과는 아래 §5 실행 기록 참조.
- 인수인계: ModelManager 목 응답은 스트리밍 청크 형태(`list[str]`)로 주입됨. 실서버 연결 확인은 `agk serve` 후 Claude Code에서 `ANTHROPIC_BASE_URL` 지정으로 수동 검증.

### [2026-09-04] Phase 2 — GGUF 양자화 파싱
- 구현: `_QUANT_TOKEN_RE` + `_extract_quantization()`. unsloth UD 접두사 포함.
- 테스트: `tests/test_quantization_discovery.py` — 결과 §5 참조.
- 인수인계: 파서는 순수 함수라 별도 I/O 없음. Ollama 폴백 우선순위: 파일명 양자 > Ollama details > 빈값.

### [2026-09-04] Phase 3 — `agk start` 브리지
- 구현: `agent_bridges.py`(스펙 테이블) + `cli.py start` 명령.
- 테스트: `tests/test_agent_bridges.py` — 결과 §5 참조.
- 인수인계: 새 에이전트 추가는 `AGENT_BRIDGES` dict에 한 줄 추가로 확장 가능.

### [2026-09-04] Phase 4 — 검증 완료 (최종 상태)
- 신규 테스트 38개 전부 통과, 회귀 125 passed / 2 skipped, ruff clean, mypy 신규 파일 에러 0.
- **주의 (타 에이전트)**: `src/antigravity_k/api/routes/filesystem.py`에 진행 중인 타 에이전트 변경(171 insertions)이 있고
  그 파일에 mypy 기존 에러(`Any` 미임포트, 392줄)가 있다. 본 작업과 무관 — 수정하지 않고 그대로 뒀다.
- **주의 (타 에이전트)**: 워크스페이스에 진행 중인 변경(730+ 파일)이 많다. 커밋은 본인이 만든 파일만 대상으로 해야 한다.
- 다음 담당자 시작점: §6 P3 후속 목록, 또는 `/v1/messages`에 tool-use content block 지원 확장(현재 text만).

### [2026-09-04] Phase 5 — Anthropic tool-use 구현 완료

- 구현: `anthropic_tool_bridge.py`(양방향 변환 엔진) + `messages_api.py`(tools 수신, tool_use 응답, input_json_delta 스트리밍).
- 핵심 결정: 로컬 모델의 `<tool_call>` 텍스트 출력을 매개로 함 — Anthropic tool_use JSON을 강제하지 않고
  기존 `RobustToolParser`로 수리. 새 파서/엔진 로직 제로, 변환만 추가.
- 테스트: 엔진 14 + API 통합 5 = 19개 신규, 전부 통과. 회귀 144 passed / 2 skipped.
- 테스트가 잡아낸 이슈: (1) tool_call 태그가 텍스트 블록에 새어나가는 문제 → `strip_tool_call_syntax`로 해결,
  (2) 도구 전용 응답에서 빈 text 블록 → 생략하도록 변경.
- 인수인계: Claude Code 실연동은 `agk start claude` 환경변수 설정 후 실제 세션 필요(수동).
  스트리밍은 응답 완료 후 청킹 방식이므로 실시간 토큰 스트리밍이 필요하면 ModelManager.stream_generate의
  비동기 래퍼부터 작업해야 한다.
- 다음 담당자 시작점: §6 P3 후속 목록.

### [2026-09-04] Phase 6 — P3 후속 구현 완료

- 6A 세션 고지: `session_disclosure.py`(엔진) + `disclosure_api.py`(API 2 엔드포인트) + `agk session`(CLI).
  CostGuard 설정 규칙(config cost 섹션 → 환경변수)과 동일하게 초기화하므로 대시보드와 값이 일치.
- 6B 데이터 레시피: `data_recipes.py`(카탈로그+변환기) + `LoRAPipeline.apply_recipe()`(원패스 오케스트레이션)
  + `agk recipes` / `agk train-recipe`(CLI).
- 테스트: 신규 31개(고지 12 + 레시피 19) 전부 통과. 회귀 252 passed / 2 skipped
  (기존 cost_guard, lora_dpo, finetune_training_recipe 포함 — apply_recipe 추가가 기존 파이프라인을 깨지 않음 확인).
- 인수인계: 대시보드 UI 카드(고지 마크다운 표시)는 프론트엔드 작업으로 남김 — API가 데이터를 다 준비된 상태.
  PDF/DOCX 소스 확장은 완료 (Phase 10, `documents` extra).
- 다음 담당자 시작점: 대시보드 고지 카드, 실시간 토큰 스트리밍(§4 Phase 5 제한 참고), 또는 아래 P3 잔여 항목.

### [2026-09-04] Phase 7 — 양자화 품질 배지 구현 완료

- 구현: `quantQuality.ts`(등급 산출) + ModelHubPage 배지 + CSS(라이트/다크).
  백엔드 `/api/models/local`이 이미 `quantization`을 반환하므로 프론트만 수정 — API 변경 없음.
- 등급 체계는 unsloth Dynamic GGUF 품질 가이드 기준. Phase 2 파서 토큰 집합(Q/IQ/TQ/UD/NNbit)과 1:1 대응.
- 테스트: 단위 7 + 통합 1 통과. 전체 프론트 스위트 644 passed / 54 files (기존 ChatPage 등 회귀 없음), tsc clean.
- 인수인계: 등급 기준을 바꾸려면 `quantQuality.ts`의 regex 4개(PREMIUM/HIGH/BALANCED/COMPACT_RE)만 수정하면
  배지·툴팁·테스트가 전부 따라온다. ChatPage의 `badge-quant`는 등급 없는 단순 배지로 남겨뒀다(기존 UX 존중) —
  통일하려면 같은 유틸을 적용하면 된다.

### [2026-09-04] Phase 13 — 대시보드 전역 경고 배너 완료
- 구현: `SessionDisclosureBanner` — warning/exhausted에서만 표시되는 전역 배너. 닫아도 등급이 악화되면 재표시.
- 인수인계: 배너와 SettingsPage 카드가 같은 `/api/session/disclosure`를 각각 폴링한다(60초/30초) — 필요 시
  공용 스토어로 통합 가능하나 현재 규모에서는 과설계. 링크는 `agk:pushstate` 이벤트 방식(App.tsx의 푸시스테이트 훅 의존).

### [2026-09-04] Phase 12 — 전체 백엔드 테스트 + 커버리지 리포트 완료
- 전체 스위트 실행(11분): 4,988 passed / 26 failed / 8 errors. **신규 파일 관련 실패 0건.**
- 실패 26건 전수 분류: git_api/filesystem 계열 15건=타 에이전트 미커밋 재작성, e2e_smoke+cli_smoke 15건=
  러너가 venv 밖 miniforge python을 사용하는 환경 문제(sys.executable이 venv를 가리키지 않음).
- 신규 파일 커버리지: 합계 68.0% (cli.py 제외 89.5%), 최저 disclosure_api 67.7% → 최고 agent_bridges 100%.
- 커버리지 JSON: `.tmp/coverage_full.json` (임시 파일 — 재생성 명령은 §5 테스트 기록 참조).

### [2026-09-04] Phase 11 — 하이퍼파라미터 문서 감사 완료
- 교정 6건: mlx `--lora-layers`→`--num-layers` (0.31.x에서 삭제된 플래그 — 실측 확인), DPO lr 1e-6→5e-6,
  unsloth SFT effective batch 8→16, DPO 스크립트 공식 노트북 기준 전면 갱신, 레시피 오버라이드 키 통일(iters→iterations).
- **감사 방법론 (재사용 권장)**: 웹 문서보다 설치된 패키지 소스의 기본값이 우선 — `CONFIG_DEFAULTS` +
  `--help` 실측이 정확도가 높았음. unsloth는 가이드 문서(2e-4/5e-6/effective 16)가 명확한 앵커.

### [2026-09-04] Phase 10 — PDF/DOCX 소스 변환 완료
- 구현: `documents` extra + `_pdf_records`/`_docx_records` 변환기 + `pdf-qa-sft`/`docx-qa-sft` 프리셋.
- **테스트 인프라 발견**: pypdf writer에 content stream(텍스트 연산자)을 직접 넣으면 reportlab 없이도 실제 텍스트 PDF를 생성할 수 있다 — 폰트 리소스(/F1 → Helvetica) 정의가 없으면 extract_text가 빈 문자열을 반환하니 주의.
- 인수인계: 미설치 환경에서는 PDF/DOCX 테스트가 skip됨 (CI에 documents extra 없어도 통과). 미설치 에러 UX는 `MissingDocumentParserError`가 담당 — 새 변환기 추가 시 동일 패턴 준수할 것.

### [2026-09-04] Phase 9 — 대시보드 세션 고지 카드 구현 완료
- 구현: zod 스키마 → API 클라이언트 함수 → `SessionDisclosurePanel` (등급별 배너·게이지·배지) → SettingsPage 마운트.
- 테스트: 컴포넌트 5개 (healthy/exhausted/에러/빈한도/리셋), 전체 프론트 스위트 회귀 포함.
- 인수인계: 패널은 자율 폴링(30초)이라 부모는 데이터를 알 필요 없음. 등급 색상은 `LEVEL_META` 한 곳에서 관리 — CLI(`agk session`)와 대시보드의 등급 체계는 backend `session_disclosure.py`가 단일 진실원.

### [2026-09-04] Phase 8 — 라이브 E2E 완료 + crash-safe tool 형식 전환
- 구현: E2E 클라이언트를 scripts/로 승격, llama.cpp crash 근원 분석 문서화, bridge 형식 마이그레이션.
- **라이브 검증**: `agk serve` (port 8477) + qwen3.8 → 4/4 PASS. tool-use 1턴 `stop_reason=tool_use`, 2턴 `end_turn`.
- **핵심 발견 (다음 담당자 필독)**: qwen3.8 GGUF의 llama.cpp 런너는 `<tool_call>` 리터럴을 *생성*하려 하면 세그폴트하고 Ollama가 `{"error":"EOF"}`를 반환한다. 프롬프트에 이 리터럴을 넣는 것은 안전하지만 모델이 출력하도록 유도하면 크래시한다. 카탈로그/히스토리는 ```` ```json ```` 코드펜스 형식을 사용할 것. `RobustToolParser`는 양쪽 형식을 모두 파싱하므로 추출 로직 변경은 불필요했다.
- 서버 운영 노트: `setsid`는 macOS에 없음 — detached spawn은 Python `subprocess.Popen(start_new_session=True)` 사용. nohup 백그라운드 프로세스는 툴 셸 종료 시 회수될 수 있음.

**2026-09-04 (Phase 26) — 스모크 테스트 러너 무관화**
- `tests/_cli_subprocess.py` 헬퍼로 subprocess 인터프리터를 선택 — pytest 러너 환경과 무관하게 통과.
- uv run·miniforge 양쪽에서 cli_smoke 8/8, e2e_smoke 9/9 확인. Phase 12 트리아지 15건 해소.
- 인수인계: CI에서 명시 지정이 필요하면 `AGK_TEST_PYTHON` env 사용.

**2026-09-04 (Phase 25) — bridge/disclosure 커버리지 100%**
- `tests/test_bridge_disclosure_edge_branches.py` 33개 신규 — 예외 폴백·skip 분기·guard 경로 커버.
- anthropic_tool_bridge 83.7→100%, disclosure_api 60→100%, session_disclosure 97.3→100%.
- 도달 불가 폴백은 mock 주입으로 검증 (방법론은 Phase 25 섹션 참조).

**2026-09-04 (Phase 24) — 레시피 하이퍼파라미터 UI**
- `GET /api/recipes` 신규 + `apply_recipe(hyperparameter_overrides=)` 병합 우선순위 확장 +
  StudioPage STEP 4 프리셋 선택기(필드 채움, 편집 가능).
- 검증: 프론트 657 passed + tsc clean, 백엔드 48 passed + API 라이브 확인, ruff clean.

**2026-09-04 (Phase 23) — 실제 mlx-lm LoRA 학습 E2E**
- 수확 6건 시드 → apply_recipe(harvest) → 감사된 명령 그대로 600 iters 학습 (47초, loss 0.581 수렴).
- 어댑터 저장·로드 추론 확인. **핵심 발견**: mlx-lm은 train/valid 디렉터리 구조 + 배치 크기 이상 분할 필요 —
  단일 JSONL은 미지원 → apply_recipe의 자동 분할 확장을 P2 백로그에 기록.
- 산출물은 data/lora_e2e_out/에 보존.

**2026-09-04 (Phase 22) — mlx-lm 플래그 드리프트 CI 체크**
- `tests/test_mlx_command_flags.py` 4개 + CI matrix에 mlx extra 조합 추가.
- 생성 명령(SFT/DPO/fuse)의 플래그를 설치된 mlx-lm `--help`와 대조 — 미지 플래그 시 CI 실패.
- 인수인계: mlx-lm 업그레이드 시 이 테스트가 1차 방파제. 값/의미 변경은 Phase 11 감사 절차 병행.

**2026-09-04 (Phase 21) — PDF 페이지 범위·헤더 필터**
- `--pdf-pages`(예: 1-5,8) / `--pdf-header-filter`(정규식, !접두사=제외) 추가 — 변환기→API→CLI 전 구간.
- 검증: 28 passed + 회귀 76 passed, ruff/mypy clean, 라이브 3 시나리오 실측.
- 인수인계: 필터로 인한 스킵은 요약 폴백을 만들지 않는다 — 레코드 수가 줄어들면
  최소 레코드 미달 경고(sufficient: false)로 사용자에게 알려진다.

**2026-09-04 (Phase 20) — train-recipe PDF 라이브 E2E**
- 실제 5페이지 PDF → `agk train-recipe pdf-qa-sft` → ChatML 5레코드 + mlx 학습 설정 산출 확인.
- 산출물 검증(구조/원문 대응/하이퍼파라미터 병합) 통과, 임시 파일 정리 완료.
- 재현 방법은 Phase 20 섹션 기술 (테스트 헬퍼 `_write_pdf_with_text` + CLI 명령).

**2026-09-04 (Phase 19) — 세션 고지 카드 재복원**
- 사용자 요청으로 Phase 14 제거를 되돌림. 카드+백엔드+CLI 복원, 전역 배너는 미복원(요청 범위 외).
- 검증: 백엔드 17 passed, 프론트 5 passed (전체 654), tsc/ruff clean.
- 교훈: 제거 이력(Phase 14)과 복원(Phase 19)이 모두 문서에 남아 있어 경로 추적 가능.

**2026-09-04 (Phase 18) — CLI 품질 등급 가이던스**
- `engine/quant_quality.py` 신규(TS util과 1:1) + `agk model list` Quant 컬럼(등급 색상 문자) + 범례.
- 검증: 28 passed + 인접 회귀 51 passed, ruff/mypy clean, 라이브 CLI 출력 확인.
- 인수인계: 등급 체계 변경 시 `quantQuality.ts`와 `quant_quality.py`를 **함께** 수정할 것.

**2026-09-04 (Phase 17) — Model Hub 품질 등급 필터**
- 등급 프리셋 pill row 4종(전체/균형↑/높음↑/프리미엄만) 추가, 카테고리·검색과 AND 조합.
- 검증: Model Hub 5/5, 전체 649 passed + tsc clean. unknown 모델 제외 트레이오프는 Phase 17 설계 노트 참조.

**2026-09-04 (Phase 15) — ChatPage 배지 품질 등급 통일**
- ChatPage 팝오버의 `badge-quant` 칩에 `q-{level}` 클래스 + 툴팁 적용, CSS 변형 5종(라이트/다크) 추가.
- 칩은 전체 양자화 토큰을 유지(식별자), 등급 색상+툴팁으로 Model Hub와 동일 정보 전달.
- 검증: ChatPage 스위트 통과, 전체 프론트 회귀 + tsc clean. P3 백로그에서 해당 항목 완료 처리.

**2026-09-04 (Phase 14) — 세션 고지 레이어 제거**
- 사용자 판단: 개인 사용 프로그램이라 한도 관리·고지 UX 불필요 → Phase 6A(백엔드)+9(카드)+13(배너) 전체 제거.
- 제거 범위: session_disclosure.py, disclosure_api.py, 라우터 등록, `agk session`, 프론트 패널/배너/테스트/스키마/클라이언트 함수/마운트 2곳.
- 유지: `cost_guard.py`(원래 존재하던 강제 로직) — env 미설정 시 기존과 동일하게 비개입.
- 검증: 라우터 disclosure 경로 0건, CLI import OK, ruff clean, 프론트 644 passed + tsc clean.
- 인수인계: 복원이 필요하면 Phase 6A/9/13의 체크리스트가 상세 사양이므로 역순으로 재구현하면 됨.

---

## 5. 테스트 실행 기록

| 일시 | 대상 | 명령 | 결과 |
|:---|:---|:---|:---|
| 2026-09-04 | Phase 1 | `uv run pytest tests/test_messages_api.py -v` | ✅ 8 passed |
| 2026-09-04 | Phase 2 | `uv run pytest tests/test_quantization_discovery.py -v` | ✅ 20 passed (초기 3 fail → regex 수정 후 통과) |
| 2026-09-04 | Phase 3 | `uv run pytest tests/test_agent_bridges.py -v` | ✅ 10 passed |
| 2026-09-04 | Phase 3 CLI | `uv run python -m antigravity_k.cli start claude/codex/unknownagent` | ✅ 브리지 플랜 출력·에러 안내 정상 |
| 2026-09-04 | 전체 신규 | `uv run pytest tests/test_messages_api.py tests/test_quantization_discovery.py tests/test_agent_bridges.py -q` | ✅ 38 passed |
| 2026-09-04 | 회귀 (API+라우터+디스커버리) | `uv run pytest tests/test_api_server.py tests/test_models_system_api.py tests/test_gateway_api.py tests/test_model_router.py tests/test_local_models_api.py + 신규 3종` | ✅ 125 passed, 2 skipped |
| 2026-09-04 | 린트 | `uv run ruff check` (변경 파일 전체) | ✅ All checks passed |
| 2026-09-04 | 타입 | `uv run mypy messages_api.py agent_bridges.py` | ✅ 신규 파일 에러 0 (filesystem.py:392 기존 에러 1건 — 타 에이전트 진행 중 변경, 본 작업 무관) |
| 2026-09-04 | Phase 5 엔진 | `uv run pytest tests/test_anthropic_tool_bridge.py -v` | ✅ 14 passed |
| 2026-09-04 | Phase 5 통합 | `uv run pytest tests/test_messages_api.py -v` | ✅ 13 passed (기존 8 + tool-use 5) |
| 2026-09-04 | Phase 5 전체 | `uv run pytest` (신규 4종 + API/라우터/디스커버리 회귀) | ✅ 144 passed, 2 skipped |
| 2026-09-04 | Phase 6A/6B | `uv run pytest tests/test_session_disclosure.py tests/test_data_recipes.py tests/test_disclosure_api.py -v` | ✅ 31 passed |
| 2026-09-04 | Phase 6 CLI | `agk session`, `agk recipes`, `agk train-recipe chat-sft --out /tmp/...` | ✅ 고지 패널/카탈로그/레시피 적용 출력 확인 |
| 2026-09-04 | Phase 6 전체 | `uv run pytest` (신규 3종 + 기존 12종 회귀 incl. cost_guard/lora_dpo) | ✅ 252 passed, 2 skipped |
| 2026-09-04 | Phase 6 린트/타입 | ruff + mypy (신규 파일) | ✅ clean (filesystem.py:392 기존 에러만 존재 — 타 에이전트 소유) |
| 2026-09-04 | Phase 7 프론트 | `cd dashboard && npx vitest run quantQuality ModelHubPage` | ✅ 10 passed |
| 2026-09-04 | Phase 7 전체 | `cd dashboard && npx vitest run` (54 files) + `tsc --noEmit` | ✅ 644 passed, tsc clean |
| 2026-09-04 | Phase 8 라이브 E2E | `agk serve --port 8477` + `uv run python scripts/e2e_messages_client.py` (qwen3.8 실모델) | ✅ 4/4 PASS (비스트리밍/스트리밍/tool-use 1·2턴) |
| 2026-09-04 | Phase 8 회귀 | `uv run pytest tests/test_anthropic_tool_bridge.py tests/test_messages_api.py -q` | ✅ 30 passed (17 엔진 + 13 API, crash-safe 형식 전환 포함) |
| 2026-09-04 | Phase 8 린트/타입 | ruff + mypy (`anthropic_tool_bridge.py`, E2E 클라이언트) | ✅ clean |
| 2026-09-04 | Phase 9 컴포넌트 | `cd dashboard && npx vitest run SessionDisclosurePanel` | ✅ 5 passed |
| 2026-09-04 | Phase 9 전체 | `cd dashboard && npx vitest run` (55 files) + `tsc --noEmit` | ✅ 649 passed, tsc clean |
| 2026-09-04 | Phase 10 변환 | `uv run pytest tests/test_data_recipes.py -q` (PDF/DOCX 실생성 포함) | ✅ 29 passed |
| 2026-09-04 | Phase 10 회귀 | data_recipes + disclosure + finetune 스위트 | ✅ 46 passed, ruff/mypy clean |
| 2026-09-04 | Phase 11 감사 | `uv run pytest tests/test_lora_dpo.py tests/test_data_recipes.py tests/test_finetune_training_recipe.py -q` | ✅ 51 passed (검증 3개 추가) |
| 2026-09-04 | Phase 11 전체 | 전체 회귀 (9스위트) + ruff + mypy | ✅ 125 passed, clean |
| 2026-09-04 | Phase 12 전체 | `uv run pytest tests/ -m 'not slow and not benchmark' --cov=src/antigravity_k --cov-report=json:.tmp/coverage_full.json` | 4,988 passed / 26 failed(타 에이전트·러너 환경, 신규 파일 무관) / 8 err / 6 skip, 커버리지 77.23% |
| 2026-09-04 | Phase 12 신규파일 | 위 JSON에서 매니페스트 9파일 추출 집계 | 평균 68.0% (cli 제외 89.5%) |
| 2026-09-04 | Phase 13 배너 | `cd dashboard && npx vitest run SessionDisclosureBanner` | ✅ 6 passed |
| 2026-09-04 | Phase 13 전체 | `cd dashboard && npx vitest run` + `tsc --noEmit` | ✅ 655 passed, tsc clean |
| 2026-09-04 | Phase 14 제거 검증 | 라우터 경로 assert + `agk` import + ruff + 프론트 vitest/tsc | ✅ 백엔드 OK, 644 passed, tsc clean |
| 2026-09-04 | Phase 16 실서버 E2E | Claude Code CLI 2.1.260 → agk serve 8479 → qwen3.8 | ✅ 3/3 PASS (단턴/멀티턴/도구 루프), /v1/messages 6회 200 |
| 2026-09-04 | Phase 17 등급 필터 | `cd dashboard && npx vitest run ModelHubPage` + 전체 회귀 + tsc | ✅ 5/5, 649 passed, tsc clean |
| 2026-09-04 | Phase 18 CLI 등급 | `uv run pytest tests/test_quant_quality.py` + 인접 회귀 + 라이브 `agk model list` | ✅ 28 passed, 회귀 51 passed, 라이브 확인 |
| 2026-09-04 | Phase 19 고지 카드 복원 | 백엔드 disclosure 스위트 + 프론트 패널 테스트 + 전체 회귀 | ✅ 17 passed, 5 passed (전체 654), tsc/ruff clean |
| 2026-09-04 | Phase 20 train-recipe E2E | 실제 PDF 5페이지 → `agk train-recipe pdf-qa-sft` 라이브 | ✅ 5레코드 ChatML + mlx config, 정합성 검증 통과 |
| 2026-09-04 | Phase 21 PDF 옵션 | `uv run pytest tests/test_pdf_source_options.py` + 회귀 + 라이브 3 시나리오 | ✅ 28 passed, 회귀 76 passed, 라이브 확인 |
| 2026-09-04 | Phase 22 mlx 드리프트 체크 | `uv run pytest tests/test_mlx_command_flags.py` + YAML 검증 | ✅ 4 passed (0.31.3), 음성 검증 완료, ci.yml 유효 |
| 2026-09-04 | Phase 23 실제 학습 E2E | harvest 6건 → apply_recipe → mlx_lm.lora 600 iters → 어댑터 추론 | ✅ 47초 수렴 (loss 0.581), 어댑터 저장·로드 확인 |
| 2026-09-04 | Phase 24 레시피 UI | 프론트 Studio 프리셋 테스트 + 백엔드 API/오버라이드 검증 | ✅ 프론트 3 passed (657), 백엔드 48 passed, API 라이브 확인 |
| 2026-09-04 | Phase 25 커버리지 100% | coverage run (대상 3파일) + 인접 스위트 79 passed | ✅ 3파일 모두 100%, ruff/mypy clean |
| 2026-09-04 | Phase 26 러너 무관화 | uv run pytest + miniforge pytest × (cli_smoke, e2e_smoke) | ✅ 양쪽 러너 모두 cli 8/8, e2e 9/9 |
| 2026-09-05 | **기준선 (§⭐)** | `uv run --no-sync pytest tests/ -q` | ✅ **5280 passed, 13 skipped, 0 failed** (Phase 52~56 포함 working tree) |
| 2026-09-05 | **기준선 프론트 (§⭐)** | `cd dashboard && npx vitest run` + `tsc --noEmit` | ✅ **698 passed (63 files)**, tsc clean |
| 2026-09-05 | slow E2E | `uv run --no-sync pytest -m slow -q` | ✅ 4 passed (기본 스위트 제외 확인) |
| 2026-09-05 | Phase 56 계약 | 관련 6스위트 + 뮤테이션 7종 | ✅ 66 passed, 변이 전부 차단, 소스 무손상 복구 |

### 테스트 중 발견·수정한 결함

| 결함 | 수정 |
|:---|:---|
| 양자화 regex가 I-quant(`IQ4_XS`, `IQ2_M`) 미매칭 — `[IQT]` 단일 문자 클래스는 두 글자 접두사 `IQ`/`TQ`를 커버 못함 | `(?:TQ\|IQ\|Q)\d(?:_[A-Z0-9]+)+` 로 수정 |
| 양자화 regex가 `Q3` (언더스코어 없는 미완성 토큰) 오탐 | 언더스코어 그룹 `+` 필수로 변경 |
| messages_api.py 초판 문법 오류 다수 (python 스타일 실수) | 전면 재작성 |
| mypy: `err` 변수 이중 대입 타입 충돌 + redundant cast | 변수 분리(`parse_err`/`validation`/`gen_err`) + cast 제거 |
| **라이브 E2E**: tool-use 시나리오에서 Ollama `{"error":"EOF"}` (llama.cpp 런너 세그폴트) — qwen3.8 GGUF가 `<tool_call>` 리터럴 **생성** 시 크래시 (토큰 특이적, Ssak-Ai 코드 결함 아님) | 카탈로그·히스토리를 ```` ```json ```` 코드펜스 형식으로 전환 (`RobustToolParser` 백틱 폴백이 이미 지원) — Phase 8 참조 |
| Phase 9: `DisclosureLevel`/`LimitDisclosure` 타입을 client.ts에 재-export하지 않아 tsc 실패 | client.ts export type 블록에 추가 — vitest는 목 모듈이라 잡지 못하고 tsc가 잡음 (타입 검증 병행 필요 확인 사례) |

---

## 6. 미완료 후속 작업 (P3)

- [x] **P2 (Phase 23 발견)**: `apply_recipe`가 mlx 플랫폼(`platform="mlx"`)에서 train/valid을 자동 분할해
  mlx-lm 디렉터리 구조(`mlx_dataset/train.jsonl` + `valid.jsonl`)로 산출하도록 확장 — **완료**
  (`split_dataset_for_mlx` 구현, 2*batch_size 미만 시 전체 재사용 폴백, lora_config.json 연동 및 단위 테스트 6종 완료)

- [x] 세션 한도/데이터 사용 고지 UX (freebuff 벤치마킹) — Phase 6A 완료 → **Phase 14에서 제거** (개인 사용 불필요 판단)
- [x] 학습 데이터 레시피(Data Recipe) 프리셋 (unsloth 벤치마킹) — Phase 6B 완료 (6 프리셋 + `agk train-recipe`)
- [x] 대시보드 고지 카드: `/api/session/disclosure` 데이터를 UI에 표시 — Phase 9 → 14 제거 → **Phase 19 재복원 (현재 상태)**
- [x] ChatPage 모델 선택 배지(`badge-quant`)에도 quantQuality 등급 적용 (Model Hub와 UX 통일) — 완료 (Phase 15)
- [x] PDF/DOCX 소스 변환 (data_recipes 확장) — 완료 (Phase 10, `documents` extra: pypdf + python-docx)
- [x] 실서버 E2E: `agk serve` 기동 후 Claude Code/Codex 실제 연결 검증 — **완료**. Claude Code (Phase 16: 단턴/멀티턴/도구 루프 3/3) + **Codex (Phase 35 구현, Phase 41 재검증: Responses API 브리지로 2 시나리오 통과)**. `agk start claude|codex`로 환경변수/config 레시피 발급 가능
- [x] 실시간 토큰 스트리밍: ModelManager.stream_generate 비동기 래퍼 — **완료 (Phase 31)**. `stream_generate_async`(iterate_in_threadpool)가 버퍼링 없이 토큰을 전달. 라이브 재검증(Phase 38): 첫 text_delta 0.51s / 총 1.44s, 20개 델타, stop=end_turn. 테스트 19건 (실시간성 단언 포함) 통과. (구 §6 항목 — Phase 31에서 구현됐으나 체크리스트 미반영 → 2026-09-04 갱신)
- [x] MCP 서버 헬스 캐시 대시보드 (기존 mcp_upgrade_report P2 계승) — **완료**: `MCPHealthCache` + `GET/POST /api/mcp/health[/refresh]`, Settings `McpHealthCachePanel`, 로더 연동·vitest/pytest
- [x] OAuth 2.1 interactive flow (기존 mcp_upgrade_report P1 계승) — **완료**: `mcp_oauth` (authorization code + PKCE, PRM/AS discovery, vault 토큰 저장/갱신/해제) + `GET/POST /api/mcp/oauth/{status,start,callback,complete,revoke}`, Settings `McpOAuthPanel`, 로더 Bearer 헤더 연동·pytest/vitest. 실브라우저 E2E는 수동 확인(패널 안내) — 네트워크 목 단위 테스트로 코드 경로 검증.
