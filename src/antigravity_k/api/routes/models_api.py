"""Models & Health API — 헬스체크, OpenAI 호환 모델 목록, 임베딩, Wake 이벤트."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from antigravity_k import __version__
from antigravity_k.api.dependencies import (
    __get_tool_registry,
    get_agent_runtime,
    get_embedding_engine,
    get_model_manager,
    get_orchestrator,
    get_vault_engine,
)
from antigravity_k.api.models import EmbeddingData, EmbeddingRequest, EmbeddingResponse, UsageStats
from antigravity_k.engine.audit_logger import get_audit_logger
from antigravity_k.engine.embeddings import EmbeddingEngine
from antigravity_k.engine.model_manager import ModelManager

router = APIRouter()
logger = logging.getLogger("antigravity_k.api.routes.models")


@router.get("/health")
@router.get("/v1/health")
def health_check():
    """Health Check."""
    manager = get_model_manager()
    info = manager.status() if manager else {}
    backends = info.get("loaded_models", {}) if isinstance(info, dict) else {}

    # 시스템 상태 추가 (RAG, CoV)
    orchestrator = get_orchestrator()
    rag_files = 0
    cov_active = False
    if orchestrator:
        rag_indexer = getattr(orchestrator, "_rag_indexer", None)
        if rag_indexer:
            rag_files = len(getattr(rag_indexer, "_file_hashes", {}))
        if getattr(orchestrator, "_cov_engine", None):
            cov_active = True

    return {
        "status": "ok",
        "version": __version__,
        "backends": backends,
        "rag_index_files": rag_files,
        "cov_active": cov_active,
    }


class WakeRequest(BaseModel):
    """Wakerequest.

    Bases: BaseModel
    """

    event_type: str = Field(
        ...,
        description="Type of event (e.g. 'file_changed', 'lint_error', 'comment')",
    )
    payload: dict[str, Any] = Field(..., description="Detailed payload for the event")
    target_model: str = Field(
        default="qwen3.6:latest",
        description="Model to use for the wake task",
    )


@router.post("/api/agent/wake")
async def wake_agent(
    req: WakeRequest,
    manager: ModelManager = Depends(get_model_manager),
    registry: Any = Depends(__get_tool_registry),
    vault: Any = Depends(get_vault_engine),
):
    """Paperclip의 Comment-driven Wake 개념을 포팅.

    특정 시스템 이벤트 발생 시 에이전트가 백그라운드에서 즉시 기상하여 태스크를 수행합니다.
    """
    runtime = get_agent_runtime()

    payload_str = json.dumps(req.payload, ensure_ascii=False)
    prompt = (
        f"System Wake Event Triggered:\n- Type: {req.event_type}\n- Details:"
        f"{payload_str}\n\nPlease analyze this event and"
        f" take any necessary actions."
    )

    task_id = runtime.submit_task(
        prompt=prompt,
        target_model=req.target_model,
        context={"wake_event": req.event_type, "use_worktree": False},
    )

    return {
        "status": "woken",
        "task_id": task_id,
        "message": f"Agent woken by '{req.event_type}' event and assigned background task {task_id}.",
    }


@router.get("/v1/models")
def list_models(manager: ModelManager = Depends(get_model_manager)):
    """설치/로드된 모델 목록 반환."""
    import time

    models = manager._registry.list_models()
    provider_capabilities = manager.provider_capabilities()
    # Ensure it follows OpenAI-like format
    formatted_data = []
    for m in models:
        formatted_data.append(
            {
                "id": m.name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "system",
                "role": m.role,
                "description": m.description,
                "provider_capability": provider_capabilities.get(m.name),
                **m.routing_metadata(),
            },
        )
    return {"object": "list", "data": formatted_data}


@router.get("/v1/models/operations")
def model_operations_status(
    manager: ModelManager = Depends(get_model_manager),
    refresh: bool = False,
) -> dict[str, Any]:
    routing_status = manager.router.status()
    return {
        "provider_capabilities": manager.provider_capabilities(refresh=refresh),
        "quality_calibration": routing_status.get("quality_calibration", {}),
    }


@router.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    engine: EmbeddingEngine = Depends(get_embedding_engine),
):
    """Create embeddings.

    Args:
        request (EmbeddingRequest): EmbeddingRequest request.
        engine (EmbeddingEngine): EmbeddingEngine engine.

    """
    audit = get_audit_logger()
    audit.log_event("embedding_request", {"model": request.model, "input_len": len(request.input)})

    try:
        # Generate embeddings
        embeddings = engine.embed(request.input, request.model)

        # Format response
        data = []
        for i, emb in enumerate(embeddings):
            data.append(EmbeddingData(embedding=emb, index=i))

        # Basic usage tracking (dummy for now)
        tokens = sum(len(t) // 4 for t in request.input) if isinstance(request.input, list) else len(request.input) // 4

        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage=UsageStats(prompt_tokens=tokens, total_tokens=tokens),
        )
    except (ValueError, RuntimeError, KeyError) as e:
        logger.error("Embedding error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
