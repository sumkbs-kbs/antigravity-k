from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, ListToolsResult, Tool
from pydantic import SecretStr

from antigravity_k.engine.approval_manager import ApprovalDecision, ApprovalManager
from antigravity_k.engine.provider_adapters.unsloth_resource_broker import UnslothResourceBroker
from antigravity_k.engine.provider_adapters.unsloth_resource_contracts import (
    UnslothAdmissionRequest,
    UnslothArtifactProvenance,
    UnslothMemorySnapshot,
    UnslothResourceOperation,
)
from antigravity_k.engine.provider_adapters.unsloth_studio_contracts import UnslothStudioSettings
from antigravity_k.engine.provider_adapters.unsloth_training import UnslothTrainingService
from antigravity_k.engine.provider_adapters.unsloth_training_contracts import (
    UnslothTrainingLaunchState,
    UnslothTrainingRecipe,
    UnslothTrainingStartRequest,
)
from antigravity_k.tools.base_tool import RiskLevel, ToolCategory
from antigravity_k.tools.mcp_session_manager import MCPSessionManager
from antigravity_k.tools.tool_contracts import Permission, PermissionDecision, ToolSpec
from antigravity_k.tools.tool_registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class _MemoryProbe:
    def snapshot(self) -> UnslothMemorySnapshot:
        return UnslothMemorySnapshot(total_bytes=1_000, available_bytes=900)


@dataclass(frozen=True, slots=True)
class _Harness:
    service: UnslothTrainingService
    broker: UnslothResourceBroker
    manager: MagicMock
    registry: MagicMock


def _request(idempotency_key: str) -> UnslothTrainingStartRequest:
    return UnslothTrainingStartRequest(
        admission=UnslothAdmissionRequest(
            idempotency_key=idempotency_key,
            operation=UnslothResourceOperation.TRAINING,
            device_id="unified:0",
            estimated_peak_bytes=100,
            artifact=UnslothArtifactProvenance(
                source_uri="hf://unsloth/Qwen3-Coder",
                revision="a" * 40,
                sha256="b" * 64,
            ),
        ),
        dataset_artifact=UnslothArtifactProvenance(
            source_uri="hf://datasets/code-instructions",
            revision="c" * 40,
            sha256="d" * 64,
        ),
        recipe=UnslothTrainingRecipe(
            model_name="unsloth/Qwen3-Coder",
            model_snapshot_path="/models/snapshots/model",
            hf_dataset="datasets/code-instructions",
            dataset_snapshot_path="/datasets/snapshots/code",
            format_type="chatml",
            max_seq_length=4_096,
            num_epochs=1,
            learning_rate=Decimal("0.0002"),
            batch_size=1,
            gradient_accumulation_steps=8,
            lora_r=16,
            lora_alpha=16,
        ),
    )


def _harness(tmp_path: Path, approvals: ApprovalManager) -> _Harness:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    session = MagicMock(spec=ClientSession)
    session.list_tools = AsyncMock(
        return_value=ListToolsResult(
            tools=[Tool(name="start_training", description="start", inputSchema={"type": "object"})],
        ),
    )
    session.call_tool = AsyncMock(
        return_value=CallToolResult(content=[], structuredContent=None, isError=False),
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
    return _Harness(
        service=UnslothTrainingService(
            settings=UnslothStudioSettings(
                token=SecretStr("studio-secret"),
                write_tools_enabled=True,
            ),
            manager=manager,
            registry=registry,
            broker=broker,
            approvals=approvals,
        ),
        broker=broker,
        manager=manager,
        registry=registry,
    )


@pytest.mark.asyncio
async def test_policy_denial_prevents_approval_reservation_and_mcp(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    harness = _harness(tmp_path, approvals)
    harness.registry.authorize_tool.return_value = PermissionDecision(
        spec=ToolSpec(
            name="start_training",
            risk_level=RiskLevel.CRITICAL.value,
            category=ToolCategory.SYSTEM.value,
        ),
        permission=Permission.DENY,
        source="capability_policy",
        reason="Training denied by policy.",
    )

    outcome = await harness.service.launch(_request("training-policy-0001"))

    assert outcome.state is UnslothTrainingLaunchState.POLICY_DENIED
    assert approvals.get_pending() == []
    assert harness.broker.status().active_reservations == ()
    harness.manager.connect_streamable_http.assert_not_awaited()


@pytest.mark.asyncio
async def test_always_allow_cannot_replace_per_request_training_approval(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    request = _request("training-always-0001")
    approval = approvals.request_approval(
        "start_training",
        {"request_fingerprint": request.request_fingerprint()},
        RiskLevel.CRITICAL.value,
    )
    assert approvals.resolve(approval.request_id, ApprovalDecision.ALWAYS_ALLOW)
    approved = request.model_copy(update={"approval_id": approval.request_id})
    harness = _harness(tmp_path, approvals)

    outcome = await harness.service.launch(approved)

    assert outcome.state is UnslothTrainingLaunchState.APPROVAL_DENIED
    assert harness.broker.status().active_reservations == ()
    harness.manager.connect_streamable_http.assert_not_awaited()


@pytest.mark.asyncio
async def test_busy_device_prevents_remote_training_call(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    request = _request("training-busy-000001")
    approval = approvals.request_approval(
        "start_training",
        {"request_fingerprint": request.request_fingerprint()},
        RiskLevel.CRITICAL.value,
    )
    assert approvals.resolve(approval.request_id, ApprovalDecision.APPROVE)
    approved = request.model_copy(update={"approval_id": approval.request_id})
    harness = _harness(tmp_path, approvals)
    occupied = harness.broker.admit(_request("training-occupy-0001").admission)
    assert occupied.allowed

    outcome = await harness.service.launch(approved)

    assert outcome.state is UnslothTrainingLaunchState.RESOURCE_DENIED
    harness.manager.connect_streamable_http.assert_not_awaited()
