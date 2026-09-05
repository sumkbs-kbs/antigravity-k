from collections.abc import Iterator
from dataclasses import dataclass, field
from threading import Event, Thread
from urllib.parse import parse_qsl, urlsplit

import anyio
import pytest
from anyio.to_thread import run_sync
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.types import Message
from starlette.websockets import WebSocketDisconnect, WebSocketState
from websockets.sync.server import ServerConnection, serve

from antigravity_k.api import auth_routes
from antigravity_k.api.routes import workspace_services
from antigravity_k.api.routes.workspace_websocket import relay_workspace_websocket
from antigravity_k.config import config
from antigravity_k.engine.auth import TokenService, hash_pin
from antigravity_k.engine.workspace_service_registry import WorkspaceServiceRegistry

TEST_PIN = "f01-isolated-test-pin"


@dataclass
class EchoUpstream:
    port: int = 0
    paths: list[str] = field(default_factory=list)
    headers: list[dict[str, str]] = field(default_factory=list)
    disconnected: Event = field(default_factory=Event)

    def handle(self, connection: ServerConnection) -> None:
        assert connection.request is not None
        self.paths.append(connection.request.path)
        self.headers.append(dict(connection.request.headers))
        try:
            connection.send(connection.request.path)
            for message in connection:
                if message in ("close-normal", "close-error"):
                    connection.close(code=1000 if message == "close-normal" else 1011)
                    return
                connection.send(message)
        finally:
            self.disconnected.set()


@pytest.fixture
def echo() -> Iterator[EchoUpstream]:
    upstream = EchoUpstream()
    with serve(upstream.handle, "127.0.0.1", 0, close_timeout=1) as server:
        upstream.port = server.socket.getsockname()[1]
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield upstream
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


@pytest.fixture
def token_service(monkeypatch: pytest.MonkeyPatch) -> TokenService:
    service = TokenService()
    monkeypatch.setattr(auth_routes, "_token_service", service)
    monkeypatch.setattr(auth_routes, "_pin_hash", hash_pin(TEST_PIN))
    monkeypatch.setattr(config.security, "access_pin", TEST_PIN)
    monkeypatch.setattr(config.server, "host", "127.0.0.1")
    monkeypatch.setenv("AGK_ENV", "development")
    return service


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> WorkspaceServiceRegistry:
    registry = WorkspaceServiceRegistry()
    monkeypatch.setattr(workspace_services, "_registry", registry)
    return registry


@pytest.fixture
def client(token_service: TokenService, registry: WorkspaceServiceRegistry) -> Iterator[TestClient]:
    _ = token_service, registry
    app = FastAPI()
    app.include_router(workspace_services.router)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("suffix", ["", "/nested/socket"])
@pytest.mark.parametrize("credential", ["missing", "invalid", "expired", "wrong-pin", "subprotocol"])
def test_unauthorized_workspace_ws_never_reaches_upstream(
    client: TestClient,
    echo: EchoUpstream,
    registry: WorkspaceServiceRegistry,
    token_service: TokenService,
    suffix: str,
    credential: str,
) -> None:
    record = registry.register("echo", "main", "qa", echo.port)
    query = ""
    protocols: list[str] = []
    if credential == "invalid":
        query = "?token=invalid.credential.signature"
    elif credential == "expired":
        query = "?token=" + token_service.issue_token("qa", extra_claims={"exp": 1})
    elif credential == "wrong-pin":
        query = "?pin=wrong-pin"
    elif credential == "subprotocol":
        protocols = ["bearer.invalid.credential.signature"]
    with client.websocket_connect(
        f"/api/workspace/services/{record.hostname}/ws{suffix}{query}",
        subprotocols=protocols,
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            _ = ws.receive_text()
        assert closed.value.code == 4401
    assert echo.paths == [], "Unauthenticated request reached the workspace upstream"


@pytest.mark.parametrize("suffix", ["", "/nested/socket"])
@pytest.mark.parametrize("channel", ["token", "pin", "subprotocol"])
def test_authenticated_workspace_ws_roundtrip_strips_credentials(
    client: TestClient,
    echo: EchoUpstream,
    registry: WorkspaceServiceRegistry,
    token_service: TokenService,
    suffix: str,
    channel: str,
) -> None:
    record = registry.register("echo", "main", "qa", echo.port)
    token = token_service.issue_token("qa")
    query = "room=alpha&room=beta&empty=&text=a%2Bb%20c"
    protocols: list[str] = []
    if channel == "subprotocol":
        protocols = [f"bearer.{token}"]
    elif channel == "pin":
        query += f"&pin={TEST_PIN}"
    else:
        query += f"&token={token}&token={token}&p%69n=do-not-forward"
    with client.websocket_connect(
        f"/api/workspace/services/{record.hostname}/ws{suffix}?{query}",
        subprotocols=protocols,
    ) as ws:
        forwarded = urlsplit(ws.receive_text())
        assert forwarded.path == (suffix or "/")
        assert parse_qsl(forwarded.query, keep_blank_values=True) == [
            ("room", "alpha"),
            ("room", "beta"),
            ("empty", ""),
            ("text", "a+b c"),
        ]
        ws.send_text("한글 text")
        assert ws.receive_text() == "한글 text"
        ws.send_bytes(b"\x00\x01binary")
        assert ws.receive_bytes() == b"\x00\x01binary"
    assert echo.disconnected.wait(timeout=5), "Upstream connection leaked after client disconnect"
    assert "sec-websocket-protocol" not in echo.headers[0]
    assert "authorization" not in echo.headers[0]
    assert echo.headers[0]["x-workspace-service"] == "echo"


@pytest.mark.parametrize("ready", [False, True])
def test_auth_precedes_service_lookup(client: TestClient, registry: WorkspaceServiceRegistry, ready: bool) -> None:
    hostname = "unknown.localhost"
    if ready:
        hostname = registry.register("echo", "main", "qa", 1, status="stopped").hostname
    with client.websocket_connect(f"/api/workspace/services/{hostname}/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            _ = ws.receive_text()
        assert closed.value.code == 4401


@pytest.mark.parametrize("service_state", ["unknown", "stopped"])
def test_authenticated_unavailable_service_closes_cleanly(
    client: TestClient,
    registry: WorkspaceServiceRegistry,
    service_state: str,
) -> None:
    hostname = "unknown.localhost"
    if service_state == "stopped":
        hostname = registry.register("echo", "main", "qa", 1, status="stopped").hostname
    with client.websocket_connect(f"/api/workspace/services/{hostname}/ws?pin={TEST_PIN}") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            _ = ws.receive_text()
        assert closed.value.code == 1008


@pytest.mark.parametrize(
    "environment,host", [("development", "127.0.0.1"), ("production", "127.0.0.1"), ("development", "0.0.0.0")]
)
def test_no_pin_loopback_policy_is_preserved(
    client: TestClient,
    echo: EchoUpstream,
    registry: WorkspaceServiceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    host: str,
) -> None:
    monkeypatch.setattr(config.security, "access_pin", "")
    monkeypatch.setattr(config.server, "host", host)
    monkeypatch.setenv("AGK_ENV", environment)
    record = registry.register("echo", "main", "qa", echo.port)
    with client.websocket_connect(f"/api/workspace/services/{record.hostname}/ws") as ws:
        if environment == "production" or host == "0.0.0.0":
            with pytest.raises(WebSocketDisconnect) as closed:
                _ = ws.receive_text()
            assert closed.value.code == 4401
        else:
            assert ws.receive_text() == "/"


@pytest.mark.asyncio
async def test_send_side_disconnect_does_not_close_already_disconnected_socket(echo: EchoUpstream) -> None:
    async def receive() -> Message:
        await anyio.sleep_forever()
        raise AssertionError("receive wait unexpectedly completed")

    async def send(message: Message) -> None:
        assert message["type"] == "websocket.send"
        raise OSError("client disconnected during send")

    websocket = WebSocket({"type": "websocket", "query_string": b"", "headers": []}, receive, send)
    websocket.client_state = WebSocketState.CONNECTED
    websocket.application_state = WebSocketState.CONNECTED
    record = WorkspaceServiceRegistry().register("echo", "main", "qa", echo.port)
    with anyio.fail_after(5):
        await relay_workspace_websocket(websocket, record, "")
    assert websocket.application_state == WebSocketState.DISCONNECTED
    assert websocket.client_state == WebSocketState.CONNECTED
    assert await run_sync(echo.disconnected.wait, 5)
