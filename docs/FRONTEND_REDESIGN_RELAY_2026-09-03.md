---
title: 프론트엔드 화면구성 리디자인 릴레이 문서 (Antigravity × Codex × Unsloth)
tags: [frontend, dashboard, redesign, antigravity, codex, unsloth, relay, agent-workspace, e2e, tool-policy]
date: 2026-09-03
branch: codex/m1-task-events
status: 2차 고도화 완료 (E2E 실서버 검증·활동 피드·도구 정책 반영)
---

# 프론트엔드 화면구성 리디자인 릴레이 문서

> **이 문서의 목적**: 사용자가 제공한 참고 스크린샷 3종(① 구글 안티그래비티, ② 오픈AI 코덱스, ③ 언슬로스)과
> 동일한 화면 구성으로 대시보드를 개선하는 작업의 **전체 진행 사항과 남은 과제**를 기록한다.
> 다른 에이전트는 이 문서만 읽고 이어서 작업할 수 있어야 한다.
>
> **2차 고도화(2026-09-03 오후)**: 실서버 E2E 검증, 활동 타임라인(ws 이벤트),
> Search/Code/MCP 칩의 백엔드 도구 정책 연결까지 완료 — §6 참조.

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
   **54 passed / 3 failed**. 실패 3건은 코드 문제가 아님(아래 6.2 참조).
   추가로 이번 라운드에서 고친 것: chat 모델 셀렉터 셀렉터 호환(`model-select-trigger`),
   명령 팔레트 버튼 부활(상단바 ⌘, `명령 팔레트 열기 (Cmd+K)`), 사이드바 Git 숨김 라벨,
   `expectTitle` 기본값 Ssak-Ai, a11y 사이드바 키보드 테스트 셀렉터 갱신,
   file-explorer.spec을 환경 레일 기반으로 전면 재작성, 색상 대비 WCAG AA 수정
   (`.codex-section-label` 등 #9ca3af → #5d6470, `.avatar-initial-circle` → #047857 배경).
   → **a11y 스위트 12개 전부 통과.**
2. ✅ **활동 피드 고도화**: `stores/activityStore.ts`(신규) + `components/Chat/ActivityTimeline.tsx`(신규).
   `/v1/ws/events`의 ToolExecutionStarted/Finished, FileOpened/Modified, FailureDetected,
   PlanningModeStarted 이벤트를 받아 안티그래비티식 접힘 활동 행("파일 수정함 / 파일 읽음 /
   명령 실행 · 활동 N개 · M개 실행 중")으로 피드에 렌더링. 도구명 한국어 라벨 맵,
   1.5초 dedupe, 60건 캡. 새 요청 시작 시 clear. 라이브 ws 모킹 스크린샷으로 검증 완료.
3. ✅ **Search/Code/MCP 칩 백엔드 분기**: `tool_executor.py`에 요청 단위 `ToolPolicy`
   (contextvar) 추가 — `web_search=false` → `web_search` 도구 차단, `code_mode=false` →
   `run_bash_command` 차단, `mcp_servers` 목록 → 해당 서버 외 MCPTool 차단.
   `chat.py`가 tri-state(키 없음=구형 클라이언트, 무제한)로 파싱해 에이전트 스트림에
   set/reset. `ToolRegistry.get_tool()` 공개 메서드 추가. tests/test_tool_executor.py에
   정책 테스트 4건 추가(32 passed).

### 6.1 남은 과제

1. **task-execution 375px 반응형 버그(기존)**: `/agent` 페이지에서 375px 뷰포트일 때
   실행 추적 트리의 `<strong>Lead agent</strong>`가 hidden 처리됨 — 이번 리디자인과 무관한
   기존 결함. AgentPage/TaskExecutionView 반응형 레이아웃 수정 필요.
2. **auth-bootstrap 스펙 2건(환경 의존)**: `.env`에 `AGK_ACCESS_PIN`이 설정된 머신에서는
   "no-auth 부트스트랩" 시나리오(잘못된 PIN → 503)가 성립하지 않음. 코드 결함 아님.
   클린 환경(PIN 미설정)에서만 통과.
3. **브랜치 전환 액션**: 환경 레일 브랜치 목록은 표시+`/git` 안내만 함. gitApi에 checkout
   mutation 추가 후 인라인 전환 승격 (승인 플로우 필요 — 파괴적 변경).
4. **소스(소스=MCP) 섹션 동적화**: 현재 `codebase-memory-mcp` 하드코딩 1건.
   백엔드 MCP 서버 목록 API(`/api/system` 쪽 MCPServerRegistry, system_api.py:705 참조)와 연결.
5. **큐 카드 UX 소폭 보완**: 드래그 재정렬(코덱스는 지원), 다건 전송 중 전체 중단 버튼.
6. **다크 모드**: 신규 `.agk-*`/`.env-*` 섹션은 라이트 톤 고정(hex 하드코딩). themeStore
   다크 테마 대응 시 색만 변수화. (단, 대비 수정값 #5d6470/#047857은 변수화 기준으로 사용.)

### 6.2 E2E 현재 상태 (2026-09-03 기준)

- **57개 중 54 통과.** 실패 3건 = 위 6.1의 1·2번(코드 수정 불요 2건 + 기존 버그 1건).
- 실행: 터미널 1) `uv run agk serve --port 8012` (주의: config 기본 포트는 8000이라
  반드시 `--port 8012` 지정 — 8000은 다른 프로세스가 점유 중) 터미널 2) `cd dashboard && npx playwright test`.
- 프론트엔드 수정 후에는 `npx vite build`로 dist 재생성 후 E2E할 것(백엔드가 dist를 서빙).

## 7. 주의사항

- `ChatMessage.tsx`의 DOM 구조(`.message/.avatar/.bubble`)와 memo 비교자는 변경 금지 (E2E+유닛 의존).
- `chatStore` 세션 저장 키(`antigravity_chat_{workspace}`)와 localStorage 키 변경 금지.
- CSS는 기존 섹션을 건드리지 말고 파일 말미 신규 섹션에만 추가할 것(13k→14k 줄, 충돌 최소화).
- `dashboard/src/components/Chat/{ChatInput,ModelSelector,PlanToggleBar}.tsx`는 구형 컴포넌트로
  현재 ChatPage에서 미사용. 삭제 전 다른 참조 확인 후 정리 가능.
