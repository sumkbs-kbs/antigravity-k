---
title: NX-05 PIN 변경·전체 세션 폐기 — 구현 인계
created: 2026-09-16
state: REVIEW (구현·시험 green, 독립 검토 대기)
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
depends_on: docs/qa/2026-09-16-followup/nx03/handoff.md, docs/adr/ADR-DAT-02-conversation-history-journal.md
tags: [nx-05, auth, epoch, revocation, handoff]
---

# NX-05 인계 기록 (구현 완료 / REVIEW)

```text
Task ID / attempt: NX-05 / attempt-001
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토 필요)
State: REVIEW — 구현·시험 green. 커밋하지 않았다.
Baseline full SHA: ffb0ebb312b76d86742d3e4065628a9704f8268e
Dirty paths (secret contents excluded):
  신규: src/antigravity_k/security/auth_state.py, tests/test_nx05_auth_epoch_revocation.py,
        dashboard/src/pages/SettingsPage.nx05.test.tsx, docs/qa/2026-09-16-followup/nx05/**
  수정: src/antigravity_k/engine/auth.py, src/antigravity_k/security/ws_ticket.py,
        src/antigravity_k/api/auth_routes.py, src/antigravity_k/api/auth_policy.py,
        src/antigravity_k/api/startup_security.py, src/antigravity_k/api/routes/session_state.py,
        scripts/api_forwarder.py, dashboard/src/pages/SettingsPage.tsx, dashboard/src/api/client.ts,
        dashboard/src/App.tsx, tests/test_auth.py
Scope / files / symbols: security/auth_state.py(AuthState, read_auth_state, current_epoch,
  write_auth_state_atomic, bump_epoch_atomic, _state_process_lock, LEGACY_EPOCH),
  engine/auth.py(TokenService.epoch_provider/current_epoch, EPOCH_CLAIM, verify_token),
  security/ws_ticket.py(WSTicketService.epoch_provider, consume), api/auth_routes.py
  (get_current_auth_epoch, get_current_pin_hash=파일 우선, _persist_pin_hash_atomic,
  change_pin+_revoke_authorized_ws_connections, ChangePinResponse), api/routes/session_state.py
  (register_authorized_ws/authorized_ws_count/reset_authorized_ws_registry/close_authorized_ws_blocking/
  aclose_authorized_ws), api/auth_policy.py(read_hash 가 read_pin_hash 사용),
  api/startup_security.py(_has_valid_pin_hash 가 read_pin_hash 사용), scripts/api_forwarder.py
  (_load_forwarder_pin_hash, bump_epoch_atomic).
Preconditions / dependency evidence: 기준 트리 재현 exit 3 / 수정 트리 exit 0 (before.md/after.md).
Observed failure before / exact reproduction: before.md §2~3 — 이전 bearer 200, 구 PIN(외부 변경 후) 200,
  stale WS ticket 재사용, 폐기 API 부재. old→after 비교는 after.md §1.
Change and invariant: PIN 변경 시 (1) hash+epoch 이 한 파일에서 원자 교체되고 (2) 세대가 잠금 안에서
  +1 되며 (3) 모든 토큰/ticket 검증이 **캐시 없이** 현재 세대와 비교되고 (4) 인증된 열린 WS 는 즉시 4401 로
  닫히고 (5) 화면이 재로그인을 요구한다. 실패(불일치 401 / 저장 5xx)는 폐기를 일으키지 않는다.
Commands / cwd / exit codes / environment: commands.txt (cwd = 레포 루트, 대시보드는 cwd=dashboard).
Runtime expected vs observed: 드라이버 before exit 3 → after exit 0. WS close 는 시험에서 4401 +
  경과 ≤5초. change-pin 응답에 reauth_required/epoch/sessions_revoked.
Regression results / raw log paths / hashes: regression.txt
  - tests/test_nx05_auth_epoch_revocation.py 21 passed
  - 인증·정책·WS 좁은 회귀 108 passed, forwarder 32 passed
  - 전체 스위트 6485 passed / 9 skipped / 0 failed (수집 6502 = NX-04 6481 + 신규 21)
  - 대시보드 87 files / 880 passed, typecheck·build exit 0
  - ruff / mypy clean
Data migration / backup / rollback observed: 기존 한 줄 hash 를 **읽기만** 한다(원본 보존).
  첫 검증에서 구버전 토큰이 거부되고 재로그인. rollback 은 이전 버전에서 폐기 토큰이 되살아나므로
  카드 조건(전 세션 재발급 + 구키 폐기) 없이는 하지 않는다.
Unverified / reason / impact:
  (1) 실제 원격 배포에서의 다중 기기 폐기 관측은 이 환경에서 불가(로컬 TestClient 관측만).
  (2) ~~SSE 스트림 **실연결** 폐기는 401 재연결로만 확인했다 — 이미 열린 SSE 응답 자체를 닫는
      경로는 없다(WS 전용).~~ → **해소(2026-09-16, NX-10 동결 배치)**: 실서버 관측에서 세대 변경
      1.112초 뒤 `event: session.revoked` + EOF 를 확인했고(`sse-live-revocation.md`,
      `before-sse.json`/`after-sse.json`), 계약은 `tests/test_nx05_sse_live_revocation.py`(10 passed)가
      고정한다. 구현은 `api/sse_revocation.py` + `server.py` 배선(라우트 16곳을 건드리지 않는다).
      남은 것: 브라우저 UI 가 이 이벤트로 로그인 화면으로 전환하는 동선(NX-09 후속).
      카드의 "활성 스트림에 epoch 재검증 경로가 없으면 DONE 으로 표시하지 않는다"에 해당 →
      SSE 는 다음 이벤트/재연결에서 끊기며, 이 범위를 DONE 으로 주장하지 않는다.
  (3) PIN 변경 동시성은 서로 다른 프로세스 간 flock 직렬화로 보장하지만, NFS 처럼 flock 의미가 약한
      파일시스템은 시험하지 않았다.
Reviewer verdict / reviewed SHA / artifact: 미지정 — 독립 검토 필요.
Next owner / exact next action: 19번 체크리스트 순서상 다음은 NX-06(deploy readiness).
  NX-05 잔여(위 (2) SSE, (3) 파일시스템 가정)는 NX-08/NX-10 에서 재확인한다.
```

## 1. 왜 epoch 을 "파일"에 두었는가

메모리 카운터나 별도 파일로는 (a) 프로세스 재시작, (b) 다중 프로세스, (c) hash 와 세대의 원자성
중 하나가 반드시 깨진다. 세대를 hash 와 **같은 문서**에 넣으면 "PIN 이 바뀐 순간"과 "세대가 오른
순간"이 같은 순간이 되고, 읽는 쪽은 부분 상태를 관측할 수 없다(시험 125회 관측으로 고정).

## 2. 다른 프로세스가 바꾼 PIN 을 즉시 반영하지 않던 결함 (추가 수정)

카드의 "프로세스별 stale cache 로 이전 토큰을 계속 받지 않게 한다"를 확인하는 과정에서,
토큰뿐 아니라 **PIN 검증 자체**가 시작 시점 hash 를 캐시하는 것을 확인했다
(before 드라이버 `old_pin_accepted_after_external_change: true`). 이 경로는 구 PIN 으로 **새 세대
토큰**을 발급하므로 폐기가 무력해진다. `get_current_pin_hash()` 를 파일 우선(캐시 없음)으로 바꾸고,
`AuthPolicy.read_hash` 도 같은 계약으로 맞췄다. 같은 카드 범위의 결함이라 함께 고쳤다.

## 3. 레거시 폴백 경로 정리 (스크립트)

`scripts/api_forwarder.py` 는 저장 파일을 직접 `read_text()` 해 hash 로 사용했으므로, 새 JSON 형식
도입 시 **PIN 검증이 전부 실패**하게 된다. `read_pin_hash`/`bump_epoch_atomic` 로 바꾸고, 시작 시
캐시 대신 요청마다 재판독하도록 고쳤다(구 PIN 이 계속 통하는 창을 없앤다).

## 4. 변경한 기존 계약 (검토 시 확인 필요)

| 파일 | 이전 | 이후 | 이유 |
|---|---|---|---|
| `tests/test_auth.py::test_change_pin_success` | PIN 원복을 같은 토큰으로 호출 | 새로 발급한 토큰으로 호출 | PIN 변경이 세대를 올리므로 이전 토큰 재사용은 401 이 정상(계약 변경) |
| `src/antigravity_k/api/auth_routes.py::get_current_pin_hash` | `_pin_hash` 반환 | 파일 우선, 파일이 없을 때만 `_pin_hash` | 다중 프로세스 stale cache 제거 |
| `src/antigravity_k/api/auth_policy.py::read_hash` | 파일 원문 반환 | `read_pin_hash` 결과 반환 | JSON 원문/`pin_hash:null` 오판 방지 |
| `ChangePinResponse` | `ok`, `detail` | + `reauth_required`, `epoch`, `sessions_revoked` | 재인증 필요를 계약으로 노출(필드 추가, 기존 소비자는 그대로 동작) |
| 저장 파일 형식 | 한 줄 hash | `agk.auth.v1` JSON (한 줄도 계속 읽음) | hash+epoch 원자성 |

## 5. 검토자가 우선 볼 지점

1. `bump_epoch_atomic` 의 잠금이 `write_auth_state_atomic` 의 `os.replace` 원자성과 충돌하지 않는지
   (잠금은 별도 sidecar `.auth_hash.lock`, fsync 는 원본 교체 전에 수행).
2. `close_authorized_ws_blocking` 이 **동기 라우트(FastAPI threadpool)** 에서 다른 루프로 넘기는
   방식 — 데드락 여부(교차 스케줄 시나리오: WS 핸들러가 close 를 기다리는 동안 PIN 변경이 완료를
   기다림). 현재 구현은 `future.result(timeout=5)` 로 상한을 둔다.
3. 대시보드 `agk:pin-required` 핸들러가 이제 거부된 토큰을 지운다 — 401 이 인증 플로우 밖에서
   발생하는 경우(예: 다른 기기의 폐기)에도 로그인 화면으로 전환되는지.
4. open_loopback(익명) 연결은 폐기 대상이 아니다 — credential 이 없으므로 세대가 없고, 정책상
   허용된 익명이다. 이 범위를 "폐기 미구현"으로 오해하지 않도록 시험으로 고정했다.
