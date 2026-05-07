"""
Agent Activity API — 에이전트 활동 상태 + 감사 로그 조회 엔드포인트
====================================================================
Sidabari의 패널 활동 추적 + SQLite 감사 로그를 대시보드에 제공합니다.
"""

from fastapi import APIRouter, Query
from typing import Optional
import logging
import time

logger = logging.getLogger("antigravity_k.api.routes.agent_activity")

router = APIRouter(prefix="/api/agent")


@router.get("/activity")
async def get_agent_activity():
    """모든 에이전트의 현재 활동 상태를 조회합니다.

    Returns:
        패널별 activity 상태 (thinking/idle) + 현재 도구 정보
    """
    try:
        from antigravity_k.engine.panel_activity_tracker import (
            get_panel_activity_tracker,
        )

        tracker = get_panel_activity_tracker()
        activities = tracker.get_all_activities()
        thinking_panels = tracker.get_thinking_panels()

        return {
            "ok": True,
            "activities": activities,
            "thinking_count": len(thinking_panels),
            "thinking_panels": thinking_panels,
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"Activity query failed: {e}")
        return {"ok": False, "error": str(e), "activities": {}}


@router.get("/audit/recent")
async def get_recent_audit_events(
    limit: int = Query(default=50, le=500),
    kind: Optional[str] = Query(default=None),
    panel_id: Optional[str] = Query(default=None),
    since_minutes: Optional[int] = Query(default=None),
):
    """최근 감사 이벤트를 조회합니다.

    Args:
        limit: 최대 반환 수 (기본 50, 최대 500)
        kind: 이벤트 종류 필터
        panel_id: 패널 ID 필터
        since_minutes: 최근 N분 이내 이벤트만
    """
    try:
        from antigravity_k.engine.audit_db import get_audit_db

        db = get_audit_db()
        if not db._initialized:
            return {"ok": False, "error": "AuditDb not initialized", "events": []}

        since_ms = None
        if since_minutes:
            since_ms = int((time.time() - since_minutes * 60) * 1000)

        events = db.query_recent(
            limit=limit,
            kind=kind,
            panel_id=panel_id,
            since_ms=since_ms,
        )

        return {
            "ok": True,
            "events": events,
            "count": len(events),
            "total": db.count_events(since_ms=since_ms),
        }
    except Exception as e:
        logger.error(f"Audit query failed: {e}")
        return {"ok": False, "error": str(e), "events": []}


@router.get("/audit/tool-stats")
async def get_tool_stats(
    since_minutes: Optional[int] = Query(default=60),
):
    """도구별 호출 통계를 조회합니다.

    Args:
        since_minutes: 최근 N분 이내 통계 (기본 60분)
    """
    try:
        from antigravity_k.engine.audit_db import get_audit_db

        db = get_audit_db()
        if not db._initialized:
            return {"ok": False, "error": "AuditDb not initialized", "stats": []}

        since_ms = None
        if since_minutes:
            since_ms = int((time.time() - since_minutes * 60) * 1000)

        stats = db.query_tool_stats(since_ms=since_ms)

        return {
            "ok": True,
            "stats": stats,
            "period_minutes": since_minutes,
        }
    except Exception as e:
        logger.error(f"Tool stats query failed: {e}")
        return {"ok": False, "error": str(e), "stats": []}


@router.get("/deny-rules/status")
async def get_deny_rules_status(directory: Optional[str] = Query(default=None)):
    """현재 deny 패턴 설치 상태를 확인합니다."""
    try:
        from antigravity_k.engine.claude_deny_patterns import (
            get_deny_rules_status,
        )

        if not directory:
            import os

            directory = os.getcwd()

        status = get_deny_rules_status(directory)
        if status:
            return {"ok": True, "installed": True, **status.to_dict()}
        else:
            return {"ok": True, "installed": False}
    except Exception as e:
        logger.error(f"Deny rules status check failed: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/deny-rules/install")
async def install_deny_rules(directory: Optional[str] = None):
    """deny 패턴을 설치합니다."""
    try:
        from antigravity_k.engine.claude_deny_patterns import (
            install_deny_rules as _install,
        )

        if not directory:
            import os

            directory = os.getcwd()

        report = _install(directory)
        return {"ok": True, **report.to_dict()}
    except Exception as e:
        logger.error(f"Deny rules installation failed: {e}")
        return {"ok": False, "error": str(e)}
