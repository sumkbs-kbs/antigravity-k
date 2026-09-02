"""FastAPI dependency injection providers (singletons and getters)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from pydantic import TypeAdapter, ValidationError

from antigravity_k.engine.agent_runtime import AgentRuntime
from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.durable_memory import DurableMemoryProvider
from antigravity_k.engine.embeddings import EmbeddingEngine
from antigravity_k.engine.memory_provider import (
    BuiltinMemoryProvider,
    EpisodicMemoryProvider,
    GlobalMemoryProvider,
    MemoryManager,
    WorkingMemoryBuffer,
)
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.project_memory import ProjectMemoryProvider
from antigravity_k.engine.project_memory_paths import project_memory_dir
from antigravity_k.engine.protocol_translator import ProtocolTranslator
from antigravity_k.engine.scheduled_job_service import ScheduledJobService
from antigravity_k.engine.session_manager import SessionManager
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.voice_service import VoiceService
from antigravity_k.tools.tool_registry import ToolRegistry

logger = logging.getLogger("antigravity_k.api.dependencies")

if TYPE_CHECKING:
    from antigravity_k.engine.mode_manager import ModeManager


type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]


@runtime_checkable
class _SlashRegistryLike(Protocol):
    def bind_runtime(self, runtime: AgentRuntime) -> None: ...


@runtime_checkable
class _RuntimeContextLike(Protocol):
    slash_commands: _SlashRegistryLike


_JSON_VALUE_ADAPTER: Final[TypeAdapter[JsonValue]] = TypeAdapter(JsonValue)
_DURABLE_EXPORT_ADAPTER: Final[TypeAdapter[list[dict[str, JsonValue]]]] = TypeAdapter(list[dict[str, JsonValue]])


def _json_object(value: JsonValue | None) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _json_text(value: JsonValue | None) -> str:
    return value if isinstance(value, str) else ""


def _widen_graph_record(record: Mapping[str, object]) -> dict[str, object]:
    widened: dict[str, object] = {}
    for key, value in record.items():
        widened[key] = value
    return widened

# Global instances
model_manager: ModelManager | None = None
protocol_translator: ProtocolTranslator | None = None
vault_engine: VaultEngine | None = None

_tool_registry: ToolRegistry | None = None
_skill_loader: SkillLoader | None = None
_context_shaper: ContextShaper | None = None
_session_manager: SessionManager | None = None
_orchestrator: OrchestratorAgent | None = None
_agent_runtime: AgentRuntime | None = None
_scheduled_job_service: ScheduledJobService | None = None
_voice_service: VoiceService | None = None
_benchmark_harness: BenchmarkHarness | None = None
_memory_manager: MemoryManager | None = None
_mode_manager: ModeManager | None = None


def get_mode_manager() -> ModeManager:
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


get_session_manager = _get_session_manager


def get_memory_manager(project_root: str | None = None) -> MemoryManager:
    global _memory_manager
    root = Path(project_root or os.getcwd()).resolve()
    if _memory_manager is None:
        _memory_manager = MemoryManager(project_root=str(root))
        _memory_manager.add_provider(BuiltinMemoryProvider(_get_session_manager()))
        episodic_dir = project_memory_dir(root) / "episodic"
        _memory_manager.add_provider(EpisodicMemoryProvider(max_episodes=200, persist_dir=str(episodic_dir)))
        _memory_manager.add_provider(WorkingMemoryBuffer(max_turns=20))
        _memory_manager.add_provider(GlobalMemoryProvider())
        _memory_manager.add_provider(ProjectMemoryProvider(root))
        _memory_manager.add_provider(
            DurableMemoryProvider(
                "memory_service",
                _clear_memory_service,
                _export_memory_service,
                _redact_memory_service,
                _retain_memory_service,
            ),
        )
        _memory_manager.add_provider(
            DurableMemoryProvider("wiki", _clear_wiki, _export_wiki, _redact_wiki, _retain_wiki),
        )
        _memory_manager.add_provider(
            DurableMemoryProvider("gbrain", _clear_gbrain, _export_gbrain, _redact_gbrain),
        )
        _memory_manager.add_provider(
            DurableMemoryProvider(
                "project_vector",
                _clear_project_vector,
                _export_project_vector,
                _redact_project_vector,
            ),
        )
        _memory_manager.add_provider(
            DurableMemoryProvider(
                "search_cache",
                _clear_search_cache,
                _export_search_cache,
                _redact_search_cache,
                _retain_search_cache,
            ),
        )
    _memory_manager.bind_project_root(root)
    return _memory_manager


def _clear_memory_service() -> int:
    from antigravity_k.knowledge.memory_service import MemoryService

    return MemoryService().clear_all()


def _clear_wiki() -> int:
    from antigravity_k.knowledge.wiki import LLMWiki

    return LLMWiki().clear_all()


def _clear_gbrain() -> int:
    from antigravity_k.engine.gbrain import global_gbrain

    return global_gbrain.clear_all()


def _clear_project_vector() -> int:
    vector_path = Path.cwd() / ".antigravity" / "vault_data"
    if not vector_path.exists():
        return 0

    from antigravity_k.engine.vector_store import VectorStore

    vector_store = VectorStore(str(vector_path), collection_name="agent_knowledge")
    try:
        return vector_store.clear()
    finally:
        vector_store.close()


def _clear_search_cache() -> int:
    cache_dir = Path.cwd() / "data" / "search_cache"
    if not cache_dir.exists():
        return 0

    deleted = 0
    for cache_file in cache_dir.glob("*.json"):
        cache_file.unlink()
        deleted += 1
    return deleted


def _export_memory_service() -> list[dict[str, JsonValue]]:
    from antigravity_k.knowledge.memory_service import MemoryService

    return _DURABLE_EXPORT_ADAPTER.validate_python(MemoryService().export_all())


def _redact_memory_service() -> int:
    from antigravity_k.knowledge.memory_service import MemoryService

    return MemoryService().redact_all()


def _retain_memory_service(max_age_days: int) -> int:
    from antigravity_k.knowledge.memory_service import MemoryService

    return MemoryService().apply_retention(max_age_days)


def _export_wiki() -> list[dict[str, JsonValue]]:
    from antigravity_k.knowledge.wiki import LLMWiki

    return _DURABLE_EXPORT_ADAPTER.validate_python(LLMWiki().export_all())


def _redact_wiki() -> int:
    from antigravity_k.knowledge.wiki import LLMWiki

    return LLMWiki().redact_all()


def _retain_wiki(max_age_days: int) -> int:
    from antigravity_k.knowledge.wiki import LLMWiki

    return LLMWiki().apply_retention(max_age_days)


def _export_gbrain() -> list[dict[str, JsonValue]]:
    from antigravity_k.engine.gbrain import global_gbrain

    return _DURABLE_EXPORT_ADAPTER.validate_python(
        [_widen_graph_record(record) for record in global_gbrain.export_all()],
    )


def _redact_gbrain() -> int:
    from antigravity_k.engine.gbrain import global_gbrain

    return global_gbrain.redact_all()


def _export_project_vector() -> list[dict[str, JsonValue]]:
    vector_path = Path.cwd() / ".antigravity" / "vault_data"
    if not vector_path.exists():
        return []
    from antigravity_k.engine.vector_store import VectorStore

    vector_store = VectorStore(str(vector_path), collection_name="agent_knowledge")
    try:
        return _DURABLE_EXPORT_ADAPTER.validate_python(
            [_widen_graph_record(record) for record in vector_store.export_all()],
        )
    finally:
        vector_store.close()


def _redact_project_vector() -> int:
    vector_path = Path.cwd() / ".antigravity" / "vault_data"
    if not vector_path.exists():
        return 0
    from antigravity_k.engine.vector_store import VectorStore

    vector_store = VectorStore(str(vector_path), collection_name="agent_knowledge")
    try:
        return vector_store.redact_all()
    finally:
        vector_store.close()


def _export_search_cache() -> list[dict[str, JsonValue]]:
    cache_dir = Path.cwd() / "data" / "search_cache"
    if not cache_dir.exists():
        return []
    records: list[dict[str, JsonValue]] = []
    for cache_file in cache_dir.glob("*.json"):
        try:
            data = _JSON_VALUE_ADAPTER.validate_json(cache_file.read_text(encoding="utf-8"))
            records.append({"file": cache_file.name, "data": data})
        except (OSError, ValidationError):
            continue
    return records


def _redact_search_cache() -> int:
    from antigravity_k.engine.secret_scanner import redact_full

    changed = 0
    for record in _export_search_cache():
        data = json.dumps(record["data"], ensure_ascii=False)
        redacted = redact_full(data)
        if redacted != data:
            cache_file = _json_text(record.get("file"))
            if not cache_file:
                continue
            _ = (Path.cwd() / "data" / "search_cache" / cache_file).write_text(redacted, encoding="utf-8")
            changed += 1
    return changed


def _retain_search_cache(max_age_days: int) -> int:
    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    deleted = 0
    for record in _export_search_cache():
        cached_at = _json_text(_json_object(record.get("data")).get("cached_at"))
        try:
            timestamp = datetime.fromisoformat(cached_at)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            continue
        if timestamp < cutoff:
            try:
                cache_file = _json_text(record.get("file"))
                if not cache_file:
                    continue
                (Path.cwd() / "data" / "search_cache" / cache_file).unlink()
                deleted += 1
            except OSError:
                continue
    return deleted


def __get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(project_root=os.getcwd())
        _ = _tool_registry.auto_discover("antigravity_k.tools")
    return _tool_registry


def get_tool_registry() -> ToolRegistry:
    return __get_tool_registry()


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

        registry = ModelRegistry()
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
            memory_manager=get_memory_manager(),
        )
    return _orchestrator


def get_benchmark_harness() -> BenchmarkHarness:
    global _benchmark_harness
    from antigravity_k.engine.task_runner import get_task_runner

    if _benchmark_harness is None:
        manager = get_model_manager()
        _benchmark_harness = BenchmarkHarness(
            manager,
            task_calibration_updater=manager.router.set_task_calibration,
        )
    _ = _benchmark_harness.bind_task_runner(get_task_runner())
    return _benchmark_harness


def get_agent_runtime() -> AgentRuntime:
    global _agent_runtime
    if _agent_runtime is None:
        from antigravity_k.engine.task_runner import get_task_runner

        task_runner = get_task_runner()
        benchmark_harness = get_benchmark_harness()
        _agent_runtime = AgentRuntime(
            get_orchestrator(),
            task_runner,
            task_outcome_recorder=benchmark_harness.record_task_outcome,
        )
        context_value = vars(_agent_runtime.orchestrator).get("ctx")
        if isinstance(context_value, _RuntimeContextLike):
            ctx = context_value
            ctx.slash_commands.bind_runtime(_agent_runtime)
    return _agent_runtime


def get_scheduled_job_service() -> ScheduledJobService:
    global _scheduled_job_service
    if _scheduled_job_service is None:
        from antigravity_k.engine.scheduled_job_store import ScheduledJobStore
        from antigravity_k.engine.task_runner import get_task_runner

        runtime = get_agent_runtime()
        configured_path = os.environ.get("AGK_JOB_DB_PATH", "").strip()
        db_path = configured_path or get_task_runner().db_path
        _scheduled_job_service = ScheduledJobService(
            ScheduledJobStore(db_path),
            runtime.submit_task,
            runtime.get_task_status,
        )
    return _scheduled_job_service


def get_voice_service() -> VoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service


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


_slash_registry = None


def get_slash_registry():
    """Slash command registry singleton (DI-wired)."""
    global _slash_registry
    if _slash_registry is None:
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        _slash_registry = SlashCommandRegistry(
            tool_registry=__get_tool_registry(),
            session_manager=_get_session_manager(),
            context_shaper=_get_context_shaper(),
            model_manager=get_model_manager(),
            skill_loader=__get_skill_loader(),
            agent_runtime=get_agent_runtime(),
        )
    return _slash_registry
