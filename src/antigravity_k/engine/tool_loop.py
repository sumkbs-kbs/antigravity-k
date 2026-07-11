"""Tool Loop engine — LLM stream parsing, tool dispatch, and result merging."""

import asyncio
import logging
from collections.abc import Generator
from typing import Any

from antigravity_k.engine.error_classifier import classify_api_error
from antigravity_k.engine.tool_call_parser import EventType
from antigravity_k.engine.tool_guardrails import (
    append_guardrail_guidance,
    guardrail_synthetic_result,
)

logger = logging.getLogger(__name__)


class ToolLoopEngine:
    """Orchestrator에서 분리된 도구 실행 루프(Tool Loop) 관리 엔진.

    책임:
    - LLM 스트림 파싱 및 도구 호출 감지
    - 도구 병렬 실행 (asyncio 기반)
    - 도구 실행 결과 및 Guardrail 판정의 컨텍스트 병합
    """

    def __init__(self, orchestrator):
        """Initialize the ToolLoopEngine.

        Args:
            orchestrator: orchestrator.

        """
        self.orch = orchestrator

    def _native_tools_kwargs(self, delegate_model: str) -> dict:
        """네이티브 function calling 지원 provider에 tools 스키마를 전달 (P1-1).

        OpenAI 호환 provider(OpenRouter, NIM)는 네이티브 function calling을 지원.
        로컬 Ollama 모델은 기존 XML 파싱 경로 유지 (네이티브 미지원 모델 다수).
        config의 native_function_calling 플래그로 전역 제어 (기본 False — 점진적 도입).
        """
        # config에서 네이티브 function calling 활성화 여부
        raw_cfg = getattr(self.orch, "config", {}) or {}
        native_fc_enabled = (
            raw_cfg.get("tool_loop", {}).get("native_function_calling", False) if isinstance(raw_cfg, dict) else False
        )
        if not native_fc_enabled:
            return {}

        # 모델의 provider 확인 — OpenAI 호환 provider만 네이티브 지원
        try:
            registry = self.orch.manager._registry
            profile = registry.get_model(delegate_model)
            if profile and profile.provider in ("openrouter", "nim"):
                tool_registry = getattr(self.orch, "tool_registry", None)
                if tool_registry and hasattr(tool_registry, "to_openai_schemas"):
                    schemas = tool_registry.to_openai_schemas()
                    if schemas:
                        return {"tools": schemas, "tool_choice": "auto"}
        except Exception:
            logger.debug("네이티브 tools 스키마 준비 실패 — XML 파싱 폴백", exc_info=True)
        return {}

    def run_loop(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int = 15,
        target_model: str | None = None,
    ) -> Generator[str, None, None]:
        """Run the agentic tool-execution loop, yielding output chunks.

        Streams the model response, detects tool calls, executes them in async
        batches (respecting ``waitForPreviousTools`` ordering), and appends
        results to the conversation context. Loops until no more tool calls
        are produced or ``max_steps`` is reached. Post-loop quality/reflection
        checks are delegated to :meth:`_post_loop_checks`.

        Args:
            messages: The conversation messages so far.
            delegate_to: The agent role to delegate to (e.g. ``"CODER"``).
            task_type: The task classification (e.g. ``"code"``, ``"chat"``).
            max_steps: Maximum number of tool-call rounds.
            target_model: Override model name; if ``None`` the role default is used.

        Yields:
            Streaming text chunks and tool-execution status messages.

        """
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
            # 콤보 이름(coding-swarm 등)은 is_loaded 체크를 건너뜀 —
            # 라우터가 폴백 체인에서 실제 가용 모델을 선택함
            is_combo = self.orch.manager.router.get_combo(delegate_model) is not None
            if not is_combo and not self.orch.manager.is_loaded(delegate_model):
                logger.error("No model %s is loaded to execute.", delegate_model)
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
                prompt=prompt_str,
                target=delegate_model,
                task_type=task_type,
                **self._native_tools_kwargs(delegate_model),
            )

            from antigravity_k.engine.stream_processor import StreamProcessor
            from antigravity_k.engine.tool_call_parser import ToolCallParser

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
                            assert event.tool_call is not None
                            tool_name = event.tool_call.name
                            tool_args = event.tool_call.arguments

                            try:
                                from antigravity_k.engine.event_bus import global_event_bus

                                global_event_bus.publish("ToolExecutionStarted", name=tool_name)
                            except Exception:
                                logger.exception("Unhandled exception")
                                pass

                            # Pre-call guardrail
                            pre_decision = self.orch.ctx.tool_guardrail.before_call(
                                tool_name,
                                tool_args,
                            )
                            if not pre_decision.allows_execution:
                                yield f"\n\n🛡️ **[Guardrail]** {pre_decision.message}\n"

                            if event.tool_call is not None:
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
                        if event.tool_call is not None:
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
                logger.error("Error during stream generation: %s", e, exc_info=True)

                if classified.should_compress:
                    yield "\n\n⚠️ **컨텍스트 초과 감지** — 자동 압축을 시도합니다...\n"
                    if hasattr(self.orch, "context_shaper"):
                        shaped_messages = self.orch.context_shaper.shape(
                            shaped_messages,
                            force_compact=True,
                        )
                    prompt_str = self.orch._rebuild_prompt(
                        system_prompt,
                        tool_prompt,
                        skill_prompts,
                        shaped_messages,
                    )
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

                # DAG 기반 도구 실행 그룹화 (waitForPreviousTools 처리)
                execution_batches = []
                current_batch: list[Any] = []
                for tc in pending_tool_calls:
                    if tc is None:
                        continue
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
                        tasks = [self._run_tool_task_async(tc) for tc in batch]
                        batch_results = loop.run_until_complete(
                            asyncio.gather(*tasks, return_exceptions=True),
                        )
                    finally:
                        loop.close()

                    # Error handling inside batch results
                    for idx, res in enumerate(batch_results):
                        if isinstance(res, BaseException):
                            tc = batch[idx]
                            results_collected.append((tc, None, None, f"Exception: {res}", True))
                        else:
                            results_collected.append(res)

                # UI Formatting (Markdown rather than hardcoded raw HTML where possible)
                from antigravity_k.engine.tool_call_parser import ToolCallParser

                parser = ToolCallParser()
                parser.tool_responses = []

                for tc, pre_decision, post_decision, tool_result, blocked in results_collected:
                    if tc is None:
                        continue
                    tool_name = tc.name
                    if blocked:
                        yield f"\n> 🛡️ **[Tool Blocked]** {pre_decision.message if pre_decision else tool_result}\n"
                        parser.tool_responses.append(
                            f"<tool_response>\n{tool_result}\n</tool_response>",
                        )
                        continue

                    is_failed = isinstance(tool_result, str) and tool_result.strip().startswith(
                        "Error",
                    )
                    is_approval_required = isinstance(tool_result, str) and (
                        "[APPROVAL REQUIRED]" in tool_result or "WAITING_FOR_USER_APPROVAL" in tool_result
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
                    display_name = (
                        f"{tool_action} - {tool_summary}"
                        if tool_action and tool_summary
                        else f"Executing **{tool_name}**"
                    )

                    # Yield Markdown formatted response instead of HTML details/summary
                    yield f"\n> 🛠️ **{display_name}** (Step {step}/{max_steps}) {status_icon}\n"

                    if post_decision and post_decision.action == "warn":
                        tool_result = append_guardrail_guidance(tool_result, post_decision)
                        yield f"> ⚠️ {post_decision.message}\n"
                    elif post_decision and post_decision.should_halt:
                        tool_result = append_guardrail_guidance(tool_result, post_decision)
                        yield f"\n> 🛡️ **[Tool Loop Guard]** {post_decision.message}\n"

                    result_preview = (
                        tool_result[:1500] if isinstance(tool_result, str) and len(tool_result) > 1500 else tool_result
                    )

                    yield f"> ```\n> {result_preview}\n> ```\n\n"

                    parser.tool_responses.append(
                        f"<tool_response>\n{tool_result}\n</tool_response>",
                    )
                    tool_executed = True

            if tool_executed:
                import re

                tool_call_blocks = re.findall(
                    r"(<(?:tool_call|action_call)>.*?</(?:tool_call|action_call)>)",
                    full_response,
                    re.DOTALL,
                )
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
        user_task = messages[-1].get("content", "") if messages else ""
        yield from self._post_loop_checks(messages, task_type, full_output, user_task)

    def _post_loop_checks(
        self,
        messages: list[dict[str, str]],
        task_type: str,
        full_output: str,
        user_task: str,
    ) -> Generator[str, None, None]:
        """Run post-loop quality, reflection, and event hooks.

        Extracted from ``run_loop`` to reduce its size. Yields any user-facing
        messages from the quality gate.
        """
        try:
            if hasattr(self.orch, "cognitive_loop") and self.orch.ctx.cognitive_loop:
                self.orch.ctx.cognitive_loop.reflect(user_task, full_output)
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("Reflection error: %s", e)

        try:
            if hasattr(self.orch, "quality_gate") and self.orch.ctx.quality_gate:
                quality = self.orch.ctx.quality_gate.evaluate(task_type, user_task, full_output)
                if quality.user_message:
                    yield f"\n{quality.user_message}\n"
                if quality.should_retry and quality.feedback:
                    self.orch.ctx.quality_gate.mark_retry()
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("QualityGate error: %s", e)

        try:
            if hasattr(self.orch, "ctx") and hasattr(self.orch.ctx, "decision_anchor"):
                candidate = self.orch.ctx.decision_anchor.auto_extract(user_task, full_output)
                if candidate:
                    self.orch.ctx.decision_anchor.add(
                        decision=candidate["decision"],
                        category=candidate["category"],
                        priority=5,
                        source="auto",
                    )
        except Exception:
            logger.exception("Unhandled exception")
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
            logger.exception("Unhandled exception")
            pass

    async def _run_tool_task_async(self, tc):
        """Execute a single tool call with guardrails and cognitive verification.

        Extracted from ``run_loop`` as a top-level async method so it can be
        unit-tested independently. Returns a tuple of
        ``(tool_call, pre_decision, post_decision, result, blocked)``.
        """
        tool_name = tc.name
        tool_args = tc.arguments

        try:
            from antigravity_k.engine.event_bus import global_event_bus

            global_event_bus.publish("ToolExecutionStarted", name=tool_name)
        except Exception:
            logger.exception("Unhandled exception")
            pass

        pre_decision = self.orch.ctx.tool_guardrail.before_call(tool_name, tool_args)
        if not pre_decision.allows_execution:
            synthetic = guardrail_synthetic_result(pre_decision)
            try:
                from antigravity_k.engine.event_bus import global_event_bus

                global_event_bus.publish("ToolExecutionFinished", name=tool_name)
            except Exception:
                logger.exception("Unhandled exception")
            return tc, pre_decision, None, synthetic, True

        tool_result = await self.orch.ctx.tool_executor.execute_async(tool_name, tool_args)

        try:
            from antigravity_k.engine.event_bus import global_event_bus

            global_event_bus.publish("ToolExecutionFinished", name=tool_name)
        except Exception:
            logger.exception("Unhandled exception")
            pass

        try:
            if hasattr(self.orch, "cognitive_loop") and self.orch.ctx.cognitive_loop:
                self.orch.ctx.cognitive_loop.verify_tool_result(tool_name, tool_args, str(tool_result))
        except Exception as ve:
            logger.exception("Unhandled exception")
            logger.debug("Cognitive verification error: %s", ve)

        post_decision = self.orch.ctx.tool_guardrail.after_call(
            tool_name,
            tool_args,
            tool_result,
            failed=(isinstance(tool_result, str) and tool_result.strip().startswith("Error")),
        )
        return tc, pre_decision, post_decision, tool_result, False
