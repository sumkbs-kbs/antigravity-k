"""Shared agent-session primitives for streaming routes.

스트림 라우트 전반에서 공유하는 활성 에이전트 세션 상태와
WebSocket 인증 헬퍼를 담는 중립 모듈이다. 라우트 모듈 간에는
이 모듈을 향한 의존만 허용하고, 모듈 간 직접 임포트(역류)는 하지 않는다.
"""

import logging
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

    SEC-01 단일 정책: 판정은 HTTP 미들웨어와 같은 공유 AuthPolicy로 수행한다.
    저장 PIN hash가 있으면 loopback 개발 모드도 보호 상태이며, 익명 허용은
    명시적 dev 설정 + loopback + credential 전무 조건에서만 가능하다.

    Authenticates the connection using a bearer token (``?token=`` query or
    ``Sec-WebSocket-Protocol`` subprotocol). PIN query 인증은 제거되었다 —
    PIN은 rate-limited login route로만 제출한다 (SEC-02 표면 축소 정합).
    """
    from antigravity_k.api.auth_policy import get_shared_auth_policy
    from antigravity_k.api.auth_routes import get_token_service
    from antigravity_k.config import config
    from antigravity_k.engine.auth import extract_token_from_ws

    # Accept first so we can send a close code; Starlette requires accept before close.
    await websocket.accept()
    websocket.state.agk_accepted = True

    credential = extract_token_from_ws(websocket)

    token_verified = False
    token_subject: str | None = None
    if credential and "." in credential:
        claims = get_token_service().verify_token(credential)
        if claims is not None:
            token_verified = True
            subject = claims.get("sub")
            token_subject = subject if isinstance(subject, str) and subject else "bearer"

    decision = get_shared_auth_policy().evaluate_credential(
        token_verified=token_verified,
        pin=None,  # WS에서 PIN credential을 받지 않는다 (query ?pin= 제거).
        host=config.server.host,
    )
    if decision.level == "open_loopback":
        websocket.state.auth_subject = "loopback"
        return False
    if token_verified and token_subject is not None:
        websocket.state.auth_subject = token_subject
        return False

    # SEC-02: WS는 bearer token만 수용한다 — 과거 "점이 없으면 legacy PIN으로
    # 간주해 PBKDF2 검증" 분기는 query로 PIN 후보를 반복 전송해 PBKDF2 CPU 비용을
    # 유발하는 공격 표면이었으므로 제거되었다. evaluate_credential에 pin=None을
    # 전달하므로 이 경로에서 PBKDF2가 실행될 수 없다.
    # No valid credential — deny (4401, plan 규정 equivalent).
    await websocket.close(code=4401, reason="Unauthorized")
    return True
