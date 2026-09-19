from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import unsloth_studio_api
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.provider_adapters.unsloth_resource_broker import (
    UnslothResourceBroker,
)
from antigravity_k.engine.provider_adapters.unsloth_resource_contracts import (
    UnslothAdmissionRequest,
    UnslothArtifactProvenance,
    UnslothMemorySnapshot,
    UnslothResourceOperation,
)


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


@dataclass(frozen=True, slots=True)
class _MemoryProbe:
    def snapshot(self) -> UnslothMemorySnapshot:
        return UnslothMemorySnapshot(total_bytes=1_000, available_bytes=900)


def _request(idempotency_key: str) -> UnslothAdmissionRequest:
    return UnslothAdmissionRequest(
        idempotency_key=idempotency_key,
        operation=UnslothResourceOperation.TRAINING,
        device_id="unified:0",
        estimated_peak_bytes=100,
        artifact=UnslothArtifactProvenance(
            source_uri="hf://unsloth/Qwen3-Coder",
            revision="a" * 40,
            sha256="b" * 64,
        ),
    )


@contextmanager
def _client_for(broker: UnslothResourceBroker) -> Generator[TestClient, None, None]:
    app.dependency_overrides[unsloth_studio_api.get_unsloth_resource_broker] = lambda: broker
    try:
        with TestClient(app) as client:
            yield client
    finally:
        _ = app.dependency_overrides.pop(
            unsloth_studio_api.get_unsloth_resource_broker,
            None,
        )


def test_admission_api_accepts_a_safe_memory_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    audit = MagicMock()
    monkeypatch.setattr(unsloth_studio_api, "get_audit_logger", lambda: audit)

    with _client_for(broker) as client:
        response = client.post(
            "/v1/integrations/unsloth/resources/admissions",
            headers=_auth_headers(),
            json=_request("training-run-0001").model_dump(mode="json"),
        )

    assert response.status_code == 200
    assert response.json()["code"] == "accepted"
    assert response.json()["write_tools_enabled"] is False
    logged_details = audit.log_event.call_args.args[1]
    assert "idempotency_key" not in logged_details
    assert "source_uri" not in logged_details


def test_resource_status_api_returns_active_reservations(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    accepted = broker.admit(_request("api-status-run-001"))

    with _client_for(broker) as client:
        response = client.get("/v1/integrations/unsloth/resources", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["write_tools_enabled"] is False
    assert response.json()["active_reservations"][0]["reservation_id"] == accepted.reservation_id


def test_release_api_returns_released_reservation_and_safe_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    accepted = broker.admit(_request("api-release-run-01"))
    audit = MagicMock()
    monkeypatch.setattr(unsloth_studio_api, "get_audit_logger", lambda: audit)

    with _client_for(broker) as client:
        response = client.post(
            f"/v1/integrations/unsloth/resources/reservations/{accepted.reservation_id}/release",
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert response.json()["state"] == "released"
    assert response.json()["released_at"] is not None
    logged_details = audit.log_event.call_args.args[1]
    assert "idempotency_key" not in logged_details
    assert "provenance_fingerprint" not in logged_details


def test_release_api_returns_404_without_audit_for_an_unknown_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    audit = MagicMock()
    monkeypatch.setattr(unsloth_studio_api, "get_audit_logger", lambda: audit)

    with _client_for(broker) as client:
        response = client.post(
            "/v1/integrations/unsloth/resources/reservations/00000000-0000-0000-0000-000000000000/release",
            headers=_auth_headers(),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unsloth resource reservation was not found."
    audit.log_event.assert_not_called()


def test_admission_api_rejects_malformed_provenance_without_side_effects(tmp_path: Path) -> None:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    payload = _request("api-invalid-run-01").model_dump(mode="json")
    payload["artifact"]["revision"] = "main"

    with _client_for(broker) as client:
        response = client.post(
            "/v1/integrations/unsloth/resources/admissions",
            headers=_auth_headers(),
            json=payload,
        )

    assert response.status_code == 422
    assert broker.status().active_reservations == ()
