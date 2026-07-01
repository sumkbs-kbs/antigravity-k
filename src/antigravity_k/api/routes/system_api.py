"""Antigravity-K: System API Routes (Memory, Toolset, Harness, Shields, System).

================================================================================

Memory, Toolset, Harness, Shields, Security, Slash, Session, Code Intel, System routes.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict

import psutil
import yaml
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from antigravity_k.api.dependencies import (
    __get_skill_loader,
    __get_tool_registry,
    _get_context_shaper,
    _get_session_manager,
    get_model_manager,
)
from antigravity_k.api.models import _active_session

logger = logging.getLogger("antigravity_k.api.system_api")
router = APIRouter()


# ─── Helpers ────────────────────────────────────────────────────


def _get_slash_registry():
    from antigravity_k.engine.slash_commands import SlashCommandRegistry

    return SlashCommandRegistry(
        tool_registry=__get_tool_registry(),
        session_manager=_get_session_manager(),
        context_shaper=_get_context_shaper(),
        model_manager=get_model_manager(),
        skill_loader=__get_skill_loader(),
    )


def _get_memory_manager():
    from antigravity_k.engine.memory_provider import (
        BuiltinMemoryProvider,
        MemoryManager,
    )

    mm = MemoryManager()
    try:
        sm = _get_session_manager()
        mm.add_provider(BuiltinMemoryProvider(sm))
    except Exception:
        logger.exception("BuiltinMemoryProvider 초기화 실패")
    return mm


def _get_toolset_manager():
    from antigravity_k.engine.toolset_manager import ToolsetManager

    try:
        config_file = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            ),
            "config.yaml",
        )
        if os.path.exists(config_file):
            with open(config_file, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return ToolsetManager.from_config(cfg.get("toolsets", {}))
    except Exception:
        logger.exception("Unhandled exception")
        pass
    return ToolsetManager()


def _get_shields_manager():
    from antigravity_k.engine.shields import ShieldsManager

    try:
        config_file = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            ),
            "config.yaml",
        )
        shields_config = {}
        if os.path.exists(config_file):
            with open(config_file, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            shields_config = cfg.get("shields", {})
        return ShieldsManager.from_config(
            shields_config,
            toolset_manager=_get_toolset_manager(),
        )
    except Exception:
        logger.exception("Unhandled exception")
        return ShieldsManager(toolset_manager=_get_toolset_manager())


def get_harness():
    """Retrieve harness."""
    from antigravity_k.engine.harness import TestHarness

    return TestHarness()


# ─── Slash & Session API ────────────────────────────────────────


@router.post("/api/slash")
async def slash_command(request: Request):
    """Slash Command.

    Args:
        request (Request): Request request.

    """
    body = await request.json()
    text = body.get("command") or body.get("input") or body.get("text") or ""
    registry = _get_slash_registry()
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
    msgs = sm.get_messages()
    dicts = [m.to_simple_dict() for m in msgs] if msgs and hasattr(msgs[0], "to_simple_dict") else msgs
    return {"ok": True, "messages": dicts}


@router.post("/api/session/save")
async def session_save():
    """Session Save."""
    sm = _get_session_manager()
    sm.save()
    return {"ok": True, "message": "Session saved."}


# ─── Memory API ─────────────────────────────────────────────────


@router.get("/api/memory/stats")
async def get_memory_stats():
    """Retrieve memory stats."""
    mm = _get_memory_manager()
    return {"memory": mm.get_stats()}


@router.get("/api/memory/recall")
async def recall_memory(query: str = ""):
    """Recall Memory.

    Args:
        query (str): str query.

    """
    mm = _get_memory_manager()
    result = mm.prefetch_all(query or "general")
    return {"recalled": result, "query": query}


# ─── Toolset API ────────────────────────────────────────────────


@router.get("/api/toolsets")
async def list_toolsets():
    """List Toolsets."""
    ts = _get_toolset_manager()
    return {"toolsets": ts.list_toolsets(), "active": ts.active_toolset}


@router.post("/api/toolsets/activate")
async def activate_toolset(request: Request):
    """Activate Toolset.

    Args:
        request (Request): Request request.

    """
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
    """Retrieve toolset tools.

    Args:
        name (str): str name.

    """
    ts = _get_toolset_manager()
    tools = ts.resolve(name)
    return {"toolset": name, "tools": tools, "count": len(tools)}


# ─── Harness API ────────────────────────────────────────────────


@router.post("/api/harness/self-test")
async def harness_self_test(request: Request):
    """Harness Self Test.

    Args:
        request (Request): Request request.

    """
    try:
        body = await request.json()
    except Exception:
        logger.exception("Unhandled exception")
        body = {}
    scope = body.get("scope", "api_only")
    harness = get_harness()
    report = await harness.run_all(use_browser=(scope != "api_only"))
    return {"ok": True, "report": report.to_dict()}


@router.get("/api/harness/results")
async def harness_results():
    """Harness Results."""
    harness = get_harness()
    report = harness.get_latest_report()
    if report:
        return {"ok": True, "report": report.to_dict()}
    return {"ok": True, "report": None, "message": "아직 테스트가 실행되지 않았습니다."}


@router.get("/api/harness/trend")
async def harness_trend():
    """Harness Trend."""
    harness = get_harness()
    trend = harness.feedback.get_trend()
    return {"ok": True, "trend": trend}


# ─── System API ─────────────────────────────────────────────────

START_TIME = time.time()


@router.get("/api/system/status")
async def system_status():
    """System Status."""
    try:
        mem_info = psutil.virtual_memory()
        uptime_seconds = int(time.time() - START_TIME)
        model_manager = get_model_manager()
        total_tokens = model_manager.tracker.get_total_tokens()
        return {
            "ok": True,
            "status": "online",
            "memory_mb": mem_info.percent,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "total_tokens": total_tokens,
            "uptime_seconds": uptime_seconds,
            "version": "v0.2.0",
        }
    except Exception as e:
        logger.error("Status error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/system/restart")
async def system_restart(background_tasks: BackgroundTasks):
    """System Restart.

    Args:
        background_tasks (BackgroundTasks): BackgroundTasks background tasks.

    """
    try:

        def delay_restart():
            trigger_file = os.path.abspath(os.path.join("src", ".restart_trigger"))
            with open(trigger_file, "a"):
                os.utime(trigger_file, None)
            logger.info("Restart triggered via API (delayed).")

        background_tasks.add_task(delay_restart)
        return {
            "ok": True,
            "message": "Restart triggered. The server will reboot in a moment.",
        }
    except Exception as e:
        logger.error("Restart error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/system/full-status")
async def get_system_status_extended():
    """Retrieve system status extended."""
    mm = _get_memory_manager()
    ts = _get_toolset_manager()
    return {
        "status": "running",
        "memory": mm.get_stats(),
        "toolset": {
            "active": ts.active_toolset,
            "available": list(ts.list_toolsets().keys()),
        },
        "guardrails": {"warnings_enabled": True, "hard_stop_enabled": False},
    }


# ─── Terminal WebSocket (PTY-based) ──────────────────────────────

import asyncio
import fcntl
import pty
import struct
import termios

from fastapi import WebSocket, WebSocketDisconnect

from antigravity_k.api.models import close_unauthorized_ws


@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """Websocket Terminal.

    Args:
        websocket (WebSocket): WebSocket websocket.

    """
    if await close_unauthorized_ws(websocket):
        return
    if os.environ.get("AGK_ENABLE_TERMINAL_WS", "").lower() not in {"1", "true", "yes"}:
        await websocket.close(code=1008, reason="Terminal WebSocket is disabled")
        return

    await websocket.accept()

    master, slave = pty.openpty()
    shell = os.environ.get("SHELL", "/bin/zsh")
    pid = os.fork()
    if pid == 0:
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(master)
        os.close(slave)
        os.execlp(shell, shell)

    os.close(slave)
    loop = asyncio.get_running_loop()

    def pty_output_callback():
        try:
            data = os.read(master, 1024)
            if data:
                asyncio.create_task(
                    websocket.send_text(data.decode("utf-8", errors="replace")),
                )
            else:
                loop.remove_reader(master)
        except Exception:
            logger.exception("Unhandled exception")
            loop.remove_reader(master)

    loop.add_reader(master, pty_output_callback)

    def _cleanup_pty():
        try:
            loop.remove_reader(master)
        except Exception:
            logger.exception("Unhandled exception")
            pass
        try:
            os.close(master)
        except OSError:
            pass
        import signal
        import time

        try:
            os.kill(pid, signal.SIGTERM)
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
            if data.startswith('{"type":"resize"'):
                try:
                    import json

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


# ─── Code Intel API ─────────────────────────────────────────────


@router.post("/api/code-intel/index")
async def code_intel_index(request: Request):
    """Code Intel Index.

    Args:
        request (Request): Request request.

    """
    try:
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        data = await request.json()
        repo_path = data.get("repo_path", ".")
        force = data.get("force", False)
        pipeline = CodeIndexPipeline()
        result = pipeline.run(repo_path, force=force)
        return result
    except ImportError:
        raise HTTPException(status_code=501, detail="Code Intel not installed")
    except Exception as e:
        logger.error("Code Intel index error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/code-intel/search")
async def code_intel_search(q: str, repo_path: str, top_k: int = 10):
    """Code Intel Search.

    Args:
        q (str): str q.
        repo_path (str): str repo path.
        top_k (int): int top k.

    """
    try:
        from antigravity_k.engine.code_intel.hybrid_search import HybridSearchEngine
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        pipeline = CodeIndexPipeline()
        loaded = pipeline.load_existing(repo_path)
        if not loaded:
            raise HTTPException(
                status_code=404,
                detail=f"'{repo_path}'의 인덱스가 없습니다.",
            )
        search = HybridSearchEngine(pipeline.graph)
        search.build_index()
        results = search.search(q, top_k=top_k)
        return {"query": q, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Code Intel search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/code-intel/impact")
async def code_intel_impact(request: Request):
    """Code Intel Impact.

    Args:
        request (Request): Request request.

    """
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
            raise HTTPException(
                status_code=404,
                detail=f"'{repo_path}'의 인덱스가 없습니다.",
            )
        analyzer = ImpactAnalyzer(pipeline.graph)
        result = analyzer.analyze(symbol_id, max_depth=max_depth)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Code Intel impact error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Shields & Security API ─────────────────────────────────────


@router.get("/api/shields/status")
async def get_shields_status():
    """Retrieve shields status."""
    shields = _get_shields_manager()
    return shields.status()


@router.post("/api/shields/down")
async def shields_down(request: Request):
    """Shields Down.

    Args:
        request (Request): Request request.

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
    """Shields Up."""
    shields = _get_shields_manager()
    shields.shields_up(restored_by="api_operator")
    return shields.status()


@router.get("/api/shields/audit")
async def get_shields_audit(limit: int = Query(default=50, ge=1, le=500)):
    """Retrieve shields audit.

    Args:
        limit (int): int limit.

    """
    shields = _get_shields_manager()
    return {"audit_log": shields.get_audit_log(limit=limit)}


@router.post("/api/security/scan")
async def scan_text_for_secrets(request: Request):
    """Scan Text For Secrets.

    Args:
        request (Request): Request request.

    """
    body = await request.json()
    text = body.get("text", "")
    mode = body.get("redact_mode", "partial")

    from antigravity_k.engine.secret_scanner import (
        redact,
        redact_full,
        scan_for_secrets,
    )

    matches = scan_for_secrets(text)
    redacted_text = redact(text) if mode == "partial" else redact_full(text)
    return {
        "secrets_found": len(matches),
        "matches": [{"pattern": m.pattern, "redacted": m.redacted} for m in matches],
        "redacted_text": redacted_text,
    }


@router.post("/api/security/strip-config")
async def strip_config_credentials(request: Request):
    """Strip Config Credentials.

    Args:
        request (Request): Request request.

    """
    body = await request.json()
    config_data = body.get("config", {})
    from antigravity_k.engine.secret_scanner import strip_credentials

    return {"sanitized": strip_credentials(config_data)}


@router.get("/api/health/deep")
async def get_deep_health():
    """Retrieve deep health."""
    try:
        from antigravity_k.engine.runtime_recovery import deep_health_check

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
    except ImportError:
        logger.warning("runtime_recovery module not available")
        return {
            "status": "unknown",
            "components": [],
            "diagnosis": "deep_health_check not available",
        }


# ─── Harness Status (active session dependent) ──────────────────


@router.get("/api/harness/status")
async def get_live_harness_status():
    """Retrieve live harness status."""
    if not _active_session.is_active or not _active_session.orchestrator:
        return {
            "ok": True,
            "phase": "bypass",
            "gates_passed": 0,
            "gates_total": 0,
            "tools_allowed": 0,
            "tools_blocked": 0,
            "anchors": 0,
            "cache_hit_rate": 0,
            "overall_health": "healthy",
        }
    orch = _active_session.orchestrator
    phase = "bypass"
    if hasattr(orch, "plan_guard") and orch.plan_guard:
        phase = orch.plan_guard.get_phase().value
    gates_passed = 0
    gates_total = 0
    tools_allowed = 0
    tools_blocked = 0
    overall_health = "healthy"
    if hasattr(orch, "harness") and orch.harness:
        stats = orch.harness.get_stats()
        gates_passed = stats.get("gates_passed", 0)
        gates_total = stats.get("gates_total", 0)
        tools_allowed = stats.get("tools_allowed", 0)
        tools_blocked = stats.get("tools_blocked", 0)
        overall_health = orch.harness.get_harness_status().overall_health
    anchors_count = 0
    if hasattr(orch, "ctx") and hasattr(orch.ctx, "decision_anchor"):
        anchors_count = len(orch.ctx.decision_anchor.get_all())
    return {
        "ok": True,
        "phase": phase,
        "gates_passed": gates_passed,
        "gates_total": gates_total,
        "tools_allowed": tools_allowed,
        "tools_blocked": tools_blocked,
        "anchors": anchors_count,
        "cache_hit_rate": 85,
        "overall_health": overall_health,
    }
