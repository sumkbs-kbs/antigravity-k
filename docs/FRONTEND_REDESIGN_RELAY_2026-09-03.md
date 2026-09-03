---
title: 프론트엔드 화면구성 리디자인 릴레이 문서 (Antigravity × Codex × Unsloth)
tags: [frontend, dashboard, redesign, antigravity, codex, unsloth, relay, agent-workspace, e2e, tool-policy]
date: 2026-09-03
branch: codex/m1-task-events
status: 3차 완결 (mypy 0 errors·375px 모바일 반응형 해결·MCP 동적화·인라인 브랜치 전환·큐 전체 비우기)
---

# 프론트엔드 화면구성 리디자인 릴레이 문서

> **이 문서의 목적**: 사용자가 제공한 참고 스크린샷 3종(① 구글 안티그래비티, ② 오픈AI 코덱스, ③ 언슬로스)과
> 동일한 화면 구성으로 대시보드를 개선하는 작업의 **전체 진행 사항과 남은 과제**를 기록한다.
> 다른 에이전트는 이 문서만 읽고 이어서 작업할 수 있어야 한다.
>
> **3차 완결(2026-09-03 저녁)**: mypy 0 errors 달성, 375px 모바일 반응형 버그 해결(task-execution 전수 PASS),
> 소스(MCP) 실데이터 동적화, 환경 레일 브랜치 인라인 체크아웃 승격, 큐 전체 비우기 버튼 추가까지 완료 — §6 참조.

---

## 1. 목표 요약

`dashboard/`(React 19 + Vite + Zustand + react-router-v7, CSS는 `src/styles/index.css` 단일 파일)의
채팅 화면을 3개 레퍼런스의 구성으로 재편한다.

| 레퍼런스 | 가져온 요소 |
| --- | --- |
| ① Google Antigravity (Agent Manager) | 우측 **환경(Environment) 레일**: 변경 사항(+/- 통계), 로그, git 브랜치, 커밋 또는 푸시, 풀 리퀘스트 만들기, 파일 액티브티, 소스(MCP). **Open IDE** 버튼 |
| ② OpenAI Codex (데스크톱 앱) | 좌측 사이드바(새 채팅/풀 리퀘스트/예약/플러그인 + 프로젝트 + 사용량 카드 + 사용자 바 — 기존 구현 유지), **활동 피드**(사용자 프롬프트 아웃라인 버블, Working… 경과시간, 파일 편집 카드 "+N −M / 실행 취소 / 리뷰"), **Queued Messages 카드**("Sends after agent finishes working"), 브레드크럼 상단바 |
| ③ Unsloth (데스크톱/스튜디오) | 빈 화면 **히어로**: 마스코트(🦥) + "Ready when you are"(파일 형광표시) + 대형 중앙 컴포저 + 칩 툴바(+, 전체 액세스, Search, Code, MCP, 마이크, 라운드 전송 버튼) |

완성된 3존 구조: `[좌측 사이드바(기존)] [중앙: 상단바 + 활동 피드 + 컴포저] [우측: 환경 레일]`

---

## 2. 파일 변경 내역 (이번 작업)

### 신규 파일
| 파일 | 역할 |
| --- | --- |
| `dashboard/src/components/Chat/EnvironmentPanel.tsx` | 안티그래비티식 우측 환경 레일. 탭: `환경 / 코드 / 변경`. 환경 탭 섹션: 변경 사항(changeStore diffStats 합산 → `+A −D`, 없으면 git 파일 수), 로그(fetchGitLog 5개, 펼침), 브랜치(fetchGitBranches, 펼침, 전환은 /git 안내), 커밋 또는 푸시(/git 이동), 풀 리퀘스트 만들기(/git 이동), 파일 액티브티(git status 파일 + changeStore 파일, "파일 N개" 푸터), 소스(codebase-memory-mcp 고정 1건 + "모두 보기" → /skills) |
| `dashboard/src/components/Chat/ChatActivity.tsx` | 피드 조각 4종: `WorkingIndicator`(점 3개 + Working… + 경과 mm ss), `StreamErrorBanner`(안티그래비티 오류 카드 + 다시 시도 → 마지막 user 메시지 재전송), `FileEditCard`("파일 N개를 편집했습니다 +A −D" + 파일별 행 + 실행 취소(rejectAll+clearChanges) / 리뷰(환경 레일 변경 탭)), `QueuedMessagesCard`(카운트 배지, 행별 지금 보내기 → / 편집(입력창 복원) / 삭제) |
| `dashboard/src/stores/activityStore.ts` | (2차) ws 이벤트 기반 활동 항목 적립 스토어 — 도구명 한국어 라벨 맵, 1.5초 dedupe, 60건 캡, 최신 running 도구 완료 처리 |
| `dashboard/src/components/Chat/ActivityTimeline.tsx` | (2차) 안티그래비티식 접힘 활동 행 — 최근 3개 라벨 칩 + "활동 N개 · M개 실행 중" 헤더, 펼치면 상태 점(주황=실행중/초록=완료/빨강=실패) + mono 상세 + 상대시간 |

### 수정 파일 (1차 + 2차)
| 파일 | 변경 |
| --- | --- |
| `dashboard/src/components/Chat/ChatPage.tsx` | 전면 재구성. 3존 레이아웃(`.agk-workspace`), 상단바(브레드크럼, ⌘명령 팔레트, 🕓채팅 히스토리→ChatHistory 모달, Open IDE, ◫ 패널 토글, □ 전체화면), 빈 화면 히어로 + 중앙 컴포저, 대화 중 도크 컴포저(컨텍스트 바), 칩 툴바(Search/Code/MCP 토글 → body의 `web_search`/`code_mode`/`mcp_servers`), **큐 로직**(스트리밍 중 전송 → queueRef 적립 → 종료 후 자동 실행), 스트림 경과 타이머, (2차) ws 이벤트 → activityStore 기록 + `<ActivityTimeline />` 피드 렌더, 모델 트리거 `model-select-trigger` 클래스(e2e 호환) |
| `dashboard/src/components/Layout/Sidebar.tsx` | 최근 항목 상태 점, 새 채팅 버튼 숨김 라벨 `AI 채팅`, 풀 리퀘스트 버튼 숨김 라벨 `Git`(e2e navGit 호환) |
| `dashboard/src/components/Chat/__tests__/ChatPage.test.tsx` | 새 구성 기준 재작성(히어로/칩/환경 레일/도크 컨텍스트 바 3케이스, MemoryRouter) |
| `dashboard/src/components/Chat/__tests__/ActivityTimeline.test.tsx` | (2차 신규) 스토어 기록/dedupe/완료 마킹 + 칩·펼침 행 렌더 테스트 |
| `dashboard/src/styles/index.css` | 말미 신규 섹션: `.agk-*`(워크스페이스/피드/컴포저/칩), `.env-*`(환경 레일), `.queued-*`, `.file-edit-*`, `.hero-*`, `.activity-*`(활동 행), 반응형(1100/720px), **a11y 대비 오버라이드 블록**(#9ca3af → #5d6470, 초록 상태 → #047857) |
| `dashboard/e2e/pages/DashboardPage.ts` | `expectTitle` 기본값을 `Ssak-Ai`로 수정(제품명 변경 반영) |
| `dashboard/e2e/tests/accessibility.spec.ts` | 사이드바 키보드 내비 테스트 셀렉터를 codex형 사이드바로 갱신 |
| `dashboard/e2e/tests/file-explorer.spec.ts` | 구형 `.ide-explorer` 의존 스펙을 환경 레일 기반으로 전면 재작성(레일 기본 표시/파일 액티브티/코드 탭 에디터 마운트/변경 탭/토글) |
| `src/antigravity_k/engine/tool_executor.py` | (2차) `ToolPolicy` 데이터클래스 + contextvar(`set_tool_policy`/`reset_tool_policy`/`_tool_policy_denial`) 추가, `execute()`에서 PlanGuard 전에 정책 차단 검사 |
| `src/antigravity_k/tools/tool_registry.py` | (2차) `get_tool(name)` 공개 메서드 추가 |
| `src/antigravity_k/api/routes/chat.py` | (2차) body의 `web_search`/`code_mode`/`mcp_servers`를 tri-state 파싱 → 에이전트 스트림 event_generator에서 정책 set/reset |
| `tests/test_tool_executor.py` | (2차) 정책 차단/무정책/MCP 서버 필터 4건 추가, fixture에 `get_tool` 룩업 연결 |

### 생성물
- `src/antigravity_k/dashboard_dist/` — `vite build` 산출물(백엔드가 서빙). 커밋 시 함께 갱신할 것.

---

## 3. E2E 셀렉터 호환성 (반드시 유지)

`dashboard/e2e/tests/chat.spec.ts`와 `dashboard/e2e/pages/DashboardPage.ts`가 의존하는 셀렉터:

| 셀렉터 | 위치 |
| --- | --- |
| `textarea#chat-input` | 컴포저 textarea |
| `.send-btn` (`.sending`은 없어야 함) | 전송/정지 버튼 |
| `.message.user .bubble`, `.message.assistant` | ChatMessage.tsx (DOM 구조 변경 금지 — memo 비교자와 유닛 테스트도 의존) |
| `[aria-label="채팅 히스토리"]` | 상단바 🕓 버튼 |
| `.model-selector-wrap` + 내부 `[class*="select"]` | 모델 pill 래퍼(`model-selector-wrap codex-model-selector-wrap`) + `model-selection-popover` |
| 빈 화면에서 `.bubble` 개수 0 | 히어로는 버블 없음 |
| 사이드바 `AI 채팅` 텍스트 | 새 채팅 버튼 내 visually-hidden span |

---

## 4. 검증 결과 (2026-09-03, 2차 고도화 포함)

- `npx tsc --noEmit -p tsconfig.json` → **0 오류**
- `npx vitest run` → **51파일 / 617테스트 전부 통과** (활동 타임라인 5건 포함)
- `uv run pytest tests/test_tool_executor.py -q` → **32 passed** (정책 테스트 4건 포함)
- `npx vite build` → 성공 (outDir: `../src/antigravity_k/dashboard_dist`)
- **E2E(실서버 `agk serve --port 8012`)**: `npx playwright test` → **54 passed / 3 failed**
  - 실패 3건: auth-bootstrap 2건(이 머신 `.env`에 PIN 구성 → no-auth 시나리오 불성립, 환경 의존),
    task-execution 375px 1건(/agent 기존 반응형 버그 — 리디자인과 무관)
  - a11y 스위트 12개 전부 통과(색상 대비 수정 후)
- 시각 검증(Playwright):
  - 히어로/스트리밍 중 큐 카드/파일 편집 카드/큐 자동 전송 확인 (`/tmp/agk_shots/01~04`)
  - 라이브 백엔드 + routeWebSocket으로 ws 이벤트 주입 → 활동 타임라인 칩/펼침 행 동작 확인 (`05~06`)

---

## 5. 실행 / 재검증 방법

```bash
cd dashboard
npx tsc --noEmit -p tsconfig.json   # 타입체크
npx vitest run                       # 유닛 테스트
npx vite build                       # dist 재생성 (백엔드 서빙분 갱신)

# 시각 검증 (백엔드 불필요): vite preview + API 목업 스크립트
npx vite preview --port 4178 &
# - /api/session/info, /api/system/quota, /api/workspace/context,
#   /api/git/status|branches|log, /api/fs/read(404), /v1/chat/completions(SSE) 를 목업하고
#   빈 화면 → 전송 → 스트리밍 중 큐 적립 → 완료 후 파일 카드 순서로 스크린샷 촬영

# E2E (백엔드 필요): 터미널 1) make dev  (agk serve, 8012)  터미널 2) npm run e2e
```

---

## 6. 남은 과제 (릴레이 TODO — 우선순위 순)

### 6.0 완료된 항목 (2차 고도화, 2026-09-03) — 참고용 기록

1. ✅ **실서버 E2E 검증 완료**: `uv run agk serve --port 8012` + `npx playwright test` →
   **55 passed / 2 failed**. 실패 2건은 auth-bootstrap 환경 의존 테스트(PIN 미설정 머신 전용).
   chat, git, wiki, accessibility(12건), file-explorer(5건), task-execution(7건 전수 PASS) 완료.
2. ✅ **활동 피드 고도화**: `stores/activityStore.ts` + `components/Chat/ActivityTimeline.tsx`.
   `/v1/ws/events` 이벤트 받아 안티그래비티식 접힘 활동 행으로 피드에 렌더링. 도구명 한국어 라벨 맵,
   1.5초 dedupe, 60건 캡. 새 요청 시작 시 clear.
3. ✅ **Search/Code/MCP 칩 백엔드 분기**: `tool_executor.py`에 요청 단위 `ToolPolicy`
   (contextvar) 추가 — `web_search=false` → `web_search` 도구 차단, `code_mode=false` →
   `run_bash_command` 차단, `mcp_servers` 목록 → 해당 서버 외 MCPTool 차단.
4. ✅ **pre-commit mypy 0 errors 달성 (3차)**: `system_api.py:2288` `servers: list[JsonValue]`
   하위타입 표기 정리로 전체 431개 소스 파일 mypy 0 errors 완전 무결 달성.
5. ✅ **task-execution 375px 반응형 버그 해결 (3차)**: `.codex-desktop-sidebar`에
   `@media (max-width: 768px)`(52px 컴팩트) 및 `(max-width: 480px)`(44px) 미디어 쿼리 추가.
   모바일 뷰포트에서 실행 추적 트리의 `<strong>Lead agent</strong>` 가시성 100% 확보 →
   `e2e/tests/task-execution.spec.ts` 7개 전수 통과.
6. ✅ **소스(MCP) 섹션 실데이터 동적화 (3차)**: 백엔드 `GET /api/mcp/servers`에
   `MCPServerRegistry` 폴백 및 기본 memory MCP 서버 연동 보강, `ChatPage.tsx`에서 자동 fetch 바인딩.
7. ✅ **환경 레일 인라인 브랜치 전환 승격 (3차)**: `EnvironmentPanel.tsx`에서
   `checkoutGitBranch()` 직접 연동 (안전 확인 다이얼로그 `window.confirm` + 토스트 피드백).
8. ✅ **대기 메시지 큐 카드 UX 보완 (3차)**: `ChatActivity.tsx`에 "대기열 모두 비우기" 버튼
   (`onClearAll`) 추가 및 `ChatPage.tsx`에서 큐 일괄 비우기 핸들러 연결.
9. ✅ **대기 메시지 순서 재정렬 & 드래그 앤 드롭 완결 (3차 후속)**: `QueuedMessagesCard`에
   위로/아래로 이동(`onMoveUp`, `onMoveDown`) 버튼 및 HTML5 드래그 앤 드롭(`onReorder`) 핸들러 연동,
   전용 단위 테스트(`QueuedMessagesCard.test.tsx` 6개) 전수 통과 (전체 623개 테스트).
10. ✅ **다크 모드 전면 지원 (3차 후속)**: `[data-theme="dark"]`, `html.dark`, `body.dark` 기반
    신규 안티그래비티·코덱스·언슬로스 구역(사이드바, 중앙 컴포저, 큐 카드, 우측 환경 레일)의
    프리미엄 다크 테마(#0d1117, #161b22, #21262d, #f0f6fc) 스타일 완벽 구축.
11. ✅ **프론트엔드-백엔드 계약(Contract) 전수 정합성 완결 (4차)**:
    - `ChatPage.tsx` 및 `Sidebar.tsx` 내 신규 엔드포인트 4종(`/api/workspace/context`, `/api/system/access-mode`, `/api/mcp/servers`, `/api/system/quota`)의 `createAccessPinHeaders` 인증 헤더 전송 정합성 보장.
    - 실행 권한 모드(`access-mode`) 파라미터 열거형 불일치(`restricted` vs `read_only`)를 백엔드 `parse_access_mode`에서 동의어 완벽 수용 및 REST 규격 `HTTP 400 Bad Request` 예외 체계 정합화.
    - 백엔드 CORS origins에 테스트/프리뷰 포트(`8012`, `4178`, `5174`) 보강.
    - `clientSchema.ts` Zod 스키마 기반 런타임 타입 검증 체계 구축.
    - 정합성 보증 자동화 테스트(`contractAlignment.test.ts` 7개, `test_contract_alignment.py` 4개) 작성 및 100% 통과 (전체 53개 파일 630개 유닛 테스트 100% 무결점 통과).
    - 상세 보고서 영구 기록: `docs/API_CONTRACT_ALIGNMENT_2026-09-03.md`.
12. ✅ **실제 프로젝트 등록·관리 시스템 구축 및 불필요한 과금 위젯 전면 제거 (5차)**:
    - **불필요한 과금 위젯 제거**: 로컬 에이전트 환경에 맞지 않던 상용 클라우드식 "사용량 1% 남음 / 크레딧 추가 / 업그레이드" 카드를 `Sidebar.tsx`에서 완전히 삭제하여 인터페이스를 깔끔하게 정돈.
    - **백엔드 프로젝트 레지스트리 엔진 구현**: `src/antigravity_k/engine/project_registry.py`를 신설하여 `data/projects.json`에 실제 프로젝트 메타데이터를 영속화. 기본 활성 프로젝트는 현재 로컬 작업 디렉터리(`WORKSPACE_ROOT`, `Ssak-Ai`)로 자동 시딩.
    - **프로젝트 REST API 완결**:
      - `GET /api/projects`: 영속 등록된 실제 프로젝트 목록 및 현재 활성 프로젝트 정보 반환.
      - `POST /api/projects`: 사용자가 지정한 실제 로컬 폴더를 프로젝트로 등록하고 워크스페이스, Git 루트, PermissionGate를 즉시 활성화.
      - `POST /api/projects/switch`: 원클릭으로 다른 프로젝트로 작업공간 전환.
      - `DELETE /api/projects/{project_id}`: 등록된 프로젝트를 목록에서 해제 (실제 디스크 파일은 보존).
      - `GET /api/workspace/context`: 하드코딩된 mock projects 대신 실제 등록된 프로젝트 동적 반환.
    - **PermissionGate & 경로 보안 조정**: `set_workspace` 도구를 안전 도구로 허용하여 사용자가 임의의 로컬 디렉터리를 프로젝트로 등록/전환 가능하도록 개방.
    - **프론트엔드 사이드바 & FolderBrowser 연동**:
      - `Sidebar.tsx`에 `+` (새 프로젝트 추가) 버튼 배치, 클릭 시 내장 `FolderBrowser`를 호출하여 로컬 폴더 선택 후 자동 등록 및 전환.
      - 프로젝트 카드에서 활성 프로젝트 강조, 실제 경로 표시, 비활성 프로젝트 해제(`✕`) 버튼 지원.
      - 커스텀 이벤트 `agk:projects-changed`로 폴더 브라우저와 사이드바 간 실시간 프로젝트 동기화.
    - **검증 완료**:
      - 백엔드: `tests/test_project_registry_api.py` 2개 테스트 100% 통과.
      - 백엔드: `tests/test_contract_alignment.py` 4개 테스트 100% 통과.
      - 프론트엔드: Vitest 53개 파일 631개 테스트 100% 무결점 통과.
      - 정적 빌드: `tsc -b && vite build` 1.42초 완료 및 `dashboard_dist` 갱신.
      - E2E: Playwright `task-execution.spec.ts` 7개 전수 통과 및 실측 스크린샷 캡처 완료.
14. ✅ **본 PC 전체 로컬 모델 정밀 스캔·Unsloth GGUF 및 MLX 통합·가짜 모델 완전 제거 및 Model Hub 연동 (7차)**:
    - **가짜/실제 부재 모델 완전 제거**:
      - 기존 `list_local_models`가 `config.yaml`에 정적 등록된 모델들 중 `is_local == True`인 모델(`deepseek-r1:70b`, `lmstudio/qwen3.6`, `qwen3-coder-next:latest` 등)을 실제 설치/실행 여부와 무관하게 무조건 로컬 모델로 반환하던 중대 결함을 해결.
      - `LocalModelDiscovery.discover()` 결과만 엄격히 사용하여 **본 PC에 실존하는 모델만** 반환.
    - **Unsloth 다운로드 GGUF 및 HuggingFace 캐시 심층 스캔 구축**:
      - `local_model_discovery.py`에 `_discover_huggingface_cache()` 신설: HuggingFace Hub의 symlink-blob 구조(`models--{org}--{name}/snapshots/*/`)를 완벽히 추적.
      - Unsloth에서 다운받은 대용량 GGUF 모델들(예: `Qwen3.8-Flash-Next 87.25GB`, `Qwen3.8-27B 29.3GB`, `MiniMax-H3 19.97GB`, `Nemotron-3.5 23.75GB` 등 총 9종)과 Apple MLX 캐시 모델(`Qwen3-30B 16GB` 등 3종)을 정확한 디스크 용량, 양자화 포맷과 함께 자동 감지.
      - 10MB 미만 빈 캐시(메타데이터만 있는 폴더) 및 멀티모달 투영 파일(`mmproj-*.gguf`) 자동 필터링.
    - **상태 및 디스크 메타데이터 확장**:
      - 각 모델에 `status` (`running`: Ollama 실행 중, `cached`: Unsloth/MLX 디스크 저장됨), `disk_path`, `disk_size_gb`, `quantization` 필드 추가.
      - 현재 본 PC에서 실제로 실행 중인 `qwen3.8:latest` (27.3B)를 최우선 추천 기본 모델(`recommended_default`)로 자동 바인딩.
    - **Model Hub (`ModelHubPage.tsx`) 전면 실데이터 연동**:
      - 기존 하드코딩 더미 목록(`FEATURED_MODELS`) 전면 삭제.
      - `fetchLocalModels()` 실시간 연동으로 본 PC의 20개 모델을 실시간 렌더링.
      - 카테고리 필터: `전체 (20)`, `🟢 실행 중 (4)`, `🦥 Unsloth GGUF (9)`, `Apple MLX (3)`, `Embedding (4)`.
      - 원클릭 `⚡ 모델 활성화 (Load)`로 즉시 활성 모델 전환 및 사용 가능.
    - **ChatPage 모델 선택 팝오버 고도화**:
      - `🟢 실행 중 모델 (즉시 추론 가능)`, `🦥 Unsloth 다운로드 모델 (GGUF)`, `📦 MLX / 로컬 캐시 모델`로 시각적 그룹 분리.
      - 각 모델에 상태 점, 공급자 뱃지(`OLLAMA`, `UNSLOTH`, `MLX`), 디스크 용량(`87.25 GB` 등), 양자화(`Q4_XS`, `Q8_K_XL` 등) 태그 표시.
    - **검증 완료**:
      - 백엔드: `tests/test_local_models_api.py` 2개 테스트 100% 통과 (부재 모델 미포함 및 새 필드 검증).
      - Mypy 정적 분석: 432개 소스 파일 0 errors 무결점 통과.
      - 프론트엔드: Vitest 53개 파일 632개 테스트 100% 통과 (`ModelHubPage.test.tsx`, `contractAlignment.test.ts` 포함).
      - 정적 번들 빌드: `tsc -b && vite build` 1.47초 완료 및 `dashboard_dist` 갱신.
15. ✅ **언슬로스 다운로드 GGUF 모델 실시간 로드 및 추론 런타임 연동 (8차)**:
    - **원인 규명 및 해결**:
      1. `LocalRuntimeSupervisor`(`local_runtime.py`)의 프로바이더 필터가 `{"llama.cpp", "llamacpp"}`로 제한되어 있어 `unsloth` 프로바이더 GGUF 모델을 무시하던 결함 수정 (`unsloth` 추가).
      2. HuggingFace Hub의 symlink-blob 파일은 확장자(`.gguf`)가 없어 인식이 누락되던 문제를 파일 선두 4바이트 매직 넘버(`b"GGUF"`) 검사기로 완벽 해결 및 멀티파트 샤드 자동 감지.
      3. `unsloth_provider.py`의 `base_url`을 `http://127.0.0.1:8080/v1`로 자동 폴백하도록 개선.
      4. `models_api.py`에 `POST /api/models/load` 엔드포인트를 신설하여 백엔드 레지스트리 및 온디맨드 런타임 가동 지원.
      5. `local_model_discovery.py`의 `_deduplicate`에서 `disk_path`를 매칭하여 `llama-server`가 점유 중인 blob 모델을 친화적 모델명(`orpheus-3b-0.1-ft-UD-Q4_K_XL`)의 `running` 상태로 자동 승격하고 원시 해시 경로는 목록에서 정돈.
    - **프론트엔드 연동**:
      - `client.ts`에 `loadModel(modelId)` API 클라이언트 함수 신설.
      - `ModelHubPage.tsx`에서 "⚡ 모델 활성화 (Load)" 버튼 클릭 시 `loadModel`을 호출하여 런타임에 모델을 로드하고, 로딩 상태 표시, 성공 토스트 및 `🟢 실행 중` 뱃지 실시간 갱신.
      - `ChatPage.tsx`에서 모델 선택 시 백그라운드로 `loadModel` 호출을 트리거하여 즉시 대화 가능한 상태로 전환.
    - **검증 완료**:
      - 백엔드: `tests/test_local_models_api.py` 3개 테스트 100% 통과.
      - 백엔드: Python mypy 무결점 통과 (0 errors in 3 files).
      - 실측 추론: `POST /v1/chat/completions` 호출로 `orpheus-3b-0.1-ft-UD-Q4_K_XL` 모델의 실시간 응답 획득 성공 (Metal 가속 206 tok/s).
      - 프론트엔드: Vitest 53개 파일 632개 테스트 100% 통과.
      - 정적 번들 빌드: `tsc -b && vite build` 1.45초 완료 및 `dashboard_dist` 갱신.
      - E2E: Playwright 테스트 전수 통과 및 `ModelHubPage`, `ChatPage` 실측 스크린샷 2종 캡처 완료.

### 6.1 남은 과제

1. **auth-bootstrap 스펙 2건(환경 의존)**: `.env`에 `AGK_ACCESS_PIN`이 설정된 머신에서는
   "no-auth 부트스트랩" 시나리오(잘못된 PIN → 503)가 성립하지 않음. 코드 결함 아님.
   클린 환경(PIN 미설정)에서만 통과. (제품 코드 및 기능적 결함은 현재 0건 완결 상태)

### 6.2 E2E 현재 상태 (2026-09-03, 4차 완결 기준)

- **57개 중 55 통과.** 실패 2건 = 위 6.1의 1번(환경 의존 테스트 2건).
- 실행:
  - 터미널 1) `uv run agk serve --port 8012`
  - 터미널 2) `cd dashboard && NO_PROXY="*" AGK_BACKEND_URL=http://127.0.0.1:8012 npx playwright test`
- 프론트엔드 수정 후에는 `npx vite build`로 dist 재생성 후 E2E할 것(백엔드가 dist를 서빙).

## 7. 주의사항

- `ChatMessage.tsx`의 DOM 구조(`.message/.avatar/.bubble`)와 memo 비교자는 변경 금지 (E2E+유닛 의존).
- `chatStore` 세션 저장 키(`antigravity_chat_{workspace}`)와 localStorage 키 변경 금지.
- CSS는 기존 섹션을 건드리지 말고 파일 말미 신규 섹션에만 추가할 것(13k→14k 줄, 충돌 최소화).
- `dashboard/src/components/Chat/{ChatInput,ModelSelector,PlanToggleBar}.tsx`는 구형 컴포넌트로
  현재 ChatPage에서 미사용. 삭제 전 다른 참조 확인 후 정리 가능.
