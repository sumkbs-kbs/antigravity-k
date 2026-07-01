"""Antigravity-K: Legacy Agent Routes.

====================================

Health check, agent wake/evolve, SSE stream, models, embeddings, logs, and
settings routes extracted from legacy.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from antigravity_k.api.dependencies import (
    __get_tool_registry,
    get_embedding_engine,
    get_model_manager,
    get_orchestrator,
    get_vault_engine,
)
from antigravity_k.api.models import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EvolveRequest,
    EvolveSystemPromptRequest,
    UsageStats,
    WakeRequest,
    _active_session,
)
from antigravity_k.engine.embeddings import EmbeddingEngine
from antigravity_k.engine.model_manager import ModelManager

logger = logging.getLogger("antigravity_k.api.agent_api")
router = APIRouter()


# ─── Health Check ───────────────────────────────────────────────


@router.get("/health")
@router.get("/v1/health")
def health_check():
    """Health Check."""
    manager = get_model_manager()
    info = manager.status() if manager else {}
    backends = info.get("loaded_models", {}) if isinstance(info, dict) else {}

    orchestrator = get_orchestrator()
    rag_files = 0
    cov_active = False
    if orchestrator:
        if getattr(orchestrator, "_rag_indexer", None):
            rag_files = len(getattr(orchestrator._rag_indexer, "_file_hashes", {}))
        if getattr(orchestrator, "_cov_engine", None):
            cov_active = True

    return {
        "status": "ok",
        "backends": backends,
        "rag_index_files": rag_files,
        "cov_active": cov_active,
    }


# ─── Model Listing ──────────────────────────────────────────────


@router.get("/v1/models")
def list_models(manager: ModelManager = Depends(get_model_manager)):
    """List Models.

    Args:
        manager (ModelManager): ModelManager manager.

    """
    models = manager._registry.list_models()
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
            },
        )
    return {"object": "list", "data": formatted_data}


# ─── Embeddings ─────────────────────────────────────────────────


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
    from antigravity_k.engine.audit_logger import get_audit_logger

    audit = get_audit_logger()
    audit.log_event(
        "embedding_request",
        {"model": request.model, "input_len": len(request.input)},
    )
    try:
        embeddings = engine.embed(request.input, request.model)
        data = []
        for i, emb in enumerate(embeddings):
            data.append(EmbeddingData(embedding=emb, index=i))
        tokens = sum(len(t) // 4 for t in request.input) if isinstance(request.input, list) else len(request.input) // 4
        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage=UsageStats(prompt_tokens=tokens, total_tokens=tokens),
        )
    except Exception as e:
        logger.error("Embedding error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Agent Wake / Evolve ────────────────────────────────────────


@router.post("/api/agent/wake")
async def wake_agent(
    req: WakeRequest,
    manager: ModelManager = Depends(get_model_manager),
    registry: Any = Depends(__get_tool_registry),
    vault: Any = Depends(get_vault_engine),
):
    """Wake Agent.

    Args:
        req (WakeRequest): WakeRequest req.
        manager (ModelManager): ModelManager manager.
        registry (Any): registry.
        vault (Any): vault.

    """
    return {
        "status": "woken",
        "task_id": "dummy_task_id",
        "message": f"Agent woken by '{req.event_type}' event (legacy mock).",
    }


@router.post("/api/agent/evolve")
async def evolve_skill_api(
    req: EvolveRequest,
    manager: ModelManager = Depends(get_model_manager),
    vault: Any = Depends(get_vault_engine),
):
    """Evolve Skill Api.

    Args:
        req (EvolveRequest): EvolveRequest req.
        manager (ModelManager): ModelManager manager.
        vault (Any): vault.

    """
    from antigravity_k.engine.evolution import EvolutionManager

    if not isinstance(req, EvolveRequest):
        raise HTTPException(status_code=422, detail="Invalid evolution request")
    if vault is None:
        raise HTTPException(
            status_code=422,
            detail=("VaultEngine is not initialized. Set ANTIGRAVITY_VAULT_PATH environment variable."),
        )
    ev_manager = EvolutionManager(model_manager=manager, vault_engine=vault)
    draft_path = ev_manager.evolve_skill(
        skill_name=req.skill_name,
        target_model=req.target_model,
    )
    if draft_path:
        return {
            "status": "success",
            "message": f"Skill '{req.skill_name}' has been successfully evolved.",
            "draft_path": draft_path,
        }
    raise HTTPException(
        status_code=500,
        detail="Failed to evolve skill. Check logs for details.",
    )


@router.post("/api/agent/evolve_system_prompt")
async def evolve_system_prompt_api(
    req: EvolveSystemPromptRequest,
    manager: ModelManager = Depends(get_model_manager),
    vault: Any = Depends(get_vault_engine),
):
    """Evolve System Prompt Api.

    Args:
        req (EvolveSystemPromptRequest): EvolveSystemPromptRequest req.
        manager (ModelManager): ModelManager manager.
        vault (Any): vault.

    """
    from antigravity_k.engine.evolution import EvolutionManager

    if not isinstance(req, EvolveSystemPromptRequest):
        raise HTTPException(
            status_code=422,
            detail="Invalid system prompt evolution request",
        )
    if vault is None:
        raise HTTPException(
            status_code=422,
            detail=("VaultEngine is not initialized. Set ANTIGRAVITY_VAULT_PATH environment variable."),
        )
    ev_manager = EvolutionManager(model_manager=manager, vault_engine=vault)
    draft_path = ev_manager.evolve_system_prompt(target_model=req.target_model)
    if draft_path:
        return {
            "status": "success",
            "message": "System prompt has been successfully evolved.",
            "draft_path": draft_path,
        }
    raise HTTPException(status_code=500, detail="Failed to evolve system prompt.")


# ─── Active Agent ───────────────────────────────────────────────


@router.get("/api/agent/active")
async def get_active_agent():
    """Retrieve active agent."""
    if _active_session.is_active:
        return {
            "active": True,
            "q": _active_session.q,
            "history": _active_session.history,
        }
    return {"active": False}


@router.get("/api/stream_agent")
async def stream_agent(
    q: str = Query(None, description="User prompt to the agent"),
    reconnect: bool = False,
):
    """Stream Agent.

    Args:
        q (str): str q.
        reconnect (bool): bool reconnect.

    """
    from starlette.concurrency import iterate_in_threadpool

    async def event_generator():
        if reconnect and _active_session.is_active:
            for chunk in _active_session.history:
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            last_idx = len(_active_session.history)
            while _active_session.is_active:
                if len(_active_session.history) > last_idx:
                    for chunk in _active_session.history[last_idx:]:
                        yield f"data: {json.dumps({'text': chunk})}\n\n"
                    last_idx = len(_active_session.history)
                await asyncio.sleep(0.5)
            if _active_session.error:
                yield f"data: {json.dumps({'error': _active_session.error})}\n\n"
            elif _active_session.done:
                yield f"data: {json.dumps({'done': True})}\n\n"
            return

        if not q:
            yield f"data: {json.dumps({'error': 'Missing query'})}\n\n"
            return

        # Mutate in place so all modules sharing legacy_state see the update
        _active_session.q = q
        _active_session.is_active = True
        _active_session.history.clear()
        _active_session.done = False
        _active_session.error = None
        _active_session.orchestrator = None

        try:
            from antigravity_k.engine.orchestrator import OrchestratorAgent

            manager = get_model_manager()
            vault = get_vault_engine()
            orchestrator = OrchestratorAgent(model_manager=manager, vault_engine=vault)
            _active_session.orchestrator = orchestrator

            messages = [{"role": "user", "content": q}]
            target_model = orchestrator._get_model_for_role("default")

            async for chunk in iterate_in_threadpool(
                orchestrator.run_stream(messages, target_model=target_model),
            ):
                if chunk:
                    _active_session.history.append(chunk)
                    payload = json.dumps({"text": chunk})
                    yield f"data: {payload}\n\n"

            _active_session.done = True
            yield f"data: {json.dumps({'done': True})}\n\n"
        except asyncio.CancelledError:
            logger.info("SSE client disconnected, but task might continue in thread.")
            raise
        except Exception as e:
            logger.error("SSE Error: %s", e, exc_info=True)
            _active_session.error = str(e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            _active_session.is_active = False

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Background Tasks ────────────────────────────────────────────


@router.post("/api/tasks/submit")
async def submit_background_task(request: Request):
    """Submit Background Task.

    Args:
        request (Request): Request request.

    """
    return {"status": "submitted", "task_id": "dummy_task_id"}


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Retrieve task status.

    Args:
        task_id (str): str task id.

    """
    return {"status": "ok", "data": {"status": "completed"}}


@router.get("/api/tasks")
async def list_tasks(limit: int = Query(default=20)):
    """List Tasks.

    Args:
        limit (int): int limit.

    """
    return {"status": "ok", "data": []}


@router.get("/api/tasks/{task_id}/output")
async def get_task_output(task_id: str):
    """Retrieve task output.

    Args:
        task_id (str): str task id.

    """
    return {"status": "ok", "output": "Legacy output mock"}


@router.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """Resume Task.

    Args:
        task_id (str): str task id.

    """
    return {"status": "resumed", "task_id": task_id}


# ─── Logs & Settings ────────────────────────────────────────────


@router.get("/api/logs")
async def get_logs(lines: int = 100):
    """Retrieve logs.

    Args:
        lines (int): int lines.

    """
    log_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "logs",
        "server_debug.log",
    )
    if not os.path.exists(log_file):
        return {"logs": ["Log file not found."]}
    try:
        with open(log_file, encoding="utf-8") as f:
            all_lines = f.readlines()
        return {"logs": all_lines[-lines:]}
    except Exception as e:
        logger.exception("Unhandled exception")
        return {"logs": [f"Error reading logs: {str(e)}"]}


@router.get("/api/settings")
async def get_settings():
    """Retrieve settings."""
    config_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "config.yaml",
    )
    if not os.path.exists(config_file):
        return {"settings": {}}
    try:
        with open(config_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if "api_keys" in cfg:
            for k in cfg["api_keys"]:
                val = cfg["api_keys"][k]
                if val and len(val) > 4:
                    cfg["api_keys"][k] = val[:4] + "*" * (len(val) - 4)
        return {"settings": cfg}
    except Exception as e:
        logger.exception("Unhandled exception")
        return {"settings": {"error": str(e)}}
