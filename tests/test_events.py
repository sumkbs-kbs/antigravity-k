import asyncio
import threading
from typing import cast

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


class _EventWebSocket(WebSocket):
    """WebSocket that replies with N normal messages, then a disconnect."""

    def __init__(self, receives_before_disconnect: int = 0) -> None:
        scope: Scope = {"type": "websocket", "headers": [], "query_string": b""}
        self._remaining = receives_before_disconnect
        self._connect_seen = False
        self.sent: list[object] = []
        super().__init__(scope, self._receive, self._send)

    async def _receive(self) -> Message:
        if not self._connect_seen:
            self._connect_seen = True
            return {"type": "websocket.connect"}
        if self._remaining > 0:
            self._remaining -= 1
            return {"type": "websocket.receive", "text": "ping"}
        return {"type": "websocket.disconnect"}

    async def _send(self, _message: Message) -> None:
        return None

    async def send_json(self, data: object, mode: str = "text") -> None:
        del mode
        self.sent.append(data)


class _FakeBus:
    def __init__(self) -> None:
        self.subscribed: list[tuple[str, object]] = []
        self.unsubscribed: list[tuple[str, object]] = []

    def subscribe(self, e_name: str, cb: object) -> None:
        self.subscribed.append((e_name, cb))

    def unsubscribe(self, e_name: str, cb: object) -> None:
        self.unsubscribed.append((e_name, cb))


@pytest.mark.asyncio
async def test_websocket_events_exits_promptly_on_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    """핸들러가 클라이언트 disconnect를 queue 타임아웃(30s)을 기다리지 않고 즉시 종료한다."""
    fake_bus = _FakeBus()
    monkeypatch.setattr(events, "global_event_bus", fake_bus)

    async def _authorize(websocket: WebSocket) -> bool:
        await websocket.accept()
        return False

    monkeypatch.setattr(events, "close_unauthorized_ws", _authorize)
    ws = _EventWebSocket()

    await asyncio.wait_for(events.websocket_events(ws), timeout=2.0)

    # 구독/해제가 균형을 이룬다 (워처 취소로 인한 해제 포함)
    assert len(fake_bus.subscribed) == len(fake_bus.unsubscribed)
    assert len(fake_bus.subscribed) > 0


class _ControlledWebSocket(WebSocket):
    """connect 수신 후 disconnect 신호를 기다리는 동안 연결을 유지하는 가짜 소켓.

    Starlette의 accept()는 connect 메시지를 먼저 소비하므로 connect를 반환한 뒤
    _release가 설정될 때까지 receive를 블록한다.
    """

    def __init__(self) -> None:
        scope: Scope = {"type": "websocket", "headers": [], "query_string": b""}
        self._release = asyncio.Event()
        self._connect_seen = False
        self.sent: list[object] = []
        super().__init__(scope, self._receive, self._send)

    async def _receive(self) -> Message:
        if not self._connect_seen:
            self._connect_seen = True
            return {"type": "websocket.connect"}
        await self._release.wait()
        return {"type": "websocket.disconnect"}

    async def _send(self, _message: Message) -> None:
        return None

    async def send_json(self, data: object, mode: str = "text") -> None:
        del mode
        self.sent.append(data)

    async def disconnect(self) -> None:
        self._release.set()


@pytest.mark.asyncio
async def test_websocket_events_forwards_events_published_from_non_loop_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """루프가 없는 일반 스레드(HookEventBus watcher 등)에서 발행된 이벤트도 유실 없이 전송된다.

    회귀: 이전 구현은 _cb 내부에서 asyncio.get_running_loop()를 호출해 루프 없는
    스레드에서 RuntimeError로 이벤트를 조용히 유실했다.
    """
    fake_bus = _FakeBus()
    monkeypatch.setattr(events, "global_event_bus", fake_bus)

    async def _authorize(websocket: WebSocket) -> bool:
        await websocket.accept()
        return False

    monkeypatch.setattr(events, "close_unauthorized_ws", _authorize)
    ws = _ControlledWebSocket()

    handler_task = asyncio.create_task(events.websocket_events(ws))
    for _ in range(200):
        if fake_bus.subscribed:
            break
        await asyncio.sleep(0.01)
    assert fake_bus.subscribed, "핸들러가 EventBus에 구독을 마쳐야 한다"

    def _publish_from_thread() -> None:
        # HookEventBus watcher 스레드 시뮬레이션 — asyncio 루프가 없는 일반 스레드
        _, callback = fake_bus.subscribed[0]
        callback(tool_name="read_file")

    thread = threading.Thread(target=_publish_from_thread)
    thread.start()
    thread.join()

    # 루프가 스레드에서 스케줄된 put_nowait를 처리하고 전송할 시간을 준다
    for _ in range(200):
        if ws.sent:
            break
        await asyncio.sleep(0.01)

    assert ws.sent, "비-루프 스레드 발행 이벤트가 WebSocket으로 전송되어야 한다"
    forwarded = cast(dict[str, object], ws.sent[0])
    assert forwarded["event"] == "ToolExecutionStarted"
    assert forwarded["data"] == {"tool_name": "read_file"}

    await ws.disconnect()
    await asyncio.wait_for(handler_task, timeout=2.0)


@pytest.mark.asyncio
async def test_websocket_events_forwards_queued_events_then_exits_on_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """큐에 담긴 이벤트는 전송되고, 이후 disconnect 시 즉시 종료된다."""
    monkeypatch.setattr(events, "global_event_bus", _FakeBus())

    async def _authorize(websocket: WebSocket) -> bool:
        await websocket.accept()
        return False

    monkeypatch.setattr(events, "close_unauthorized_ws", _authorize)
    ws = _EventWebSocket(receives_before_disconnect=1)

    queued_event: dict[str, object] = {"event": "ToolExecutionStarted", "data": {"tool_name": "read_file"}}

    class _PreFilledQueue(asyncio.Queue):  # type: ignore[type-arg]
        def __init__(self) -> None:
            super().__init__()
            self.put_nowait(queued_event)

    monkeypatch.setattr(events.asyncio, "Queue", _PreFilledQueue)

    await asyncio.wait_for(events.websocket_events(ws), timeout=2.0)

    assert ws.sent == [queued_event]


# ─── 프론트엔드-백엔드 WS 이벤트 계약 ────────────────────────────────────────
# dashboard/src/hooks/useEventWebSocket.ts 의 eventMessageSchema(discriminatedUnion)가
# 소비하는 이벤트 이름 — 이 목록이 events_to_track에 빠지면 대시보드 UI 훅이
# 영구적으로 무음이 되므로 계약 테스트로 고정한다.
FRONTEND_WS_EVENTS = frozenset(
    {
        "ModeChanged",
        "ToolExecutionStarted",
        "ToolExecutionFinished",
        "FailureDetected",
        "CognitiveAdaptation",
        "PlanningModeStarted",
        "ApprovalRequired",
        "AgentTurnStarted",
        "AgentTurnEnded",
        "QualityCheckPassed",
        "QualityCheckFailed",
        "AntiPatternsDetected",
        "FileOpened",
        "FileModified",
    }
)

# TRACKED_EVENTS 전체의 실제 발행자 문서화 (죽은 구독 방지).
# 프론트가 소비하지 않아도 kanban_api 등 EventBus 직접 구독자가 있으면 유지한다.
WS_EVENT_PUBLISHERS: dict[str, str] = {
    "ToolExecutionStarted": "engine.tool_loop._publish_event",
    "ToolExecutionFinished": "engine.tool_loop._publish_event",
    "FailureDetected": "engine.tool_executor._broadcast_failure_event",
    "AgentTurnStarted": "event_bus bridge HOOK_KIND_TO_EVENT_NAME (autonomous_learner 발신)",
    "AgentTurnEnded": "event_bus bridge HOOK_KIND_TO_EVENT_NAME (autonomous_learner 발신)",
    "QualityCheckPassed": "engine.tool_loop._publish_quality_event (QualityGate 결과)",
    "QualityCheckFailed": "engine.tool_loop._publish_quality_event (QualityGate 결과)",
    "AntiPatternsDetected": "engine.cognitive_loop._publish_anti_patterns (반복 실패 감지)",
    "FileOpened": "engine.tool_executor._broadcast_file_event",
    "FileModified": "engine.tool_executor._broadcast_file_event",
    "ModeChanged": "engine.mode_manager._publish_to_eventbus",
    "CognitiveAdaptation": "engine.cognitive_loop._publish_cognitive_adaptation",
    "PlanningModeStarted": "engine.mode_manager._publish_planning_started",
    "ApprovalRequired": "engine.tool_executor._broadcast_approval_required",
}


def test_events_to_track_covers_frontend_ws_contract() -> None:
    """/v1/ws/events 구독 목록이 프론트엔드가 소비하는 모든 이벤트를 포함한다."""
    missing = FRONTEND_WS_EVENTS - set(events.TRACKED_EVENTS)
    assert missing == set(), f"프론트엔드가 소비하지만 WS가 구독하지 않는 이벤트: {sorted(missing)}"


def test_tracked_events_have_no_dead_subscriptions() -> None:
    """TRACKED_EVENTS의 모든 항목은 프론트가 소비하거나 실제 발행자가 있어야 한다.

    발행자도 소비자도 없는 죽은 구독(QualityCheck*, FailureRecovered, AntiPatternsDetected
    등)이 다시 추가되지 않도록 고정한다.
    """
    unknown = set(events.TRACKED_EVENTS) - FRONTEND_WS_EVENTS - set(WS_EVENT_PUBLISHERS)
    assert unknown == set(), (
        f"발행자도 소비자도 없는 죽은 구독: {sorted(unknown)} — " "발행자를 연결하거나 TRACKED_EVENTS에서 제거할 것"
    )
