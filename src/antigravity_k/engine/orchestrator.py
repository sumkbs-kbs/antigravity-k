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

import logging
import os
import re
from typing import List, Dict, Any, Generator, Optional, Union

from antigravity_k.engine.tool_call_parser import ToolCallParser, EventType
from antigravity_k.engine.tool_guardrails import (
    append_guardrail_guidance,
    guardrail_synthetic_result,
)
from antigravity_k.engine.error_classifier import classify_api_error
from antigravity_k.engine.ceo_analyzer import ceo_analyze as _ceo_analyze_fn
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.state_graph import StateContext
from antigravity_k.engine.stream_processor import StreamProcessor
from antigravity_k.engine.memory_recorder import MemoryRecorder
from antigravity_k.engine.capacity_flow import CapacityCheckpoint, CapacityAction
from antigravity_k.agents.personas import get_orchestrator_prompt

logger = logging.getLogger("antigravity_k.orchestrator")

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
        self.memory_manager = self.ctx.memory_manager

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
        self._tool_executor.reset_error_counter()

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

        # Artifact Engine 초기화 및 도구 등록
        try:
            from antigravity_k.engine.artifact_engine import register_artifact_tool

            self.artifact_engine = register_artifact_tool(
                self.tool_registry, self.project_root
            )
            logger.info(
                "[Orchestrator] Artifact Engine 활성화 및 write_artifact 도구 등록 완료"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ArtifactEngine: {e}")

        # 세션 자동 시작 (프로젝트별 대화 영속성)
        try:
            self.session_manager.start_session(project_path=self.project_root)
        except Exception as e:
            logger.warning(f"Session start failed: {e}")

    def _get_model_for_role(self, role: str) -> str:
        """역할에 맞는 모델을 반환합니다. config.yaml 매핑 우선."""
        return self.agent_models.get(
            role, self.agent_models.get("default", "qwen3.6:latest")
        )

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
                skill_loader=self.skill_loader,
                model_manager=self.manager,
                project_root=self.project_root,
                slash_commands=getattr(self.slash_commands, "_commands", {}),
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
        return self._tool_executor.execute(name, args)

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
            skill_loader=self.skill_loader,
            model_manager=self.manager,
            project_root=self.project_root,
            slash_commands=getattr(self.slash_commands, "_commands", {}),
        )
        return engine.render_markdown(snapshot)

    def _register_claw_tools(self):
        """ToolExecutor에 위임합니다. (I-1 리팩터링)"""
        self._tool_executor.register_default_tools()

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

    def _run_single_agent(
        self,
        messages: List[Dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int = 15,
    ) -> Generator[str, None, None]:
        delegate_model = self._get_model_for_role(delegate_to)
        if hasattr(self, "manager") and not self.manager.is_loaded(delegate_model):
            yield f"\n\n*(🚀 `{delegate_model}` 모델을 VRAM에 로드 중입니다. 모델 크기에 따라 1~3분이 소요될 수 있습니다...)*\n\n"
        system_prompt = get_orchestrator_prompt(delegate_to)

        # [Phase 17] 복합/대규모 태스크인 경우 Planning Mode 워크플로우 강제 주입
        if self._requires_planning_mode(task_type, messages) and delegate_to != "CEO":
            if hasattr(self, "artifact_engine"):
                planning_mode_enforcement = (
                    self.artifact_engine.inject_planning_prompt()
                )
            else:
                planning_mode_enforcement = (
                    "\n\n[CRITICAL ALGORITHM OVERRIDE]\n"
                    "You are executing a COMPLEX task. You MUST enter PLANNING MODE.\n"
                    "1. DO NOT write any functional code or implementation details in your initial response.\n"
                    "2. You MUST use the `write_file` tool to create `artifacts/implementation_plan.md` outlining your technical plan.\n"
                    "3. End your response EXACTLY with the string `[APPROVAL REQUIRED]` on a new line to pause execution and ask the user for permission to proceed.\n"
                    "Failure to do this will result in a Quality Gate failure and retry loop.\n"
                )
            system_prompt += planning_mode_enforcement

        tool_prompt = self._build_tool_prompt() if delegate_to != "CEO" else ""

        # 턴 시작 시 에러 카운터 리셋 (이전 턴의 에러가 이월되지 않도록)
        self._tool_executor.reset_error_counter()
        user_objective = messages[-1].get("content", "") if messages else ""
        if hasattr(self._tool_executor, "set_objective"):
            self._tool_executor.set_objective(user_objective)

        # ─── E-1: 인지 루프 초기화 ───
        self.cognitive_loop.reset()
        self.quality_gate.reset()

        # ─── E-3: 실패 학습 컨텍스트 주입 ───
        failure_context = self.failure_memory.build_prompt(
            messages[-1].get("content", "") if messages else ""
        )

        # Skill injection
        skill_prompts = (
            self.skill_loader.get_active_prompts()
            if hasattr(self, "skill_loader")
            else ""
        )

        # IDE Context injection
        ide_prompt = self.ide_manager.format_prompt()
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

        for msg in shaped_messages:
            prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
        prompt += "Assistant: "

        logger.info(
            f"Delegate: role={delegate_to}, model={delegate_model}, task_type={task_type}"
        )

        # ─── Tool Loop Guardrail (Hermes 패턴 + Capacity Flow) ───
        self.tool_guardrail.reset_for_turn()

        full_output = ""
        stream_proc = StreamProcessor()
        for step in range(max_steps):
            requires_approval_break = False
            parser = ToolCallParser()
            full_response = ""
            tool_executed = False
            stream_proc.reset()
            pending_tool_calls = []

            # Capacity Flow: 스텝 예산 체크 (DeepSeek-TUI 패턴)
            capacity = self._capacity_checkpoint.check_step_budget(step, max_steps)
            if capacity.action == CapacityAction.WARN:
                prompt += f"\n[SYSTEM WARNING] {capacity.message}\n"
            elif capacity.action == CapacityAction.COMPRESS:
                prompt += f"\n[CAPACITY COMPRESS] {capacity.message}\n"
                if self.context_shaper:
                    shaped_messages = self.context_shaper.shape(
                        shaped_messages, force_compact=True
                    )
            elif capacity.action == CapacityAction.HALT:
                yield f"\n\n⚠️ **[Capacity Guard]** {capacity.message}\n"
                break

            # /no_think 플래그가 포함되어 있으면 특정 모델(Qwen)이 즉시 종료하는 버그 방지
            clean_sys_prompt = (
                system_prompt.replace("/no_think", "").replace("System:", "").strip()
            )
            final_sys_prompt = f"{clean_sys_prompt}\n{tool_prompt}".strip()

            try:
                stream = self.manager.stream_generate(
                    prompt=prompt,
                    target=delegate_model,
                    raw_messages=shaped_messages,
                    system_prompt=final_sys_prompt,
                )
                for chunk in stream:
                    full_response += chunk
                    for event in parser.feed(chunk):
                        if event.type == EventType.TEXT:
                            # StreamProcessor로 내부 태그 필터링 + 반복 감지
                            processed, is_repeat = stream_proc.process_text(event.data)
                            if is_repeat:
                                logger.warning(
                                    "[StreamProcessor] Repetition loop — stopping"
                                )
                                yield "\n\n⚠️ *반복 루프 감지 — 자동 중단*\n"
                                tool_executed = True
                                break
                            if processed:
                                yield processed
                                full_output += processed

                        elif event.type == EventType.TOOL_CALL_START:
                            yield "\n🔧 "

                        elif event.type == EventType.TOOL_CALL_COMPLETE:
                            tool_name = event.tool_call.name
                            tool_args = event.tool_call.arguments

                            # ── Before-call 가드레일 (Hermes 패턴) ──
                            try:
                                from antigravity_k.engine.event_bus import (
                                    global_event_bus,
                                )

                                global_event_bus.publish(
                                    "ToolExecutionStarted", name=tool_name
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to publish ToolExecutionStarted: {e}"
                                )

                            pre_decision = self.tool_guardrail.before_call(
                                tool_name, tool_args
                            )
                            if not pre_decision.allows_execution:
                                # 차단: 합성 에러 결과 주입
                                logger.warning(
                                    f"🛡️ Guardrail blocked: {pre_decision.code} ({tool_name})"
                                )
                                yield f"\n\n🛡️ **[Tool Loop Guard]** {pre_decision.message}\n"
                                synthetic = guardrail_synthetic_result(pre_decision)
                                parser.tool_responses.append(
                                    f"<tool_response>\n{synthetic}\n</tool_response>"
                                )

                                try:
                                    global_event_bus.publish(
                                        "ToolExecutionFinished", name=tool_name
                                    )
                                except Exception:
                                    pass

                                if pre_decision.should_halt:
                                    tool_executed = True
                                    break
                                tool_executed = True
                                continue

                            tool_result = self._execute_tool(tool_name, tool_args)

                            try:
                                global_event_bus.publish(
                                    "ToolExecutionFinished", name=tool_name
                                )
                            except Exception:
                                pass

                            # ── E-1: 인지 루프 검증 (CognitiveLoop Verify) ──
                            try:
                                verification = self.cognitive_loop.verify_tool_result(
                                    tool_name, tool_args, str(tool_result)
                                )
                                if not verification["passed"]:
                                    # E-3: 실패 기록
                                    self.failure_memory.record(
                                        tool=tool_name,
                                        error_text=str(tool_result)[:500],
                                        args_summary=str(tool_args)[:200],
                                    )
                            except Exception as ve:
                                logger.debug(f"Cognitive verification error: {ve}")

                            # ── After-call 가드레일 ──
                            is_failed = isinstance(
                                tool_result, str
                            ) and tool_result.strip().startswith("Error")

                            is_approval_required = (
                                isinstance(tool_result, str)
                                and (
                                    "[APPROVAL REQUIRED]" in tool_result
                                    or "WAITING_FOR_USER_APPROVAL" in tool_result
                                )
                                and tool_name in ["run_command", "ask_question", "plan"]
                            )
                            if is_approval_required:
                                requires_approval_break = True

                            post_decision = self.tool_guardrail.after_call(
                                tool_name, tool_args, tool_result, failed=is_failed
                            )

                            if is_approval_required:
                                status_icon = "✋"
                            elif (
                                is_failed
                                or post_decision.action == "warn"
                                or post_decision.should_halt
                            ):
                                status_icon = "❌"
                            else:
                                status_icon = "✅"
                            yield '<details class="tool-card" style="margin: 10px 0; border: 1px solid #333; border-radius: 8px; background: rgba(0,0,0,0.2);">\n'
                            yield f'<summary style="padding: 8px; cursor: pointer; font-weight: bold; border-bottom: 1px solid #333;"><span class="icon">🛠️</span> Executing <b>{tool_name}</b> <span style="opacity:0.7; font-weight:normal; font-size:0.9em;">(Step {step+1}/{max_steps})</span> {status_icon}</summary>\n'
                            yield '<div style="padding: 10px;">\n'

                            # 경고 메시지 주입
                            if post_decision.action == "warn":
                                tool_result = append_guardrail_guidance(
                                    tool_result, post_decision
                                )
                                yield f"\n⚠️ {post_decision.message}\n"
                            elif post_decision.should_halt:
                                logger.warning(
                                    f"🛡️ Guardrail halt: {post_decision.code} ({tool_name})"
                                )
                                tool_result = append_guardrail_guidance(
                                    tool_result, post_decision
                                )
                                yield f"\n\n🛡️ **[Tool Loop Guard]** {post_decision.message}\n"

                            result_preview = (
                                tool_result[:1500]
                                if len(str(tool_result)) > 1500
                                else tool_result
                            )
                            yield f"\n```\n{result_preview}\n```\n"
                            yield "</div>\n</details>\n\n"

                            # 응답 블록을 저장 (스트림 종료 후 한번에 추가하기 위함)
                            parser.tool_responses.append(
                                f"<tool_response>\n{tool_result}\n</tool_response>"
                            )

                            if post_decision.should_halt:
                                tool_executed = True
                                break
                            tool_executed = True

                        elif event.type == EventType.TOOL_CALL_ERROR:
                            logger.warning(f"Tool call parse error: {event.data}")
                            error_msg = f"[TOOL CALL PARSE ERROR] Please check your JSON syntax. Details: {event.data}"
                            yield f"\n\n⚠️ **{error_msg}**\n"

                            parser.tool_responses.append(
                                f"<tool_response>\n{error_msg}\n</tool_response>"
                            )
                            tool_executed = True

                for event in parser.flush():
                    if event.type == EventType.TEXT:
                        # StreamProcessor로 필터링
                        processed = stream_proc.process_flush_text(event.data)
                        if processed and processed.strip():
                            yield processed
                            full_output += processed

                    elif event.type == EventType.TOOL_CALL_COMPLETE:
                        # flush()에서 bare JSON 도구 호출이 감지된 경우
                        tool_name = event.tool_call.name
                        tool_args = event.tool_call.arguments
                        logger.info(f"[Flush] Bare JSON tool call: {tool_name}")

                        try:
                            from antigravity_k.engine.event_bus import global_event_bus

                            global_event_bus.publish(
                                "ToolExecutionStarted", name=tool_name
                            )
                        except Exception:
                            pass

                        pre_decision = self.tool_guardrail.before_call(
                            tool_name, tool_args
                        )
                        if pre_decision.allows_execution:
                            yield f"\n🔧 **{tool_name}** 실행 중...\n"
                            tool_result = self._execute_tool(tool_name, tool_args)
                            result_preview = (
                                tool_result[:1500]
                                if len(str(tool_result)) > 1500
                                else tool_result
                            )
                            yield f"\n```\n{result_preview}\n```\n"

                            is_approval_required = (
                                isinstance(tool_result, str)
                                and (
                                    "[APPROVAL REQUIRED]" in tool_result
                                    or "WAITING_FOR_USER_APPROVAL" in tool_result
                                )
                                and tool_name in ["run_command", "ask_question", "plan"]
                            )
                            if is_approval_required:
                                requires_approval_break = True

                            parser.tool_responses.append(
                                f"<tool_response>\n{tool_result}\n</tool_response>"
                            )
                            tool_executed = True
                        else:
                            yield f"\n\n🛡️ **[Guardrail]** {pre_decision.message}\n"

                        try:
                            global_event_bus.publish(
                                "ToolExecutionFinished", name=tool_name
                            )
                        except Exception:
                            pass
            except Exception as e:
                # ── API 에러 분류 (Hermes 패턴) ──
                classified = classify_api_error(
                    e,
                    provider="ollama",
                    model=delegate_model,
                    approx_tokens=len(prompt) // 4,
                )
                logger.error(
                    f"Error during stream generation: {classified.reason.value} "
                    f"(retryable={classified.retryable}, compress={classified.should_compress})",
                    exc_info=True,
                )

                if classified.should_compress:
                    yield "\n\n⚠️ **컨텍스트 초과 감지** — 자동 압축을 시도합니다...\n"
                    shaped_messages = self.context_shaper.shape(
                        shaped_messages, force_compact=True
                    )
                    prompt = self._rebuild_prompt(
                        system_prompt, tool_prompt, skill_prompts, shaped_messages
                    )
                    continue
                elif classified.retryable and step < max_steps - 1:
                    yield f"\n\n⚠️ **일시적 오류** ({classified.reason.value}) — 재시도합니다...\n"
                    continue
                else:
                    yield (
                        f"\n\n❌ **에이전트 실행 오류** [{classified.reason.value}]: "
                        f"모델(`{delegate_model}`)을 실행하는 중 문제가 발생했습니다.\n"
                        f"상세 에러: {str(e)}\n\n"
                        f"*팁: 해당 모델이 설치되어 있지 않다면 `ollama pull {delegate_model}` 명령어로 설치해주세요.*\n"
                    )
                    return

            if pending_tool_calls:
                import concurrent.futures
                from antigravity_k.engine.event_bus import global_event_bus

                yield f"\n\n🚀 **[{len(pending_tool_calls)}개의 도구 병렬 실행 시작]**\n"

                def _run_tool_task(tc):
                    tool_name = tc.name
                    tool_args = tc.arguments

                    try:
                        global_event_bus.publish("ToolExecutionStarted", name=tool_name)
                    except Exception:
                        pass

                    pre_decision = self.tool_guardrail.before_call(tool_name, tool_args)
                    if not pre_decision.allows_execution:
                        logger.warning(
                            f"🛡️ Guardrail blocked: {pre_decision.code} ({tool_name})"
                        )
                        synthetic = guardrail_synthetic_result(pre_decision)

                        try:
                            global_event_bus.publish(
                                "ToolExecutionFinished", name=tool_name
                            )
                        except Exception:
                            pass

                        return tc, pre_decision, None, synthetic, True

                    tool_result = self._execute_tool(tool_name, tool_args)

                    try:
                        global_event_bus.publish(
                            "ToolExecutionFinished", name=tool_name
                        )
                    except Exception:
                        pass

                    # CognitiveLoop Verify
                    try:
                        verification = self.cognitive_loop.verify_tool_result(
                            tool_name, tool_args, str(tool_result)
                        )
                        if not verification["passed"]:
                            self.failure_memory.record(
                                tool=tool_name,
                                error_text=str(tool_result)[:500],
                                args_summary=str(tool_args)[:200],
                            )
                    except Exception as ve:
                        logger.debug(f"Cognitive verification error: {ve}")

                    post_decision = self.tool_guardrail.after_call(
                        tool_name,
                        tool_args,
                        tool_result,
                        failed=(
                            isinstance(tool_result, str)
                            and tool_result.strip().startswith("Error")
                        ),
                    )
                    return tc, pre_decision, post_decision, tool_result, False

                results_collected = []

                # DAG 기반 도구 실행 그룹화 (waitForPreviousTools 처리)
                execution_batches = []
                current_batch = []
                for tc in pending_tool_calls:
                    wait_for_previous = False
                    if isinstance(tc.arguments, dict):
                        wait_for_previous = tc.arguments.get(
                            "waitForPreviousTools", False
                        )

                    if wait_for_previous and current_batch:
                        execution_batches.append(current_batch)
                        current_batch = []
                    current_batch.append(tc)
                if current_batch:
                    execution_batches.append(current_batch)

                for batch in execution_batches:
                    batch_results = []
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=5
                    ) as executor:
                        futures = {
                            executor.submit(_run_tool_task, tc): tc for tc in batch
                        }
                        for future in concurrent.futures.as_completed(futures):
                            try:
                                res = future.result()
                                batch_results.append(res)
                            except Exception as e:
                                tc = futures[future]
                                batch_results.append(
                                    (tc, None, None, f"Exception: {e}", True)
                                )

                    # 원래 배치 순서대로 정렬하여 UI 출력
                    batch_results.sort(key=lambda x: batch.index(x[0]))

                    for (
                        tc,
                        pre_decision,
                        post_decision,
                        tool_result,
                        blocked,
                    ) in batch_results:
                        results_collected.append(
                            (tc, pre_decision, post_decision, tool_result, blocked)
                        )

                        tool_name = tc.name
                        if blocked:
                            yield f"\n\n🛡️ **[Tool Loop Guard]** {pre_decision.message if pre_decision else tool_result}\n"
                            parser.tool_responses.append(
                                f"<tool_response>\n{tool_result}\n</tool_response>"
                            )
                            continue

                        is_failed = isinstance(
                            tool_result, str
                        ) and tool_result.strip().startswith("Error")
                        is_approval_required = (
                            isinstance(tool_result, str)
                            and (
                                "[APPROVAL REQUIRED]" in tool_result
                                or "WAITING_FOR_USER_APPROVAL" in tool_result
                            )
                            and tool_name
                            in ["run_command", "ask_question", "plan", "write_artifact"]
                        )
                        if is_approval_required:
                            requires_approval_break = True

                        if is_approval_required:
                            status_icon = "✋"
                        elif is_failed or (
                            post_decision
                            and (
                                post_decision.action == "warn"
                                or post_decision.should_halt
                            )
                        ):
                            status_icon = "❌"
                        else:
                            status_icon = "✅"

                        # Gemini Antigravity 도구 메타데이터 출력 지원
                        tool_summary = (
                            tc.arguments.get("toolSummary", "")
                            if isinstance(tc.arguments, dict)
                            else ""
                        )
                        tool_action = (
                            tc.arguments.get("toolAction", "")
                            if isinstance(tc.arguments, dict)
                            else ""
                        )
                        display_name = (
                            f"{tool_action} - {tool_summary}"
                            if tool_action and tool_summary
                            else f"Executing <b>{tool_name}</b>"
                        )

                        yield '<details class="tool-card" style="margin: 10px 0; border: 1px solid #333; border-radius: 8px; background: rgba(0,0,0,0.2);">\n'
                        yield f'<summary style="padding: 8px; cursor: pointer; font-weight: bold; border-bottom: 1px solid #333;"><span class="icon">🛠️</span> {display_name} <span style="opacity:0.7; font-weight:normal; font-size:0.9em;">(Step {step+1}/{max_steps})</span> {status_icon}</summary>\n'
                        yield '<div style="padding: 10px;">\n'

                        if post_decision and post_decision.action == "warn":
                            tool_result = append_guardrail_guidance(
                                tool_result, post_decision
                            )
                            yield f"\n⚠️ {post_decision.message}\n"
                        elif post_decision and post_decision.should_halt:
                            tool_result = append_guardrail_guidance(
                                tool_result, post_decision
                            )
                            yield f"\n\n🛡️ **[Tool Loop Guard]** {post_decision.message}\n"

                        result_preview = (
                            tool_result[:1500]
                            if isinstance(tool_result, str) and len(tool_result) > 1500
                            else tool_result
                        )
                        yield f"\n```\n{result_preview}\n```\n"
                        yield "</div>\n</details>\n\n"

                        parser.tool_responses.append(
                            f"<tool_response>\n{tool_result}\n</tool_response>"
                        )

            if tool_executed:
                # 스트림이 모두 종료된 후, 컨텍스트(prompt 및 shaped_messages)를 갱신
                # Context Scrubbing: 로컬 모델이 <tool_call> 전에 출력한 불필요한 대화(Pre-fill fluff)를 제거
                import re
                tool_call_blocks = re.findall(r"(<tool_call>.*?</tool_call>)", full_response, re.DOTALL)
                clean_assistant_content = "\n".join(tool_call_blocks) if tool_call_blocks else full_response

                all_tool_responses = "\n".join(getattr(parser, "tool_responses", []))
                prompt += clean_assistant_content + "\n" + all_tool_responses + "\nAssistant: "

                # API 전송용 raw_messages에도 반영
                shaped_messages.append({"role": "assistant", "content": clean_assistant_content})
                shaped_messages.append({"role": "user", "content": all_tool_responses})

                # Planning Mode 및 Tool Guardrail 승인 대기 지원
                if requires_approval_break:
                    yield "\n\n✋ **[APPROVAL REQUIRED]** 사용자의 승인을 대기합니다. (계획안 검토 후 승인/거절을 결정해 주세요.)\n"
                    break

                continue
            break
        else:
            # max_steps에 도달 — 하드 리밋 경고
            yield f"\n\n⚠️ **[Step Limit]** 최대 도구 호출 횟수({max_steps})에 도달했습니다. 작업을 종료합니다.\n"

        # 반환값은 Generator지만, 파이프라인에서 이전 결과를 받기 위해 내부적으로 저장
        self._last_agent_output = full_output

        # ─── E-1: 인지 루프 성찰 (Reflect) ───
        try:
            user_task = messages[-1].get("content", "") if messages else ""
            self.cognitive_loop.reflect(user_task, full_output)
            anti_patterns = self.cognitive_loop.get_anti_patterns()
            if anti_patterns:
                logger.info(
                    f"[CognitiveLoop] Anti-patterns detected: {len(anti_patterns)}"
                )
        except Exception as e:
            logger.debug(f"Reflection error: {e}")

        # ─── E-5: 품질 검증 게이트 ───
        try:
            quality = self.quality_gate.evaluate(
                task_type,
                messages[-1].get("content", "") if messages else "",
                full_output,
            )
            if quality.user_message:
                yield f"\n{quality.user_message}\n"
            if quality.should_retry and quality.feedback:
                self.quality_gate.mark_retry()
                retry_messages = list(shaped_messages)
                retry_messages.extend(
                    [
                        {"role": "assistant", "content": full_output},
                        {
                            "role": "user",
                            "content": (
                                f"{quality.feedback}\n"
                                "도구를 새로 호출하지 말고, 위 문제만 수정해 최종 답변을 한국어로 다시 작성하세요."
                            ),
                        },
                    ]
                )
                retry_prompt = self._rebuild_prompt(
                    system_prompt
                    + "\n\n[QUALITY RETRY] Rewrite the final answer only. Do not call tools.",
                    "",
                    skill_prompts,
                    retry_messages,
                )
                retry_output = ""
                try:
                    for chunk in self.manager.stream_generate(
                        retry_prompt,
                        delegate_model,
                        temperature=0.2,
                    ):
                        retry_output += str(chunk)
                        yield str(chunk)
                    if retry_output.strip():
                        full_output = retry_output
                        self._last_agent_output = full_output
                except Exception as retry_error:
                    logger.warning(f"Quality retry failed: {retry_error}")
            if quality.grade.value in ("retry", "fail"):
                logger.warning(
                    f"[QualityGate] Grade={quality.grade.value}, score={quality.score}"
                )
        except Exception as e:
            logger.debug(f"QualityGate error: {e}")

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
            recalled = self.memory_manager.prefetch_all(user_text)
            if recalled:
                messages = list(messages)  # 원본 불변
                messages.insert(
                    1 if len(messages) > 1 else 0,
                    {"role": "system", "content": f"[Recalled Memory]\n{recalled}"},
                )
        except Exception as e:
            logger.debug(f"Memory prefetch error: {e}")

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
                self.memory_manager.sync_all(
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
