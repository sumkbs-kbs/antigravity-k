"""Primary API routes: vault, chat, tasks, kanban, code-intel, slash commands, shields."""

import asyncio
import json
import logging
import os
from collections.abc import Iterable
from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import StreamingResponse

from antigravity_k.api.dependencies import (
    _get_session_manager,
    get_agent_runtime,
    get_model_manager,
    get_slash_registry,
)
from antigravity_k.config import config
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_contracts import ToolInvocation, ToolSpec

logger = logging.getLogger("antigravity_k.api.legacy")
router = APIRouter()


def _permission_gate() -> PermissionGate:
    return PermissionGate(project_root=str(config.paths.project_root), mode="auto-pilot")


def _require_allowed(tool_name: str, args: dict[str, Any], risk_level: str) -> None:
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied for {tool_name}: {decision.permission.value}",
        )


# NOTE: The unauthenticated ``/ws/terminal`` handler that previously lived here
# has been removed. It duplicated the safer, auth-gated version in system_api.py
# (which checks ``close_unauthorized_ws`` + the ``AGK_ENABLE_TERMINAL_WS`` flag)
# but — being registered first — shadowed it, leaving an open PTY behind a
# 4-digit PIN. The authenticated version in system_api.py is now reachable.


# Mount static dashboard if available
# ─── Claw Code: Slash Commands & Session API ─────────────────
# 팩토리 구현은 dependencies로 이동 — 하위 호환 별칭 유지
_get_slash_registry = get_slash_registry


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
    result: object = registry.execute(text)
    if not isinstance(result, str) and isinstance(result, Iterable):
        result = "".join(str(chunk) for chunk in result)
    return {"ok": True, "result": str(result)}


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


from antigravity_k.api.routes.session_state import (
    _active_session,
    reset_active_session,
)


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

        # Start new session — 바인딩 재할당 대신 동일 객체를 리셋한다
        # (값 복사 임포트 소비자의 stale 바인딩 방지)
        reset_active_session()
        _active_session.is_active = True
        _active_session.q = q

        try:
            # Instantiate orchestrator
            runtime = get_agent_runtime()
            _active_session.orchestrator = runtime.orchestrator

            messages = [{"role": "user", "content": q}]
            target_model = runtime.resolve_model()
            tracked_stream = runtime.start_stream(messages, target_model=target_model)
            if tracked_stream.task_id:
                yield f"data: {json.dumps({'task_id': tracked_stream.task_id})}\n\n"

            # We don't want the task to cancel if the client disconnects,
            # so we run it completely and buffer. Wait, actually SSE generator
            # might still be cancelled. But with iterate_in_threadpool it usually
            # finishes the thread.
            async for chunk in iterate_in_threadpool(
                tracked_stream.chunks,
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


@router.post("/api/models/default")
async def set_default_model(request: Request):
    """Set default model for a role in config.yaml.

    Body:
        name: model slug (e.g. "nvidia/nemotron-3-ultra-550b-a55b:free")
        role: optional role override (default: auto-detect from registry)
    """
    try:
        body = await request.json()
        name = body.get("name", "")
        if not name:
            raise HTTPException(status_code=400, detail="'name' is required")

        from antigravity_k.engine.model_registry import ModelRegistry

        registry = ModelRegistry()
        model = registry.get_model(name)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model '{name}' not found in registry")

        role = body.get("role", model.role)
        config_file = os.path.join(config.paths.project_root, "config.yaml")

        with open(config_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        if "defaults" not in cfg or not isinstance(cfg["defaults"], dict):
            cfg["defaults"] = {}

        old_default = cfg["defaults"].get(role, "(없음)")
        cfg["defaults"][role] = name

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Re-registry reload
        registry.reload()

        return {
            "ok": True,
            "role": role,
            "old_default": old_default,
            "new_default": name,
            "message": f"기본 {role} 모델이 {name}(으)로 변경되었습니다.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to set default model: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/settings")
async def get_settings():
    """Retrieve settings — .env에서 API 키 상태를 포함하여 반환."""
    # __file__ = src/antigravity_k/api/routes/legacy.py → 5번 dirname = 프로젝트 루트
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    config_file = os.path.join(project_root, "config.yaml")
    if not os.path.exists(config_file):
        return {"settings": {}}
    try:
        with open(config_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        # .env에서 API 키 상태 확인 (마스킹)
        env_keys = [
            "OPENROUTER_API_KEY",
            "NVIDIA_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "ZAI_API_KEY",
            "ANTHROPIC_API_KEY",
        ]
        api_keys = {}
        for k in env_keys:
            val = os.environ.get(k, "")
            if val and len(val) > 4:
                api_keys[k] = val[:4] + "*" * (len(val) - 4)
            elif val:
                api_keys[k] = "****"
            else:
                api_keys[k] = ""
        cfg["api_keys"] = api_keys
        cfg.setdefault("model", {})
        cfg["model"]["name"] = cfg.get("defaults", {}).get("reasoning", "")
        cfg["model"]["provider"] = cfg.get("model", {}).get("api_engine", "")
        return {"settings": cfg}
    except Exception as e:
        logger.exception("Unhandled exception")
        return {"settings": {"error": str(e)}}


# ─── Memory & Toolset & Guardrail APIs ─────────────────────────────────────

from antigravity_k.engine.toolset_manager import ToolsetManager

_toolset_manager: ToolsetManager | None = None


def _get_memory_manager():
    from antigravity_k.api.dependencies import get_memory_manager

    return get_memory_manager()


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
    _require_allowed("shields_down", body, "critical")
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
    _require_allowed("shields_up", {}, "high")
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


@router.post("/api/settings/env")
async def save_env_settings(request: Request):
    """사용자가 설정한 API 키 등을 .env 파일에 저장합니다."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    _require_allowed(
        "save_env_settings",
        {"keys": sorted(key for key, value in body.items() if value)},
        "critical",
    )

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    env_path = os.path.join(project_root, ".env")

    # 기존 .env 읽기
    existing_lines = []
    existing_keys: dict[str, int] = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                existing_lines.append(line.rstrip("\n"))
                if "=" in line and not line.startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    existing_keys[key] = i

    # API 키와 설정값 업데이트
    env_var_keys = [
        "OPENROUTER_API_KEY",
        "NVIDIA_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "ZAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AGK_DAILY_BUDGET_USD",
        "AGK_HOURLY_ACTION_LIMIT",
    ]
    updated_count = 0
    for key, value in body.items():
        if not value:
            continue
        if key in env_var_keys or key.endswith("_API_KEY"):
            if key in existing_keys:
                existing_lines[existing_keys[key]] = f"{key}={value}"
            else:
                existing_lines.append(f"{key}={value}")
            updated_count += 1

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(existing_lines) + "\n")

    return {"ok": True, "updated": updated_count, "message": "설정이 .env에 저장되었습니다."}
