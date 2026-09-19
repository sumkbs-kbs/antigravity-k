from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, ListToolsResult, Tool
from pydantic import SecretStr

from antigravity_k.api.routes import unsloth_training_api
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.approval_manager import ApprovalManager, get_approval_manager, reset_approval_manager
from antigravity_k.engine.provider_adapters.unsloth_resource_broker import UnslothResourceBroker
from antigravity_k.engine.provider_adapters.unsloth_resource_contracts import UnslothMemorySnapshot
from antigravity_k.engine.provider_adapters.unsloth_studio_contracts import UnslothStudioSettings
from antigravity_k.engine.provider_adapters.unsloth_training import UnslothTrainingService
from antigravity_k.tools.base_tool import RiskLevel, ToolCategory
from antigravity_k.tools.mcp_session_manager import MCPSessionManager
from antigravity_k.tools.tool_contracts import Permission, PermissionDecision, ToolSpec
from antigravity_k.tools.tool_registry import ToolRegistry


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


def _payload_json() -> str:
    return json.dumps(
        {
            "admission": {
                "idempotency_key": "training-launch-0001",
                "operation": "training",
                "device_id": "unified:0",
                "estimated_peak_bytes": 100,
                "artifact": {
                    "source_uri": "hf://unsloth/Qwen3-Coder",
                    "revision": "a" * 40,
                    "sha256": "b" * 64,
                },
            },
            "dataset_artifact": {
                "source_uri": "hf://datasets/code-instructions",
                "revision": "c" * 40,
                "sha256": "d" * 64,
            },
            "recipe": {
                "model_name": "unsloth/Qwen3-Coder",
                "model_snapshot_path": "/models/snapshots/model",
                "hf_dataset": "datasets/code-instructions",
                "dataset_snapshot_path": "/datasets/snapshots/code",
                "format_type": "chatml",
                "max_seq_length": 4096,
                "num_epochs": 1,
                "learning_rate": "0.0002",
                "batch_size": 1,
                "gradient_accumulation_steps": 8,
                "lora_r": 16,
                "lora_alpha": 16,
            },
        }
    )


@dataclass(frozen=True, slots=True)
class _MemoryProbe:
    def snapshot(self) -> UnslothMemorySnapshot:
        return UnslothMemorySnapshot(total_bytes=1_000, available_bytes=900)


@dataclass(frozen=True, slots=True)
class _ApiHarness:
    service: UnslothTrainingService
    broker: UnslothResourceBroker
    session: MagicMock


def _api_harness(tmp_path: Path, approvals: ApprovalManager) -> _ApiHarness:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    session = MagicMock(spec=ClientSession)
    session.list_tools = AsyncMock(
        return_value=ListToolsResult(
            tools=[Tool(name="start_training", description="start", inputSchema={"type": "object"})],
        ),
    )
    session.call_tool = AsyncMock(
        return_value=CallToolResult(
            content=[],
            structuredContent={"job_id": "job-http-1", "status": "queued", "message": "queued"},
            isError=False,
        ),
    )
    manager = MagicMock(spec=MCPSessionManager)
    manager.connect_streamable_http = AsyncMock(return_value=session)
    manager.disconnect_server = AsyncMock()
    registry = MagicMock(spec=ToolRegistry)
    registry.authorize_tool.return_value = PermissionDecision(
        spec=ToolSpec(
            name="start_training",
            risk_level=RiskLevel.CRITICAL.value,
            category=ToolCategory.SYSTEM.value,
        ),
        permission=Permission.PROMPT,
        source="capability_policy",
        reason="Explicit approval required.",
    )
    service = UnslothTrainingService(
        settings=UnslothStudioSettings(
            token=SecretStr("test-only-token"),
            write_tools_enabled=True,
        ),
        manager=manager,
        registry=registry,
        broker=broker,
        approvals=approvals,
    )
    return _ApiHarness(service=service, broker=broker, session=session)


@contextmanager
def _client_for(service: UnslothTrainingService) -> Generator[TestClient, None, None]:
    app.dependency_overrides[unsloth_training_api.get_unsloth_training_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        _ = app.dependency_overrides.pop(
            unsloth_training_api.get_unsloth_training_service,
            None,
        )


def test_training_start_api_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNSLOTH_STUDIO_WRITE_TOOLS_ENABLED", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/v1/integrations/unsloth/training/start",
            content=_payload_json(),
            headers={**_auth_headers(), "Content-Type": "application/json"},
        )

    assert response.status_code == 403
    assert response.json()["state"] == "write_disabled"
    assert response.json()["write_tools_enabled"] is False


def test_training_start_api_creates_a_bound_approval_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSLOTH_STUDIO_WRITE_TOOLS_ENABLED", "true")
    monkeypatch.setenv("UNSLOTH_STUDIO_MCP_TOKEN", "test-only-token")
    reset_approval_manager()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/integrations/unsloth/training/start",
                content=_payload_json(),
                headers={**_auth_headers(), "Content-Type": "application/json"},
            )

        assert response.status_code == 202
        assert response.json()["state"] == "approval_required"
        approval_id = response.json()["approval_id"]
        approval = get_approval_manager().get_request(approval_id)
        assert approval is not None
        assert approval.tool_name == "start_training"
        assert set(approval.tool_args) == {"request_fingerprint"}
    finally:
        reset_approval_manager()


def test_invalid_write_flag_returns_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNSLOTH_STUDIO_WRITE_TOOLS_ENABLED", "sometimes")

    with TestClient(app) as client:
        response = client.post(
            "/v1/integrations/unsloth/training/start",
            content=_payload_json(),
            headers={**_auth_headers(), "Content-Type": "application/json"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Unsloth Studio MCP configuration is invalid."


def test_training_start_http_flow_requires_approval_and_replays_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_approval_manager()
    approvals = get_approval_manager()
    harness = _api_harness(tmp_path, approvals)
    audit = MagicMock()
    monkeypatch.setattr(unsloth_training_api, "get_audit_logger", lambda: audit)

    try:
        with _client_for(harness.service) as client:
            first = client.post(
                "/v1/integrations/unsloth/training/start",
                content=_payload_json(),
                headers={**_auth_headers(), "Content-Type": "application/json"},
            )
            approval_id = first.json()["approval_id"]
            resolved = client.post(
                f"/api/approval/{approval_id}/resolve",
                json={"decision": "approve"},
                headers=_auth_headers(),
            )
            payload = json.loads(_payload_json())
            payload["approval_id"] = approval_id
            started = client.post(
                "/v1/integrations/unsloth/training/start",
                json=payload,
                headers=_auth_headers(),
            )
            replayed = client.post(
                "/v1/integrations/unsloth/training/start",
                json=payload,
                headers=_auth_headers(),
            )

        assert first.status_code == 202
        assert first.json()["state"] == "approval_required"
        assert resolved.status_code == 200
        assert started.status_code == 202
        assert started.json()["state"] == "started"
        assert started.json()["resource_job_id"] == "job-http-1"
        assert replayed.status_code == 200
        assert replayed.json()["state"] == "idempotent_replay"
        harness.session.call_tool.assert_awaited_once()
        assert harness.broker.status().active_reservations[0].resource_job_id == "job-http-1"
        logged = json.dumps([call.args[1] for call in audit.log_event.call_args_list])
        assert "test-only-token" not in logged
        assert "training-launch-0001" not in logged
        assert "hf://" not in logged
    finally:
        reset_approval_manager()
