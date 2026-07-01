"""Server module."""

import asyncio
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from antigravity_k.config import config

logger = logging.getLogger("antigravity_k.api.server")

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan.

    Args:
        app (FastAPI): FastAPI app.

    """
    # Startup — Sidabari 패턴 기반 서브시스템 초기화
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    vault_data_dir = os.path.join(project_root, "vault_data")

    # 1) HookEventBus 초기화 (파일 기반 실시간 이벤트 IPC)
    try:
        from antigravity_k.engine.hook_event_bus import init_hook_event_bus

        init_hook_event_bus(vault_data_dir)
        logger.info("[Startup] HookEventBus initialized")
    except Exception:
        logger.exception("[Startup] HookEventBus init skipped")

    # 2) AuditDb 초기화 (SQLite 감사 로그)
    try:
        from antigravity_k.engine.audit_db import init_audit_db

        init_audit_db(vault_data_dir)
        logger.info("[Startup] AuditDb initialized")
    except Exception:
        logger.exception("[Startup] AuditDb init skipped")

    # 3) PanelActivityTracker 초기화 (에이전트 활동 추적)
    try:
        from antigravity_k.engine.panel_activity_tracker import (
            init_panel_activity_tracker,
        )

        init_panel_activity_tracker()
        logger.info("[Startup] PanelActivityTracker initialized")
    except Exception:
        logger.exception("[Startup] PanelActivityTracker init skipped")

    # 4) EventBus ↔ HookEventBus 듀얼 싱크 브릿지
    try:
        from antigravity_k.engine.event_bus import bridge_to_hook_event_bus

        bridge_to_hook_event_bus()
        logger.info("[Startup] EventBus dual-sync bridge established")
    except Exception:
        logger.exception("[Startup] EventBus bridge skipped")

    # 5) RAG 자동 인덱싱 (기존)
    try:
        from antigravity_k.engine.rag_indexer import RAGIndexer

        async def _bg_index():
            try:
                indexer = RAGIndexer(project_root=project_root)
                count = indexer.index_project()
                logger.info("[RAG] Background indexing complete: %s files indexed", count)
            except Exception:
                logger.exception("[RAG] Background indexing failed")

        task = asyncio.create_task(_bg_index())
        if not hasattr(app.state, "background_tasks"):
            app.state.background_tasks = set()
        app.state.background_tasks.add(task)
        task.add_done_callback(app.state.background_tasks.discard)
        logger.info("[RAG] Background indexing started")
    except Exception:
        logger.exception("[RAG] Auto-index startup skipped")

    # 6) IDE Server (code-server Web IDE)
    try:
        from antigravity_k.engine.ide_server import IDEServer

        ide_server = IDEServer(port=8080, workspace_dir=project_root)
        ide_server.start()
        app.state.ide_server = ide_server
        logger.info("[Startup] IDE Server initialized on port 8080")
    except Exception:
        logger.exception("[Startup] IDE Server init skipped")

    yield
    # Shutdown
    logger.info("Server shutting down — cancelling application background tasks...")
    tasks = [task for task in getattr(app.state, "background_tasks", set()) if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Sidabari 서브시스템 정리
    try:
        from antigravity_k.engine.hook_event_bus import get_hook_event_bus

        get_hook_event_bus().shutdown()
    except Exception:
        logger.exception("Unhandled exception")
        pass

    try:
        from antigravity_k.engine.audit_db import get_audit_db

        get_audit_db().close()
    except Exception:
        logger.exception("Unhandled exception")
        pass

    try:
        if hasattr(app.state, "ide_server"):
            app.state.ide_server.stop()
    except Exception:
        logger.exception("Unhandled exception")
        pass

    logger.info("Shutdown complete: %s tasks cancelled.", len(tasks))


app = FastAPI(
    title="Antigravity-K API",
    description="OpenAI-compatible API for Antigravity-K Local Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def verify_access_pin(request: Request, call_next):
    """API 접근 시 설정된 보안 PIN을 검증하세요.

    Header(X-Access-Pin) 또는 Cookie(ag_access_pin)를 통해 검사합니다.
    """
    if request.url.path.startswith("/api/"):
        required_pin = config.security.access_pin
        if required_pin:
            pin_from_header = request.headers.get("X-Access-Pin")
            pin_from_cookie = request.cookies.get("ag_access_pin")

            if pin_from_header != required_pin and pin_from_cookie != required_pin:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing Access PIN", "ok": False},
                )
    return await call_next(request)


from antigravity_k.api.routes import api_router

app.include_router(api_router)

import httpx
from fastapi.responses import StreamingResponse


@app.api_route(
    "/ide/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def reverse_proxy_ide(request: Request, path: str):
    """code-server (Web IDE)에 대한 리버스 프록시.

    주의: 완벽한 VS Code 구동을 위해서는 WebSocket 프록싱이 필요하며,
    현 구현은 기초적인 HTTP 프록싱만 제공합니다. 실사용 시 Nginx 등을 권장합니다.
    """
    ide_host = "http://127.0.0.1:8080"
    url = f"{ide_host}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    # httpx를 이용해 트래픽 포워딩
    async with httpx.AsyncClient() as client:
        # 헤더 조작 시 Host 헤더 등이 충돌할 수 있으므로 필터링 필요
        req_headers = dict(request.headers)
        req_headers.pop("host", None)

        rp_req = client.build_request(
            request.method,
            url,
            headers=req_headers,
            content=await request.body(),
        )
        try:
            rp_resp = await client.send(rp_req, stream=True)
            return StreamingResponse(
                rp_resp.aiter_raw(),
                status_code=rp_resp.status_code,
                headers=dict(rp_resp.headers),
            )
        except httpx.RequestError as exc:
            return JSONResponse(
                status_code=502,
                content={"detail": "IDE Server Proxy Error", "error": str(exc)},
            )


# --- STATIC FILES FOR DASHBOARD ---
dashboard_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "dashboard",
    "dist",
)
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
else:
    logger.warning(
        "Dashboard build not found at %s. Please run npm run build in dashboard/",
        dashboard_path,
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "antigravity_k.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src", "config.yaml"],
    )
