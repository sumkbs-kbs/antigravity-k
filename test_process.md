# DOM 기반 정밀 기능 테스트 프로시저 (v3.4)

> **최종 검증일**: 2026-05-06 18:32 KST
> **최종 결과**: 10/10 전체 통과 (100%)
> **적용 엔진**: `TestHarness` (`src/antigravity_k/engine/harness.py`), `GoalRunner` (`src/antigravity_k/engine/goal_runner.py`), `OmniTDDEngine` (`src/antigravity_k/engine/tdd_engine.py`)
> **최종 리포트**: `test_report.md`

본 문서는 브라우저 에이전트 및 QA 봇이 대시보드의 **DOM 조작 기반 동적 UI/UX 통합 테스트(Harness Testing)**를 수행하기 위한 정밀 가이드라인입니다. 각 페이즈별로 통과해야 할 명확한 DOM 상태와 엣지 케이스를 정의합니다.

---

## 사전 조건 (Prerequisites)

테스트를 시작하기 전 아래 환경이 준비되어야 합니다:

| 항목 | 필수 여부 | 확인 방법 |
|------|----------|----------|
| 백엔드 서버 (FastAPI) | ✅ 필수 | `curl http://localhost:8000/v1/health` → `{"status":"ok"}` |
| 백엔드 헬스 호환 라우트 | ✅ 필수 | `curl http://localhost:8000/health` → `{"status":"ok"}` |
| 프론트엔드 서버 (Vite) 또는 FastAPI 정적 대시보드 | ✅ 필수 | Vite: `curl http://localhost:5173`, 정적: `curl http://localhost:8000/` → HTML 응답 |
| Vite Proxy 설정 | ✅ 필수 | `VITE_BACKEND_URL` 또는 `AGK_BACKEND_URL` 미설정 시 `/api`, `/v1`, `/ws` → `127.0.0.1:8000` 프록시 |
| Playwright 설치 | ✅ 필수 | `pip install playwright && playwright install chromium` |
| Ollama 실행 | ⚠️ 선택 | 비전 분석(Phase 6, 8)에 필요. `ollama list`에 `qwen2.5vl:32b` 확인 |
| Accessibility 권한 | ⚠️ 선택 | External Brain(Phase 7)의 Gemini 앱 제어에 필요 |
| 정적 분석 도구 | ✅ 필수 | `python -m ruff --version` → `ruff 0.15.12`, `python -m ruff check src tests` → 통과 |

**서버 시작 명령어** (서버가 꺼진 경우):
```bash
# 백엔드
cd /path/to/antigravity-k && PYTHONPATH=src python3 -m uvicorn antigravity_k.api.server:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

# 프론트엔드
cd /path/to/antigravity-k/dashboard && npm run dev
```

**포트 충돌 또는 단일 서버 검증 시 권장 명령어**:
```bash
# FastAPI가 dashboard/dist 정적 파일까지 제공하는 smoke test 모드
cd /path/to/antigravity-k
PYTHONPATH=src python3 -m uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 8012
```

**Vite 프록시 포트 변경 예시**:
```bash
cd /path/to/antigravity-k/dashboard
VITE_BACKEND_URL=http://127.0.0.1:8012 npm run dev
```

---

## 테스트 페이즈 (Test Phases)

### Phase 1: 코어 레이어 및 내비게이션 검증
* **검증 목적**: 사이드바 및 탭 전환 시 화면 깜빡임, DOM 렌더링 누락 방지.
* **대응 인텐트**: `dashboard_load`
* **액션**:
  1. `http://localhost:5173` 또는 FastAPI 정적 대시보드 `http://127.0.0.1:8012` 접속.
  2. `AI 채팅`, `LLM Wiki`, `에이전트`, `설정` 탭을 1초 간격으로 순회 클릭.
* **통과 조건(Assertion)**:
  - `#app` 요소가 존재하고 `<title>`에 "Antigravity-K"가 포함되어야 함.
  - 사이드바 네비게이션 요소의 `.active` 클래스가 즉시 변경되어야 함.
  - 콘솔(Console)에 Uncaught Error나 Network 404/500 에러가 0건이어야 함.
  - 각 탭 전환 시 기존 DOM 노드가 정리되고 새 노드가 마운트되어야 함 (메모리 누수 확인).
* **✅ 최근 결과**: PASS — title "Antigravity-K" 확인, 정적 대시보드 로드 정상. `/v1/health`, `/health` 모두 HTTP 200. Full Harness 기준 `dashboard_load` 421ms.

### Phase 2: Command Palette 정밀 테스트
* **검증 목적**: 키보드 중심(Keyboard-first) 워크플로우의 완벽성 검증.
* **액션**:
  1. `Cmd+K` 입력.
  2. 팔레트 오버레이 표시 확인.
  3. `brain` 입력 → External Brain 항목 필터링 확인.
  4. `Escape`로 닫기.
  5. `명령 팔레트` 버튼 클릭 → `settings` 입력 직후 Enter → 설정 화면 이동 확인.
* **등록된 명령어 목록** (2026-05-06 기준, 총 12개):
  1. 🔍 Search Notes
  2. 📝 Create New Note
  3. 💬 Open AI Chat
  4. 🎯 Autonomous Goal (/goal)
  5. ⚙️ Preferences
  6. 🔄 Sync Vault (Git)
  7. 🧪 Run Self-Test (Cmd+Shift+T)
  8. 🤖 Autonomous QA Loop (Cmd+Shift+Q)
  9. 🧪 Test-Driven Code Generation (Cmd+Shift+D)
  10. 🧠 External Brain — List Available
  11. ♊ External Brain — Ask Gemini App
  12. ⚖️ External Brain — Compare All
* **통과 조건(Assertion)**:
  - 팔레트 오버레이 오퍼시티가 즉시 1로 변경되어야 함.
  - 검색 결과가 0.5초 이내에 렌더링(Debounce 검증)되어야 함.
  - 사용자가 검색어 입력 직후 Enter를 눌러도 debounce 이전 stale selection이 실행되면 안 됨.
  - 방향키 조작 시 `.selected` 클래스가 정확히 이동해야 함.
  - 위 12개 명령어가 모두 표시되어야 함.
  - `goal` 검색 후 Enter 실행 시 채팅 입력창에 `/goal ` 프리필이 들어가야 함.
* **✅ 최근 결과**: PASS — 12개 명령어 전체 표시, 검색 필터링, `goal` → `/goal ` 프리필, `settings` 빠른 Enter → `시스템 설정 Settings` 이동 확인.

### Phase 3: 채팅 인터랙션 및 레이아웃 엣지 케이스
* **검증 목적**: 메시지 버블, 인풋 박스 레이아웃의 견고성 및 스트리밍 성능.
* **대응 인텐트**: `chat_send`
* **액션**:
  1. 채팅창에 텍스트 입력 (placeholder: `명령어나 질문을 입력하세요` 또는 `이미지 Drag & Drop 가능`).
  2. Enter로 전송.
  3. 스트리밍 응답 수신 대기 (최대 60초, Self-Healing 포함).
  4. 하단 자동 스크롤 확인.
  5. Plan 토글 확인.
* **통과 조건(Assertion)**:
  - 하단 입력창이 커질 때 위쪽 메시지를 가리지 않아야 함 (`padding-bottom` 확보).
  - 전송 전 assistant bubble 수를 기록하고, 전송 후 새 assistant bubble이 생성되어야 함.
  - 새 응답은 `Thinking` placeholder 또는 `API 요청 중 오류`가 아니어야 함.
  - 스트리밍 응답 도중 화면 스크롤이 버벅이지 않아야 함.
  - Token 사용량 표시 (`Tokens Used: In: N | Out: N`).
  - `/goal ...`로 시작하는 메시지는 일반 모델 스트림이 아니라 슬래시 레지스트리로 라우팅되어야 함.
* **✅ 최근 결과**: PASS — 강화된 `chat_send` 기준으로 새 assistant 응답 감지 완료. `/goal` UI 전송 시 `# /goal Autonomous Goal Contract`, `Autonomous Judgment Policy`, `execute_with_verification` 렌더링 확인.

### Phase 4: 에이전트 매니저 & 터미널 통합
* **검증 목적**: 파일 탐색기, 터미널 WebSocket의 정상 동작 검증.
* **대응 인텐트**: `file_explorer`, `terminal_ws`
* **액션**:
  1. 파일 탐색기 영역에서 `.file-item, .tree-item, [class*='explorer'] li` 존재 확인.
  2. 터미널 WebSocket 연결 시도. 기본값은 `ws://localhost:8000/ws/terminal`, 포트 변경 시 `ws_url`로 명시.
  3. `echo 'harness_test_ok'` 명령 전송 → 응답 수신.
* **통과 조건(Assertion)**:
  - 파일 탐색기에 1개 이상의 항목이 표시되어야 함.
  - WebSocket이 5초 이내에 연결되고, 명령 응답이 3초 이내에 수신되어야 함.
* **✅ 최근 결과**: `file_explorer` PASS — 49개 파일 항목 표시 (96ms, 2-Layer 검증). `terminal_ws` PASS — 11ms.

---

## 결함 수정 프로세스 (Hotfix Protocol)

테스트 진행 중 위 통과 조건을 불만족하는 경우, 에이전트는 테스트를 중단하지 않고 **즉시 코드를 리팩토링**하여 결함을 수정해야 합니다. (예: CSS 패딩 조정, JS 이벤트 리스너 수정 등)

**과거 Hotfix 이력**:
| 일시 | 문제 | 수정 |
|------|------|------|
| 2026-05-06 | `vision_analyze` 테스트 HTTP 500 | `HTTPException` 재전파로 스크린샷 없음 케이스를 HTTP 400으로 고정 |
| 2026-05-06 | Agent helper API의 파일 쓰기/shell 실행 권한 경계 미흡 | `/api/agent/tools/fs/write`, `/api/agent/tools/shell/run`에 `PermissionGate` 적용 |
| 2026-05-06 | TestHarness가 `8000/5173/ws://localhost:8000`에 고정 | `base_url`, `dashboard_url`, `ws_url`, `AGK_HARNESS_*` 환경변수 지원 |
| 2026-05-06 | Command Palette에서 검색 직후 Enter 시 stale selection 실행 가능 | 입력 즉시 로컬 명령 필터링 렌더링, 원격 검색 실패 시 로컬 결과 유지 |
| 2026-05-06 | `chat_send` 하네스가 welcome/placeholder를 응답으로 오인 가능 | 전송 후 새 assistant bubble + 실제 내용 조건으로 강화 |
| 2026-05-06 | Vite proxy backend target 고정 | `VITE_BACKEND_URL` 또는 `AGK_BACKEND_URL` 지원 |
| 2026-05-06 | 서버 재시작 시 신규 라우트 미반영 | uvicorn `--reload` 플래그로 자동 반영 확인 |
| 2026-05-06 | 자율 E2E 중 `write_file` Sandbox 이탈 오류 (`[APPROVAL REQUIRED]`) | `run_e2e_test.py`의 생성 타겟을 `project_root` 내부로 수정하여 권한 허용 |
| 2026-05-06 | 도구 환각(Hallucination)에 의한 무한 루프 (`</create_directory>`) | `prompt_builder.py` 내 절대 도구 이름을 XML 태그로 사용 금지 규칙 명문화 |
| 2026-05-06 | `/goal` 자율 목표 명령 부재 | `GoalRunner` 추가, `SlashCommandRegistry`에 `/goal` 등록, 채팅 API slash 라우팅 적용 |
| 2026-05-06 | Command Palette에서 `/goal` 접근 경로 부재 | `Autonomous Goal (/goal)` 명령 추가 및 채팅 입력 프리필 구현 |
| 2026-05-06 | Self-Test 기본 호출이 8000 포트에 고정될 수 있음 | `/api/agent/tools/browser/self-test`가 현재 요청 base URL을 기본값으로 사용하도록 개선 |
| 2026-05-06 | WebSocket 유지 SPA에서 Playwright `networkidle` 대기 타임아웃 | Harness 대시보드 로드를 `domcontentloaded` + `#app/#chat-input` readiness로 변경 |
| 2026-05-06 | `terminal_ws` 실패 메시지가 빈 문자열일 수 있음 | 예외 타입과 대상 `ws_url`을 포함하도록 실패 메시지 보강 |
| 2026-05-06 | `external_brain.py` Gemini 응답 추출 중 undefined `prompt` | `_wait_for_response(prompt)`로 원본 프롬프트 전달 |
| 2026-05-06 | `tdd_engine.py` 중복/미사용 import로 ruff 실패 | 중복 `re` import 제거 및 미사용 `Any` 제거 |
| 2026-05-06 | `file_explorer` Self-Test 실패 (SPA lazy-loading) | `_test_file_explorer`를 2-Layer(UI 컨테이너 + API 검증) 구조로 개선 |
| 2026-05-06 | 하네스 수정 후 `resp` 미사용 변수 ruff F841 | `resp` → `_resp` 변경 |
| 2026-05-06 | `/goal`이 실행 가능 여부 판단 정책을 구조화하지 않음 | `GoalJudgment`, `GoalSignal`, `Autonomous Judgment Policy` 추가 |
| 2026-05-06 | 루트 `/health` 직접 호출 시 404 | `/health` alias 추가 및 `test_health_check_root_alias` 회귀 테스트 추가 |
| 2026-05-06 | **TDD 코드-only 응답 (품질 핵심)** | `_reconstruct_response()` 추가: 3단 구조(분석→코드→설명) 한국어 응답 생성 |
| 2026-05-06 | **불필요 TDD 멀티모델 레이싱** | `_should_skip_racing()` Adaptive Mode: 로컬 모델 단독 실행으로 10~15배 속도 향상 |
| 2026-05-06 | **Output Quality Gate 부재** | `prompt_builder.py`에 규칙 11~16 추가 (한국어 설명, Big-O, 비교표, 반복 금지, 최소 길이) |
| 2026-05-06 | **TDD Baseline JSON 파싱 실패** | `_generate_local_baseline` 2단 폴백 파싱 (JSON → 코드 블록 분리) |

---

### Phase 5: 자가 진단 오케스트레이션 테스트 (Self-Test Loop)
* **검증 목적**: Antigravity-K가 스스로를 테스트하는 자율 진화 루프의 완전성 검증.
* **대응 인텐트**: `health_api`, `models_api` (+ 모든 UI/통합 인텐트)
* **트리거 방법**:
  - Command Palette → `🧪 Run Self-Test (Cmd+Shift+T)`
  - 단축키 `Cmd+Shift+T`
  - API 직접 호출: `POST /api/agent/tools/browser/self-test`
  - 별도 경로: `POST /api/harness/self-test`
* **검증 포인트**:
  - `health_api`: `/v1/health`가 `{"status": "ok"}`를 반환해야 함.
  - `models_api`: `/v1/models`가 1개 이상의 모델을 반환해야 함.
  - `dashboard_load`: Playwright가 `dashboard_url`에 접속하여 `#app` 또는 title `Antigravity-K`를 확인해야 함.
  - `chat_send`: 채팅 입력 → 전송 → 응답 수신 플로우가 Self-Healing 포함 60초 이내 완료되어야 함.
  - `file_explorer`: 파일 탐색기에 1개 이상의 항목이 표시되어야 함.
  - `terminal_ws`: WebSocket 연결 + echo 응답.
* **통과 조건(Assertion)**:
  - 전체 합격률(pass_rate) 80% 이상.
  - Self-Healing으로 복구된 테스트는 `healed`로 분류 (통과에 포함).
  - 마크다운 리포트가 채팅창에 자동 출력되어야 함.
* **✅ 최근 결과**: 기본 호출 `POST /api/agent/tools/browser/self-test {}` 기준 Full self-test 10/10 PASS, 1,993ms.

**포트 변경 시 API 직접 호출 예시**:
```bash
curl -s -X POST http://127.0.0.1:8012/api/agent/tools/browser/self-test \
  -H 'Content-Type: application/json' \
  -d '{"scope":"api_only","base_url":"http://127.0.0.1:8012"}'
```

### Phase 6: 완전 자율 QA 루프 (Autonomous QA — Vision → Fix → Verify)
* **검증 목적**: 비전 분석 결과를 코드 자동 수정까지 연결하는 완전 폐쇄 루프 검증.
* **대응 인텐트**: `autonomous_qa_dry`
* **트리거 방법**:
  - Command Palette → `🤖 Autonomous QA Loop (Cmd+Shift+Q)`
  - 단축키 `Cmd+Shift+Q`
  - API 직접 호출: `POST /api/agent/tools/browser/autonomous-qa`
* **자율 루프 흐름**:
  1. Playwright로 대시보드 전체 스크린샷 촬영
  2. `qwen2.5vl:32b` 비전 모델이 UI 결함 분석 (JSON 구조화 출력)
  3. `qwen2.5-coder:32b` 코딩 모델이 결함 수정 패치 생성
  4. 패치를 실제 파일에 자동 적용 (`search/replace`)
  5. 페이지 리로드 → 재스크린샷 → Visual Regression 비교
  6. 결함 해소 확인 시 종료, 미해소 시 최대 3회 반복
* **추가 검증**:
  - **반응형 테스트**: Desktop(1280×800), Tablet(768×1024), Mobile(375×812) 3개 뷰포트에서 가로 스크롤 없음 확인
  - **성능 메트릭**: DOM Content Loaded, First Contentful Paint, DOM 노드 수, JS Heap 크기 수집
  - **콘솔 에러**: 테스트 전체 과정에서 발생한 console.error/warning 자동 수집
* **통과 조건(Assertion)**:
  - `status`가 `fixed` 또는 `no_issues`여야 함.
  - 반응형 테스트 3개 뷰포트 중 2개 이상 pass.
  - AutonomousQAEngine 초기화 성공 + 스크린샷 촬영 가능 (1,000 bytes 이상).
* **✅ 최근 결과**: PASS — AutonomousQA 초기화 OK, 스크린샷 111,341 bytes.

### Phase 7: 외부 AI 두뇌 간접 연동 (External Brain)
* **검증 목적**: Antigravity-K가 GUI 자동화를 통해 외부 AI 앱(Gemini, ChatGPT)의 두뇌를 간접적으로 활용할 수 있는지 검증.
* **대응 인텐트**: `external_brain_list`
* **트리거 방법**:
  - Command Palette → `🧠 External Brain — List Available`
  - Command Palette → `♊ External Brain — Ask Gemini App`
  - Command Palette → `⚖️ External Brain — Compare All`
  - API: `GET /api/agent/tools/external-brain/list`
  - API: `POST /api/agent/tools/external-brain/send`
* **검증 포인트**:
  - `external_brain_list`: API가 3개 어댑터(gemini_app, chatgpt_web, gemini_web) 목록을 반환해야 함.
  - `external_brain_gemini`: Gemini 앱이 실행 중이고 Accessibility 권한이 있으면, AppleScript로 프롬프트 전송 → 응답 수신이 120초 이내 완료되어야 함.
  - `external_brain_compare`: compare 전략으로 여러 두뇌에 동시 전송 시, 최소 1개 이상의 성공 응답이 있어야 함.
* **통과 조건(Assertion)**:
  - `/external-brain/list` 응답에 `brains` 배열이 3개 이상이어야 함.
  - 각 어댑터의 `available` 상태가 boolean으로 반환되어야 함.
  - `latency_ms`가 기록되어야 함 (0 초과).
* **✅ 최근 결과**: PASS — 219ms, 3개 어댑터 전체 반환 (gemini_app, chatgpt_web, gemini_web).

### Phase 8: 멀티모달 비전 분석 (Vision Analysis)
* **검증 목적**: 스크린샷 기반 UI 결함 분석 API가 비전 모델(qwen2.5vl:32b)과 정상 연동되는지 검증.
* **대응 인텐트**: `vision_analyze`
* **트리거 방법**:
  - API: `POST /api/agent/tools/browser/vision-analyze`
* **검증 포인트**:
  - `vision_analyze`: 스크린샷 없이 호출 시 400/422 응답 (API 라우트 존재 확인).
  - 스크린샷 포함 호출 시 비전 모델이 분석 텍스트를 반환.
  - `config.yaml`의 `defaults.vision`이 `qwen2.5vl:32b`로 설정.
* **통과 조건(Assertion)**:
  - API 엔드포인트가 등록되어 있어야 함 (404가 아닌 400/422/200).
  - 스크린샷 없이 호출 시 HTTP 400과 `"No screenshot"` 메시지가 포함된 에러를 반환해야 함.
  - HTTP 500으로 감싸지면 실패로 처리해야 함.
* **✅ 최근 결과**: PASS — 스크린샷 없이 호출 시 HTTP 400, Harness에서는 `Vision API reachable (expected 400)`로 통과.

### Phase 9: 반응형 3종 뷰포트 (Responsive Check)
* **검증 목적**: 대시보드가 데스크톱/태블릿/모바일 3종 뷰포트에서 레이아웃이 깨지지 않는지 검증.
* **대응 인텐트**: `responsive_check`
* **액션**:
  1. Playwright에서 `page.set_viewport_size()`로 3종 뷰포트 설정.
  2. 각 뷰포트에서 `dashboard_url` 로드. 기본값은 `http://localhost:5173`.
  3. `document.documentElement.scrollWidth > document.documentElement.clientWidth` 평가 (가로 스크롤 발생 여부).
* **뷰포트 정의**:
  | 이름 | 해상도 |
  |------|--------|
  | Desktop | 1280×800 |
  | Tablet | 768×1024 |
  | Mobile | 375×812 |
* **통과 조건(Assertion)**:
  - 3개 중 2개 이상 뷰포트에서 가로 스크롤이 없어야 함.
  - `#app` 요소가 각 뷰포트에서 visible이어야 함.
* **✅ 최근 결과**: PASS — 173ms, 3/3 뷰포트 전체 통과 (✅ desktop, ✅ tablet, ✅ mobile).

---

## Phase 10: 통합 자가 진단 (Full Integration Self-Test)

* **검증 목적**: Phase 1~9의 모든 기능이 하나의 `run_all()` 호출로 자동 테스트되는지 검증.
* **트리거 방법**:
  - API: `POST /api/agent/tools/browser/self-test`
  - Command Palette → `🧪 Run Self-Test (Cmd+Shift+T)`
  - 포트 변경 시 body에 `base_url`, `dashboard_url`, `ws_url` 명시
* **실행되는 전체 인텐트** (10개):

| # | ID | 카테고리 | 대응 Phase | 기준 시간 |
|---|-----|---------|-----------|----------|
| 1 | `health_api` | API | Phase 5 | < 100ms |
| 2 | `models_api` | API | Phase 5 | < 100ms |
| 3 | `vision_analyze` | API | Phase 8 | < 100ms |
| 4 | `external_brain_list` | API | Phase 7 | < 500ms |
| 5 | `dashboard_load` | UI | Phase 1 | < 3,000ms |
| 6 | `chat_send` | Integration | Phase 3 | < 60,000ms |
| 7 | `file_explorer` | UI | Phase 4 | < 3,000ms |
| 8 | `terminal_ws` | Integration | Phase 4 | < 5,000ms |
| 9 | `autonomous_qa_dry` | Integration | Phase 6 | < 5,000ms |
| 10 | `responsive_check` | UI | Phase 9 | < 10,000ms |

* **통과 조건(Assertion)**:
  - 전체 10개 인텐트 중 8개 이상 통과 (80%).
  - 마크다운 리포트에 각 인텐트의 상태/소요시간이 포함.
  - 리포트가 채팅창에 자동 출력되어야 함.
* **✅ 최신 재검증 결과**: **10/10 전체 통과 (100%, 총 1,993ms)** — `POST /api/agent/tools/browser/self-test` 기본 `{}` 호출 기준, DOM QA Agent 검증 완료.

**최신 재검증 명령어**:
```bash
curl -s -X POST http://127.0.0.1:8012/api/agent/tools/browser/self-test \
  -H 'Content-Type: application/json' \
  -d '{}'
```

---

## Phase 11: 코드 레벨 회귀 및 보안 계약 테스트

* **검증 목적**: UI 하네스만으로 잡히지 않는 API 계약, 권한 경계, 하네스 설정 주입, 에이전트 도구 실행 경로를 회귀 테스트로 고정.
* **실행 명령어**:
```bash
cd /path/to/antigravity-k
python -m ruff check src tests
python -m pytest
python -m compileall -q src tests
cd dashboard && npm run build
```
* **핵심 테스트 파일**:
  - `tests/test_agent_tools_api.py`
  - `tests/test_harness_config.py`
  - `tests/test_agent_program_creation.py`
  - `tests/test_api_server.py`
  - `tests/test_goal_runner.py`
* **통과 조건(Assertion)**:
  - `python -m ruff check src tests` 통과.
  - `python -m pytest` 전체 통과.
  - `python -m compileall -q src tests` 통과.
  - `npm run build` 통과.
  - `vision_analyze` 스크린샷 없음 케이스는 HTTP 400.
  - 위험 shell 명령 `rm -rf /`는 HTTP 403.
  - 프로젝트 외부 파일 쓰기는 HTTP 403.
  - `TestHarness`는 `base_url`, `dashboard_url`, `ws_url` 변경을 반영해야 함.
* **✅ 최신 재검증 결과**:
```text
python -m ruff check src tests
All checks passed!

python -m pytest
233 passed in 7.53s

python -m compileall -q src tests
PASS

dashboard npm run build
PASS
```

---

### Phase 14: 출력 품질 비교 검증 (Output Quality Gate)
* **검증 목적**: Antigravity-K의 출력물 품질을 Codex/Claude Code 수준과 1:1 비교 검증.
* **테스트 입력**: "Python으로 GCD 함수를 유클리드 호제법과 반복문 2가지로 작성 + 시간복잡도 비교"
* **통과 조건(Assertion)**:
  - 응답에 **한국어 설명**이 포함되어야 함 (코드-only 불가)
  - **Big-O 표기**가 포함되어야 함 (O(log(min(a,b))) 등)
  - **코드 블록**이 포함되어야 함 (```python)
  - **💡 팁/참고 섹션**이 포함되어야 함
  - 3개 이상 방법 비교 시 **비교 표**가 포함되어야 함
  - Adaptive Mode에서 불필요 레이싱이 자동 스킵되어야 함
* **관련 수정 사항**:
  - `tdd_engine.py` — `_reconstruct_response()`, `_should_skip_racing()`, `_get_local_only_candidate()` 추가
  - `prompt_builder.py` — Output Quality Gate 규칙 11~16 추가
  - `chat.py` — TDD 응답 포맷 3단 구조(메타→설명→코드) 변경
* **✅ 최근 결과**: Adaptive Mode + Response Reconstructor 동작 확인, Big-O 포함, 한국어 설명 포함

---

## 등록된 API 엔드포인트 전체 목록

테스트 대상 API 엔드포인트 (2026-05-06 기준):

```
POST /api/agent/tools/browser/action         — 브라우저 액션 실행
POST /api/agent/tools/browser/self-test      — 통합 자가 진단
POST /api/agent/tools/browser/autonomous-qa  — 자율 QA 루프
POST /api/agent/tools/browser/vision-analyze — 비전 분석
POST /api/agent/tools/fs/read                — 파일 읽기 (PermissionGate 적용)
POST /api/agent/tools/fs/write               — 파일 쓰기 (PermissionGate 적용)
POST /api/agent/tools/shell/run              — shell 실행 (PermissionGate 적용)
GET  /api/agent/tools/external-brain/list    — 외부 두뇌 목록
POST /api/agent/tools/external-brain/send    — 외부 두뇌 프롬프트 전송
GET  /health                                 — 헬스 체크 호환 alias
GET  /v1/health                              — OpenAI 호환 헬스 체크
POST /api/slash                              — 슬래시 명령 실행 (`/goal` 포함)
GET  /api/slash/completions                  — 슬래시 명령 자동완성
POST /api/harness/self-test                  — 하네스 자가 진단
GET  /api/harness/results                    — 하네스 결과 조회
GET  /api/harness/trend                      — 하네스 트렌드
```

---

## Phase 12: API-Driven Autonomous E2E Workflow (Planning-Execution Loop)

* **검증 목적**: 프론트엔드 개입 없이 백엔드 API만을 통해 모델이 자율적으로 계획(Plan)을 수립하고, 사용자 자동 승인에 따라 도구(Tool)를 활용해 코드를 구축하는 전체 사이클 검증.
* **실행 명령어**:
```bash
cd /path/to/antigravity-k
python run_e2e_test.py
```
* **검증 포인트 (테스트 대상 로직)**:
  - `chat.py` 스트리밍 통신 및 상태 추적 대기 (`WAITING_FOR_USER_APPROVAL`).
  - `ToolCallParser`의 도구 호출 태그 파싱 방어력 (모델의 `<tool_name>` 환각 방어).
  - `PermissionGate`의 Sandbox 권한 검사 (허가된 `project_root` 내 파일 쓰기).
* **통과 조건(Assertion)**:
  - 기획 작성 후 승인 대기 단계에서 멈춤 확인.
  - "승인" 신호를 받아 실제 도구 실행 모드로 전환.
  - `write_file` 호출이 `[APPROVAL REQUIRED]` 없이 정상 수행되어 파일(예: `index.html`, `style.css`)이 온전히 생성될 것.
  - 파서 오류 발생 시 에이전트가 자체적으로 Self-Healing을 거쳐 정상 종료(`Exit code 0`)될 것.
* **✅ 최신 재검증 결과**: PASS — 기획안 자동 승인 수신 후 대상 디렉토리 구축 완수. (종료 코드 0)

---

## Phase 13: `/goal` 자율 목표 계약 테스트

* **검증 목적**: Codex식 목표 고정, 성공 기준, Plan/Act/Observe, 검증 게이트, 증거 리포팅 루프를 Antigravity-K의 슬래시 명령과 채팅 UI에 이식했는지 검증.
* **대상 구현**:
  - `src/antigravity_k/engine/goal_runner.py`
  - `src/antigravity_k/engine/slash_commands.py`
  - `src/antigravity_k/api/routes/chat.py`
  - `dashboard/src/command_palette.js`
* **트리거 방법**:
  - 채팅창: `/goal DOM 기능을 테스트하고 리포트를 업데이트해줘`
  - API: `POST /api/slash {"command":"/goal ..."}`
  - OpenAI 호환 API: `POST /v1/chat/completions`의 최신 user message가 `/goal ...`인 경우
  - Command Palette: `Autonomous Goal (/goal)` 선택 → 채팅 입력창에 `/goal ` 프리필
* **통과 조건(Assertion)**:
  - 응답에 `# /goal Autonomous Goal Contract`가 포함되어야 함.
  - `Readiness`, `Success Criteria`, `Autonomous Judgment Policy`, `Autonomous Loop`, `Capability Transfer Matrix`, `Next Actions` 섹션이 포함되어야 함.
  - 일반 검증 가능 목표는 `execute_with_verification`, 고위험 목표는 `approval_required`, 목표 누락은 `clarify_objective`로 판단되어야 함.
  - 고위험 목표(예: 운영 배포, 삭제, 시크릿 포함)는 `approval-gated`로 분류되어야 함.
  - 채팅 UI에서 `/goal` 전송 시 `API 요청 중 오류` 없이 assistant bubble에 계약 문서가 표시되어야 함.
  - `/api/slash/completions?prefix=/go`가 `/goal`을 반환해야 함.
* **✅ 최신 재검증 결과**:
  - `tests/test_goal_runner.py` PASS.
  - `tests/test_claw_integration.py` 내 `/goal` help/completion/execute PASS.
  - `tests/test_api_server.py` 내 `/v1/chat/completions` slash 라우팅 PASS.
  - In-app Browser DOM 테스트: Command Palette `goal` 검색 → `/goal ` 프리필 확인, 채팅 `/goal` 전송 → `# /goal Autonomous Goal Contract`, `Autonomous Judgment Policy`, `execute_with_verification` 표시 확인.
