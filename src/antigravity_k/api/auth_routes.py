"""Authentication API routes: login, token verify, logout.

Provides a token-exchange login flow on top of :mod:`antigravity_k.engine.auth`.
On first boot, the configured plaintext PIN is hashed and persisted so that
subsequent logins are verified against the hash (constant-time) rather than the
plaintext.

Routes
------
- ``POST /api/auth/login``  — exchange a PIN for a signed bearer token.
- ``POST /api/auth/verify`` — confirm a token is still valid.
- ``POST /api/auth/logout`` — informational; stateless tokens are client-revoked.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, ParamSpec, Protocol, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from antigravity_k.config import config
from antigravity_k.engine.auth import TokenService, hash_pin, verify_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Local limiter reference for the login route. The app-level limiter
# (registered in server.py via app.state.limiter) handles the SlowAPIMiddleware
# integration; per-route decorators reference a Limiter instance directly.
_P = ParamSpec("_P")
_R = TypeVar("_R")


class _RateLimitDecorator(Protocol):
    def __call__(self, function: Callable[_P, _R]) -> Callable[_P, _R]: ...


class _Limiter(Protocol):
    def limit(
        self,
        limit_value: str,
        key_func: Callable[..., str] | None = None,
        per_method: bool = False,
        methods: list[str] | None = None,
        error_message: str | None = None,
        exempt_when: Callable[..., bool] | None = None,
        cost: int | Callable[..., int] = 1,
        override_defaults: bool = True,
    ) -> _RateLimitDecorator: ...


_limiter: _Limiter = Limiter(key_func=get_remote_address)


def _rate_limit(limit_value: str) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    return _limiter.limit(limit_value)


# ---------------------------------------------------------------------------
# Shared state — initialized once at import time via :func:`init_auth_state`.
# ---------------------------------------------------------------------------

_token_service: TokenService | None = None
_pin_hash: str | None = None


def init_auth_state() -> None:
    """Initialize the token service and bootstrap the PIN hash.

    Idempotent: safe to call multiple times. On first call it:
      1. Creates the :class:`TokenService` using the configured secret path.
      2. Loads an existing PIN hash from ``pin_hash_file`` if present.
      3. Otherwise hashes the configured plaintext ``access_pin`` and persists
         it, so future logins verify against the hash.
    """
    global _token_service, _pin_hash

    if _token_service is not None:
        return

    _token_service = TokenService(
        secret_path=config.security.token_secret_file,
        token_ttl_hours=config.security.token_ttl_hours,
    )

    # SEC-01: 공유 AuthPolicy를 현재 config 바인딩으로 (재)초기화 —
    # HTTP/WS/상태 endpoint가 이 policy 객체 하나를 공유한다.
    from antigravity_k.api.auth_policy import init_shared_auth_policy

    _ = init_shared_auth_policy(config.security.pin_hash_file)

    hash_path = Path(config.security.pin_hash_file)
    if hash_path.exists():
        try:
            _pin_hash = hash_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            logger.warning("Could not read PIN hash from %s", hash_path)
            _pin_hash = None
        if _pin_hash is not None:
            try:
                hash_path.chmod(0o600)
            except OSError:
                logger.warning("Could not restrict PIN hash permissions on %s", hash_path)

    if _pin_hash is None and config.security.access_pin:
        # Bootstrap: hash the plaintext PIN and persist it.
        _pin_hash = hash_pin(config.security.access_pin)
        try:
            hash_path.parent.mkdir(parents=True, exist_ok=True)
            _ = hash_path.write_text(_pin_hash, encoding="utf-8")
            try:
                hash_path.chmod(0o600)
            except OSError:
                pass
            logger.info("Bootstrapped PIN hash at %s", hash_path)
        except OSError:
            logger.warning("Could not persist PIN hash to %s", hash_path)


def get_token_service() -> TokenService:
    """Return the singleton :class:`TokenService`, initializing if needed."""
    if _token_service is None:
        init_auth_state()
    assert _token_service is not None  # noqa: S101 — initialized above
    return _token_service


def get_current_pin_hash() -> str | None:
    """Return the active PIN hash (or None if auth is disabled)."""
    if _token_service is None:
        init_auth_state()
    return _pin_hash


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Login request body."""

    pin: str = Field(..., description="The access PIN.")


class TokenResponse(BaseModel):
    """Successful login response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class VerifyResponse(BaseModel):
    """Token verification response."""

    valid: bool
    subject: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
@_rate_limit("5/minute")
def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Exchange a PIN for a signed bearer token.

    SEC-02: PIN은 이 route(rate-limited)에서만 수용한다. 두 겹의 방어:
      1. slowapi — IP당 요청 레이트 제한 (429)
      2. credential_gate — 실패 burst/sustained 임계 초과 시 lockout (403).
         lockout 중에는 PBKDF2 검증을 실행하지 않아 공격이 CPU를 소진하지 못한다.
    모든 성공/실패/lockout은 credential 없이 audit에 기록된다.
    """
    from antigravity_k.security.auth_audit import record_auth_event
    from antigravity_k.security.credential_gate import get_credential_gate

    remote = request.client.host if request.client else "unknown"
    gate = get_credential_gate()
    gate_key = f"ip:{remote}"

    # 1단계: credential gate — lockout이면 PBKDF2로 진입하지 않는다.
    gate_decision = gate.register(gate_key)
    if not gate_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Too many failed attempts. Retry after {max(1, int(gate_decision.retry_after_sec))}s.",
            headers={"Retry-After": str(max(1, int(gate_decision.retry_after_sec)))},
        )

    stored = get_current_pin_hash()

    if stored is None:
        # No PIN configured — auth is effectively disabled.
        logger.warning("Login attempted with no PIN hash configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    if not verify_pin(body.pin, stored):
        decision = gate.record_failure(gate_key)
        logger.info("Failed login attempt from %s", remote)
        record_auth_event("login_failed", remote)
        if not decision.allowed:
            record_auth_event("lockout", remote, "failure threshold reached")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Too many failed attempts. Retry after {max(1, int(decision.retry_after_sec))}s.",
                headers={"Retry-After": str(max(1, int(decision.retry_after_sec)))},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    gate.record_success(gate_key)
    record_auth_event("login_success", remote)
    token = get_token_service().issue_token(subject="user")
    return TokenResponse(access_token=token, expires_in=get_token_service().ttl_seconds)


@router.post("/token", response_model=TokenResponse)
@_rate_limit("5/minute")
def token_login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """OAuth2-compatible token endpoint (password grant type).

    Swagger UI의 Authorize 버튼에서 사용됩니다.
    `username` 필드에 액세스 PIN을 입력하면 JWT 토큰을 반환합니다.
    `password` 필드는 무시됩니다 (자리 채움용).

    Returns:
        표준 OAuth2 token response: ``{"access_token": "...", "token_type": "bearer", "expires_in": ...}``
    """
    _ = request
    from antigravity_k.security.auth_audit import record_auth_event
    from antigravity_k.security.credential_gate import get_credential_gate

    remote = request.client.host if request.client else "unknown"
    gate = get_credential_gate()
    gate_key = f"ip:{remote}"
    gate_decision = gate.register(gate_key)
    if not gate_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Too many failed attempts. Retry after {max(1, int(gate_decision.retry_after_sec))}s.",
            headers={"Retry-After": str(max(1, int(gate_decision.retry_after_sec)))},
        )

    stored = get_current_pin_hash()
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    if not verify_pin(form_data.username, stored):
        decision = gate.record_failure(gate_key)
        record_auth_event("login_failed", remote)
        if not decision.allowed:
            record_auth_event("lockout", remote, "failure threshold reached")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Too many failed attempts. Retry after {max(1, int(decision.retry_after_sec))}s.",
                headers={"Retry-After": str(max(1, int(decision.retry_after_sec)))},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    gate.record_success(gate_key)
    record_auth_event("login_success", remote)
    token = get_token_service().issue_token(subject="user")
    return TokenResponse(
        access_token=token,
        expires_in=get_token_service().ttl_seconds,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_token(request: Request) -> VerifyResponse:
    """Verify a bearer token is still valid.

    Extracts the token from the Authorization header and checks its signature
    and expiration. Returns the validation result and the token subject.
    """
    token = _extract_bearer(request)
    if token is None:
        return VerifyResponse(valid=False, subject=None)

    claims = get_token_service().verify_token(token)
    if claims is None:
        return VerifyResponse(valid=False, subject=None)

    subject = claims.get("sub")
    return VerifyResponse(valid=True, subject=subject if isinstance(subject, str) else None)


@router.post("/logout")
def logout() -> dict[str, str]:
    """Logout endpoint.

    Tokens are stateless (signed JWTs), so the server cannot revoke them
    directly. The client must discard its token. This endpoint exists for API
    symmetry and future blocklist support.
    """
    return {"detail": "Token is stateless; discard it client-side to complete logout."}


class WSTicketResponse(BaseModel):
    """SEC-03 — 단기 1회성 WS ticket 발급 응답."""

    ticket: str
    expires_in: int


@router.post("/ws-ticket", response_model=WSTicketResponse)
def issue_ws_ticket(request: Request) -> WSTicketResponse:
    """인증된 세션에 단기(30초) 1회성 WebSocket ticket을 발급한다.

    SEC-03: browser WS 클라이언트는 장기 bearer를 URL에 실을 수 없다(로그/
    history 노출). 대신 이 endpoint(Bearer 인증 필요)에서 ticket을 받아
    ``?ticket=``로 단 한 번 사용한다. ticket은 재사용 불가이므로 유출되어도
    노출 창이 수 초다. 인증되지 않은 호출은 middleware가 차단한다(401).
    """
    from antigravity_k.security.ws_ticket import get_ws_ticket_service

    subject = getattr(request.state, "auth_subject", None)
    if not isinstance(subject, str) or not subject:
        subject = "bearer"
    service = get_ws_ticket_service(get_token_service())
    return WSTicketResponse(ticket=service.issue(subject), expires_in=int(service.ttl_sec))


@router.get("/status")
def auth_status() -> dict[str, object]:
    """SEC-01 상태 endpoint — UI 표시와 실제 인증이 같은 policy 소스를 쓴다.

    응답은 공유 AuthPolicy의 ``status()`` 그대로다:
      ``{protected, level, reason, dev_no_pin_allow}``
    PIN 변경/삭제/재시작 후 이 endpoint가 즉시 새 상태를 반영한다 (캐시 없음).
    """
    from antigravity_k.api.auth_policy import get_shared_auth_policy

    return get_shared_auth_policy().status()


# ---------------------------------------------------------------------------
# Helpers used by the middleware and the verify route
# ---------------------------------------------------------------------------


def _extract_bearer(request: Request) -> str | None:
    """Pull the bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _mark_authenticated(request: Request, subject: str) -> None:
    request.state.auth_subject = subject


def authenticate_request(request: Request) -> bool:
    """Return True if the request carries valid credentials.

    SEC-01 단일 정책: 판정은 공유 :class:`~antigravity_k.api.auth_policy.AuthPolicy`
    의 단일 진리표를 따른다 (HTTP/WS/상태 endpoint가 같은 객체를 사용). 구버전의
    "plaintext PIN 부재 시 loopback 익명 허용" 분기는 저장 hash를 무시하는
    결함이므로 제거되었다.

    SEC-02: **bearer 토큰만 수용한다** — raw PIN(X-Access-Pin 헤더/ag_access_pin
    쿠키)은 이 경로에서 PBKDF2 검증하지 않는다. PIN은 rate-limited
    ``/api/auth/login`` (또는 ``/api/auth/token``)에서만 토큰으로 교환된다.
    임의 보호 URL로 PIN 후보를 보내도 PBKDF2 비용이 발생하지 않는다.

    Checks, in order:
      1. A valid bearer token in the ``Authorization`` header.
      2. Anonymous access only when the shared policy resolves
         ``open_loopback`` (explicit dev allow + loopback + no credential).
      3. Everything else fails closed. Raw PIN headers/cookies are ignored
         here by design (SEC-02 credential surface reduction).
    """
    from antigravity_k.api.auth_policy import get_shared_auth_policy

    policy = get_shared_auth_policy()
    token = _extract_bearer(request)
    if token is not None:
        claims = get_token_service().verify_token(token)
        if claims is not None:
            subject = claims.get("sub")
            _mark_authenticated(request, subject if isinstance(subject, str) and subject else "bearer")
            return True

    # SEC-02: raw PIN 헤더/쿠키는 credential 표면에서 제거됐다 — verify_pin
    # (PBKDF2)은 rate-limited login/token route에서만 실행된다. 익명 허용은
    # 정책이 open_loopback으로 판정할 때만 가능하다 (SEC-01 fail-closed).
    decision = policy.resolve(host=config.server.host)
    if decision.level == "open_loopback":
        _mark_authenticated(request, "loopback")
        return True
    return False
    return False
