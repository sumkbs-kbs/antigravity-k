import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from fastapi.staticfiles import StaticFiles
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
)

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
