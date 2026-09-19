"""disclosure_api 테스트 — FastAPI 라우트 응답 검증."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from antigravity_k.api.routes.disclosure_api import get_cost_guard, router
from antigravity_k.engine.cost_guard import CostGuard


def _client(monkeypatch: pytest.MonkeyPatch, guard: CostGuard) -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_cost_guard] = lambda: guard
    return TestClient(app)


import pytest  # noqa: E402 — 위의 _client 정의 후 임포트 (FastAPI 지연)


def test_disclosure_endpoint_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True))
    response = client.get("/api/session/disclosure")
    assert response.status_code == 200
    payload: dict[str, Any] = response.json()
    assert payload["level"] in {"healthy", "warning", "exhausted"}
    assert isinstance(payload["limits"], list)
    assert "markdown" in payload


def test_disclosure_markdown_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True))
    response = client.get("/api/session/disclosure.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "세션 한도" in response.text


def test_disclosure_with_set_seeded_cost_guard() -> None:
    from fastapi import FastAPI

    from antigravity_k.api.routes.disclosure_api import set_seeded_cost_guard
    from antigravity_k.engine.session_disclosure import seed_cost_guard

    guard = CostGuard(daily_budget_usd=50.0, hourly_action_limit=100, enabled=True)
    seed_cost_guard(guard, seed_level="warning")
    set_seeded_cost_guard(guard)
    try:
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        res = client.get("/api/session/disclosure")
        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "warning"
        budget_limit = next(item for item in data["limits"] if item["kind"] == "budget")
        assert budget_limit["used"] == 44.0
    finally:
        set_seeded_cost_guard(None)


def test_disclosure_with_env_seed_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI

    from antigravity_k.api.routes.disclosure_api import set_seeded_cost_guard

    set_seeded_cost_guard(None)
    monkeypatch.setenv("AGK_SEED_BUDGET", "30%")
    monkeypatch.setenv("AGK_DAILY_BUDGET_USD", "50.0")
    monkeypatch.setenv("AGK_HOURLY_ACTION_LIMIT", "100")
    try:
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        res = client.get("/api/session/disclosure")
        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "healthy"
        budget_limit = next(item for item in data["limits"] if item["kind"] == "budget")
        assert budget_limit["used"] == 15.0
        assert budget_limit["usage_percent"] == 30.0
    finally:
        set_seeded_cost_guard(None)


def test_disclosure_with_env_seed_level_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI

    from antigravity_k.api.routes.disclosure_api import set_seeded_cost_guard

    set_seeded_cost_guard(None)
    monkeypatch.setenv("AGK_SEED_LEVEL", "exhausted")
    try:
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        res = client.get("/api/session/disclosure")
        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "exhausted"
    finally:
        set_seeded_cost_guard(None)


def test_cli_serve_and_dev_help() -> None:
    from typer.testing import CliRunner

    from antigravity_k.cli import app

    runner = CliRunner()
    result_serve = runner.invoke(app, ["serve", "--help"])
    assert result_serve.exit_code == 0
    assert "--seed-budget" in result_serve.output
    assert "--seed-level" in result_serve.output
    assert "--seed-actions" in result_serve.output

    result_dev = runner.invoke(app, ["dev", "--help"])
    assert result_dev.exit_code == 0
    assert "--seed-budget" in result_dev.output
    assert "--seed-level" in result_dev.output
    assert "--seed-actions" in result_dev.output


def test_cli_session_seeding() -> None:
    from typer.testing import CliRunner

    from antigravity_k.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["session", "--seed-budget", "30%"])
    assert result.exit_code == 0
    assert "15.00" in result.output
