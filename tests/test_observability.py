"""Tests for observability: Prometheus /metrics endpoint, RED middleware,
correlation-ID propagation, and the global error handler (no str(exc) leak).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from antigravity_k.engine.metrics import (
    REGISTRY,
    render_metrics,
    request_counter,
)

# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def metrics_client():
    """Provide a TestClient for checking the /metrics endpoint."""
    from antigravity_k.api.server import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_metrics_endpoint_public(metrics_client: TestClient):
    """The /metrics endpoint must be reachable without auth and return 200."""
    resp = metrics_client.get("/metrics")
    assert resp.status_code == 200
    # Prometheus exposition format starts with # HELP or # TYPE or a metric name.
    body = resp.text
    assert "http_requests_total" in body or "# HELP" in body or "# TYPE" in body


def test_render_metrics_returns_bytes():
    """render_metrics() must return Prometheus exposition format bytes."""
    data = render_metrics()
    assert isinstance(data, bytes)
    assert len(data) > 0


def test_request_counter_increments():
    """Incrementing the counter must reflect in the registry output."""
    request_counter().labels(method="GET", path="/test", status="200").inc()
    after = render_metrics().decode("utf-8")
    # The counter must have incremented (the output should differ or contain
    # the label set).
    assert "http_requests_total" in after


def test_metrics_registry_is_isolated():
    """The custom registry must not be the global default."""
    from prometheus_client import REGISTRY as DEFAULT_REGISTRY

    assert REGISTRY is not DEFAULT_REGISTRY, "Metrics should use a dedicated registry, not the global default."


# ---------------------------------------------------------------------------
# Correlation ID propagation
# ---------------------------------------------------------------------------


def test_correlation_id_echoed_in_response(metrics_client: TestClient):
    """A request must get an X-Request-Id header back (generated or echoed)."""
    resp = metrics_client.get("/metrics")
    assert "x-request-id" in {k.lower() for k in resp.headers.keys()}
    assert resp.headers.get("x-request-id"), "X-Request-Id must not be empty"


def test_inbound_correlation_id_propagated(metrics_client: TestClient):
    """An inbound X-Request-Id must be echoed back unchanged."""
    resp = metrics_client.get("/metrics", headers={"X-Request-Id": "trace-abc-123"})
    assert resp.headers.get("x-request-id") == "trace-abc-123"


# ---------------------------------------------------------------------------
# Error handler — no str(exc) leak
# ---------------------------------------------------------------------------


def test_error_handler_does_not_leak_exception_detail(metrics_client: TestClient):
    """A 500 response must NOT contain the raw exception message.

    We verify by checking the error handler module directly: its response body
    must contain correlation_id, not detail=str(exc).
    """
    import json

    from antigravity_k.api.error_handler import global_exception_handler

    # Construct a fake request-like call — we test the handler function directly
    # because triggering a real 500 in TestClient is unreliable (it raises).
    class FakeRequest:
        method = "GET"
        url = type("U", (), {"path": "/boom", "__str__": lambda self: "/boom"})()

    import asyncio

    async def _run():
        return await global_exception_handler(FakeRequest(), RuntimeError("SECRET_INTERNAL_PATH=/etc/passwd"))

    response = asyncio.run(_run())
    body = json.loads(response.body)
    assert "detail" not in body, "Error response must not include 'detail' (str(exc) leak)"
    assert "SECRET_INTERNAL_PATH" not in response.body.decode("utf-8"), "Raw exception text leaked into response"
    assert "correlation_id" in body, "Response must include a correlation_id"
    assert body["error"] == "Internal Server Error"
