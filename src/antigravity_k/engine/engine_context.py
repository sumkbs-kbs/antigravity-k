"""Antigravity-K: Engine Context (DI Container).

============================================
Provides a unified context holding initialized services (Singletons/Scoped)
to decouple Orchestrator from direct instantiations.
"""

import logging
import os

import yaml

from antigravity_k.engine.autonomous_learner import AutonomousLearner
from antigravity_k.engine.cognitive_loop import CognitiveLoop
from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.failure_memory import FailureMemory
from antigravity_k.engine.ide_sync import IDEContextManager
from antigravity_k.engine.knowledge import KIEngine
from antigravity_k.engine.memory_provider import (
    BuiltinMemoryProvider,
    EpisodicMemoryProvider,
    MemoryManager,
    WorkingMemoryBuffer,
)
from antigravity_k.engine.mode_manager import ModeManager
from antigravity_k.engine.prompt_builder import PromptBuilder
from antigravity_k.engine.quality_gate import QualityGate
from antigravity_k.engine.session_manager import SessionManager
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.engine.tool_guardrails import (
    ToolCallGuardrailConfig,
    ToolCallGuardrailController,
)
from antigravity_k.engine.uncertainty import UncertaintyEstimator
from antigravity_k.engine.user_model import UserIntentModeler
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.tool_registry import ToolRegistry

logger = logging.getLogger("antigravity_k.engine_context")


class EngineContext:
    """Central context object wiring together all engine subsystems for a session."""

    def __init__(self, model_manager, vault_engine=None, project_root=None, tool_registry=None, session_manager=None):
        """Initialize the EngineContext.

        Args:
            model_manager: model manager.
            vault_engine: vault engine.
            project_root: project root.
            tool_registry: tool registry.
            session_manager: 외부에서 주입받은 SessionManager (작업 1: 인스턴스 통일).
                            None이면 내부에서 새로 생성. chat.py와 동일한 인스턴스를
                            공유해야 단기기억이 끊기지 않음.

        """
        self.model_manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root or os.getcwd()

        # Load Config
        self.config = {}
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = yaml.safe_load(f) or {}

        # Core Tools & Gates
        self.shared_tool_registry = tool_registry is not None
        capability_policy_config = self.config.get("autonomous_capabilities", {})
        self.tool_registry = tool_registry or ToolRegistry(
            project_root=self.project_root,
            capability_policy_config=capability_policy_config,
        )
        self.permission_gate = PermissionGate(project_root=self.project_root)

        # Knowledge & Memory
        self.ki_engine = KIEngine(project_root=self.project_root)
        self.failure_memory = FailureMemory(project_root=self.project_root)

        # Learners & Cognition
        self.autonomous_learner = AutonomousLearner(
            model_manager=model_manager,
            ki_engine=self.ki_engine,
            project_root=self.project_root,
        )
        self.cognitive_loop = CognitiveLoop(
            project_root=self.project_root,
            failure_memory=self.failure_memory,
        )

        # Guardrails & Quality
        guardrail_cfg = self._load_guardrail_config()
        self.tool_guardrail = ToolCallGuardrailController(config=guardrail_cfg)
        self.quality_gate = QualityGate()
        self.uncertainty_estimator = UncertaintyEstimator()

        # Context & Modeling
        self.user_model = UserIntentModeler(project_root=self.project_root)
        self.context_shaper = ContextShaper()
        # 작업 1: 외부 주입 SessionManager 우선 사용 — chat.py와 동일 인스턴스 공유
        self.session_manager = session_manager or SessionManager()

        # 4-Tier Cognitive Memory System + 글로벌 메모리 (P2-3)
        from antigravity_k.engine.memory_provider import GlobalMemoryProvider

        self.memory_manager = MemoryManager()
        self.memory_manager.add_provider(BuiltinMemoryProvider(self.session_manager))
        self.memory_manager.add_provider(EpisodicMemoryProvider(max_episodes=200))
        self.memory_manager.add_provider(WorkingMemoryBuffer(max_turns=20))
        # Cross-Project 글로벌 메모리 — 사용자 선호/패턴 영속화
        self.global_memory = GlobalMemoryProvider()
        self.memory_manager.add_provider(self.global_memory)

        self.skill_loader = SkillLoader(
            project_root=self.project_root,
            capability_policy_config=capability_policy_config,
        )
        self.ide_manager = IDEContextManager()
        self.prompt_builder = PromptBuilder()

        # ─── Mode Manager (Plan/Build/Interactive) ───
        self.mode_manager = ModeManager()

        # ─── Phase 1 D3: PlanGuard + GatePipeline ───
        from antigravity_k.engine.cost_guard import CostGuard
        from antigravity_k.engine.gate_pipeline import GatePipeline, create_default_pipeline
        from antigravity_k.engine.plan_guard import PlanGuard

        self.plan_guard = PlanGuard()

        # CostGuard 인스턴스화 (작업 4: 비용 게이트 활성화)
        # config의 cost 섹션 → 환경변수(.env의 AGK_DAILY_BUDGET_USD 등) 순서로 초기화
        cost_cfg = self.config.get("cost", {}) if isinstance(self.config, dict) else {}

        daily_budget = float(cost_cfg.get("daily_budget_usd") or os.environ.get("AGK_DAILY_BUDGET_USD", "50.0"))
        hourly_limit = int(cost_cfg.get("hourly_action_limit") or os.environ.get("AGK_HOURLY_ACTION_LIMIT", "100"))
        cost_enabled = bool(cost_cfg.get("enabled", True))
        self.cost_guard = CostGuard(
            daily_budget_usd=daily_budget,
            hourly_action_limit=hourly_limit,
            enabled=cost_enabled,
        )

        self.gate_pipeline: GatePipeline = create_default_pipeline(
            guardrails=self.tool_guardrail,
            cost_guard=self.cost_guard,
        )

        self.slash_commands = SlashCommandRegistry(
            tool_registry=self.tool_registry,
            session_manager=self.session_manager,
            context_shaper=self.context_shaper,
            model_manager=model_manager,
            skill_loader=self.skill_loader,
            mode_manager=self.mode_manager,
        )

        self.tool_executor = ToolExecutor(
            tool_registry=self.tool_registry,
            permission_gate=self.permission_gate,
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
            capability_policy_config=capability_policy_config,
            plan_guard=self.plan_guard,
            gate_pipeline=self.gate_pipeline,
        )

        if not self.shared_tool_registry:
            self.tool_executor.register_default_tools()

    def _load_guardrail_config(self) -> ToolCallGuardrailConfig:
        try:
            section = self.config.get("tool_loop_guardrails", {})
            return ToolCallGuardrailConfig.from_config(section)
        except Exception:
            logger.exception("Failed to load guardrail config")
        return ToolCallGuardrailConfig()
