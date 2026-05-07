import logging
import os
from typing import Optional

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.protocol_translator import ProtocolTranslator
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.session_manager import SessionManager
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.embeddings import EmbeddingEngine
from antigravity_k.engine.skill_loader import SkillLoader

logger = logging.getLogger("antigravity_k.api.dependencies")

# Global instances
model_manager: Optional[ModelManager] = None
protocol_translator: Optional[ProtocolTranslator] = None
vault_engine: Optional[VaultEngine] = None

_tool_registry: Optional[ToolRegistry] = None
_skill_loader: Optional[SkillLoader] = None
_context_shaper: Optional[ContextShaper] = None
_session_manager: Optional[SessionManager] = None
_orchestrator: Optional[OrchestratorAgent] = None


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
    global model_manager
    if model_manager is None:
        logger.info("Lazy initializing ModelManager...")
        registry = ModelRegistry("config.yaml")
        model_manager = ModelManager(registry)
    return model_manager


def get_vault_engine() -> Optional[VaultEngine]:
    global vault_engine
    if vault_engine is None:
        vault_path = os.environ.get("ANTIGRAVITY_VAULT_PATH", "./vault_data")
        try:
            vault_engine = VaultEngine(vault_path=vault_path, sync_rag=True)
        except Exception as e:
            logger.warning(f"VaultEngine 초기화 실패 (RAG 비활성): {e}")
            try:
                vault_engine = VaultEngine(vault_path=vault_path, sync_rag=False)
            except Exception as e2:
                logger.error(f"VaultEngine 완전 실패: {e2}")
                return None
    return vault_engine


def get_orchestrator() -> OrchestratorAgent:
    global _orchestrator
    if _orchestrator is None:
        logger.info("Lazy initializing OrchestratorAgent (singleton)...")
        _orchestrator = OrchestratorAgent(
            model_manager=get_model_manager(),
            vault_engine=get_vault_engine(),
        )
    return _orchestrator


def get_translator() -> ProtocolTranslator:
    global protocol_translator
    if protocol_translator is None:
        logger.info("Lazy initializing ProtocolTranslator...")
        protocol_translator = ProtocolTranslator()
    return protocol_translator


def get_embedding_engine() -> EmbeddingEngine:
    engine = EmbeddingEngine()
    engine.initialize()
    return engine
