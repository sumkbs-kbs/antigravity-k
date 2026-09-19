# NX-09 after — 인증 후 실제 사용자 동선 (2026-09-16)

측정 조건: 작업 트리 소스 + `pnpm build` 로 **현재 소스를 서빙**하게 만든 `dashboard_dist`.
hermetic 서버(`startAuthServer`) + **가짜 provider**(`startFakeProvider`) + 실 브라우저(chromium headless).
실행: `npx playwright test e2e/tests/nx09-user-journey.spec.ts --workers=1` (8 tests: 7 passed + 1 expected-fail).

## 1. 수정(제품 코드)

| ID | 수정 | 파일 |
|---|---|---|
| F01 | 세션이 없으면 **클라이언트가** 대화 id 를 만든다(`addMessage`) · 서버 폴백 id(`conv_unspecified`)는 **정체성으로 채택하지 않는다**(`applyServerSnapshot`) | `dashboard/src/stores/chatStore.ts` |
| F02 | 프로젝트 정체성이 도착하면 서버 이력 동기화를 다시 실행한다(`syncConversationRef` + `activeProjectId` effect) | `dashboard/src/components/Chat/ChatPage.tsx` |
| F05 | 인증 WS 폐기 판정을 "close 호출이 **디스패치**됐는가"로 바꾸고(`application_state`), 완료 대기를 5s→0.25s 유예로 줄였다. 프레임 이후의 예외는 실패로 세지 않는다 | `src/antigravity_k/api/routes/session_state.py` |
| UX | PIN 모달이 **왜** 떴는지 스스로 설명한다(`pinModalNotice`) — 모달이 앱을 대체해 다른 안내가 사라지던 문제 | `stores/uiStore.ts`, `components/UI/PinModal.tsx`, `pages/SettingsPage.tsx`, `App.tsx` |
| 하네스 | hermetic 서버가 대화 저장소를 격리한다(`AGK_CONVERSATION_STORE_DIR`) · 서버 로그 열람(`output()`) | `e2e/helpers/hermeticBackend.ts` |

수정하지 않은 것(이 카드 시점): **F03**(첨부 이미지 미전달 — 메시지 스키마/ADR 결정 필요), **F04**(서빙 SPA 낡음 — 패키징 절차).
(F06 은 재측정에서 **결함이 아님**으로 판정됐다 — 아래 §3.)
**둘 다 같은 날 후속 작업에서 진전됐다:** F03 은 [f03/after.md](f03/after.md)·[ADR-0005](../../../adr/0005-multimodal-attachments.md)
(첨부가 실제 바이트로 모델에 도달 — 증인 T4 가 계약으로 승격, 8 passed), F04 는 여전히 열려 있다.

## 2. after 관측 (증인별 원문은 같은 디렉터리의 `t*-observation.json`)

| 증인 | 재는 것 | 결과 |
|---|---|---|
| T1 | PIN UI 로그인 → 모델 선택(UI) → 대화 → 응답 | **PASS** — 화면에 가짜 provider 표식, provider 가 받은 본문에 사용자 요청이 있음(`reachedProvider: true`, 경로 `/chat/completions`·`/api/chat`) |
| T2 | 저장 → 재시작 → 이어가기 | **PASS** — 대화 id `mu3mi8w0hrt2afks`, 서버 `revision 2`·`message_count 2`; **빈 localStorage** 로 새로 연 창이 `/v1/conversations/<id>` 를 호출해(r200) 그 턴을 복원 |
| T3 | 삭제 → 미노출 | **PASS** — delete 200, 이후 스냅샷/export/history **404 · 404 · 404**, 새 창에도 원문 없음. (1회차에 `ECONNRESET` 전송 플레이크 1건 — 재실행 green) |
| T4 | 첨부가 모델에 도달 | **(이 카드 시점) expected-fail** — 입력창 주석만, provider 본문에 이미지 없음 → **후속 작업에서 수정**: [f03/after.md](f03/after.md) 의 T4 는 `imageReachedProvider: true` |
| T5 | PIN 변경 → 재로그인 모달(UI) | **PASS** — `change-pin 200`, 저장 토큰 제거, 모달 표시, 모달 안내문 `보안을 위해 모든 세션이 종료되었습니다…`, 새 PIN 으로 재로그인 성공 |
| T6 | 새 대화는 별개 레코드 | **PASS** — `mu3mjqp8oledt9x2` ≠ `mu3mjr4qbjd5bmuy`, 각 스냅샷에 자기 턴만, 저장소 파일에 **폴백 id 레코드 0** |
| T7 | PIN 변경이 열린 WS 를 닫는다(같은 창, HTTP API 경로) | **PASS** — `sessions_revoked: 1`, 브라우저 소켓 1/1 closed |
| T8 | PIN 변경이 **다른 창**의 살아 있는 WS 를 닫는다(실 UI 설정 화면 경로) | **PASS** — `sessions_revoked: 1`, 창 A 소켓 1/1 closed, **close 이벤트 571ms**(카드 계약 ≤5초) |

드라이버(`repro_nx09_ws_revocation.py`, 실 `uvicorn.Server` + 실 ticket WS):

```
before                                      after
registry_after_connect : 1                  registry_after_connect : 1
sessions_revoked       : 0                  sessions_revoked       : 1
ws_close_code          : 4401 (3ms)         ws_close_code          : 4401 (3ms)
warning                : close did not      change_pin_seconds     : 0.353
                         complete within 5s  close_warnings         : []
```

즉 폐기 자체는 before 부터 동작했고(4401·3ms), **보고·대기**가 틀렸다 → 수정 후 보고가 실제와 일치하고
응답이 5초 상한을 기다리지 않는다.

## 3. 남긴 것 (DONE 아님)

- ~~**F03 첨부 이미지 미전달(P2, 기능)**~~ → **후속 작업에서 해결**: [f03/](f03/) 패키지 · [ADR-0005](../../../adr/0005-multimodal-attachments.md).
  손실 지점은 다섯 곳이었고(요청 스키마·관리자 납작화·에이전트 프롬프트 경로·어댑터 4종·문자열 가정 코드),
  내부 정규형을 `content`(문자열) + `images` 로 정해 해결했다. T4 의 `test.fail` 은 **계약으로 승격**됐다.
- **F06 UI 경로 폐기 — NOT_REPRODUCED(계기 오독).** 원래 관측은 **한 창**에서 `page.goto('/settings')` 뒤
  PIN 을 바꾸고 그 **같은 창**의 소켓 객체를 봤다. 두 가지가 겹쳤다:
  1. 그 창은 이동 순간 문서가 통째로 교체되어 **채팅 화면(=이벤트 WS 를 여는 유일한 화면, ChatPage/AgentPage)**
     이 unmount 되고 `useEventWebSocket` 의 cleanup 이 소켓을 닫는다 → 요청 시점의 레지스트리가 **비어 있다**.
     그래서 `sessions_revoked: 0` 은 **정상**이다(폐기할 연결이 없다).
  2. Playwright 의 소켓 객체는 **파괴된 창**의 close 를 보고하지 않는다 — `isClosed()` 가 `false` 로 남아
     "소켓이 살아 있다"로 오독된다.
  자를 바꾼 재측정(T8): 창 A 를 채팅 화면에 그대로 두고(이동 없음) **창 B** 의 설정 화면에서 PIN 을 바꿨다 →
  `t8-observation.json`: `sessionsRevoked: 1`, 창 A 소켓 `isClosed: true`+close 이벤트, `closeLatencyMs: [571]`.
  즉 폐기 계약은 실 UI 경로에서도 지켜지고, 원래 0 은 **살아 있는 연결이 없어서** 나온 값이다. 같은 계약을
  한 창·API 경로로 잰 T7 도 `1` 이다 — 두 증인이 같은 레지스트리를 다른 방향에서 확인한다.
  (기록만 남긴 것: PIN 변경 시각에 창 A 의 재로그인 모달은 아직 `false` 였다 — 재연결 시도 뒤에 뜨는 경로이며
  이번에 단정하지 않았다.)
- **F04 서빙 SPA 낡음(P2, 패키징)**: 커밋된 `dashboard_dist` 가 소스보다 뒤처져 있다. 이번 작업 트리는 빌드본을
  포함한다(미커밋) — 후보 고정(NX-10) 시 번들 신선도를 절차로 확인해야 한다.
- NX-01 이 NX-09 로 넘긴 **cue lexicon 회수율 실측(기억 시나리오)** 은 이번에 하지 않았다: 그 시나리오는
  "첫 메시지 정책 → 반복 요약 → 도구 실행 뒤 정책 유지"를 실제 agent 경로에서 재야 하는데, 이 증인의
  agent 실행은 가짜 provider 로 라우팅 단계만 지난다. 소유자 재지정 필요(별도 카드 권장).
- 긴 tool 출력·disk-full·취소·연타·keyboard-only·작은 화면은 이번 witnessed 범위 밖이다(핵심 동선 우선).

## 4. 한계

- 모든 결과는 fake provider 기준이다. cloud/live provider 지원 증거가 아니며 EX-01 을 대체하지 않는다.
- 멀티 프로세스 폐기(원격 다중 기기), rollback 리허설, 실 기기 데스크톱은 여전히 미실시다.
