#!/usr/bin/env python3
"""NX-09 드라이버 — PIN 변경이 **실 uvicorn 의 인증 WS** 를 정말 닫는가.

왜 브라우저 관측으로는 부족한가
------------------------------
`nx09-user-journey.spec.ts` T5 는 브라우저에서 "소켓이 살아 있다"와 응답의
`sessions_revoked: 0` 을 **함께** 관측했다. 서버가 등록을 안 했는지, 등록했는데 못 닫았는지,
브라우저가 재연결한 것인지는 그 두 값만으로 **구분되지 않는다**. 이 드라이버는 프로세스 안에서
같은 객체를 직접 보기 때문에 그 구분을 한다:

  * 실제 `uvicorn.Server`(TestClient 아님)로 앱을 띄운다 — 게이트/레지스트리가 실 배포와 같다.
  * 제품 경로 그대로 **단기 ticket**(`/api/auth/ws-ticket` → `?ticket=`)으로 붙는다.
  * 연결 직후 `authorized_ws_count()`(레지스트리 실측)를 읽는다.
  * PIN 변경 응답의 `sessions_revoked` 와 **WS 클라이언트가 받은 close code** 를 함께 본다.

이것은 X-09 의 "PIN 변경 → 재로그인·연결 종료 실제 UI 관측" 을 **서버 쪽에서** 확정하는 자다.
사용자 데이터·프로젝트 데이터는 쓰지 않는다(임시 디렉터리).

종료 코드: 0 = 측정 완료(판정은 JSON), 1 = 측정 실패.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def prepare_env(state: Path) -> None:
    (state / "data").mkdir(parents=True, exist_ok=True)
    (state / "logs").mkdir(parents=True, exist_ok=True)
    (state / "vault").mkdir(parents=True, exist_ok=True)
    (state / "empty.env").write_text("# isolated\n", encoding="utf-8")
    (state / "token_secret").write_text(secrets.token_hex(32), encoding="utf-8")
    os.environ.update(
        {
            "AGK_ENV": "development",
            "AGK_ENV_FILE": str(state / "empty.env"),
            "AGK_SEC_ACCESS_PIN": "nx09-driver-pin",
            "AGK_SEC_TOKEN_TTL_HOURS": "1",
            "AGK_SEC_PIN_HASH_FILE": str(state / "pin_hash"),
            "AGK_SEC_TOKEN_SECRET_FILE": str(state / "token_secret"),
            "AGK_PATH_DATA_DIR": str(state / "data"),
            "AGK_PATH_LOGS_DIR": str(state / "logs"),
            "AGK_CONVERSATION_STORE_DIR": str(state / "conversations"),
            "AGK_HOOK_VAULT_DIR": str(state / "vault"),
            "PYTHONPATH": str(SRC),
        }
    )
    # 이 시나리오는 **인증이 구성된** 서버를 잰다 — 익명 허용이 섞이면 질문이 달라진다.
    os.environ.pop("AGK_SEC_DEV_NO_PIN_ALLOW", None)


def main() -> int:
    state = Path(tempfile.mkdtemp(prefix="agk-nx09-ws-"))
    prepare_env(state)

    import httpx
    import uvicorn
    from websockets.asyncio.client import connect as ws_connect

    from antigravity_k.api.routes import session_state
    from antigravity_k.api.server import app

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    report: dict[str, object] = {"base_url": base}
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        print(json.dumps({"error": "server did not start"}, ensure_ascii=False))
        return 1

    try:
        with httpx.Client(base_url=base, timeout=10) as client:
            login = client.post("/api/auth/login", json={"pin": "nx09-driver-pin"})
            report["login_status"] = login.status_code
            token = login.json().get("access_token", "")
            headers = {"Authorization": f"Bearer {token}"}
            ticket_response = client.post("/api/auth/ws-ticket", headers=headers)
            ticket = ticket_response.json().get("ticket", "")
            report["ticket_status"] = ticket_response.status_code
            report["ticket_len"] = len(ticket)

            async def measure() -> dict[str, object]:
                ws_url = f"ws://127.0.0.1:{port}/v1/ws/events?ticket={ticket}"
                outcome: dict[str, object] = {}
                closed = asyncio.Event()
                close_info: dict[str, object] = {}

                # 폐기 경로가 **왜** 세지 못했는지 그대로 남긴다(측정용 로거 가로채기).
                warnings: list[object] = []
                original_warning = session_state.logger.warning
                session_state.logger.warning = lambda *args, **_kwargs: warnings.append(args)

                async with ws_connect(ws_url) as socket_client:
                    # 게이트가 등록했는지 **프로세스 안에서** 직접 본다.
                    for _ in range(20):
                        if session_state.authorized_ws_count() >= 1:
                            break
                        await asyncio.sleep(0.1)
                    outcome["registry_after_connect"] = session_state.authorized_ws_count()
                    # 상태 판정의 근거를 직접 본다 — close 프레임이 갔는데 상태가 안 바뀌는가?
                    registered = [ref() for ref, _loop in session_state._authorized_ws]  # noqa: SLF001

                    def watch() -> None:
                        asyncio.run_coroutine_threadsafe(socket_client.wait_closed(), asyncio.get_event_loop())
                        closed.set()

                    change_started = time.time()
                    response = client.post(
                        "/api/auth/change-pin",
                        headers=headers,
                        json={"current_pin": "nx09-driver-pin", "new_pin": "nx09-driver-pin-2"},
                    )
                    outcome["change_pin_seconds"] = round(time.time() - change_started, 3)
                    outcome["change_pin_status"] = response.status_code
                    outcome["change_pin_body"] = response.json() if response.status_code == 200 else response.text
                    started = time.time()
                    try:
                        await asyncio.wait_for(socket_client.wait_closed(), timeout=10)
                        outcome["ws_closed"] = True
                        outcome["ws_close_code"] = socket_client.close_code
                        outcome["ws_close_latency_s"] = round(time.time() - started, 3)
                    except asyncio.TimeoutError:
                        outcome["ws_closed"] = False
                        outcome["ws_close_code"] = None
                        outcome["ws_close_latency_s"] = None
                    outcome["registry_after_change"] = session_state.authorized_ws_count()
                    outcome["server_side_state"] = [
                        {
                            "client_state": str(getattr(obj, "client_state", None)),
                            "application_state": str(getattr(obj, "application_state", None)),
                        }
                        for obj in registered
                        if obj is not None
                    ]
                    _ = (watch, closed, close_info)
                session_state.logger.warning = original_warning
                outcome["close_warnings"] = [" ".join(str(part) for part in args) for args in warnings]
                return outcome

            report["ws"] = asyncio.run(measure())
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        # 사용자 홈을 건드리지 않았음을 남긴다.
        report["state_dir"] = str(state)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
