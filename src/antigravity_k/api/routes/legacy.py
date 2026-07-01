"""Legacy module."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from antigravity_k.api.dependencies import (
    __get_skill_loader,
    __get_tool_registry,
    _get_context_shaper,
    _get_session_manager,
    get_model_manager,
    get_orchestrator,
    get_vault_engine,
)
from antigravity_k.api.models import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    UsageStats,
)
from antigravity_k.config import config
from antigravity_k.engine.audit_logger import get_audit_logger
from antigravity_k.engine.embeddings import EmbeddingEngine, get_embedding_engine
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.vault import VaultEngine

logger = logging.getLogger("antigravity_k.api.legacy")
router = APIRouter()


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
    from antigravity_k.engine.task_runner import get_task_runner

    runner = get_task_runner()
    orchestrator = get_orchestrator()

    payload_str = json.dumps(req.payload, ensure_ascii=False)
    prompt = (
        f"System Wake Event Triggered:\n- Type: {req.event_type}\n- Details:"
        f"{payload_str}\n\nPlease analyze this event and"
        f" take any necessary actions."
    )

    task_id = runner.submit_task(
        prompt=prompt,
        orchestrator=orchestrator,
        target_model=req.target_model,
        context={"wake_event": req.event_type, "use_worktree": False},
    )

    return {
        "status": "woken",
        "task_id": task_id,
        "message": f"Agent woken by '{req.event_type}' event and assigned background task {task_id}.",
    }


class EvolveRequest(BaseModel):
    """Evolverequest.

    Bases: BaseModel
    """

    skill_name: str = Field(..., description="Name of the skill to evolve")
    target_model: str = Field(default="qwen3.6:latest", description="Model to use for evolution")


@router.post("/api/agent/evolve")
async def evolve_skill_api(
    req: EvolveRequest,
    manager: ModelManager = Depends(get_model_manager),
    vault: Any = Depends(get_vault_engine),
):
    """특정 스킬에 대해 과거 실패 이력을 바탕으로 한 자율 진화(Self-Evolution)를 시작합니다.

    진화된 결과는 SKILL_EVOLVED.md 로 저장되어 인간의 검토를 기다립니다.
    """
    from antigravity_k.engine.evolution import EvolutionManager

    if vault is None:
        raise HTTPException(
            status_code=422,
            detail="VaultEngine is not initialized. Set ANTIGRAVITY_VAULT_PATH environment variable.",
        )

    ev_manager = EvolutionManager(model_manager=manager, vault_engine=vault)
    draft_path = ev_manager.evolve_skill(skill_name=req.skill_name, target_model=req.target_model)

    if draft_path:
        return {
            "status": "success",
            "message": f"Skill '{req.skill_name}' has been successfully evolved.",
            "draft_path": draft_path,
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to evolve skill. Check logs for details.",
        )


class EvolveSystemPromptRequest(BaseModel):
    """Evolvesystempromptrequest.

    Bases: BaseModel
    """

    target_model: str = Field(default="qwen3.6:latest", description="Model to use for evolution")


@router.post("/api/agent/evolve_system_prompt")
async def evolve_system_prompt_api(
    req: EvolveSystemPromptRequest,
    manager: ModelManager = Depends(get_model_manager),
    vault: Any = Depends(get_vault_engine),
):
    """시스템 프롬프트의 자율 진화를 시작합니다."""
    from antigravity_k.engine.evolution import EvolutionManager

    if vault is None:
        raise HTTPException(
            status_code=422,
            detail="VaultEngine is not initialized. Set ANTIGRAVITY_VAULT_PATH environment variable.",
        )

    ev_manager = EvolutionManager(model_manager=manager, vault_engine=vault)
    draft_path = ev_manager.evolve_system_prompt(target_model=req.target_model)

    if draft_path:
        return {
            "status": "success",
            "message": "System prompt has been successfully evolved.",
            "draft_path": draft_path,
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to evolve system prompt.")


@router.get("/v1/models")
def list_models(manager: ModelManager = Depends(get_model_manager)):
    """설치/로드된 모델 목록 반환."""
    import time

    models = manager._registry.list_models()
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
            },
        )
    return {"object": "list", "data": formatted_data}


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


# ─── VAULT CRUD APIs (Wiki + Chat Integration) ──────────────────────


@router.get("/api/vault/config")
def vault_config(engine: VaultEngine = Depends(get_vault_engine)):
    """현재 Vault 설정 조회."""
    if not engine:
        return {"ok": False, "vault_path": None, "message": "VaultEngine not available"}
    return {"ok": True, "vault_path": str(engine.vault_path)}


@router.post("/api/vault/config")
async def set_vault_config(request: Request):
    """Vault 경로를 동적으로 변경 (Wiki + Chat 공유용)."""
    global vault_engine
    body = await request.json()
    new_path = body.get("vault_path", "")
    if not new_path:
        raise HTTPException(status_code=400, detail="'vault_path' is required")
    target = os.path.abspath(new_path)
    if not os.path.isdir(target):
        # 디렉토리가 없으면 생성 시도
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as e:
            raise HTTPException(status_code=400, detail=f"Cannot create directory: {e}")
    try:
        vault_engine = VaultEngine(vault_path=target, sync_rag=True)
    except (OSError, RuntimeError, ValueError) as e:
        logger.warning("Vault 재초기화 실패 (RAG 비활성): %s", e)
        try:
            vault_engine = VaultEngine(vault_path=target, sync_rag=False)
        except (OSError, RuntimeError, ValueError) as e2:
            raise HTTPException(status_code=500, detail=f"Vault init failed: {e2}")
    return {"ok": True, "vault_path": str(vault_engine.vault_path)}


@router.get("/api/vault/tree")
def vault_tree(engine: VaultEngine = Depends(get_vault_engine)):
    """Return the vault directory tree as a nested JSON structure."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")

    def build_tree(base_path: Path, rel_prefix: str = "") -> list:
        items = []
        try:
            entries = sorted(base_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return items
        for entry in entries:
            if entry.name.startswith("."):
                continue
            rel = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            if entry.is_dir():
                children = build_tree(entry, rel)
                items.append(
                    {
                        "name": entry.name,
                        "path": rel,
                        "type": "folder",
                        "children": children,
                    },
                )
            elif entry.suffix.lower() in (".md", ".txt", ".yaml", ".yml"):
                items.append(
                    {
                        "name": entry.name,
                        "path": rel,
                        "type": "file",
                        "size": entry.stat().st_size,
                    },
                )
        return items

    tree = build_tree(engine.vault_path)
    return {"tree": tree, "vault_path": str(engine.vault_path)}


@router.get("/api/vault/read")
def vault_read(path: str, engine: VaultEngine = Depends(get_vault_engine)):
    """Read a note from the vault. Returns metadata + content."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")
    # Security: prevent path traversal
    clean = Path(path)
    if ".." in clean.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        metadata, content = engine.read_note(path)
        return {"path": path, "metadata": metadata, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/vault/write")
async def vault_write(request: Request, engine: VaultEngine = Depends(get_vault_engine)):
    """Create or update a note in the vault."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")
    body = await request.json()
    path = body.get("path", "")
    content = body.get("content", "")
    metadata = body.get("metadata", {})
    if not path:
        raise HTTPException(status_code=400, detail="'path' is required")
    clean = Path(path)
    if ".." in clean.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        engine.write_note(path, metadata, content, commit_message=f"Wiki edit: {path}")
        return {"ok": True, "path": path}
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/vault/sync")
async def vault_sync(engine: VaultEngine = Depends(get_vault_engine)):
    """현재 Vault 상태를 Git 스냅샷으로 저장."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")
    try:
        commit_hash = engine.create_snapshot("Manual sync via Command Palette")
        return {"ok": True, "commit": commit_hash}
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/notes/search")
def search_notes(q: str, engine: VaultEngine = Depends(get_vault_engine)):
    """Search for notes.

    Args:
        q (str): str q.
        engine (VaultEngine): VaultEngine engine.

    """
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    audit = get_audit_logger()
    audit.log_event("search_notes", {"query": q})

    try:
        # 1. Semantic search via RAG (ChromaDB)
        semantic_results = engine.vector_store.search(q, n_results=5)

        # 2. Keyword search via Vault text match
        keyword_results = engine.search_notes(q)

        return {
            "query": q,
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
        }
    except (ValueError, KeyError) as e:
        logger.error("Search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── BACKGROUND TASK API (Codex-style long-horizon tasks) ─────────
from antigravity_k.engine.task_runner import get_task_runner


@router.post("/api/tasks/submit")
async def submit_background_task(
    request: Request,
    manager: ModelManager = Depends(get_model_manager),
    vault: VaultEngine | None = Depends(get_vault_engine),
):
    """백그라운드 태스크 제출 — 장기 실행 작업을 비동기로 처리."""
    body = await request.json()
    prompt = body.get("prompt", "")
    context = body.get("context", {})
    model = body.get("model", "")

    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    orchestrator = get_orchestrator()
    runner = get_task_runner()
    task_id = runner.submit_task(
        prompt=prompt,
        context=context,
        orchestrator=orchestrator,
        target_model=model,
    )

    return {"status": "submitted", "task_id": task_id}


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """태스크 진행 상태 조회."""
    runner = get_task_runner()
    status = runner.get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "data": status}


@router.get("/api/tasks")
async def list_tasks(limit: int = Query(default=20)):
    """최근 태스크 목록."""
    runner = get_task_runner()
    return {"status": "ok", "data": runner.list_tasks(limit=limit)}


@router.get("/api/tasks/{task_id}/output")
async def get_task_output(task_id: str):
    """완료된 태스크의 전체 출력."""
    runner = get_task_runner()
    output = runner.get_output(task_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Task output not found")
    return {"status": "ok", "output": output}


@router.post("/api/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    manager: ModelManager = Depends(get_model_manager),
    vault: VaultEngine | None = Depends(get_vault_engine),
):
    """중단된 태스크를 마지막 체크포인트에서 재개."""
    orchestrator = get_orchestrator()
    runner = get_task_runner()
    success = runner.resume_task(task_id=task_id, orchestrator=orchestrator)
    if not success:
        raise HTTPException(status_code=404, detail="No checkpoint found for task")
    return {"status": "resumed", "task_id": task_id}


# ─── KANBAN API ──────────────────────────────────────────────────
kanban_tasks = []
task_counter = 100
kanban_clients = set()


def _default_project_path() -> str:
    try:
        return str(Path(config.paths.project_root).resolve())
    except Exception:
        logger.exception("Unhandled exception")
        return str(Path.cwd().resolve())


def _normalize_project_path(project_path: str | None = None) -> str:
    raw = str(project_path or "").strip()
    if not raw or raw == "/":
        return _default_project_path()
    return str(Path(raw).expanduser().resolve())


def _project_name(project_path: str) -> str:
    path = Path(project_path)
    return path.name or str(path)


def _task_matches_workspace(task: dict, workspace: str | None) -> bool:
    if not workspace:
        return True
    expected = _normalize_project_path(workspace)
    actual = _normalize_project_path(task.get("project_path"))
    return actual == expected


def _serialize_kanban_payload(tasks: list | None = None) -> dict:
    selected = list(tasks if tasks is not None else kanban_tasks)
    payload = {
        "tasks": selected,
        "todo": [],
        "in_progress": [],
        "completed": [],
        "cancelled": [],
        # Backward-compatible aliases for older Kanban consumers.
        "BACKLOG": [],
        "IN_PROGRESS": [],
        "REVIEW": [],
        "DONE": [],
    }
    for task in selected:
        status = task.get("status", "todo")
        if status in payload:
            payload[status].append(task)
        if status == "todo":
            payload["BACKLOG"].append(task)
        elif status == "in_progress":
            payload["IN_PROGRESS"].append(task)
        elif status == "completed":
            payload["DONE"].append(task)
        elif status == "cancelled":
            payload["DONE"].append(task)
    return payload


async def broadcast_kanban():
    """Broadcast Kanban."""
    # Helper to broadcast the flat task list plus grouped status views.
    message = json.dumps(_serialize_kanban_payload())
    for client in list(kanban_clients):
        try:
            await client.send_text(message)
        except Exception:
            logger.exception("Unhandled exception")
            kanban_clients.discard(client)


def _on_agent_turn_started(**kwargs):
    global task_counter
    task_type = kwargs.get("task_type", "Task")
    role = kwargs.get("role", "WORKER")

    # Check if a similar task is already in progress
    for task in kanban_tasks:
        if task["role"] == role and task["status"] == "in_progress":
            return  # Update existing if needed, or skip

    kanban_tasks.append(
        {
            "id": f"T{task_counter}",
            "title": f"[{role}] {task_type}",
            "description": "Agent is working on the task...",
            "status": "in_progress",
            "type": "Agent",
            "role": role,
            "priority": "normal",
            "project_path": _default_project_path(),
            "project_name": _project_name(_default_project_path()),
        },
    )
    task_counter += 1


def _on_agent_turn_ended(**kwargs):
    role = kwargs.get("role", "WORKER")
    for task in reversed(kanban_tasks):
        if task["role"] == role and task["status"] == "in_progress":
            task["status"] = "completed"
            task["description"] = "Task completed successfully."
            break


from antigravity_k.engine.event_bus import global_event_bus

global_event_bus.subscribe("AgentTurnStarted", _on_agent_turn_started)
global_event_bus.subscribe("AgentTurnEnded", _on_agent_turn_ended)


@router.post("/api/kanban/tasks")
async def create_kanban_task(request: Request):
    """Create kanban task.

    Args:
        request (Request): Request request.

    """
    global task_counter
    data = await request.json()
    project_path = _normalize_project_path(
        data.get("project_path") or data.get("workspace_path") or data.get("workspace"),
    )
    task = {
        "id": f"T{task_counter}",
        "title": data.get("description", "Untitled Task"),
        "description": data.get("description", "Untitled Task"),
        "role": data.get("assignee", "auto"),
        "status": "todo",
        "tokens": 0,
        "type": data.get("type", "Task"),
        "priority": data.get("priority", "normal"),
        "project_path": project_path,
        "project_name": _project_name(project_path),
    }
    task_counter += 1
    kanban_tasks.append(task)
    await broadcast_kanban()
    return task


@router.get("/api/kanban/tasks")
async def get_kanban_tasks(workspace: str | None = Query(None)):
    """Retrieve kanban tasks.

    Args:
        workspace (str | None): str | None workspace.

    """
    tasks = [t for t in kanban_tasks if _task_matches_workspace(t, workspace)]
    return {
        "data": tasks,
        "workspace": _normalize_project_path(workspace) if workspace else None,
    }


@router.post("/api/kanban/tasks/{task_id}/cancel")
async def cancel_kanban_task_endpoint(task_id: str):
    """Cancel Kanban Task Endpoint.

    Args:
        task_id (str): str task id.

    """
    # 실제 백그라운드 엔진 취소 호출 (mocking for non-existing real tasks)
    try:
        from antigravity_k.engine.task_runner import get_task_runner

        runner = get_task_runner()
        runner.cancel_task(task_id)
    except Exception:
        logger.exception("Engine cancel failed or skipped")

    for task in kanban_tasks:
        if str(task["id"]) == str(task_id):
            task["status"] = "cancelled"
            task["title"] = f"[중단됨] {task.get('title', '')}"
            await broadcast_kanban()
            return {"ok": True, "message": "Task cancelled", "task": task}

    raise HTTPException(status_code=404, detail="Task not found")


@router.delete("/api/kanban/tasks/{task_id}")
async def delete_kanban_task_endpoint(task_id: str):
    """Remove kanban task endpoint.

    Args:
        task_id (str): str task id.

    """
    for idx, task in enumerate(list(kanban_tasks)):
        if str(task["id"]) == str(task_id):
            removed = kanban_tasks.pop(idx)
            await broadcast_kanban()
            return {"ok": True, "message": "Task removed", "task": removed}

    raise HTTPException(status_code=404, detail="Task not found")


from pydantic import BaseModel


class StatusUpdate(BaseModel):
    """Statusupdate.

    Bases: BaseModel
    """

    status: str


@router.put("/api/kanban/tasks/{task_id}/status")
async def update_kanban_task_status(task_id: str, update: StatusUpdate):
    """Update kanban task status.

    Args:
        task_id (str): str task id.
        update (StatusUpdate): StatusUpdate update.

    """
    for task in kanban_tasks:
        if task["id"] == task_id:
            task["status"] = update.status
            await broadcast_kanban()
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@router.websocket("/ws/kanban")
async def websocket_kanban(websocket: WebSocket):
    """Websocket Kanban.

    Args:
        websocket (WebSocket): WebSocket websocket.

    """
    await websocket.accept()
    kanban_clients.add(websocket)
    try:
        await websocket.send_text(json.dumps(_serialize_kanban_payload()))

        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.CancelledError):
        kanban_clients.discard(websocket)
    except Exception:
        logger.exception("Unhandled exception")
        kanban_clients.discard(websocket)


import fcntl
import os
import pty
import struct
import termios


@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """Websocket Terminal.

    Args:
        websocket (WebSocket): WebSocket websocket.

    """
    await websocket.accept()

    # Create PTY
    master, slave = pty.openpty()

    # Spawn shell
    shell = os.environ.get("SHELL", "/bin/zsh")
    pid = os.fork()
    if pid == 0:
        # Child process
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(master)
        os.close(slave)
        # Execute the shell
        os.execlp(shell, shell)

    # Parent process
    os.close(slave)

    loop = asyncio.get_running_loop()

    def pty_output_callback():
        try:
            data = os.read(master, 1024)
            if data:
                # Need to use a task to send over websocket
                asyncio.create_task(websocket.send_text(data.decode("utf-8", errors="replace")))
            else:
                loop.remove_reader(master)
        except Exception:
            logger.exception("Unhandled exception")
            loop.remove_reader(master)

    loop.add_reader(master, pty_output_callback)

    def _cleanup_pty():
        """PTY와 자식 프로세스를 정리합니다."""
        try:
            loop.remove_reader(master)
        except Exception:
            logger.exception("Unhandled exception")
            pass
        try:
            os.close(master)
        except OSError:
            pass
        # I-7: Graceful shutdown — SIGTERM 우선, SIGKILL 폴백
        import signal
        import time

        try:
            os.kill(pid, signal.SIGTERM)
            # 최대 2초 대기 후 강제 종료
            for _ in range(20):
                try:
                    result = os.waitpid(pid, os.WNOHANG)
                    if result[0] != 0:
                        break
                except ChildProcessError:
                    break
                time.sleep(0.1)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            # Handle terminal resize message JSON (optional feature)
            if data.startswith('{"type":"resize"'):
                try:
                    msg = json.loads(data)
                    cols = msg.get("cols", 80)
                    rows = msg.get("rows", 24)
                    winsize = struct.pack("HHHH", rows, cols, 0, 0)
                    fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
                except Exception:
                    logger.exception("Resize error")
            else:
                os.write(master, data.encode("utf-8"))
    except (WebSocketDisconnect, asyncio.CancelledError):
        _cleanup_pty()
    except Exception:
        logger.exception("Unhandled exception")
        _cleanup_pty()


# Mount static dashboard if available
# ─── CODE INTEL API ──────────────────────────────────────────────
@router.post("/api/code-intel/index")
async def code_intel_index(request: Request):
    """코드 저장소를 인덱싱합니다."""
    try:
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        data = await request.json()
        repo_path = data.get("repo_path", ".")
        force = data.get("force", False)
        pipeline = CodeIndexPipeline()
        result = pipeline.run(repo_path, force=force)
        return result
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Code Intel 모듈이 설치되지 않았습니다 (pip install networkx rank-bm25)",
        )
    except (json.JSONDecodeError, FileNotFoundError, ValueError, RuntimeError) as e:
        logger.error("Code Intel index error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/code-intel/search")
async def code_intel_search(q: str, repo_path: str, top_k: int = 10):
    """코드 심볼을 하이브리드 검색합니다."""
    try:
        from antigravity_k.engine.code_intel.hybrid_search import HybridSearchEngine
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        pipeline = CodeIndexPipeline()
        loaded = pipeline.load_existing(repo_path)
        if not loaded:
            raise HTTPException(
                status_code=404,
                detail=f"'{repo_path}'의 인덱스가 없습니다. 먼저 인덱싱해주세요.",
            )
        search = HybridSearchEngine(pipeline.graph)
        search.build_index()
        results = search.search(q, top_k=top_k)
        return {"query": q, "results": results}
    except HTTPException:
        raise
    except (ValueError, KeyError, RuntimeError) as e:
        logger.error("Code Intel search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/code-intel/impact")
async def code_intel_impact(request: Request):
    """심볼의 Blast Radius 영향도를 분석합니다."""
    try:
        from antigravity_k.engine.code_intel.impact_analyzer import ImpactAnalyzer
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        data = await request.json()
        repo_path = data.get("repo_path", ".")
        symbol_id = data.get("symbol_id", "")
        max_depth = data.get("max_depth", 5)
        pipeline = CodeIndexPipeline()
        loaded = pipeline.load_existing(repo_path)
        if not loaded:
            raise HTTPException(status_code=404, detail=f"'{repo_path}'의 인덱스가 없습니다.")
        analyzer = ImpactAnalyzer(pipeline.graph)
        result = analyzer.analyze(symbol_id, max_depth=max_depth)
        return result
    except HTTPException:
        raise
    except (ValueError, KeyError, RuntimeError) as e:
        logger.error("Code Intel impact error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Claw Code: Slash Commands & Session API ─────────────────
# P0 수정: 싱글톤 패턴 적용 + SlashRegistry 전체 DI 연결
_slash_registry = None


def _get_slash_registry():
    global _slash_registry
    if _slash_registry is None:
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        _slash_registry = SlashCommandRegistry(
            tool_registry=__get_tool_registry(),
            session_manager=_get_session_manager(),
            context_shaper=_get_context_shaper(),
            model_manager=get_model_manager(),
            skill_loader=__get_skill_loader(),
        )
    return _slash_registry


@router.post("/api/slash")
async def slash_command(request: Request):
    """Slash Command.

    Args:
        request (Request): Request request.

    """
    body = await request.json()
    text = body.get("command") or body.get("input") or body.get("text") or ""
    registry = _get_slash_registry()

    # is_command() 검사를 제거하여 일반 텍스트도 자연어 처리(_execute_natural_language)로 넘어가게 합니다.
    result = registry.execute(text)
    import types

    if isinstance(result, types.GeneratorType):
        result = "".join(str(chunk) for chunk in result)
    return {"ok": True, "result": result}


@router.get("/api/slash/completions")
async def slash_completions(prefix: str = "/"):
    """Slash Completions.

    Args:
        prefix (str): str prefix.

    """
    registry = _get_slash_registry()
    return {"completions": registry.get_completions(prefix)}


@router.get("/api/session/info")
async def session_info():
    """Session Info."""
    sm = _get_session_manager()
    return {"ok": True, "session": sm.get_session_info() or {}}


@router.get("/api/session/messages")
async def session_messages():
    """Session Messages."""
    sm = _get_session_manager()
    sm.start_session(resume=True)
    return {"ok": True, "messages": sm.get_messages()}


@router.post("/api/session/save")
async def session_save():
    """Session Save."""
    # P0 수정: 매번 새 인스턴스 대신 싱글톤 사용
    sm = _get_session_manager()
    sm.save()
    return {"ok": True, "message": "Session saved."}


# ─── File System API (I-6 리팩터링: routes/filesystem.py로 분리) ─────────────────
from antigravity_k.api.routes.filesystem import router as fs_router

router.include_router(fs_router)


# ─── System API (Status & Restart) ─────────────────
import time

import psutil

# 서버 시작 시간 (업타임 계산용)
START_TIME = time.time()


@router.get("/api/system/status")
async def system_status():
    """서버의 현재 상태, 메모리 사용량 및 업타임을 반환합니다."""
    try:
        from antigravity_k.api.dependencies import get_model_manager

        mem_info = psutil.virtual_memory()
        uptime_seconds = int(time.time() - START_TIME)

        # Get global token usage from tracker
        model_manager = get_model_manager()
        total_tokens = model_manager.tracker.get_total_tokens()

        return {
            "ok": True,
            "status": "online",
            "memory_mb": mem_info.percent,  # Returns percentage despite the legacy key name
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "total_tokens": total_tokens,
            "uptime_seconds": uptime_seconds,
            "version": "v0.2.0",
        }
    except (psutil.Error, OSError, RuntimeError) as e:
        logger.error("Status error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import BackgroundTasks


@router.post("/api/system/restart")
async def system_restart(background_tasks: BackgroundTasks):
    """서버 재시작을 트리거합니다 (uvicorn --reload 동작 전제)."""
    try:

        def delay_restart():
            import time

            time.sleep(1.5)
            # uvicorn의 watchfiles가 감지하도록 더미 파일의 시간 스탬프를 업데이트합니다.
            trigger_file = os.path.abspath(".restart_trigger")
            with open(trigger_file, "a"):
                os.utime(trigger_file, None)
            logger.info("Restart triggered via API (delayed).")

        background_tasks.add_task(delay_restart)

        return {
            "ok": True,
            "message": "Restart triggered. The server will reboot in a moment.",
        }
    except (OSError, RuntimeError) as e:
        logger.error("Restart error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class ActiveAgentSession:
    """Activeagentsession."""

    def __init__(self):
        """Initialize the ActiveAgentSession."""
        self.q = ""
        self.is_active = False
        self.history = []
        self.done = False
        self.error = None


_active_session = ActiveAgentSession()


@router.get("/api/agent/active")
async def get_active_agent():
    """Return the currently active agent session if any."""
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
    """Server-Sent Events (SSE) endpoint to stream agent thoughts and outputs.

    Supports reconnection to an ongoing session.
    """
    from starlette.concurrency import iterate_in_threadpool

    async def event_generator():
        global _active_session

        # If reconnecting to an active session
        if reconnect and _active_session.is_active:
            # Yield history first
            for chunk in _active_session.history:
                yield f"data: {json.dumps({'text': chunk})}\n\n"

            # Then poll for new chunks until done
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

        # Start new session
        _active_session = ActiveAgentSession()
        _active_session.is_active = True
        _active_session.q = q

        try:
            # Instantiate orchestrator
            from antigravity_k.engine.orchestrator import OrchestratorAgent

            manager = get_model_manager()
            vault = get_vault_engine()
            orchestrator = OrchestratorAgent(model_manager=manager, vault_engine=vault)

            messages = [{"role": "user", "content": q}]
            target_model = orchestrator._get_model_for_role("default")

            # We don't want the task to cancel if the client disconnects,
            # so we run it completely and buffer. Wait, actually SSE generator
            # might still be cancelled. But with iterate_in_threadpool it usually
            # finishes the thread.
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
            # Client disconnected, but the thread might still run.
            logger.info("SSE client disconnected, but task might continue in thread.")
            raise
        except Exception as e:
            logger.error("SSE Error: %s", e, exc_info=True)
            _active_session.error = str(e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # Delay clearing so reconnects right after finish can see it's done
            _active_session.is_active = False

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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


import yaml


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
        # Mask API keys
        if "api_keys" in cfg:
            for k in cfg["api_keys"]:
                val = cfg["api_keys"][k]
                if val and len(val) > 4:
                    cfg["api_keys"][k] = val[:4] + "*" * (len(val) - 4)
        return {"settings": cfg}
    except Exception as e:
        logger.exception("Unhandled exception")
        return {"settings": {"error": str(e)}}


# ─── Memory & Toolset & Guardrail APIs ─────────────────────────────────────

from antigravity_k.engine.memory_provider import BuiltinMemoryProvider, MemoryManager
from antigravity_k.engine.toolset_manager import ToolsetManager

_memory_manager: MemoryManager | None = None
_toolset_manager: ToolsetManager | None = None


def _get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
        try:
            sm = _get_session_manager()
            _memory_manager.add_provider(BuiltinMemoryProvider(sm))
        except Exception:
            logger.exception("BuiltinMemoryProvider 초기화 실패")
    return _memory_manager


def _get_toolset_manager() -> ToolsetManager:
    global _toolset_manager
    if _toolset_manager is None:
        try:
            config_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "config.yaml",
            )
            if os.path.exists(config_file):
                with open(config_file, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                _toolset_manager = ToolsetManager.from_config(cfg.get("toolsets", {}))
            else:
                _toolset_manager = ToolsetManager()
        except Exception:
            logger.exception("Unhandled exception")
            _toolset_manager = ToolsetManager()
    return _toolset_manager


@router.get("/api/memory/stats")
async def get_memory_stats():
    """메모리 시스템 상태를 반환합니다."""
    mm = _get_memory_manager()
    return {"memory": mm.get_stats()}


@router.get("/api/memory/recall")
async def recall_memory(query: str = ""):
    """쿼리 기반 메모리 회상."""
    mm = _get_memory_manager()
    result = mm.prefetch_all(query or "general")
    return {"recalled": result, "query": query}


@router.get("/api/toolsets")
async def list_toolsets():
    """등록된 모든 toolset 목록을 반환합니다."""
    ts = _get_toolset_manager()
    return {"toolsets": ts.list_toolsets(), "active": ts.active_toolset}


@router.post("/api/toolsets/activate")
async def activate_toolset(request: Request):
    """활성 toolset을 변경합니다."""
    body = await request.json()
    name = body.get("name", "full")
    ts = _get_toolset_manager()
    success = ts.set_active(name)
    return {
        "success": success,
        "active": ts.active_toolset,
        "tools": ts.get_active_tools() if success else [],
    }


@router.get("/api/toolsets/{name}/tools")
async def get_toolset_tools(name: str):
    """특정 toolset의 해석된 도구 목록을 반환합니다."""
    ts = _get_toolset_manager()
    tools = ts.resolve(name)
    return {"toolset": name, "tools": tools, "count": len(tools)}


@router.get("/api/system/full-status")
async def get_system_status_extended():
    """시스템 전체 상태를 반환합니다 (메모리, toolset, 가드레일, shields 포함)."""
    mm = _get_memory_manager()
    ts = _get_toolset_manager()
    shields = _get_shields_manager()
    return {
        "status": "running",
        "memory": mm.get_stats(),
        "toolset": {
            "active": ts.active_toolset,
            "available": list(ts.list_toolsets().keys()),
        },
        "guardrails": {
            "warnings_enabled": True,
            "hard_stop_enabled": False,
        },
        "shields": shields.status(),
    }


# ─── Harness Engineering API (Self-Test & Intent-Based Testing) ──────────────

_harness_instance = None


def get_harness():
    """Retrieve harness."""
    global _harness_instance
    if _harness_instance is None:
        from antigravity_k.engine.harness import TestHarness

        _harness_instance = TestHarness()
    return _harness_instance


@router.post("/api/harness/self-test")
async def harness_self_test(request: Request):
    """에이전트가 대시보드 전체를 자동 테스트합니다."""
    try:
        body = await request.json()
    except Exception:
        logger.exception("Unhandled exception")
        body = {}

    scope = body.get("scope", "api_only")  # 기본: API만 (브라우저 없이 빠르게)

    harness = get_harness()
    report = await harness.run_all(use_browser=(scope != "api_only"))

    return {"ok": True, "report": report.to_dict()}


@router.get("/api/harness/results")
async def harness_results():
    """최근 테스트 결과를 조회합니다."""
    harness = get_harness()
    report = harness.get_latest_report()
    if report:
        return {"ok": True, "report": report.to_dict()}
    return {"ok": True, "report": None, "message": "아직 테스트가 실행되지 않았습니다."}


@router.get("/api/harness/trend")
async def harness_trend():
    """테스트 추세를 조회합니다."""
    harness = get_harness()
    trend = harness.feedback.get_trend()
    return {"ok": True, "trend": trend}


# ─── Shields & Security APIs (NemoClaw ported) ──────────────────────────────

from antigravity_k.engine.runtime_recovery import (
    deep_health_check,
)
from antigravity_k.engine.secret_scanner import (
    redact,
    scan_for_secrets,
    strip_credentials,
)
from antigravity_k.engine.shields import ShieldsManager

_shields_manager: ShieldsManager | None = None


def _get_shields_manager() -> ShieldsManager:
    global _shields_manager
    if _shields_manager is None:
        try:
            config_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "config.yaml",
            )
            shields_config = {}
            if os.path.exists(config_file):
                with open(config_file, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                shields_config = cfg.get("shields", {})
            _shields_manager = ShieldsManager.from_config(
                shields_config,
                toolset_manager=_get_toolset_manager(),
            )
        except Exception:
            logger.exception("Unhandled exception")
            _shields_manager = ShieldsManager(
                toolset_manager=_get_toolset_manager(),
            )
    return _shields_manager


@router.get("/api/shields/status")
async def get_shields_status():
    """현재 Shields 보호 레벨을 조회합니다."""
    shields = _get_shields_manager()
    return shields.status()


@router.post("/api/shields/down")
async def shields_down(request: Request):
    """Shields를 내립니다 (시간 제한 권한 완화).

    Body:
        reason: 변경 사유 (선택)
        timeout_seconds: 타임아웃 초 (선택, 기본 300)
        target_toolset: 완화 시 toolset (선택, 기본 "full")
    """
    body = await request.json()
    shields = _get_shields_manager()
    shields.shields_down(
        reason=body.get("reason"),
        timeout_seconds=body.get("timeout_seconds"),
        target_toolset=body.get("target_toolset", "full"),
    )
    return shields.status()


@router.post("/api/shields/up")
async def shields_up():
    """Shields를 올립니다 (보호 복원)."""
    shields = _get_shields_manager()
    shields.shields_up(restored_by="api_operator")
    return shields.status()


@router.get("/api/shields/audit")
async def get_shields_audit(limit: int = Query(default=50, ge=1, le=500)):
    """Shields 감사 로그를 조회합니다."""
    shields = _get_shields_manager()
    return {"audit_log": shields.get_audit_log(limit=limit)}


@router.post("/api/security/scan")
async def scan_text_for_secrets(request: Request):
    """텍스트에서 시크릿을 스캔합니다.

    Body:
        text: 스캔할 텍스트
        redact_mode: "partial" (기본) | "full"
    """
    body = await request.json()
    text = body.get("text", "")
    mode = body.get("redact_mode", "partial")

    matches = scan_for_secrets(text)
    from antigravity_k.engine.secret_scanner import redact_full

    redacted_text = redact(text) if mode == "partial" else redact_full(text)

    return {
        "secrets_found": len(matches),
        "matches": [{"pattern": m.pattern, "redacted": m.redacted} for m in matches],
        "redacted_text": redacted_text,
    }


@router.post("/api/security/strip-config")
async def strip_config_credentials(request: Request):
    """설정 딕셔너리에서 민감 필드를 제거합니다.

    Body:
        config: 필터링할 설정 딕셔너리
    """
    body = await request.json()
    config = body.get("config", {})
    return {"sanitized": strip_credentials(config)}


@router.get("/api/health/deep")
async def get_deep_health():
    """전체 시스템 깊은 Health Check를 수행합니다.

    인퍼런스, 메모리, 가드레일, shields 등 모든 컴포넌트를 점검합니다.
    """
    from dataclasses import asdict

    health = deep_health_check(
        model_manager=get_model_manager(),
        session_manager=_get_session_manager(),
        memory_manager=_get_memory_manager(),
        toolset_manager=_get_toolset_manager(),
        shields_manager=_get_shields_manager(),
    )
    return {
        "status": health.status.value,
        "components": [asdict(c) for c in health.components],
        "diagnosis": health.diagnosis,
        "checked_at": health.checked_at,
    }
