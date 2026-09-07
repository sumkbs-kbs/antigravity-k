"""SEC-03 — 단기 1회성 WebSocket ticket.

GA-100 plan §SEC-03: "authenticated HTTP session에서 짧은 수명의 1회성 WS
ticket을 발급하고 Origin allowlist를 적용한다."

설계:
- ticket은 TokenService와 같은 서명 secret으로 서명된 **단기(기본 30초) JWT**다.
  ``typ=ws-ticket`` + ``jti``(1회성 id) + ``sub``(subject) 클레임을 갖는다.
- 1회성: 성공적 소비(consume) 시 ``jti``를 메모리 사용 목록에 기록한다.
  같은 ``jti`` 재사용은 거절된다 (replay 방지).
- 만료: JWT ``exp``(기본 30초)로 거절된다. 사용 목록 항목은 만료 후 60초 뒤
  지연 청소된다 (무한 메모리 성장 없이 재사용 방지 유지).
- credential 노출 없음: ticket은 장기 bearer가 아니므로 유출되어도 노출 창이
  수 초이며, 재사용 불가다. 로그/audit에는 jti 전체를 남기지 않는다.
- Origin allowlist와의 조합: ticket 소비는 gate에서 Origin 검증 **뒤**에
  수행된다 (gate.py 참고) — cross-site 페이지는 ticket을 발급받을 수 없고,
  알아내도 origin이 맞지 않아 소비할 수 없다.

stdlib + PyJWT만 사용 (engine/auth.py와 동일 의존 수준).
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Final

import jwt

__all__ = [
    "WSTicketError",
    "WSTicketService",
    "get_ws_ticket_service",
    "reset_ws_ticket_service",
]

_TICKET_TYPE: Final[str] = "ws-ticket"

# 사용된 jti는 (만료시각 + 60s)까지 재사용 방지 목록에 남는다.
_REUSE_GRACE_SEC: Final[float] = 60.0


class WSTicketError(Exception):
    """ticket 발급/검증 실패."""


class WSTicketService:
    """단기 1회성 WS ticket 발급기/검증기.

    TokenService의 서명 secret을 공유해 같은 서버 프로세스에서 발급된
    bearer와 ticket의 무결성 기반을 일치시킨다.
    """

    def __init__(
        self,
        token_service: object,
        *,
        ttl_sec: float = 30.0,
    ) -> None:
        """token_service의 secret을 재사용하는 ticket 서비스를 만든다."""
        self._secret: str = token_service.secret  # type: ignore[attr-defined]
        self._ttl_sec = max(1.0, float(ttl_sec))
        self._lock = threading.Lock()
        # jti -> 만료시각(monotonic 기준 + grace). 1회성 판정용.
        self._used: dict[str, float] = {}

    @property
    def ttl_sec(self) -> float:
        """ticket 유효 시간(초)."""
        return self._ttl_sec

    def issue(self, subject: str) -> str:
        """인증된 subject에게 1회성 ticket을 발급한다."""
        now = time.time()
        payload: dict[str, object] = {
            "sub": subject,
            "iat": int(now),
            "exp": now + self._ttl_sec,
            "jti": secrets.token_urlsafe(16),
            "typ": _TICKET_TYPE,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def consume(self, ticket: str) -> str | None:
        """ticket을 검증하고 소비한다. 성공 시 subject, 실패 시 None.

        판정 순서: 서명/만료(jwt) → typ → 1회성(jti).
        성공한 소비만 jti를 사용 목록에 기록한다 — 실패한 ticket은
        재사용 목록을 오염시키지 않는다.
        """
        try:
            claims = jwt.decode(
                ticket,
                self._secret,
                algorithms=["HS256"],
                options={"require": ["exp", "iat", "sub", "jti"]},
            )
        except jwt.PyJWTError:
            return None
        if claims.get("typ") != _TICKET_TYPE:
            return None

        jti = claims.get("jti")
        subject = claims.get("sub")
        if not isinstance(jti, str) or not isinstance(subject, str) or not subject:
            return None

        now = time.monotonic()
        with self._lock:
            self._cleanup_locked(now)
            if jti in self._used:
                return None  # replay
            self._used[jti] = now + self._ttl_sec + _REUSE_GRACE_SEC
        return subject

    def _cleanup_locked(self, now: float) -> None:
        """만료 + grace를 지난 jti 항목을 제거한다 (lock 보유 필수)."""
        if len(self._used) < 64:
            return
        expired = [j for j, until in self._used.items() if until <= now]
        for j in expired:
            del self._used[j]

    def _used_count(self) -> int:
        """테스트 관찰용 — 사용 목록 크기."""
        with self._lock:
            return len(self._used)


_service: WSTicketService | None = None


def get_ws_ticket_service(token_service: object | None = None) -> WSTicketService:
    """공유 ticket 서비스 싱글톤. 최초 호출에 token_service가 필요하다."""
    global _service
    if _service is None:
        if token_service is None:
            from antigravity_k.api.auth_routes import get_token_service

            token_service = get_token_service()
        _service = WSTicketService(token_service)
    return _service


def reset_ws_ticket_service() -> None:
    """테스트용 — 싱글톤과 사용 목록을 초기화한다."""
    global _service
    _service = None
