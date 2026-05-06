import re
import sys


def main():
    file_path = "src/antigravity_k/engine/orchestrator.py"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Imports
    content = re.sub(
        r"from antigravity_k\.engine\.tool_executor import ToolExecutor.*?logger = logging\.getLogger\(\"antigravity_k\.orchestrator\"\)",
        """from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.engine.ceo_analyzer import ceo_analyze as _ceo_analyze_fn
from antigravity_k.engine.autonomous_learner import AutonomousLearner
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.state_graph import StateContext
from antigravity_k.engine.stream_processor import StreamProcessor
from antigravity_k.engine.memory_recorder import MemoryRecorder
from antigravity_k.engine.agent_loop import (
    StepContext, NudgeDetector, ParseErrorGuard,
)

logger = logging.getLogger("antigravity_k.orchestrator")""",
        content,
        flags=re.DOTALL,
    )

    # 2. __init__
    init_target = r"        # 설정 로드(.*?)def _load_guardrail_config"

    init_replacement = """        self.ctx = EngineContext(
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
            tool_registry=tool_registry
        )

        # Shortcut references to keep existing code compatible
        self.config = self.ctx.config
        self.tool_registry = self.ctx.tool_registry
        self.session_manager = self.ctx.session_manager
        self.context_shaper = self.ctx.context_shaper
        self.ki_engine = self.ctx.ki_engine
        self.failure_memory = self.ctx.failure_memory
        self.autonomous_learner = self.ctx.autonomous_learner
        self.cognitive_loop = self.ctx.cognitive_loop
        self.quality_gate = self.ctx.quality_gate
        self.uncertainty_estimator = self.ctx.uncertainty_estimator
        self.user_model = self.ctx.user_model
        self.skill_loader = self.ctx.skill_loader
        self.ide_manager = self.ctx.ide_manager
        self.slash_commands = self.ctx.slash_commands
        self.tool_guardrail = self.ctx.tool_guardrail
        self._tool_executor = self.ctx.tool_executor

        # AmbientWatchdog 초기화
        self.watchdog = None
        if self.config.get("ambient_partner", {}).get("watchdog_enabled", False):
            try:
                from antigravity_k.engine.ambient_watchdog import AmbientWatchdog
                self.watchdog = AmbientWatchdog(self.project_root, self.manager, self.vault_engine)
                self.watchdog.start()
            except Exception as e:
                logger.error(f"Failed to start AmbientWatchdog: {e}")

        # 연속 에러 카운터 (자동 롤백 트리거용)
        self._consecutive_errors = 0

        # 외부 주입 확인 (하위 호환성 유지)
        self._shared_tool_registry = tool_registry is not None

        # ─── State Graph 엔진 (P2 리팩토링) ───
        try:
            from antigravity_k.engine.orchestrator_handlers import build_orchestrator_graph
            self._state_graph = build_orchestrator_graph()
            logger.info("[Orchestrator] State Graph 엔진 활성화 완료")
        except Exception as e:
            logger.warning(f"[Orchestrator] State Graph 초기화 실패: {e}")
            self._state_graph = None

        # 세션 자동 시작 (프로젝트별 대화 영속성)
        try:
            self.session_manager.start_session(project_path=self.project_root)
        except Exception as e:
            logger.warning(f"Session start failed: {e}")

    def _load_guardrail_config"""

    content = re.sub(init_target, init_replacement, content, flags=re.DOTALL)

    # 3. Delete _load_guardrail_config and _register_claw_tools (already gone? wait, _register_claw_tools is in __init__. Let's remove _load_guardrail_config entirely)
    content = re.sub(
        r"    def _load_guardrail_config.*?def _get_model_for_role",
        "    def _get_model_for_role",
        content,
        flags=re.DOTALL,
    )

    # 4. Replace _run_pipeline, _run_debate, run_stream, run_sync
    run_stream_target = r"    def _run_pipeline(.*)"

    run_stream_replacement = """    def run_stream(self, messages: List[Dict[str, str]], target_model: str, max_steps: int = 15, ephemeral_message: Optional[str] = None) -> Generator[str, None, None]:
        \"\"\"
        State Graph 기반 멀티 에이전트 스트리밍 실행.

        기존의 레거시 선형 루프를 완전히 폐기하고,
        내부를 명시적 상태 전이 그래프(AgentStateGraph)로 단일화하여 실행합니다.
        \"\"\"
        if not self._state_graph:
            # Fallback to building the graph if not initialized
            from antigravity_k.engine.orchestrator_handlers import build_orchestrator_graph
            self._state_graph = build_orchestrator_graph()

        ctx = StateContext(
            messages=messages,
            target_model=target_model,
            max_steps=max_steps,
            ephemeral_message=ephemeral_message,
        )

        logger.info(f"[Orchestrator] State Graph 실행 시작 (trace_id={ctx.trace_id})")

        yield from self._state_graph.execute(ctx, orchestrator=self)

        # 에이전트 출력 동기화
        if ctx.agent_output:
            self._last_agent_output = ctx.agent_output

        logger.info(
            f"[Orchestrator] State Graph 완료: {ctx.current_state.value}, "
            f"{len(ctx.state_history)}개 전이, {ctx.get_duration_ms():.0f}ms"
        )

    def run_sync(self, messages: List[Dict[str, str]], target_model: str, max_steps: int = 15) -> str:
        \"\"\"동기식 실행 (커맨드 팔레트 등에서 사용).\"\"\"
        result = []
        for chunk in self.run_stream(messages, target_model, max_steps):
            result.append(chunk)
        return "".join(result)
"""
    content = re.sub(
        run_stream_target, run_stream_replacement, content, flags=re.DOTALL
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Refactoring complete.")


if __name__ == "__main__":
    main()
