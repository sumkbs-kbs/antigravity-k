"""CR-14 F-20 계약 — 로그인 보안 상태(레이트리밋·lockout)는 테스트 사이에 새지 않는다.

발견(F-20, attempt-013)
=======================
로그인 경로에는 **키가 "호출자 IP"인 전역 상태 기계가 둘** 있고, TestClient 는 항상 같은
주소를 쓰기 때문에 한 pytest 프로세스 안의 앞선 테스트가 뒤 테스트의 결과를 바꿨다:

  1. `auth_routes._limiter` (slowapi `5/minute`) → 초과 시 **429**.
  2. `credential_gate` 실패 burst/sustained 임계 → **lockout 403**.

실측(같은 코드, 순서만 다름, deps=dev+rag):

    pytest tests/test_sec03_ws_origin_ticket.py::TestWsGateIntegration          -> 7 passed
    pytest <로그인 5회 태우는 파일> tests/...::TestWsGateIntegration             -> 5 failed (429)
    pytest tests/test_auth.py tests/test_auth_policy_truth_table.py             -> 1 failed (403)

두 기계가 서로를 가려 왔다는 점이 핵심이다 — 레이트리밋 카운터가 먼저 차서 429로 끝나면
실패가 임계까지 쌓이지 않아 lockout 이 켜지지 않는다. 즉 지금까지의 초록은 "누수가 없어서"가
아니라 "한 누수가 다른 누수를 가려서"였다. 대응은 개별 테스트의 우회였고(429만 처리),
실제로 도착한 403 은 막지 못했다.

격리는 하네스(`conftest.py::_reset_login_security_state`)가 소유한다. 이 파일은 그 계약이
지켜지는지를 **순서로** 잰다 — 앞 테스트가 상태를 태우고, 뒤 테스트가 깨끗한 상태를 받는다.

제품 계약은 그대로다: 한 테스트 안에서 5회는 허용, 6회는 429(`test_auth.py` 가 더 넓게 잰다).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.auth import hash_pin

BURN_COUNT = 5


@pytest.fixture
def login_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """저장 PIN hash 를 가진 보호 서버 TestClient — 로그인 상태 기계만 재는 최소 하네스."""
    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.config import config
    from antigravity_k.security import ws_ticket as ws_ticket_mod

    hash_file = tmp_path / "auth_hash"
    hash_file.write_text(hash_pin("stored-pin-1234"), encoding="utf-8")

    orig = (
        config.security.access_pin,
        config.security.pin_hash_file,
        config.security.token_secret_file,
    )
    config.security.access_pin = ""
    config.security.pin_hash_file = str(hash_file)
    config.security.token_secret_file = str(tmp_path / "token_secret")
    monkeypatch.delenv("AGK_SEC_DEV_NO_PIN_ALLOW", raising=False)

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    ws_ticket_mod.reset_ws_ticket_service()

    from antigravity_k.api.server import app

    yield TestClient(app, raise_server_exceptions=False)

    (
        config.security.access_pin,
        config.security.pin_hash_file,
        config.security.token_secret_file,
    ) = orig
    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    ws_ticket_mod.reset_ws_ticket_service()


def _login(client: TestClient) -> int:
    """로그인 1회의 상태 코드."""
    return client.post("/api/auth/login", json={"pin": "stored-pin-1234"}).status_code


def test_burn_the_login_window(login_client: TestClient) -> None:
    """이 테스트는 창(1분)의 5회를 태운다 — 제품의 의도된 허용 한도까지.

    뒤 테스트가 깨끗한 상태를 받지 못하면 429/403 으로 실패한다. 그래서 이 테스트는
    부작용을 **일부러** 남기고, 계약은 다음 테스트가 잰다.
    """
    for attempt in range(1, BURN_COUNT + 1):
        assert _login(login_client) == 200, f"{attempt}번째 로그인이 거절됐다"

    # 한도 초과는 제품 계약이다(여기서 429/403 이 나오지 않으면 게이트가 사라진 것이다).
    assert _login(login_client) in (429, 403), "한도 초과가 더 이상 거절되지 않는다"


def test_next_test_starts_with_a_clean_window(login_client: TestClient) -> None:
    """앞 테스트가 태운 상태가 새지 않는다 — 새 테스트의 첫 로그인은 성공해야 한다.

    이 단언이 F-20 의 계약이다. `conftest.py` 의 리셋이 사라지면 앞 테스트가 남긴
    카운터/lockout 때문에 여기서 429 또는 403 이 온다(순서 의존의 정확한 재현).
    """
    assert _login(login_client) == 200
