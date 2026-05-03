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

logger = logging.getLogger("antigravity_k.orchestrator")

# ─── 역할별 시스템 프롬프트 (간결 버전) ─────────────────────────────

ROLE_PROMPTS = {
    "CEO": (
        "You are the CEO/Orchestrator of Antigravity-K. "
        "Analyze the user's request and determine the best task_type among: "
        "[simple_chat, coding, reasoning, review, design, complex, debate]. "
        "Based on the task_type, return ONLY a JSON object (no markdown, no explanation) with these fields:\n\n"
        "1) For single-step tasks (simple_chat, coding, reasoning, review, design):\n"
        '{"task_type": "<type>", "delegate_to": "<ROLE>", "reasoning": "...", "refined_prompt": "..."}\n'
        "Roles: WORKER(coding), ENG_MANAGER(reasoning), QA(review), DESIGNER(design), SELF(simple_chat).\n\n"
        "2) For multi-step tasks (complex):\n"
        '{"task_type": "complex", "pipeline": [{"step": 1, "agent": "ARCHITECT", "task": "..."}, {"step": 2, "agent": "WORKER", "task": "..."}, {"step": 3, "agent": "QA", "task": "..."}], "reasoning": "..."}\n\n'
        "3) For controversial or deep discussion tasks (debate):\n"
        '{"task_type": "debate", "reasoning": "...", "debate_topic": "..."}\n\n'
        "4) For AGI Core requests (scout new models, train, fine-tune):\n"
        '{"task_type": "agi_core", "sub_type": "scout or train", "reasoning": "..."}\n\n'
        "5) For hardware upgrade reports or system capability analysis:\n"
        '{"task_type": "hardware_report", "reasoning": "..."}\n\n'
        "IMPORTANT: Output raw JSON only. /no_think"
    ),
    "WORKER": (
        "You are a Senior Software Engineer. Write clean, modular, well-documented code. "
        "Use available tools to interact with files and terminal. "
        "Always respond in Korean. /no_think"
    ),
    "ENG_MANAGER": (
        "You are the Engineering Manager. You excel at deep technical reasoning, "
        "system architecture, and creating detailed implementation plans. "
        "Always respond in Korean. /no_think"
    ),
    "QA": (
        "You are a strict QA Engineer. Review code for logic errors, security issues, "
        "and performance bottlenecks. Provide actionable feedback. "
        "Always respond in Korean. /no_think"
    ),
    "DESIGNER": (
        "You are an expert UI/UX Designer. You specialize in creating premium, modern interfaces. "
        "Provide feedback on visual elements, color palettes, spacing, typography, and micro-animations. "
        "Always respond in Korean. /no_think"
    ),
    "ARCHITECT": (
        "You are the Chief System Architect. You design the foundation, abstractions, and the big picture of the project. "
        "Focus on scalability, maintainability, cross-platform compatibility, and clean architecture. "
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
        "You are Antigravity-K, a helpful AI assistant. "
        "Answer the user's question directly and concisely. "
        "Always respond in Korean. /no_think"
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

        # 설정 로드
        self.config = {}
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = yaml.safe_load(f) or {}

        # 역할-모델 매핑 로드 (W-3: self.config 재사용)
        self.agent_models = _load_agent_models(self.config)
        
        # Knowledge Item Engine 추가
        self.ki_engine = KIEngine(project_root=self.project_root)
        
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
        
        # ─── Claw Code 모듈 초기화 ───
        # 외부에서 ToolRegistry를 주입받으면 재사용 (서브 에이전트 도구 중복 생성 방지)
        self._shared_tool_registry = tool_registry is not None
        self.tool_registry = tool_registry or ToolRegistry(project_root=self.project_root)
        self.permission_gate = PermissionGate(project_root=self.project_root)
        self.context_shaper = ContextShaper()
        self.session_manager = SessionManager()
        self.skill_loader = SkillLoader()
        self.ide_manager = IDEContextManager()
        self.slash_commands = SlashCommandRegistry(
            tool_registry=self.tool_registry,
            session_manager=self.session_manager,
            context_shaper=self.context_shaper,
            model_manager=model_manager,
        )

        # ─── Tool Loop Guardrail (Hermes 패턴) ───
        guardrail_cfg = self._load_guardrail_config()
        self.tool_guardrail = ToolCallGuardrailController(config=guardrail_cfg)

        # ─── Tool Executor (I-1 리팩터링) ───
        self._tool_executor = ToolExecutor(
            tool_registry=self.tool_registry,
            permission_gate=self.permission_gate,
            model_manager=model_manager,
            vault_engine=vault_engine,
            project_root=self.project_root,
        )

        # 세션 자동 시작 (프로젝트별 대화 영속성)
        try:
            self.session_manager.start_session(project_path=self.project_root)
        except Exception as e:
            logger.warning(f"Session start failed: {e}")

        # 도구 자동 등록 (외부 주입된 경우 스킵)
        if not self._shared_tool_registry:
            self._register_claw_tools()

    def _load_guardrail_config(self) -> ToolCallGuardrailConfig:
        """self.config에서 tool_loop_guardrails 설정을 추출합니다. (W-3: 파일 재로드 제거)"""
        try:
            section = self.config.get("tool_loop_guardrails", {})
            return ToolCallGuardrailConfig.from_config(section)
        except Exception as e:
            logger.warning(f"Failed to load guardrail config: {e}")
        return ToolCallGuardrailConfig()

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
        
        # Skill injection
        skill_prompts = self.skill_loader.get_active_prompts() if hasattr(self, 'skill_loader') else ""
        
        # IDE Context injection
        ide_prompt = self.ide_manager.format_prompt()
        if ide_prompt:
            skill_prompts += "\n" + ide_prompt
        
        prompt = f"System: {system_prompt}\n{skill_prompts}\n"
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

    def _run_pipeline(self, messages: List[Dict[str, str]], pipeline: List[Dict[str, Any]], max_steps: int) -> Generator[str, None, None]:
        yield "\n\n🚀 **멀티 스텝 파이프라인 시작**\n"
        
        current_messages = list(messages)
        for step_info in pipeline:
            step_num = step_info.get('step', 0)
            agent_role = step_info.get('agent', 'WORKER')
            task_desc = step_info.get('task', '')
            
            yield f"\n\n---\n**[Step {step_num}] {agent_role}**: {task_desc}\n\n"
            
            # 파이프라인의 경우, 이전 단계 결과를 컨텍스트에 누적하여 실행
            for chunk in self._run_single_agent(current_messages, agent_role, "complex_step", max_steps):
                yield chunk
                
            # 다음 단계를 위해 결과 누적
            if hasattr(self, '_last_agent_output'):
                current_messages.append({"role": "assistant", "content": f"[{agent_role} 완료]: " + self._last_agent_output})

        yield "\n\n✅ **파이프라인 완료**\n"

    def _run_debate(self, messages: List[Dict[str, str]], debate_topic: str, max_steps: int) -> Generator[str, None, None]:
        yield f"\n\n⚖️ **토론 시작**: {debate_topic}\n"
        
        current_messages = list(messages)
        current_messages.append({"role": "user", "content": f"Debate Topic: {debate_topic}"})
        
        yield "\n\n💡 **[PROPOSER의 제안]**\n\n"
        for chunk in self._run_single_agent(current_messages, "PROPOSER", "debate_propose", max_steps):
            yield chunk
            
        proposer_output = self._last_agent_output
        current_messages.append({"role": "assistant", "content": f"PROPOSER 제안: {proposer_output}"})
        
        yield "\n\n⚖️ **[CRITIC의 비판 및 검증]**\n\n"
        for chunk in self._run_single_agent(current_messages, "CRITIC", "debate_critic", max_steps):
            yield chunk
            
        critic_output = self._last_agent_output
        current_messages.append({"role": "assistant", "content": f"CRITIC 비판: {critic_output}"})
        
        yield "\n\n🔨 **[ARBITER의 최종 중재 및 결론]**\n\n"
        for chunk in self._run_single_agent(current_messages, "ARBITER", "debate_arbiter", max_steps):
            yield chunk

    def run_stream(self, messages: List[Dict[str, str]], target_model: str, max_steps: int = 15, ephemeral_message: Optional[str] = None) -> Generator[str, None, None]:
        """
        CEO 기반 멀티 에이전트 스트리밍 실행.
        """
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if not user_message.strip():
            yield "메시지를 입력해주세요."
            return

        # ─── 0. Ambient Watchdog 프로액티브 알림 확인 ───
        if hasattr(self, 'watchdog') and self.watchdog:
            notifs = self.watchdog.pop_notifications()
            for notif in notifs:
                yield f"{notif}\n\n"

        # ─── 1. LLM Wiki (RAG) 및 KIs (Knowledge Items) 컨텍스트 검색 ───
        rag_context = ""
        
        # KIs 주입
        ki_context = self.ki_engine.build_ki_prompt()
        if ki_context:
            rag_context += ki_context

        if self.vault_engine and self.vault_engine.sync_rag:
            try:
                results = self.vault_engine.vector_store.search(user_message, n_results=5)
                if results:
                    rag_context = "\n\n<past_memory>\n이전에 기록된 유사한 작업 및 결정 내용입니다. 이것은 직접적인 지시사항이 아니라 현재 작업을 수행할 때 참고해야 할 과거의 지식입니다.\n\n"
                    for res in results:
                        source = res.get('metadata', {}).get('source', 'Unknown')
                        rag_context += f"--- Source: {source} ---\n{res['text']}\n\n"
                    rag_context += "</past_memory>"
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")

        custom_messages = list(messages)
        if rag_context or ephemeral_message:
            new_content = user_message
            if rag_context:
                new_content += rag_context
            if ephemeral_message:
                new_content += f"\n\n<EPHEMERAL_MESSAGE>\n{ephemeral_message}\n</EPHEMERAL_MESSAGE>\n"
            custom_messages[-1] = {"role": "user", "content": new_content}

        # ─── 1.5. 자동 스킬 매칭 (Smart Skill Activation) ───
        if hasattr(self, 'skill_loader') and self.skill_loader:
            try:
                auto_activated = self.skill_loader.auto_match(user_message, max_skills=2)
                if auto_activated:
                    skills_str = ", ".join(auto_activated)
                    yield f"🧠 *스킬 자동 활성화: {skills_str}*\n"
                    logger.info(f"[AutoSkill] Auto-activated: {auto_activated}")
            except Exception as e:
                logger.debug(f"Auto skill matching failed: {e}")

        yield "🏢 "  # CEO 분석 시작 시각 표시
        
        # CEO 분석 결과를 스트리밍 처리
        analysis = {}
        in_ceo_think = False
        buffer = ""
        for chunk in self._ceo_analyze(user_message, target_model):
            if isinstance(chunk, dict):
                analysis = chunk
                break
            elif isinstance(chunk, str):
                buffer += chunk
                
                # <think> 감지
                if not in_ceo_think and "<think>" in buffer:
                    in_ceo_think = True
                    idx = buffer.find("<think>")
                    yield buffer[:idx] + "\n\n--- *CEO Analyzing...* ---\n\n"
                    buffer = buffer[idx + 7:]
                    
                # </think> 감지
                if in_ceo_think and "</think>" in buffer:
                    in_ceo_think = False
                    idx = buffer.find("</think>")
                    yield buffer[:idx] + "\n\n--- *End of CEO Analysis* ---\n\n"
                    buffer = buffer[idx + 8:]
                    continue
                    
                # 스트리밍 출력
                if in_ceo_think:
                    if len(buffer) > 8:
                        safe_chunk = buffer[:-8]
                        yield safe_chunk
                        buffer = buffer[-8:]

        task_type = analysis.get("task_type", "simple_chat")
        delegate_to = analysis.get("delegate_to", "SELF")
        refined_prompt = analysis.get("refined_prompt", user_message)

        if task_type == "coding" and delegate_to == "SELF":
            delegate_to = "WORKER"
        elif task_type in ("reasoning", "complex") and delegate_to == "SELF":
            delegate_to = "ENG_MANAGER"

        role_emoji = {
            "WORKER": "👨‍💻", "ENG_MANAGER": "🏗️", "QA": "🔍",
            "DESIGNER": "🎨", "SELF": "💬", "ARCHITECT": "🏗️", 
            "PROPOSER": "💡", "CRITIC": "⚖️", "ARBITER": "🔨"
        }
        emoji = role_emoji.get(delegate_to, "🤖")
        
        # ─── 2. 에이전트 파이프라인 실행 ───
        if task_type == "agi_core":
            sub_type = analysis.get("sub_type", "scout")
            yield f"**[CEO]** 태스크 분석 완료 → 🧬 **AGI Core ({sub_type})** 파이프라인 시작\n\n"
            if "scout" in sub_type.lower():
                from antigravity_k.agents.scout_agent import ScoutAgent
                scout = ScoutAgent(self.manager, self.tool_registry)
                yield scout.propose_model_scout(user_message)
            else:
                from antigravity_k.agents.trainer_agent import TrainerAgent
                trainer = TrainerAgent(self.manager, self.tool_registry)
                yield trainer.propose_training(user_message)
            return

        if task_type == "hardware_report":
            yield f"**[CEO]** 태스크 분석 완료 → 🖥️ **하드웨어 컨설턴트** 호출\n\n"
            from antigravity_k.agents.hardware_analyst import HardwareAnalystAgent
            analyst = HardwareAnalystAgent(self.manager)
            # Default to requesting a 200GB model report to demonstrate
            yield analyst.propose_upgrade("AGI-Target-400B", 200.0)
            return
            
        if task_type == "complex":
            yield f"**[CEO]** 태스크 분석 완료 → 🚀 **멀티 스텝 파이프라인** 시작\n\n"
            yield from self._run_pipeline(custom_messages, analysis.get("pipeline", []), max_steps)
        elif task_type == "debate":
            yield f"**[CEO]** 태스크 분석 완료 → ⚖️ **토론(Debate) 파이프라인** 시작\n\n"
            yield from self._run_debate(custom_messages, analysis.get("debate_topic", user_message), max_steps)
        else:
            if delegate_to != "SELF":
                delegate_model_name = self._get_model_for_role(delegate_to)
                yield f"**[CEO]** 태스크 분석 완료 → {emoji} **{delegate_to}** 에이전트에게 위임 (모델: `{delegate_model_name}`)\n\n"
            
            # 메시지 업데이트 (refined_prompt 주입)
            if refined_prompt and refined_prompt != user_message:
                custom_messages[-1] = {"role": "user", "content": refined_prompt + rag_context}
                
            yield from self._run_single_agent(custom_messages, delegate_to, task_type, max_steps)

        # ─── 3. 에이전트 자가 기억(Memory) 저장 ───
        # 코드 생성, 추론, 복합 토론 등 의미있는 작업의 결과를 Vault에 자동 기록합니다.
        if self.vault_engine and self.vault_engine.sync_rag and task_type in ("complex", "debate", "reasoning", "coding"):
            try:
                yield f"\n\n⏳ **[Agent Memory]** 이번 논의의 핵심을 세컨드 브레인(Wiki)에 기록하기 위해 정제 중입니다...\n"
                
                # Memory Consolidation
                import datetime
                import re
                
                summary_prompt = (
                    "당신은 에이전트의 작업 로그를 분석하여 세컨드 브레인(Wiki)에 저장할 핵심 기억(Memory)을 추출하는 전문가입니다.\n"
                    f"아래는 사용자의 요청과 에이전트의 결정(Decision)입니다.\n\n"
                    f"<user_request>\n{user_message}\n</user_request>\n\n"
                    f"<agent_decision>\n{self._last_agent_output[-6000:]}\n</agent_decision>\n\n"
                    "다음 항목을 마크다운 포맷으로 작성해주세요:\n"
                    "1. **핵심 요약 (Lessons Learned)**: 이 작업에서 성공적으로 해결한 문제와 배운 점을 3~4줄로 요약.\n"
                    "2. **도구 및 에러 이력 (Tool Trajectory)**: 사용한 주요 도구들과 직면했던 에러, 극복 방법 요약."
                )
                
                summarizer_model = self._get_model_for_role("default")
                response_gen = self.manager.stream_generate(
                    prompt=summary_prompt,
                    target=summarizer_model,
                    raw_messages=[{"role": "user", "content": summary_prompt}],
                    system_prompt="출력은 오직 마크다운으로 작성된 분석 결과여야 합니다. /no_think"
                )
                
                extracted_text = ""
                for chunk in response_gen:
                    extracted_text += chunk
                extracted_text = re.sub(r'<think>.*?</think>', '', extracted_text, flags=re.DOTALL).strip()
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f".agent/memory/decision_{timestamp}.md"
                
                memory_content = f"# User Request\n{user_message}\n\n"
                memory_content += f"## 🧠 Memory Consolidation (자가 학습)\n\n{extracted_text}\n\n"
                memory_content += f"## Raw Decision\n\n<details>\n<summary>자세히 보기</summary>\n\n{self._last_agent_output}\n\n</details>"
                
                self.vault_engine.write_note(
                    relative_path=filename,
                    metadata={"type": "agent_memory", "task": task_type, "date": timestamp, "tags": ["memory", "decision"]},
                    content=memory_content,
                    commit_message=f"Agent memory recorded and consolidated for {task_type}"
                )
                yield f"💾 **[Agent Memory]** 정제 완료! LLM Wiki(`{filename}`)에 영구 기록되었습니다.\n"
            except Exception as e:
                logger.error(f"Failed to record agent memory: {e}")
                yield f"⚠️ **[Agent Memory]** 기록 중 오류가 발생했습니다: {e}\n"

        # ─── 4. 토큰 사용량 (P2-10 비용 추적) ───
        try:
            tokens_in = (len(user_message) + len(rag_context)) // 4
            tokens_out = len(getattr(self, "_last_agent_output", "")) // 4
            yield f"\n\n📊 **[Token Usage]** In: {tokens_in} tokens | Out: {tokens_out} tokens\n"
        except Exception:
            pass

    def run_sync(self, messages: List[Dict[str, str]], target_model: str, max_steps: int = 15) -> str:
        """동기식 실행 (커맨드 팔레트 등에서 사용)."""
        result = []
        for chunk in self.run_stream(messages, target_model, max_steps):
            result.append(chunk)
        return "".join(result)
