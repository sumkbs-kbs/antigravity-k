"""Orchestrator setup/initialization logic.

오케스트레이터의 각 컴포넌트를 초기화하는 함수들을 제공합니다.
"""

import logging

logger = logging.getLogger("antigravity_k.orchestrator.setup")

# ─── Planning Mode fallback prompt (ArtifactEngine 미사용 시) ──────────

PLANNING_MODE_BLOCK = (
    "\n\n[CRITICAL ALGORITHM OVERRIDE: PLANNING MODE]\n"
    "You are executing a COMPLEX task or requested to plan. You MUST enter PLANNING MODE.\n"
    "1. DO NOT write functional code yet. Research and plan first.\n"
    "2. Create `implementation_plan.md` outlining your technical plan.\n"
    "3. After approval, create a `task.md` with a checkbox list.\n"
    "4. After completion, create a `walkthrough.md` summarizing the changes.\n"
)


def load_agent_models(config: dict) -> dict[str, str]:
    """Config dict에서 역할별 모델 매핑을 추출합니다."""
    return config.get("agent_models", {})


def create_state_graph():
    """State Graph 엔진을 초기화합니다."""
    try:
        from antigravity_k.engine.orchestrator_handlers import build_orchestrator_graph

        graph = build_orchestrator_graph()
        logger.info("[Orchestrator] State Graph 엔진 활성화 완료")
        return graph
    except Exception:
        logger.exception("[Orchestrator] State Graph 초기화 실패")
        return None


def create_artifact_engine(project_root: str):
    """Artifact Engine을 초기화합니다."""
    try:
        from antigravity_k.engine.artifact_engine import ArtifactEngine

        engine = ArtifactEngine(project_root)
        logger.info("[Orchestrator] Artifact Engine 활성화 완료")
        return engine
    except Exception:
        logger.exception("Failed to initialize ArtifactEngine")
        return None


def create_watchdog(config: dict, project_root: str, manager, vault_engine):
    """AmbientWatchdog을 조건부로 초기화합니다."""
    if not config.get("ambient_partner", {}).get("watchdog_enabled", False):
        return None
    try:
        from antigravity_k.engine.ambient_watchdog import AmbientWatchdog

        watchdog = AmbientWatchdog(project_root, manager, vault_engine)
        watchdog.start()
        return watchdog
    except Exception:
        logger.exception("Failed to start AmbientWatchdog")
        return None


def create_plan_guard_harness(project_root: str):
    """PlanGuard + HarnessEnforcer를 초기화합니다."""
    try:
        from antigravity_k.engine.harness_enforcer import HarnessEnforcer
        from antigravity_k.engine.plan_guard import PlanGuard

        plan_guard = PlanGuard()
        harness = HarnessEnforcer(project_root=project_root, strict_mode=False)
        harness.load_guidelines()
        logger.info("[Orchestrator] PlanGuard + HarnessEnforcer 활성화 완료")
        return plan_guard, harness
    except Exception:
        logger.exception("PlanGuard/Harness init failed")
        return None, None


def create_fact_appender(manager, project_root: str):
    """FactAppender를 초기화합니다."""
    try:
        from antigravity_k.engine.fact_appender import initialize_fact_appender

        appender = initialize_fact_appender(manager, project_root)
        logger.info("[Orchestrator] FactAppender 활성화 완료")
        return appender
    except Exception:
        logger.exception("Failed to initialize FactAppender")
        return None


def create_mode_manager():
    """ModeManager를 초기화합니다."""
    try:
        from antigravity_k.engine.mode_manager import ModeManager

        mgr = ModeManager()
        logger.info("[Orchestrator] ModeManager 활성화 완료 (mode=%s)", mgr.current_mode.value)
        return mgr
    except Exception:
        logger.exception("Failed to initialize ModeManager")
        return None


def create_evolution_coordinator(
    project_root: str,
    model_manager,
    verify_fn,
):
    """Self-Evolution Coordinator를 초기화합니다."""
    try:
        from antigravity_k.engine.self_evolution_coordinator import (
            SelfEvolutionCoordinator,
        )

        coordinator = SelfEvolutionCoordinator(
            project_root=project_root,
            model_manager=model_manager,
            verify_fn=verify_fn,
        )
        logger.info("[Orchestrator] Self-Evolution Coordinator 활성화 완료")
        return coordinator
    except Exception:
        logger.exception("[Orchestrator] Self-Evolution Coordinator 초기화 실패")
        return None
