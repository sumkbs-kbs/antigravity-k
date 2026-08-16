"""OrchestratorAgent — CEO 기반 멀티 에이전트 오케스트레이터 클래스."""

import logging
import os
import re
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from antigravity_k.agents.personas import get_orchestrator_prompt
from antigravity_k.engine.capacity_flow import CapacityCheckpoint
from antigravity_k.engine.ceo_analyzer import ceo_analyze as _ceo_analyze_fn
from antigravity_k.engine.context_budget import context_budget_for_model
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.memory_provider import MemoryManager
from antigravity_k.engine.memory_recorder import MemoryRecorder
from antigravity_k.engine.orchestrator.setup import (
    PLANNING_MODE_BLOCK,
    create_artifact_engine,
    create_evolution_coordinator,
    create_fact_appender,
    create_plan_guard_harness,
    create_state_graph,
    create_watchdog,
    load_agent_models,
)
from antigravity_k.engine.task_state_store import (
    TaskExecutionContext,
    TaskStateStore,
    bind_task_execution_context,
)

logger = logging.getLogger("antigravity_k.orchestrator")


class OrchestratorAgent:
    """CEO 기반 멀티 에이전트 오케스트레이터.

    사용자 명령 흐름:
    1. CEO 분석 (빠른 모델) → 태스크 유형 판별
    2. 역할별 모델 위임 → 전문 에이전트 실행
    3. 도구 호출 (ReAct 루프) → 실제 작업 수행
    4. 결과 스트리밍 → 대시보드 표시
    """

    def __init__(
        self,
        model_manager,
        vault_engine=None,
        project_root=None,
        tool_registry=None,
        session_manager=None,
        memory_manager: MemoryManager | None = None,
    ):
        """Initialize the OrchestratorAgent.

        Args:
            model_manager: model manager.
            vault_engine: vault engine.
            project_root: project root.
            tool_registry: tool registry.
            session_manager: 외부 SessionManager (작업 1: chat.py와 인스턴스 통일).

        """
        self.manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root or os.getcwd()

        self.ctx = EngineContext(
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
            tool_registry=tool_registry,
            session_manager=session_manager,
            memory_manager=memory_manager,
        )

        # Shortcut references
        self.config = self.ctx.config
        self.agent_models = load_agent_models(self.config)
        self.tool_registry = self.ctx.tool_registry
        self.session_manager = self.ctx.session_manager
        self.context_shaper = self.ctx.context_shaper

        self._memory_recorder = MemoryRecorder(
            self.vault_engine,
            self.manager,
            self._get_model_for_role,
        )

        # Capacity Flow 가드레일
        self._capacity_checkpoint = CapacityCheckpoint()

        # ─── Mode Manager (Plan/Build/Interactive) ───
        self.mode_manager = self.ctx.mode_manager

        # ─── Setup: Optional Components ───
        self.watchdog = create_watchdog(
            self.config,
            self.project_root,
            self.manager,
            self.vault_engine,
        )
        self._state_graph = create_state_graph()
        self.artifact_engine = create_artifact_engine(self.project_root)
        self.plan_guard, self.harness = create_plan_guard_harness(self.project_root)
        self.fact_appender = create_fact_appender(self.manager, self.project_root)

        # ─── Self-Evolution Coordinator ───
        self._evolution_coordinator = self._init_evolution_coordinator()

        # 연속 에러 카운터
        self.ctx.tool_executor.reset_error_counter()
        self._shared_tool_registry = tool_registry is not None

        # 상태 추적
        self._last_agent_output = ""
        self._task_execution_context: ContextVar[TaskExecutionContext | None] = ContextVar(
            "task_execution_context",
            default=None,
        )

        # ─── Freebuff-Style Proactive: Code Tree Indexer (P0) ───
        self._code_tree_indexer = None

        # ─── P4: MAX Mode Parallel Engine (지연 초기화) ───
        self._max_engine = None

        # ─── P1-2: 통합 위임 엔진 (지연 초기화) ───
        self._delegation_engine = None

        # Lazy-init Heavy Components
        self._skill_auto_learner_initialized = False
        self._skill_auto_learner_instance = None
        self._trajectory_compressor_initialized = False
        self._trajectory_compressor_instance = None
        self._context_compressor_initialized = False
        self._context_compressor_instance = None

        # 세션 자동 시작
        try:
            self.session_manager.start_session(project_path=self.project_root)
        except (RuntimeError, ConnectionError, AttributeError):
            logger.warning("Session start failed (non-critical)", exc_info=True)

    def _init_evolution_coordinator(self):
        """Self-Evolution Coordinator를 초기화합니다. (self 참조 필요)"""

        def _sec_verify_fn(prompt: str) -> str:
            if self.manager:
                try:
                    return self.manager.generate(
                        prompt=prompt,
                        target=self._get_model_for_role("QA"),
                        max_tokens=256,
                    )
                except (RuntimeError, ValueError):
                    return ""
            return ""

        return create_evolution_coordinator(
            project_root=self.project_root,
            model_manager=self.manager,
            verify_fn=_sec_verify_fn if self.manager else None,
        )

    def _get_model_for_role(self, role: str) -> str:
        """역할에 맞는 모델을 반환합니다. config.yaml 매핑 우선."""
        return self.agent_models.get(role, self.agent_models.get("default", "qwen3.8-27b"))

    def get_model_for_role(self, role: str) -> str:
        return self._get_model_for_role(role)

    @property
    def task_execution_context(self) -> TaskExecutionContext | None:
        return self._task_execution_context.get()

    @contextmanager
    def bind_task_execution(self, task_id: str, state_store: TaskStateStore) -> Iterator[None]:
        execution_context = TaskExecutionContext(task_id, state_store)
        token = self._task_execution_context.set(execution_context)
        try:
            with bind_task_execution_context(execution_context):
                yield
        finally:
            self._task_execution_context.reset(token)

    # ─── Lazy Properties ─────────────────────────────────────────────

    def _default_reasoning_model(self) -> str:
        raw_cfg = getattr(self, "config", {}) or {}
        if isinstance(raw_cfg, dict):
            defaults = raw_cfg.get("defaults", {})
            if isinstance(defaults, dict):
                model_name = defaults.get("reasoning")
                if isinstance(model_name, str) and model_name:
                    return model_name
        return "qwen3.6:latest"

    def _compression_budget(self, target_model: str | None = None):
        raw_cfg = getattr(self, "config", {}) or {}
        config = raw_cfg if isinstance(raw_cfg, dict) else {}
        return context_budget_for_model(config, target_model or self._default_reasoning_model())

    def _compression_summarize_fn(self):
        if not self.manager:
            return None
        model_name = self._default_reasoning_model()

        def _summarize(prompt: str) -> str:
            return self.manager.generate(
                prompt=prompt,
                target=model_name,
                max_tokens=512,
            )

        return _summarize

    def _build_trajectory_compressor(self, target_model: str | None = None):
        from antigravity_k.engine.trajectory_compressor import TrajectoryCompressor

        budget = self._compression_budget(target_model)
        return TrajectoryCompressor(
            summarize_fn=self._compression_summarize_fn(),
            max_messages=budget.trajectory_max_messages,
            max_chars=budget.trajectory_max_chars,
        )

    def _build_context_compressor(self, target_model: str | None = None):
        from antigravity_k.engine.context_compressor import ContextCompressor

        budget = self._compression_budget(target_model)
        return ContextCompressor(
            token_limit=budget.token_limit,
            keep_last_n=10,
            summarize_fn=self._compression_summarize_fn(),
            persistence_dir=os.path.join(self.project_root, "data", "context_memory"),
        )

    @property
    def skill_auto_learner(self):
        """SkillAutoLearner 지연 초기화 (첫 접근 시 생성)."""
        if not self._skill_auto_learner_initialized:
            self._skill_auto_learner_initialized = True
            try:
                from antigravity_k.engine.skill_auto_learner import SkillAutoLearner

                self._skill_auto_learner_instance = SkillAutoLearner(
                    self.project_root,
                    self.manager,
                )
                logger.info("[Orchestrator] SkillAutoLearner (Closed Learning Loop) 활성화 완료")
            except (ImportError, RuntimeError, AttributeError):
                logger.warning("SkillAutoLearner init failed", exc_info=True)
                self._skill_auto_learner_instance = None
        return self._skill_auto_learner_instance

    @property
    def trajectory_compressor(self):
        """TrajectoryCompressor 지연 초기화 (첫 접근 시 생성)."""
        if not self._trajectory_compressor_initialized:
            self._trajectory_compressor_initialized = True
            try:
                self._trajectory_compressor_instance = self._build_trajectory_compressor()
                logger.info("[Orchestrator] TrajectoryCompressor 활성화 완료")
            except (ImportError, RuntimeError, AttributeError, ValueError):
                logger.warning("TrajectoryCompressor init failed", exc_info=True)
                self._trajectory_compressor_instance = None
        return self._trajectory_compressor_instance

    def trajectory_compressor_for(self, target_model: str):
        if target_model == self._default_reasoning_model():
            return self.trajectory_compressor
        try:
            return self._build_trajectory_compressor(target_model)
        except (ImportError, RuntimeError, AttributeError, ValueError):
            logger.warning("TrajectoryCompressor init failed", exc_info=True)
            return None

    @property
    def context_compressor(self):
        """ContextCompressor 지연 초기화 (토큰 예산 기반 적응형 압축).

        TrajectoryCompressor(메시지 수 기반)보다 정교한 토큰 예산 기반 압축을 수행합니다.
        작업 유형별로 keep_last_n과 max_tool_chars를 다르게 적용하며,
        pruned 메시지를 장기 기억 JSON으로 영속화합니다.
        summarize_fn이 없으면 휴리스틱 폴백으로 동작합니다 (LLM 호출 없음).
        """
        if not self._context_compressor_initialized:
            self._context_compressor_initialized = True
            try:
                self._context_compressor_instance = self._build_context_compressor()
                logger.info(
                    "[Orchestrator] ContextCompressor 활성화 완료 (token_limit=%s)",
                    self._context_compressor_instance.token_limit,
                )
            except (ImportError, RuntimeError, AttributeError, ValueError):
                logger.warning("ContextCompressor init failed", exc_info=True)
                self._context_compressor_instance = None
        return self._context_compressor_instance

    def context_compressor_for(self, target_model: str):
        if target_model == self._default_reasoning_model():
            return self.context_compressor
        try:
            return self._build_context_compressor(target_model)
        except (ImportError, RuntimeError, AttributeError, ValueError):
            logger.warning("ContextCompressor init failed", exc_info=True)
            return None

    @property
    def delegation_engine(self):
        """통합 위임 엔진 (P1-2) — 5개 위임 메커니즘을 단일 인터페이스로.

        기존 MAX/Pipeline/Debate/SubagentSpawner/single을 전략 패턴으로 통합.
        recommend_strategy()로 결정적 전략 선택, delegate()로 단일 진입점.
        """
        if self._delegation_engine is None:
            try:
                from antigravity_k.engine.delegation_engine import DelegationEngine

                self._delegation_engine = DelegationEngine(self)
                logger.info("[Orchestrator] DelegationEngine 활성화 완료")
            except (ImportError, RuntimeError, AttributeError):
                logger.warning("DelegationEngine init failed", exc_info=True)
                self._delegation_engine = None
        return self._delegation_engine

    # ─── 툴 프롬프트 ─────────────────────────────────────────────────

    def _build_tool_prompt(self) -> str:
        """도구 목록을 프롬프트에 주입합니다. few-shot 예시 포함."""
        tool_section = (
            "## Tool Usage Instructions\n"
            "You are a function calling AI model. You may call one or more functions to assist with the user query.\n"
            "Don't make assumptions about what values to plug into functions.\n"
            "To use a tool, you MUST use the <scratch_pad> XML tags to record your reasoning and planning before"
            "you call the function.\n\n"
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
        tool_section += "\n" + self.ctx.prompt_builder.response_contract() + "\n"
        if hasattr(self.tool_registry, "render_autonomous_policy"):
            tool_section += "\n" + self.tool_registry.render_autonomous_policy() + "\n"
        try:
            from antigravity_k.engine.codex_transfer import CodexTransferEngine

            tool_section += "\n" + CodexTransferEngine().render_prompt_contract() + "\n"
        except ImportError:
            logger.debug("CodexTransferEngine 미설치 — prompt contract 생략")
        except (AttributeError, RuntimeError) as e:
            logger.warning("Codex operating contract unavailable: %s", e)
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
        except ImportError:
            logger.debug("SelfCapabilityEngine 미설치 — prompt contract 생략")
        except (AttributeError, RuntimeError, ValueError) as e:
            logger.warning("Self-capability contract unavailable: %s", e)
        # ── 30B Model Amplification: Dynamic Tool Masking ──
        raw_schemas = self.tool_registry.to_llm_schemas()
        try:
            from antigravity_k.engine.tool_masker import ActiveToolMasker

            masker = ActiveToolMasker(mode=getattr(self.mode_manager, "current_mode", None))
            schemas_to_render = masker.filter_tools(raw_schemas)
        except Exception:
            schemas_to_render = raw_schemas

        for schema in schemas_to_render:
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

    def _requires_planning_mode(self, task_type: str, messages: list[dict[str, str]]) -> bool:
        """복잡한 구조 변경에만 Planning Mode를 강제합니다.

        ModeManager의 should_enforce_plan_mode()에 위임합니다.
        """
        if hasattr(self, "mode_manager") and self.mode_manager:
            user_text = self._latest_user_text(messages)
            return self.mode_manager.should_enforce_plan_mode(task_type, user_text)

        # Fallback (ModeManager 미연결 시 레거시 로직)
        if task_type == "complex":
            return True
        if task_type != "coding":
            return False
        request_text = "\n".join(str(msg.get("content", "")) for msg in messages if msg.get("role") == "user").lower()
        return bool(
            re.search(
                r"(아키텍처|구조|전면|대규모|마이그레이션|프레임워크|리팩토링|"
                r"architecture|refactor|migrate|framework|plugin system)",
                request_text,
            ),
        )

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """ToolExecutor에 위임합니다. (Phase 1 D3: execution_mode 전달)"""
        mode = self._get_execution_mode()
        return self.ctx.tool_executor.execute(name, args, execution_mode=mode)

    def _get_execution_mode(self) -> str:
        """현재 실행 모드 문자열을 반환합니다. ("plan", "build", "interactive")

        ModeManager가 없으면 기본값 "interactive" 반환.
        PlanGuard, GatePipeline, QualityGate에 execution_mode를 전달하는 소스 역할.
        """
        if hasattr(self, "mode_manager") and self.mode_manager:
            try:
                return self.mode_manager.current_mode.value
            except (AttributeError, ValueError):
                logger.debug("mode_manager.current_mode 조회 실패 — interactive로 폴백")
        return "interactive"

    def _inject_mode_prompt(
        self,
        system_prompt: str,
        task_type: str,
        messages: list[dict[str, str]],
        delegate_to: str,
    ) -> str:
        """현재 실행 모드에 따라 system prompt에 모드별 지시사항을 주입합니다.

        PLAN 모드:
          - ArtifactEngine.inject_planning_prompt() 또는 PLANNING_MODE_BLOCK 추가
          - 읽기 전용 도구만 사용하도록 강제

        BUILD 모드:
          - Plan이 검증되었음을 명시
          - Plan 태스크를 실행할 것을 지시
          - 모든 도구 사용 가능

        INTERACTIVE 모드:
          - 기존 동작 유지 (추가 주입 없음)

        Args:
            system_prompt: 원본 system prompt
            task_type: 태스크 유형
            messages: 대화 메시지
            delegate_to: 위임 대상 역할

        Returns:
            모드별 지시사항이 추가된 system prompt
        """
        mode = self._get_execution_mode()

        if mode == "plan" and delegate_to != "CEO":
            # PLAN 모드: 계획 수립 프롬프트 주입
            if hasattr(self, "artifact_engine") and self.artifact_engine:
                planning_mode_enforcement = self.artifact_engine.inject_planning_prompt()
            else:
                planning_mode_enforcement = PLANNING_MODE_BLOCK
            system_prompt += planning_mode_enforcement

        elif mode == "build" and delegate_to != "CEO":
            # BUILD 모드: 실행 중심 프롬프트 주입
            plan_path = ""
            if hasattr(self.mode_manager, "plan_artifact_path") and self.mode_manager.plan_artifact_path:
                plan_path = self.mode_manager.plan_artifact_path

            build_prompt = (
                "\n\n[EXECUTION MODE: BUILD]\n"
                "You are now in BUILD MODE. The plan has been validated and approved.\n"
                "1. Execute the tasks defined in the plan using all available tools.\n"
                "2. You have full access to all tools — read, write, execute, and manage files.\n"
                "3. Follow the plan's implementation steps in order.\n"
                "4. After completing each task, update the task status in the Kanban board.\n"
                "5. If you encounter unexpected issues, document them and adjust the approach.\n"
            )
            if plan_path:
                build_prompt += f"\nReference Plan: `{plan_path}`\n"

            system_prompt += build_prompt

        # INTERACTIVE 모드와 CEO 역할은 추가 주입 없음

        return system_prompt

    def _latest_user_text(self, messages: list[dict[str, Any]]) -> str:
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
        """ToolExecutor에 도구를 등록합니다."""
        self.ctx.tool_executor.register_default_tools()

    # ─── CEO 분석 단계 ───────────────────────────────────────────────

    def _ceo_analyze(
        self,
        user_message: str,
        target_model: str,
    ) -> Generator[str | dict[str, Any], None, None]:
        """CEO 분석을 ceo_analyzer 모듈에 위임합니다."""
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
        messages: list[dict[str, str]],
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
        messages: list[dict[str, Any]],
        delegate_to: str,
        task_type: str,
    ) -> tuple[str, str, str, str, str, list[dict[str, Any]]]:
        """에이전트 실행에 필요한 프롬프트와 컨텍스트를 준비합니다.

        Returns:
            (delegate_model, system_prompt, tool_prompt, skill_prompts,
             prompt, shaped_messages)

        """
        delegate_model = self._get_model_for_role(delegate_to)
        system_prompt = get_orchestrator_prompt(delegate_to)

        # 실행 모드에 따라 system prompt 분기 (Phase 1 D5)
        system_prompt = self._inject_mode_prompt(system_prompt, task_type, messages, delegate_to)

        tool_prompt = self._build_tool_prompt() if delegate_to != "CEO" else ""

        # 에러 카운터 리셋
        self.ctx.tool_executor.reset_error_counter()
        user_objective = messages[-1].get("content", "") if messages else ""
        if hasattr(self.ctx.tool_executor, "set_objective"):
            self.ctx.tool_executor.set_objective(user_objective)

        # 인지 루프 초기화
        if self.ctx.cognitive_loop:
            self.ctx.cognitive_loop.reset()
        if self.ctx.quality_gate:
            self.ctx.quality_gate.reset()

        # 실패 학습 컨텍스트 주입
        failure_context = ""

        # Skill injection
        skill_prompts = ""
        if hasattr(self.ctx, "skill_loader") and self.ctx.skill_loader:
            skill_prompts = self.ctx.skill_loader.get_active_prompts()

        # IDE Context injection
        ide_prompt = self.ctx.ide_manager.format_prompt() if hasattr(self.ctx, "ide_manager") else ""
        if ide_prompt:
            skill_prompts += "\n" + ide_prompt

        # ── 30B Model Amplification: Deterministic Structural Context & Working Memory ──
        pinned_context = ""
        try:
            from antigravity_k.engine.structural_snapshot import StructuralSnapshotBuilder
            from antigravity_k.engine.working_memory_compactor import WorkingMemoryCompactor

            snapshot = StructuralSnapshotBuilder.build(self.project_root)
            working_mem = WorkingMemoryCompactor.compact(messages)
            pinned_context = (
                snapshot.format_pinned_block() + "\n\n" + working_mem.format_pinned_working_memory() + "\n\n"
            )
        except Exception as se:
            logger.debug("StructuralSnapshot/WorkingMemory build skipped: %s", se)

        prompt = f"System: {pinned_context}{system_prompt}\n{skill_prompts}\n"
        if failure_context:
            prompt += f"\n{failure_context}\n"
        if tool_prompt:
            prompt += f"\n{tool_prompt}\n"
        prompt += "\n"

        # Context Shaper 적용
        shaped_messages = self.context_shaper.shape(messages)
        shaped_messages = self.context_shaper.clear_old_tool_results(shaped_messages)

        # Decision Anchor 주입
        decision_anchor = getattr(self.ctx, "decision_anchor", None)
        if decision_anchor:
            shaped_messages = decision_anchor.inject_into_messages(shaped_messages)

        # Budget Awareness 주입
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

    # ─── 실행 ─────────────────────────────────────────────────────────

    @property
    def code_tree_indexer(self):
        """CodeTreeIndexer 지연 초기화 (Freebuff-Style 자동 컨텍스트).

        최초 접근 시 1회 빌드되며, 이후 변경 감지로 증분 갱신됩니다.
        빌드 실패 시 None을 반환하여 메인 플로우에 영향을 주지 않습니다.
        """
        if self._code_tree_indexer is None:
            try:
                from antigravity_k.engine.code_tree_indexer import CodeTreeIndexer

                self._code_tree_indexer = CodeTreeIndexer(project_root=self.project_root)
                logger.info("[Proactive] CodeTreeIndexer 활성화 완료")
            except (ImportError, RuntimeError, AttributeError):
                logger.debug("CodeTreeIndexer init failed (non-critical)")
                self._code_tree_indexer = None

            # 최초 1회는 try/except 밖에서 백그라운드 빌드 시도
            if self._code_tree_indexer:
                try:
                    self._code_tree_indexer.build_tree()
                    stats = self._code_tree_indexer.stats()
                    logger.info(
                        "[Proactive] Code tree built: %s files, %s KB",
                        stats["files_indexed"],
                        stats["tree_size_kb"],
                    )
                except (RuntimeError, KeyError):
                    logger.debug("CodeTree 초기 빌드 실패 (non-critical)")

        return self._code_tree_indexer

    @property
    def max_engine(self):
        """MaxModeEngine 지연 초기화 (P4: MAX Mode 병렬 편집).

        여러 워커를 병렬로 실행하고 Selector가 최적 결과를 선정합니다.
        실패 시 None을 반환하여 메인 플로우에 영향 없음.
        """
        if self._max_engine is None:
            try:
                from antigravity_k.engine.max_engine import MaxModeEngine

                self._max_engine = MaxModeEngine(
                    model_manager=self.manager,
                    project_root=self.project_root,
                )

                # 워커 수 설정 (config에서 또는 기본값)
                max_workers = (
                    getattr(self.ctx, "config", {})
                    .get(
                        "max_mode",
                        {},
                    )
                    .get("max_workers", 3)
                )
                self._max_engine.set_max_workers(max_workers)

                logger.info("[MAX] MaxModeEngine 활성화 완료 (%s workers)", max_workers)
            except (ImportError, RuntimeError, AttributeError):
                logger.debug("MaxModeEngine init failed (non-critical)")
                self._max_engine = None

        return self._max_engine

    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Generator[str, None, None]:
        """State Graph 기반 멀티 에이전트 스트리밍 실행.

        내부 구현은 orchestrator.stream 모듈에 위임됩니다.
        """
        from antigravity_k.engine.orchestrator.stream import run_stream as _stream_run

        yield from _stream_run(self, messages, target_model, max_steps, ephemeral_message)

    def run_sync(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
    ) -> str:
        """동기식 실행 (커맨드 팔레트 등에서 사용)."""
        from antigravity_k.engine.orchestrator.stream import run_sync as _sync_run

        return _sync_run(self, messages, target_model, max_steps)
