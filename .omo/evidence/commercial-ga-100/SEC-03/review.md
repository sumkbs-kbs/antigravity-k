# SEC-03 독립 리뷰 — r1 APPROVE

- **Reviewer:** sec_03_verify (구현자 sec_03_impl과 상이한 세션 — Freebuff/Claude 세션, 2026-09-07)
- **검증 대상:** baseline에 병합된 `codex/sec-03-ws-origin-ticket` @ `71b48a7` (merge `3be742d`)
- **Verdict:** **APPROVE** — 발견 결함 0건. 수용기준 4건 전부 독립 재현으로 확인.

## 검증 방법

1. **구현자 테스트 재실행**: `test_sec03_ws_origin_ticket.py`(18) + `test_workspace_websocket.py` + `test_workspace_websocket_live.py` = **44 passed** (병합 후 baseline에서)
2. **독립 시나리오 재현** (구현자 테스트와 별개 스크립트):
   - **AC-1 Origin allowlist**: missing origin(None/"") = non-browser 허용 · `evil.example`/미등록 포트/scheme 교체(`https://localhost:8000`)/suffix 우회(`localhost:5173.evil.com`) 전부 거절 · allowlist 정확 일치만 수용 — **PASS**
   - **AC-2 Ticket 1회성**: 첫 consume 성공(subject 반환) → 동일 ticket 재소비 거절(replay) · 변조(`+x`)/garbage 거절 · `ttl_sec=1` 서비스로 만료 후 거절 재현 · **bearer 토큰을 ticket 자리에 사용 시 typ 검증으로 거절** — **PASS**
   - **AC-3 credential 비노출**: WS 게이트 소스 정적 재현 — `?token=`/subprotocol 채널 부재, ticket-only 게이트 · 발급 route(`POST /v1/auth/ws-ticket`)는 Bearer 인증 필요, 응답은 단기 ticket뿐 — **PASS**
   - **AC-4 cross-site 차단**: 악의 Origin + 유효 ticket 조합에서 Origin 게이트가 ticket 소비 전에 거절 — **PASS**
3. **회귀 대조**: 병합 전 baseline `ec144cd` vs 병합 후 `0c72ad6` 전체 스위트 실패 목록 **byte-identical (9=9)** — 회귀 0건 (증거: `.omo/evidence/commercial-ga-100/SEC-03/full-suite-failures.txt`)

## 비고

- 병합 시점에 구현자 테스트 1건(`test_default_allowlist_accepts_dashboard_dev_origin`)이 개발자 `.env`의 좁은 `AGK_CORS_ORIGINS`에 의존해 실패 — 이미 `3f6924c`에서 env 격리로 수정 확인. 계약 자체("env가 설정되면 그 목록을 신뢰")는 올바르게 동작.
- dashboard ticket 교환(`wsTicket.ts` + `useEventWebSocket`/`TerminalSession`)은 vitest 748/749(1건 baseline 선행)로 확인.

## 결론

SEC-03 **DONE** 판정. 브랜치는 audit trail로 보존.
