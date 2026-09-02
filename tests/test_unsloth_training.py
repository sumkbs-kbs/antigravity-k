from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from mcp.types import CallToolResult
from pydantic import SecretStr, ValidationError

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

from .test_unsloth_training_doubles import AsyncCallRecorder, SessionDouble


class _MemoryProbe:
    def snapshot(self) -> UnslothMemorySnapshot:
        return UnslothMemorySnapshot(total_bytes=1_000, available_bytes=900)


@dataclass(frozen=True, slots=True)
class _Harness:
    service: UnslothTrainingService
    broker: UnslothResourceBroker
    session_call_tool: AsyncCallRecorder[CallToolResult]
    manager_connect: AsyncCallRecorder[SessionDouble]


def _request(idempotency_key: str = "training-service-0001") -> UnslothTrainingStartRequest:
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


def test_unsloth_backend_features_reach_the_exact_mcp_config() -> None:
    default_request = _request()
    assert default_request.recipe.load_in_4bit is True
    assert default_request.recipe.packing is False
    assert default_request.recipe.use_gradient_checkpointing == "unsloth"
    feature_recipe = UnslothTrainingRecipe.model_validate(
        {
            **default_request.recipe.model_dump(),
            "load_in_4bit": False,
            "packing": True,
            "use_gradient_checkpointing": False,
        },
    )
    feature_request = default_request.model_copy(update={"recipe": feature_recipe})

    config = feature_request.mcp_config()

    assert config.model_dump(mode="json") == {
        "model_name": "unsloth/Qwen3-Coder",
        "start_request_id": "training-service-0001",
        "training_type": "LoRA/QLoRA",
        "load_in_4bit": False,
        "max_seq_length": 4_096,
        "trust_remote_code": False,
        "model_snapshot_path": "/models/snapshots/model",
        "hf_dataset": "datasets/code-instructions",
        "dataset_snapshot_path": "/datasets/snapshots/code",
        "format_type": "chatml",
        "num_epochs": 1,
        "learning_rate": "0.0002",
        "batch_size": 1,
        "gradient_accumulation_steps": 8,
        "lora_r": 16,
        "lora_alpha": 16,
        "packing": True,
        "use_gradient_checkpointing": False,
        "use_lora": True,
        "enable_wandb": False,
    }
    assert feature_request.request_fingerprint() != default_request.request_fingerprint()


def test_unsloth_rejects_unknown_gradient_checkpointing_mode() -> None:
    recipe = _request().recipe

    with pytest.raises(ValidationError):
        _ = UnslothTrainingRecipe.model_validate(
            {**recipe.model_dump(), "use_gradient_checkpointing": "automatic"},
        )


def _approve(request: UnslothTrainingStartRequest, approvals: ApprovalManager) -> UnslothTrainingStartRequest:
    approval = approvals.request_approval(
        "start_training",
        {"request_fingerprint": request.request_fingerprint()},
        RiskLevel.CRITICAL.value,
    )
    assert approvals.resolve(approval.request_id, ApprovalDecision.APPROVE)
    return request.model_copy(update={"approval_id": approval.request_id})


def _policy_prompt() -> PermissionDecision:
    return PermissionDecision(
        spec=ToolSpec(
            name="start_training",
            risk_level=RiskLevel.CRITICAL.value,
            category=ToolCategory.SYSTEM.value,
        ),
        permission=Permission.PROMPT,
        source="capability_policy",
        reason="Explicit approval required.",
    )


def _harness(
    tmp_path: Path,
    approvals: ApprovalManager,
    call_result: CallToolResult,
) -> _Harness:
    broker = UnslothResourceBroker(tmp_path / "resources.sqlite3", _MemoryProbe())
    session = SessionDouble.with_result(call_result)
    manager = MagicMock(spec=MCPSessionManager)
    manager_connect = AsyncCallRecorder(session)
    manager.connect_streamable_http = manager_connect
    manager.disconnect_server = AsyncCallRecorder(None)
    registry = MagicMock(spec=ToolRegistry)
    registry.authorize_tool = MagicMock(return_value=_policy_prompt())
    service = UnslothTrainingService(
        settings=UnslothStudioSettings(token=SecretStr("studio-secret"), write_tools_enabled=True),
        manager=manager,
        registry=registry,
        broker=broker,
        approvals=approvals,
    )
    return _Harness(service, broker, session.call_tool, manager_connect)


@pytest.mark.asyncio
async def test_approved_training_binds_the_remote_job_to_the_reservation(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    request = _approve(_request(), approvals)
    harness = _harness(
        tmp_path,
        approvals,
        CallToolResult(
            content=[],
            structuredContent={"job_id": "job-1", "status": "queued", "message": "queued"},
            isError=False,
        ),
    )

    outcome = await harness.service.launch(request)

    assert outcome.state is UnslothTrainingLaunchState.STARTED
    assert outcome.resource_job_id == "job-1"
    assert harness.broker.status().active_reservations[0].resource_job_id == "job-1"
    harness.session_call_tool.assert_awaited_once()
    call = harness.session_call_tool.await_args
    assert call is not None
    arguments_value = call.kwargs.get("arguments")
    assert isinstance(arguments_value, dict)
    config = arguments_value.get("config")
    assert isinstance(config, dict)
    arguments = config
    assert arguments["start_request_id"] == request.admission.idempotency_key
    assert arguments["load_in_4bit"] is True
    assert arguments["trust_remote_code"] is False
    assert arguments["enable_wandb"] is False


@pytest.mark.asyncio
async def test_bound_job_replay_does_not_call_remote_training_twice(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    request = _approve(_request("training-replay-0001"), approvals)
    harness = _harness(
        tmp_path,
        approvals,
        CallToolResult(
            content=[],
            structuredContent={"job_id": "job-replay", "status": "queued", "message": "queued"},
            isError=False,
        ),
    )
    _ = await harness.service.launch(request)
    harness.session_call_tool.reset_mock()

    replay = await harness.service.launch(request)

    assert replay.state is UnslothTrainingLaunchState.IDEMPOTENT_REPLAY
    assert replay.resource_job_id == "job-replay"
    harness.session_call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_remote_rejection_releases_the_resource_reservation(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    request = _approve(_request("training-rejected-01"), approvals)
    harness = _harness(
        tmp_path,
        approvals,
        CallToolResult(
            content=[],
            structuredContent={
                "job_id": "job-rejected",
                "status": "error",
                "message": "rejected",
                "error_code": "invalid_recipe",
            },
            isError=False,
        ),
    )

    outcome = await harness.service.launch(request)

    assert outcome.state is UnslothTrainingLaunchState.REMOTE_REJECTED
    assert harness.broker.status().active_reservations == ()


@pytest.mark.asyncio
async def test_connection_loss_after_remote_call_keeps_reservation_for_safe_replay(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    request = _approve(_request("training-uncertain-01"), approvals)
    harness = _harness(
        tmp_path,
        approvals,
        CallToolResult(content=[], structuredContent=None, isError=False),
    )
    harness.session_call_tool.side_effect = OSError("connection lost")

    outcome = await harness.service.launch(request)

    assert outcome.state is UnslothTrainingLaunchState.UNCERTAIN
    assert len(harness.broker.status().active_reservations) == 1


@pytest.mark.asyncio
async def test_approval_is_bound_to_the_exact_training_request(tmp_path: Path) -> None:
    approvals = ApprovalManager()
    approved = _approve(_request("training-bound-0001"), approvals)
    mismatched = _request("training-bound-0002").model_copy(update={"approval_id": approved.approval_id})
    harness = _harness(
        tmp_path,
        approvals,
        CallToolResult(content=[], structuredContent=None, isError=False),
    )

    outcome = await harness.service.launch(mismatched)

    assert outcome.state is UnslothTrainingLaunchState.APPROVAL_DENIED
    assert harness.broker.status().active_reservations == ()
    harness.manager_connect.assert_not_awaited()
