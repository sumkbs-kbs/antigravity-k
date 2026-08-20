"""Agent execution handlers for the orchestrator state graph."""

import logging
from collections.abc import Generator

from antigravity_k.engine.state_graph import StateContext

logger = logging.getLogger("antigravity_k.engine.orchestrator_handlers")


def max_execute_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """MAX 모드: 여러 워커를 병렬로 실행하고 Selector가 최적 선정.

    Codebuff MAX Mode 방식:
    1. N개 워커를 서로 다른 모델/전략으로 동시 실행
    2. Selector 엔진이 모든 결과 검토
    3. 최적 결과 선정 또는 합성
    """
    # refined_prompt 주입
    if ctx.refined_prompt and ctx.refined_prompt != ctx.user_message:
        ctx.custom_messages[-1] = {
            "role": "user",
            "content": ctx.refined_prompt + ctx.rag_context,
        }

    yield "⚡ **[MAX Mode]** 다중 워커 병렬 실행 중...\n"

    try:
        max_engine = getattr(orch, "max_engine", None)
        if max_engine is None:
            # 폴백: 싱글 에이전트
            yield "ℹ️ MAX Engine not available, falling back to single agent.\n"
            from antigravity_k.engine.tool_loop import ToolLoopEngine

            tool_loop = ToolLoopEngine(orch)
            yield from tool_loop.run_loop(
                ctx.custom_messages,
                ctx.delegate_to,
                ctx.task_type,
                ctx.max_steps,
                ctx.target_model,
            )
            ctx.agent_output = getattr(orch, "_last_agent_output", "")
            return

        # MAX 모드 태스크 명세 구성
        task_spec = {
            "prompt": ctx.refined_prompt or ctx.user_message,
            "messages": ctx.custom_messages,
            "task_type": ctx.task_type,
            "delegate_to": ctx.delegate_to,
            "max_steps": ctx.max_steps,
            "target_model": ctx.target_model,
        }

        runtime = getattr(orch, "agent_runtime", None)
        result = (
            runtime.run_max(task_spec)
            if runtime is not None and getattr(runtime, "is_canonical_runtime", False) is True
            else max_engine.run(task_spec, orchestrator=orch)
        )

        if result.final_output:
            # 결과가 이미 trace를 포함하므로 바로 yield
            if result.selected_idx >= 0 and result.results:
                selected = result.results[result.selected_idx]
                ctx.agent_output = selected.output

                # 결과 프레임 출력
                worker_summary = (
                    f"\n\n🏆 **[MAX Selector]** Worker {result.selected_idx + 1} 선정 "
                    f"({selected.model}, {selected.strategy}, {selected.elapsed_sec}s)\n"
                )
                yield worker_summary
            else:
                ctx.agent_output = result.final_output
        else:
            error_msg = result.error or "All workers failed"
            yield f"\n\n❌ **[MAX Error]** {error_msg}\n"
            ctx.agent_output = f"[MAX Error] {error_msg}"

        # 워커 상세 정보 표시 (성공한 워커만)
        if result.results:
            for i, r in enumerate(result.results):
                status = "✅" if r.error is None and r.output.strip() else "❌"
                yield f"{status} Worker {i + 1}: {r.model} [{r.strategy}] — {r.elapsed_sec}s\n"

    except Exception as e:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK - fallback boundary
        logger.exception("[MAX] Max execute handler failed")
        yield f"\n\n❌ **[MAX Error]** 병렬 실행 실패: {e}\n"
        # 폴백: 싱글 에이전트
        yield "🔄 싱글 에이전트로 폴백합니다...\n\n"
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        tool_loop = ToolLoopEngine(orch)
        yield from tool_loop.run_loop(
            ctx.custom_messages,
            ctx.delegate_to,
            ctx.task_type,
            ctx.max_steps,
            ctx.target_model,
        )
        ctx.agent_output = getattr(orch, "_last_agent_output", "")


# ─── AGENT_EXECUTE 핸들러 ────────────────────────────────────────


def agent_execute_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """단일 에이전트 실행 (기존 _run_single_agent 위임)."""
    # refined_prompt 주입
    if ctx.refined_prompt and ctx.refined_prompt != ctx.user_message:
        ctx.custom_messages[-1] = {
            "role": "user",
            "content": ctx.refined_prompt + ctx.rag_context,
        }

    from antigravity_k.engine.tool_loop import ToolLoopEngine

    tool_loop = ToolLoopEngine(orch)
    yield from tool_loop.run_loop(
        ctx.custom_messages,
        ctx.delegate_to,
        ctx.task_type,
        ctx.max_steps,
        ctx.target_model,
        evaluation_user_task=ctx.user_message,
    )
    ctx.agent_output = getattr(orch, "_last_agent_output", "")


# ─── PIPELINE_EXECUTE 핸들러 ─────────────────────────────────────


def pipeline_execute_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """멀티 스텝 파이프라인 실행."""
    pipeline = ctx.analysis.get("pipeline", [])
    yield "\n\n🚀 **멀티 스텝 파이프라인 시작**\n"

    current_messages = list(ctx.custom_messages)
    for step_info in pipeline:
        step_num = step_info.get("step", 0)
        agent_role = step_info.get("agent", "WORKER")
        task_desc = step_info.get("task", "")

        yield f"\n\n---\n**[Step {step_num}] {agent_role}**: {task_desc}\n\n"

        from antigravity_k.engine.tool_loop import ToolLoopEngine

        tool_loop = ToolLoopEngine(orch)
        yield from tool_loop.run_loop(current_messages, agent_role, "complex_step", ctx.max_steps)

        if hasattr(orch, "_last_agent_output"):
            current_messages.append(
                {
                    "role": "assistant",
                    "content": f"[{agent_role} 완료]: " + orch._last_agent_output,
                }
            )

    yield "\n\n✅ **파이프라인 완료**\n"
    ctx.agent_output = getattr(orch, "_last_agent_output", "")


# ─── DEBATE_EXECUTE 핸들러 ───────────────────────────────────────


def debate_execute_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """토론 파이프라인 실행."""
    debate_topic = ctx.analysis.get("debate_topic", ctx.user_message)
    yield f"\n\n⚖️ **토론 시작**: {debate_topic}\n"

    current_messages = list(ctx.custom_messages)
    current_messages.append({"role": "user", "content": f"Debate Topic: {debate_topic}"})

    yield "\n\n💡 **[PROPOSER의 제안]**\n\n"
    from antigravity_k.engine.tool_loop import ToolLoopEngine

    tool_loop = ToolLoopEngine(orch)
    for chunk in tool_loop.run_loop(current_messages, "PROPOSER", "debate_propose", ctx.max_steps):
        yield chunk

    proposer_output = getattr(orch, "_last_agent_output", "")
    current_messages.append({"role": "assistant", "content": f"PROPOSER 제안: {proposer_output}"})

    yield "\n\n⚖️ **[CRITIC의 비판 및 검증]**\n\n"
    from antigravity_k.engine.tool_loop import ToolLoopEngine

    tool_loop = ToolLoopEngine(orch)
    for chunk in tool_loop.run_loop(current_messages, "CRITIC", "debate_critic", ctx.max_steps):
        yield chunk

    critic_output = getattr(orch, "_last_agent_output", "")
    current_messages.append({"role": "assistant", "content": f"CRITIC 비판: {critic_output}"})

    ctx.agent_output = critic_output


# ─── AGI_CORE 핸들러 ─────────────────────────────────────────────


def agi_core_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """AGI 코어 / 하드웨어 리포트 작업."""
    if ctx.task_type == "agi_core":  # noqa: E501  # noqa: IF_VARIANT_OK - open task vocabulary
        sub_type = ctx.analysis.get("sub_type", "scout")
        if "scout" in sub_type.lower():
            from antigravity_k.agents.scout_agent import ScoutAgent

            scout = ScoutAgent(orch.manager, orch.tool_registry)
            yield scout.propose_model_scout(ctx.user_message)
        else:
            from antigravity_k.agents.trainer_agent import TrainerAgent

            trainer = TrainerAgent(orch.manager, orch.tool_registry)
            yield trainer.propose_training(ctx.user_message)
    elif ctx.task_type == "hardware_report":
        from antigravity_k.agents.hardware_analyst import HardwareAnalystAgent

        analyst = HardwareAnalystAgent(orch.manager)
        yield analyst.propose_upgrade("AGI-Target-400B", 200.0)
