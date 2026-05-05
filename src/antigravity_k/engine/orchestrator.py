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
import json
import logging
import os
import re
import yaml
from typing import List, Dict, Any, Generator, Optional, Union

from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.engine.skill_loader import SkillLoader
from antigravity_k.engine.context_shaper import ContextShaper
from antigravity_k.engine.session_manager import SessionManager
from antigravity_k.engine.ide_sync import IDEContextManager
from antigravity_k.engine.slash_commands import SlashCommandRegistry
from antigravity_k.engine.tool_call_parser import ToolCallParser, EventType
from antigravity_k.engine.tool_guardrails import (
    ToolCallGuardrailController,
    ToolCallGuardrailConfig,
    append_guardrail_guidance,
    guardrail_synthetic_result,
)
from antigravity_k.engine.error_classifier import classify_api_error
from antigravity_k.engine.knowledge import KIEngine
from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.engine.ceo_analyzer import ceo_analyze as _ceo_analyze_fn
from antigravity_k.engine.autonomous_learner import AutonomousLearner
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.state_graph import StateContext
from antigravity_k.engine.stream_processor import StreamProcessor
from antigravity_k.engine.memory_recorder import MemoryRecorder
from antigravity_k.engine.agent_loop import (
    StepContext, NudgeDetector, ParseErrorGuard,
)

logger = logging.getLogger("antigravity_k.orchestrator")

# ─── 역할별 시스템 프롬프트 (간결 버전) ─────────────────────────────

ROLE_PROMPTS = {
    "CEO": (
        "You are the CEO/Orchestrator of Antigravity-K. "
        "Analyze the user's request and determine the best task_type among: "
        "[simple_chat, coding, reasoning, review, design, complex, debate]. "
        "Based on the task_type, return ONLY a JSON object (no markdown, no explanation) with these fields:\n\n"
        "1) For single-step tasks (simple_chat, coding, reasoning, review, design):\n"
        '{"task_type": "<type>", "delegate_to": "<ROLE>", "confidence": "high|medium|low", "reasoning": "...", "refined_prompt": "..."}\n'
        "Roles: WORKER(coding), ENG_MANAGER(reasoning), QA(review), DESIGNER(design), SELF(simple_chat).\n\n"
        "2) For multi-step tasks (complex):\n"
        '{"task_type": "complex", "confidence": "high|medium|low", "pipeline": [{"step": 1, "agent": "ARCHITECT", "task": "..."}, {"step": 2, "agent": "WORKER", "task": "..."}, {"step": 3, "agent": "QA", "task": "..."}], "reasoning": "..."}\n\n'
        "3) For controversial or deep discussion tasks (debate):\n"
        '{"task_type": "debate", "confidence": "high|medium|low", "reasoning": "...", "debate_topic": "..."}\n\n'
        "4) For AGI Core requests (scout new models, train, fine-tune):\n"
        '{"task_type": "agi_core", "sub_type": "scout or train", "reasoning": "..."}\n\n'
        "5) For hardware upgrade reports or system capability analysis:\n"
        '{"task_type": "hardware_report", "reasoning": "..."}\n\n'
        "IMPORTANT: Output raw JSON only. Include 'confidence' field. /no_think"
    ),
    "WORKER": (
        "You are a Senior Software Engineer and a trusted partner to the user.\n"
        "Core Principles:\n"
        "1. VERIFY before delivering — always test/validate your output\n"
        "2. Be HONEST about uncertainty — say 'I\'m not sure' when appropriate\n"
        "3. EXPLAIN your reasoning — the user should understand WHY\n"
        "4. LEARN from mistakes — never repeat the same error twice\n"
        "5. PROACTIVELY suggest improvements the user didn't ask for\n"
        "Write clean, modular, well-documented code. Use available tools. "
        "Always respond in Korean. /no_think"
    ),
    "ENG_MANAGER": (
        "You are the Engineering Manager and the user's strategic thinking partner.\n"
        "You excel at deep technical reasoning, system architecture, and implementation plans.\n"
        "Always verify your analysis against reality before presenting conclusions.\n"
        "If uncertain, state your assumptions explicitly. Always respond in Korean. /no_think"
    ),
    "QA": (
        "You are a strict but fair QA Engineer who protects the user's codebase quality.\n"
        "Review for logic errors, security issues, and performance bottlenecks.\n"
        "Provide actionable feedback with specific fix suggestions, not just problem descriptions.\n"
        "Always respond in Korean. /no_think"
    ),
    "DESIGNER": (
        "You are an expert UI/UX Designer who creates premium, modern interfaces.\n"
        "Provide feedback on visual elements, color palettes, spacing, typography, and micro-animations.\n"
        "Always explain the WHY behind design decisions. Always respond in Korean. /no_think"
    ),
    "ARCHITECT": (
        "You are the Chief System Architect and the user's long-term technical advisor.\n"
        "Design the foundation, abstractions, and big picture with scalability and maintainability.\n"
        "Always consider edge cases and failure modes. Present trade-offs honestly.\n"
        "Always respond in Korean. /no_think"
    ),
    "PROPOSER": (
        "You are a Solution Proposer. Construct the most optimal, logical, and robust initial solution to a given problem. "
        "Always respond in Korean. /no_think"
    ),
    "CRITIC": (
        "You are a Solution Critic. Critically analyze proposals. Hunt for edge cases, security vulnerabilities, performance bottlenecks, and logical flaws. "
        "Provide concrete suggestions on how to fix issues. "
        "Always respond in Korean. /no_think"
    ),
    "ARBITER": (
        "You are the Debate Arbiter. Objectively analyze the debate between the PROPOSER and the CRITIC. "
        "Weigh the pros and cons, resolve conflicts, and construct the final, optimal, and highly secure consensus solution. "
        "Always respond in Korean. /no_think"
    ),
    "DEFAULT": (
        "You are Antigravity-K, the user's trusted AI partner.\n"
        "You grow together with the user, learning from every interaction.\n"
        "Be honest about what you know and don't know.\n"
        "Proactively suggest improvements and anticipate the user's needs.\n"
        "Answer directly, concisely, and always in Korean. /no_think"
    ),
}


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

    def __init__(self, model_manager, vault_engine=None, project_root=None, tool_registry=None):
        self.manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root or os.getcwd()

        self.ctx = EngineContext(
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

    def _get_model_for_role(self, role: str) -> str:
        """역할에 맞는 모델을 반환합니다. config.yaml 매핑 우선."""
        return self.agent_models.get(role, self.agent_models.get("default", "qwen3.6:latest"))

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
            "- Output ONLY ONE tool_call per message.\n"
            "- Wait for the <tool_response> before making another tool call.\n"
            "- If no tool is needed, just answer directly without any tool_call or scratch_pad tags.\n\n"
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
        for schema in self.tool_registry.to_llm_schemas():
            params = schema.get('input_schema', {})
            required = params.get('required') or []
            tool_section += f"- **{schema['name']}**: {schema['description']}\n"
            props = params.get('properties') or {}
            if props:
                param_strs = []
                for k, v in props.items():
                    p_type = v.get("type", "any")
                    p_req = "required" if k in required else "optional"
                    param_strs.append(f"{k} ({p_type}, {p_req})")
                tool_section += f"  Parameters: {', '.join(param_strs)}\n"
        return tool_section

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """ToolExecutor에 위임합니다. (I-1 리팩터링)"""
        return self._tool_executor.execute(name, args)

    @property
    def _consecutive_errors(self):
        return self._tool_executor._consecutive_errors

    @_consecutive_errors.setter
    def _consecutive_errors(self, value):
        self._tool_executor._consecutive_errors = value

    def _register_claw_tools(self):
        """ToolExecutor에 위임합니다. (I-1 리팩터링)"""
        self._tool_executor.register_default_tools()

    # ─── CEO 분석 단계 ─────────────────────────────────────────────────

    def _ceo_analyze(self, user_message: str, target_model: str) -> Generator[Union[str, dict], None, None]:
        """CEO 분석을 ceo_analyzer 모듈에 위임합니다. (I-1 리팩터링)"""
        yield from _ceo_analyze_fn(
            user_message=user_message,
            target_model=target_model,
            ceo_prompt_template=ROLE_PROMPTS['CEO'],
            get_model_for_role_fn=self._get_model_for_role,
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

    def _run_single_agent(self, messages: List[Dict[str, str]], delegate_to: str, task_type: str, max_steps: int = 15) -> Generator[str, None, None]:
        delegate_model = self._get_model_for_role(delegate_to)
        if hasattr(self, 'manager') and not self.manager.is_loaded(delegate_model):
            yield f"\n\n*(🚀 `{delegate_model}` 모델을 VRAM에 로드 중입니다. 모델 크기에 따라 1~3분이 소요될 수 있습니다...)*\n\n"
        system_prompt = ROLE_PROMPTS.get(delegate_to, ROLE_PROMPTS["DEFAULT"])
        tool_prompt = self._build_tool_prompt() if delegate_to != "CEO" else ""
        
        # 턴 시작 시 에러 카운터 리셋 (이전 턴의 에러가 이월되지 않도록)
        self._consecutive_errors = 0
        
        # ─── E-1: 인지 루프 초기화 ───
        self.cognitive_loop.reset()
        self.quality_gate.reset()
        
        # ─── E-3: 실패 학습 컨텍스트 주입 ───
        failure_context = self.failure_memory.build_prompt(messages[-1].get('content', '') if messages else '')
        
        # Skill injection
        skill_prompts = self.skill_loader.get_active_prompts() if hasattr(self, 'skill_loader') else ""
        
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

        logger.info(f"Delegate: role={delegate_to}, model={delegate_model}, task_type={task_type}")

        # ─── Tool Loop Guardrail (Hermes 패턴) ───
        self.tool_guardrail.reset_for_turn()
        _WARN_STEP = max(max_steps - 3, max_steps // 2)  # 경고 시작 스텝

        full_output = ""
        for step in range(max_steps):
            parser = ToolCallParser()
            full_response = ""
            tool_executed = False
            in_think_block = False
            
            # 스텝 경고: 남은 스텝이 적으면 에이전트에게 알림
            if step >= _WARN_STEP:
                remaining = max_steps - step
                prompt += f"\n[SYSTEM WARNING] You have only {remaining} tool call steps remaining. Wrap up your work and provide your final answer.\n"

            # /no_think 플래그가 포함되어 있으면 특정 모델(Qwen)이 즉시 종료하는 버그 방지
            clean_sys_prompt = system_prompt.replace("/no_think", "").replace("System:", "").strip()
            final_sys_prompt = f"{clean_sys_prompt}\n{tool_prompt}".strip()
            
            try:
                stream = self.manager.stream_generate(
                    prompt=prompt, 
                    target=delegate_model,
                    raw_messages=shaped_messages,
                    system_prompt=final_sys_prompt
                )
                for chunk in stream:
                    full_response += chunk
                    for event in parser.feed(chunk):
                        if event.type == EventType.TEXT:
                            text = event.data
                            output = ""
                            i = 0
                            while i < len(text):
                                if in_think_block:
                                    end_idx = text.find('</think>', i)
                                    if end_idx != -1:
                                        output += text[i:end_idx] + "\n\n--- *End of Thinking* ---\n\n"
                                        i = end_idx + len('</think>')
                                        in_think_block = False
                                    else:
                                        output += text[i:]
                                        break
                                else:
                                    start_idx = text.find('<think>', i)
                                    if start_idx != -1:
                                        output += text[i:start_idx] + "\n\n--- *Thinking Process* ---\n\n"
                                        i = start_idx + len('<think>')
                                        in_think_block = True
                                    else:
                                        output += text[i:]
                                        break
                            if output:
                                yield output
                                full_output += output

                        elif event.type == EventType.TOOL_CALL_START:
                            yield "\n🔧 "

                        elif event.type == EventType.TOOL_CALL_COMPLETE:
                            tool_name = event.tool_call.name
                            tool_args = event.tool_call.arguments
                            
                            # ── Before-call 가드레일 (Hermes 패턴) ──
                            pre_decision = self.tool_guardrail.before_call(tool_name, tool_args)
                            if not pre_decision.allows_execution:
                                # 차단: 합성 에러 결과 주입
                                logger.warning(f"🛡️ Guardrail blocked: {pre_decision.code} ({tool_name})")
                                yield f"\n\n🛡️ **[Tool Loop Guard]** {pre_decision.message}\n"
                                synthetic = guardrail_synthetic_result(pre_decision)
                                parser.tool_responses.append(f"<tool_response>\n{synthetic}\n</tool_response>")
                                if pre_decision.should_halt:
                                    tool_executed = False
                                    break
                                tool_executed = True
                                continue
                            
                            
                            tool_result = self._execute_tool(tool_name, tool_args)
                            
                            
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
                            is_failed = isinstance(tool_result, str) and tool_result.strip().startswith("Error")
                            post_decision = self.tool_guardrail.after_call(
                                tool_name, tool_args, tool_result, failed=is_failed
                            )
                            
                            status_icon = "❌" if is_failed or post_decision.action == "warn" or post_decision.should_halt else "✅"
                            yield f"<details class=\"tool-card\" style=\"margin: 10px 0; border: 1px solid #333; border-radius: 8px; background: rgba(0,0,0,0.2);\">\n"
                            yield f"<summary style=\"padding: 8px; cursor: pointer; font-weight: bold; border-bottom: 1px solid #333;\"><span class=\"icon\">🛠️</span> Executing <b>{tool_name}</b> <span style=\"opacity:0.7; font-weight:normal; font-size:0.9em;\">(Step {step+1}/{max_steps})</span> {status_icon}</summary>\n"
                            yield "<div style=\"padding: 10px;\">\n"

                            # 경고 메시지 주입
                            if post_decision.action == "warn":
                                tool_result = append_guardrail_guidance(tool_result, post_decision)
                                yield f"\n⚠️ {post_decision.message}\n"
                            elif post_decision.should_halt:
                                logger.warning(f"🛡️ Guardrail halt: {post_decision.code} ({tool_name})")
                                tool_result = append_guardrail_guidance(tool_result, post_decision)
                                yield f"\n\n🛡️ **[Tool Loop Guard]** {post_decision.message}\n"
                            
                            result_preview = tool_result[:1500] if len(str(tool_result)) > 1500 else tool_result
                            yield f"\n```\n{result_preview}\n```\n"
                            yield "</div>\n</details>\n\n"
                            
                            # 응답 블록을 저장 (스트림 종료 후 한번에 추가하기 위함)
                            parser.tool_responses.append(f"<tool_response>\n{tool_result}\n</tool_response>")
                            
                            if post_decision.should_halt:
                                tool_executed = False
                                break
                            tool_executed = True

                        elif event.type == EventType.TOOL_CALL_ERROR:
                            logger.warning(f"Tool call parse error: {event.data}")
                            error_msg = f"[TOOL CALL PARSE ERROR] Please check your JSON syntax. Details: {event.data}"
                            yield f"\n\n⚠️ **{error_msg}**\n"
                            
                            parser.tool_responses.append(f"<tool_response>\n{error_msg}\n</tool_response>")
                            tool_executed = True

                for event in parser.flush():
                    if event.type == EventType.TEXT:
                        text = event.data
                        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
                        if '<think>' in text:
                            text = text[:text.index('<think>')]
                        if text.strip():
                            yield text
                            full_output += text
            except Exception as e:
                # ── API 에러 분류 (Hermes 패턴) ──
                classified = classify_api_error(
                    e, provider="ollama", model=delegate_model,
                    approx_tokens=len(prompt) // 4,
                )
                logger.error(
                    f"Error during stream generation: {classified.reason.value} "
                    f"(retryable={classified.retryable}, compress={classified.should_compress})",
                    exc_info=True,
                )
                
                if classified.should_compress:
                    yield f"\n\n⚠️ **컨텍스트 초과 감지** — 자동 압축을 시도합니다...\n"
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

            if tool_executed:
                # 스트림이 모두 종료된 후, 컨텍스트(prompt 및 shaped_messages)를 갱신
                all_tool_responses = "\n".join(getattr(parser, "tool_responses", []))
                prompt += full_response + "\n" + all_tool_responses + "\nAssistant: "
                
                # API 전송용 raw_messages에도 반영
                shaped_messages.append({"role": "assistant", "content": full_response})
                shaped_messages.append({"role": "user", "content": all_tool_responses})
                
                # Planning Mode 지원: 아티팩트 피드백 요청 시 루프를 일시 중지
                if "WAITING_FOR_USER_APPROVAL" in all_tool_responses:
                    yield "\n\n✋ **[PLANNING MODE]** 사용자의 승인을 대기합니다. (계획안 검토 후 승인/거절을 결정해 주세요.)\n"
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
            reflection = self.cognitive_loop.reflect(user_task, full_output)
            anti_patterns = self.cognitive_loop.get_anti_patterns()
            if anti_patterns:
                logger.info(f"[CognitiveLoop] Anti-patterns detected: {len(anti_patterns)}")
        except Exception as e:
            logger.debug(f"Reflection error: {e}")
        
        # ─── E-5: 품질 검증 게이트 ───
        try:
            quality = self.quality_gate.evaluate(task_type, 
                messages[-1].get("content", "") if messages else "", full_output)
            if quality.user_message:
                yield f"\n{quality.user_message}\n"
            if quality.grade.value in ("retry", "fail"):
                logger.warning(f"[QualityGate] Grade={quality.grade.value}, score={quality.score}")
        except Exception as e:
            logger.debug(f"QualityGate error: {e}")

    def run_stream(self, messages: List[Dict[str, str]], target_model: str, max_steps: int = 15, ephemeral_message: Optional[str] = None) -> Generator[str, None, None]:
        """
        State Graph 기반 멀티 에이전트 스트리밍 실행.
        
        기존의 레거시 선형 루프를 완전히 폐기하고, 
        내부를 명시적 상태 전이 그래프(AgentStateGraph)로 단일화하여 실행합니다.
        """
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
        """동기식 실행 (커맨드 팔레트 등에서 사용)."""
        result = []
        for chunk in self.run_stream(messages, target_model, max_steps):
            result.append(chunk)
        return "".join(result)
