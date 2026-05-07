import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
from antigravity_k.config import config
import asyncio

logger = logging.getLogger("antigravity_k.api.server")

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — Sidabari 패턴 기반 서브시스템 초기화
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    vault_data_dir = os.path.join(project_root, "vault_data")

    # 1) HookEventBus 초기화 (파일 기반 실시간 이벤트 IPC)
    try:
        from antigravity_k.engine.hook_event_bus import init_hook_event_bus

        init_hook_event_bus(vault_data_dir)
        logger.info("[Startup] HookEventBus initialized")
    except Exception as e:
        logger.warning(f"[Startup] HookEventBus init skipped: {e}")

    # 2) AuditDb 초기화 (SQLite 감사 로그)
    try:
        from antigravity_k.engine.audit_db import init_audit_db

        init_audit_db(vault_data_dir)
        logger.info("[Startup] AuditDb initialized")
    except Exception as e:
        logger.warning(f"[Startup] AuditDb init skipped: {e}")

    # 3) PanelActivityTracker 초기화 (에이전트 활동 추적)
    try:
        from antigravity_k.engine.panel_activity_tracker import (
            init_panel_activity_tracker,
        )

        init_panel_activity_tracker()
        logger.info("[Startup] PanelActivityTracker initialized")
    except Exception as e:
        logger.warning(f"[Startup] PanelActivityTracker init skipped: {e}")

    # 4) EventBus ↔ HookEventBus 듀얼 싱크 브릿지
    try:
        from antigravity_k.engine.event_bus import bridge_to_hook_event_bus

        bridge_to_hook_event_bus()
        logger.info("[Startup] EventBus dual-sync bridge established")
    except Exception as e:
        logger.warning(f"[Startup] EventBus bridge skipped: {e}")

    # 5) RAG 자동 인덱싱 (기존)
    try:
        from antigravity_k.engine.rag_indexer import RAGIndexer

        async def _bg_index():
            try:
                indexer = RAGIndexer(project_root=project_root)
                count = indexer.build_index()
                logger.info(
                    f"[RAG] Background indexing complete: {count} files indexed"
                )
            except Exception as e:
                logger.warning(f"[RAG] Background indexing failed: {e}")

        task = asyncio.create_task(_bg_index())
        if not hasattr(app.state, "background_tasks"):
            app.state.background_tasks = set()
        app.state.background_tasks.add(task)
        task.add_done_callback(app.state.background_tasks.discard)
        logger.info("[RAG] Background indexing started")
    except Exception as e:
        logger.warning(f"[RAG] Auto-index startup skipped: {e}")

    yield
    # Shutdown
    logger.info("Server shutting down — cancelling application background tasks...")
    tasks = [
        task
        for task in getattr(app.state, "background_tasks", set())
        if not task.done()
    ]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Sidabari 서브시스템 정리
    try:
        from antigravity_k.engine.hook_event_bus import get_hook_event_bus
        get_hook_event_bus().shutdown()
    except Exception:
        pass

    try:
        from antigravity_k.engine.audit_db import get_audit_db
        get_audit_db().close()
    except Exception:
        pass

    logger.info(f"Shutdown complete: {len(tasks)} tasks cancelled.")


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
    """
    API 접근 시 설정된 보안 PIN을 검증합니다.
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
        f"Dashboard build not found at {dashboard_path}. Please run npm run build in dashboard/"
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
