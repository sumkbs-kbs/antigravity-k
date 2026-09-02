import pytest
from fastapi import WebSocket, WebSocketDisconnect
from starlette.types import Message, Receive, Scope, Send

from antigravity_k.api.routes import events


class _DisconnectingWebSocket(WebSocket):
    def __init__(self) -> None:
        scope: Scope = {"type": "websocket", "headers": [], "query_string": b""}
        receive: Receive = self._receive
        send: Send = self._send
        super().__init__(
            scope,
            receive,
            send,
        )

    async def _receive(self) -> Message:
        return {"type": "websocket.disconnect"}

    async def _send(self, _message: Message) -> None:
        return None

    async def send_json(self, data: object, mode: str = "text") -> None:
        del data, mode
        raise WebSocketDisconnect(code=1000)


@pytest.mark.asyncio
async def test_websocket_keepalive_disconnect_is_handled_without_error() -> None:
    assert await events._send_keepalive(_DisconnectingWebSocket()) is False
