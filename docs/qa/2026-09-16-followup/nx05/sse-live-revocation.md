# NX-05 잔여 — 이미 열려 있는 SSE 스트림의 폐기 (2026-09-16, NX-10 동결 배치)

NX-05 는 PIN 변경이 (a) 새 요청을 401 로 막고 (b) 열려 있는 **WS** 를 4401 로 닫는다는 것까지
고정했지만, (c) **이미 열려 있는 SSE 응답을 닫는 경로는 없었다** — 그때 이 범위를 DONE 으로
주장하지 않았다([handoff §5](handoff.md)). 이 문서가 그 항목을 닫는다.

## 결함의 정체

SSE 는 인증을 **요청 시점에 한 번**만 받는다(미들웨어 `verify_access_token`). 스트림 본문을
만드는 루프는 `request.is_disconnected()` 만 보므로, 세대가 바뀌어도 서버는 계속 이벤트를
보낸다. 즉 폐기 수단(세대·WS 레지스트리)이 SSE 에는 적용되지 않았다.

## before / after (실서버 관측 — `TestClient` 로는 관측할 수 없다)

`TestClient` 는 응답을 전부 버퍼링하므로 "읽는 중에 끊긴다"를 볼 수 없다(개발 중 실제로 이
함정에 걸렸다 — 그래서 실서버 드라이버를 만들었다). 드라이버는 uvicorn 을 띄우고 httpx 로
**점진적으로** 읽는다.

```bash
# before: 같은 트리에서 가드 미들웨어 배선만 드라이버가 벗긴다(제품 파일은 그대로)
NX05_TREE=before NX05_SSE_DISABLE_GUARD=1 AGK_SSE_REVOCATION_CHECK_SECONDS=0.5 PYTHONPATH=src \
    .venv/bin/python docs/qa/2026-09-16-followup/nx05/repro_sse_live_revocation.py > before-sse.json
# after: 기본값(가드 배선됨)
NX05_TREE=after AGK_SSE_REVOCATION_CHECK_SECONDS=0.5 PYTHONPATH=src \
    .venv/bin/python docs/qa/2026-09-16-followup/nx05/repro_sse_live_revocation.py > after-sse.json
```

| 관측 | before (`before-sse.json`) | after (`after-sse.json`) |
|---|---|---|
| 세대 변경 **뒤** 도착한 데이터 프레임 | **9** | **1** (검사 주기 0.5s 안쪽에 한 번) |
| `session.revoked` 프레임 | 없음 | **1.112초**에 도착 |
| 폐기 뒤 스트림 종료(EOF) | 아니오 | **예** (`stream_ended_after_revocation: true`) |
| 폐기된 bearer 의 새 요청 | 401 | 401 (이미 정상이었다 — 갭은 열린 스트림뿐) |

기준선을 HEAD 추출본으로 두지 않은 이유: epoch 폐기 자체가 미커밋이라 HEAD 에는
`security/auth_state.py` 가 없다. 그래서 **같은 트리에서 가드 배선 한 줄만** 달리해 대조군을
만들었고, 드라이버가 그 사실을 리포트에 `guard_disabled_by_driver` 로 남긴다.

## 구현

* `src/antigravity_k/api/sse_revocation.py` — `SSERevocationMiddleware`(BaseHTTPMiddleware).
  `content-type: text/event-stream` 응답의 `body_iterator` 만 감싼다. 검사 주기는
  `AGK_SSE_REVOCATION_CHECK_SECONDS`(기본 1초, 잘못된 값은 기본값 + 경고).
* 감싼 스트림은 **청크 도착에 묶이지 않는다**: 청크를 주기만큼만 기다리고 기다리는 동안에도
  폐기를 확인한다(유휴 스트림이 폐기를 피하지 못한다).
* 폐기 시 마지막 프레임은 `event: session.revoked` + `{"type":"session.revoked","reason":"auth_epoch_changed"}`
  이고 그 뒤 스트림이 끝난다. 집계는 `ssak_auth_events_total{outcome="stream_revoked"}`.
* bearer 가 없는 연결(익명 `open_loopback`)은 폐기하지 않는다 — 무효화할 세대가 없다(NX-05 정책).
* `server.py` 에서 **가장 먼저 등록**해 미들웨어 스택의 안쪽에 둔다(라우트의 `StreamingResponse` 를
  직접 감싼다). SSE 를 여는 지점이 16곳이라 미들웨어 한 곳에서 처리한다 — 라우트별로 손대면
  다음에 추가되는 스트림이 다시 빠진다.

## 시험

`tests/test_nx05_sse_live_revocation.py` — **10 passed**.

* 열린 스트림이 폐기 프레임을 받고 **끝난다**(첫 프레임은 받고, 전체 프레임은 받지 못한다),
* 유휴 스트림(30초 대기 중)도 폐기된다 — 본문이 폐기 프레임 하나뿐이고 5초 안에 끝난다,
* 유효한 자격 증명으로 열린 스트림은 닫히지 않는다(오탐 0),
* 익명 연결은 폐기되지 않는다,
* 이미 폐기된 자격 증명으로 열린 스트림은 **첫 청크도 내보내지 않는다**,
* SSE 가 아닌 응답은 건드리지 않는다,
* 실제 `app` 에 배선돼 있고 인증 미들웨어보다 **안쪽**이다,
* 실제 app + 실제 인증 미들웨어에서 task 이벤트 SSE 가 닫히고, 같은 bearer 의 새 요청이 401,
* 폐기가 운영 metric 을 1 증가시킨다.

## 남은 것

* 실 브라우저에서 `session.revoked` 를 받은 UI 가 로그인 화면으로 전환하는 동선은 이 카드에서
  만들지 않았다(서버가 스트림을 닫고 이유를 보내는 것까지가 이 카드의 계약). UI 동선은 NX-09 후속.
* 워커·클라우드 provider 의 장시간 스트림에서 같은 폐기가 관측되는지(provider 별 버퍼링)는 미관측.
