"""Authentication primitives: PIN hashing, JWT token issuance/verification.

This module provides the crypto layer for the API auth system. It is
deliberately self-contained (no FastAPI/Starlette imports) so it can be unit
tested in isolation and reused by both HTTP middleware and WebSocket handlers.

Design notes
------------
- PIN hashing uses PBKDF2-HMAC-SHA256 with a per-hash random salt and 600,000
  iterations (OWASP 2023 guidance). The format is compatible with common
  ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`` strings.
- All comparisons are constant-time via :func:`hmac.compare_digest`.
- Tokens are HS256-signed JWTs. The signing secret is generated once and
  persisted to a file so tokens survive a server restart; if the file cannot
  be written an ephemeral in-memory secret is used (tokens then do not survive
  restart, which is the safe default).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jwt

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

# PBKDF2 parameters (OWASP 2023 recommendation for SHA-256).
_PBKDF2_ITERATIONS = 600_000
_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_HASH_DIGEST_SIZE = 32  # SHA-256 output length in bytes

# Default token lifetime, overridable by the caller.
DEFAULT_TOKEN_TTL_HOURS = 12

# JWT configuration.
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER = "antigravity-k"

# File permissions for the persisted signing secret (owner read/write only).
_SECRET_FILE_MODE = 0o600


class AuthError(Exception):
    """Base class for authentication errors."""


def hash_pin(pin: str, *, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Hash a PIN using PBKDF2-HMAC-SHA256 with a random salt.

    Args:
        pin: The plaintext PIN to hash.
        iterations: PBKDF2 iteration count (default 600,000).

    Returns:
        A string of the form ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``.

    """
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, _HASH_DIGEST_SIZE)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"{_PBKDF2_ALGORITHM}${iterations}${salt_b64}${hash_b64}"


def verify_pin(pin: str, stored: str) -> bool:
    """Verify a plaintext PIN against a stored hash.

    Uses constant-time comparison to mitigate timing attacks. Returns ``False``
    for any malformed stored value rather than raising, so callers can treat
    "no valid hash" and "wrong PIN" identically.

    Args:
        pin: The plaintext PIN to check.
        stored: The stored hash string (as produced by :func:`hash_pin`).

    Returns:
        True if the PIN matches, False otherwise (including malformed stored).

    """
    try:
        algorithm, iters_str, salt_b64, hash_b64 = stored.split("$", 3)
    except ValueError:
        logger.warning("Malformed stored PIN hash; rejecting login.")
        return False

    if algorithm != _PBKDF2_ALGORITHM:
        logger.warning("Unknown PIN hash algorithm '%s'; rejecting login.", algorithm)
        return False

    try:
        iterations = int(iters_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, binascii.Error):
        logger.warning("Corrupt PIN hash components; rejecting login.")
        return False

    derived = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations, dklen=len(expected))
    # Constant-time comparison of the raw bytes.
    return hmac.compare_digest(derived, expected)


def generate_token_secret() -> str:
    """Generate a cryptographically random signing secret for JWTs.

    Returns:
        A URL-safe base64 string with ~512 bits of entropy.

    """
    return secrets.token_urlsafe(64)


class TokenService:
    """Issue and verify HS256 JWT access tokens.

    The signing secret is loaded from (or written to) ``secret_path`` so that
    tokens remain valid across server restarts. The class is thread-safe.
    """

    def __init__(
        self,
        secret_path: str | Path | None = None,
        *,
        token_ttl_hours: int = DEFAULT_TOKEN_TTL_HOURS,
    ):
        """Initialize the token service, loading or creating the signing secret.

        Args:
            secret_path: Optional path to persist the signing secret. If the
                file exists its content is loaded; otherwise a new secret is
                generated and (best-effort) written there.
            token_ttl_hours: Token lifetime in hours.

        """
        self._ttl = timedelta(hours=token_ttl_hours)
        self._lock = threading.Lock()
        self._secret = self._load_or_create_secret(secret_path)

    @staticmethod
    def _load_or_create_secret(secret_path: str | Path | None) -> str:
        """Return a signing secret, persisting a new one if none exists."""
        if secret_path is None:
            return generate_token_secret()

        path = Path(secret_path)
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    return content
        except OSError:
            logger.warning("Could not read token secret from %s; generating new one.", path)

        # Generate a fresh secret and persist it.
        new_secret = generate_token_secret()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write with restricted permissions.
            fd = path.open("w", encoding="utf-8")
            with fd:
                fd.write(new_secret)
            try:
                path.chmod(_SECRET_FILE_MODE)
            except OSError:
                pass  # chmod may fail on some platforms/setups; non-fatal.
            logger.info("Generated and persisted new JWT signing secret at %s", path)
        except OSError:
            logger.warning("Could not persist token secret to %s; using ephemeral secret.", path)
        return new_secret

    @property
    def secret(self) -> str:
        """The signing secret (exposed for testing)."""
        return self._secret

    @property
    def ttl_seconds(self) -> int:
        """Token lifetime in seconds."""
        return int(self._ttl.total_seconds())

    def issue_token(self, subject: str, *, extra_claims: dict[str, Any] | None = None) -> str:
        """Issue a signed JWT for ``subject``.

        Args:
            subject: The subject claim (e.g. ``"user"`` or a client id).
            extra_claims: Optional additional claims to include.

        Returns:
            The encoded JWT string.

        """
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": subject,
            "iat": now,
            "exp": now + self._ttl,
            "iss": _JWT_ISSUER,
        }
        if extra_claims:
            payload.update(extra_claims)
        with self._lock:
            return jwt.encode(payload, self._secret, algorithm=_JWT_ALGORITHM)

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify a JWT's signature and expiry.

        Args:
            token: The encoded JWT string.

        Returns:
            The decoded claims dict on success, or ``None`` if the token is
            invalid, expired, or tampered with.

        """
        try:
            with self._lock:
                claims = jwt.decode(
                    token,
                    self._secret,
                    algorithms=[_JWT_ALGORITHM],
                    issuer=_JWT_ISSUER,
                    options={"require": ["exp", "iat", "sub"]},
                )
            return claims
        except jwt.PyJWTError as e:
            logger.debug("Token verification failed: %s", e)
            return None


def extract_bearer_token(authorization_header: str | None) -> str | None:
    """Extract a bearer token from an ``Authorization`` header value.

    Args:
        authorization_header: The raw header value (may be None).

    Returns:
        The token string, or None if the header is absent or malformed.

    """
    if not authorization_header:
        return None
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def extract_token_from_ws(websocket: "WebSocket") -> str | None:
    """Extract an auth token from a WebSocket connection.

    Browsers cannot set custom headers on WebSocket handshakes, so we accept
    the token from either a ``token`` query parameter or (preferably) the
    ``Sec-WebSocket-Protocol`` subprotocol. A ``pin`` query parameter is also
    accepted for backwards compatibility with legacy PIN auth.

    Args:
        websocket: The inbound WebSocket connection.

    Returns:
        The token or PIN string, or None if none was provided.

    """
    # Query parameter (primary for browser WS clients).
    token = websocket.query_params.get("token")
    if token:
        return token
    pin = websocket.query_params.get("pin")
    if pin:
        return pin
    # Subprotocol header (set by non-browser clients).
    protocols = websocket.headers.get("sec-websocket-protocol")
    if protocols:
        for proto in protocols.split(","):
            candidate = proto.strip()
            if candidate.startswith("bearer."):
                return candidate[len("bearer.") :]
    return None
