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
    # Startup
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
