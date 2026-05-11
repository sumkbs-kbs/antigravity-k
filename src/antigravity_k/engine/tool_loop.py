import asyncio
from typing import List, Dict, Generator
from antigravity_k.engine.tool_call_parser import EventType
from antigravity_k.engine.error_classifier import classify_api_error
from antigravity_k.engine.tool_guardrails import append_guardrail_guidance, guardrail_synthetic_result

from antigravity_k.engine.logging_util import get_structured_logger
logger = get_structured_logger(__name__)

class ToolLoopEngine:
    """
    Orchestrator에서 분리된 도구 실행 루프(Tool Loop) 관리 엔진.
    
    책임:
    - LLM 스트림 파싱 및 도구 호출 감지
    - 도구 병렬 실행 (asyncio 기반)
    - 도구 실행 결과 및 Guardrail 판정의 컨텍스트 병합
    """
    
    def __init__(self, orchestrator):
        self.orch = orchestrator

    def run_loop(
        self,
        messages: List[Dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int = 15,
        target_model: str = None,
    ) -> Generator[str, None, None]:
        
        # 내부 상태 및 의존성 복사
        (
            _,  # We determine delegate_model below
            system_prompt_part,
            tool_prompt_part,
            skill_prompts_part,
            prompt_str,
            shaped_messages,
        ) = self.orch._prepare_agent_prompt(messages, delegate_to, task_type)

        if delegate_to == "SELF" and target_model and target_model != "default":
            delegate_model = target_model
        else:
            # If target_model is 'default', resolve it to the actual default model for the role
            delegate_model = self.orch._get_model_for_role(delegate_to)
        
        system_prompt = self.orch.manager.get_system_prompt() if hasattr(self.orch.manager, "get_system_prompt") else ""
        tool_prompt = self.orch.manager.get_tool_prompt() if hasattr(self.orch.manager, "get_tool_prompt") else ""
        skill_prompts = getattr(self.orch, "_skill_prompts_cache", "")
        # We use prompt_str for the prompt to stream_generate
        
        full_output = ""
        step = 0
        
        while step < max_steps:
            step += 1
            if not self.orch.manager.is_loaded(delegate_model):
                logger.error(f"No model {delegate_model} is loaded to execute.")
                yield f"\n❌ **모델({delegate_model})이 로드되지 않았습니다.**\n"
                return

            if self.orch.ctx.tool_guardrail and hasattr(self.orch.ctx.tool_guardrail, "reset"):
                self.orch.ctx.tool_guardrail.reset()
                
            from antigravity_k.engine.capacity_flow import CapacityAction
            if hasattr(self.orch, "_capacity_checkpoint"):
                decision = self.orch._capacity_checkpoint.check_step_budget(step, max_steps)
                action = decision.action
                if action == CapacityAction.HALT:
                    yield "\n\n⚠️ **[Capacity Limit]** 시스템 리소스 보호를 위해 작업을 중단합니다.\n"
                    return
                elif action == CapacityAction.WARN or action == CapacityAction.COMPRESS:
                    yield "\n\n📉 **[Capacity Warning]** 시스템 리소스 압박으로 성능이 저하될 수 있습니다.\n"

            stream_gen = self.orch.manager.stream_generate(
                prompt=prompt_str, target=delegate_model, task_type=task_type
            )
            
            from antigravity_k.engine.stream_processor import StreamProcessor
            from antigravity_k.engine.tool_call_parser import ToolCallParser, EventType
            
            stream_proc = StreamProcessor()
            tool_parser = ToolCallParser()
            
            full_response = ""
            pending_tool_calls = []
            
            requires_approval_break = False
            tool_executed = False

            try:
                for chunk in stream_gen:
                    chunk_str = str(chunk)
                    full_response += chunk_str
                    
                    events = tool_parser.feed(chunk_str)
                    for event in events:
                        if event.type == EventType.TEXT:
                            cleaned_text, is_repeat = stream_proc.process_text(event.data)
                            if cleaned_text:
                                yield cleaned_text
                                full_output += cleaned_text
                        elif event.type == EventType.TOOL_CALL_COMPLETE:
                            tool_name = event.tool_call.name
                            tool_args = event.tool_call.arguments
                            
                            try:
                                from antigravity_k.engine.event_bus import global_event_bus
                                global_event_bus.publish("ToolExecutionStarted", name=tool_name)
                            except Exception:
                                pass

                            # Pre-call guardrail
                            pre_decision = self.orch.ctx.tool_guardrail.before_call(tool_name, tool_args)
                            if not pre_decision.allows_execution:
                                yield f"\n\n🛡️ **[Guardrail]** {pre_decision.message}\n"
                            
                            pending_tool_calls.append(event.tool_call)

                # Flush parser and stream
                events = tool_parser.flush()
                for event in events:
                    if event.type == EventType.TEXT:
                        cleaned_text, is_repeat = stream_proc.process_text(event.data)
                        if cleaned_text:
                            yield cleaned_text
                            full_output += cleaned_text
                    elif event.type == EventType.TOOL_CALL_COMPLETE:
                        pending_tool_calls.append(event.tool_call)

                processed = stream_proc.process_flush_text("")
                if processed and processed.strip():
                    yield processed
                    full_output += processed

            except Exception as e:
                classified = classify_api_error(
                    e,
                    provider="ollama",
                    model=delegate_model,
                    approx_tokens=len(prompt_str) // 4,
                )
                logger.error(f"Error during stream generation: {e}", exc_info=True)
                
                if classified.should_compress:
                    yield "\n\n⚠️ **컨텍스트 초과 감지** — 자동 압축을 시도합니다...\n"
                    if hasattr(self.orch, "context_shaper"):
                        shaped_messages = self.orch.context_shaper.shape(shaped_messages, force_compact=True)
                    prompt_str = self.orch._rebuild_prompt(system_prompt, tool_prompt, skill_prompts, shaped_messages)
                    continue
                elif classified.retryable and step < max_steps - 1:
                    yield f"\n\n⚠️ **일시적 오류** ({classified.reason.value}) — 재시도합니다...\n"
                    continue
                else:
                    yield f"\n\n❌ **에이전트 실행 오류**: {str(e)}\n"
                    return

            if pending_tool_calls:
                yield f"\n\n🚀 **[{len(pending_tool_calls)}개의 도구 비동기 병렬 실행 시작]**\n"
                
                # Phase 2: Async Execution Batching
                results_collected = []
                
                async def _run_tool_task_async(tc):
                    tool_name = tc.name
                    tool_args = tc.arguments
                    
                    try:
                        from antigravity_k.engine.event_bus import global_event_bus
                        global_event_bus.publish("ToolExecutionStarted", name=tool_name)
                    except Exception:
                        pass
                        
                    pre_decision = self.orch.ctx.tool_guardrail.before_call(tool_name, tool_args)
                    if not pre_decision.allows_execution:
                        synthetic = guardrail_synthetic_result(pre_decision)
                        try:
                            from antigravity_k.engine.event_bus import global_event_bus
                            global_event_bus.publish("ToolExecutionFinished", name=tool_name)
                        except Exception:
                            pass
                        return tc, pre_decision, None, synthetic, True
                        
                    # Execute tool asynchronously via ToolExecutor
                    tool_result = await self.orch.ctx.tool_executor.execute_async(tool_name, tool_args)
                    
                    try:
                        from antigravity_k.engine.event_bus import global_event_bus
                        global_event_bus.publish("ToolExecutionFinished", name=tool_name)
                    except Exception:
                        pass
                        
                    # CognitiveLoop Verify
                    try:
                        if hasattr(self.orch, "cognitive_loop") and self.orch.ctx.cognitive_loop:
                            self.orch.ctx.cognitive_loop.verify_tool_result(tool_name, tool_args, str(tool_result))
                    except Exception as ve:
                        logger.debug(f"Cognitive verification error: {ve}")
                        
                    post_decision = self.orch.ctx.tool_guardrail.after_call(
                        tool_name,
                        tool_args,
                        tool_result,
                        failed=(isinstance(tool_result, str) and tool_result.strip().startswith("Error")),
                    )
                    return tc, pre_decision, post_decision, tool_result, False

                # DAG 기반 도구 실행 그룹화 (waitForPreviousTools 처리)
                execution_batches = []
                current_batch = []
                for tc in pending_tool_calls:
                    wait_for_previous = False
                    if isinstance(tc.arguments, dict):
                        wait_for_previous = tc.arguments.get("waitForPreviousTools", False)
                    if wait_for_previous and current_batch:
                        execution_batches.append(current_batch)
                        current_batch = []
                    current_batch.append(tc)
                if current_batch:
                    execution_batches.append(current_batch)
                    
                for batch in execution_batches:
                    # Run the batch concurrently
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        tasks = [_run_tool_task_async(tc) for tc in batch]
                        batch_results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                    finally:
                        loop.close()
                    
                    # Error handling inside batch results
                    for idx, res in enumerate(batch_results):
                        if isinstance(res, Exception):
                            tc = batch[idx]
                            results_collected.append((tc, None, None, f"Exception: {res}", True))
                        else:
                            results_collected.append(res)
                
                # UI Formatting (Markdown rather than hardcoded raw HTML where possible)
                from antigravity_k.engine.tool_call_parser import ToolCallParser
                parser = ToolCallParser()
                parser.tool_responses = []
                
                for (tc, pre_decision, post_decision, tool_result, blocked) in results_collected:
                    tool_name = tc.name
                    if blocked:
                        yield f"\n> 🛡️ **[Tool Blocked]** {pre_decision.message if pre_decision else tool_result}\n"
                        parser.tool_responses.append(f"<tool_response>\n{tool_result}\n</tool_response>")
                        continue
                        
                    is_failed = isinstance(tool_result, str) and tool_result.strip().startswith("Error")
                    is_approval_required = (
                        isinstance(tool_result, str)
                        and ("[APPROVAL REQUIRED]" in tool_result or "WAITING_FOR_USER_APPROVAL" in tool_result)
                    )
                    if is_approval_required:
                        requires_approval_break = True
                        
                    if is_approval_required:
                        status_icon = "✋"
                    elif is_failed or (post_decision and (post_decision.action == "warn" or post_decision.should_halt)):
                        status_icon = "❌"
                    else:
                        status_icon = "✅"
                        
                    tool_summary = tc.arguments.get("toolSummary", "") if isinstance(tc.arguments, dict) else ""
                    tool_action = tc.arguments.get("toolAction", "") if isinstance(tc.arguments, dict) else ""
                    display_name = f"{tool_action} - {tool_summary}" if tool_action and tool_summary else f"Executing **{tool_name}**"

                    # Yield Markdown formatted response instead of HTML details/summary
                    yield f"\n> 🛠️ **{display_name}** (Step {step}/{max_steps}) {status_icon}\n"
                    
                    if post_decision and post_decision.action == "warn":
                        tool_result = append_guardrail_guidance(tool_result, post_decision)
                        yield f"> ⚠️ {post_decision.message}\n"
                    elif post_decision and post_decision.should_halt:
                        tool_result = append_guardrail_guidance(tool_result, post_decision)
                        yield f"\n> 🛡️ **[Tool Loop Guard]** {post_decision.message}\n"
                        
                    result_preview = tool_result[:1500] if isinstance(tool_result, str) and len(tool_result) > 1500 else tool_result
                    
                    yield f"> ```\n> {result_preview}\n> ```\n\n"
                    
                    parser.tool_responses.append(f"<tool_response>\n{tool_result}\n</tool_response>")
                    tool_executed = True

            if tool_executed:
                import re
                tool_call_blocks = re.findall(r"(<(?:tool_call|action_call)>.*?</(?:tool_call|action_call)>)", full_response, re.DOTALL)
                clean_assistant_content = "\n".join(tool_call_blocks) if tool_call_blocks else full_response
                
                all_tool_responses = "\n".join(getattr(parser, "tool_responses", []))
                prompt_str += clean_assistant_content + "\n" + all_tool_responses + "\nAssistant: "
                
                shaped_messages.append({"role": "assistant", "content": clean_assistant_content})
                shaped_messages.append({"role": "user", "content": all_tool_responses})
                
                if requires_approval_break:
                    yield "\n\n✋ **[APPROVAL REQUIRED]** 사용자의 승인을 대기합니다.\n"
                    break
                continue
            break
        else:
            yield f"\n\n⚠️ **[Step Limit]** 최대 도구 호출 횟수({max_steps})에 도달했습니다.\n"

        self.orch._last_agent_output = full_output
        
        # Post-loop checks (Cognitive, QualityGate, DecisionAnchor, ALDA)
        try:
            user_task = messages[-1].get("content", "") if messages else ""
            if hasattr(self.orch, "cognitive_loop") and self.orch.ctx.cognitive_loop:
                self.orch.ctx.cognitive_loop.reflect(user_task, full_output)
        except Exception as e:
            logger.debug(f"Reflection error: {e}")
            
        try:
            if hasattr(self.orch, "quality_gate") and self.orch.ctx.quality_gate:
                quality = self.orch.ctx.quality_gate.evaluate(task_type, user_task, full_output)
                if quality.user_message:
                    yield f"\n{quality.user_message}\n"
                if quality.should_retry and quality.feedback:
                    self.orch.ctx.quality_gate.mark_retry()
                    # For simplicity, we skip inner retry here, deferring it to orchestrator handlers or quality gate loop
        except Exception as e:
            logger.debug(f"QualityGate error: {e}")
            
        try:
            if hasattr(self.orch, "ctx") and hasattr(self.orch.ctx, "decision_anchor"):
                candidate = self.orch.ctx.decision_anchor.auto_extract(user_task, full_output)
                if candidate:
                    self.orch.ctx.decision_anchor.add(
                        decision=candidate["decision"],
                        category=candidate["category"],
                        priority=5,
                        source="auto"
                    )
        except Exception:
            pass
            
        try:
            from antigravity_k.engine.event_bus import global_event_bus
            global_event_bus.publish(
                "AgentTurnCompleted",
                user_message=user_task,
                assistant_response=full_output,
                project_root=self.orch.project_root,
            )
        except Exception:
            pass
