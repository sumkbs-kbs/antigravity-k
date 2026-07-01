"""Events module."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from antigravity_k.engine.event_bus import global_event_bus

logger = logging.getLogger("antigravity_k.api.events")

router = APIRouter()


@router.websocket("/v1/ws/events")
async def websocket_events(websocket: WebSocket):
    """Websocket Events.

    Args:
        websocket (WebSocket): WebSocket websocket.

    """
    await websocket.accept()
    queue = asyncio.Queue()

    def make_callback(e_name):
        def _cb(**kwargs):
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(queue.put_nowait, {"event": e_name, "data": kwargs})
            except Exception:
                logger.exception("Unhandled exception")
                pass

        return _cb

    events_to_track = [
        "ToolExecutionStarted",
        "ToolExecutionFinished",
        "QualityCheckStarted",
        "QualityCheckFailed",
        "QualityCheckPassed",
        "FailureDetected",
        "FailureRecovered",
        "AgentTurnStarted",
        "AgentTurnEnded",
        "AntiPatternsDetected",
        "FileOpened",
        "FileModified",
    ]

    callbacks = {e: make_callback(e) for e in events_to_track}
    for e, cb in callbacks.items():
        global_event_bus.subscribe(e, cb)

    try:
        while True:
            # timeout으로 주기적으로 깨어나서 shutdown 시그널을 확인할 수 있게 합니다
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # keepalive ping — 클라이언트 연결 유효성 확인
                try:
                    await websocket.send_json({"event": "ping", "data": {}})
                except Exception:
                    logger.exception("Unhandled exception")
                    break
    except (WebSocketDisconnect, asyncio.CancelledError):
        logger.info("WebSocket disconnected from /v1/ws/events")
    except Exception as e:
        logger.exception("WebSocket /v1/ws/events unexpected error")
    finally:
        for e, cb in callbacks.items():
            global_event_bus.unsubscribe(e, cb)
