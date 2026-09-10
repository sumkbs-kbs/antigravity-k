"""SEC-01 — 단일 AuthPolicy 진리표 테스트.

계약 (docs/11_COMMERCIAL_GA_100_PLAN.md §SEC-01):
  startup/HTTP/SSE/WS가 같은 AuthPolicy를 사용한다.
  저장 PIN hash가 있으면 loopback 개발 모드도 보호 상태로 처리한다.
  무자격 HTTP/SSE/WS가 각각 401/401/4401로 거절된다.
  dev no-PIN 허용은 명시적 설정 + loopback 조건이 모두 충족될 때만 가능하다.
  PIN 상태(있음/없음/변경)와 표시(protected status)가 항상 일치한다.

진리표 (8행 — auth_policy.resolve_auth_decision 입력→결정):
  ┌──────────────┬──────────────┬─────────────┬──────────────────┐
  │ stored_hash  │ plaintext_pin│ loopback    │ dev_no_pin_허용  │
  ├──────────────┼──────────────┼─────────────┼──────────────────┤
  │ 없음         │ 없음         │ O           │ O → open-loopback│
  │ 없음         │ 없음         │ O           │ X → deny(401)    │
  │ 없음         │ 없음         │ X           │ - → deny(401)    │
  │ 없음         │ 있음         │ -           │ - → hash-protect │
  │ 있음         │ 없음         │ O           │ - → DENY (핵심)  │
  │ 있음         │ 없음         │ X           │ - → DENY         │
  │ 있음         │ 있음         │ O           │ - → DENY         │
  │ 있음         │ 있음         │ X           │ - → DENY         │
  └──────────────┴──────────────┴─────────────┴──────────────────┘
  "stored_hash 있음"인 모든 행은 loopback/dev 설정과 무관하게 보호 상태.
  이것이 SEC-01의 핵심 계약: "저장 hash만 있어도 보호 상태가 유지된다".

전송면 통합 검증:
  HTTP  → 미인증 /v1/chat/completions        → 401
  SSE   → 미인증 /v1/messages (stream)        → 401
  WS    → 미인증 /v1/ws/events                → close 4401
  세 면 모두 같은 policy 객체를 사용한다 (모듈 싱글톤 주입 검증).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from antigravity_k.api.startup_security import is_loopback_host
from antigravity_k.engine.auth import hash_pin

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 1) 단일 policy 진리표 (순수 단위)
# ---------------------------------------------------------------------------


class TestAuthPolicyTruthTable:
    """auth_policy.resolve_auth_decision — 8행 전수 검증."""

    @pytest.fixture()
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGK_SEC_DEV_NO_PIN_ALLOW", raising=False)
        monkeypatch.delenv("AGK_ENV", raising=False)

    @pytest.mark.parametrize(
        ("has_stored_hash", "has_plaintext_pin", "loopback", "dev_allow", "expected"),
        [
            # stored hash 없음 — dev 허용(명시) + loopback일 때만 open
            (False, False, True, True, "open_loopback"),
            (False, False, True, False, "deny"),
            (False, False, False, True, "deny"),
            # plaintext PIN 구성 — loopback/dev 조건 무관 보호
            (False, True, True, True, "protected"),
            (False, True, False, False, "protected"),
            # stored hash 존재 — 항상 보호 (SEC-01 핵심 계약)
            (True, False, True, True, "protected"),
            (True, False, False, False, "protected"),
            (True, True, True, True, "protected"),
            (True, True, False, False, "protected"),
        ],
        ids=[
            "nopin-loopback-devallow-open",
            "nopin-loopback-nodev-deny",
            "nopin-remote-devallow-deny",
            "plaintext-loopback-protected",
            "plaintext-remote-protected",
            "hashonly-loopback-devallow-DENY",
            "hashonly-remote-DENY",
            "hash+pin-loopback-DENY",
            "hash+pin-remote-DENY",
        ],
    )
    def test_truth_table(
        self,
        _clean_env: None,
        has_stored_hash: bool,
        has_plaintext_pin: bool,
        loopback: bool,
        dev_allow: bool,
        expected: str,
    ) -> None:
        from antigravity_k.api import auth_policy

        decision = auth_policy.resolve_auth_decision(
            stored_pin_hash="pbkdf2_sha256$600000$c2FsdA==$aGFzaA==" if has_stored_hash else None,
            plaintext_pin_configured="x" * 8 if has_plaintext_pin else "",
            host="127.0.0.1" if loopback else "0.0.0.0",
            dev_no_pin_allow=dev_allow,
        )
        assert decision.level == expected

    def test_dev_allow_requires_explicit_env_not_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """dev_no_pin_allow는 기본값 False — 명시적 설정 없으면 open-loopback 불가."""
        from antigravity_k.api import auth_policy

        monkeypatch.delenv(auth_policy.DEV_NO_PIN_ALLOW_ENV, raising=False)
        policy = auth_policy.AuthPolicy(
            stored_pin_hash=lambda: None,
            plaintext_pin=lambda: "",
        )
        assert policy.dev_no_pin_allow is False

    def test_hash_only_plus_dev_allow_env_is_still_protected(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """환경변수로 dev 허용을 켜도 stored hash가 있으면 보호 유지 (fail-closed)."""
        from antigravity_k.api import auth_policy

        monkeypatch.setenv("AGK_SEC_DEV_NO_PIN_ALLOW", "1")
        hash_file = tmp_path / "auth_hash"
        hash_file.write_text(hash_pin("real-pin-1234"), encoding="utf-8")
        policy = auth_policy.AuthPolicy.from_config(pin_hash_file=hash_file)
        decision = policy.resolve(host="127.0.0.1")
        assert decision.level == "protected"

    def test_pin_removal_changes_level_immediately(self, tmp_path: Path) -> None:
        """PIN 삭제(hash 파일 제거) 후 level이 즉시 재평가된다 (표시-실제 일치)."""
        from antigravity_k.api import auth_policy

        hash_file = tmp_path / "auth_hash"
        hash_file.write_text(hash_pin("pin-12345678"), encoding="utf-8")
        policy = auth_policy.AuthPolicy.from_config(pin_hash_file=hash_file)
        assert policy.resolve(host="127.0.0.1").level == "protected"
        hash_file.unlink()
        # 파일 삭제 후에도 같은 policy 객체가 캐시 없이 재평가.
        assert policy.resolve(host="127.0.0.1").level != "protected"

    def test_pin_change_reflected_in_status_payload(self, tmp_path: Path) -> None:
        """PIN 변경(hash 파일 갱신) 후 status payload가 새 상태를 반영한다."""
        from antigravity_k.api import auth_policy

        hash_file = tmp_path / "auth_hash"
        hash_file.write_text(hash_pin("first-pin-1"), encoding="utf-8")
        policy = auth_policy.AuthPolicy.from_config(pin_hash_file=hash_file)
        assert policy.status()["protected"] is True
        hash_file.unlink()
        assert policy.status()["protected"] is False


# ---------------------------------------------------------------------------
# 2) HTTP/SSE/WS 전송면 — hash-only loopback에서 무자격 거부
# ---------------------------------------------------------------------------


@pytest.fixture()
def hash_only_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """저장 PIN hash만 있는 loopback 개발 서버 TestClient.

    access_pin=""(plaintext 없음) + pin_hash_file에 유효 hash 저장.
    SEC-01 핵심 시나리오: hash-only loopback 개발 모드도 보호 상태.
    """
    from fastapi.testclient import TestClient

    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.config import config

    hash_file = tmp_path / "auth_hash"
    hash_file.write_text(hash_pin("stored-pin-1234"), encoding="utf-8")

    orig_pin = config.security.access_pin
    orig_hash_file = config.security.pin_hash_file
    orig_secret_file = config.security.token_secret_file
    config.security.access_pin = ""  # plaintext 없음 — hash만 존재
    config.security.pin_hash_file = str(hash_file)
    config.security.token_secret_file = str(tmp_path / "token_secret")
    monkeypatch.delenv("AGK_SEC_DEV_NO_PIN_ALLOW", raising=False)

    setattr(auth_routes_mod, "_token_service", None)
    setattr(auth_routes_mod, "_pin_hash", None)
    auth_routes_mod.init_auth_state()

    from antigravity_k.api.server import app

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    config.security.access_pin = orig_pin
    config.security.pin_hash_file = orig_hash_file
    config.security.token_secret_file = orig_secret_file
    setattr(auth_routes_mod, "_token_service", None)
    setattr(auth_routes_mod, "_pin_hash", None)
    auth_routes_mod.init_auth_state()


class TestHashOnlyLoopbackIsProtected:
    """저장 hash만 있는 loopback — 무자격 HTTP 401 / WS 4401 / status=protected."""

    def test_http_unauthenticated_rejected_401(self, hash_only_server: TestClient) -> None:
        resp = hash_only_server.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 401

    def test_sse_unauthenticated_rejected_401(self, hash_only_server: TestClient) -> None:
        resp = hash_only_server.post(
            "/v1/messages",
            json={"model": "m", "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 401

    def test_ws_unauthenticated_closed_4401(self, hash_only_server: TestClient) -> None:
        """무자격 WS — accept 직후 close 4401 프레임 수신 (plan 규정 equivalent).

        TestClient에서 서버가 accept 후 close하면 connect는 성공 표시되고
        첫 수신 프레임이 ``websocket.close`` 4401로 온다 — 예외 대신 프레임 검증.
        """
        with hash_only_server.websocket_connect("/v1/ws/events") as ws:
            first = ws.receive()
        assert first == {"type": "websocket.close", "code": 4401, "reason": "Unauthorized"}

    def test_login_with_stored_pin_succeeds(self, hash_only_server: TestClient) -> None:
        """저장 hash의 PIN으로 로그인하면 토큰 발급 — 보호 상태에서 정상 경로.

        test_auth.py의 rate-limit 테스트가 slowapi 카운터를 소진할 수 있으므로
        (공유 limiter, testclient 동일 IP), 429면 카운터 리셋 후 1회 재시도한다.
        """
        resp = hash_only_server.post("/api/auth/login", json={"pin": "stored-pin-1234"})
        if resp.status_code == 429:
            from antigravity_k.api.auth_routes import _limiter

            _limiter.reset()
            resp = hash_only_server.post("/api/auth/login", json={"pin": "stored-pin-1234"})
        assert resp.status_code == 200
        token = cast(dict[str, Any], resp.json())["access_token"]
        ok = hash_only_server.get(
            "/api/session/info",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ok.status_code != 401

    def test_status_endpoint_reports_protected(self, hash_only_server: TestClient) -> None:
        resp = hash_only_server.get("/api/auth/status")
        assert resp.status_code == 200
        payload = cast(dict[str, Any], resp.json())
        assert payload["protected"] is True
        assert payload["level"] == "protected"


# ---------------------------------------------------------------------------
# 3) 단일 정책 일치 — HTTP/WS가 같은 AuthPolicy 인스턴스를 사용
# ---------------------------------------------------------------------------


class TestSinglePolicyConsistency:
    """startup/HTTP/WS가 같은 policy 소스를 쓰는지 구조적으로 고정."""

    def test_http_middleware_delegates_to_shared_policy(self) -> None:
        """authenticate_request가 auth_policy 모듈의 policy를 사용한다."""
        import inspect

        import antigravity_k.api.auth_policy as auth_policy
        import antigravity_k.api.auth_routes as auth_routes

        src = inspect.getsource(auth_routes.authenticate_request)
        assert "get_shared_auth_policy" in src, (
            "authenticate_request는 공유 AuthPolicy를 통해 평가해야 한다 (SEC-01 단일 정책)"
        )
        assert hasattr(auth_policy, "get_shared_auth_policy")

    def test_ws_gate_delegates_to_shared_policy(self) -> None:
        import inspect

        from antigravity_k.api.routes import session_state

        src = inspect.getsource(session_state.close_unauthorized_ws)
        assert "get_shared_auth_policy" in src, "close_unauthorized_ws도 같은 공유 AuthPolicy를 사용해야 한다"

    def test_extract_token_from_ws_no_longer_accepts_pin_query(self) -> None:
        """WS query ?pin= 인증 경로 제거 — credential로 PIN을 받지 않는다."""
        from types import SimpleNamespace

        from antigravity_k.engine.auth import extract_token_from_ws

        ws = SimpleNamespace(query_params={"pin": "whatever"}, headers={})
        assert extract_token_from_ws(cast(Any, ws)) is None

    def test_ws_query_pin_param_not_authorized(self, hash_only_server: TestClient) -> None:
        """?pin=<stored pin>으로도 WS 인증 불가 — PIN credential 수집 자체를 안 한다."""
        with hash_only_server.websocket_connect("/v1/ws/events?pin=stored-pin-1234") as ws:
            first = ws.receive()
        assert first == {"type": "websocket.close", "code": 4401, "reason": "Unauthorized"}

    def test_is_loopback_host_matrix(self) -> None:
        assert is_loopback_host("127.0.0.1")
        assert is_loopback_host("::1")
        assert is_loopback_host("localhost")
        assert not is_loopback_host("0.0.0.0")
        assert not is_loopback_host("192.168.1.5")


# ---------------------------------------------------------------------------
# 4) startup 통합 — hash-only가 서버 기동을 막지 않으면서 보호 유지
# ---------------------------------------------------------------------------


class TestStartupIntegration:
    def test_startup_accepts_hash_only_on_public_bind(self, tmp_path: Path) -> None:
        from antigravity_k.api.startup_security import validate_startup_security

        hash_file = tmp_path / "auth_hash"
        hash_file.write_text(hash_pin("x" * 12), encoding="utf-8")
        # 예외 미발생 = 기동 허용 (hash가 strong credential).
        validate_startup_security(
            host="0.0.0.0",
            environment="development",
            access_pin="",
            pin_hash_file=hash_file,
        )

    def test_startup_still_rejects_no_credential_public_bind(self, tmp_path: Path) -> None:
        from antigravity_k.api.startup_security import StartupSecurityError, validate_startup_security

        with pytest.raises(StartupSecurityError):
            validate_startup_security(
                host="0.0.0.0",
                environment="development",
                access_pin="",
                pin_hash_file=tmp_path / "missing",
            )


# ---------------------------------------------------------------------------
# 5) WS loopback open 모드 — dev 허용 명시 시에만 익명 허용
# ---------------------------------------------------------------------------


class TestOpenLoopbackRequiresExplicitDevAllow:
    @pytest.fixture()
    def _no_pin_setup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import antigravity_k.api.auth_routes as auth_routes_mod
        from antigravity_k.config import config

        monkeypatch.setattr(config.security, "access_pin", "")
        monkeypatch.setattr(auth_routes_mod, "get_current_pin_hash", lambda: None)
        monkeypatch.delenv("AGK_SEC_DEV_NO_PIN_ALLOW", raising=False)

    def _ws_allowed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> bool:
        from types import SimpleNamespace

        from antigravity_k.api.routes import session_state

        closed: list[Any] = []

        async def fake_accept() -> None:
            return None

        async def fake_close(**kwargs: object) -> None:
            closed.append(kwargs)

        ws = cast(Any, SimpleNamespace(query_params={}, headers={}, state=SimpleNamespace()))
        ws.accept = fake_accept  # type: ignore[method-assign]
        ws.close = fake_close  # type: ignore[method-assign]

        import asyncio

        asyncio.run(session_state.close_unauthorized_ws(ws))
        return len(closed) == 0

    def test_no_pin_loopback_without_explicit_allow_denies(
        self, _no_pin_setup: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """dev 허용 env 없이 no-PIN loopback이면 deny — 기본 fail-closed."""
        monkeypatch.chdir(tmp_path)
        assert self._ws_allowed(monkeypatch, tmp_path) is False

    def test_no_pin_loopback_with_explicit_allow_accepts(
        self, _no_pin_setup: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("AGK_SEC_DEV_NO_PIN_ALLOW", "1")
        monkeypatch.chdir(tmp_path)
        assert self._ws_allowed(monkeypatch, tmp_path) is True

    def test_non_loopback_host_always_denies_even_with_allow(
        self, _no_pin_setup: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from antigravity_k.config import config

        monkeypatch.setenv("AGK_SEC_DEV_NO_PIN_ALLOW", "1")
        monkeypatch.setattr(config.server, "host", "0.0.0.0")
        monkeypatch.chdir(tmp_path)
        assert self._ws_allowed(monkeypatch, tmp_path) is False

    def test_production_always_denies_anon(
        self, _no_pin_setup: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("AGK_SEC_DEV_NO_PIN_ALLOW", "1")
        monkeypatch.setenv("AGK_ENV", "production")
        monkeypatch.chdir(tmp_path)
        assert self._ws_allowed(monkeypatch, tmp_path) is False
