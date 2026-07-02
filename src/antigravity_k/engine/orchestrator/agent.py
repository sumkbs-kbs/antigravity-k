"""OrchestratorAgent — CEO 기반 멀티 에이전트 오케스트레이터 클래스."""

import logging
import os
import re
from collections.abc import Generator
from typing import Any, Union

from antigravity_k.agents.personas import get_orchestrator_prompt
from antigravity_k.engine.capacity_flow import CapacityCheckpoint
from antigravity_k.engine.ceo_analyzer import ceo_analyze as _ceo_analyze_fn
from antigravity_k.engine.engine_context import EngineContext
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
logger = logging.getLogger("antigravity_k.orchestrator")


class OrchestratorAgent:
    """CEO 기반 멀티 에이전트 오케스트레이터.

    사용자 명령 흐름:
    1. CEO 분석 (빠른 모델) → 태스크 유형 판별
    2. 역할별 모델 위임 → 전문 에이전트 실행
    3. 도구 호출 (ReAct 루프) → 실제 작업 수행
    4. 결과 스트리밍 → 대시보드 표시
    """

    def __init__(self, model_manager, vault_engine=None, project_root=None, tool_registry=None):
        """Initialize the OrchestratorAgent.

        Args:
            model_manager: model manager.
            vault_engine: vault engine.
            project_root: project root.
            tool_registry: tool registry.

        """
        self.manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root or os.getcwd()

        self.ctx = EngineContext(
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
            tool_registry=tool_registry,
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

        # ─── Setup: Optional Components ───
        self.watchdog = create_watchdog(
            self.config, self.project_root, self.manager, self.vault_engine,
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

        # ─── Freebuff-Style Proactive: Code Tree Indexer (P0) ───
        self._code_tree_indexer = None

        # ─── P4: MAX Mode Parallel Engine (지연 초기화) ───
        self._max_engine = None

        # Lazy-init Heavy Components
        self._skill_auto_learner_initialized = False
        self._skill_auto_learner_instance = None
        self._trajectory_compressor_initialized = False
        self._trajectory_compressor_instance = None

        # 세션 자동 시작
        try:
            self.session_manager.start_session(project_path=self.project_root)
        except Exception:
            logger.exception("Session start failed")

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
                except Exception:
                    return ""
            return ""

        return create_evolution_coordinator(
            project_root=self.project_root,
            model_manager=self.manager,
            verify_fn=_sec_verify_fn if self.manager else None,
        )

    def _get_model_for_role(self, role: str) -> str:
        """역할에 맞는 모델을 반환합니다. config.yaml 매핑 우선."""
        return self.agent_models.get(role, self.agent_models.get("default", "qwen3.6:latest"))

    # ─── Lazy Properties ─────────────────────────────────────────────

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
            except Exception:
                logger.exception("SkillAutoLearner init failed")
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
                            "reasoning",
                            "qwen3.6:latest",
                        )
                        return self.manager.generate(
                            prompt=prompt,
                            target=default_m,
                            max_tokens=512,
                        )

                    summarize_fn = _summarize
                self._trajectory_compressor_instance = TrajectoryCompressor(
                    summarize_fn=summarize_fn,
                )
                logger.info("[Orchestrator] TrajectoryCompressor 활성화 완료")
            except Exception:
                logger.exception("TrajectoryCompressor init failed")
                self._trajectory_compressor_instance = None
        return self._trajectory_compressor_instance

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
        if hasattr(self.tool_registry, "render_autonomous_policy"):
            tool_section += "\n" + self.tool_registry.render_autonomous_policy() + "\n"
        try:
            from antigravity_k.engine.codex_transfer import CodexTransferEngine

            tool_section += "\n" + CodexTransferEngine().render_prompt_contract() + "\n"
        except ImportError:
            logger.debug("CodexTransferEngine not installed — skipping prompt contract")
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
            logger.debug("SelfCapabilityEngine not installed — skipping")
        except (AttributeError, RuntimeError, ValueError) as e:
            logger.warning("Self-capability contract unavailable: %s", e)
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

    def _requires_planning_mode(self, task_type: str, messages: list[dict[str, str]]) -> bool:
        """복잡한 구조 변경에만 Planning Mode를 강제합니다."""
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
        """ToolExecutor에 위임합니다."""
        return self.ctx.tool_executor.execute(name, args)

    def _latest_user_text(self, messages: list[dict[str, str]]) -> str:
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
    ) -> Generator[Union[str, dict], None, None]:
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
        messages: list[dict[str, str]],
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

        # 복합/대규모 태스크인 경우 Planning Mode 주입
        if self._requires_planning_mode(task_type, messages) and delegate_to != "CEO":
            if hasattr(self, "artifact_engine") and self.artifact_engine:
                planning_mode_enforcement = self.artifact_engine.inject_planning_prompt()
            else:
                planning_mode_enforcement = PLANNING_MODE_BLOCK
            system_prompt += planning_mode_enforcement

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

        prompt = f"System: {system_prompt}\n{skill_prompts}\n"
        if failure_context:
            prompt += f"\n{failure_context}\n"
        if tool_prompt:
            prompt += f"\n{tool_prompt}\n"
        prompt += "\n"

        # Context Shaper 적용
        shaped_messages = self.context_shaper.shape(messages)
        shaped_messages = self.context_shaper.clear_old_tool_results(shaped_messages)

        # Decision Anchor 주입
        if hasattr(self.ctx, "decision_anchor") and self.ctx.decision_anchor:
            shaped_messages = self.ctx.decision_anchor.inject_into_messages(shaped_messages)

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
            except Exception:
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
                except Exception:
                    logger.debug("Initial code tree build failed (non-critical)")

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
                max_workers = getattr(self.ctx, "config", {}).get(
                    "max_mode", {},
                ).get("max_workers", 3)
                self._max_engine.set_max_workers(max_workers)

                logger.info("[MAX] MaxModeEngine 활성화 완료 (%s workers)", max_workers)
            except Exception:
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
