# SEC-01 독립 리뷰 — r1 APPROVE

- **Reviewer:** sec_01_verify (구현자 sec_01_policy와 상이한 세션 — Freebuff/Claude 세션, 2026-09-06)
- **검증 대상:** `codex/sec-01-auth-policy` @ `89ad09f` (2 commits: 8f9396c + 89ad09f, base `6d3c515`)
- **Verdict:** **APPROVE** — 발견 결함 0건. 수용기준 6건 전부 독립 재현으로 확인.

## 검증 방법

1. **코드 리뷰**: `api/auth_policy.py` 전체 (resolve_auth_decision 순수 함수 + AuthPolicy 콜백 래퍼 + 공유 싱글톤), auth_routes/session_state/engine.auth 연동부, conftest 하네스
2. **독립 재현 스크립트**: 리뷰어 작성 시나리오 스크립트로 구현자 테스트와 무관하게 정책 직접 평가 (아래 표)
3. **증거 재현**: `test_auth_policy_truth_table.py` 29건 + auth/WS 인접 스위트 46건 재실행
4. **정적 검사**: ruff (변경 파일 전체), mypy repo-wide (461 files, 0 errors)

## 수용기준 대조 (독립 재현)

| 수용기준 | 독립 재현 결과 |
|---|---|
| 단일 정책 — startup/HTTP/SSE/WS 모두 같은 AuthPolicy | **PASS** — 구조 고정 테스트 + 소스 확인 (authenticate_request/close_unauthorized_ws/status가 get_shared_auth_policy 공유) |
| 저장 hash만으로 보호 (hash-only 서버) | **PASS** — 스크립트 1번: hash-only loopback이 `protected/credential-present` 반환 (수정 전에는 익명 허용되던 핵심 결함) |
| 무자격 요청 fail-closed (HTTP/SSE 401, WS 4401) | **PASS** — 진리표 스위트의 전송면 테스트 (close 프레임 코드 검증 포함) |
| dev no-PIN 허용 명시적 3조건 | **PASS** — 스크립트 2·3·5번: env+loopback+무credential 조건, production 무시, 0.0.0.0 deny |
| PIN 변경/삭제/restart 표시-실제 일치 | **PASS** — 스크립트 4번: hash 파일 삭제 즉시 protected→open_loopback 전환 (캐시 없음 확인) |
| 진리표 자동 테스트 | **PASS** — 29 tests (9행 진리표 parametrize 전수 + 전송면 3종 + 구조 고정) |

독립 재현 스크립트 결과: **6/6 PASS** (`/tmp/sec01_acceptance_check.py`).

## 테스트 재실행

- `test_auth_policy_truth_table.py`: **29 passed**
- `test_auth.py` + `test_workspace_websocket.py` + `test_workspace_websocket_live.py`: **46 passed**
- 합계 75 passed, 0 failed

## 관찰 (non-blocking)

1. `AuthDecision`에 `allowed` 헬퍼 property가 없어 호출부가 `level` 문자열 비교를 한다 — 가독성 개선 여지.
2. `resolve()`의 production 재검사가 `resolve_auth_decision` 밖에서 이중으로 수행됨 — 안전이면 방어적이나 진리표 단일화 관점에서 흡수 가능.
3. `/api/auth/status`가 public allowlist에 추가됨 — level/reason만 노출하고 credential을 반환하지 않으므로 정보 노출 우려 없음 (코드 확인).

## 결론

구현은 plan §SEC-01의 계약을 정확히 충족하며, 시작 시점과 런타임 정책 불일치(저장 hash 존재 시에도 익명 허용)라는 핵심 결함을 제거했다. **r1 APPROVE** — 병합 조건 충족.
