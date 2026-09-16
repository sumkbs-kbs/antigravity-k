#!/usr/bin/env python
"""NX-05 잔여 before/after driver: 이미 열려 있는 SSE 스트림이 PIN 변경으로 끊기는가?

`TestClient` 는 응답을 다 버퍼링하므로 "읽는 중에 끊긴다"를 관측할 수 없다. 이 드라이버는
**실제 uvicorn** 을 띄우고 httpx 로 **점진적으로** 읽는다 — 카드가 요구한 "실연결" 관측이다.

**같은 트리**에서 가드 배선만 켜고 끄며 돌린다(epoch 폐기 자체가 미커밋이라 HEAD 추출본은
기준선이 될 수 없다 — `security/auth_state.py` 가 커밋에 없다):

    # before: 드라이버가 가드 미들웨어만 벗긴다(제품 파일은 그대로)
    NX05_TREE=before NX05_SSE_DISABLE_GUARD=1 AGK_SSE_REVOCATION_CHECK_SECONDS=0.5 PYTHONPATH=src \
        .venv/bin/python docs/qa/2026-09-16-followup/nx05/repro_sse_live_revocation.py > before-sse.json
    # after: 기본값(가드 배선됨)
    NX05_TREE=after AGK_SSE_REVOCATION_CHECK_SECONDS=0.5 PYTHONPATH=src \
        .venv/bin/python docs/qa/2026-09-16-followup/nx05/repro_sse_live_revocation.py > after-sse.json

관측(공개 HTTP 표면만 사용):

* 세대가 바뀐 **뒤에도** 데이터 프레임이 계속 오는가 (`frames_after_epoch_change`),
* `session.revoked` 프레임이 오는가, 오면 언제인가 (`seconds_to_revocation`),
* 그 뒤 스트림이 **끝나는가**(EOF) — 폐기 프레임을 보낸 뒤에도 계속 흐르면 폐기가 아니다,
* 폐기 뒤 같은 bearer 의 **새 요청**이 401 인가(스트림과 HTTP 가 같은 세대를 보는지).

종료 코드: 0 = 폐기 관측(수정 트리), 3 = 폐기 없음(결함 재현).
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

PIN = "nx05-sse-pin-1234"
NEW_PIN = "nx05-sse-pin-5678"
REVOCATION_MARKER = "session.revoked"
FRAMES_DEADLINE_S = 6.0  # 폐기 관측 상한(기본 검사 주기 1초 + 여유)
POST_REVOCATION_DEADLINE_S = 3.0


class _IdleRuntime:
    """이벤트가 계속 생기고 상태가 종료가 아닌 task — 스트림이 살아 있게 유지된다."""

    def __init__(self) -> None:
        self._sequence = 0

    def get_task_status(self, task_id: str, owner_subject: str | None = None) -> dict[str, object]:
        return {"task_id": task_id, "prompt": "live sse probe", "status": "running", "output": ""}

    def list_task_events(
        self,
        task_id: str,
        after_sequence: int,
        limit: int,
        owner_subject: str | None = None,
    ) -> list[dict[str, object]]:
        self._sequence += 1
        return [
            {
                "sequence": self._sequence,
                "schema_version": 2,
                "task_id": task_id,
                "step_id": "step-1",
                "agent_id": "agent-root",
                "parent_id": None,
                "tool_call_id": None,
                "approval_id": None,
                "resource_job_id": None,
                "correlation_id": "sse-probe",
                "event_type": "task.progress",
                "payload_json": json.dumps({"tick": self._sequence}),
                "created_at": "2026-09-16T00:00:00+00:00",
            }
        ]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def main() -> int:
    tree = os.environ.get("NX05_TREE", "unspecified")

    from antigravity_k.config import config

    tmpdir = Path(tempfile.mkdtemp(prefix=f"nx05-sse-{getpass.getuser()}-"))
    config.security.access_pin = PIN
    config.security.pin_hash_file = str(tmpdir / "auth_hash")
    config.security.token_secret_file = str(tmpdir / "token_secret")
    state_path = Path(config.security.pin_hash_file)

    import antigravity_k.api.auth_routes as auth_routes
    import antigravity_k.api.routes.task_api as task_api
    from antigravity_k.api.auth_policy import init_shared_auth_policy

    auth_routes._token_service = None
    auth_routes._pin_hash = None
    auth_routes.init_auth_state()
    _ = init_shared_auth_policy(config.security.pin_hash_file)
    task_api.get_agent_runtime = lambda: _IdleRuntime()  # type: ignore[assignment]

    import httpx
    import uvicorn

    from antigravity_k.api.server import app

    # 대조군(guard 만 제거): epoch 폐기 자체가 아직 미커밋 작업이므로 HEAD 추출본은 기준선이 될 수
    # 없다(`security/auth_state.py` 가 커밋에 없다). 그래서 **같은 트리에서 가드 배선 한 줄만**
    # 드라이버가 벗겨 대조군을 만든다 — 제품 파일은 건드리지 않는다. 이 env 가 있으면 before,
    # 없으면 after 다(리포트에도 그대로 남는다).
    driver_disabled = os.environ.get("NX05_SSE_DISABLE_GUARD") == "1"
    if driver_disabled:
        app.user_middleware = [
            middleware
            for middleware in app.user_middleware
            if getattr(middleware.cls, "__name__", "") != "SSERevocationMiddleware"
        ]
        app.middleware_stack = None

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    started_at = time.monotonic()
    while not server.started and time.monotonic() - started_at < 20:
        time.sleep(0.05)
    if not server.started:
        print(json.dumps({"tree": tree, "error": "uvicorn did not start"}, ensure_ascii=False))
        return 1

    base = f"http://127.0.0.1:{port}"
    report: dict[str, Any] = {
        "tree": tree,
        "python": sys.version.split()[0],
        "pythonpath": os.environ.get("PYTHONPATH"),
        "port": port,
        "endpoint": "/api/tasks/task-live/events/stream",
        "check_interval_seconds": os.environ.get("AGK_SSE_REVOCATION_CHECK_SECONDS", "(default 1.0)"),
        "guard_disabled_by_driver": driver_disabled,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, read=10.0)) as client:
            login = client.post(f"{base}/api/auth/login", json={"pin": PIN})
            report["login_status"] = login.status_code
            if login.status_code != 200:
                report["error"] = login.text
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1
            bearer = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # 스트림이 열려 있는 동안 다른 프로세스/요청의 PIN 변경을 흉내낸다(저장 계층에서 +1).
            from antigravity_k.engine.auth import hash_pin
            from antigravity_k.security.auth_state import bump_epoch_atomic, current_epoch

            report["epoch_before"] = current_epoch(state_path)
            bump_time: dict[str, float] = {}

            def bump_after(delay_s: float) -> None:
                time.sleep(delay_s)
                bump_epoch_atomic(state_path, pin_hash=hash_pin(NEW_PIN))
                bump_time["at"] = time.monotonic()

            bump_thread = threading.Thread(target=bump_after, args=(0.8,), daemon=True)
            bump_thread.start()

            started = time.monotonic()
            frames_before: list[float] = []
            frames_after: list[float] = []
            revocation_at: float | None = None
            closed = False

            try:
                with client.stream("GET", f"{base}/api/tasks/task-live/events/stream", headers=bearer) as response:
                    report["stream_status"] = response.status_code
                    report["stream_content_type"] = response.headers.get("content-type")
                    # 한 번만 만든 반복자로 읽는다 — httpx 는 두 번 스트리밍하면 StreamConsumed 다.
                    lines = response.iter_lines()
                    for line in lines:
                        now = time.monotonic() - started
                        if REVOCATION_MARKER in line:
                            revocation_at = now
                            break
                        if line.startswith("data:"):
                            (frames_after if "at" in bump_time else frames_before).append(now)
                        if now > FRAMES_DEADLINE_S:
                            break

                    # 폐기 관측 뒤: 스트림이 정말 끝나는지(EOF) + 끝나기 전에 프레임이 더 오는지.
                    if revocation_at is not None:
                        last = time.monotonic()
                        for line in lines:
                            if line.startswith("data:"):
                                frames_after.append(time.monotonic() - started)
                            if time.monotonic() - last > POST_REVOCATION_DEADLINE_S:
                                break
                        else:
                            closed = True
            except httpx.ReadTimeout:
                report["read_timeout"] = True

            bump_thread.join(timeout=5)
            report.update(
                {
                    "frames_before_epoch_change": len(frames_before),
                    "frames_after_epoch_change": len(frames_after),
                    "revocation_frame_seen": revocation_at is not None,
                    "seconds_to_revocation": round(revocation_at, 3) if revocation_at is not None else None,
                    "stream_ended_after_revocation": closed,
                    "epoch_after": current_epoch(state_path),
                }
            )

            # 스트림과 HTTP 경로가 같은 세대를 보는가: 폐기된 bearer 로 새 요청.
            after = client.get(f"{base}/api/tasks/task-live/events/stream", headers=bearer)
            report["new_request_with_revoked_bearer_status"] = after.status_code
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    revoked = bool(report.get("revocation_frame_seen"))
    return 0 if revoked else 3


if __name__ == "__main__":
    raise SystemExit(main())
