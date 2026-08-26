"""테스트: Models/Health/Wake/Embeddings + System Status·Restart 계약.
==========================================================
legacy에서 추출·귀속된 엔드포인트의 응답 구조와 권한 게이트를 검증한다.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from antigravity_k.api.routes import models_api, system_api
from antigravity_k.api.server import app
from antigravity_k.config import config


@pytest.fixture
def client():
    headers = {"X-Access-Pin": config.security.access_pin}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(headers)
        yield test_client


def _fake_manager():
    profile = SimpleNamespace(
        name="qwen3-test",
        role="reasoning",
        description="테스트용",
        routing_metadata=lambda: {"tier": 1},
    )
    manager = MagicMock()
    manager._registry.list_models.return_value = [profile]
    manager.provider_capabilities.return_value = {"qwen3-test": {"native_tools": True}}
    manager.router.status.return_value = {"quality_calibration": {"score": 0.9}}
    manager.tracker.get_total_tokens.return_value = 4242
    return manager


# ─── Models/Health/Wake (models_api) ─────────────────────────────


class TestModelsApi:
    def test_health_reports_version_and_backend_shape(self, client, monkeypatch):
        manager = MagicMock()
        manager.status.return_value = {"loaded_models": {"m1": {}}}
        monkeypatch.setattr(models_api, "get_model_manager", lambda: manager)
        monkeypatch.setattr(models_api, "get_orchestrator", lambda: None)

        body = client.get("/v1/health").json()

        assert body["status"] == "ok"
        assert isinstance(body["version"], str)
        assert body["backends"] == {"m1": {}}
        assert body["cov_active"] is False

    def test_wake_submits_background_task(self, client, monkeypatch):
        runtime = SimpleNamespace(submit_task=lambda **kw: "task_777")
        monkeypatch.setattr(models_api, "get_agent_runtime", lambda: runtime)

        body = client.post(
            "/api/agent/wake",
            json={"event_type": "lint_error", "payload": {"file": "a.py"}},
        ).json()

        assert body["status"] == "woken"
        assert body["task_id"] == "task_777"
        assert "lint_error" in body["message"]

    def test_v1_models_openai_shape(self, client):
        manager = _fake_manager()
        client.app.dependency_overrides[models_api.get_model_manager] = lambda: manager
        try:
            body = client.get("/v1/models").json()
        finally:
            client.app.dependency_overrides.clear()

        assert body["object"] == "list"
        model = body["data"][0]
        assert model["id"] == "qwen3-test"
        assert model["object"] == "model"
        assert model["owned_by"] == "system"
        assert model["provider_capability"] == {"native_tools": True}

    def test_model_operations_refresh_passthrough(self, client):
        manager = _fake_manager()
        client.app.dependency_overrides[models_api.get_model_manager] = lambda: manager
        try:
            body = client.get("/v1/models/operations", params={"refresh": True}).json()
        finally:
            client.app.dependency_overrides.clear()

        assert body["quality_calibration"]["score"] == 0.9
        manager.provider_capabilities.assert_called_with(refresh=True)

    def test_embeddings_usage_and_error(self, client):
        engine = MagicMock()
        engine.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
        client.app.dependency_overrides[models_api.get_embedding_engine] = lambda: engine

        ok = client.post("/v1/embeddings", json={"input": ["aaaa", "bb"], "model": "e"}).json()
        assert ok["usage"]["prompt_tokens"] == 1  # 4//4 + 2//4
        assert ok["data"][1]["index"] == 1

        engine.embed.side_effect = ValueError("차원 불일치")
        try:
            err = client.post("/v1/embeddings", json={"input": ["x"], "model": "e"})
        finally:
            client.app.dependency_overrides.clear()
        assert err.status_code == 500


# ─── System status/restart (system_api 귀속분) ───────────────────


class TestSystemStatusRestart:
    def test_status_reports_uptime_and_tokens(self, client, monkeypatch):
        fake_psutil = SimpleNamespace(
            virtual_memory=lambda: SimpleNamespace(percent=41.5),
            cpu_percent=lambda interval=0: 12.0,
            Error=Exception,
        )
        monkeypatch.setattr(system_api.psutil, "virtual_memory", fake_psutil.virtual_memory)
        monkeypatch.setattr(system_api.psutil, "cpu_percent", fake_psutil.cpu_percent)

        import antigravity_k.api.dependencies as deps

        manager = _fake_manager()
        monkeypatch.setattr(deps, "get_model_manager", lambda: manager)

        body = client.get("/api/system/status").json()

        assert body["ok"] is True and body["status"] == "online"
        assert body["total_tokens"] == 4242
        assert body["uptime_seconds"] >= 0

    def test_restart_requires_critical_permission(self, client, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        denied = HTTPException(status_code=403, detail="denied")
        monkeypatch.setattr(system_api, "_require_allowed", lambda *a, **k: (_ for _ in ()).throw(denied))

        response = client.post("/api/system/restart")

        assert response.status_code == 403

    def test_restart_schedules_trigger_file(self, client, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(system_api, "_require_allowed", lambda *a, **k: None)

        body = client.post("/api/system/restart").json()

        assert body["ok"] is True
        assert "reboot" in body["message"]
