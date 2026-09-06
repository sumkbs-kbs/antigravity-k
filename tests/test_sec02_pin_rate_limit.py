"""SEC-02: PIN 교환 제한과 credential 표면 축소 (Red 테스트).

GA-100 plan §SEC-02 수용기준:
1. 임의 보호 URL에서 PIN 후보를 보내도 PBKDF2 검증이 실행되지 않는다.
2. IP와 계정/session 기준 burst 및 sustained limit이 적용된다.
3. 성공/실패/lockout audit가 secret 없이 남는다.
4. 부하 시험에서 공격 요청이 정상 인증 latency와 CPU를 threshold 이상 악화시키지 않는다.

SEC-01이 통합한 auth_policy 위에 SEC-02는 "PIN은 rate-limited login/token route에서만
수용"하는 계약을 잠는다. WS gate의 query/헤더 PIN, HTTP middleware의 legacy
X-Access-Pin 헤더/쿠키 PIN은 제거 대상이다 (query PIN은 SEC-01에서 이미 제거됨).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

# ─── 1. raw PIN 검증 표면 제거 ────────────────────────────────────────


class TestRawPinSurfaceRemoved:
    @pytest.fixture(autouse=True)
    def _pin_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """loopback anonymous 경로를 막아 PIN 표면만 순수하게 검사한다."""
        from antigravity_k.config import config

        monkeypatch.setattr(config.security, "access_pin", "configured")

    def test_middleware_rejects_pin_header_without_pbkdf2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """X-Access-Pin 헤더를 보내도 middleware에서 PBKDF2 verify_pin을 호출하지 않는다."""
        import antigravity_k.api.auth_routes as auth_routes

        calls: list[tuple[str, str]] = []

        def spy_verify(pin: str, stored: str) -> bool:
            calls.append((pin, stored))
            return False

        monkeypatch.setattr(auth_routes, "verify_pin", spy_verify)

        request = Request({"type": "http", "headers": [(b"x-access-pin", b"guessed-pin")]})
        assert auth_routes.authenticate_request(request) is False
        assert calls == [], "middleware가 raw PIN에 대해 PBKDF2 검증을 실행했다 — SEC-02 위반"

    def test_middleware_rejects_pin_cookie_without_pbkdf2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import antigravity_k.api.auth_routes as auth_routes

        calls: list[tuple[str, str]] = []

        def spy_verify(pin: str, stored: str) -> bool:
            calls.append((pin, stored))
            return False

        monkeypatch.setattr(auth_routes, "verify_pin", spy_verify)

        request = Request({"type": "http", "headers": [(b"cookie", b"ag_access_pin=guessed-pin")], "method": "GET"})
        assert auth_routes.authenticate_request(request) is False
        assert calls == [], "middleware가 쿠키 PIN에 대해 PBKDF2 검증을 실행했다 — SEC-02 위반"

    def test_ws_gate_rejects_pin_credential_without_pbkdf2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WS gate에서 PIN으로 보이는 credential(점 없는 토큰)로 PBKDF2를 돌리지 않는다."""
        from antigravity_k.config import config

        monkeypatch.setattr(config.security, "access_pin", "configured")
        import antigravity_k.api.routes.session_state as ss_mod
        from antigravity_k.api.routes import session_state

        calls: list[tuple[str, str]] = []

        def spy_verify(pin: str, stored: str) -> bool:
            calls.append((pin, stored))
            return False

        monkeypatch.setattr(session_state, "verify_pin", spy_verify, raising=False)
        monkeypatch.setattr(ss_mod, "verify_pin", spy_verify, raising=False)

        class _FakeState:
            agk_accepted = False
            auth_subject: str | None = None

        class _FakeWebSocket:
            state = _FakeState()

            async def accept(self) -> None: ...

            async def close(self, code: int, reason: str) -> None: ...

            @property
            def query_params(self) -> dict[str, str]:
                return {"pin": "guessed-pin"}

            @property
            def headers(self) -> dict[str, str]:
                # SEC-01 subprotocol 채널 — 이 테스트는 제공하지 않는다.
                return {}

        ws = _FakeWebSocket()
        closed = asyncio_run(session_state.close_unauthorized_ws(ws))
        assert closed is True, "PIN credential로 WS가 통과됐다 — SEC-02 위반"
        assert calls == [], "WS gate가 raw PIN에 대해 PBKDF2 검증을 실행했다 — SEC-02 위반"

    def test_login_route_is_the_only_pbkdf2_path(self) -> None:
        """verify_pin 호출처는 login/token 두 rate-limited route뿐이어야 한다."""
        import re
        from pathlib import Path

        hits: list[str] = []
        for path in Path("src/antigravity_k").rglob("*.py"):
            if path.name == "auth.py":  # engine/auth.py는 구현체
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(r"\bverify_pin\(", text):
                hits.append(str(path))
        allowed = {"src/antigravity_k/api/auth_routes.py"}  # login/token route (rate-limited)
        unexpected = {f for f in hits if f not in allowed}
        assert not unexpected, f"rate-limit 밖 verify_pin 호출: {sorted(unexpected)}"


# ─── 2. burst / sustained limit (IP + actor/session) ─────────────────


class TestCredentialGate:
    def test_burst_limit_blocks_before_pbkdf2_after_threshold(self) -> None:
        """burst 임계(5번째) 도달 시 lockout이 시작된다."""
        from antigravity_k.security.credential_gate import CredentialGate

        gate = CredentialGate(burst_limit=5, burst_window_sec=60.0, lockout_sec=30.0)
        decisions = [gate.record_failure(key="ip:1.2.3.4") for _ in range(5)]
        assert all(d.allowed for d in decisions[:4]), "burst 임계 이전 실패는 허용돼야 한다"
        assert not decisions[4].allowed and decisions[4].reason == "lockout"
        decision = gate.check("ip:1.2.3.4")
        assert decision.allowed is False
        assert decision.reason == "lockout"

    def test_sustained_limit_sliding_window(self) -> None:
        """sustained limit — 긴 창 누적 실패도 차단된다."""
        from antigravity_k.security.credential_gate import CredentialGate

        gate = CredentialGate(burst_limit=100, burst_window_sec=60.0, sustained_limit=20, sustained_window_sec=600.0)
        for _ in range(20):
            _ = gate.record_failure(key="ip:5.6.7.8")
        decision = gate.check("ip:5.6.7.8")
        assert decision.allowed is False

    def test_success_resets_failures(self) -> None:
        from antigravity_k.security.credential_gate import CredentialGate

        gate = CredentialGate(burst_limit=3, burst_window_sec=60.0, lockout_sec=30.0)
        for _ in range(2):
            _ = gate.record_failure(key="ip:8.8.8.8")
        gate.record_success(key="ip:8.8.8.8")
        decision = gate.check("ip:8.8.8.8")
        assert decision.allowed is True

    def test_lockout_expiry_allows_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from antigravity_k.security.credential_gate import CredentialGate

        gate = CredentialGate(burst_limit=2, burst_window_sec=60.0, lockout_sec=1.0)
        for _ in range(2):
            _ = gate.record_failure(key="ip:9.9.9.9")
        assert gate.check("ip:9.9.9.9").allowed is False
        # 시간 흐름 시뮬레이션
        real_monotonic = time.monotonic
        monkeypatch.setattr("antigravity_k.security.credential_gate.time.monotonic", lambda: real_monotonic() + 2.0)
        decision = gate.check("ip:9.9.9.9")
        assert decision.allowed is True, "lockout 만료 후 재시도가 가능해야 한다"
        assert isinstance(decision.retry_after_sec, float)

    def test_keys_are_independent(self) -> None:
        from antigravity_k.security.credential_gate import CredentialGate

        gate = CredentialGate(burst_limit=2, burst_window_sec=60.0, lockout_sec=30.0)
        for _ in range(2):
            _ = gate.record_failure(key="ip:1.1.1.1")
        assert gate.check("ip:1.1.1.1").allowed is False
        assert gate.check("ip:2.2.2.2").allowed is True, "다른 IP가 영향을 받았다"

    def test_login_enforces_gate_after_slowapi(self, auth_gate_client: TestClient) -> None:
        """gate가 실패 5회에서 lockout(403)으로 전환하고, 이후 slowapi 429가 이어진다."""
        statuses: list[int] = []
        for _ in range(8):
            resp = auth_gate_client.post("/api/auth/login", json={"pin": "wrong"})
            statuses.append(resp.status_code)
        assert statuses[4] == 403, f"5번째 실패에서 lockout 403이어야 한다: {statuses}"
        assert 429 in statuses[5:], f"lockout 이후 slowapi 429가 이어져야 한다: {statuses}"

    def test_gate_blocks_by_ip_not_affected_by_other_ip(self, auth_gate_client: TestClient) -> None:
        """실패 1회 누적 상태에서는 정상 PIN 로그인이 통과한다 (slowapi 5회 한도 내)."""
        _ = auth_gate_client.post("/api/auth/login", json={"pin": "wrong"})
        resp = auth_gate_client.post("/api/auth/login", json={"pin": "gate-pin-1234"})
        assert resp.status_code == 200, f"정상 PIN 로그인 실패: {resp.status_code}"


# ─── 3. audit — secret 없이 ──────────────────────────────────────────


class TestAuthAudit:
    def test_failures_recorded_without_secret(self, auth_gate_client: TestClient) -> None:
        from antigravity_k.security.auth_audit import get_auth_audit_events

        for _ in range(2):
            _ = auth_gate_client.post("/api/auth/login", json={"pin": "super-secret-pin-xyz"})

        events = get_auth_audit_events()
        assert len(events) >= 2
        for event in events:
            assert event["event"] in {"login_failed", "login_success", "lockout"}
            assert "remote" in event
            assert "super-secret-pin-xyz" not in json_dumps(events), "audit에 PIN secret이 남았다"
            assert "attempt" not in event or event.get("attempt") is None, "audit에 시도한 PIN이 저장됐다"

    def test_success_recorded(self, auth_gate_client: TestClient) -> None:
        from antigravity_k.security.auth_audit import get_auth_audit_events

        _ = auth_gate_client.post("/api/auth/login", json={"pin": "gate-pin-1234"})
        events = get_auth_audit_events()
        assert any(e["event"] == "login_success" for e in events)

    def test_lockout_recorded(self, auth_gate_client: TestClient) -> None:
        from antigravity_k.security.auth_audit import get_auth_audit_events

        statuses: list[int] = []
        for _ in range(8):
            resp = auth_gate_client.post("/api/auth/login", json={"pin": "wrong"})
            statuses.append(resp.status_code)
        events = get_auth_audit_events()
        assert statuses[4] == 403, f"lockout 403이 없다: {statuses}"
        assert any(e["event"] == "lockout" for e in events), f"lockout 이벤트 부재: {[e['event'] for e in events]}"

    def test_audit_event_has_no_credential_fields(self, auth_gate_client: TestClient) -> None:
        from antigravity_k.security.auth_audit import get_auth_audit_events

        _ = auth_gate_client.post("/api/auth/login", json={"pin": "whatever-pin"})
        for event in get_auth_audit_events():
            for key in event:
                assert key not in {"pin", "password", "credential", "token"}, f"audit에 credential 필드 {key}"


# ─── 4. 부하 — 공격 요청이 정상 인증 latency를 악화시키지 않는다 ────────


class TestLoadBehavior:
    def test_attack_sweep_does_not_trigger_pbkdf2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """공격 sweep(무작위 PIN) 중 gate가 PBKDF2 자체를 호출하지 않는다.

        gate는 순수 실패 카운터 — PBKDF2는 login route에서 gate 통과 후에만 실행.
        sweep 시나리오: gate에 실패를 계속 기록하면 lockout 후 카운터 입력 자체가
        차단되어 login route의 PBKDF2 호출이 임계(초기 burst)를 넘지 못한다.
        """
        from antigravity_k.security import credential_gate as cg

        gate = cg.CredentialGate(burst_limit=5, burst_window_sec=60.0, lockout_sec=30.0)
        key = "ip:10.0.0.1"
        accepted = 0
        for _ in range(50):
            decision = gate.register(key)
            if decision.allowed:
                accepted += 1  # PBKDF2가 실행될 수 있었던 횟수
            _ = gate.record_failure(key)

        # 50회 sweep 중 PBKDF2 실행 기회는 초기 burst(5) 이내로 제한된다
        assert accepted <= 5, f"lockout 없이 {accepted}회 PBKDF2 실행 허용 — 게이트 미작동"

    def test_attack_latency_stays_flat(self) -> None:
        """lockout 중 check()는 상수 시간에 가깝다 — 누적 실패 수와 무관."""
        from antigravity_k.security.credential_gate import CredentialGate

        gate = CredentialGate(burst_limit=5, burst_window_sec=60.0, lockout_sec=30.0)
        for _ in range(50):
            _ = gate.record_failure(key="ip:lat")

        start = time.perf_counter()
        for _ in range(1000):
            _ = gate.check("ip:lat")
        elapsed_locked = time.perf_counter() - start

        gate2 = CredentialGate(burst_limit=5, burst_window_sec=60.0, lockout_sec=30.0)
        gate2.record_failure(key="ip:idle")
        start = time.perf_counter()
        for _ in range(1000):
            _ = gate2.check("ip:idle")
        elapsed_clean = time.perf_counter() - start

        assert elapsed_locked < max(elapsed_clean * 5, elapsed_clean + 0.05), (
            f"lockout 상태 check가 느림: locked={elapsed_locked:.4f}s clean={elapsed_clean:.4f}s"
        )


# ─── helpers ─────────────────────────────────────────────────────────


def asyncio_run(coro: Any) -> Any:
    import asyncio

    return asyncio.run(coro)


def json_dumps(events: list[dict[str, Any]]) -> str:
    import json

    return json.dumps(events, ensure_ascii=False, default=str)


@pytest.fixture()
def auth_gate_client() -> Any:
    """전용 gate 테스트 클라이언트 — credential gate/audit/slowapi 카운터 초기화.

    slowapi limiter 상태를 초기화해 burst 테스트가 429가 아닌 403을 보도록 한다.
    """
    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.config import config
    from antigravity_k.security import auth_audit
    from antigravity_k.security.credential_gate import reset_credential_gate

    tmpdir = Path_tmp()
    orig_pin = config.security.access_pin
    orig_hash_file = config.security.pin_hash_file
    orig_secret_file = config.security.token_secret_file

    config.security.access_pin = "gate-pin-1234"
    config.security.pin_hash_file = str(tmpdir / "auth_hash")
    config.security.token_secret_file = str(tmpdir / "token_secret")

    setattr(auth_routes_mod, "_token_service", None)
    setattr(auth_routes_mod, "_pin_hash", None)
    auth_routes_mod.init_auth_state()
    reset_credential_gate()
    auth_audit.reset_auth_audit()
    _reset_slowapi(auth_routes_mod)

    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    config.security.access_pin = orig_pin
    config.security.pin_hash_file = orig_hash_file
    config.security.token_secret_file = orig_secret_file
    setattr(auth_routes_mod, "_token_service", None)
    setattr(auth_routes_mod, "_pin_hash", None)
    auth_routes_mod.init_auth_state()
    reset_credential_gate()
    auth_audit.reset_auth_audit()
    _reset_slowapi(auth_routes_mod)


def _reset_slowapi(auth_routes_mod: Any) -> None:
    """slowapi in-memory 카운터 리셋 — 테스트 간 5/minute 잔량을 분리한다."""
    limiter = getattr(auth_routes_mod, "_limiter", None)
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()


def Path_tmp() -> Any:
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp(prefix="sec02_gate_"))


def unused_helper(c: Callable[[], None]) -> None:
    _ = cast(object, c)
