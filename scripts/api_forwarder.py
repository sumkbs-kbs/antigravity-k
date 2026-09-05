#!/usr/bin/env python3
"""Ssak-Ai: OpenAI 호환 API 통합 포워더 (Unified Proxy)
===========================================================
모든 로컬 추론 엔진(mlx-lm, Ollama, vLLM, LM Studio)을
단일 엔드포인트 http://localhost:1234/v1 로 통합합니다.

사용법:
    python scripts/api_forwarder.py
    python scripts/api_forwarder.py --port 1234 --default-backend ollama

기능:
    - 모델 이름 기반 자동 라우팅
    - 백엔드 헬스체크 & 자동 페일오버
    - 요청/응답 로깅 (감사 추적용)
    - 스트리밍 지원 (SSE)
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypeAlias, cast

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonMap: TypeAlias = dict[str, JsonValue]


class KanbanBoardProtocol(Protocol):
    def get_board_state(self) -> JsonValue: ...

    def create_task(self, description: str, assignee: str | None = None) -> str: ...

    def move_task(self, task_id: str, status: str) -> object: ...


class SearchResultProtocol(Protocol):
    title: str
    snippet: str
    url: str
    source: str


class SearchResponseProtocol(Protocol):
    query: str
    engine: str
    cached: bool
    search_time_ms: float
    total_results: int
    results: Sequence[SearchResultProtocol]


class WebSearchEngineProtocol(Protocol):
    async def search(self, query: str) -> SearchResponseProtocol: ...

    def format_for_llm(self, response: SearchResponseProtocol) -> str: ...


class WikiEntryProtocol(Protocol):
    id: int
    title: str
    content: str
    category: str
    tags: list[str]
    source: str
    source_url: str | None
    created_at: str
    updated_at: str
    access_count: int


class WikiHitProtocol(Protocol):
    entry: WikiEntryProtocol
    score: float


class WikiProtocol(Protocol):
    def search_for_llm(self, query: str, limit: int = 3) -> str: ...

    def search(self, query: str, category: str | None = None, limit: int = 10) -> Sequence[WikiHitProtocol]: ...

    def save_web_search(self, query: str, results: list[JsonMap]) -> object: ...

    def add_entry(self, **kwargs: str | list[str]) -> int: ...

    def get_entry(self, entry_id: int) -> WikiEntryProtocol | None: ...

    def delete_entry(self, entry_id: int) -> bool: ...

    def get_stats(self) -> JsonMap: ...

    def import_obsidian_vault(self, vault_path: str) -> int: ...


# ─── 프로젝트 모듈 임포트 ────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
KanbanBoardFactory: type[KanbanBoardProtocol] | None = None
WikiFactory: type[WikiProtocol] | None = None
WebSearchEngineFactory: type[WebSearchEngineProtocol] | None = None
try:
    from antigravity_k.agents.kanban import KanbanBoard as imported_kanban_board
    from antigravity_k.knowledge.wiki import LLMWiki as imported_wiki
    from antigravity_k.tools.web_search import WebSearchEngine as imported_search_engine

    has_tools = True
except ImportError:
    has_tools = False
else:
    KanbanBoardFactory = cast(type[KanbanBoardProtocol], imported_kanban_board)
    WikiFactory = cast(type[WikiProtocol], imported_wiki)
    WebSearchEngineFactory = cast(type[WebSearchEngineProtocol], imported_search_engine)

# ─── 로깅 설정 ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("api_forwarder")


def _json_map(value: object) -> JsonMap:
    if not isinstance(value, dict):
        return {}
    mapping = cast(dict[object, object], value)
    return {str(key): cast(JsonValue, item) for key, item in mapping.items()}


# ─── 백엔드 정의 ─────────────────────────────────────────────────────────────


@dataclass
class Backend:
    """추론 백엔드 서버 정보."""

    name: str
    base_url: str
    priority: int = 0  # 낮을수록 우선
    healthy: bool = False
    last_check: float = 0.0
    models: list[str] = field(default_factory=list)


# 사전 정의된 백엔드 목록
BACKENDS: dict[str, Backend] = {
    "mlx-lm": Backend(
        name="mlx-lm",
        base_url="http://localhost:8401",
        priority=1,
    ),
    "ollama": Backend(
        name="ollama",
        base_url="http://localhost:11434",
        priority=2,
    ),
    "vllm": Backend(
        name="vllm",
        base_url="http://localhost:8000",
        priority=3,
    ),
    "lm-studio": Backend(
        name="lm-studio",
        base_url="http://localhost:1234",
        priority=4,
    ),
}

# 모델 → 백엔드 라우팅 규칙
MODEL_ROUTES: dict[str, str] = {
    # MLX 모델 (mlx-community 프리픽스)
    "mlx-community/": "mlx-lm",
    # Ollama 모델 (짧은 이름)
    "qwen2.5": "ollama",
    "deepseek": "ollama",
    "llama": "ollama",
    "codellama": "ollama",
    "nomic": "ollama",
    # vLLM 모델
    "vllm/": "vllm",
}

# 시스템 프롬프트 (Reasoning Traces)
_system_prompt: str = ""
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md"


def load_system_prompt() -> None:
    """시스템 프롬프트 파일을 로드합니다."""
    global _system_prompt
    if SYSTEM_PROMPT_PATH.exists():
        _system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        logger.info(f"시스템 프롬프트 로드 완료: {len(_system_prompt)}자")
    else:
        logger.warning(f"시스템 프롬프트 파일 없음: {SYSTEM_PROMPT_PATH}")


def scan_finetuned_models() -> None:
    """models/finetuned/ 디렉토리에서 파인튜닝 모델을 자동 감지합니다."""
    ft_dir = Path(__file__).resolve().parent.parent / "models" / "finetuned"
    if not ft_dir.exists():
        return

    for meta_file in ft_dir.glob("*/agk_model_meta.json"):
        try:
            meta = _json_map(cast(object, json.loads(meta_file.read_text(encoding="utf-8"))))
            model_name = str(meta.get("name", meta_file.parent.name))
            # 라우팅 규칙에 추가
            MODEL_ROUTES[f"finetuned/{model_name}"] = "mlx-lm"
            logger.info(f"파인튜닝 모델 등록: finetuned/{model_name}")
        except Exception as e:
            logger.warning(f"파인튜닝 모델 로드 실패: {meta_file} — {e}")


app = FastAPI(
    title="Ssak-Ai API Forwarder",
    description="로컬 추론 엔진 통합 프록시",
    version="0.1.0",
)


_forwarder_auth_required = True
_forwarder_pin_hash: str | None = None
_FORWARDER_PUBLIC_PATHS = frozenset({"/", "/v1/health", "/docs", "/openapi.json"})


def validate_forwarder_startup(host: str) -> None:
    global _forwarder_auth_required, _forwarder_pin_hash
    from antigravity_k.api.startup_security import validate_startup_security
    from antigravity_k.engine.auth import hash_pin

    environment = os.environ.get("AGK_ENV", "development")
    pin_hash_file = Path(os.environ.get("AGK_SEC_PIN_HASH_FILE", "data/auth_hash"))
    validate_startup_security(
        host=host,
        environment=environment,
        access_pin=os.environ.get("AGK_SEC_ACCESS_PIN", ""),
        pin_hash_file=pin_hash_file,
    )
    _forwarder_auth_required = environment.strip().lower() == "production" or host.strip().lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if _forwarder_auth_required:
        try:
            _forwarder_pin_hash = pin_hash_file.read_text(encoding="utf-8").strip() or None
        except OSError:
            _forwarder_pin_hash = None
        if _forwarder_pin_hash is None:
            access_pin = os.environ.get("AGK_SEC_ACCESS_PIN", "").strip()
            if access_pin:
                _forwarder_pin_hash = hash_pin(access_pin)
                try:
                    pin_hash_file.parent.mkdir(parents=True, exist_ok=True)
                    pin_hash_file.write_text(_forwarder_pin_hash, encoding="utf-8")
                    pin_hash_file.chmod(0o600)
                except OSError:
                    pass
    else:
        _forwarder_pin_hash = None


def _forwarder_request_authenticated(request: Request) -> bool:
    if not _forwarder_auth_required:
        return True
    pin = request.headers.get("X-Access-Pin") or request.cookies.get("ag_access_pin")
    if not pin or not _forwarder_pin_hash:
        return False
    from antigravity_k.engine.auth import verify_pin

    return verify_pin(pin, _forwarder_pin_hash)


def _forwarder_pin_authenticated(pin: str | None) -> bool:
    if not _forwarder_auth_required:
        return True
    if not pin or not _forwarder_pin_hash:
        return False
    from antigravity_k.engine.auth import verify_pin

    return verify_pin(pin, _forwarder_pin_hash)


@app.middleware("http")
async def verify_forwarder_access(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in _FORWARDER_PUBLIC_PATHS:
        return await call_next(request)
    if not _forwarder_request_authenticated(request):
        return JSONResponse(status_code=401, content={"ok": False, "detail": "Invalid or missing credentials"})
    return await call_next(request)


# HTTP 클라이언트 (커넥션 풀)
http_client: httpx.AsyncClient | None = None

# 요청 카운터 (감사용)
request_counter = 0

# ─── 로그 디렉토리 ───────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ─── 헬스 체크 ───────────────────────────────────────────────────────────────
async def check_backend_health(backend: Backend) -> bool:
    """백엔드 서버의 상태를 확인합니다."""
    try:
        assert http_client is not None
        # /v1/models 엔드포인트로 헬스 체크
        resp = await http_client.get(
            f"{backend.base_url}/v1/models",
            timeout=3.0,
        )
        if resp.status_code == 200:
            data = _json_map(cast(object, resp.json()))
            # 사용 가능한 모델 목록 업데이트
            if "data" in data:
                backend.models = [cast(str, _json_map(m).get("id", "")) for m in cast(list[object], data["data"])]
            backend.healthy = True
        else:
            backend.healthy = False
    except Exception:
        backend.healthy = False

    backend.last_check = time.time()
    return backend.healthy


async def refresh_all_backends():
    """모든 백엔드의 상태를 갱신합니다."""
    tasks = [check_backend_health(b) for b in BACKENDS.values()]
    _ = await asyncio.gather(*tasks, return_exceptions=True)

    healthy = [b.name for b in BACKENDS.values() if b.healthy]
    logger.info(f"활성 백엔드: {healthy if healthy else '없음'}")


# ─── 라우팅 로직 ─────────────────────────────────────────────────────────────
def resolve_backend(model: str) -> Backend | None:
    """모델 이름에 따라 적절한 백엔드를 선택합니다."""
    # 1. 명시적 라우팅 규칙 확인
    for prefix, backend_name in MODEL_ROUTES.items():
        if prefix in model.lower():
            backend = BACKENDS.get(backend_name)
            if backend and backend.healthy:
                return backend

    # 2. 각 백엔드의 모델 목록에서 검색
    for backend in sorted(BACKENDS.values(), key=lambda b: b.priority):
        if backend.healthy:
            for available_model in backend.models:
                if model.lower() in available_model.lower():
                    return backend

    # 3. 우선순위 순서로 첫 번째 활성 백엔드 반환
    for backend in sorted(BACKENDS.values(), key=lambda b: b.priority):
        if backend.healthy:
            return backend

    return None


# ─── 요청 로깅 ───────────────────────────────────────────────────────────────
def log_request(method: str, path: str, model: str, backend_name: str):
    """요청을 감사 로그에 기록합니다."""
    global request_counter
    request_counter += 1

    log_entry = {
        "id": request_counter,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": method,
        "path": path,
        "model": model,
        "backend": backend_name,
    }

    # 로그 파일에 추가
    log_file = LOG_DIR / "api_requests.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        _ = f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ─── API 엔드포인트 ──────────────────────────────────────────────────────────

# Kanban 상태 및 WebSocket 관련 전역 변수
kanban_board: KanbanBoardProtocol | None = None
active_websockets: list[WebSocket] = []


async def kanban_broadcaster():
    """배경에서 Kanban 보드 상태를 주기적으로 확인하고 변경사항이 있으면 웹소켓으로 브로드캐스트합니다."""
    if not kanban_board:
        return

    last_state_str = ""
    while True:
        try:
            # 보드 상태 쿼리
            board_state = kanban_board.get_board_state()
            current_state_str = json.dumps(board_state, sort_keys=True)

            # 상태 변경 시 모든 연결된 클라이언트에게 전송
            if current_state_str != last_state_str and active_websockets:
                last_state_str = current_state_str
                disconnected: list[WebSocket] = []
                for ws in active_websockets:
                    try:
                        await ws.send_json(board_state)
                    except Exception:
                        disconnected.append(ws)

                # 끊긴 웹소켓 정리
                for ws in disconnected:
                    if ws in active_websockets:
                        active_websockets.remove(ws)
        except Exception as e:
            logger.error(f"Kanban broadcaster error: {e}")

        await asyncio.sleep(1.0)  # 1초마다 폴링 (SQLite WAL 모드이므로 부하 적음)


async def startup():
    """앱 시작 시 HTTP 클라이언트 생성, 시스템 프롬프트 로드, 백엔드 체크."""
    global http_client, kanban_board
    http_client = httpx.AsyncClient(timeout=120.0)
    load_system_prompt()
    scan_finetuned_models()

    # Kanban 보드 초기화 및 브로드캐스터 시작
    if has_tools and KanbanBoardFactory is not None:
        kanban_board = KanbanBoardFactory()
        _ = asyncio.create_task(kanban_broadcaster())
        logger.info("Kanban 보드 및 웹소켓 브로드캐스터 시작됨")

    await refresh_all_backends()
    logger.info("API Forwarder 시작됨 — http://localhost:1234/v1")


async def shutdown():
    """앱 종료 시 HTTP 클라이언트 정리."""
    global http_client
    if http_client:
        await http_client.aclose()


@app.get("/v1/models")
async def list_models():
    """모든 활성 백엔드의 모델을 통합 반환합니다."""
    await refresh_all_backends()

    all_models: list[JsonMap] = []
    seen: set[str] = set()

    for backend in sorted(BACKENDS.values(), key=lambda b: b.priority):
        if backend.healthy:
            for model_id in backend.models:
                if model_id not in seen:
                    seen.add(model_id)
                    all_models.append(
                        {
                            "id": model_id,
                            "object": "model",
                            "owned_by": backend.name,
                        }
                    )

    return {"object": "list", "data": all_models}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Chat Completions 요청을 적절한 백엔드로 포워딩합니다."""
    body = _json_map(cast(object, await request.json()))
    model = cast(str, body.get("model", ""))
    stream = cast(bool, body.get("stream", False))
    agent_mode = cast(bool, body.get("agent_mode", False))

    # ── Reasoning Traces: 시스템 프롬프트 자동 주입 ──────────────
    if _system_prompt and "messages" in body:
        messages = cast(list[JsonMap], body["messages"])
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            # Agent Mode 여부에 따라 사용 가능한 도구 설명 주입
            system_ext = ""
            if agent_mode:
                system_ext = """\n\n추가로, 당신은 다음 도구들을 사용할 수 있습니다:
- <tool_call>{"name": "web_search", "arguments": {"query": "검색어"}}</tool_call>
- <tool_call>{"name": "wiki_search", "arguments": {"query": "검색어"}}</tool_call>
필요하다면 위 형식에 맞춰 <tool_call> 태그를 출력하세요. 실행 결과는 <tool_response> 로 전달됩니다."""
            body["messages"] = [
                {"role": "system", "content": _system_prompt + system_ext},
                *messages,
            ]
            logger.info("[Reasoning] 시스템 프롬프트 자동 주입 완료")

    # 백엔드 선택
    backend = resolve_backend(model)
    if not backend:
        await refresh_all_backends()
        backend = resolve_backend(model)

    if not backend:
        raise HTTPException(
            status_code=503,
            detail="사용 가능한 추론 백엔드가 없습니다. Ollama, mlx_lm.server, 또는 LM Studio를 시작해 주세요.",
        )

    log_request("POST", "/v1/chat/completions", model, backend.name)
    target_url = f"{backend.base_url}/v1/chat/completions"

    logger.info(f"[#{request_counter}] {model} → {backend.name} ({target_url})")

    assert http_client is not None
    client = http_client

    if stream:
        if agent_mode and agent_executor:
            # Agent Loop Stream (QueryEngine Pattern)
            return StreamingResponse(
                agent_executor.run_agent_stream(client, target_url, body),
                media_type="text/event-stream",
            )
        else:
            # 일반 스트리밍 응답 포워딩
            async def stream_response():
                async with client.stream(
                    "POST", target_url, json=body, headers={"Content-Type": "application/json"}
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
            )
    else:
        # 일반 응답 포워딩
        try:
            resp = await http_client.post(
                target_url,
                json=body,
                headers={"Content-Type": "application/json"},
            )
            return JSONResponse(
                content=resp.json(),
                status_code=resp.status_code,
            )
        except httpx.ConnectError:
            backend.healthy = False
            raise HTTPException(
                status_code=503,
                detail=f"백엔드 '{backend.name}' 연결 실패. 서버가 실행 중인지 확인해 주세요.",
            )


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    """임베딩 요청 포워딩."""
    body = _json_map(cast(object, await request.json()))
    model = cast(str, body.get("model", ""))

    backend = resolve_backend(model)
    if not backend:
        raise HTTPException(status_code=503, detail="임베딩 백엔드 없음")

    log_request("POST", "/v1/embeddings", model, backend.name)
    target_url = f"{backend.base_url}/v1/embeddings"

    assert http_client is not None
    resp = await http_client.post(target_url, json=body)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/v1/health")
async def health_check():
    """전체 시스템 헬스 체크."""
    await refresh_all_backends()
    status = {}
    for name, backend in BACKENDS.items():
        status[name] = {
            "healthy": backend.healthy,
            "url": backend.base_url,
            "models": backend.models[:5],  # 최대 5개만
        }

    any_healthy = any(b.healthy for b in BACKENDS.values())
    return JSONResponse(
        content={"status": "ok" if any_healthy else "no_backends", "backends": status},
        status_code=200 if any_healthy else 503,
    )


@app.get("/")
async def root():
    """루트 경로 — 사용법 안내."""
    return {
        "service": "Ssak-Ai API Forwarder",
        "version": "0.2.0",
        "endpoints": {
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "embeddings": "/v1/embeddings",
            "health": "/v1/health",
            "search": "/api/search",
            "wiki": "/api/wiki",
            "wiki_stats": "/api/wiki/stats",
            "kanban_api": "/api/kanban",
            "kanban_ws": "/ws/kanban",
        },
        "docs": "/docs",
    }


# ─── Kanban API & WebSocket ──────────────────────────────────────────────────


@app.get("/api/kanban")
async def get_kanban_state():
    """현재 Kanban 보드 상태를 반환합니다."""
    if not kanban_board:
        raise HTTPException(status_code=503, detail="KanbanBoard가 초기화되지 않았습니다.")
    return kanban_board.get_board_state()


class TaskCreateRequest(BaseModel):
    description: str
    assignee: str | None = None


@app.post("/api/kanban/tasks")
async def create_kanban_task(req: TaskCreateRequest):
    """새로운 칸반 태스크를 생성합니다."""
    if not kanban_board:
        raise HTTPException(status_code=503, detail="KanbanBoard가 초기화되지 않았습니다.")
    task_id = kanban_board.create_task(req.description, req.assignee)
    return {"id": task_id, "status": "success"}


class TaskMoveRequest(BaseModel):
    status: str


@app.put("/api/kanban/tasks/{task_id}/status")
async def move_kanban_task(task_id: str, req: TaskMoveRequest):
    """태스크의 상태를 변경합니다."""
    if not kanban_board:
        raise HTTPException(status_code=503, detail="KanbanBoard가 초기화되지 않았습니다.")
    try:
        _ = kanban_board.move_task(task_id, req.status)
        return {"id": task_id, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.websocket("/ws/kanban")
async def websocket_kanban(websocket: WebSocket):
    """Kanban 보드 실시간 업데이트를 위한 WebSocket 엔드포인트"""
    if not _forwarder_pin_authenticated(websocket.headers.get("X-Access-Pin")):
        await websocket.close(code=4401, reason="Unauthorized")
        return
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info(f"Kanban 웹소켓 클라이언트 연결됨. 현재 접속: {len(active_websockets)}명")

    try:
        # 최초 연결 시 현재 상태 1회 전송
        if kanban_board:
            await websocket.send_json(kanban_board.get_board_state())

        # 클라이언트 연결 유지용 무한 루프
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Kanban 웹소켓 클라이언트 연결 종료")
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# ─── 웹 검색 및 에이전트 도구 API ────────────────────────────────────────────────

search_engine: WebSearchEngineProtocol | None = None
wiki: WikiProtocol | None = None


class AgentExecutor:
    """Hermes Agent Reasoning Traces 형식의 도구 호출을 처리하는 실행기"""

    def __init__(self, search_engine: WebSearchEngineProtocol | None, wiki: WikiProtocol | None) -> None:
        self.search_engine: WebSearchEngineProtocol | None = search_engine
        self.wiki: WikiProtocol | None = wiki

    async def execute_tool(self, tool_name: str, arguments: JsonMap) -> str:
        logger.info(f"[AgentExecutor] 도구 실행: {tool_name}({arguments})")
        try:
            # 외부 MCP 서버 라우팅 훅
            if tool_name.startswith("mcp_"):
                logger.info(f"[MCP] 외부 도구 호출 위임: {tool_name}")
                # TODO: 추후 mcp-python-sdk 등을 활용해 실제 서버로 JSON-RPC 요청 전달
                return f"MCP Error: 외부 MCP 서버 연동이 구성되지 않았습니다. (요청: {tool_name})"

            if tool_name == "web_search":
                query = str(arguments.get("query", ""))
                if self.search_engine:
                    res = await self.search_engine.search(query)
                    return self.search_engine.format_for_llm(res)
                return "Error: 웹 검색 엔진이 활성화되지 않았습니다."
            elif tool_name == "wiki_search":
                query = str(arguments.get("query", ""))
                if self.wiki:
                    hits = self.wiki.search_for_llm(query, limit=3)
                    return hits if hits else "관련 문서가 없습니다."
                return "Error: LLM Wiki가 활성화되지 않았습니다."
            else:
                return f"Error: 알 수 없는 도구 '{tool_name}'"
        except Exception as e:
            return f"Error: 도구 실행 중 오류 발생 - {e}"

    async def run_agent_stream(self, client: httpx.AsyncClient, target_url: str, body: JsonMap) -> AsyncIterator[str]:
        """Tool execution loop 처리. 클라이언트에는 SSE 형식으로 스트리밍"""
        import re

        max_loops = 5

        for loop in range(max_loops):
            full_content = ""

            async with client.stream(
                "POST", target_url, json=body, headers={"Content-Type": "application/json"}
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue

                    yield line + "\n"

                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = _json_map(cast(object, json.loads(data_str)))
                            choices = data.get("choices", [])
                            first_choice = cast(JsonMap, choices[0]) if isinstance(choices, list) and choices else {}
                            delta = _json_map(first_choice.get("delta", {}))
                            content = str(delta.get("content", ""))
                            if content:
                                full_content += content
                        except Exception:
                            pass

            # 스트림 완료 후 <tool_call> 확인
            tool_call_matches = re.finditer(r"<tool_call>(.*?)</tool_call>", full_content, re.DOTALL)
            calls = list(tool_call_matches)

            if not calls:
                break

            messages = body.get("messages")
            if not isinstance(messages, list):
                messages = []
                body["messages"] = messages
            typed_messages: list[JsonValue] = messages
            typed_messages.append({"role": "assistant", "content": full_content})

            tool_responses: list[str] = []
            for match in calls:
                try:
                    tool_data = _json_map(cast(object, json.loads(match.group(1))))
                    t_name = str(tool_data.get("name", ""))
                    t_args = _json_map(tool_data.get("arguments", {}))

                    logger.info(f"[{loop}] 도구 실행 감지: {t_name}")

                    # 실행 알림 스트림 전송
                    msg = f"\n\n> 🛠️ 도구 실행 중: {t_name}...\n\n"
                    chunk = json.dumps(
                        {
                            "id": "tool",
                            "object": "chat.completion.chunk",
                            "choices": [{"index": 0, "delta": {"content": msg}}],
                        }
                    )
                    yield f"data: {chunk}\n\n"

                    res = await self.execute_tool(t_name, t_args)
                    tool_responses.append(f"<tool_response>\n{res}\n</tool_response>")
                except Exception as e:
                    tool_responses.append(f"<tool_response>\nError: {e}\n</tool_response>")

            typed_messages.append({"role": "user", "content": "\n".join(tool_responses)})


agent_executor: AgentExecutor | None = None


async def init_tools():
    """웹 검색 엔진, Wiki 및 AgentExecutor를 초기화합니다."""
    global search_engine, wiki, agent_executor
    if has_tools and WebSearchEngineFactory is not None and WikiFactory is not None:
        search_engine = WebSearchEngineFactory()
        wiki = WikiFactory()
        agent_executor = AgentExecutor(search_engine, wiki)
        logger.info("웹 검색 엔진 + LLM Wiki + AgentExecutor 초기화 완료")
    else:
        logger.warning("tools/knowledge 모듈 없음 — 검색/Wiki/Agent 비활성화")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await startup()
    await init_tools()
    try:
        yield
    finally:
        await shutdown()


app.router.lifespan_context = lifespan


class SearchRequest(BaseModel):
    query: str
    max_results: int = 8
    save_to_wiki: bool = False


@app.post("/api/search")
async def web_search(req: SearchRequest):
    """웹 검색을 실행합니다."""
    if not search_engine:
        raise HTTPException(status_code=503, detail="웹 검색 엔진 미초기화")

    response = await search_engine.search(req.query)

    # Wiki에 자동 저장
    if req.save_to_wiki and wiki and response.results:
        _ = wiki.save_web_search(
            req.query,
            [{"title": r.title, "snippet": r.snippet, "url": r.url} for r in response.results],
        )

    return {
        "query": response.query,
        "engine": response.engine,
        "cached": response.cached,
        "search_time_ms": response.search_time_ms,
        "total": response.total_results,
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet, "source": r.source} for r in response.results
        ],
    }


# ─── Wiki API ────────────────────────────────────────────────────────────────


class WikiAddRequest(BaseModel):
    title: str
    content: str
    category: str = "general"
    tags: list[str] = []
    source: str = "manual"


@app.post("/api/wiki")
async def wiki_add(req: WikiAddRequest):
    """위키에 항목을 추가합니다."""
    if not wiki:
        raise HTTPException(status_code=503, detail="Wiki 미초기화")

    entry_id = wiki.add_entry(
        title=req.title,
        content=req.content,
        category=req.category,
        tags=req.tags,
        source=req.source,
    )
    return {"id": entry_id, "message": f"'{req.title}' 항목이 추가되었습니다."}


@app.get("/api/wiki/search")
async def wiki_search(q: str, category: str | None = None, limit: int = 10):
    """위키를 검색합니다."""
    if not wiki:
        raise HTTPException(status_code=503, detail="Wiki 미초기화")

    hits = wiki.search(q, category=category, limit=limit)
    return {
        "query": q,
        "total": len(hits),
        "results": [
            {
                "id": h.entry.id,
                "title": h.entry.title,
                "content": h.entry.content[:300],
                "category": h.entry.category,
                "tags": h.entry.tags,
                "score": round(h.score, 3),
                "source": h.entry.source,
                "updated_at": h.entry.updated_at,
            }
            for h in hits
        ],
    }


@app.get("/api/wiki/{entry_id}")
async def wiki_get(entry_id: int):
    """위키 항목을 조회합니다."""
    if not wiki:
        raise HTTPException(status_code=503, detail="Wiki 미초기화")

    entry = wiki.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="항목 없음")

    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "category": entry.category,
        "tags": entry.tags,
        "source": entry.source,
        "source_url": entry.source_url,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
        "access_count": entry.access_count,
    }


@app.delete("/api/wiki/{entry_id}")
async def wiki_delete(entry_id: int):
    """위키 항목을 삭제합니다."""
    if not wiki:
        raise HTTPException(status_code=503, detail="Wiki 미초기화")

    ok = wiki.delete_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="항목 없음")
    return {"deleted": entry_id}


@app.get("/api/wiki/stats")
async def wiki_stats():
    """위키 통계를 반환합니다."""
    if not wiki:
        return {"total_entries": 0, "status": "미초기화"}
    return wiki.get_stats()


class ObsidianImportRequest(BaseModel):
    vault_path: str


@app.post("/api/wiki/import-obsidian")
async def wiki_import_obsidian(req: ObsidianImportRequest):
    """Obsidian 볼트를 위키에 임포트합니다."""
    if not wiki:
        raise HTTPException(status_code=503, detail="Wiki 미초기화")

    count = wiki.import_obsidian_vault(req.vault_path)
    return {"imported": count, "vault": req.vault_path}


# ─── CLI 엔트리포인트 ────────────────────────────────────────────────────────
def main():
    """CLI에서 직접 실행."""
    import argparse

    parser = argparse.ArgumentParser(description="Ssak-Ai API Forwarder")
    _ = parser.add_argument("--host", default="127.0.0.1", help="바인딩 호스트")
    _ = parser.add_argument("--port", type=int, default=1234, help="포트 (기본: 1234)")
    _ = parser.add_argument(
        "--default-backend",
        choices=list(BACKENDS.keys()),
        default=None,
        help="기본 백엔드",
    )
    args = parser.parse_args()

    # 기본 백엔드 우선순위 조정
    default_backend = cast(str | None, args.default_backend)
    host = cast(str, args.host)
    port = cast(int, args.port)
    validate_forwarder_startup(host)
    if default_backend and default_backend in BACKENDS:
        BACKENDS[default_backend].priority = 0
        logger.info(f"기본 백엔드: {default_backend}")

    logger.info(f"API Forwarder 시작: http://{host}:{port}/v1")
    logger.info("Swagger UI: http://{args.host}:{args.port}/docs")

    _ = uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
