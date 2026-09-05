from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from antigravity_k.api.routes import operational_alerts
from antigravity_k.api.server import app
from antigravity_k.engine.operational_alert_store import OperationalAlertStore


def test_operational_alert_routes_are_registered() -> None:
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/alerts" in paths
    assert "/api/alerts/{alert_id}/acknowledge" in paths


def test_list_and_acknowledge_alerts(monkeypatch, tmp_path) -> None:
    store = OperationalAlertStore(tmp_path / "alerts.json")
    recorded = store.record("watchdog", "worker stalled", severity="critical")
    monkeypatch.setattr(operational_alerts, "_get_alert_store", lambda: store)
    test_app = FastAPI()
    test_app.include_router(operational_alerts.router)

    with TestClient(test_app) as client:
        listed = client.get("/api/alerts")
        assert listed.status_code == 200
        assert listed.json()[0]["alert_id"] == recorded.alert_id
        assert listed.json()[0]["severity"] == "critical"

        acknowledged = client.post(f"/api/alerts/{recorded.alert_id}/acknowledge")
        assert acknowledged.status_code == 200
        assert acknowledged.json() == {
            "alert_id": recorded.alert_id,
            "acknowledged": True,
        }

        assert client.get("/api/alerts").json() == []


def test_acknowledge_unknown_alert_returns_not_found(monkeypatch, tmp_path) -> None:
    store = OperationalAlertStore(tmp_path / "alerts.json")
    monkeypatch.setattr(operational_alerts, "_get_alert_store", lambda: store)
    test_app = FastAPI()
    test_app.include_router(operational_alerts.router)

    with TestClient(test_app) as client:
        response = client.post("/api/alerts/missing/acknowledge")

    assert response.status_code == 404
