# NX-09 handoff — 인증 후 실제 사용자 동선 (2026-09-16)

카드: `docs/18` §NX-09 / `docs/19` §NX-09. 선행: NX-01~06·NX-08(REVIEW).
State: **REVIEW** — 실 UI 동선 재현·수정·회귀 green. 독립 검토자·출시 판단은 미실시(소유자 미배정).
소유(작업): Buffy. 검토자: 미지정.

## 1. 무엇을 실측했는가

**이 카드의 핵심은 "인증 후 실제 사용자 동선"을 실 UI 에서 재는 것**이고, 그래서 자를 새로 만들었다:

- `dashboard/e2e/tests/nx09-user-journey.spec.ts` — 실 브라우저 + **실 hermetic 서버**(실 PIN/실 JWT/실 대화 저장소)
  + **가짜 provider**. 브라우저 `page.route` 로 채팅을 가로채면 `서버→provider` 구간이 사라지므로 쓰지 않았다.
  증인 8개: T1 핵심 동선 · T2 저장→재시작→이어가기 · T3 삭제 미노출 · T4 첨부(미해결 고정) · T5 PIN 변경 UI ·
  T6 새 대화 정체성 · T7 PIN 변경 → 열린 WS 폐기(같은 창, HTTP API 경로) ·
  T8 PIN 변경 → **다른 창**의 살아 있는 WS 폐기(실 UI 설정 화면 경로, F06 재검증).
- `dashboard/e2e/helpers/fakeProvider.ts` — OpenAI/Ollama 두 표면 + `status`/`abort`/`tool_call` 스크립트.
- `nx09/repro_nx09_ws_revocation.py` — 실 `uvicorn.Server` + 실 ticket WS + **프로세스 안 레지스트리**.
  브라우저 관측만으로는 "등록 실패 / 닫기 실패 / 재연결"을 구분할 수 없어서 만들었다.

산출물: `t1..t8-observation.json`, `t1-storage.json`, `probe.json`, `before.md`, `after.md`, `commands.txt`, `regression.txt`.

## 2. 확인된 결함과 조치

| ID | 결함 | 심각도 | 상태 |
|---|---|---|---|
| NX-09-F01 | 첫 대화의 정체성이 서버 폴백(`conv_unspecified`)으로 무너진다 — 이력 목록에 없고, 서로 다른 창/사용자의 첫 대화가 한 레코드로 섞이며, 삭제가 남의 이력까지 지운다 | P1(데이터) | **수정**(store) |
| NX-09-F02 | 재시작 뒤 서버 이력 동기화가 프로젝트 하이드레이션 레이스에 걸려 **한 번도 실행되지 않는다** | P1(데이터) | **수정**(ChatPage) |
| NX-09-F05 | PIN 변경 폐기: 소켓은 4401 로 닫히는데(3ms) 보고는 `sessions_revoked: 0`, 응답은 5초 상한을 기다린다 | P2(관측/지연) | **수정**(session_state) |
| UX | 재로그인 모달이 앱을 대체해 "왜 잠겼는지"가 사라진다 | P3 | **수정**(uiStore/PinModal/SettingsPage/App) |
| 하네스 | hermetic 서버가 대화 저장소를 격리하지 않아 채팅 E2E 가 개발 기계 홈을 읽고 503 을 받았다 | P2(하네스) | **수정**(hermeticBackend) |
| NX-09-F03 | 첨부가 `[첨부 파일: …]` 텍스트로만 나가 이미지가 모델에 도달하지 않는다(Vision 미동작) | P2(기능) | **후속 작업에서 수정**([f03/handoff.md](f03/handoff.md) · [ADR-0005](../../../adr/0005-multimodal-attachments.md)) — 증인 T4 로 계약 고정, 잔여는 이전 턴 이미지 재전송·압축 상호작용 |
| NX-09-F04 | 커밋된 `dashboard_dist` 가 소스보다 낡아 **서빙되는 SPA ≠ 소스** | P2(패키징) | **미해결** — 후보 고정(NX-10) 전 빌드 절차 필요 |
| NX-09-F06 | (원래 관측) UI 경로(설정 화면)에서 PIN 변경 시 열린 브라우저 WS 가 남고 `sessions_revoked: 0` | —(결함 아님) | **NOT_REPRODUCED** — 한 창 측정 아티팩트. 두 창 시험 T8: `sessions_revoked: 1`·close 571ms |

## 3. 수정한 파일(제품)

```
dashboard/src/stores/chatStore.ts          F01: 세션 자동 생성 + 폴백 id 미채택(SERVER_FALLBACK_CONVERSATION_ID)
dashboard/src/components/Chat/ChatPage.tsx F02: 정체성 도착 시 서버 이력 재동기화(syncConversationRef)
src/antigravity_k/api/routes/session_state.py F05: 폐기 판정=디스패치(application_state), 대기 5s→0.25s
dashboard/src/stores/uiStore.ts            pinModalNotice
dashboard/src/components/UI/PinModal.tsx   모달이 이유를 표시(+성공 시 초기화)
dashboard/src/pages/SettingsPage.tsx       PIN 변경 시 이유 전달
dashboard/src/App.tsx                      401 경로도 이유 전달
dashboard/e2e/helpers/hermeticBackend.ts   대화 저장소 격리 + output() 로그 열람
+ 신규: e2e/helpers/fakeProvider.ts, e2e/tests/nx09-user-journey.spec.ts,
        src/stores/__tests__/chatStore.nx09.test.ts
삭제: e2e/tests/nx09-probe.spec.ts(일회용 탐침)
```

## 4. 검증

- `nx09-user-journey.spec.ts` 8건: 이 카드 시점 **7 passed + 1 expected-fail(F03)** → F03 수정 뒤 **8 passed**. `--workers=1` 로 실행(T3 는 1회차
  `ECONNRESET` 전송 플레이크 후 재실행 green).
- 대시보드 vitest **89 files/888 tests passed**, 관련 pytest **44 + 297 + 327 passed**, ruff·mypy·tsc clean.
- 전량 E2E **191 passed/10 failed** — 실패 9건은 이 환경의 ambient 8012 인스턴스 때문이며 **커밋된 dist 로
  되돌린 상태에서도 동일**했다(재측정 3 passed/8 failed). 이 카드가 만든 실패는 T4 하나뿐이다.
- 드라이버: `sessions_revoked 0 → 1`, `change_pin_seconds 0.353`, close 4401 3ms.

## 5. 운영 주의(반드시 읽을 것)

1. **UI 증인은 `pnpm build` 가 전제다.** 커밋본 번들이 소스보다 낡아서(F04) 빌드 없이 돌리면 증인이 **다른 제품**을
   재게 된다. 그래서 증인이 시작할 때 번들 표식(`pin-modal-notice`·`conv_unspecified`)을 확인하고, 낡았으면
   "`cd dashboard && pnpm build` 후 다시 실행하라" 로 **명시적으로 실패**한다(원인 불명의 실패로 보이지 않게).
   이번 최종 상태는 번들을 커밋본으로 되돌렸다(파생 산출물 — 후보 고정 시 다시 빌드한다).
   최종 확인: 빌드 후 `--workers=1` 로 **7 passed**(6 + 의도된 T4 expected-fail).
2. 증인을 병렬(`--workers=3` 이상)로 돌리면 각 시험이 실 서버를 띄우므로 느려진다 — `--workers=1` 권장.
3. `nx09/repro_nx09_ws_revocation.py` 는 **임시 디렉터리**만 쓴다(사용자 홈·실 프로젝트 무변경).
4. **계기 주의(계속 유효):** Playwright 의 소켓 객체는 **파괴된 창**의 close 를 보고하지 않는다 — `page.goto` 로
   문서를 바꾼 뒤 그때까지 관측한 소켓의 `isClosed()` 가 `false` 로 남는다. 이 값을 "소켓이 살아 있다"로 읽으면
   없는 결함을 만든다(F06 이 정확히 그렇게 태어났다). 소켓 수명을 주장할 때는 **그 창을 이동시키지 말고**
   다른 창에서 자극해 관측하라(T8 패턴).

## 6. 다음 소유자에게(정확한 다음 행동)

1. **F03 잔여**(결정은 [ADR-0005](../../../adr/0005-multimodal-attachments.md) 로 완료): ① **이전 턴 이미지 재전송**은
   저장소에 base64 를 넣지 않기로 해서 하지 않는다 — 재전송이 필요하면 저장 크기·압축과 함께 결정해야 한다.
   ② **압축 뒤 첨부 의미 보존**은 미정. ③ live/cloud provider 의 실제 Vision 품질은 EX-01 축이다.
2. **F04 절차화**: 후보 고정 단계에 "소스↔빌드 번들 신선도 확인"을 넣는다(NX-10). 실 UI 증인은 그 전까지
   `cd dashboard && pnpm build` 를 전제한다(안 하면 증인이 표식 검사로 **명시적으로** 실패한다).
   참고: F06 은 계약으로 닫혔다(T8) — 설정 화면 **자체에는 이벤트 WS 가 없다**(연결은 ChatPage/AgentPage 가 연다).
   그러므로 설정 화면 경로의 `sessions_revoked: 0` 은 정상값이고, 그 값만 보고 결함으로 읽으면 안 된다.
4. **NX-01 이 넘긴 항목**: cue lexicon 회수율(기억 시나리오 — 첫 메시지 정책 → 반복 요약 → 도구 실행 뒤 정책 유지)은
   이 카드에서 **하지 않았다**(가짜 provider 경로로는 요약·도구 실행의 의미를 재현할 수 없다). 별도 카드로 재지정 필요.
5. 이 카드 범위 밖으로 남긴 시나리오: 긴 tool 출력·disk-full·취소·연타·keyboard-only·작은 화면.
   (NX-08 이 넘긴 "손상된 대화 격리·폐기 운영 절차"도 여전히 소유자 미지정이다.)
5. NX-10 은 `dashboard/src/stores/chatStore.ts`·`ChatPage.tsx`·`session_state.py`·`uiStore.ts`·`PinModal.tsx`·
   `SettingsPage.tsx`·`App.tsx` 가 바뀐 뒤이므로 **후보 지문을 새로 고정**해야 한다.
