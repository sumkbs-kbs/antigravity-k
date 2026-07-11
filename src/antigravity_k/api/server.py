"""FastAPI application factory, middleware, and lifespan for the Antigravity-K API."""

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()  # .env 로드 — config import 전에 실행되어야 함

from antigravity_k.config import config

logger = logging.getLogger("antigravity_k.api.server")

from contextlib import asynccontextmanager

# ---------------------------------------------------------------------------
# Rate limiter (slowapi) — single shared Limiter instance.
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan.

    Args:
        app (FastAPI): FastAPI app.

    """
    # Startup — Sidabari 패턴 기반 서브시스템 초기화
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    vault_data_dir = os.path.join(project_root, "vault_data")

    # 0) 시작 시 config 검증 (fail-fast, 작업 D) — 잘못된 설정을 런타임 전에 발견
    try:
        problems = config.validate()
        if problems:
            logger.warning("[Startup] 설정 검증 %d개 문제 — 계속 시작하지만 확인 필요:", len(problems))
            for p in problems:
                logger.warning("  ⚠️  %s", p)
    except Exception:
        logger.exception("[Startup] config 검증 중 예외 (non-critical)")

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


from antigravity_k import __version__

app = FastAPI(
    title="Antigravity-K API",
    description="OpenAI-compatible API for Antigravity-K Local Engine",
    version=__version__,
    lifespan=lifespan,
)

# CORS origins from config or environment (AGK_CORS_ORIGINS)
# Comma-separated list of allowed origins. Default: dashboard dev server + production
_cors_env = os.environ.get("AGK_CORS_ORIGINS", "")
if _cors_env:
    cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    cors_origins = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8000",  # Production uvicorn
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# slowapi state + middleware registration
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Inject security headers on every response.

    The CSP allows the CDN-hosted scripts the dashboard depends on (cdnjs,
    jsdelivr, Google Fonts) and inline styles/scripts (required by the
    vanilla-JS dashboard), but blocks ``javascript:`` navigation and restricts
    frame ancestors. This is defense-in-depth alongside DOMPurify sanitization
    of agent output in the frontend.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    # CSP: allow self + the specific CDNs the dashboard uses. 'unsafe-inline'
    # is required for the vanilla-JS dashboard's inline styles/handlers; this
    # will be tightened when the frontend moves to a build-time CSP nonce.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' "
        "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' ws: wss: http: https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    return response


# ---------------------------------------------------------------------------
# Public paths that do NOT require authentication.
# Kept as a set for O(1) lookups in the hot path.
# ---------------------------------------------------------------------------
_PUBLIC_EXACT_PATHS = frozenset(
    {
        "/api/auth/login",
        "/health",
        "/v1/health",
        "/api/health/deep",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)

# Path prefixes that require authentication.
_PROTECTED_PREFIXES = ("/api/", "/v1/", "/ws/", "/ide/")


def _is_protected_path(path: str) -> bool:
    """Return True if the request path requires authentication.

    A path is protected if it falls under one of the protected prefixes
    (``/api/``, ``/v1/``, ``/ws/``, ``/ide/``) and is not in the explicit
    public allowlist.
    """
    if path in _PUBLIC_EXACT_PATHS:
        return False
    return path.startswith(_PROTECTED_PREFIXES)


@app.middleware("http")
async def verify_access_token(request: Request, call_next):
    """Authenticate requests to protected paths via bearer token (or legacy PIN).

    Coverage is widened from the previous ``/api/``-only guard to also include
    ``/v1/*`` (LLM inference), ``/ws/*`` (terminal/events), and ``/ide/*``.
    Health checks, docs, and the login endpoint remain public.

    Credentials are accepted in two forms:
      1. ``Authorization: Bearer <jwt>``  — primary, issued by /api/auth/login.
      2. ``X-Access-Pin`` header / ``ag_access_pin`` cookie — legacy fallback
         for existing dashboard clients during the migration window. Compared
         constant-time via PBKDF2 verification.
    """
    if _is_protected_path(request.url.path):
        from antigravity_k.api.auth_routes import authenticate_request

        if not authenticate_request(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing credentials", "ok": False},
            )
    return await call_next(request)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect RED (Rate, Errors, Duration) metrics for every HTTP request.

    Records request count (by method/path/status), latency histogram, and an
    in-flight gauge. Runs after auth so that 401 responses are also counted.
    """
    from antigravity_k.engine.metrics import (
        request_counter,
        request_latency,
        requests_in_flight,
    )

    # Short-circuit: skip collection for the metrics endpoint itself to avoid
    # a feedback loop (scraping /metrics would increment its own counters).
    if request.url.path == "/metrics":
        return await call_next(request)

    requests_in_flight().inc()
    start = asyncio.get_event_loop().time()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        elapsed = asyncio.get_event_loop().time() - start
        requests_in_flight().dec()
        # Normalize path templates to avoid high-cardinality label explosion.
        # Use the raw path with query stripped; route templating would be ideal
        # but the middleware runs before route resolution.
        path = request.url.path
        request_counter().labels(method=request.method, path=path, status=status_code).inc()
        request_latency().labels(method=request.method, path=path).observe(elapsed)


from antigravity_k.api.auth_routes import router as auth_router
from antigravity_k.api.routes import api_router

app.include_router(auth_router)
app.include_router(api_router)

# Prometheus metrics endpoint (public — Prometheus scrapers need access).
# We expose a plain GET route at exactly /metrics (the ASGI mount from
# make_asgi_app only serves /metrics/ with a trailing slash, which Prometheus
# does not send by default).
from fastapi import Response  # noqa: E402

from antigravity_k.engine.metrics import render_metrics  # noqa: E402


@app.get("/metrics")
def metrics_endpoint() -> Response:
    """Prometheus exposition endpoint."""
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# Correlation-ID middleware + global exception handler registration.
# ---------------------------------------------------------------------------
import uuid  # noqa: E402

from antigravity_k.api.error_handler import (  # noqa: E402
    correlation_id_var,
    global_exception_handler,
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Assign or propagate a correlation id for every request.

    Reads an inbound ``X-Request-Id`` header if present (so callers can trace
    a request across services), otherwise generates one. The id is stored in a
    ``ContextVar`` so log records can include it, and echoed back in the
    ``X-Request-Id`` response header.
    """
    cid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    token = correlation_id_var.set(cid)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = cid
        return response
    finally:
        correlation_id_var.reset(token)


# Register the catch-all exception handler so 500s never leak str(exc).
app.add_exception_handler(Exception, global_exception_handler)

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
