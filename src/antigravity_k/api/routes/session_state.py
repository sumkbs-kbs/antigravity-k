"""Shared agent-session primitives for streaming routes.

스트림 라우트 전반에서 공유하는 활성 에이전트 세션 상태와
WebSocket 인증 헬퍼를 담는 중립 모듈이다. 라우트 모듈 간에는
이 모듈을 향한 의존만 허용하고, 모듈 간 직접 임포트(역류)는 하지 않는다.
"""

import logging
import os
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from antigravity_k.engine.agent_runtime import OrchestratorPort

logger = logging.getLogger("antigravity_k.api.session_state")


class ActiveAgentSession:
    """Holds the currently active agent session state for streaming."""

    def __init__(self) -> None:
        """Initialize the ActiveAgentSession."""
        self.q: str = ""
        self.is_active: bool = False
        self.history: list[str] = []
        self.done: bool = False
        self.error: str | None = None
        self.orchestrator: OrchestratorPort | None = None


_active_session = ActiveAgentSession()


def get_active_session() -> ActiveAgentSession:
    """활성 세션 싱글톤을 반환합니다.

    세션 교체는 바인딩 재할당이 아니라 reset_active_session()으로 수행한다.
    값 복사 임포트를 하는 소비자 모듈이 있어도 바인딩이 흐트러지지 않는다.
    """
    return _active_session


def reset_active_session() -> ActiveAgentSession:
    """세션 필드를 초기화하되 싱글톤 객체 정체는 유지합니다."""
    _active_session.q = ""
    _active_session.is_active = False
    _active_session.history.clear()
    _active_session.done = False
    _active_session.error = None
    _active_session.orchestrator = None
    return _active_session


async def close_unauthorized_ws(websocket: WebSocket) -> bool:
    """Close WebSocket if not authorized. Returns True if closed.

    Authenticates the connection using a bearer token or legacy PIN provided
    via query parameters (``?token=`` or ``?pin=``) since browsers cannot set
    custom headers on WebSocket handshakes. If the connection carries valid
    credentials this returns ``False`` (not closed); otherwise it accepts then
    immediately closes the socket with a 4401 policy code and returns ``True``.
    """
    from antigravity_k.api.auth_routes import get_token_service
    from antigravity_k.engine.auth import extract_token_from_ws, verify_pin

    # Accept first so we can send a close code; Starlette requires accept before close.
    await websocket.accept()
    websocket.state.agk_accepted = True

    credential = extract_token_from_ws(websocket)

    from antigravity_k.api.startup_security import is_loopback_host
    from antigravity_k.config import config

    if (
        not config.security.access_pin
        and os.environ.get("AGK_ENV", "development").strip().lower() != "production"
        and is_loopback_host(config.server.host)
    ):
        websocket.state.auth_subject = "loopback"
        return False

    # Try bearer token first.
    if credential:
        token_service = get_token_service()
        # Heuristic: tokens contain dots (JWT structure), PINs don't.
        if "." in credential:
            claims = token_service.verify_token(credential)
            if claims is not None:
                subject = claims.get("sub")
                websocket.state.auth_subject = subject if isinstance(subject, str) and subject else "bearer"
                return False
        # Otherwise treat as a legacy PIN.
        from antigravity_k.api.auth_routes import get_current_pin_hash

        stored = get_current_pin_hash()
        if stored and verify_pin(credential, stored):
            websocket.state.auth_subject = "pin-user"
            return False

    # No valid credential — deny.
    await websocket.close(code=4401, reason="Unauthorized")
    return True
