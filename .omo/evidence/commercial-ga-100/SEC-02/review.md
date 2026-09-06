# SEC-02 독립 리뷰 — r1 APPROVE

- **Reviewer:** sec_02_verify (구현자 sec_02_impl과 상이한 세션 — Freebuff 세션, 2026-09-07)
- **검증 대상:** `codex/sec-02-pin-rate-limit` @ `eab18a4` (rebase 완료 — base tip `25c4226` 위 `24c7ae3` 구현 + `eab18a4` 리베이스 통합 수정)
- **Verdict:** **APPROVE** — 결함 1건 발견 후 당일 수정·재검증 완료. 수용기준 4건 전부 독립 재현으로 확인.

## 리뷰 전제 정리 (rebase)

구현은 base `6d3c515`에서 완료되었으나 커밋이 pre-commit 충돌로 유실된 상태였다.
리뷰어가 이를 복구·커밋(`24c7ae3`)하고, SEC-01 병합 이후의 baseline `25c4226`에 리베이스했다.
리베이스 충돌 5파일은 다음 원칙으로 해소했다:

- **auth_routes.py** — SEC-01의 fail-closed AuthPolicy + open_loopback 익명 판정 유지,
  legacy PIN 검증 leg(PBKDF2) 제거 (SEC-02 표면 축소)
- **auth_policy.py** — `evaluate_credential`에서 `pin` 파라미터/검증 leg 제거.
  SEC-01이 추가한 정책 객체의 pin leg는 SEC-02 이후 dead code이자 잠재 PBKDF2 표면이므로
  "rate-limited login/token에서만 PBKDF2" 계약과 정합하게 제거 (리뷰 판정 강화)
- **session_state.py** — WS gate는 bearer 토큰만, `evaluate_credential(token_verified=...)`만 호출
- **테스트** — legacy PIN 인증 테스트는 SEC-02 거부 테스트로 대체, fixture는 SEC-01의
  subprotocol 채널(headers)과 정합

## 검증 방법

1. **수용기준 독립 재현**: 구현자 테스트와 별개의 리뷰어 스크립트
   `reviewer-acceptance-check.py` — **12/12 PASS** (output: `reviewer-output.txt`)
2. **인접 스위트 재실행**: SEC-02 17건 + auth + 진리표 + WS(단위/live) + harness — **147 passed**
3. **회귀 분석**: merge-base `25c4226` throwaway worktree vs branch `eab18a4` 전체 스위트
   (slow/benchmark 제외, tests/e2e 제외) 실패 목록 diff → **byte-identical (21=21)**.
   회귀 0건. (기록: `/tmp/sec02_rv_base_failures.txt`, `/tmp/sec02_rv_branch_failures.txt`)

## 수용기준별 결과

### AC-1 임의 보호 URL에서 PIN 후보를 보내도 PBKDF2 검증이 실행되지 않는다 — PASS

- 정적 검증: `verify_pin(` 호출처가 rate-limited login/token route(auth_routes.py)뿐 — 전 src 스캔
- 동적 검증: X-Access-Pin 헤더로 authenticate_request → `False`, verify_pin spy 호출 **0회**
- WS: query `?pin=` → 4401 close, PBKDF2 **0회**
- 리뷰 강화: SEC-01이 통합한 `auth_policy.evaluate_credential`의 pin leg도 제거 —
  정책 객체는 이제 임의 요청에서 실행 가능한 PBKDF2 표면을 갖지 않는다

### AC-2 IP와 계정/session 기준 burst 및 sustained limit이 적용된다 — PASS

- burst 5회 실패 → lockout 시작(5번째 실패에서 차단)
- lockout 중 `register()` 즉시 거절 + Retry-After 300s
- sustained(600s 창) 누적 10회 → lockout
- key 분리: 다른 계정 key는 독립 판정, `record_success`로 해제

### AC-3 성공/실패/lockout audit가 secret 없이 남는다 — PASS

- login_failed / login_success / lockout 3종 이벤트 기록 확인
- detail에 `pin=…`, `credential=…` 주입 → 스크럽 확인, credential 값이 어떤 필드에도 없음

### AC-4 공격 요청이 정상 인증 latency 대비 threshold 이상으로 악화되지 않는다 — PASS

- 실측: PBKDF2(600k iter) 1회 = 42ms. lockout 공격 200회 시도가 유발한 총 CPU = **0.3ms**
  (동일 시도가 검증을 통과했다면 8,367ms — **4 orders of magnitude 절감**)
- lockout 중 모든 register 거절 확인

## 발견 결함과 해소

| # | 등급 | 내용 | 해소 |
|---|------|------|------|
| F1 | 중 | 리베이스 자동 병합이 WS gate의 구 call부(`pin=None` kwarg)를 남겨 `evaluate_credential` 시그니처 불일치 — truth table 스위트 TypeError | `eab18a4`에서 호출부 정리 + 미사용 verify_pin import 제거 + fixture 보강. 147건 재실행 green |

## 비차단 관찰 (non-blocking)

1. `CredentialGate.register`가 lockout 중 `record_event`를 로컬 변수로 참조(`_audit_record`) —
   import 이름 정합성 확인 요(동작은 테스트로 검증됨)
2. slowapi(429)와 gate(403)의 이중 방어는 유지 — 문서화된 설계대로
3. 대시보드는 token-first(accessPinCredential.ts)라 서버 표면 제거만으로 정합 — 별도 마이그레이션 불필요

## 결론

SEC-02의 핵심 계약 — "PBKDF2는 rate-limited 교환 경로에서만 실행된다" — 가
HTTP/WS 전 표면에서 성립하며, gate/audit가 secret-free로 동작한다.
baseline 회귀 0건. **r1 APPROVE**, 병합 권고.
