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
from pathlib import Path

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
_limiter = Limiter(key_func=get_remote_address)


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

    hash_path = Path(config.security.pin_hash_file)
    if hash_path.exists():
        try:
            _pin_hash = hash_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            logger.warning("Could not read PIN hash from %s", hash_path)
            _pin_hash = None

    if _pin_hash is None and config.security.access_pin:
        # Bootstrap: hash the plaintext PIN and persist it.
        _pin_hash = hash_pin(config.security.access_pin)
        try:
            hash_path.parent.mkdir(parents=True, exist_ok=True)
            hash_path.write_text(_pin_hash, encoding="utf-8")
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
@_limiter.limit("5/minute")
def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Exchange a PIN for a signed bearer token.

    The PIN is verified against the stored PBKDF2 hash using a constant-time
    comparison. On success a JWT is issued; on failure a 401 is returned.
    Rate-limited via slowapi (configured at the application level).
    """
    stored = get_current_pin_hash()
    if stored is None:
        # No PIN configured — auth is effectively disabled.
        logger.warning("Login attempted with no PIN hash configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    if not verify_pin(body.pin, stored):
        logger.info("Failed login attempt from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    token = get_token_service().issue_token(subject="user")
    return TokenResponse(access_token=token, expires_in=get_token_service().ttl_seconds)


@router.post("/token", response_model=TokenResponse)
@_limiter.limit("5/minute")
def token_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """OAuth2-compatible token endpoint (password grant type).

    Swagger UI의 Authorize 버튼에서 사용됩니다.
    `username` 필드에 액세스 PIN을 입력하면 JWT 토큰을 반환합니다.
    `password` 필드는 무시됩니다 (자리 채움용).

    Returns:
        표준 OAuth2 token response: ``{"access_token": "...", "token_type": "bearer", "expires_in": ...}``
    """
    stored = get_current_pin_hash()
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    if not verify_pin(form_data.username, stored):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

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

    return VerifyResponse(valid=True, subject=claims.get("sub"))


@router.post("/logout")
def logout() -> dict[str, str]:
    """Logout endpoint.

    Tokens are stateless (signed JWTs), so the server cannot revoke them
    directly. The client must discard its token. This endpoint exists for API
    symmetry and future blocklist support.
    """
    return {"detail": "Token is stateless; discard it client-side to complete logout."}


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


def authenticate_request(request: Request) -> bool:
    """Return True if the request carries valid credentials.

    Checks, in order:
      1. A valid bearer token in the ``Authorization`` header.
      2. (Legacy compatibility) a valid PIN in the ``X-Access-Pin`` header or
         ``ag_access_pin`` cookie.

    This is the single source of truth used by the HTTP middleware so that
    token and legacy PIN auth share one code path.
    """
    token = _extract_bearer(request)
    if token is not None:
        if get_token_service().verify_token(token) is not None:
            return True

    # Legacy PIN compatibility (constant-time via verify_pin).
    pin = request.headers.get("X-Access-Pin") or request.cookies.get("ag_access_pin")
    if pin:
        stored = get_current_pin_hash()
        if stored and verify_pin(pin, stored):
            return True

    return False
