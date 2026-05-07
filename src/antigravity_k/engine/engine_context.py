"""
Antigravity-K: Engine Context (DI Container)
============================================
Provides a unified context holding initialized services (Singletons/Scoped)
to decouple Orchestrator from direct instantiations.
"""

import os
import yaml
import logging

from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.session_manager import SessionManager
from antigravity_k.engine.ide_sync import IDEContextManager
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.engine.tool_guardrails import (
    ToolCallGuardrailController,
    ToolCallGuardrailConfig,
)
from antigravity_k.engine.knowledge import KIEngine
from antigravity_k.engine.autonomous_learner import AutonomousLearner
from antigravity_k.engine.cognitive_loop import CognitiveLoop
from antigravity_k.engine.quality_gate import QualityGate
from antigravity_k.engine.failure_memory import FailureMemory
from antigravity_k.engine.uncertainty import UncertaintyEstimator
from antigravity_k.engine.user_model import UserIntentModeler
from antigravity_k.engine.prompt_builder import PromptBuilder
from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.engine.memory_provider import (
    MemoryManager,
    BuiltinMemoryProvider,
    EpisodicMemoryProvider,
    WorkingMemoryBuffer,
)

logger = logging.getLogger("antigravity_k.engine_context")


class EngineContext:
    def __init__(
        self, model_manager, vault_engine=None, project_root=None, tool_registry=None
    ):
        self.model_manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root or os.getcwd()

        # Load Config
        self.config = {}
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config.yaml"
        )
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
        self.session_manager = SessionManager()

        # 4-Tier Cognitive Memory System
        self.memory_manager = MemoryManager()
        self.memory_manager.add_provider(BuiltinMemoryProvider(self.session_manager))
        self.memory_manager.add_provider(EpisodicMemoryProvider(max_episodes=200))
        self.memory_manager.add_provider(WorkingMemoryBuffer(max_turns=20))

        self.skill_loader = SkillLoader(
            project_root=self.project_root,
            capability_policy_config=capability_policy_config,
        )
        self.ide_manager = IDEContextManager()
        self.prompt_builder = PromptBuilder()

        self.slash_commands = SlashCommandRegistry(
            tool_registry=self.tool_registry,
            session_manager=self.session_manager,
            context_shaper=self.context_shaper,
            model_manager=model_manager,
            skill_loader=self.skill_loader,
        )

        self.tool_executor = ToolExecutor(
            tool_registry=self.tool_registry,
            permission_gate=self.permission_gate,
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
            capability_policy_config=capability_policy_config,
        )

        if not self.shared_tool_registry:
            self.tool_executor.register_default_tools()

    def _load_guardrail_config(self) -> ToolCallGuardrailConfig:
        try:
            section = self.config.get("tool_loop_guardrails", {})
            return ToolCallGuardrailConfig.from_config(section)
        except Exception as e:
            logger.warning(f"Failed to load guardrail config: {e}")
        return ToolCallGuardrailConfig()
