SEC-01 수동 검증 기록
=====================

## 1. hash-only loopback 시나리오 (핵심 계약)

직접 관찰 (python REPL, 실서버 app):
  조건: config.security.access_pin="" / pin_hash_file에 유효 pbkdf2 hash 저장 /
        AGK_SEC_DEV_NO_PIN_ALLOW 미설정 / host=127.0.0.1

  구버전: authenticate_request() == True  ← 결함 (익명 허용)
  신버전: authenticate_request() == False → 미들웨어가 401 반환

  curl 등가 (TestClient):
    POST /v1/chat/completions (무자격) → 401
    POST /v1/messages        (무자격) → 401
    WS   /v1/ws/events       (무자격) → accept 직후 close 4401
    POST /api/auth/login (저장 PIN)    → 200 + token
    GET  /api/session/info (Bearer)   → 200대 (401 아님)
    GET  /api/auth/status             → {"protected": true, "level": "protected", ...}

## 2. dev 익명 허용 조건 (명시적 계약)

  - AGK_SEC_DEV_NO_PIN_ALLOW 미설정 + no-credential + loopback → deny (기본 fail-closed)
  - AGK_SEC_DEV_NO_PIN_ALLOW=1 + no-credential + loopback → open_loopback (익명 허용)
  - AGK_SEC_DEV_NO_PIN_ALLOW=1 + no-credential + 0.0.0.0 → deny
  - AGK_ENV=production + dev-allow + loopback → deny (이중 안전장치)

## 3. PIN 상태 일치 (표시-실제)

  - hash 파일 삭제 직후 /api/auth/status.protected == false (캐시 없음, 즉시 재평가)
  - hash 파일 갱신 직후 status가 새 상태 반영
  - status payload는 HTTP/WS와 동일 get_shared_auth_policy()에서 산출

## 4. WS credential 표면

  - ?pin= 쿼리로는 인증 불가 (extract_token_from_ws가 수집 자체를 안 함)
  - ?token= / Sec-WebSocket-Protocol bearer.* 채널만 유효
  - workspace WS 테스트 26건이 token 채널로 이전되어 통과

## 5. 환경 함정 (재발 방지 기록)

  - 이 머신의 기본 python이 miniforge3 — 테스트 서브프로세스는 반드시
    sys.executable(=venv python) 사용. uv run --no-sync pytest 사용.
  - worktree 최초 실행 시 uv sync --all-extras 필요 (기본 extras만으로는
    mlx/pytest-asyncio 부재로 위양성 실패 발생 — DAT-03에서 동일 함정 확인됨).
  - 로컬 data/auth_hash는 conftest가 AGK_SEC_PIN_HASH_FILE을 tmp로 격리하여
    테스트 결과에 영향을 주지 않음 (결정론).
