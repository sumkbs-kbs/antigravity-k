"""Dependencies module."""

import logging
import os
from typing import Any

from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.embeddings import EmbeddingEngine
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.protocol_translator import ProtocolTranslator
from antigravity_k.engine.session_manager import SessionManager
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.tools.tool_registry import ToolRegistry

logger = logging.getLogger("antigravity_k.api.dependencies")

# Global instances
model_manager: ModelManager | None = None
protocol_translator: ProtocolTranslator | None = None
vault_engine: VaultEngine | None = None

_tool_registry: ToolRegistry | None = None
_skill_loader: SkillLoader | None = None
_context_shaper: ContextShaper | None = None
_session_manager: SessionManager | None = None
_orchestrator: OrchestratorAgent | None = None
_mode_manager: Any | None = None


def get_mode_manager():
    """ModeManager 싱글톤을 반환합니다.

    Phase 1 D7: Dashboard WebSocket이 실제 실행 모드를 조회하기 위해 사용.
    EngineContext.mode_manager와 동일한 인스턴스를 공유합니다.
    """
    global _mode_manager
    if _mode_manager is None:
        from antigravity_k.engine.mode_manager import ModeManager

        _mode_manager = ModeManager()
        logger.info("Lazy initializing ModeManager (singleton)...")
    return _mode_manager


def _get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def __get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(project_root=os.getcwd())
        _tool_registry.auto_discover("antigravity_k.tools")
    return _tool_registry


def __get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader(project_root=os.getcwd())
    return _skill_loader


def _get_context_shaper() -> ContextShaper:
    global _context_shaper
    if _context_shaper is None:
        _context_shaper = ContextShaper()
    return _context_shaper


def get_model_manager() -> ModelManager:
    """Retrieve model manager.

    Returns:
        ModelManager: The modelmanager result.

    """
    global model_manager
    if model_manager is None:
        logger.info("Lazy initializing ModelManager...")
        from antigravity_k.engine.usage_tracker import UsageTracker

        registry = ModelRegistry("config.yaml")
        tracker = UsageTracker(db_path="data/token_usage.json")
        model_manager = ModelManager(registry, tracker=tracker)
    return model_manager


def get_vault_engine() -> VaultEngine | None:
    """Retrieve vault engine.

    Returns:
        VaultEngine | None: The vaultengine | none result.

    """
    global vault_engine
    if vault_engine is None:
        vault_path = os.environ.get("ANTIGRAVITY_VAULT_PATH", "./vault_data")
        try:
            vault_engine = VaultEngine(vault_path=vault_path, sync_rag=True)
        except (OSError, RuntimeError, ValueError) as e:
            logger.warning("VaultEngine 초기화 실패 (RAG 비활성): %s", e)
            try:
                vault_engine = VaultEngine(vault_path=vault_path, sync_rag=False)
            except OSError:
                logger.exception("VaultEngine 완전 실패")
                return None
    return vault_engine


def get_orchestrator() -> OrchestratorAgent:
    """Retrieve orchestrator.

    Returns:
        OrchestratorAgent: The orchestratoragent result.

    """
    global _orchestrator
    if _orchestrator is None:
        logger.info("Lazy initializing OrchestratorAgent (singleton)...")
        _orchestrator = OrchestratorAgent(
            model_manager=get_model_manager(),
            vault_engine=get_vault_engine(),
            session_manager=_get_session_manager(),  # 작업 1: 인스턴스 통일
        )
    return _orchestrator


def get_translator() -> ProtocolTranslator:
    """Retrieve translator.

    Returns:
        ProtocolTranslator: The protocoltranslator result.

    """
    global protocol_translator
    if protocol_translator is None:
        logger.info("Lazy initializing ProtocolTranslator...")
        protocol_translator = ProtocolTranslator()
    return protocol_translator


def get_embedding_engine() -> EmbeddingEngine:
    """Retrieve embedding engine.

    Returns:
        EmbeddingEngine: The embeddingengine result.

    """
    engine = EmbeddingEngine()
    engine.initialize()
    return engine
