import socket
from collections.abc import Iterator
from threading import Event, Thread
from typing import cast, override

import httpx
import pytest
import uvicorn
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from antigravity_k.api.auth_routes import TokenResponse
from antigravity_k.api.routes.workspace_services import ServiceResponse
from antigravity_k.api.server import app
from antigravity_k.engine.auth import TokenService
from antigravity_k.engine.workspace_service_registry import WorkspaceServiceRegistry
from tests.test_workspace_websocket import TEST_PIN, EchoUpstream
from tests.test_workspace_websocket import echo as echo
from tests.test_workspace_websocket import registry as registry
from tests.test_workspace_websocket import token_service as token_service


class LiveServer(uvicorn.Server):
    def __init__(self) -> None:
        super().__init__(uvicorn.Config(app, lifespan="off", log_level="warning", ws="websockets-sansio"))
        self.ready: Event = Event()

    @override
    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets)
        self.ready.set()


@pytest.fixture
def live_server(token_service: TokenService, registry: WorkspaceServiceRegistry) -> Iterator[str]:
    _ = token_service, registry
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        server = LiveServer()
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            assert server.ready.wait(timeout=10), "Uvicorn did not start"
            yield f"127.0.0.1:{listener.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "Uvicorn leaked a running thread"


def test_live_login_register_and_workspace_ws_auth(live_server: str, echo: EchoUpstream) -> None:
    with httpx.Client(base_url=f"http://{live_server}", trust_env=False) as client:
        assert client.get("/api/workspace/services").status_code == 401
        response = client.post("/api/auth/login", json={"pin": TEST_PIN})
        assert response.status_code == 200
        token = TokenResponse.model_validate_json(response.content).access_token
        created = client.post(
            "/api/workspace/services",
            headers={"Authorization": f"Bearer {token}"},
            json={"service": "echo", "branch": "main", "project": "qa", "port": echo.port},
        )
        assert created.status_code == 201
        hostname = ServiceResponse.model_validate_json(created.content).hostname
        assert client.get(f"/api/workspace/services/{hostname}/proxy").status_code == 401
    for suffix in ("", "/nested/socket"):
        url = f"ws://{live_server}/api/workspace/services/{hostname}/ws{suffix}"
        with connect(url, proxy=None, open_timeout=5) as ws:
            with pytest.raises(ConnectionClosed) as closed:
                _ = ws.recv(timeout=5)
            assert closed.value.rcvd is not None and closed.value.rcvd.code == 4401
        with connect(url + f"?token={token}&room=qa", proxy=None, open_timeout=5) as ws:
            assert ws.recv(timeout=5) == f"{suffix or '/'}?room=qa"
            ws.send("live 한글")
            assert ws.recv(timeout=5) == "live 한글"
            ws.send(b"\x00live")
            assert ws.recv(timeout=5) == b"\x00live"
    assert len(echo.paths) == 2, "Rejected requests must not open upstream connections"
    print("WIRE: HTTP no-auth=401, login=200, register=201, WS no-auth=4401 x2, authenticated text/binary=PASS x2")


@pytest.mark.parametrize("command,code", [("close-normal", 1000), ("close-error", 1011)])
def test_live_upstream_close_reaches_client(
    live_server: str,
    echo: EchoUpstream,
    registry: WorkspaceServiceRegistry,
    command: str,
    code: int,
) -> None:
    record = registry.register("echo", "main", "qa", echo.port)
    url = f"ws://{live_server}/api/workspace/services/{record.hostname}/ws?pin={TEST_PIN}"
    with connect(url, proxy=None, open_timeout=5, close_timeout=1) as ws:
        assert ws.recv(timeout=5) == "/"
        ws.send(command)
        with pytest.raises(ConnectionClosed) as closed:
            _ = ws.recv(timeout=2)
        assert closed.value.rcvd is not None and closed.value.rcvd.code == code
    assert echo.disconnected.wait(timeout=5)


def test_live_unreachable_upstream_closes_1011(live_server: str, registry: WorkspaceServiceRegistry) -> None:
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = cast(tuple[str, int], reserved.getsockname())[1]
        record = registry.register("offline", "main", "qa", port)
        url = f"ws://{live_server}/api/workspace/services/{record.hostname}/ws?pin={TEST_PIN}"
        with connect(url, proxy=None, open_timeout=5) as ws:
            with pytest.raises(ConnectionClosed) as closed:
                _ = ws.recv(timeout=15)
            assert closed.value.rcvd is not None and closed.value.rcvd.code == 1011
