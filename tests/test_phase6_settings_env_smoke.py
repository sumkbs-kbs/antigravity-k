"""Phase 6 — settings save smoke pointer (no live secrets / vault).

Documents the authenticated product path: ``POST /api/settings/env`` returns 200
under the allow gate. Deep contract coverage lives in
``tests/test_cr05_settings_secret_contract.py``; this file is a thin Phase 6
checklist tick that avoids real API keys.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import system_api
from antigravity_k.api.server import app


@pytest.fixture()
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    env_path = tmp_path / "phase6.env"
    monkeypatch.setattr(system_api, "_settings_project_root", lambda: str(tmp_path))
    monkeypatch.setenv("AGK_ENV_FILE", str(env_path))
    yield env_path


@pytest.fixture()
def client(env_file: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from antigravity_k.api import dependencies
    from antigravity_k.engine.model_manager import ModelManager

    manager = cast(Any, MagicMock(spec=ModelManager))
    manager.generate.return_value = "mock"
    manager.status.return_value = {"loaded_models": []}
    manager.router = MagicMock()

    app.dependency_overrides[dependencies.get_model_manager] = lambda: manager
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_settings_env_post_returns_200_without_live_secrets(client: TestClient, env_file: Path) -> None:
    """Smoke: allowlisted key write → 200; value is a canary, not a vault secret."""
    canary = "phase6-settings-smoke-canary-not-a-real-key"
    response = client.post("/api/settings/env", json={"OPENAI_API_KEY": canary})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("ok") is True
    assert canary not in response.text
    assert env_file.exists()
    stored = env_file.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" in stored
