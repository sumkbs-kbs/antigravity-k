from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from antigravity_k.api.dependencies import __get_tool_registry
from antigravity_k.engine.audit_logger import get_audit_logger
from antigravity_k.engine.provider_adapters.unsloth_studio import UnslothStudioService
from antigravity_k.engine.provider_adapters.unsloth_studio_contracts import (
    UnslothStudioPermissionDenied,
    UnslothStudioSettings,
    UnslothStudioSnapshot,
)
from antigravity_k.tools.mcp_session_manager import MCPSessionManager
from antigravity_k.tools.tool_registry import ToolRegistry

router = APIRouter()


def get_unsloth_studio_service(
    registry: Annotated[ToolRegistry, Depends(__get_tool_registry)],
) -> UnslothStudioService:
    try:
        settings = UnslothStudioSettings.from_env()
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unsloth Studio MCP configuration is invalid.",
        ) from exc
    return UnslothStudioService(settings=settings, manager=MCPSessionManager(), registry=registry)


@router.get(
    "/v1/integrations/unsloth/studio",
    response_model=UnslothStudioSnapshot,
)
async def get_unsloth_studio_snapshot(
    service: Annotated[UnslothStudioService, Depends(get_unsloth_studio_service)],
) -> UnslothStudioSnapshot:
    try:
        snapshot = await service.snapshot()
    except UnslothStudioPermissionDenied as exc:
        get_audit_logger().log_event(
            "unsloth_studio_read_denied",
            {"tool": exc.tool.value, "source": exc.source},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unsloth Studio read access was denied by policy.",
        ) from exc

    get_audit_logger().log_event(
        "unsloth_studio_read",
        {
            "configured": snapshot.configured,
            "available": snapshot.available,
            "tools": [result.tool.value for result in snapshot.results if result.ok],
        },
    )
    return snapshot
