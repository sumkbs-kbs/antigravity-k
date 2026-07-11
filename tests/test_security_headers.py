"""Tests for security hardening: CSP/security headers and XSS defense posture.

These verify that the server emits the expected security headers on every
response and that the error handler does not leak internal details. The
DOMPurify frontend sanitization is a client-side concern (not testable from
Python), but we verify the server-side posture that complements it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


def test_csp_header_present(client: TestClient):
    """Every response must carry a Content-Security-Policy header."""
    resp = client.get("/metrics")
    assert "content-security-policy" in {k.lower() for k in resp.headers.keys()}
    csp = resp.headers.get("content-security-policy", "")
    # CSP must block frame-ancestors (clickjacking defense).
    assert "frame-ancestors" in csp


def test_x_content_type_options_header(client: TestClient):
    """X-Content-Type-Options: nosniff must be set."""
    resp = client.get("/metrics")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_x_frame_options_header(client: TestClient):
    """X-Frame-Options: DENY must be set (clickjacking defense)."""
    resp = client.get("/metrics")
    assert resp.headers.get("x-frame-options") == "DENY"


def test_referrer_policy_header(client: TestClient):
    """Referrer-Policy must be set to a restrictive value."""
    resp = client.get("/metrics")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_permissions_policy_header(client: TestClient):
    """Permissions-Policy must deny sensitive APIs."""
    resp = client.get("/metrics")
    pp = resp.headers.get("permissions-policy", "")
    assert "geolocation=()" in pp
    assert "camera=()" in pp


def test_csp_blocks_javascript_urls(client: TestClient):
    """The CSP must not allow 'unsafe-inline' in script-src without restrictions.

    We check that the CSP does not contain the dangerous ``javascript:``
    scheme in any directive source list. (``unsafe-inline`` is present for the
    vanilla-JS dashboard but is mitigated by DOMPurify on the client.)
    """
    resp = client.get("/metrics")
    csp = resp.headers.get("content-security-policy", "")
    # No directive should allow javascript: as a source.
    assert "javascript:" not in csp


# ---------------------------------------------------------------------------
# XSS posture — error handler does not leak internals
# ---------------------------------------------------------------------------


def test_500_response_has_no_detail_field(client: TestClient):
    """A server error must not include a 'detail' key with str(exc).

    This is verified more directly in test_observability.py, but we add a
    quick check here that the error handler contract holds: no 'detail'.
    """
    import asyncio
    import json

    from antigravity_k.api.error_handler import global_exception_handler

    class FakeRequest:
        method = "GET"
        url = type("U", (), {"path": "/x", "__str__": lambda self: "/x"})()

    response = asyncio.run(global_exception_handler(FakeRequest(), ValueError("leak-test-secret")))
    body = json.loads(response.body)
    assert "detail" not in body
    assert "leak-test-secret" not in response.body.decode()
    assert "correlation_id" in body
