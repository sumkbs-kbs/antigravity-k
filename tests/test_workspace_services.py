"""작업공간 서비스 레지스트리와 결정적 프록시 주소 계약."""

import sys
from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.routes import workspace_services
from antigravity_k.api.server import app
from antigravity_k.engine.workspace_service_registry import (
    ServiceConflictError,
    WorkspaceServiceRegistry,
    build_service_hostname,
)
from antigravity_k.engine.workspace_service_runtime import ServiceProcessError, WorkspaceServiceRuntime


@pytest.fixture
def client() -> Iterator[TestClient]:
    from antigravity_k.config import config

    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update({"X-Access-Pin": config.security.access_pin})
        workspace_services.get_service_runtime().stop_all()
        workspace_services.get_service_registry().clear()
        yield test_client
        workspace_services.get_service_runtime().stop_all()
        workspace_services.get_service_registry().clear()


def test_hostname_is_dns_safe_and_deterministic() -> None:
    # Given: service metadata contains branch separators and mixed case.
    first = build_service_hostname("API", "feature/login", "Demo Project")

    # When: the same metadata is normalized again.
    second = build_service_hostname("api", "feature-login", "demo-project")

    # Then: both addresses are stable, lowercase, and localhost-scoped.
    assert first == second
    assert first.endswith(".localhost")
    assert len(first.removesuffix(".localhost")) <= 63
    assert all(char.islower() or char.isdigit() or char in ".-" for char in first)


def test_registry_rejects_hostname_collision() -> None:
    # Given: two registrations resolve to the same DNS identity.
    registry = WorkspaceServiceRegistry()
    _ = registry.register("api", "main", "demo", 4312)

    # When/Then: a different port cannot silently replace the service.
    with pytest.raises(ServiceConflictError):
        _ = registry.register("api", "main", "demo", 4313)


def test_service_api_registers_lists_and_changes_state(client: TestClient) -> None:
    # When: a workspace service is registered through the authenticated API.
    created = client.post(
        "/api/workspace/services",
        json={"service": "api", "branch": "feature/login", "project": "demo", "port": 4312},
    )

    # Then: the response exposes deterministic HTTP and WebSocket entrypoints.
    assert created.status_code == 201
    body = cast(dict[str, object], created.json())
    hostname = cast(str, body["hostname"])
    assert hostname == "api--feature-login--demo.localhost"
    assert body["http_url"] == f"http://{hostname}/api/workspace/services/{hostname}/proxy"
    assert body["websocket_url"] == f"ws://{hostname}/api/workspace/services/{hostname}/ws"

    listed = client.get("/api/workspace/services")
    assert listed.status_code == 200
    assert len(cast(list[object], listed.json())) == 1

    stopped = client.patch(
        f"/api/workspace/services/{hostname}",
        json={"status": "stopped"},
    )
    assert stopped.status_code == 200
    assert cast(dict[str, object], stopped.json())["status"] == "stopped"


def test_service_api_rejects_non_loopback_target(client: TestClient) -> None:
    # When: a caller tries to register a public upstream target.
    response = client.post(
        "/api/workspace/services",
        json={
            "service": "api",
            "branch": "main",
            "project": "demo",
            "host": "example.com",
            "port": 4312,
        },
    )

    # Then: the registry keeps the proxy boundary local-only.
    assert response.status_code == 422


def test_service_api_manages_process_lifecycle(client: TestClient) -> None:
    # Given: a service registration contains a real long-running local command.
    created = client.post(
        "/api/workspace/services",
        json={
            "service": "worker",
            "branch": "main",
            "project": "demo",
            "port": 4313,
            "status": "stopped",
            "command": [sys.executable, "-c", "import time; time.sleep(60)"],
        },
    )
    assert created.status_code == 201
    hostname = cast(str, cast(dict[str, object], created.json())["hostname"])

    # When: the lifecycle endpoints start and then stop that process.
    started = client.post(f"/api/workspace/services/{hostname}/start")
    started_health = client.get(f"/api/workspace/services/{hostname}/health")
    stopped = client.post(f"/api/workspace/services/{hostname}/stop")

    # Then: registry state and process health reflect both transitions.
    assert started.status_code == 200
    assert cast(dict[str, object], started.json())["status"] == "ready"
    assert started_health.status_code == 200
    started_health_body = cast(dict[str, object], started_health.json())
    assert started_health_body["status"] == "ready"
    assert started_health_body["managed"] is True
    assert started_health_body["process_running"] is True
    assert isinstance(started_health_body["process_id"], int)
    assert stopped.status_code == 200
    assert cast(dict[str, object], stopped.json())["status"] == "stopped"
    stopped_health = client.get(f"/api/workspace/services/{hostname}/health")
    assert stopped_health.status_code == 200
    assert cast(dict[str, object], stopped_health.json())["process_running"] is False


def test_service_runtime_reports_missing_start_command() -> None:
    # Given: a registry record without a managed process command.
    registry = WorkspaceServiceRegistry()
    record = registry.register("api", "main", "demo", 4312)
    runtime = WorkspaceServiceRuntime(registry)

    # When/Then: starting is rejected as a typed lifecycle error.
    with pytest.raises(ServiceProcessError):
        _ = runtime.start(record.hostname)
