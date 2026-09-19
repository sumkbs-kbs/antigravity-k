# NX-09-F03 before — 첨부 이미지가 모델에 도달하지 않는다

측정 조건: 작업 트리(수정 전) + 실 브라우저 + 실 hermetic 서버 + **가짜 provider**(제품 서버가 실제 HTTP 를 친다).
증인: `dashboard/e2e/tests/nx09-user-journey.spec.ts` T4(당시 `test.fail(true, ...)` 로 고정).
탐침: `docs/qa/2026-09-16-followup/nx09/f03_probe_trace.py`(수정 후 추가 — 손실 지점 추적용).

## 1. 관측

- 화면: 파일을 고르면 입력창에 `[첨부 파일: nx09-attach.png]` 만 들어간다.
- provider 본문: **이미지 없음**. T4 는 `test.fail` 로 "미해결 결함"을 고정하고 있었다
  (수정되면 오히려 실패하게 만들어, 조용한 통과를 막는 장치).
- 즉 사용자에게는 "붙였다"고 보이지만 모델은 파일명만 본다 — **화면이 거짓말한다**.

## 2. 손실 지점 (수정 중 탐침으로 확정)

첨부 채널은 하나가 아니라 **다섯 곳**에서 끊겨 있었다. 이것이 \"스키마 한 줄 추가\"로 끝나지
않은 이유다.

| # | 지점 | 실측 증상 |
|---|---|---|
| ① | 요청 스키마 | `attachments` 필드 자체가 없어 화면이 보낼 곳이 없다 |
| ② | `model_manager._prepare_stream_messages` | 파트 배열을 텍스트로 납작하게 만든다 → 이미지 소실 |
| ③ | 에이전트 파이프라인 | 모델 입력이 프롬프트 **문자열**(압축·예산 게이트) — 이미지가 지나갈 자리가 없다 |
| ④ | provider 어댑터 4종 | 각자 `api_msgs` 를 다시 만들며 같은 방식으로 버린다 |
| ⑤ | 문자열 가정 코드 | 첨부를 파트 배열로 실으면 `'list' object has no attribute 'strip'` / `expected string or bytes-like object, got 'list'` / 스냅샷 `ValidationError` / SQLite 바인딩 오류로 **500** |

⑤ 는 ③ 을 우회해 파트 배열을 그대로 흘려보냈을 때의 결과다(실측: `orchestrator_context_handlers`
init, `direct_task_execution._latest_user_text`, 태스크 스냅샷). 즉 "그냥 파트로 바꾸면 된다"는
선택지는 이 코드베이스에서 성립하지 않는다 — 내부 정규형을 `content`(문자열) + `images` 로
정한 이유다(ADR-0005 §2-3).

## 3. 탐침이 없었으면 못 찾았을 것

브라우저 E2E 는 "결국 provider 본문에 이미지가 없다"까지만 말한다. 추적 탐침은 다중모달 seam 을
감싸 호출·이미지 개수를 기록해 **실패 지점을 함수 이름으로** 보여 준다(수정 후 artifact:
`probe-trace.json`). 어댑터가 별도 경로라는 사실(관리자 메서드가 아예 호출되지 않음)도 여기서
드러났다 — 그 전까지는 관리자 경로만 고치고 "왜 아직 안 되지"를 반복하고 있었다.
