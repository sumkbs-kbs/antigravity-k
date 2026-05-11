"""
Antigravity-K: CEO 기반 멀티 에이전트 오케스트레이터
====================================================
사용자 명령 → CEO 접수/분석 → 역할별 위임 → 결과 종합 → 스트리밍 응답

핵심 구조:
  1) CEO가 태스크 유형을 판별 (simple_chat / coding / reasoning / complex)
  2) 유형에 따라 최적의 역할(WORKER, ENG_MANAGER 등)과 모델을 자동 매핑
  3) 위임된 에이전트가 실제 작업 수행 (도구 호출 포함)
  4) CEO가 최종 결과를 종합하여 사용자에게 스트리밍
"""

from ui.prompts import PLANNING_MODE_BLOCK
import os
import re
from typing import List, Dict, Any, Generator, Optional, Union

from antigravity_k.engine.ceo_analyzer import ceo_analyze as _ceo_analyze_fn
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.state_graph import StateContext
from antigravity_k.engine.memory_recorder import MemoryRecorder
from antigravity_k.engine.capacity_flow import CapacityCheckpoint
from antigravity_k.agents.personas import get_orchestrator_prompt

from antigravity_k.engine.logging_util import get_structured_logger
logger = get_structured_logger("antigravity_k.orchestrator")

# ─── 역할별 시스템 프롬프트 ─────────────────────────────────────────
# Single Source of Truth: agents/personas.py
# get_orchestrator_prompt(role) 를 사용합니다.


def _load_agent_models(config: dict) -> Dict[str, str]:
    """config dict에서 역할별 모델 매핑을 추출합니다."""
    return config.get("agent_models", {})


class OrchestratorAgent:
    """
    CEO 기반 멀티 에이전트 오케스트레이터.

    사용자 명령 흐름:
    1. CEO 분석 (빠른 모델) → 태스크 유형 판별
    2. 역할별 모델 위임 → 전문 에이전트 실행
    3. 도구 호출 (ReAct 루프) → 실제 작업 수행
    4. 결과 스트리밍 → 대시보드 표시
    """

    def __init__(
        self, model_manager, vault_engine=None, project_root=None, tool_registry=None
    ):
        self.manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root or os.getcwd()

        self.ctx = EngineContext(
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
            tool_registry=tool_registry,
        )

        # Shortcut references to keep existing code compatible
        self.config = self.ctx.config
        self.agent_models = _load_agent_models(self.config)
        self.tool_registry = self.ctx.tool_registry
        self.session_manager = self.ctx.session_manager
        self.context_shaper = self.ctx.context_shaper

        self._memory_recorder = MemoryRecorder(
            self.vault_engine, self.manager, self._get_model_for_role
        )

        # Capacity Flow 가드레일 (DeepSeek-TUI 패턴 이식)
        self._capacity_checkpoint = CapacityCheckpoint()

        # AmbientWatchdog 초기화
        self.watchdog = None
        if self.config.get("ambient_partner", {}).get("watchdog_enabled", False):
            try:
                from antigravity_k.engine.ambient_watchdog import AmbientWatchdog

                self.watchdog = AmbientWatchdog(
                    self.project_root, self.manager, self.vault_engine
                )
                self.watchdog.start()
            except Exception as e:
                logger.error(f"Failed to start AmbientWatchdog: {e}")

        # 연속 에러 카운터 (자동 롤백 트리거용)
        self.ctx.tool_executor.reset_error_counter()

        # 외부 주입 확인 (하위 호환성 유지)
        self._shared_tool_registry = tool_registry is not None

        # ─── State Graph 엔진 (P2 리팩토링) ───
        try:
            from antigravity_k.engine.orchestrator_handlers import (
                build_orchestrator_graph,
            )

            self._state_graph = build_orchestrator_graph()
            logger.info("[Orchestrator] State Graph 엔진 활성화 완료")
        except Exception as e:
            logger.warning(f"[Orchestrator] State Graph 초기화 실패: {e}")
            self._state_graph = None

        # Artifact Engine 초기화
        try:
            from antigravity_k.engine.artifact_engine import ArtifactEngine
            self.artifact_engine = ArtifactEngine(self.project_root)
            logger.info("[Orchestrator] Artifact Engine 활성화 완료")
        except Exception as e:
            logger.warning(f"Failed to initialize ArtifactEngine: {e}")

        # 상태 추적 초기화
        self._last_agent_output = ""

        # ─── Lazy-init Heavy Components ───
        # SkillAutoLearner와 TrajectoryCompressor는 실제 사용 시점에 초기화됩니다.
        # (시작 시간과 메모리 절약)
        self._skill_auto_learner_initialized = False
        self._skill_auto_learner_instance = None
        self._trajectory_compressor_initialized = False
        self._trajectory_compressor_instance = None

        # 세션 자동 시작 (프로젝트별 대화 영속성)
        try:
            self.session_manager.start_session(project_path=self.project_root)
        except Exception as e:
            logger.warning(f"Session start failed: {e}")

        # ─── PlanGuard + HarnessEnforcer (바이브코딩 + 하네스 엔지니어링) ───
        try:
            from antigravity_k.engine.plan_guard import PlanGuard
            from antigravity_k.engine.harness_enforcer import HarnessEnforcer

            self.plan_guard = PlanGuard()
            self.harness = HarnessEnforcer(
                project_root=self.project_root,
                strict_mode=False,
            )
            self.harness.load_guidelines()
            logger.info("[Orchestrator] PlanGuard + HarnessEnforcer 활성화 완료")
        except Exception as e:
            logger.warning(f"PlanGuard/Harness init failed: {e}")
            self.plan_guard = None
            self.harness = None

        # Fact Appender 초기화 (ALDA LLM Wiki 기능)
        try:
            from antigravity_k.engine.fact_appender import initialize_fact_appender

            self.fact_appender = initialize_fact_appender(
                self.manager, self.project_root
            )
            logger.info("[Orchestrator] FactAppender 활성화 완료")
        except Exception as e:
            logger.warning(f"Failed to initialize FactAppender: {e}")

    def _get_model_for_role(self, role: str) -> str:
        """역할에 맞는 모델을 반환합니다. config.yaml 매핑 우선."""
        return self.agent_models.get(
            role, self.agent_models.get("default", "qwen3.6:latest")
        )

    @property
    def skill_auto_learner(self):
        """SkillAutoLearner 지연 초기화 (첫 접근 시 생성)."""
        if not self._skill_auto_learner_initialized:
            self._skill_auto_learner_initialized = True
            try:
                from antigravity_k.engine.skill_auto_learner import SkillAutoLearner

                self._skill_auto_learner_instance = SkillAutoLearner(
                    self.project_root, self.manager
                )
                logger.info(
                    "[Orchestrator] SkillAutoLearner (Closed Learning Loop) 활성화 완료"
                )
            except Exception as e:
                logger.warning(f"SkillAutoLearner init failed: {e}")
                self._skill_auto_learner_instance = None
        return self._skill_auto_learner_instance

    @property
    def trajectory_compressor(self):
        """TrajectoryCompressor 지연 초기화 (첫 접근 시 생성)."""
        if not self._trajectory_compressor_initialized:
            self._trajectory_compressor_initialized = True
            try:
                from antigravity_k.engine.trajectory_compressor import (
                    TrajectoryCompressor,
                )

                summarize_fn = None
                if self.manager:

                    def _summarize(prompt: str) -> str:
                        default_m = self.manager.config.get("defaults", {}).get(
                            "reasoning", "qwen3.6:latest"
                        )
                        return self.manager.generate(
                            prompt=prompt, target=default_m, max_tokens=512
                        )

                    summarize_fn = _summarize
                self._trajectory_compressor_instance = TrajectoryCompressor(
                    summarize_fn=summarize_fn
                )
                logger.info("[Orchestrator] TrajectoryCompressor 활성화 완료")
            except Exception as e:
                logger.warning(f"TrajectoryCompressor init failed: {e}")
                self._trajectory_compressor_instance = None
        return self._trajectory_compressor_instance

    def _build_tool_prompt(self) -> str:
        """도구 목록을 프롬프트에 주입합니다. few-shot 예시 포함."""
        tool_section = (
            "## Tool Usage Instructions\n"
            "You are a function calling AI model. You may call one or more functions to assist with the user query.\n"
            "Don't make assumptions about what values to plug into functions.\n"
            "To use a tool, you MUST use the <scratch_pad> XML tags to record your reasoning and planning before you call the function.\n\n"
            "<scratch_pad>\n"
            "Goal: <state task assigned by user>\n"
            "Actions: <describe what tools you will call>\n"
            "Observation: <set observation 'None' if you haven't called yet, or summarize previous tool results>\n"
            "Reflection: <evaluate if tools are relevant and if you have all required parameters>\n"
            "</scratch_pad>\n\n"
            "After the scratch_pad, output a JSON block wrapped in XML tags exactly like this:\n"
            "<tool_call>\n"
            '{"name": "tool_name", "arguments": {"arg1": "value1"}}\n'
            "</tool_call>\n\n"
            "CRITICAL RULES:\n"
            "- You can output MULTIPLE tool_call blocks sequentially if they can be executed in parallel.\n"
            "- Wait for ALL <tool_response> tags before making another batch of tool calls.\n"
            "- If no tool is needed, just answer directly without any tool_call or scratch_pad tags.\n"
            "OUTPUT QUALITY GATES:\n"
            "1. You MUST include Korean explanations even when asked for code. Do not just output code blocks.\n"
            "2. Provide Big-O notation (Time/Space complexity) for algorithmic tasks.\n"
            "3. Provide reasoning for your technical choices before or after code blocks.\n"
            "4. Use Markdown Tables when comparing 3 or more methods.\n"
            "5. Never repeat the same paragraph twice.\n\n"
            "### Example Usage:\n"
            "User: Show me the contents of main.py\n"
            "Assistant: \n"
            "<scratch_pad>\n"
            "Goal: Read the contents of main.py to answer the user.\n"
            "Actions: I will call read_file tool on main.py.\n"
            "Observation: None\n"
            "Reflection: I have the required file path. Ready to call.\n"
            "</scratch_pad>\n"
            "<tool_call>\n"
            '{"name": "read_file", "arguments": {"file_path": "main.py"}}\n'
            "</tool_call>\n\n"
            "## Available Tools\n"
        )
        if hasattr(self.tool_registry, "render_autonomous_policy"):
            tool_section += "\n" + self.tool_registry.render_autonomous_policy() + "\n"
        try:
            from antigravity_k.engine.codex_transfer import CodexTransferEngine

            tool_section += "\n" + CodexTransferEngine().render_prompt_contract() + "\n"
        except Exception as e:
            logger.debug(f"Codex operating contract unavailable: {e}")
        try:
            from antigravity_k.engine.self_capability import SelfCapabilityEngine

            engine = SelfCapabilityEngine()
            snapshot = engine.build(
                tool_registry=self.tool_registry,
                skill_loader=self.ctx.skill_loader,
                model_manager=self.manager,
                project_root=self.project_root,
                slash_commands=getattr(self.ctx.slash_commands, "_commands", {}),
            )
            tool_section += "\n" + engine.render_prompt_contract(snapshot) + "\n"
        except Exception as e:
            logger.debug(f"Self-capability contract unavailable: {e}")
        for schema in self.tool_registry.to_llm_schemas():
            params = schema.get("input_schema", {})
            required = params.get("required") or []
            tool_section += f"- **{schema['name']}**: {schema['description']}\n"
            props = params.get("properties") or {}
            if props:
                param_strs = []
                for k, v in props.items():
                    p_type = v.get("type", "any")
                    p_req = "required" if k in required else "optional"
                    param_strs.append(f"{k} ({p_type}, {p_req})")
                tool_section += f"  Parameters: {', '.join(param_strs)}\n"
        return tool_section

    def _requires_planning_mode(
        self, task_type: str, messages: List[Dict[str, str]]
    ) -> bool:
        """복잡한 구조 변경에만 Planning Mode를 강제합니다."""
        if task_type == "complex":
            return True
        if task_type != "coding":
            return False

        request_text = "\n".join(
            str(msg.get("content", "")) for msg in messages if msg.get("role") == "user"
        ).lower()
        return bool(
            re.search(
                r"(아키텍처|구조|전면|대규모|마이그레이션|프레임워크|리팩토링|"
                r"architecture|refactor|migrate|framework|plugin system)",
                request_text,
            )
        )

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """ToolExecutor에 위임합니다. (I-1 리팩터링)"""
        return self.ctx.tool_executor.execute(name, args)

    def _latest_user_text(self, messages: List[Dict[str, str]]) -> str:
        """최근 user 메시지의 텍스트만 반환합니다."""
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                return " ".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ).strip()
        return ""

    def _render_self_capability_response(self) -> str:
        """런타임 사실 기반 자기 능력 보고서를 생성합니다."""
        from antigravity_k.engine.self_capability import SelfCapabilityEngine

        engine = SelfCapabilityEngine()
        snapshot = engine.build(
            tool_registry=self.tool_registry,
            skill_loader=self.ctx.skill_loader,
            model_manager=self.manager,
            project_root=self.project_root,
            slash_commands=getattr(self.ctx.slash_commands, "_commands", {}),
        )
        return engine.render_markdown(snapshot)

    def _register_claw_tools(self):
        """ToolExecutor에 위임합니다. (I-1 리팩터링)"""
        self.ctx.tool_executor.register_default_tools()

    # ─── CEO 분석 단계 ─────────────────────────────────────────────────

    def _ceo_analyze(
        self, user_message: str, target_model: str
    ) -> Generator[Union[str, dict], None, None]:
        """CEO 분석을 ceo_analyzer 모듈에 위임합니다. (I-1 리팩터링)"""
        yield from _ceo_analyze_fn(
            user_message=user_message,
            target_model=target_model,
            ceo_prompt_template=get_orchestrator_prompt("CEO"),
            model_manager=self.manager,
        )

    def _rebuild_prompt(
        self,
        system_prompt: str,
        tool_prompt: str,
        skill_prompts: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """컨텍스트 압축 후 프롬프트를 재구성합니다."""
        prompt = f"System: {system_prompt}\n{skill_prompts}\n"
        if tool_prompt:
            prompt += f"\n{tool_prompt}\n"
        prompt += "\n"
        for msg in messages:
            prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
        prompt += "Assistant: "
        return prompt

    def _prepare_agent_prompt(
        self,
        messages: List[Dict[str, str]],
        delegate_to: str,
        task_type: str,
    ) -> tuple:
        """에이전트 실행에 필요한 프롬프트와 컨텍스트를 준비합니다.

        Returns:
            (delegate_model, system_prompt, tool_prompt, skill_prompts,
             prompt, shaped_messages)
        """
        delegate_model = self._get_model_for_role(delegate_to)
        system_prompt = get_orchestrator_prompt(delegate_to)

        # [Phase 17] 복합/대규모 태스크인 경우 Planning Mode 워크플로우 강제 주입
        if self._requires_planning_mode(task_type, messages) and delegate_to != "CEO":
            if hasattr(self, "artifact_engine"):
                planning_mode_enforcement = (
                    self.artifact_engine.inject_planning_prompt()
                )
            else:
                planning_mode_enforcement = PLANNING_MODE_BLOCK
            system_prompt += planning_mode_enforcement

        tool_prompt = self._build_tool_prompt() if delegate_to != "CEO" else ""

        # 턴 시작 시 에러 카운터 리셋 (이전 턴의 에러가 이월되지 않도록)
        self.ctx.tool_executor.reset_error_counter()
        user_objective = messages[-1].get("content", "") if messages else ""
        if hasattr(self.ctx.tool_executor, "set_objective"):
            self.ctx.tool_executor.set_objective(user_objective)

        # ─── E-1: 인지 루프 초기화 ───
        if self.ctx.cognitive_loop:
            self.ctx.cognitive_loop.reset()
        if self.ctx.quality_gate:
            self.ctx.quality_gate.reset()

        # ─── E-3: 실패 학습 컨텍스트 주입 ───
        failure_context = ""

        # Skill injection
        skill_prompts = (
            self.ctx.skill_loader.get_active_prompts()
            if hasattr(self, "skill_loader")
            else ""
        )

        # IDE Context injection
        ide_prompt = self.ctx.ide_manager.format_prompt()
        if ide_prompt:
            skill_prompts += "\n" + ide_prompt

        prompt = f"System: {system_prompt}\n{skill_prompts}\n"
        if failure_context:
            prompt += f"\n{failure_context}\n"
        if tool_prompt:
            prompt += f"\n{tool_prompt}\n"
        prompt += "\n"

        # ─── Context Shaper 적용 (컨텍스트 압축 시스템) ───
        shaped_messages = self.context_shaper.shape(messages)

        # ─── Tool Result Clearing (Anthropic Context Editing) ───
        shaped_messages = self.context_shaper.clear_old_tool_results(shaped_messages)

        # ─── Decision Anchor 주입 (Anthropic 컨텍스트 엔지니어링) ───
        if hasattr(self.ctx, "decision_anchor"):
            shaped_messages = self.ctx.decision_anchor.inject_into_messages(
                shaped_messages
            )

        # ─── Budget Awareness 주입 (Anthropic Context Awareness) ───
        shaped_messages = self.context_shaper.inject_budget_awareness(shaped_messages)

        for msg in shaped_messages:
            prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
        prompt += "Assistant: "

        return (
            delegate_model,
            system_prompt,
            tool_prompt,
            skill_prompts,
            prompt,
            shaped_messages,
        )

    def run_stream(
        self,
        messages: List[Dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        State Graph 기반 멀티 에이전트 스트리밍 실행.

        기존의 레거시 선형 루프를 완전히 폐기하고,
        내부를 명시적 상태 전이 그래프(AgentStateGraph)로 단일화하여 실행합니다.
        """
        try:
            from antigravity_k.engine.self_capability import (
                is_self_capability_request,
            )

            if is_self_capability_request(self._latest_user_text(messages)):
                response = self._render_self_capability_response()
                self._last_agent_output = response
                yield response
                return
        except Exception as e:
            logger.debug(f"Self-capability fast path skipped: {e}")

        if not self._state_graph:
            # Fallback to building the graph if not initialized
            from antigravity_k.engine.orchestrator_handlers import (
                build_orchestrator_graph,
            )

            self._state_graph = build_orchestrator_graph()

        # Memory Prefetch: 대화 시작 전 관련 기억 주입
        try:
            user_text = self._latest_user_text(messages)

            # --- Hermes Synergy: Preflight Validator ---
            from antigravity_k.engine.preflight_validator import PreflightValidator
            from antigravity_k.engine.engine_profile import (
                EngineProfile,
            )

            validator = PreflightValidator(self.model_manager)
            is_valid, reject_reason, profile = validator.validate(user_text)
            if not is_valid:
                yield f"✈️ [Preflight 거부]\n{reject_reason}"
                return

            if profile == EngineProfile.FAST_PROTOTYPER:
                yield "🚀 [FAST_PROTOTYPER 모드] 엄격한 검증을 생략하고 빠른 구축을 시작합니다...\n\n"
            else:
                yield "🛡️ [STRICT_ENGINEER 모드] 정밀한 엔지니어링 및 44단계 검증 프로세스를 시작합니다...\n\n"
            # -------------------------------------------

            recalled = self.ctx.memory_manager.prefetch_all(user_text)
            if recalled:
                messages = list(messages)  # 원본 불변
                messages.insert(
                    1 if len(messages) > 1 else 0,
                    {"role": "system", "content": f"[Recalled Memory]\n{recalled}"},
                )
        except Exception as e:
            logger.debug(f"Memory prefetch error: {e}")

        # ─── Trajectory Compressor: 대화 궤적 압축 체크포인트 ───
        try:
            if (
                self.trajectory_compressor
                and self.trajectory_compressor.should_compress(messages)
            ):
                result = self.trajectory_compressor.compress(messages)
                messages = result.compressed_messages
                yield f"\n{result.user_message}\n\n"
                logger.info(f"[Orchestrator] {result.user_message}")
        except Exception as e:
            logger.debug(f"Trajectory compression error: {e}")

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
            # Memory Sync: 턴 완료 후 모든 메모리 제공자에 동기화
            try:
                self.ctx.memory_manager.sync_all(
                    self._latest_user_text(messages),
                    ctx.agent_output,
                )
            except Exception as e:
                logger.debug(f"Memory sync error: {e}")

        logger.info(
            f"[Orchestrator] State Graph 완료: {ctx.current_state.value}, "
            f"{len(ctx.state_history)}개 전이, {ctx.get_duration_ms():.0f}ms"
        )

    def run_sync(
        self, messages: List[Dict[str, str]], target_model: str, max_steps: int = 15
    ) -> str:
        """동기식 실행 (커맨드 팔레트 등에서 사용)."""
        result = []
        for chunk in self.run_stream(messages, target_model, max_steps):
            result.append(chunk)
        return "".join(result)
