---
title: 프론트엔드 화면구성 리디자인 릴레이 문서 (Antigravity × Codex × Unsloth)
tags: [frontend, dashboard, redesign, antigravity, codex, unsloth, relay, agent-workspace]
date: 2026-09-03
branch: codex/m1-task-events
status: 1차 구현 완료 (빌드·유닛·시각검증 통과)
---

# 프론트엔드 화면구성 리디자인 릴레이 문서

> **이 문서의 목적**: 사용자가 제공한 참고 스크린샷 3종(① 구글 안티그래비티, ② 오픈AI 코덱스, ③ 언슬로스)과
> 동일한 화면 구성으로 대시보드를 개선하는 작업의 **전체 진행 사항과 남은 과제**를 기록한다.
> 다른 에이전트는 이 문서만 읽고 이어서 작업할 수 있어야 한다.

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

### 수정 파일
| 파일 | 변경 |
| --- | --- |
| `dashboard/src/components/Chat/ChatPage.tsx` | 전면 재구성. 3존 레이아웃(`.agk-workspace`), 상단바(브레드크럼 `antigravity-k / {세션제목}`, 🕓채팅 히스토리→ChatHistory 모달, Open IDE, ◫ 패널 토글, □ 전체화면), 빈 화면 히어로 + 중앙 컴포저, 대화 중 도크 컴포저(컨텍스트 바: 프로젝트/로컬/브랜치), 칩 툴바(Search/Code/MCP 토글은 요청 body에 `web_search`/`code_mode`/`mcp_servers` 포함 — 백엔드는 무시해도 무방), **큐 로직**: 스트리밍 중 전송 시 `queueRef` 적립 → 스트림 종료 후 자동 1건 실행(runRef로 재귀), 스트림 경과 타이머 |
| `dashboard/src/components/Layout/Sidebar.tsx` | 최근 항목에 상태 점(`.recent-status-dot`, hover/active 표시), 새 채팅 버튼에 스크린리더용 `AI 채팅` 라벨(e2e `navChat` 셀렉터 호환) |
| `dashboard/src/components/Chat/__tests__/ChatPage.test.tsx` | 새 구성 기준으로 재작성 (히어로/칩/환경 레일/도크 컨텍스트 바 3케이스, MemoryRouter 사용 — EnvironmentPanel이 useNavigate 사용) |
| `dashboard/src/styles/index.css` | 파일 말미에 `Agent Workspace Redesign — Antigravity × Codex × Unsloth` 섹션(~1,200줄) 추가: `.agk-*`, `.env-*`, `.queued-*`, `.file-edit-*`, `.hero-*`, `.tool-chip`, `.access-chip`, `.mcp-*`, 1100px/720px 반응형 |

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

## 4. 검증 결과 (2026-09-03)

- `npx tsc --noEmit -p tsconfig.json` → **0 오류**
- `npx vitest run` → **50파일 / 612테스트 전부 통과**
- `npx vite build` → 성공 (outDir: `../src/antigravity_k/dashboard_dist`)
- Playwright 시각 검증(`vite preview :4178` + API 루트 목업):
  - 빈 화면: 히어로 중앙 정렬 + 칩 텔레바 + 환경 레일 확인
  - 스트리밍 중: 사용자 버블 / Working… 경과시간 / Queued Messages(1) 카드 / 정지 버튼 / 토스트 확인
  - 완료 후: 파일 편집 카드("파일 1개를 편집했습니다 +3 −0", 실행 취소/리뷰, 파일 행), 큐 자동 전송(두 번째 프롬프트가 이어서 실행) 확인
  - 스크린샷: `/tmp/agk_shots/01-hero.png ~ 04-expanded.png` (임시 파일, 재생성 스크립트는 이 문서 §5)

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

1. **백엔드 연동 확인(가장 중요)**: 실제 `agk serve` 기동 후 E2E 전량 실행.
   특히 `POST /api/system/access-mode`, `/api/workspace/context`, git 3종 응답 스키마와
   환경 레일 표시값 대조. E2E가 백엔드 없으면 실행 불가(`baseURL = http://127.0.0.1:8012`).
2. **브랜치 전환 액션**: 환경 레일 브랜치 목록은 현재 표시+`/git` 안내만 함.
   `gitApi`에 checkout mutation 추가 후 인라인 전환으로 승격 (승인 플로우 필요 — 파괴적 변경).
3. **소스(소스=MCP) 섹션 동적화**: 현재 `codebase-memory-mcp` 하드코딩 1건.
   백엔드 MCP 서버 목록 API가 있으면 연결(없다면 `/api/skills` 또는 설정 페이지에서 읽기).
4. **Search/Code/MCP 칩의 백엔드 의미 부여**: 요청 body에 `web_search`/`code_mode`/`mcp_servers`를
   이미 실으므로, `src/antigravity_k` 쪽 라우터에서 실제 도구 분기로 연결.
5. **활동 피드 고도화(안티그래비티 단계 카드)**: 현재는 최종 응답 + 파일 카드만 표시.
   `features/task-execution`(taskEventReplica/useTaskExecutionEvents)의 이벤트 스트림을 피드에
   연결해 "파일 수정함 / 명령을 실행함 / 읽음" 접기 행을 채우면 첨부 ①번 스크린샷 중앙부와 동일해짐.
6. **큐 카드 UX 소폭 보완**: 드래그 재정렬(코덱스는 지원), 다건 전송 시 순차 실행 중단 버튼.
7. **다크 모드**: 신규 `.agk-*`/`.env-*` 섹션은 라이트 톤 고정. `themeStore` 다크 테마 대응 시
   색만 변수화하면 됨(현재 hex 하드코딩 — #ffffff/#e5e7eb/#111827 계열).
8. **모바일 <720px**: 환경 레일은 1100px 이하에서 오버레이 전환됨. 히어로/칩 줄바꿈은 확인 완료.

## 7. 주의사항

- `ChatMessage.tsx`의 DOM 구조(`.message/.avatar/.bubble`)와 memo 비교자는 변경 금지 (E2E+유닛 의존).
- `chatStore` 세션 저장 키(`antigravity_chat_{workspace}`)와 localStorage 키 변경 금지.
- CSS는 기존 섹션을 건드리지 말고 파일 말미 신규 섹션에만 추가할 것(13k→14k 줄, 충돌 최소화).
- `dashboard/src/components/Chat/{ChatInput,ModelSelector,PlanToggleBar}.tsx`는 구형 컴포넌트로
  현재 ChatPage에서 미사용. 삭제 전 다른 참조 확인 후 정리 가능.
