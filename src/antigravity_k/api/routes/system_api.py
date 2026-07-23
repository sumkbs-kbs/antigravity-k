"""Antigravity-K: System API Routes (Memory, Toolset, Harness, Shields, System).

================================================================================

Memory, Toolset, Harness, Shields, Security, Slash, Session, Code Intel, System routes.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from datetime import datetime

import psutil
import yaml
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from antigravity_k import __version__
from antigravity_k.api.dependencies import (
    __get_skill_loader,
    __get_tool_registry,
    _get_context_shaper,
    _get_session_manager,
    get_model_manager,
)
from antigravity_k.api.routes.legacy import _active_session
from antigravity_k.engine.api_cache import TAG_SKILLS, TAG_SYSTEM, api_cache, cached
from antigravity_k.engine.log_level_manager import LogLevelManager

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
@cached(ttl=30, tags=[TAG_SYSTEM])
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


# ─── Skills API (D16: Dashboard Skills Browser) ─────────────────


@router.get("/api/system/skills")
@cached(ttl=60, tags=[TAG_SKILLS])
async def system_skills():
    """SkillLoader.list_skills() 결과를 JSON으로 반환합니다.

    Phase 1 D16: Dashboard Skills Browser에서 사용.
    각 스킬의 source(global/local/market), id, name, description, version 정보 포함.
    """
    try:
        sl = __get_skill_loader()
        skills = sl.list_skills()
        return {"ok": True, "skills": skills}
    except Exception as e:
        logger.error("Skills list error: %s", e)
        return {"ok": False, "skills": [], "error": str(e)}


@router.get("/api/system/skills/installed")
@cached(ttl=60, tags=[TAG_SKILLS])
async def system_skills_installed():
    """SkillMarketRegistry.list_installed() 결과를 JSON으로 반환합니다.

    Phase 1 D16: Dashboard Skills Browser — Marketplace 탭에서 사용.
    설치된 스킬의 상세 정보 (name, version, is_loaded, mcp_server_id 등) 포함.
    """
    try:
        from antigravity_k.engine.skill_installer import SkillInstaller
        from antigravity_k.engine.skill_market_client import SkillMarketClient
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        sl = __get_skill_loader()
        installer = SkillInstaller(project_root=os.getcwd(), skill_loader=sl)
        client = SkillMarketClient(
            project_root=os.getcwd(),
            install_dir=".agent/skills/market",
        )
        registry = SkillMarketRegistry(
            project_root=os.getcwd(),
            market_client=client,
            installer=installer,
            skill_loader=sl,
        )
        installed = registry.list_installed()
        result = []
        for skill in installed:
            s = {
                "name": skill.name,
                "version": skill.version,
                "is_loaded": skill.is_loaded,
                "mcp_server_id": skill.mcp_server_id,
                "security_issues": skill.security_issues,
            }
            result.append(s)
        return {"ok": True, "installed": result}
    except Exception as e:
        logger.error("Installed skills error: %s", e)
        return {"ok": False, "installed": [], "error": str(e)}


@router.get("/api/system/skills/mcp")
@cached(ttl=30, tags=[TAG_SKILLS])
async def system_skills_mcp():
    """MCPServerRegistry.list_skills_with_mcp() 결과를 JSON으로 반환합니다.

    Phase 1 D16: Dashboard Skills Browser — MCP Servers 탭에서 사용.
    각 스킬별 MCP 서버 정보 (name, status, tools) 포함.
    """
    try:
        from antigravity_k.tools.mcp_tool_loader import MCPServerRegistry

        mcp = MCPServerRegistry()
        servers = mcp.list_skills_with_mcp()
        return {"ok": True, "servers": servers}
    except Exception as e:
        logger.error("MCP skills error: %s", e)
        return {"ok": False, "servers": [], "error": str(e)}


@router.get("/api/system/skills/search")
async def system_skills_search(
    q: str = Query("", description="Search query for npm skill packages"),
    limit: int = Query(15, ge=1, le=50, description="Max results"),
):
    """npm 레지스트리에서 @antigravity-k/skill-* 패키지를 검색합니다.

    Phase 1 D20: Dashboard Skills Browser — Search tab에서 실시간 검색.
    """
    try:
        from antigravity_k.engine.skill_market_client import SkillMarketClient

        client = SkillMarketClient()
        results = client.search(q, limit=limit)
        formatted = [r.to_dict() for r in results]
        return {"ok": True, "results": formatted, "count": len(formatted)}
    except Exception as e:
        logger.error("Skills search error: %s", e)
        return {"ok": False, "results": [], "count": 0, "error": str(e)}


@router.post("/api/system/skills/install")
async def system_skills_install(request: Request):
    """npm 패키지를 설치합니다.

    Phase 1 D20: Dashboard Skills Browser — Install 버튼.
    """
    try:
        body = await request.json()
        package_name = body.get("package_name", "")
        if not package_name:
            return {"ok": False, "error": "package_name is required"}

        from antigravity_k.engine.skill_installer import SkillInstaller
        from antigravity_k.engine.skill_market_client import SkillMarketClient
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        sl = __get_skill_loader()
        installer = SkillInstaller(project_root=os.getcwd(), skill_loader=sl)
        client = SkillMarketClient(project_root=os.getcwd())
        registry = SkillMarketRegistry(
            project_root=os.getcwd(),
            market_client=client,
            installer=installer,
            skill_loader=sl,
        )
        result = registry.install(package_name)
        return {"ok": result.get("success", False), "result": result}
    except Exception as e:
        logger.error("Skill install error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/api/system/skills/remove")
async def system_skills_remove(request: Request):
    """설치된 스킬을 제거합니다.

    Phase 1 D20: Dashboard Skills Browser — Remove 버튼.
    """
    try:
        body = await request.json()
        skill_name = body.get("skill_name", "")
        if not skill_name:
            return {"ok": False, "error": "skill_name is required"}

        from antigravity_k.engine.skill_installer import SkillInstaller
        from antigravity_k.engine.skill_market_client import SkillMarketClient
        from antigravity_k.engine.skill_market_registry import SkillMarketRegistry

        sl = __get_skill_loader()
        installer = SkillInstaller(project_root=os.getcwd(), skill_loader=sl)
        client = SkillMarketClient(project_root=os.getcwd())
        registry = SkillMarketRegistry(
            project_root=os.getcwd(),
            market_client=client,
            installer=installer,
            skill_loader=sl,
        )
        result = registry.remove(skill_name)
        return {"ok": result.get("success", False), "result": result}
    except Exception as e:
        logger.error("Skill remove error: %s", e)
        return {"ok": False, "error": str(e)}


# ─── Skill Publish API (D17: Publish to npm / GitHub PR) ──────


@router.get("/api/system/skills/local")
@cached(ttl=30, tags=[TAG_SKILLS])
async def system_skills_local():
    """로컬 스킬 디렉토리 목록을 반환합니다 (publish 가능한 스킬).

    Phase 1 D17: 로컬 .agent/skills/ 디렉토리에서 publish 가능한 스킬을 검색.
    각 스킬의 디렉토리 경로, SKILL.md frontmatter 정보, 유효성 상태를 포함.
    """
    try:
        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=os.getcwd())
        local_skills = []

        # market/ 디렉토리 검색
        if publisher.market_dir.exists():
            for skill_dir in publisher.market_dir.iterdir():
                if skill_dir.is_dir():
                    validation = publisher._validate_for_publish(skill_dir, skill_dir.name)
                    local_skills.append(
                        {
                            "name": skill_dir.name,
                            "path": str(skill_dir),
                            "source": "market",
                            "valid": validation.valid,
                            "has_skill_md": validation.has_skill_md,
                            "has_readme": validation.has_readme,
                            "version": validation.version,
                            "tool_count": validation.tool_count,
                            "warnings": validation.warnings,
                        }
                    )

        # .agent/skills/ 디렉토리 검색
        if publisher.skills_dir.exists():
            for skill_dir in publisher.skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    # market 디렉토리 자체는 건너뜀 (하위 스킬은 1차에서 이미 처리)
                    if skill_dir.name == "market" or skill_dir.parent.name == "market":
                        continue
                    already_listed = any(s["name"] == skill_dir.name for s in local_skills)
                    if not already_listed:
                        validation = publisher._validate_for_publish(skill_dir, skill_dir.name)
                        local_skills.append(
                            {
                                "name": skill_dir.name,
                                "path": str(skill_dir),
                                "source": "local",
                                "valid": validation.valid,
                                "has_skill_md": validation.has_skill_md,
                                "has_readme": validation.has_readme,
                                "version": validation.version,
                                "tool_count": validation.tool_count,
                                "warnings": validation.warnings,
                            }
                        )

        return {"ok": True, "skills": local_skills, "count": len(local_skills)}
    except Exception as e:
        logger.error("Local skills list error: %s", e)
        return {"ok": False, "skills": [], "count": 0, "error": str(e)}


@router.get("/api/system/skills/local/check")
async def system_skills_local_check(
    since: str = Query("", description="ISO timestamp or empty for full list"),
):
    """로컬 스킬 디렉토리 변경 내역을 반환합니다.

    Phase 1 D18: Skill auto-discovery — since 시점 이후 변경된 스킬 목록.
    since가 비어있으면 전체 목록 반환.

    Query params:
        since: ISO 8601 타임스탬프 (e.g. "2026-07-21T12:00:00Z").
               비어있으면 전체 스킬 목록 반환.

    Returns:
        dict: {ok, skills: [...], new: [...], removed: [...], changed: [...], checked_at, has_changes}
    """
    try:
        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=os.getcwd())
        current_skills: list[dict] = []
        seen_names: set[str] = set()

        # market/ 디렉토리 검색
        if publisher.market_dir.exists():
            for skill_dir in publisher.market_dir.iterdir():
                if skill_dir.is_dir() and skill_dir.name not in seen_names:
                    seen_names.add(skill_dir.name)
                    validation = publisher._validate_for_publish(skill_dir, skill_dir.name)
                    current_skills.append(
                        {
                            "name": skill_dir.name,
                            "source": "market",
                            "version": validation.version,
                            "valid": validation.valid,
                            "mtime": skill_dir.stat().st_mtime,
                        }
                    )

        # .agent/skills/ 디렉토리 검색
        if publisher.skills_dir.exists():
            for skill_dir in publisher.skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    if skill_dir.name == "market" or skill_dir.name in seen_names:
                        continue
                    seen_names.add(skill_dir.name)
                    validation = publisher._validate_for_publish(skill_dir, skill_dir.name)
                    current_skills.append(
                        {
                            "name": skill_dir.name,
                            "source": "local",
                            "version": validation.version,
                            "valid": validation.valid,
                            "mtime": skill_dir.stat().st_mtime,
                        }
                    )

        checked_at = datetime.utcnow().isoformat() + "Z"

        # since가 있으면 변경 탐지
        new_skills: list[dict] = []
        removed_skills: list[dict] = []
        changed_skills: list[dict] = []
        has_changes = False

        if since:
            try:
                since_ts = datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()
            except ValueError:
                since_ts = 0.0

            new_skills = [s for s in current_skills if s["mtime"] > since_ts]
            has_changes = bool(new_skills) or bool(removed_skills) or bool(changed_skills)

        return {
            "ok": True,
            "skills": current_skills,
            "new": new_skills,
            "removed": removed_skills,
            "changed": changed_skills,
            "checked_at": checked_at,
            "has_changes": has_changes,
            "count": len(current_skills),
        }
    except Exception as e:
        logger.error("Skills check error: %s", e)
        return {"ok": False, "skills": [], "count": 0, "error": str(e)}


@router.post("/api/system/skills/publish-npm")
async def system_skills_publish_npm(request: Request):
    """로컬 스킬을 npm 레지스트리에 publish합니다.

    Phase 1 D17: SkillPublisher.publish_to_npm()을 호출하여
    로컬 스킬 → npm publish 파이프라인을 실행.

    Request Body:
        skill_name (str): 스킬 이름
        version (str, optional): 버전 (기본: SKILL.md frontmatter)
        tag (str, optional): npm dist-tag (기본: "latest")
        dry_run (bool, optional): 검증만 수행 (기본: false)

    Returns:
        dict: {ok, publish_result: {success, action, package_name, version, errors, warnings, ...}}
    """
    try:
        body = await request.json()
        skill_name = body.get("skill_name", "")
        if not skill_name:
            return {"ok": False, "error": "skill_name is required"}

        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=os.getcwd())
        result = publisher.publish_to_npm(
            skill_name,
            version=body.get("version"),
            tag=body.get("tag", "latest"),
            dry_run=body.get("dry_run", False),
        )

        return {
            "ok": result.success,
            "publish_result": {
                "success": result.success,
                "action": result.action,
                "skill_name": result.skill_name,
                "package_name": result.package_name,
                "version": result.version,
                "npm_url": result.npm_url,
                "errors": result.errors,
                "warnings": result.warnings,
                "summary": result.summary(),
            },
        }
    except Exception as e:
        logger.exception("npm publish error")
        return {"ok": False, "error": str(e)}


@router.post("/api/system/skills/publish-github")
async def system_skills_publish_github(request: Request):
    """로컬 스킬을 GitHub PR로 제출합니다.

    Phase 1 D17: SkillPublisher.publish_to_github()을 호출하여
    로컬 스킬 → GitHub PR 파이프라인을 실행.

    Request Body:
        skill_name (str): 스킬 이름
        repo (str): 대상 GitHub 리포지토리 (e.g. "org/skills-repo")
        base_branch (str, optional): PR 대상 브랜치 (기본: "main")
        draft (bool, optional): Draft PR 생성 (기본: false)
        title (str, optional): PR 타이틀
        body (str, optional): PR 설명
        dry_run (bool, optional): 검증만 수행 (기본: false)

    Returns:
        dict: {ok, publish_result: {success, action, skill_name, pr_url, errors, ...}}
    """
    try:
        body = await request.json()
        skill_name = body.get("skill_name", "")
        repo = body.get("repo", "")
        if not skill_name:
            return {"ok": False, "error": "skill_name is required"}
        if not repo and not body.get("dry_run", False):
            return {"ok": False, "error": "repo is required (e.g. 'org/skills-repo')"}

        from antigravity_k.engine.skill_publisher import SkillPublisher

        publisher = SkillPublisher(project_root=os.getcwd())
        result = publisher.publish_to_github(
            skill_name,
            repo=repo,
            base_branch=body.get("base_branch", "main"),
            draft=body.get("draft", False),
            title=body.get("title"),
            body=body.get("body"),
            dry_run=body.get("dry_run", False),
        )

        return {
            "ok": result.success,
            "publish_result": {
                "success": result.success,
                "action": result.action,
                "skill_name": result.skill_name,
                "package_name": result.package_name,
                "pr_url": result.pr_url,
                "errors": result.errors,
                "warnings": result.warnings,
                "summary": result.summary(),
            },
        }
    except Exception as e:
        logger.exception("GitHub PR error")
        return {"ok": False, "error": str(e)}


@router.get("/api/system/mode/history")
async def system_mode_history():
    """ModeManager의 전체 모드 히스토리를 반환합니다.

    Phase 1 D16: Dashboard Mode Indicator 확장 — 히스토리 렌더링용.
    """
    try:
        from antigravity_k.api.dependencies import get_mode_manager

        mgr = get_mode_manager()
        history = [
            {
                "from": h.from_mode,
                "to": h.to_mode,
                "reason": h.reason,
                "timestamp": h.timestamp,
            }
            for h in mgr.mode_history
        ]
        return {"ok": True, "history": history}
    except Exception as e:
        logger.error("Mode history error: %s", e)
        return {"ok": False, "history": [], "error": str(e)}


# ─── System API ─────────────────────────────────────────────────

START_TIME = time.time()


@router.get("/api/system/mode")
async def system_mode():
    """현재 실행 모드(Plan/Build/Interactive)를 반환합니다.

    Phase 1 D7: Dashboard WebSocket이 초기 연결 시 현재 모드를 가져오기 위해 사용.
    depends에 ModeManager 싱글톤을 조회하여 실제 실행 모드 반환.
    """
    try:
        from antigravity_k.api.dependencies import get_mode_manager

        mgr = get_mode_manager()
        return {
            "ok": True,
            "mode": mgr.current_mode.value,
            "is_plan": mgr.is_plan,
            "is_build": mgr.is_build,
            "is_interactive": mgr.is_interactive,
            "plan_artifact_path": mgr.plan_artifact_path,
            "history_count": len(mgr.mode_history),
            "last_transition": (
                {
                    "from": mgr.mode_history[-1].from_mode,
                    "to": mgr.mode_history[-1].to_mode,
                    "reason": mgr.mode_history[-1].reason,
                    "timestamp": mgr.mode_history[-1].timestamp,
                }
                if mgr.mode_history
                else None
            ),
        }
    except Exception as e:
        logger.error("Mode status error: %s", e)
        return {"ok": False, "mode": "interactive", "error": str(e)}


@router.post("/api/system/mode")
async def set_system_mode(request: Request):
    """실행 모드를 전환합니다 (Interactive/Plan/Build).

    대시보드의 모드 인디케이터 클릭 시 호출됩니다.
    """
    try:
        body = await request.json()
        target_mode = body.get("mode", "").lower()
        reason = body.get("reason", "사용자 수동 전환")

        if target_mode not in ("interactive", "plan", "build"):
            return {"ok": False, "error": f"알 수 없는 모드: {target_mode}. interactive/plan/build 중 하나."}

        from antigravity_k.api.dependencies import get_mode_manager

        mgr = get_mode_manager()
        if target_mode == "plan":
            mgr.switch_to_plan(reason=reason)
        elif target_mode == "build":
            mgr.switch_to_build(reason=reason)
        else:
            mgr.switch_to_interactive(reason=reason)

        logger.info("모드 전환 (수동): %s → %s", target_mode, reason)
        return {
            "ok": True,
            "mode": mgr.current_mode.value,
            "message": f"모드가 {mgr.current_mode.value}(으)로 전환되었습니다.",
        }
    except Exception as e:
        logger.error("Mode switch error: %s", e)
        return {"ok": False, "error": str(e)}


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
            "version": __version__,
        }
    except (psutil.Error, OSError, RuntimeError) as e:
        logger.error("Status error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/search/ab-test/run")
async def run_extraction_ab_test(request: Request):
    """데이터 추출 A/B 테스트를 실행합니다.

    내장 테스트 케이스(BUILTIN_CASES) 전체를 실행하여
    현재 데이터 추출 엔진의 정확도를 측정하고 보고서를 반환합니다.

    Request Body (선택):
        version_label (str): 테스트 버전 레이블 (기본값: "api")

    Returns:
        dict: {
            ok: bool,
            report: ABTestReport.to_dict()
        }
    """
    try:
        from antigravity_k.engine.extraction_ab_test import run_builtin_suite

        body = await request.json()
        version_label = body.get("version_label", "api")

        report = run_builtin_suite(version_label=version_label)
        logger.info("A/B 테스트 완료: %d개 케이스, 정확도 %.1f%%", report.total_cases, report.avg_accuracy)
        return {"ok": True, "report": report.to_dict()}
    except Exception as e:
        logger.error("A/B test error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/system/cache-stats")
@cached(ttl=10, tags=[TAG_SYSTEM])
async def system_cache_stats():
    """API 응답 캐시 통계를 반환합니다 (Phase 28 / Phase 29).

    ApiCache의 엔트리 수, 히트율, 태그 수, 메모리 추정치,
    개별 엔트리 목록(TTL, age, hits)을 반환합니다.

    Returns:
        dict: {
            ok: bool,
            stats: {
                total_entries: int,
                total_tags: int,
                hits: int,
                misses: int,
                hit_ratio: float,
                memory_estimate_kb: float,
                entries: [{key, ttl, age, remaining_ttl, tags, hits}, ...]
            }
        }
    """
    try:
        stats = await api_cache.get_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        logger.error("Cache stats error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/search/cache-stats")
async def search_cache_stats():
    """검색 캐시 통계를 반환합니다.

    WebSearchTool의 SearchCache의 파일 수, 용량, 디렉토리 경로를 반환합니다.
    """
    try:
        from antigravity_k.tools.web_search import SearchCache

        cache = SearchCache()
        stats = cache.get_cache_stats()
        return {"ok": True, "cache_stats": stats}
    except Exception as e:
        logger.error("Cache stats error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/search/pipeline-timing")
async def get_pipeline_timing():
    """파이프라인 단계별 지연 시간 통계를 반환합니다.

    PipelineTimer로부터 검색→추출 파이프라인의 각 단계별
    평균/최소/최대/최근 지연 시간과 최근 기록을 조회합니다.

    Returns:
        dict: {
            ok: bool,
            stats: {
                steps: {step_name: {avg_ms, min_ms, max_ms, count, ...}},
                recent: [{step, duration_ms, timestamp}, ...],
                pipeline_total_avg_ms: float,
            }
        }
    """
    try:
        from antigravity_k.engine.pipeline_timer import PipelineTimer

        stats = PipelineTimer.get_stats()
        return {"ok": True, "stats": stats}
    except Exception as e:
        logger.error("Pipeline timing error: %s", e)
        return {"ok": False, "error": str(e)}


# ─── Log Level Management (Phase 30) ────────────────────────────


@router.get("/api/system/log-level")
async def system_log_level_list():
    """모든 antigravity_k.* 로거의 현재 로그 레벨을 반환합니다.

    LogLevelManager.discover_loggers()를 통해 현재 실행 중인
    모든 로거의 레벨, effective 레벨, 핸들러 수를 조회합니다.
    런타임에 생성되지 않은 KNOWN_LOGGERS도 포함됩니다.

    Returns:
        dict: {
            ok: bool,
            loggers: [{name, level, level_name, effective_level,
                      effective_level_name, handlers}, ...],
            debug_mode: bool,
            count: int
        }
    """
    try:
        loggers = LogLevelManager.discover_loggers()
        debug_mode = LogLevelManager.is_debug_mode()
        return {
            "ok": True,
            "loggers": loggers,
            "debug_mode": debug_mode,
            "count": len(loggers),
        }
    except Exception as e:
        logger.error("Log level list error: %s", e)
        return {"ok": False, "loggers": [], "debug_mode": False, "count": 0, "error": str(e)}


@router.post("/api/system/log-level")
async def system_log_level_set(request: Request):
    """특정 로거의 로그 레벨을 변경합니다.

    로거 이름과 대상 레벨을 지정하여 동적으로 로깅 레벨을 변경합니다.
    서버 재시작 없이 즉시 적용됩니다.

    Request Body:
        name (str): 로거 이름 ("root" 또는 "antigravity_k.api" 등)
        level (str | int): 대상 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    Returns:
        dict: {
            ok: bool,
            result: {name, previous_level, current_level,
                     previous_level_name, current_level_name}
        }
    """
    try:
        body = await request.json()
        logger_name = body.get("name", "")
        level = body.get("level", "INFO")

        if not logger_name:
            return {"ok": False, "error": "name is required"}
        if isinstance(level, str) and level.upper() not in LogLevelManager.LEVEL_NAMES:
            return {"ok": False, "error": f"Invalid level: {level}. Use DEBUG/INFO/WARNING/ERROR/CRITICAL"}

        result = LogLevelManager.set_level(logger_name, level)
        logger.info(
            "Log level changed: %s %s -> %s", logger_name, result["previous_level_name"], result["current_level_name"]
        )
        return {"ok": True, "result": result}
    except Exception as e:
        logger.error("Log level set error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/api/system/log-level/all")
async def system_log_level_set_all(request: Request):
    """모든 antigravity_k.* 로거의 로그 레벨을 한 번에 변경합니다.

    디버깅이 필요할 때 전체 로거를 DEBUG로 변경하거나,
    정리 후 INFO로 복원할 때 유용합니다.

    Request Body:
        level (str | int): 대상 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    Returns:
        dict: {
            ok: bool,
            result: {target_level, target_level_name, updated_count, loggers: [...]}
        }
    """
    try:
        body = await request.json()
        level = body.get("level", "INFO")

        if isinstance(level, str) and level.upper() not in LogLevelManager.LEVEL_NAMES:
            return {"ok": False, "error": f"Invalid level: {level}. Use DEBUG/INFO/WARNING/ERROR/CRITICAL"}

        result = LogLevelManager.set_all_levels(level)
        logger.info("All log levels changed: %s (%d loggers)", result["target_level_name"], result["updated_count"])
        return {"ok": True, "result": result}
    except Exception as e:
        logger.error("Log level set-all error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/api/system/debug-mode")
async def system_debug_mode(request: Request):
    """디버그 모드를 활성화/비활성화합니다.

    디버그 모드가 활성화되면 모든 antigravity_k.* 로거가 DEBUG 레벨로 설정되고,
    비활성화되면 원래 레벨로 복원됩니다.

    Request Body:
        action (str): "enable" 또는 "disable"

    Returns:
        dict: {
            ok: bool,
            debug_mode: bool,
            result: {success, message, updated_count / restored_count}
        }
    """
    try:
        body = await request.json()
        action = body.get("action", "").lower()

        if action == "enable":
            result = LogLevelManager.enable_debug_mode()
        elif action == "disable":
            result = LogLevelManager.disable_debug_mode()
        else:
            return {"ok": False, "error": "action must be 'enable' or 'disable'"}

        logger.info("Debug mode %s: %s", action, result.get("message", ""))
        return {
            "ok": True,
            "debug_mode": LogLevelManager.is_debug_mode(),
            "result": result,
        }
    except Exception as e:
        logger.error("Debug mode error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/api/search/extraction-metrics")
async def get_extraction_metrics():
    """데이터 추출 메트릭 통계를 반환합니다.

    DataExtractor의 ExtractionMetrics 클래스 레벨 카운터로부터
    전체 시스템의 데이터 추출 정확도/성공률을 조회합니다.

    Returns:
        dict: {
            ok: bool,
            metrics: {
                total_calls: int,
                stock_attempts: int,
                stock_success: int,
                weather_attempts: int,
                weather_success: int,
                exchange_attempts: int,
                exchange_success: int,
                date_attempts: int,
                date_found: int,
                errors: int,
                speculative_filtered: int,
                success_rates: {
                    stock: float,
                    weather: float,
                    exchange: float,
                    overall: float
                },
                recent_calls: [...]
            }
        }
    """
    try:
        from antigravity_k.engine.data_extractor import ExtractionMetrics

        stats = ExtractionMetrics.get_stats()
        return {"ok": True, "metrics": stats}
    except Exception as e:
        logger.error("Extraction metrics error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/api/search/extract")
async def search_and_extract(request: Request):
    """검색 실행 + 구조화된 데이터 추출을 한 번에 수행합니다.

    WebSearchTool로 검색하고 DataExtractor로 구조화 데이터(주가, 날씨, 환율, 날짜)를
    추출하여 JSON으로 반환합니다.

    Request Body:
        query (str): 검색 쿼리 (예: "한화에어로스페이스 주가 알려줘")

    Returns:
        dict: {
            ok: bool,
            query: str,
            extracted: {
                stock_prices: [...],
                weather: [...],
                exchange_rates: [...],
                dates_found: [...],
                numeric_data: [...]
            },
            extraction_log: str,  # format_for_llm() 출력
            search_length: int,   # 원시 검색 결과 길이
            has_top1_json: bool,  # TOP 1 JSON 발견 여부
        }
    """
    import asyncio
    import time as _time

    from antigravity_k.engine.data_extractor import DataExtractor
    from antigravity_k.engine.pipeline_timer import PipelineTimer
    from antigravity_k.tools.web_search import WebSearchTool

    body = await request.json()
    query = body.get("query", "")
    if not query or not query.strip():
        return {"ok": False, "error": "query is required"}

    query = query.strip()

    try:
        pipeline_timings: dict[str, float] = {}

        # 1. 검색 실행 (async로 이벤트 루프 차단 방지)
        _t0 = _time.perf_counter()
        tool = WebSearchTool()
        search_res = await asyncio.to_thread(tool.execute, query=query)
        _d = (_time.perf_counter() - _t0) * 1000
        search_length = len(search_res)
        PipelineTimer.record("web_search", _d)
        pipeline_timings["web_search_ms"] = round(_d, 1)

        # 2. TOP 1 JSON 확인
        _t0 = _time.perf_counter()
        extractor = DataExtractor()
        has_top1 = extractor._extract_top1_json(search_res) is not None
        _d = (_time.perf_counter() - _t0) * 1000
        PipelineTimer.record("top1_json", _d)
        pipeline_timings["top1_json_ms"] = round(_d, 1)

        # 3. 데이터 추출
        _t0 = _time.perf_counter()
        result = extractor.extract_all([search_res], query=query)
        _d = (_time.perf_counter() - _t0) * 1000
        PipelineTimer.record("extract_all", _d)
        pipeline_timings["extract_all_ms"] = round(_d, 1)

        # 4. 결과 직렬화
        stock_prices = []
        for sp in result.stock_prices:
            stock_prices.append(
                {
                    "name": sp.name,
                    "ticker": sp.ticker,
                    "close_price": sp.close_price,
                    "open_price": sp.open_price,
                    "high_price": sp.high_price,
                    "low_price": sp.low_price,
                    "change_percent": sp.change_percent,
                    "change_amount": sp.change_amount,
                    "volume": sp.volume,
                }
            )

        weather_list = []
        for w in result.weather:
            weather_list.append(
                {
                    "location": w.location,
                    "temperature": w.temperature,
                    "feels_like": w.feels_like,
                    "humidity": w.humidity,
                    "condition": w.condition,
                }
            )

        exchange_list = []
        for er in result.exchange_rates:
            exchange_list.append(
                {
                    "currency_pair": er.currency_pair,
                    "rate": er.rate,
                    "change_percent": er.change_percent,
                }
            )

        dates_list = result.dates_found

        # 5. LLM 포맷 로그
        _t0 = _time.perf_counter()
        extraction_log = result.format_for_llm()
        _d = (_time.perf_counter() - _t0) * 1000
        PipelineTimer.record("format_for_llm", _d)
        pipeline_timings["format_for_llm_ms"] = round(_d, 1)

        return {
            "ok": True,
            "query": query,
            "search_length": search_length,
            "has_top1_json": has_top1,
            "extracted": {
                "stock_prices": stock_prices,
                "weather": weather_list,
                "exchange_rates": exchange_list,
                "dates_found": dates_list,
            },
            "extraction_log": extraction_log,
            "pipeline_timings": pipeline_timings,
        }

    except Exception as e:
        logger.exception("Search and extract error")
        return {"ok": False, "error": str(e)}


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
    except (OSError, RuntimeError) as e:
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

from antigravity_k.api.routes.legacy import close_unauthorized_ws


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
            logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
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
            logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)

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
    except (json.JSONDecodeError, FileNotFoundError, ValueError, RuntimeError) as e:
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
    except (ValueError, KeyError, RuntimeError) as e:
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
    except (ValueError, KeyError, RuntimeError) as e:
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
