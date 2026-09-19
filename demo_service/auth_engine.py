"""JWT & HMAC Token Authentication Engine with Expiration Verification."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthTokenPayload:
    """Decoded JWT claims."""

    user_id: str
    roles: list[str]
    issued_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class SimpleJWTAuthEngine:
    """Lightweight deterministic HS256 JWT auth engine."""

    def __init__(self, secret_key: str = "ssak-ai-production-secret-999"):
        self.secret = secret_key.encode("utf-8")

    def issue_token(self, user_id: str, roles: list[str], ttl_seconds: float = 3600.0) -> str:
        """Create signed HS256 JWT token."""
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode("utf-8").rstrip("=")
        now = time.time()
        payload_data = {
            "user_id": user_id,
            "roles": roles,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        payload_bytes = json.dumps(payload_data).encode("utf-8")
        payload = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

        signing_input = f"{header}.{payload}".encode("utf-8")
        signature = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        sig_encoded = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

        return f"{header}.{payload}.{sig_encoded}"

    def verify_token(self, token: str) -> AuthTokenPayload | None:
        """Verify signature and expiration."""
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header, payload, sig_str = parts
        signing_input = f"{header}.{payload}".encode("utf-8")
        expected_sig = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        expected_sig_str = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

        if not hmac.compare_digest(sig_str, expected_sig_str):
            return None

        # Decode payload
        try:
            # Re-add padding
            pad = len(payload) % 4
            padded_payload = payload + "=" * (4 - pad if pad != 0 else 0)
            data = json.loads(base64.urlsafe_b64decode(padded_payload.encode("utf-8")))

            payload_obj = AuthTokenPayload(
                user_id=data["user_id"],
                roles=data.get("roles", []),
                issued_at=data["iat"],
                expires_at=data["exp"],
            )

            return None if payload_obj.is_expired else payload_obj
        except Exception:
            return None
