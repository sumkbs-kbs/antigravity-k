import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, Request, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError, BaseModel, Field

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.protocol_translator import ProtocolTranslator, APIFormat
from antigravity_k.api.models import (
    ChatCompletionRequest, ChatCompletionResponse,
    EmbeddingRequest, EmbeddingResponse, EmbeddingData, UsageStats
)
from antigravity_k.engine.embeddings import EmbeddingEngine, get_embedding_engine
from antigravity_k.engine.audit_logger import get_audit_logger
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.model_registry import ModelRegistry
import os
import json
import shutil
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from antigravity_k.engine.orchestrator import OrchestratorAgent

logger = logging.getLogger("antigravity_k.api.server")

app = FastAPI(
    title="Antigravity-K API",
    description="OpenAI-compatible API for Antigravity-K Local Engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
model_manager: Optional[ModelManager] = None
protocol_translator: Optional[ProtocolTranslator] = None
vault_engine: Optional[VaultEngine] = None

# ─── Claw Code 싱글톤 인스턴스 (P0 수정: 매번 새 인스턴스 생성 방지) ───
from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.session_manager import SessionManager

_tool_registry: Optional[ToolRegistry] = None
_context_shaper: Optional[ContextShaper] = None
_session_manager: Optional[SessionManager] = None
_orchestrator: Optional[OrchestratorAgent] = None

def _get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

def __get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry

def _get_context_shaper() -> ContextShaper:
    global _context_shaper
    if _context_shaper is None:
        _context_shaper = ContextShaper()
    return _context_shaper

def get_model_manager() -> ModelManager:
    global model_manager
    if model_manager is None:
        logger.info("Lazy initializing ModelManager...")
        registry = ModelRegistry("config.yaml") # Assumes config.yaml is in current directory
        model_manager = ModelManager(registry)
    return model_manager

def get_orchestrator() -> OrchestratorAgent:
    """Orchestrator 싱글톤 — 매 요청마다 재생성하지 않음 (C-4 수정)"""
    global _orchestrator
    if _orchestrator is None:
        logger.info("Lazy initializing OrchestratorAgent (singleton)...")
        _orchestrator = OrchestratorAgent(
            model_manager=get_model_manager(),
            vault_engine=get_vault_engine(),
        )
    return _orchestrator

def get_translator() -> ProtocolTranslator:
    global protocol_translator
    if protocol_translator is None:
        logger.info("Lazy initializing ProtocolTranslator...")
        protocol_translator = ProtocolTranslator()
    return protocol_translator

def get_vault_engine() -> Optional[VaultEngine]:
    global vault_engine
    if vault_engine is None:
        vault_path = os.environ.get("ANTIGRAVITY_VAULT_PATH", "./vault_data")
        try:
            vault_engine = VaultEngine(vault_path=vault_path, sync_rag=True)
        except Exception as e:
            logger.warning(f"VaultEngine 초기화 실패 (RAG 비활성): {e}")
            try:
                vault_engine = VaultEngine(vault_path=vault_path, sync_rag=False)
            except Exception as e2:
                logger.error(f"VaultEngine 완전 실패: {e2}")
                return None
    return vault_engine

@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    manager: ModelManager = Depends(get_model_manager),
    translator: ProtocolTranslator = Depends(get_translator),
    vault: Optional[VaultEngine] = Depends(get_vault_engine)
):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    source_format = translator.detect_format(body)
    internal_req = translator.translate_request(body, source=source_format)
    
    target_model = internal_req.get("model", "")
    if not target_model:
        raise HTTPException(status_code=400, detail="Model is required")
        
    messages = internal_req.get("messages", [])
    
    # Check flags
    is_stream = body.get("stream", False)
    # Default to True for Vibe Coding natural language tool execution
    is_agent_mode = body.get("agent_mode", True)
    
    audit = get_audit_logger()
    audit.log_event("chat_request", {"model": target_model, "stream": is_stream, "agent": is_agent_mode})
    
    if is_stream and is_agent_mode:
        orchestrator = get_orchestrator()
        
        def event_generator():
            try:
                for chunk in orchestrator.run_stream(messages, target_model=target_model):
                    # Format as SSE
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": target_model,
                        "choices": [{"delta": {"content": chunk}, "index": 0, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}")
                data = {"choices": [{"delta": {"content": f"\n\n[Error: {str(e)}]"}, "index": 0, "finish_reason": "error"}]}
                yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
                
        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    # Non-streaming or non-agent mode (fallback to original logic)
    system_msg = internal_req.get("system", "")
    prompt = ""
    if system_msg:
        prompt += f"System: {system_msg}\n\n"
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
        prompt += f"{role.capitalize()}: {content}\n"
    prompt += "Assistant: "

    try:
        kwargs = {
            "max_tokens": internal_req.get("max_tokens", 1024),
            "temperature": internal_req.get("temperature", 0.7),
        }
        
        if is_stream:
            # Native model streaming (no agent tools)
            def event_generator_native():
                for chunk in manager.stream_generate(prompt=prompt, target=target_model, **kwargs):
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "model": target_model,
                        "choices": [{"delta": {"content": chunk}, "index": 0, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(event_generator_native(), media_type="text/event-stream")
        else:
            response_text = manager.generate(prompt=prompt, target=target_model, **kwargs)
            internal_resp = {
                "content": response_text,
                "model": target_model,
                "finish_reason": "stop",
                "tokens_in": len(prompt) // 4,
                "tokens_out": len(response_text) // 4,
            }
            target_format = source_format if source_format != APIFormat.INTERNAL else APIFormat.OPENAI
            final_response = translator.translate_response(internal_resp, source=APIFormat.INTERNAL, target=target_format)
            audit.log_event("chat_response", {"model": target_model, "response": final_response})
            return final_response
            
    except Exception as e:
        logger.error(f"Generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/health")
def health_check():
    manager = get_model_manager()
    info = manager.status() if manager else {}
    backends = info.get("loaded_models", {}) if isinstance(info, dict) else {}
    return {"status": "ok", "backends": backends}

class WakeRequest(BaseModel):
    event_type: str = Field(..., description="Type of event (e.g. 'file_changed', 'lint_error', 'comment')")
    payload: Dict[str, Any] = Field(..., description="Detailed payload for the event")
    target_model: str = Field(default="qwen3.6:latest", description="Model to use for the wake task")

@app.post("/api/agent/wake")
async def wake_agent(
    req: WakeRequest,
    manager: ModelManager = Depends(get_model_manager),
    registry: Any = Depends(__get_tool_registry),
    vault: Any = Depends(get_vault_engine)
):
    """
    Paperclip의 Comment-driven Wake 개념을 포팅.
    특정 시스템 이벤트 발생 시 에이전트가 백그라운드에서 즉시 기상하여 태스크를 수행합니다.
    """
    from antigravity_k.engine.task_runner import get_task_runner
    from antigravity_k.engine.orchestrator import OrchestratorAgent
    
    runner = get_task_runner()
    orchestrator = get_orchestrator()
    
    prompt = f"System Wake Event Triggered:\n- Type: {req.event_type}\n- Details: {json.dumps(req.payload, ensure_ascii=False)}\n\nPlease analyze this event and take any necessary actions."
    
    task_id = runner.submit_task(
        prompt=prompt,
        orchestrator=orchestrator,
        target_model=req.target_model,
        context={"wake_event": req.event_type, "use_worktree": False}
    )
    
    return {
        "status": "woken",
        "task_id": task_id,
        "message": f"Agent woken by '{req.event_type}' event and assigned background task {task_id}."
    }

class EvolveRequest(BaseModel):
    skill_name: str = Field(..., description="Name of the skill to evolve")
    target_model: str = Field(default="qwen3.6:latest", description="Model to use for evolution")

@app.post("/api/agent/evolve")
async def evolve_skill_api(
    req: EvolveRequest,
    manager: ModelManager = Depends(get_model_manager),
    vault: Any = Depends(get_vault_engine)
):
    """
    특정 스킬에 대해 과거 실패 이력을 바탕으로 한 자율 진화(Self-Evolution)를 시작합니다.
    진화된 결과는 SKILL_EVOLVED.md 로 저장되어 인간의 검토를 기다립니다.
    """
    from antigravity_k.engine.evolution import EvolutionManager
    
    if vault is None:
        raise HTTPException(status_code=422, detail="VaultEngine is not initialized. Set ANTIGRAVITY_VAULT_PATH environment variable.")
    
    ev_manager = EvolutionManager(model_manager=manager, vault_engine=vault)
    draft_path = ev_manager.evolve_skill(skill_name=req.skill_name, target_model=req.target_model)
    
    if draft_path:
        return {
            "status": "success",
            "message": f"Skill '{req.skill_name}' has been successfully evolved.",
            "draft_path": draft_path
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to evolve skill. Check logs for details.")

class EvolveSystemPromptRequest(BaseModel):
    target_model: str = Field(default="qwen3.6:latest", description="Model to use for evolution")

@app.post("/api/agent/evolve_system_prompt")
async def evolve_system_prompt_api(
    req: EvolveSystemPromptRequest,
    manager: ModelManager = Depends(get_model_manager),
    vault: Any = Depends(get_vault_engine)
):
    """
    시스템 프롬프트의 자율 진화를 시작합니다.
    """
    from antigravity_k.engine.evolution import EvolutionManager
    
    if vault is None:
        raise HTTPException(status_code=422, detail="VaultEngine is not initialized. Set ANTIGRAVITY_VAULT_PATH environment variable.")
    
    ev_manager = EvolutionManager(model_manager=manager, vault_engine=vault)
    draft_path = ev_manager.evolve_system_prompt(target_model=req.target_model)
    
    if draft_path:
        return {
            "status": "success",
            "message": "System prompt has been successfully evolved.",
            "draft_path": draft_path
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to evolve system prompt.")

@app.get("/v1/models")
def list_models(manager: ModelManager = Depends(get_model_manager)):
    """설치/로드된 모델 목록 반환"""
    import time
    models = manager._registry.list_models()
    # Ensure it follows OpenAI-like format
    formatted_data = []
    for m in models:
        formatted_data.append({
            "id": m.name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "system",
            "role": m.role,
            "description": m.description
        })
    return {"object": "list", "data": formatted_data}

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    engine: EmbeddingEngine = Depends(get_embedding_engine)
):
    audit = get_audit_logger()
    audit.log_event("embedding_request", {"model": request.model, "input_len": len(request.input)})
    
    try:
        # Generate embeddings
        embeddings = engine.embed(request.input, request.model)
        
        # Format response
        data = []
        for i, emb in enumerate(embeddings):
            data.append(EmbeddingData(
                embedding=emb,
                index=i
            ))
            
        # Basic usage tracking (dummy for now)
        tokens = sum(len(t) // 4 for t in request.input) if isinstance(request.input, list) else len(request.input) // 4
        
        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage=UsageStats(prompt_tokens=tokens, total_tokens=tokens)
        )
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── VAULT CRUD APIs (Wiki + Chat Integration) ──────────────────────

@app.get("/api/vault/config")
def vault_config(engine: VaultEngine = Depends(get_vault_engine)):
    """현재 Vault 설정 조회"""
    if not engine:
        return {"ok": False, "vault_path": None, "message": "VaultEngine not available"}
    return {"ok": True, "vault_path": str(engine.vault_path)}

@app.post("/api/vault/config")
async def set_vault_config(request: Request):
    """Vault 경로를 동적으로 변경 (Wiki + Chat 공유용)"""
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
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot create directory: {e}")
    try:
        vault_engine = VaultEngine(vault_path=target, sync_rag=True)
    except Exception as e:
        logger.warning(f"Vault 재초기화 실패 (RAG 비활성): {e}")
        try:
            vault_engine = VaultEngine(vault_path=target, sync_rag=False)
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Vault init failed: {e2}")
    return {"ok": True, "vault_path": str(vault_engine.vault_path)}

@app.get("/api/vault/tree")
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
                items.append({"name": entry.name, "path": rel, "type": "folder", "children": children})
            elif entry.suffix.lower() in (".md", ".txt", ".yaml", ".yml"):
                items.append({"name": entry.name, "path": rel, "type": "file", "size": entry.stat().st_size})
        return items

    tree = build_tree(engine.vault_path)
    return {"tree": tree, "vault_path": str(engine.vault_path)}

@app.get("/api/vault/read")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vault/write")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/notes/search")
def search_notes(q: str, engine: VaultEngine = Depends(get_vault_engine)):
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
            "keyword_results": keyword_results
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── BACKGROUND TASK API (Codex-style long-horizon tasks) ─────────
from antigravity_k.engine.task_runner import get_task_runner

@app.post("/api/tasks/submit")
async def submit_background_task(request: Request, manager: ModelManager = Depends(get_model_manager), vault: Optional[VaultEngine] = Depends(get_vault_engine)):
    """백그라운드 태스크 제출 — 장기 실행 작업을 비동기로 처리"""
    body = await request.json()
    prompt = body.get("prompt", "")
    context = body.get("context", {})
    model = body.get("model", "")
    
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    
    orchestrator = get_orchestrator()
    runner = get_task_runner()
    task_id = runner.submit_task(prompt=prompt, context=context, orchestrator=orchestrator, target_model=model)
    
    return {"status": "submitted", "task_id": task_id}

@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """태스크 진행 상태 조회"""
    runner = get_task_runner()
    status = runner.get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "data": status}

@app.get("/api/tasks")
async def list_tasks(limit: int = Query(default=20)):
    """최근 태스크 목록"""
    runner = get_task_runner()
    return {"status": "ok", "data": runner.list_tasks(limit=limit)}

@app.get("/api/tasks/{task_id}/output")
async def get_task_output(task_id: str):
    """완료된 태스크의 전체 출력"""
    runner = get_task_runner()
    output = runner.get_output(task_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Task output not found")
    return {"status": "ok", "output": output}

@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str, manager: ModelManager = Depends(get_model_manager), vault: Optional[VaultEngine] = Depends(get_vault_engine)):
    """중단된 태스크를 마지막 체크포인트에서 재개"""
    orchestrator = get_orchestrator()
    runner = get_task_runner()
    success = runner.resume_task(task_id=task_id, orchestrator=orchestrator)
    if not success:
        raise HTTPException(status_code=404, detail="No checkpoint found for task")
    return {"status": "resumed", "task_id": task_id}

# ─── KANBAN API ──────────────────────────────────────────────────
kanban_tasks = [
    {"id": "1", "title": "사이드바 UI 렌더링", "description": "모든 사이드바 메뉴 컴포넌트 마운트", "status": "completed", "type": "Frontend"},
    {"id": "2", "title": "IDE 컨텍스트 동기화", "description": "VSCode 54321 포트 연동 및 실시간 상태 수신", "status": "completed", "type": "Backend"},
    {"id": "3", "title": "코드 리뷰 에이전트 구동", "description": "변경된 파일 목록 모니터링 및 자율 리뷰 준비", "status": "in_progress", "type": "Agent", "priority": "high"},
    {"id": "4", "title": "Git Auto Commit 연동", "description": "Orchestrator 종료 후 자동 커밋 푸시", "status": "todo", "type": "Ops"}
]
task_counter = 100
kanban_clients = set()

async def broadcast_kanban():
    # Helper to broadcast state to all connected clients
    state = {"todo": [], "in_progress": [], "completed": []}
    for t in kanban_tasks:
        if t["status"] in state:
            state[t["status"]].append(t)
    message = json.dumps(state)
    for client in list(kanban_clients):
        try:
            await client.send_text(message)
        except Exception:
            kanban_clients.discard(client)

@app.post("/api/kanban/tasks")
async def create_kanban_task(request: Request):
    global task_counter
    data = await request.json()
    task = {
        "id": f"T{task_counter}",
        "title": data.get("description", "Untitled Task"),
        "role": data.get("assignee", "auto"),
        "status": "todo",
        "tokens": 0
    }
    task_counter += 1
    kanban_tasks.append(task)
    await broadcast_kanban()
    return task

@app.get("/api/kanban/tasks")
async def get_kanban_tasks():
    return {"data": kanban_tasks}

@app.post("/api/kanban/tasks/{task_id}/cancel")
async def cancel_kanban_task_endpoint(task_id: str):
    # 실제 백그라운드 엔진 취소 호출 (mocking for non-existing real tasks)
    try:
        from antigravity_k.engine.task_runner import get_task_runner
        runner = get_task_runner()
        runner.cancel_task(task_id)
    except Exception as e:
        logger.warning(f"Engine cancel failed or skipped: {e}")
        
    for task in kanban_tasks:
        if str(task["id"]) == str(task_id):
            task["status"] = "completed"
            task["title"] = f"[중단됨] {task.get('title', '')}"
            await broadcast_kanban()
            return {"ok": True, "message": "Task cancelled"}
            
    raise HTTPException(status_code=404, detail="Task not found")

from pydantic import BaseModel
class StatusUpdate(BaseModel):
    status: str

@app.put("/api/kanban/tasks/{task_id}/status")
async def update_kanban_task_status(task_id: str, update: StatusUpdate):
    for task in kanban_tasks:
        if task["id"] == task_id:
            task["status"] = update.status
            await broadcast_kanban()
            return task
    raise HTTPException(status_code=404, detail="Task not found")

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/kanban")
async def websocket_kanban(websocket: WebSocket):
    await websocket.accept()
    kanban_clients.add(websocket)
    try:
        # Send initial state
        state = {"BACKLOG": [], "IN_PROGRESS": [], "REVIEW": [], "DONE": []}
        for t in kanban_tasks:
            state[t["status"]].append(t)
        await websocket.send_text(json.dumps(state))
        
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        kanban_clients.discard(websocket)

import pty
import os
import termios
import struct
import fcntl
import asyncio

@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
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
            loop.remove_reader(master)
            
    loop.add_reader(master, pty_output_callback)
    
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
                except Exception as e:
                    logger.error(f"Resize error: {e}")
            else:
                os.write(master, data.encode("utf-8"))
    except WebSocketDisconnect:
        loop.remove_reader(master)
        os.close(master)
        # I-7: Graceful shutdown — SIGTERM 우선, SIGKILL 폴백
        import signal, time
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

# Mount static dashboard if available
# ─── CODE INTEL API ──────────────────────────────────────────────
@app.post("/api/code-intel/index")
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
        raise HTTPException(status_code=501, detail="Code Intel 모듈이 설치되지 않았습니다 (pip install networkx rank-bm25)")
    except Exception as e:
        logger.error(f"Code Intel index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/code-intel/search")
async def code_intel_search(q: str, repo_path: str, top_k: int = 10):
    """코드 심볼을 하이브리드 검색합니다."""
    try:
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline
        from antigravity_k.engine.code_intel.hybrid_search import HybridSearchEngine
        pipeline = CodeIndexPipeline()
        loaded = pipeline.load_existing(repo_path)
        if not loaded:
            raise HTTPException(status_code=404, detail=f"'{repo_path}'의 인덱스가 없습니다. 먼저 인덱싱해주세요.")
        search = HybridSearchEngine(pipeline.graph)
        search.build_index()
        results = search.search(q, top_k=top_k)
        return {"query": q, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Code Intel search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/code-intel/impact")
async def code_intel_impact(request: Request):
    """심볼의 Blast Radius 영향도를 분석합니다."""
    try:
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline
        from antigravity_k.engine.code_intel.impact_analyzer import ImpactAnalyzer
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
    except Exception as e:
        logger.error(f"Code Intel impact error: {e}")
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
        )
    return _slash_registry


@app.post("/api/slash")
async def slash_command(request: Request):
    body = await request.json()
    text = body.get("command", "")
    registry = _get_slash_registry()
    
    # is_command() 검사를 제거하여 일반 텍스트도 자연어 처리(_execute_natural_language)로 넘어가게 합니다.
    result = registry.execute(text)
    return {"ok": True, "result": result}


@app.get("/api/slash/completions")
async def slash_completions(prefix: str = "/"):
    registry = _get_slash_registry()
    return {"completions": registry.get_completions(prefix)}


@app.get("/api/session/info")
async def session_info():
    # P0 수정: 매번 새 인스턴스 대신 싱글톤 사용
    sm = _get_session_manager()
    return {"ok": True, "session": sm.get_session_info() or {}}


@app.post("/api/session/save")
async def session_save():
    # P0 수정: 매번 새 인스턴스 대신 싱글톤 사용
    sm = _get_session_manager()
    sm.save()
    return {"ok": True, "message": "Session saved."}


# ─── File System API (For IDE Layout) ─────────────────
# 전역 워크스페이스 상태 (서버 실행 시 기본값은 현재 폴더)
WORKSPACE_ROOT = os.path.abspath(".")

from pydantic import BaseModel
class WorkspaceRequest(BaseModel):
    path: str

@app.get("/api/fs/workspace")
async def get_workspace():
    global WORKSPACE_ROOT
    return {"ok": True, "workspace": WORKSPACE_ROOT}

@app.post("/api/fs/workspace")
async def set_workspace(req: WorkspaceRequest):
    global WORKSPACE_ROOT
    target = os.path.abspath(req.path)
    if os.path.exists(target) and os.path.isdir(target):
        WORKSPACE_ROOT = target
        return {"ok": True, "workspace": WORKSPACE_ROOT}
    raise HTTPException(status_code=400, detail="Invalid directory path")

def run_workspace_ingestion(workspace_path: str, vault_engine: VaultEngine):
    """Background task to ingest workspace"""
    try:
        vault_engine.ingest_workspace(workspace_path)
        logger.info(f"Background ingestion completed for {workspace_path}")
    except Exception as e:
        logger.error(f"Background ingestion failed: {e}")

@app.post("/api/workspace/ingest")
async def ingest_workspace(
    background_tasks: BackgroundTasks,
    path: Optional[str] = Query(None, description="Target path to index"),
    vault: Optional[VaultEngine] = Depends(get_vault_engine)
):
    global WORKSPACE_ROOT
    if not vault:
        raise HTTPException(status_code=500, detail="VaultEngine not initialized")
    
    target_path = path if path else WORKSPACE_ROOT
    
    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Workspace not set or invalid")
        
    background_tasks.add_task(run_workspace_ingestion, target_path, vault)
    return {"ok": True, "message": "Workspace indexing started in background"}

@app.get("/api/fs/browse")
async def fs_browse(dir: str = "/"):
    """시스템 전체를 브라우징하는 전용 API (보안 제한 없음, 로컬 구동 전제)"""
    try:
        target_dir = os.path.abspath(dir)
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            target_dir = os.path.abspath("/") # 기본 루트 폴백

        items = []
        try:
            for entry in os.scandir(target_dir):
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    items.append({
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": True
                    })
        except PermissionError:
            pass # 권한 없는 폴더는 스킵

        items.sort(key=lambda x: x["name"].lower())
        
        parent_dir = os.path.dirname(target_dir)
        if target_dir == parent_dir:
            parent_dir = None
            
        return {"ok": True, "current": target_dir, "parent": parent_dir, "items": items}
    except Exception as e:
        logger.error(f"FS browse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
class MkdirRequest(BaseModel):
    path: str

@app.post("/api/fs/mkdir")
async def fs_mkdir(req: MkdirRequest):
    """지정된 경로에 새 디렉토리를 생성합니다"""
    try:
        global WORKSPACE_ROOT
        
        # dir이 "."이면 WORKSPACE_ROOT 자체를 의미
        clean_path = req.path.lstrip("/\\")
        if clean_path == "." or clean_path == "":
            raise HTTPException(status_code=400, detail="Invalid path for folder creation")
            
        target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, clean_path))
        
        # 보안: 워크스페이스 벗어나지 못하도록 제한
        if not target_dir.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")
            
        if os.path.exists(target_dir):
            return {"ok": False, "detail": "Folder already exists"}
            
        os.makedirs(target_dir, exist_ok=True)
        return {"ok": True, "path": target_dir}
    except Exception as e:
        logger.error(f"FS mkdir error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DeleteRequest(BaseModel):
    path: str

@app.delete("/api/fs/delete")
async def fs_delete(req: DeleteRequest):
    """지정된 파일 또는 디렉토리를 삭제합니다"""
    try:
        global WORKSPACE_ROOT
        
        clean_path = req.path.lstrip("/\\")
        if clean_path == "." or clean_path == "":
            raise HTTPException(status_code=400, detail="Cannot delete workspace root")
            
        target_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, clean_path))
        
        if not target_path.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")
            
        if not os.path.exists(target_path):
            return {"ok": False, "detail": "Path does not exist"}
            
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)
            
        return {"ok": True, "path": target_path}
    except Exception as e:
        logger.error(f"FS delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fs/list")
async def fs_list(dir: str = "."):
    """디렉토리 목록을 반환합니다 (WORKSPACE_ROOT로 제한)"""
    try:
        global WORKSPACE_ROOT
        
        # dir이 "."이면 WORKSPACE_ROOT 자체를 의미
        if dir == ".":
            target_dir = WORKSPACE_ROOT
        else:
            # 넘어온 경로는 상대경로거나 절대경로일 수 있음
            # WORKSPACE_ROOT를 기준으로 조인
            target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, dir))
            
        # 보안: 워크스페이스 벗어나지 못하도록 제한
        if not target_dir.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")
            
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            return {"ok": False, "items": []}
            
        items = []
        for entry in os.scandir(target_dir):
            # 숨김 파일/폴더 제외 (.git, .gemini 등)
            if entry.name.startswith('.'):
                continue
            # path는 WORKSPACE_ROOT 기준 상대경로로 반환
            items.append({
                "name": entry.name,
                "path": os.path.relpath(entry.path, WORKSPACE_ROOT),
                "is_dir": entry.is_dir()
            })
            
        # 폴더 먼저, 그 다음 파일 순으로 정렬
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"ok": True, "items": items}
    except Exception as e:
        logger.error(f"FS list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fs/read")
async def fs_read(file: str):
    """파일 내용을 반환합니다."""
    try:
        global WORKSPACE_ROOT
        target_file = os.path.abspath(os.path.join(WORKSPACE_ROOT, file))
        if not target_file.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")
            
        if not os.path.exists(target_file) or not os.path.isfile(target_file):
            raise HTTPException(status_code=404, detail="File not found.")
            
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {"ok": True, "content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cannot read binary file.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FS read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── System API (Status & Restart) ─────────────────
import psutil
import time

# 서버 시작 시간 (업타임 계산용)
START_TIME = time.time()

@app.get("/api/system/status")
async def system_status():
    """서버의 현재 상태, 메모리 사용량 및 업타임을 반환합니다."""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        uptime_seconds = int(time.time() - START_TIME)
        
        return {
            "ok": True,
            "status": "online",
            "memory_mb": round(mem_info.rss / (1024 * 1024), 1),
            "cpu_percent": process.cpu_percent(),
            "uptime_seconds": uptime_seconds,
            "version": "v0.2.0"
        }
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/restart")
async def system_restart():
    """서버 재시작을 트리거합니다 (uvicorn --reload 동작 전제)."""
    try:
        # uvicorn의 watchfiles가 감지하도록 더미 파일의 시간 스탬프를 업데이트합니다.
        trigger_file = os.path.abspath(".restart_trigger")
        with open(trigger_file, "a"):
            os.utime(trigger_file, None)
            
        logger.info("Restart triggered via API.")
        return {"ok": True, "message": "Restart triggered. The server will reboot in a moment."}
    except Exception as e:
        logger.error(f"Restart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))





@app.get("/api/stream_agent")
async def stream_agent(q: str = Query(..., description="User prompt to the agent")):
    """
    Server-Sent Events (SSE) endpoint to stream agent thoughts and outputs.
    """
    async def event_generator():
        try:
            # Instantiate orchestrator
            manager = get_model_manager()
            vault = get_vault_engine()
            orchestrator = OrchestratorAgent(model_manager=manager, vault_engine=vault)
            
            # 올바른 메시지 포맷으로 변환
            messages = [{"role": "user", "content": q}]
            target_model = orchestrator._get_model_for_role("default")
            
            for chunk in orchestrator.run_stream(messages, target_model=target_model):
                if chunk:
                    # Format as SSE
                    payload = json.dumps({"text": chunk})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0.01)  # small yield to event loop
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"SSE Error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/logs")
async def get_logs(lines: int = 100):
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "server_debug.log")
    if not os.path.exists(log_file):
        return {"logs": ["Log file not found."]}
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return {"logs": all_lines[-lines:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {str(e)}"]}

import yaml
@app.get("/api/settings")
async def get_settings():
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config.yaml")
    if not os.path.exists(config_file):
        return {"settings": {}}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        # Mask API keys
        if "api_keys" in cfg:
            for k in cfg["api_keys"]:
                val = cfg["api_keys"][k]
                if val and len(val) > 4:
                    cfg["api_keys"][k] = val[:4] + "*" * (len(val)-4)
        return {"settings": cfg}
    except Exception as e:
        return {"settings": {"error": str(e)}}


# ─── Memory & Toolset & Guardrail APIs ─────────────────────────────────────

from antigravity_k.engine.memory_provider import MemoryManager, BuiltinMemoryProvider
from antigravity_k.engine.toolset_manager import ToolsetManager

_memory_manager: Optional[MemoryManager] = None
_toolset_manager: Optional[ToolsetManager] = None

def _get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
        try:
            sm = _get_session_manager()
            _memory_manager.add_provider(BuiltinMemoryProvider(sm))
        except Exception as e:
            logger.warning(f"BuiltinMemoryProvider 초기화 실패: {e}")
    return _memory_manager

def _get_toolset_manager() -> ToolsetManager:
    global _toolset_manager
    if _toolset_manager is None:
        try:
            config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config.yaml")
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                _toolset_manager = ToolsetManager.from_config(cfg.get("toolsets", {}))
            else:
                _toolset_manager = ToolsetManager()
        except Exception:
            _toolset_manager = ToolsetManager()
    return _toolset_manager


@app.get("/api/memory/stats")
async def get_memory_stats():
    """메모리 시스템 상태를 반환합니다."""
    mm = _get_memory_manager()
    return {"memory": mm.get_stats()}


@app.get("/api/memory/recall")
async def recall_memory(query: str = ""):
    """쿼리 기반 메모리 회상."""
    mm = _get_memory_manager()
    result = mm.prefetch_all(query or "general")
    return {"recalled": result, "query": query}


@app.get("/api/toolsets")
async def list_toolsets():
    """등록된 모든 toolset 목록을 반환합니다."""
    ts = _get_toolset_manager()
    return {"toolsets": ts.list_toolsets(), "active": ts.active_toolset}


@app.post("/api/toolsets/activate")
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


@app.get("/api/toolsets/{name}/tools")
async def get_toolset_tools(name: str):
    """특정 toolset의 해석된 도구 목록을 반환합니다."""
    ts = _get_toolset_manager()
    tools = ts.resolve(name)
    return {"toolset": name, "tools": tools, "count": len(tools)}


@app.get("/api/system/full-status")
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
    global _harness_instance
    if _harness_instance is None:
        from antigravity_k.engine.test_harness import TestHarness
        _harness_instance = TestHarness()
    return _harness_instance

@app.post("/api/harness/self-test")
async def harness_self_test(request: Request):
    """에이전트가 대시보드 전체를 자동 테스트합니다."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    scope = body.get("scope", "api_only")  # 기본: API만 (브라우저 없이 빠르게)
    
    harness = get_harness()
    report = await harness.run_all(use_browser=(scope != "api_only"))
    
    return {"ok": True, "report": report.to_dict()}

@app.get("/api/harness/results")
async def harness_results():
    """최근 테스트 결과를 조회합니다."""
    harness = get_harness()
    report = harness.get_latest_report()
    if report:
        return {"ok": True, "report": report.to_dict()}
    return {"ok": True, "report": None, "message": "아직 테스트가 실행되지 않았습니다."}

@app.get("/api/harness/trend")
async def harness_trend():
    """테스트 추세를 조회합니다."""
    harness = get_harness()
    trend = harness.feedback.get_trend()
    return {"ok": True, "trend": trend}

# ─── Shields & Security APIs (NemoClaw ported) ──────────────────────────────

from antigravity_k.engine.shields import ShieldsManager
from antigravity_k.engine.secret_scanner import scan_for_secrets, redact, strip_credentials
from antigravity_k.engine.runtime_recovery import (
    classify_agent_state, classify_inference_failure,
    determine_recovery, deep_health_check,
)

_shields_manager: Optional[ShieldsManager] = None

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
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                shields_config = cfg.get("shields", {})
            _shields_manager = ShieldsManager.from_config(
                shields_config,
                toolset_manager=_get_toolset_manager(),
            )
        except Exception:
            _shields_manager = ShieldsManager(
                toolset_manager=_get_toolset_manager(),
            )
    return _shields_manager


@app.get("/api/shields/status")
async def get_shields_status():
    """현재 Shields 보호 레벨을 조회합니다."""
    shields = _get_shields_manager()
    return shields.status()


@app.post("/api/shields/down")
async def shields_down(request: Request):
    """Shields를 내립니다 (시간 제한 권한 완화).

    Body:
        reason: 변경 사유 (선택)
        timeout_seconds: 타임아웃 초 (선택, 기본 300)
        target_toolset: 완화 시 toolset (선택, 기본 "full")
    """
    body = await request.json()
    shields = _get_shields_manager()
    state = shields.shields_down(
        reason=body.get("reason"),
        timeout_seconds=body.get("timeout_seconds"),
        target_toolset=body.get("target_toolset", "full"),
    )
    return shields.status()


@app.post("/api/shields/up")
async def shields_up():
    """Shields를 올립니다 (보호 복원)."""
    shields = _get_shields_manager()
    shields.shields_up(restored_by="api_operator")
    return shields.status()


@app.get("/api/shields/audit")
async def get_shields_audit(limit: int = Query(default=50, ge=1, le=500)):
    """Shields 감사 로그를 조회합니다."""
    shields = _get_shields_manager()
    return {"audit_log": shields.get_audit_log(limit=limit)}


@app.post("/api/security/scan")
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


@app.post("/api/security/strip-config")
async def strip_config_credentials(request: Request):
    """설정 딕셔너리에서 민감 필드를 제거합니다.

    Body:
        config: 필터링할 설정 딕셔너리
    """
    body = await request.json()
    config = body.get("config", {})
    return {"sanitized": strip_credentials(config)}


@app.get("/api/health/deep")
async def get_deep_health():
    """전체 시스템 깊은 Health Check를 수행합니다.

    인퍼런스, 메모리, 가드레일, shields 등 모든 컴포넌트를 점검합니다.
    """
    from dataclasses import asdict

    health = deep_health_check(
        model_manager=model_manager,
        session_manager=_session_manager,
        memory_manager=_memory_manager,
        toolset_manager=_toolset_manager,
        shields_manager=_shields_manager,
    )
    return {
        "status": health.status.value,
        "components": [asdict(c) for c in health.components],
        "diagnosis": health.diagnosis,
        "checked_at": health.checked_at,
    }


# --- STATIC FILES FOR DASHBOARD ---
import os
dashboard_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "dashboard", "dist")
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
else:
    logger.warning(f"Dashboard build not found at {dashboard_path}. Please run npm run build in dashboard/")
