---
title: NX-05 after — PIN 변경 = 전체 세션 폐기 (epoch 계약)
created: 2026-09-16
tags: [nx-05, after, evidence, auth]
---

# NX-05 after — 같은 입력에서 관측된 변화

```sh
NX05_TREE=after PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python docs/qa/2026-09-16-followup/nx05/repro_nx05_pin_change_revocation.py
# → exit 0
```

`after-run-output.json` (발췌):

```json
{
  "epoch_support_present": true,
  "state_document_is_json": true,
  "state_schema": "agk.auth.v1",
  "state_epoch": 2,
  "change_pin_response_keys": ["detail", "epoch", "ok", "reauth_required", "sessions_revoked"],
  "change_pin_reports_reauth": true,
  "old_bearer_status_after_change": 401,
  "old_bearer_accepted_after_change": false,
  "old_pin_accepted_after_change": false,
  "old_pin_accepted_after_external_change": false,
  "new_pin_accepted_after_change": true,
  "open_ws_revocation_api_present": true,
  "stale_ws_ticket_subject_after_change": null,
  "stale_ws_ticket_reusable": false,
  "revoked_and_rejected": true,
  "still_valid_credentials": []
}
```

## 1. 구현한 계약

| 요소 | 내용 |
|---|---|
| 저장 형식 | `agk.auth.v1` JSON = `{schema, pin_hash, epoch, updated_at}`. hash 와 세대는 **한 파일에서 원자 교체** — 읽는 쪽은 (이전 hash, 이전 epoch) 또는 (새 hash, 새 epoch) 만 본다. 구버전 한 줄 hash 는 계속 읽는다(epoch=`0`). |
| 세대 증가 | `bump_epoch_atomic()` 이 **파일 잠금 안에서** 읽기-수정-쓰기를 수행한다. 동시 변경에서도 성공 1건 = 새 세대 1개. |
| 토큰 | `TokenService(epoch_provider=...)` 가 발급 시 `epoch` claim 을 넣고 검증 시 **현재 값과 비교**한다. claim 이 없는 구버전 토큰은 거부(재로그인). 공급자는 캐시하지 않는다(매 검증 파일 재판독). |
| PIN 검증 | `get_current_pin_hash()` 가 **파일 우선**으로 읽는다 — 다른 프로세스의 PIN 변경이 즉시 반영된다(구버전은 시작 시점 hash 를 계속 사용). |
| WS ticket | `WSTicketService` 가 발급 세대를 claim 으로 갖고 소비 시 비교 — PIN 변경 전 ticket 은 TTL 과 무관하게 즉시 무효. |
| 열린 WS | 인증 성공한 WS 를 **약한 참조** 레지스트리에 등록하고, 폐기 시 각 연결의 이벤트 루프로 close(4401)를 넘겨 완료를 기다린다(측정값 ≤5초). 핸들러 5곳은 수정하지 않는다. |
| 응답/UI | `ChangePinResponse` 에 `reauth_required=true`, `epoch`, `sessions_revoked`. 대시보드는 성공 시 저장 토큰을 지우고 PIN 모달(재로그인)을 띄운다. 401 을 받은 화면의 전역 경로도 거부된 토큰을 지운다. |
| 전파 | PIN 폐기는 401(HTTP) / 4401(WS close) / `reauth_required`(본문)로 일관되게 전달된다. 실패(PIN 불일치 401, 저장 실패 5xx)는 폐기를 일으키지 않는다. |

## 2. 카드 시험 ↔ 구현 매핑

| 카드 시험 | 구현(파일::시험) |
|---|---|
| 이전 bearer 거부 / 새 PIN 로그인 성공 / 구 PIN 거부 | `test_nx05_auth_epoch_revocation.py::test_pin_change_rotates_epoch_and_revokes_previous_bearer` |
| 동시 PIN 변경 | `::test_concurrent_pin_changes_advance_one_generation_per_success` (2스레드, 성공 수 = 세대 증가 수) |
| 쓰기 실패에서 기존 상태 유지 | `::test_change_pin_persist_failure_keeps_old_credentials` (bytes 비교 + 기존 토큰 유효 + 새 PIN 401 + 5xx) |
| 프로세스 두 개의 인증 | `::test_two_processes_share_the_generation_without_caching` (spawn 자식이 파일을 바꾸면 부모가 즉시 거부) |
| restart | `::test_restart_keeps_revocation` (auth 상태 재로드 후에도 이전 토큰 거부) |
| 기존 WS 폐기(≤5초) | `::test_open_ws_is_closed_immediately_when_sessions_are_revoked` (실제 TestClient WS, close 4401) + `::test_close_authorized_ws_blocking_closes_within_budget` (경과 시간 측정) |
| ticket 재사용 거부 | `::test_ws_ticket_from_previous_generation_is_rejected`, `::test_ws_ticket_issued_before_change_cannot_open_a_stream` |
| SSE 재연결 | `::test_sse_style_reconnect_with_revoked_bearer_is_rejected` (bearer 재사용 2회 401) |
| 모드별 규칙 | `::test_mode_specific_rules_for_pin_change` (local/remote PIN = protected, credential 없음 + dev 허용 + loopback = open_loopback, 비-loopback = deny) |
| migration 뒤 재로그인 | `::test_legacy_single_line_hash_is_read_as_epoch_zero`, `::test_token_without_epoch_claim_is_rejected` |
| 중간 상태 미노출 | `::test_auth_state_never_exposes_a_partial_document` (125회 동시 관측) |
| 쓰기 실패 시 이전 bytes 보존 | `::test_auth_state_write_failure_keeps_previous_state` |

## 3. 데이터 이전 / 복구 조건

- 기존 `data/auth_hash`(한 줄 hash)는 **그대로 읽힌다**. 첫 로그인 시도에서 사용자는 재로그인하게 된다
  (구버전 토큰에는 epoch claim 이 없으므로 거부 — 카드가 요구한 migration 동작).
- 운영자가 새 schema 로 옮기려면 PIN 변경 1회 또는 로그인 후 change-pin 을 수행하면 된다.
  별도의 파일 변환·백업이 필요하지 않다(원본 hash 를 파괴하지 않고 그대로 읽기 때문).
- 레거시 X-Access-Pin 폴백을 쓰는 `scripts/api_forwarder.py` 도 같은 문서를 읽도록 고쳤고,
  시작 시 캐시 대신 **요청마다 재판독**한다.
- rollback: 이전 버전으로 되돌리면 epoch claim 을 무시하므로 **폐기한 토큰이 다시 살아난다**.
  카드의 rollback 조건대로 검증된 절차(전 세션 재발급 + 구키 폐기) 없이는 되돌리지 않는다.

## 4. 회귀 범위

- 인증·정책·WS 좁은 회귀 108 passed, forwarder 32 passed, 전체 스위트 6485 passed / 실패 0(regression.txt).
- 대시보드 87 files / 880 passed (`pnpm test` 2회 연속 동일), `pnpm typecheck` / `pnpm build` 통과.
- `src/antigravity_k/dashboard_dist/` 는 파생 산출물이라 되돌렸다(패키징 단계에서 재생성).
