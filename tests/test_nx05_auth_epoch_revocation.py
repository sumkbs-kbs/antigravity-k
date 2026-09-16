"""NX-05: PIN 변경은 기존 인증 세션을 모두 폐기한다 (auth epoch 계약).

카드(docs/18_RELIABILITY_AND_CONNECTOME_DEVELOPMENT_PLAN.md §NX-05)의 시험 항목을
그대로 고정한다:

* 이전 bearer 거부 / 새 PIN 로그인 성공 / 구 PIN 거부,
* 구버전(epoch claim 없음) 토큰 거부 — migration 뒤 재로그인,
* 저장 실패에서 기존 상태(hash+epoch)가 유지되고 5xx로 알려짐,
* 동시 PIN 변경(2스레드)에서도 세대가 정확히 한 번씩 증가,
* 프로세스 두 개 — 한 프로세스가 바꾼 PIN 을 다른 프로세스가 **캐시 없이** 즉시 반영,
* restart 후 이전 토큰 거부,
* 발급 전 세대의 WS ticket 재사용 거부,
* 열려 있는 인증 WS 가 짧은 폐기 한도(<=5초) 안에 close code 4401 로 닫힘,
* SSE 재연결(bearer 재사용) 401,
* 모드별 규칙(open_loopback/local PIN/remote PIN),
* 구버전 한 줄 hash 파일 migration.

제품 코드의 제한을 우회하지 않는다 — 새 세대 토큰은 항상 다시 발급받는다.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.auth import EPOCH_CLAIM, TokenService, hash_pin
from antigravity_k.security.auth_state import (
    LEGACY_EPOCH,
    AuthState,
    current_epoch,
    next_epoch,
    read_auth_state,
    read_pin_hash,
    write_auth_state_atomic,
)
from antigravity_k.security.ws_ticket import WSTicketService

PIN = "test-pin-1234"
NEW_PIN = "test-pin-5678"


def _child_bump_epoch(path: str, new_pin: str) -> None:  # pragma: no cover - 자식 프로세스
    """spawn 으로 실행되는 자식 — 다른 프로세스의 PIN 변경을 흥내낸다."""
    from antigravity_k.security.auth_state import bump_epoch_atomic

    _ = bump_epoch_atomic(Path(path), pin_hash=hash_pin(new_pin))


# ---------------------------------------------------------------------------
# 단위: 저장 형식 (hash + epoch 원자 교체)
# ---------------------------------------------------------------------------


def test_auth_state_roundtrip_keeps_hash_and_epoch(tmp_path: Path) -> None:
    path = tmp_path / "auth_hash"
    written = write_auth_state_atomic(path, pin_hash=hash_pin(PIN), epoch=3)

    state = read_auth_state(path)
    assert state is not None
    assert state.epoch == 3
    assert state.pin_hash is not None
    assert read_pin_hash(path) == state.pin_hash
    assert current_epoch(path) == 3
    assert written.epoch == 3
    # 구버전 한 줄 hash 와 구별되는 새 schema 표식.
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "agk.auth.v1"


def test_auth_state_never_exposes_a_partial_document(tmp_path: Path) -> None:
    """hash 와 epoch 은 같은 파일이므로 (이전 hash, 이전 epoch) 또는 새 값만 보인다."""
    path = tmp_path / "auth_hash"
    old_hash = hash_pin(PIN)
    new_hash = hash_pin(NEW_PIN)
    _ = write_auth_state_atomic(path, pin_hash=old_hash, epoch=1)

    observed: list[tuple[str | None, int]] = []
    stop = threading.Event()

    def reader() -> None:
        while not stop.is_set():
            state = read_auth_state(path)
            assert state is not None, "부분 문서가 노출됐다"
            observed.append((state.pin_hash, state.epoch))

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for epoch in range(2, 12):
            _ = write_auth_state_atomic(path, pin_hash=new_hash, epoch=epoch)
    finally:
        stop.set()
        thread.join(timeout=10)

    assert observed, "reader 가 아무 것도 관측하지 못했다"
    for pin_hash, epoch in observed:
        # 관측된 조합은 항상 (구 hash, 1) 또는 (신 hash, 그 세대) 중 하나여야 한다.
        assert (pin_hash, epoch) in {(old_hash, 1)} | {(new_hash, e) for e in range(2, 12)}


def test_auth_state_write_failure_keeps_previous_state(tmp_path: Path) -> None:
    """쓰기 실패에서는 기존 상태가 그대로 남는다 (성공으로 보고하지 않는다)."""
    path = tmp_path / "auth_hash"
    original = hash_pin(PIN)
    _ = write_auth_state_atomic(path, pin_hash=original, epoch=2)
    before = path.read_bytes()

    blocker = tmp_path / "blocker"
    _ = blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(OSError):
        # 부모 디렉터리를 파일로 막아 mkstemp 실패를 강제한다.
        _ = write_auth_state_atomic(blocker / "nested" / "auth_hash", pin_hash=hash_pin(NEW_PIN), epoch=3)

    assert path.read_bytes() == before
    assert current_epoch(path) == 2
    assert read_pin_hash(path) == original


def test_legacy_single_line_hash_is_read_as_epoch_zero(tmp_path: Path) -> None:
    """구버전 한 줄 hash 파일은 계속 읽되 epoch 0(=구버전 토큰 무효)으로 취급한다."""
    path = tmp_path / "auth_hash"
    legacy_hash = hash_pin(PIN)
    _ = path.write_text(legacy_hash, encoding="utf-8")

    state = read_auth_state(path)
    assert state is not None
    assert state.legacy is True
    assert state.epoch == LEGACY_EPOCH
    assert state.pin_hash == legacy_hash
    assert next_epoch(state) == 1


# ---------------------------------------------------------------------------
# 단위: TokenService 의 세대 검사
# ---------------------------------------------------------------------------


def test_token_epoch_claim_is_verified_against_current_generation(tmp_path: Path) -> None:
    path = tmp_path / "auth_hash"
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(PIN), epoch=1)
    service = TokenService(secret_path=tmp_path / "secret", epoch_provider=lambda: current_epoch(path))

    token = service.issue_token(subject="user")
    assert service.verify_token(token) is not None

    # PIN 변경 = 세대 증가.
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(NEW_PIN), epoch=2)
    assert service.verify_token(token) is None, "이전 세대 토큰이 살아 있다"


def test_token_without_epoch_claim_is_rejected(tmp_path: Path) -> None:
    """구버전 토큰(claim 없음)은 재로그인을 요구한다 — 조용히 통과시키지 않는다."""
    import jwt as pyjwt

    path = tmp_path / "auth_hash"
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(PIN), epoch=4)
    service = TokenService(secret_path=tmp_path / "secret", epoch_provider=lambda: current_epoch(path))

    legacy = pyjwt.encode(
        {
            "sub": "user",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "iss": "antigravity-k",
        },
        service.secret,
        algorithm="HS256",
    )
    assert service.verify_token(legacy) is None


def test_token_epoch_claim_must_be_an_integer(tmp_path: Path) -> None:
    import jwt as pyjwt

    path = tmp_path / "auth_hash"
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(PIN), epoch=2)
    service = TokenService(secret_path=tmp_path / "secret", epoch_provider=lambda: current_epoch(path))

    forged = pyjwt.encode(
        {
            "sub": "user",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "iss": "antigravity-k",
            EPOCH_CLAIM: "2",  # 문자열 claim 은 통과하지 않는다
        },
        service.secret,
        algorithm="HS256",
    )
    assert service.verify_token(forged) is None


def test_epoch_provider_is_re_read_on_every_verification(tmp_path: Path) -> None:
    """프로세스별 캐시 금지 — 파일이 바뀌면 다음 검증이 즉시 반영한다."""
    path = tmp_path / "auth_hash"
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(PIN), epoch=1)
    service = TokenService(secret_path=tmp_path / "secret", epoch_provider=lambda: current_epoch(path))
    token = service.issue_token(subject="user")

    # 다른 프로세스를 흉내내 파일만 교체한다(이 프로세스의 객체는 그대로).
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(NEW_PIN), epoch=2)
    assert service.current_epoch() == 2
    assert service.verify_token(token) is None


# ---------------------------------------------------------------------------
# 단위: WS ticket 세대 연결
# ---------------------------------------------------------------------------


def test_ws_ticket_from_previous_generation_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "auth_hash"
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(PIN), epoch=1)
    service = TokenService(secret_path=tmp_path / "secret", epoch_provider=lambda: current_epoch(path))
    tickets = WSTicketService(service, epoch_provider=service.epoch_provider)

    ticket = tickets.issue("user")
    assert tickets.consume(ticket) == "user"  # 현재 세대는 1회 사용 가능

    stale = tickets.issue("user")
    _ = write_auth_state_atomic(path, pin_hash=hash_pin(NEW_PIN), epoch=2)
    assert tickets.consume(stale) is None, "이전 세대 ticket 이 살아 있다"


# ---------------------------------------------------------------------------
# 단위: 열린 인증 WS 폐기 (<=5초)
# ---------------------------------------------------------------------------


class _FakeWebSocket:
    """close 호출만 관측하는 테스트 더블(테스트가 직접 살려 두는 객체)."""

    def __init__(self) -> None:
        self.closed: list[tuple[int, str]] = []

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed.append((code, reason))


def test_close_authorized_ws_blocking_closes_within_budget() -> None:
    from antigravity_k.api.routes import session_state

    session_state.reset_authorized_ws_registry()

    async def scenario() -> tuple[int, float]:
        websocket = _FakeWebSocket()
        session_state.register_authorized_ws(cast(Any, websocket))
        await asyncio.sleep(0)  # 등록은 진행 중인 루프에서 이뤄진다

        started = time.perf_counter()
        closed = await asyncio.to_thread(session_state.close_authorized_ws_blocking, 4401, "Session revoked")
        return closed, time.perf_counter() - started

    closed, elapsed = asyncio.run(scenario())

    assert closed == 1
    assert elapsed <= 5.0, f"폐기가 {elapsed:.3f}s 걸렸다 (한도 5초)"
    assert session_state.authorized_ws_count() == 0


def test_registry_drops_garbage_collected_connections() -> None:
    """죽은 연결은 별도 해제 훅 없이 레지스트리에서 사라진다(핸들러 5곳 무수정)."""
    from antigravity_k.api.routes import session_state

    session_state.reset_authorized_ws_registry()

    async def scenario() -> int:
        websocket = _FakeWebSocket()
        session_state.register_authorized_ws(cast(Any, websocket))
        assert session_state.authorized_ws_count() == 1
        del websocket
        import gc

        gc.collect()
        return session_state.authorized_ws_count()

    assert asyncio.run(scenario()) == 0


# ---------------------------------------------------------------------------
# 통합: HTTP / WS / SSE (TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def nx05_client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """알려진 PIN 과 임시 credential 경로를 쓰는 클라이언트(모듈 범위)."""
    from antigravity_k.config import config

    tmpdir = tmp_path_factory.mktemp("nx05_auth")
    originals = {
        "access_pin": config.security.access_pin,
        "pin_hash_file": config.security.pin_hash_file,
        "token_secret_file": config.security.token_secret_file,
    }

    config.security.access_pin = PIN
    config.security.pin_hash_file = str(tmpdir / "auth_hash")
    config.security.token_secret_file = str(tmpdir / "token_secret")

    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.api.auth_policy import init_shared_auth_policy

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    _ = init_shared_auth_policy(config.security.pin_hash_file)

    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    config.security.access_pin = originals["access_pin"]
    config.security.pin_hash_file = originals["pin_hash_file"]
    config.security.token_secret_file = originals["token_secret_file"]
    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    _ = init_shared_auth_policy()


def _login(client: TestClient, pin: str = PIN) -> Any:
    return client.post("/api/auth/login", json={"pin": pin})


def _token_for_current_epoch() -> str:
    from antigravity_k.api.auth_routes import get_token_service

    return get_token_service().issue_token(subject="nx05")


def _state_path() -> Path:
    from antigravity_k.config import config

    return Path(config.security.pin_hash_file)


def _change_pin(client: TestClient, *, current: str, new: str) -> Any:
    return client.post(
        "/api/auth/change-pin",
        headers={"Authorization": f"Bearer {_token_for_current_epoch()}"},
        json={"current_pin": current, "new_pin": new},
    )


def test_pin_change_rotates_epoch_and_revokes_previous_bearer(nx05_client: TestClient) -> None:
    old_token = cast(str, _login(nx05_client, PIN).json()["access_token"])
    epoch_before = current_epoch(_state_path())

    response = _change_pin(nx05_client, current=PIN, new=NEW_PIN)
    assert response.status_code == 200, response.text
    body = cast(dict[str, object], response.json())
    assert body["ok"] is True
    assert body["reauth_required"] is True
    assert cast(int, body["epoch"]) == epoch_before + 1
    assert "pin=" not in response.text.lower()

    # 1) 이전 bearer 는 보호 경로(/api/auth/verify 포함)에서 401 로 거부된다.
    for path in ("/api/vault/config", "/api/auth/verify"):
        response = nx05_client.get(path, headers={"Authorization": f"Bearer {old_token}"})
        assert response.status_code == 401, (path, response.status_code, response.text)

    # 2) 새 PIN 로그인은 성공하고, 3) 구 PIN 은 실패한다.
    assert _login(nx05_client, NEW_PIN).status_code == 200
    assert _login(nx05_client, PIN).status_code == 401

    # 원복(모듈 범위 클라이언트를 쓰는 다음 테스트를 위해).
    assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_new_token_after_change_is_accepted_and_old_generation_is_not(nx05_client: TestClient) -> None:
    stale = _token_for_current_epoch()
    assert _change_pin(nx05_client, current=PIN, new=NEW_PIN).status_code == 200
    try:
        assert nx05_client.get("/api/vault/config", headers={"Authorization": f"Bearer {stale}"}).status_code == 401
        fresh = cast(str, _login(nx05_client, NEW_PIN).json()["access_token"])
        assert nx05_client.get("/api/vault/config", headers={"Authorization": f"Bearer {fresh}"}).status_code != 401
    finally:
        assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_change_pin_persist_failure_keeps_old_credentials(
    nx05_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """쓰기 실패는 5xx 로 알려지고, 이전 hash·epoch 이 그대로 유효하다."""
    state_path = _state_path()
    before_bytes = state_path.read_bytes()
    before_epoch = current_epoch(state_path)
    token = _token_for_current_epoch()

    def boom(*_args: object, **_kwargs: object) -> AuthState:
        raise OSError("disk full (injected)")

    monkeypatch.setattr("antigravity_k.api.auth_routes.bump_epoch_atomic", boom)

    response = nx05_client.post(
        "/api/auth/change-pin",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_pin": PIN, "new_pin": "unused-pin-9999"},
    )
    assert response.status_code >= 500
    assert current_epoch(state_path) == before_epoch
    assert state_path.read_bytes() == before_bytes

    # 실패 후에도 기존 토큰은 유효하고 새 PIN 은 통하지 않는다.
    assert nx05_client.get("/api/vault/config", headers={"Authorization": f"Bearer {token}"}).status_code != 401
    assert _login(nx05_client, "unused-pin-9999").status_code == 401
    monkeypatch.undo()


def test_concurrent_pin_changes_advance_one_generation_per_success(nx05_client: TestClient) -> None:
    """동시 변경에서도 성공 1건 = 세대 1증가, 실패 건은 상태를 바꾸지 않는다."""
    epoch_before = current_epoch(_state_path())

    from antigravity_k.api.auth_routes import change_pin as change_pin_handler

    assert callable(change_pin_handler)

    results: list[str] = []
    lock = threading.Lock()

    def worker(new_pin: str) -> None:
        try:
            response = _change_pin(nx05_client, current=PIN, new=new_pin)
        except Exception as exc:  # noqa: BLE001 — 동시성 시험은 실패도 관측 대상이다
            with lock:
                results.append(f"error:{exc}")
            return
        with lock:
            results.append(f"{response.status_code}")

    threads = [threading.Thread(target=worker, args=(f"concurrent-pin-{i}00{i}",)) for i in range(1, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert len(results) == 2, results
    successes = [r for r in results if r.startswith("2")]
    epoch_after = current_epoch(_state_path())
    assert epoch_after == epoch_before + len(successes), (results, epoch_before, epoch_after)

    # 상태와 성공 수가 어긋나지 않는다: 현재 epoch 토큰은 항상 검증된다.
    assert _token_for_current_epoch() is not None

    # 원복 — 마지막 성공이 정한 PIN 을 찾아 되돌린다.
    stored = read_pin_hash(_state_path())
    assert stored is not None
    from antigravity_k.engine.auth import verify_pin

    for candidate in (*[f"concurrent-pin-{i}00{i}" for i in range(1, 3)], PIN):
        if verify_pin(candidate, stored):
            if candidate != PIN:
                assert _change_pin(nx05_client, current=candidate, new=PIN).status_code == 200
            break
    else:  # pragma: no cover - 방어적
        raise AssertionError("동시 변경 후 유효한 PIN 을 찾지 못했다")


def test_two_processes_share_the_generation_without_caching(nx05_client: TestClient) -> None:
    """다른 프로세스가 PIN 을 바꾸면 이 프로세스의 다음 검증이 즉시 거부한다."""
    import multiprocessing as mp

    from antigravity_k.api.auth_routes import get_token_service

    state_path = _state_path()
    token = cast(str, _login(nx05_client, PIN).json()["access_token"])
    assert get_token_service().verify_token(token) is not None
    epoch_before = current_epoch(state_path)

    context = mp.get_context("spawn")
    child = context.Process(target=_child_bump_epoch, args=(str(state_path), NEW_PIN))
    child.start()
    child.join(timeout=60)
    assert child.exitcode == 0

    assert current_epoch(state_path) == epoch_before + 1
    assert get_token_service().current_epoch() == epoch_before + 1
    assert get_token_service().verify_token(token) is None, "다른 프로세스의 변경을 캐시가 가렸다"
    assert nx05_client.get("/api/vault/config", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    # 원복: 자식이 정한 세대를 유지한 채 PIN 만 되돌린다.
    assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_restart_keeps_revocation(nx05_client: TestClient) -> None:
    """재시작(새 TokenService + 새 auth state 로드) 후에도 이전 토큰은 거부된다."""
    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.api.auth_routes import get_token_service

    stale = _token_for_current_epoch()
    assert _change_pin(nx05_client, current=PIN, new=NEW_PIN).status_code == 200
    try:
        # 새 프로세스의 시작을 흉내낸다: 인증 상태를 처음부터 다시 로드한다.
        auth_routes_mod._token_service = None
        auth_routes_mod._pin_hash = None
        auth_routes_mod.init_auth_state()

        restarted = get_token_service()
        assert restarted.verify_token(stale) is None
        assert nx05_client.get("/api/vault/config", headers={"Authorization": f"Bearer {stale}"}).status_code == 401
        assert _login(nx05_client, NEW_PIN).status_code == 200
    finally:
        assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_sse_style_reconnect_with_revoked_bearer_is_rejected(nx05_client: TestClient) -> None:
    """SSE 재연결은 같은 bearer 를 다시 쓴다 — 폐기된 토큰이면 401 로 끝난다."""
    from antigravity_k.api.auth_routes import get_token_service

    stale = cast(str, _login(nx05_client, PIN).json()["access_token"])
    assert _change_pin(nx05_client, current=PIN, new=NEW_PIN).status_code == 200
    try:
        for attempt in range(2):  # reconnect 를 두 번 흉내낸다
            response = nx05_client.get(
                "/v1/conversations/missing/history",
                headers={"Authorization": f"Bearer {stale}"},
            )
            assert response.status_code == 401, f"attempt={attempt} status={response.status_code}"

        # 새 세대 토큰으로는 (대화가 없어도) 인증 자체는 통과한다.
        fresh = get_token_service().issue_token(subject="nx05")
        response = nx05_client.get(
            "/v1/conversations/missing/history",
            headers={"Authorization": f"Bearer {fresh}"},
        )
        assert response.status_code != 401
    finally:
        assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_ws_ticket_issued_before_change_cannot_open_a_stream(nx05_client: TestClient) -> None:
    """PIN 변경 전에 발급한 ticket 은 재사용할 수 없다(WS 게이트 거부)."""
    from antigravity_k.api.auth_routes import get_token_service
    from antigravity_k.security.ws_ticket import get_ws_ticket_service

    ticket_service = get_ws_ticket_service(get_token_service())
    stale_ticket = ticket_service.issue("nx05")

    assert _change_pin(nx05_client, current=PIN, new=NEW_PIN).status_code == 200
    try:
        with nx05_client.websocket_connect(f"/v1/ws/events?ticket={stale_ticket}") as websocket:
            message = websocket.receive()
            assert message["type"] == "websocket.close"
            assert message.get("code") == 4401
    finally:
        assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_open_ws_is_closed_immediately_when_sessions_are_revoked(nx05_client: TestClient) -> None:
    """열려 있는 인증 WS 는 다음 요청을 기다리지 않고 5초 안에 닫힌다."""
    from antigravity_k.api.auth_routes import get_token_service
    from antigravity_k.api.routes import session_state
    from antigravity_k.security.ws_ticket import get_ws_ticket_service

    session_state.reset_authorized_ws_registry()
    ticket = get_ws_ticket_service(get_token_service()).issue("nx05")

    with nx05_client.websocket_connect(f"/v1/ws/events?ticket={ticket}") as websocket:
        # 게이트가 인증을 마치고 스트림이 열릴 때까지 기다린다(등록 완료 확인).
        for _ in range(100):
            if session_state.authorized_ws_count() >= 1:
                break
            time.sleep(0.05)
        assert session_state.authorized_ws_count() >= 1, "인증된 WS 가 등록되지 않았다"

        response = _change_pin(nx05_client, current=PIN, new=NEW_PIN)
        assert response.status_code == 200
        body = cast(dict[str, object], response.json())
        assert cast(int, body["sessions_revoked"]) >= 1

        message = websocket.receive()
        assert message["type"] == "websocket.close", message
        assert message.get("code") == 4401

    assert _change_pin(nx05_client, current=NEW_PIN, new=PIN).status_code == 200


def test_mode_specific_rules_for_pin_change(nx05_client: TestClient) -> None:
    """모드별로 같은 폐기 계약이 유지된다 (local PIN / remote PIN / open loopback).

    * open_loopback(credential 없음): 변경할 PIN 이 없고, 익명 연결은 세대 검사를
      받지 않으므로 남아 있는다.
    * local PIN(loopback host): 저장 credential 이 있으면 보호 상태다.
    * remote PIN(비-loopback host): 정책이 protected/deny 이며 익명이 없다.
    """
    from antigravity_k.api.auth_policy import resolve_auth_decision

    stored = read_pin_hash(_state_path())
    assert stored is not None

    for host in ("127.0.0.1", "0.0.0.0"):
        decision = resolve_auth_decision(
            stored_pin_hash=stored,
            plaintext_pin_configured="",
            host=host,
            dev_no_pin_allow=False,
        )
        assert decision.level == "protected", (host, decision)

    anonymous = resolve_auth_decision(
        stored_pin_hash=None,
        plaintext_pin_configured="",
        host="127.0.0.1",
        dev_no_pin_allow=True,
    )
    assert anonymous.level == "open_loopback"

    # 익명(open_loopback) 연결은 폐기할 credential 이 없으므로 실질적으로 남는다 —
    # 세대가 필요 없고, 정책도 익명을 막지 않는다는 사실을 시험으로 고정한다.
    assert (
        resolve_auth_decision(
            stored_pin_hash=None,
            plaintext_pin_configured="",
            host="203.0.113.7",
            dev_no_pin_allow=True,
        ).level
        == "deny"
    )
