"""NX-05 잔여: **이미 열려 있는** SSE 스트림은 PIN 변경(세대 증가)으로 닫힌다.

NX-05 는 "새 요청은 401" 과 "열린 WS 는 4401 로 닫힘"까지 고정했지만, 열린 SSE 응답을
서버가 닫는 경로는 없었다(그래서 그때 이 범위를 DONE 으로 주장하지 않았다). 이 시험이
그 계약을 고정한다:

* 열린 SSE 는 세대가 바뀌면 ``session.revoked`` 프레임을 받고 **끝난다**(유휴 스트림도 —
  청크가 오지 않아도 검사는 돈다).
* 폐기 지연은 검사 주기 안쪽이다(실측값을 함께 남긴다).
* 유효한 자격 증명으로 열린 스트림은 닫히지 않는다(오탐 0).
* 익명(`open_loopback`, bearer 없음) 연결은 폐기 대상이 아니다 — 무효화할 세대가 없다.
* SSE 가 아닌 응답은 미들웨어가 건드리지 않는다.
* 실제 `app`(server.py)에 미들웨어가 **배선돼 있다** — 제품 경로로 확인한다.

**시험대 주의(실측):** `TestClient` 는 응답을 **다 버퍼링한 뒤** 돌려준다(`client.stream(...)`
으로 받아도 `iter_lines()` 는 앱이 끝난 다음에 진행된다). 그래서 "읽는 중에 세대를 바꾼다"를
그 자리에서 관측할 수 없다 — 대신 **세대를 바꾸는 스레드를 스트림보다 먼저 띄우고**, 끊긴 결과를
본문의 **끝까지 오지 않은 프레임**으로 확인한다. 실제 연결을 점진적으로 읽는 관측은
`docs/qa/2026-09-16-followup/nx05/repro_sse_live_revocation.py`(uvicorn 실서버)가 맡는다.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from antigravity_k.api.sse_revocation import (
    CHECK_INTERVAL_ENV,
    DEFAULT_CHECK_INTERVAL_SECONDS,
    REVOCATION_EVENT,
    SSERevocationMiddleware,
    check_interval_seconds,
    guard_sse_stream,
)
from antigravity_k.engine.auth import hash_pin
from antigravity_k.security.auth_state import bump_epoch_atomic, current_epoch

PIN = "sse-pin-1234"
NEW_PIN = "sse-pin-5678"
# 시험에서 기본 1초를 기다리지 않는다 — 계약은 "주기 안쪽"이므로 주기를 줄여 확인한다.
TEST_INTERVAL = 0.2


# ---------------------------------------------------------------------------
# 시험대: SSE 만 있는 작은 앱 + 실제 미들웨어
# ---------------------------------------------------------------------------


def _build_app(*, frame_count: int = 50, delay: float = 0.05) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SSERevocationMiddleware)

    @app.get("/events")
    async def events() -> StreamingResponse:  # pragma: no cover - 라우트 본문은 프레임워크가 호출
        async def generate() -> AsyncIterator[str]:
            for index in range(frame_count):
                yield f"data: {json.dumps({'i': index})}\n\n"
                await asyncio.sleep(delay)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/idle")
    async def idle() -> StreamingResponse:
        """프레임을 거의 만들지 않는 스트림 — 유휴 상태에서도 폐기가 관측되는지 본다."""

        async def generate() -> AsyncIterator[str]:
            yield "data: first\n\n"
            await asyncio.sleep(30)
            yield "data: never\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/json")
    async def json_route() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture()
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """알려진 PIN 으로 credential 을 구성하고 세대 저장 경로를 돌려준다.

    토큰 서비스/공유 정책은 프로세스 전역이므로 원래 상태로 되돌린다.
    """
    from antigravity_k.config import config

    state_path = tmp_path / "auth_hash"
    originals = {
        "access_pin": config.security.access_pin,
        "pin_hash_file": config.security.pin_hash_file,
        "token_secret_file": config.security.token_secret_file,
    }
    monkeypatch.setenv(CHECK_INTERVAL_ENV, str(TEST_INTERVAL))

    config.security.access_pin = PIN
    config.security.pin_hash_file = str(state_path)
    config.security.token_secret_file = str(tmp_path / "token_secret")

    import antigravity_k.api.auth_routes as auth_routes_mod
    from antigravity_k.api.auth_policy import init_shared_auth_policy

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    _ = init_shared_auth_policy(config.security.pin_hash_file)

    try:
        yield state_path
    finally:
        config.security.access_pin = originals["access_pin"]
        config.security.pin_hash_file = originals["pin_hash_file"]
        config.security.token_secret_file = originals["token_secret_file"]
        auth_routes_mod._token_service = None
        auth_routes_mod._pin_hash = None
        auth_routes_mod.init_auth_state()
        _ = init_shared_auth_policy()


def _token() -> str:
    from antigravity_k.api.auth_routes import get_token_service

    return cast(str, get_token_service().issue_token(subject="nx05-sse"))


def _bump_later(state_path: Path, *, delay: float) -> threading.Thread:
    """다른 프로세스/요청의 PIN 변경을 흉내낸다(저장 계층에서 세대 +1).

    PIN 변경 **엔드포인트**가 이 파일을 원자 교체한다는 사실은
    `tests/test_nx05_auth_epoch_revocation.py::test_pin_change_rotates_epoch_and_revokes_previous_bearer`
    가 이미 고정한다 — 여기서는 스트림 쪽 계약만 본다.
    """
    epoch_before = current_epoch(state_path)

    def run() -> None:
        time.sleep(delay)
        _ = bump_epoch_atomic(state_path, pin_hash=hash_pin(NEW_PIN))
        assert current_epoch(state_path) == epoch_before + 1

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# 계약: 열린 스트림은 세대가 바뀌면 닫힌다
# ---------------------------------------------------------------------------


def test_open_stream_ends_with_revocation_frame_after_epoch_change(auth_env: Path) -> None:
    """열린 SSE 는 `session.revoked` 를 받고 **끝난다** (남은 프레임이 오지 않는다)."""
    client = TestClient(_build_app(frame_count=50, delay=0.05))
    token = _token()
    thread = _bump_later(auth_env, delay=0.3)  # 스트림보다 먼저 띄운다(TestClient 는 버퍼링한다)

    started = time.monotonic()
    with client.stream("GET", "/events", headers={"Authorization": f"Bearer {token}"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode()
    elapsed = time.monotonic() - started
    thread.join(timeout=5)

    assert REVOCATION_EVENT in body, body
    payload_line = next(line for line in body.splitlines() if line.startswith("data:") and "revoked" in line)
    payload = json.loads(payload_line.removeprefix("data:").strip())
    assert payload["type"] == REVOCATION_EVENT
    assert payload["reason"] == "auth_epoch_changed"
    # 끊겼다: 첫 프레임은 받았지만 전체(50개)를 받지 못했고, 마지막 프레임도 오지 않았다.
    assert '"i": 0' in body, body
    assert '"i": 49' not in body, body
    assert body.index(REVOCATION_EVENT) > body.index('"i": 0')
    # 폐기 0.3s + 검사 주기(0.2s) 안쪽 — 기본 주기 1s 에서도 5초 예산 안이다.
    assert elapsed < 5.0, f"stream took {elapsed:.2f}s"

    # 같은 세대 변화는 HTTP 경로도 본다(이 시험대에는 인증 미들웨어가 없다 — 미들웨어 단독 계약).
    from antigravity_k.api.auth_routes import get_token_service

    assert get_token_service().verify_token(token) is None


def test_idle_stream_is_closed_without_waiting_for_a_chunk(auth_env: Path) -> None:
    """청크가 오지 않는 유휴 스트림도 폐기된다 — 검사가 청크 도착에 묶여 있으면 안 된다.

    내부 제너레이터는 폐기 뒤 30초를 더 자려고 한다. 본문이 **폐기 프레임 하나뿐**이고 전체
    시간이 5초 안이라는 것이 "대기를 기다리지 않고 끊었다"의 증거다.
    """
    client = TestClient(_build_app())
    token = _token()
    thread = _bump_later(auth_env, delay=0.1)

    started = time.monotonic()
    with client.stream("GET", "/idle", headers={"Authorization": f"Bearer {token}"}) as response:
        body = response.read().decode()
    elapsed = time.monotonic() - started
    thread.join(timeout=5)

    assert "never" not in body, body
    assert REVOCATION_EVENT in body, body
    assert elapsed < 5.0, f"idle revocation took {elapsed:.2f}s"


def test_valid_stream_is_not_revoked(auth_env: Path) -> None:
    """오탐 0: 세대가 그대로면 스트림은 닫히지 않고 정상 종료한다."""
    client = TestClient(_build_app(frame_count=4, delay=0.01))
    token = _token()

    with client.stream("GET", "/events", headers={"Authorization": f"Bearer {token}"}) as response:
        body = response.read().decode()

    assert REVOCATION_EVENT not in body
    assert '"i": 0' in body and '"i": 3' in body


def test_anonymous_stream_has_no_generation_to_revoke(auth_env: Path) -> None:
    """익명(open_loopback) 연결은 폐기 대상이 아니다 — 무효화할 세대가 없다(NX-05 정책)."""
    client = TestClient(_build_app(frame_count=6, delay=0.02))
    thread = _bump_later(auth_env, delay=0.05)

    with client.stream("GET", "/events") as response:  # Authorization 헤더 없음
        body = response.read().decode()

    thread.join(timeout=5)
    assert REVOCATION_EVENT not in body
    assert '"i": 5' in body


def test_non_sse_response_is_untouched(auth_env: Path) -> None:
    """미들웨어는 `text/event-stream` 만 감싼다."""
    client = TestClient(_build_app())
    assert client.get("/json").json() == {"ok": True}


def test_guard_closes_stream_when_it_starts_already_revoked(auth_env: Path) -> None:
    """이미 폐기된 자격 증명으로 열린 스트림은 **첫 청크를 내보내지 않는다**."""
    token = _token()
    _ = bump_epoch_atomic(auth_env, pin_hash=hash_pin(NEW_PIN))

    async def scenario() -> list[str]:
        from starlette.requests import Request

        emitted: list[str] = []

        async def inner() -> AsyncIterator[str]:
            emitted.append("raw-frame")
            yield "data: leaked\n\n"

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/events",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
            }
        )
        frames: list[str] = []
        async for frame in guard_sse_stream(inner(), request, interval=0.05):
            frames.append(str(frame))
        assert emitted == [], "폐기된 스트림이 원본 프레임을 끌어왔다"
        return frames

    frames = asyncio.run(scenario())
    assert len(frames) == 1
    assert REVOCATION_EVENT in frames[0]


def test_invalid_check_interval_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """잘못된 설정은 기본값으로 돌리고 조용히 이상 동작하지 않는다."""
    monkeypatch.delenv(CHECK_INTERVAL_ENV, raising=False)
    assert check_interval_seconds() == DEFAULT_CHECK_INTERVAL_SECONDS
    for bad in ("", "   ", "abc", "0", "-1"):
        monkeypatch.setenv(CHECK_INTERVAL_ENV, bad)
        assert check_interval_seconds() == DEFAULT_CHECK_INTERVAL_SECONDS
    monkeypatch.setenv(CHECK_INTERVAL_ENV, "0.25")
    assert check_interval_seconds() == 0.25


def test_middleware_is_wired_into_the_real_app() -> None:
    """제품 app 에 배선돼 있는가 — 시험대에만 있는 미들웨어는 제품 계약이 아니다."""
    from antigravity_k.api.server import app

    assert any(getattr(m.cls, "__name__", "") == "SSERevocationMiddleware" for m in app.user_middleware)
    # 인증 미들웨어보다 **안쪽**이어야 라우트의 StreamingResponse 를 직접 감싼다.
    names = [getattr(m.cls, "__name__", "") for m in app.user_middleware]
    assert names.index("SSERevocationMiddleware") > names.index("BaseHTTPMiddleware")


def test_real_app_stream_is_revoked_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """실제 app + 실제 인증 미들웨어로: task 이벤트 SSE 가 세대 변경으로 닫힌다."""
    from antigravity_k.config import config

    state_path = tmp_path / "auth_hash"
    originals = {
        "access_pin": config.security.access_pin,
        "pin_hash_file": config.security.pin_hash_file,
        "token_secret_file": config.security.token_secret_file,
    }
    monkeypatch.setenv(CHECK_INTERVAL_ENV, str(TEST_INTERVAL))
    config.security.access_pin = PIN
    config.security.pin_hash_file = str(state_path)
    config.security.token_secret_file = str(tmp_path / "token_secret")

    import antigravity_k.api.auth_routes as auth_routes_mod
    import antigravity_k.api.routes.task_api as task_api
    from antigravity_k.api.auth_policy import init_shared_auth_policy

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()
    _ = init_shared_auth_policy(config.security.pin_hash_file)

    login = None
    try:
        from antigravity_k.api.server import app

        class _IdleRuntime:
            """이벤트가 없고 상태가 종료가 아닌 task — 스트림이 유휴로 남는다."""

            def get_task_status(self, task_id: str, owner_subject: str | None = None) -> dict[str, object]:
                return {"task_id": task_id, "prompt": "idle", "status": "running", "output": ""}

            def list_task_events(
                self, task_id: str, after_sequence: int, limit: int, owner_subject: str | None = None
            ) -> list[dict[str, object]]:
                return []

        monkeypatch.setattr(task_api, "get_agent_runtime", lambda: _IdleRuntime())

        with TestClient(app, raise_server_exceptions=False) as client:
            login = client.post("/api/auth/login", json={"pin": PIN})
            assert login.status_code == 200, login.text
            bearer = {"Authorization": f"Bearer {login.json()['access_token']}"}

            thread = _bump_later(state_path, delay=0.3)
            started = time.monotonic()
            with client.stream("GET", "/api/tasks/task-idle/events/stream", headers=bearer) as response:
                assert response.status_code == 200, response.text
                body = response.read().decode()
            elapsed = time.monotonic() - started
            thread.join(timeout=5)

            assert REVOCATION_EVENT in body, body
            assert elapsed < 6.0, f"revocation took {elapsed:.2f}s"

            # 폐기 뒤 새 요청은 401 — 스트림과 HTTP 가 같은 세대를 본다.
            after = client.get("/api/tasks/task-idle/events/stream", headers=bearer)
            assert after.status_code == 401, after.text
    finally:
        config.security.access_pin = originals["access_pin"]
        config.security.pin_hash_file = originals["pin_hash_file"]
        config.security.token_secret_file = originals["token_secret_file"]
        auth_routes_mod._token_service = None
        auth_routes_mod._pin_hash = None
        auth_routes_mod.init_auth_state()
        _ = init_shared_auth_policy()


def test_revocation_increments_the_operational_counter(auth_env: Path) -> None:
    """폐기는 로그만이 아니라 **집계 가능한 metric** 으로 남는다."""
    from antigravity_k.engine.operational_metrics import snapshot_domain_counters

    before = snapshot_domain_counters().get("ssak_auth_events_total", {}).get("stream_revoked", 0.0)
    client = TestClient(_build_app())
    token = _token()
    thread = _bump_later(auth_env, delay=0.1)

    with client.stream("GET", "/events", headers={"Authorization": f"Bearer {token}"}) as response:
        body = response.read().decode()
    thread.join(timeout=5)
    assert REVOCATION_EVENT in body, body

    after = snapshot_domain_counters().get("ssak_auth_events_total", {}).get("stream_revoked", 0.0)
    assert after == before + 1
