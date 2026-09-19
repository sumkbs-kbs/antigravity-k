"""Tests for the unified agent ask API route."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.unified_agent import AgentOutcome, AgentStep


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


def test_agent_ask_endpoint_standard() -> None:
    client = TestClient(app)
    mock_outcome = AgentOutcome(
        task="What is asyncio?",
        answer="Asyncio is a concurrency library.",
        steps=[AgentStep(action="answer", detail="direct")],
        used_web=False,
        used_graphify=False,
        total_seconds=0.5,
    )

    with patch("antigravity_k.engine.unified_agent.UnifiedAgent.run", return_value=mock_outcome):
        response = client.post(
            "/api/agent/ask",
            json={"task": "What is asyncio?"},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["task"] == "What is asyncio?"
    assert data["answer"] == "Asyncio is a concurrency library."
    assert data["mode"] == "standard"
    assert data["steps"] == 1


def test_agent_ask_endpoint_adaptive_with_test_code() -> None:
    client = TestClient(app)
    mock_outcome = AgentOutcome(
        task="Write a counter",
        answer="class Counter:\n    pass",
        steps=[AgentStep(action="code+repair(0)", detail="passed")],
        used_web=False,
        used_graphify=True,
        total_seconds=1.2,
        passed=True,
    )

    with patch("antigravity_k.engine.unified_agent.UnifiedAgent.run", return_value=mock_outcome):
        response = client.post(
            "/api/agent/ask",
            json={
                "task": "Write a counter",
                "test_code": "def test_counter(): pass",
                "adaptive": True,
            },
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["mode"] == "adaptive"
    assert data["used_graphify"] is True
