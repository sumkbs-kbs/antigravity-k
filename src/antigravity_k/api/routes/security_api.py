"""Security & Shields API — 보호 레벨 제어, 시크릿 스캔, 심층 헬스체크."""

import logging
import os

import yaml
from fastapi import APIRouter, Request

from antigravity_k.config import config
from antigravity_k.engine.runtime_recovery import deep_health_check
from antigravity_k.engine.secret_scanner import redact, redact_full, scan_for_secrets, strip_credentials
from antigravity_k.engine.shields import ShieldsManager
from antigravity_k.engine.toolset_manager import ToolsetManager
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_contracts import ToolInvocation, ToolSpec

router = APIRouter()
logger = logging.getLogger("antigravity_k.api.routes.security")

_toolset_manager = None


def _permission_gate() -> PermissionGate:
    return PermissionGate(project_root=str(config.paths.project_root), mode="auto-pilot")


def _require_allowed(tool_name: str, args: dict, risk_level: str) -> None:
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403,
            detail=f"Permission denied for {tool_name}: {decision.permission.value}",
        )


def _get_memory_manager():
    from antigravity_k.api.dependencies import get_memory_manager

    return get_memory_manager()


def _get_model_manager():
    from antigravity_k.api.dependencies import get_model_manager

    return get_model_manager()


def _get_session_manager():
    from antigravity_k.api.dependencies import _get_session_manager

    return _get_session_manager()


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
                    cfg = yaml.safe_load(f) or {}
                _toolset_manager = ToolsetManager.from_config(cfg.get("toolsets", {}))
            else:
                _toolset_manager = ToolsetManager()
        except Exception:
            logger.exception("Unhandled exception")
            _toolset_manager = ToolsetManager()
    return _toolset_manager


_shields_manager = None


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
                import yaml

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
    user_config = body.get("config", {})
    return {"sanitized": strip_credentials(user_config)}


@router.get("/api/health/deep")
async def get_deep_health():
    """전체 시스템 깊은 Health Check를 수행합니다.

    인퍼런스, 메모리, 가드레일, shields 등 모든 컴포넌트를 점검합니다.
    """
    from dataclasses import asdict

    health = deep_health_check(
        model_manager=_get_model_manager(),
        session_manager=_get_session_manager(),
        memory_manager=_get_memory_manager(),
        toolset_manager=_get_toolset_manager(),
        shields_manager=_get_shields_manager(),
    )
    return {
        "status": health.status.value,
        "components": [asdict(c) for c in health.components],
    }
