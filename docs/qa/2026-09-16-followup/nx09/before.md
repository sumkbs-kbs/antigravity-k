# NX-09 before — 인증 후 실제 사용자 동선 (2026-09-16)

카드: `docs/18` §NX-09 / `docs/19` §NX-09. 선행: NX-01~06·NX-08(REVIEW).
기준: 작업 트리 소스 + **커밋된 `src/antigravity_k/dashboard_dist/`**(제품이 `/` 로 서빙하는 SPA).

## 0. 측정 도구와 그 전제(먼저 고정한 것)

| 도구 | 무엇을 재는가 | 어디 |
|---|---|---|
| `dashboard/e2e/tests/nx09-user-journey.spec.ts` | 실 브라우저 + 실 hermetic 서버 + **가짜 provider**(제품 서버가 실제 HTTP 를 친다) | T1~T7 |
| `dashboard/e2e/helpers/fakeProvider.ts` | provider 구간을 남긴다(브라우저 `page.route` 가로채기 금지 — 그러면 서버→provider 가 사라진다) | 신규 |
| `nx09/repro_nx09_ws_revocation.py` | 실 `uvicorn.Server` + 실 ticket WS + **프로세스 안 레지스트리** 관측 | 신규 |
| `nx09-probe.spec.ts` | 배관 탐침(일회용, 측정 후 삭제) | 삭제됨 |

품질 분리: 모든 결과는 **fake provider** 기준이다. cloud/live provider 지원 증거가 아니다.

### 도구 자체의 결함 3건(제품 결함이 아니다 — 자를 고친 뒤 측정했다)
1. provider 본문 비교가 원문 `includes` 라 **JSON 유니코드 이스케이프**(`\uXXXX`)를 놓쳤다 → 이스케이프를 푼 뒤 비교.
2. 대화 상태 키를 경로(`antigravity_chat_<path>`)로 가정했지만 실제 키는 **`activeProjectId`** 다.
3. PIN 모달이 앱을 대체하므로 가려진 요소에 `toBeVisible` 을 걸어 거짓 실패했다 → 존재/`textContent` 로 잰다.

### 하네스 결함 1건(측정을 막고 있었다 — 함께 고쳤다)
`hermeticBackend.ts` 가 대화 저장소를 격리하지 않아 채팅이 **개발 기계의 홈**(`~/.antigravity/conversations`)을
읽었고 CR-01 migration gate 로 503 을 받았다. 실측 응답:

```
503 {"ok":false,"error":"conversation_storage_migration_required",
     "storage_dir":"/Users/mr.k/.antigravity/conversations","legacy_record_count":3}
```

→ `AGK_CONVERSATION_STORE_DIR` 를 상태 디렉터리 아래로 고정(그 전에는 대화 E2E 가 환경 의존이었다).

## 1. before 관측(수정 전)

### F01 — 첫 대화의 정체성이 서버 폴백으로 무너진다 (P1)
- 화면이 보낸 첫 턴 본문에 `conversation_id` 가 **없다**(세션이 만들어지지 않았다).
- 서버는 폴백 `conv_unspecified` 로 저장하고, 화면은 그 값을 **자기 대화 id 로 채택**했다.
- 실측(`t2-observation.json` before): `activeSessionId == conv_unspecified`, 스냅샷 `conversation_id == conv_unspecified`,
  `sessions` 목록에 그 대화가 없음.
- 결과: 이력 목록에 첫 대화가 없고, 서로 다른 창/사용자의 첫 대화가 **한 레코드로 섞이며**, 한쪽이 지우면 함께 사라진다.

### F02 — 재시작 뒤 서버 이력 동기화가 **한 번도** 실행되지 않는다 (P1)
- 마운트 시 `syncConversation()` 이 `activeProjectId` 를 `getState()` 로 읽는데, 그 값은 하이드레이션(비동기)으로
  나중에 채워진다. init effect 의 의존성 배열에 프로젝트 정체성이 없어 **다시 실행되지 않는다**.
- 실측(`t2-observation.json` before): 빈 localStorage 로 새로 연 창(대화 id 만 심음)이 `/v1/conversations` 요청을
  **0건** 보냈고 빈 화면이었다. 같은 시각 서버는 r2·메시지 2건을 갖고 있었다.
- 결과: 로컬 캐시가 없으면(다른 기기·프로필 초기화) 서버에 이력이 있어도 빈 대화로 보인다. 재현은 레이스에 걸린다.

### F03 — 첨부는 텍스트 주석으로만 나간다 (P2)
- 입력창에 `[첨부 파일: nx09-attach.png]` 텍스트가 붙고, provider 요청에는 `image_url`/`data:image/` 가 **없다**(실측).
- 결과: 화면은 사진 첨부를 안내하지만 모델은 이미지를 보지 못한다(Vision 주장과 동작 불일치).

### F04 — 서빙되는 SPA 가 소스보다 낡았다 (P2)
- 커밋된 번들에 HEAD 소스의 표식이 없다(표식 3종 대조, dist 커밋 `0cdcd60c` vs 소스 커밋 `52a02ef0`):

| 표식(HEAD 소스) | 번들 |
|---|---|
| `settings-current-pin` | 없음 |
| `settings-pin-status` | 없음 |
| `changeAccessPin` | 없음 |

→ UI 관측은 **빌드 후**에만 현재 소스를 잰다(`pnpm build`). 이번 증거의 after 는 빌드 후 측정이다.

### F05 — 폐기 카운터·응답 지연이 실제 폐기와 어긋난다 (P2)
`repro_nx09_ws_revocation.py` (실 uvicorn, 실 ticket WS):
- 브라우저/클라이언트 관점: **4401, 3ms** — 닫혔다.
- 서버 보고: `sessions_revoked: 0`, 경고 `Authorized WS close did not complete within 5s`, 그리고 상태는
  `application_state=DISCONNECTED`(프레임은 나갔다) / `client_state=CONNECTED`(그대로).
- 즉 **폐기는 되는데 완료를 기다리다 5초 상한을 소진**하고, 그 실패를 폐기 실패로 세어 0 으로 보고했다.

### F03 — 첨부 이미지가 모델에 도달하지 않는다 (P2, 기능)
화면은 파일명 텍스트 표식(`[첨부 파일: …]`)만 입력창에 넣고 **바이트는 어디에도 보내지 않았다** —
사용자는 붙였다고 믿지만 모델은 파일명만 본다. 손실 지점은 다섯 곳(요청 스키마 부재 · 관리자
납작화 · 에이전트 프롬프트 문자열 경로 · 어댑터 4종 개별 재구성 · 문자열 가정 코드)이었고,
그래서 이 카드에서는 `test.fail` 로 고정만 하고 **결정(ADR)** 을 다음 소유자에게 넘겼다.
→ 같은 날 후속 작업에서 해결: 전용 패키지 [f03/before.md](f03/before.md)·[f03/after.md](f03/after.md)·
[ADR-0005](../../../adr/0005-multimodal-attachments.md).

### F06 — UI 경로(설정 화면)에서의 폐기 관측 (미해결, 조건 미확정)
T5(설정 화면에서 PIN 변경)에서 열린 브라우저 이벤트 WS 가 남았고 `sessions_revoked: 0` 이었다.
같은 서버·같은 계약을 API 경로로 잰 T7 은 닫혔다(`sessions_revoked: 1`). 화면 이동 뒤 폐기라는 조건 차이가
원인 후보지만 **확정하지 않았다** — 소유자에게 그대로 넘긴다.

**재측정(같은 작업 안, after):** 이 관측은 **한 창 안에서** 잰 것이었고, `page.goto('/settings')` 가 문서를
통째로 교체하는 순간 채팅 화면(=WS 소유자)이 사라져 **요청 시점에 폐기할 연결이 없다.** 살아 있는 창을 둔
두 창 시험(T8)에서는 `sessions_revoked: 1`·close **571ms** 였다 → **NOT_REPRODUCED**(계기 오독).
상세·계기 교정은 `after.md` §3.

### 부수 관측(결함 아님)
- PIN 변경 뒤 재로그인 모달이 뜨는데, 모달이 앱을 대체하므로 설정 화면의 안내 문구는 사라진다 → 사용자는
  "왜 잠겼는지"를 알 수 없다(UX). 이번에 모달이 이유를 들고 가도록 고쳤다.
- `components/Chat/ChatInput.tsx` 는 **어디에서도 렌더되지 않는다**(죽은 컴포넌트). 이번 범위에서 고치지 않았다.
