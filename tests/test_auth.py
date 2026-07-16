"""Tests for the authentication system: PIN hashing, JWT tokens, login flow,
middleware coverage, rate limiting, and WebSocket auth.

These cover the Priority #2 hardening:
- PBKDF2 PIN hashing with constant-time verification.
- JWT issuance / verification (expiry, tampering).
- /api/auth/login token exchange with rate limiting.
- Middleware coverage over /api/, /v1/, and WebSocket paths.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.auth import (
    TokenService,
    extract_bearer_token,
    hash_pin,
    verify_pin,
)

# ---------------------------------------------------------------------------
# Unit tests: PIN hashing
# ---------------------------------------------------------------------------


def test_hash_and_verify_pin_roundtrip():
    """A PIN hashed then verified with the same PIN must succeed."""
    stored = hash_pin("my-secret-pin")
    assert verify_pin("my-secret-pin", stored) is True


def test_verify_pin_wrong_pin():
    """A wrong PIN must not verify."""
    stored = hash_pin("correct-pin")
    assert verify_pin("wrong-pin", stored) is False


def test_verify_pin_malformed_stored():
    """A malformed stored hash must reject (return False), not crash."""
    assert verify_pin("anything", "not-a-valid-hash") is False
    assert verify_pin("anything", "") is False
    assert verify_pin("anything", "pbkdf2_sha256$abc$def") is False  # too few parts


def test_verify_pin_constant_time():
    """Correct and incorrect PINs should take similar time (within tolerance).

    This is a best-effort timing test: we measure verify_pin for a correct and
    incorrect PIN and assert the ratio is within a generous bound. We are not
    trying to detect nanosecond leaks, only gross timing-channel regressions.
    """
    stored = hash_pin("timing-test-pin")

    # Warm up.
    for _ in range(5):
        verify_pin("timing-test-pin", stored)
        verify_pin("wrong", stored)

    # Measure. 10 iterations is enough to detect gross timing channels
    # while keeping the test under 1 second (PBKDF2 600K is ~100ms/verify).
    t_correct_start = time.perf_counter()
    for _ in range(10):
        verify_pin("timing-test-pin", stored)
    t_correct = time.perf_counter() - t_correct_start

    t_wrong_start = time.perf_counter()
    for _ in range(10):
        verify_pin("wrong", stored)
    t_wrong = time.perf_counter() - t_wrong_start

    # The two should be in the same ballpark. PBKDF2 dominates, so the ratio
    # should be close to 1.0. Allow up to 2.5x for noise.
    ratio = max(t_correct, t_wrong) / max(min(t_correct, t_wrong), 1e-9)
    assert ratio < 2.5, f"Timing ratio {ratio:.2f} exceeds threshold (timing channel?)"


# ---------------------------------------------------------------------------
# Unit tests: JWT tokens
# ---------------------------------------------------------------------------


def test_issue_and_verify_token():
    """An issued token must verify and carry expected claims."""
    ts = TokenService(secret_path=None, token_ttl_hours=1)
    token = ts.issue_token(subject="user-123")
    claims = ts.verify_token(token)
    assert claims is not None
    assert claims["sub"] == "user-123"
    assert "exp" in claims
    assert "iat" in claims


def test_verify_expired_token():
    """An expired token must not verify."""
    ts = TokenService(secret_path=None, token_ttl_hours=1)
    # Manually craft an expired token using the same secret.
    import jwt

    import antigravity_k.engine.auth as auth_mod

    past_exp = {"sub": "user", "exp": 0, "iat": 0, "iss": auth_mod._JWT_ISSUER}
    expired_token = jwt.encode(past_exp, ts.secret, algorithm=auth_mod._JWT_ALGORITHM)
    assert ts.verify_token(expired_token) is None


def test_verify_tampered_token():
    """A token with a modified payload must not verify."""
    ts = TokenService(secret_path=None, token_ttl_hours=1)
    token = ts.issue_token(subject="user")
    # Flip a character in the signature portion.
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    assert ts.verify_token(tampered) is None


def test_token_secret_persistence(tmp_path: Path):
    """A persisted secret must be reusable across TokenService instances."""
    secret_file = tmp_path / "secret"
    ts1 = TokenService(secret_path=secret_file, token_ttl_hours=1)
    token = ts1.issue_token(subject="user")

    # New instance loading the same file must verify the token.
    ts2 = TokenService(secret_path=secret_file, token_ttl_hours=1)
    assert ts2.verify_token(token) is not None


def test_extract_bearer_token():
    """Bearer token extraction from header strings."""
    assert extract_bearer_token("Bearer abc123") == "abc123"
    assert extract_bearer_token("bearer xyz") == "xyz"
    assert extract_bearer_token(None) is None
    assert extract_bearer_token("Basic abc") is None
    assert extract_bearer_token("Bearer") is None
    assert extract_bearer_token("Bearer ") is None


# ---------------------------------------------------------------------------
# Integration tests: login flow + middleware (via TestClient)
# ---------------------------------------------------------------------------

# We use a module-scoped client to avoid re-creating the app (which triggers
# subsystem startup) for every test. The PIN is fixed for deterministic login.


@pytest.fixture(scope="module")
def auth_client(tmp_path_factory):
    """Provide a TestClient with a known PIN and temp secret storage.

    We mutate the config *instance* directly (Pydantic Settings fields are not
    class-level attributes that ``patch.object`` can replace) and reset the
    auth module state so it re-bootstraps with the test PIN.
    """
    from antigravity_k.config import config

    tmpdir = tmp_path_factory.mktemp("auth_test")

    # Save originals so we can restore after the module-scoped fixture ends.
    orig_pin = config.security.access_pin
    orig_hash_file = config.security.pin_hash_file
    orig_secret_file = config.security.token_secret_file

    # Mutate the live config instance.
    config.security.access_pin = "test-pin-1234"
    config.security.pin_hash_file = str(tmpdir / "auth_hash")
    config.security.token_secret_file = str(tmpdir / "token_secret")

    # Reset auth module state so it re-bootstraps with the patched config.
    import antigravity_k.api.auth_routes as auth_routes_mod

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()

    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    # Restore originals.
    config.security.access_pin = orig_pin
    config.security.pin_hash_file = orig_hash_file
    config.security.token_secret_file = orig_secret_file


def _login(client: TestClient, pin: str = "test-pin-1234") -> dict:
    """Helper: perform login and return the response JSON."""
    resp = client.post("/api/auth/login", json={"pin": pin})
    return resp


def test_login_correct_pin(auth_client: TestClient):
    """Login with the correct PIN must return a token."""
    resp = _login(auth_client)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_wrong_pin(auth_client: TestClient):
    """Login with a wrong PIN must return 401."""
    resp = _login(auth_client, pin="wrong-pin")
    assert resp.status_code == 401


def test_protected_route_without_token(auth_client: TestClient):
    """A protected /api/ route without a token must return 401."""
    resp = auth_client.get("/api/vault/config")
    assert resp.status_code == 401


def test_protected_route_with_valid_token(auth_client: TestClient):
    """A protected /api/ route with a valid token must succeed (or 503 if the
    vault engine is not configured — but NOT 401)."""
    token = _login(auth_client).json()["access_token"]
    resp = auth_client.get("/api/vault/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code != 401, "Valid token was rejected"


def test_v1_chat_protected(auth_client: TestClient):
    """The /v1/chat/completions endpoint must now be protected (was open)."""
    resp = auth_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401, "/v1/ path was not protected by auth middleware"


def test_health_endpoints_public(auth_client: TestClient):
    """Health endpoints must remain accessible without a token."""
    for path in ("/health", "/v1/health"):
        resp = auth_client.get(path)
        # 200 or 404 (if not registered in this test context) — but NOT 401.
        assert resp.status_code != 401, f"{path} should be public, got 401"


def test_legacy_pin_header_still_works(auth_client: TestClient):
    """The legacy X-Access-Pin header must still authenticate (migration path)."""
    resp = auth_client.get("/api/vault/config", headers={"X-Access-Pin": "test-pin-1234"})
    assert resp.status_code != 401, "Legacy PIN header was rejected"


def test_login_rate_limited(auth_client: TestClient):
    """After 5 failed logins within a minute, the 6th must be rate-limited (429).

    slowapi tracks limits per-IP; TestClient uses a local test client address.
    We send wrong-PIN attempts to exhaust the /api/auth/login limit.
    """
    statuses = []
    for _ in range(7):
        resp = auth_client.post("/api/auth/login", json={"pin": "wrong"})
        statuses.append(resp.status_code)

    # We expect at least one 429 (rate limited) within the 7 attempts.
    assert 429 in statuses, f"Expected rate limiting (429) but got statuses: {statuses}"


def test_verify_endpoint(auth_client: TestClient):
    """The /api/auth/verify endpoint must confirm a valid token.

    We issue a token directly via the TokenService (rather than calling /login
    again) to avoid exhausting the per-minute login rate limit shared across
    tests in this module.
    """
    from antigravity_k.api.auth_routes import get_token_service

    token = get_token_service().issue_token(subject="verify-test")
    resp = auth_client.post("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
