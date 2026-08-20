"""Analysis and routing handlers for the orchestrator state graph."""

import logging
from collections.abc import Generator

from antigravity_k.engine.state_graph import AgentState, StateContext

logger = logging.getLogger("antigravity_k.engine.orchestrator_handlers")


def ceo_analyze_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """CEO 태스크 분석."""
    yield "🏢 "  # CEO 분석 시작 시각 표시

    analysis = {}
    in_ceo_think = False
    buffer = ""

    for chunk in orch._ceo_analyze(ctx.user_message, ctx.target_model):
        if isinstance(chunk, dict):  # noqa: E501  # noqa: IF_VARIANT_OK - open model stream
            analysis = chunk
            break
        elif isinstance(chunk, str):
            buffer += chunk

            # <think> 감지
            if not in_ceo_think and "<think>" in buffer:
                in_ceo_think = True
                idx = buffer.find("<think>")
                yield buffer[:idx] + "\n\n<think>\n"
                buffer = buffer[idx + 7 :]

            # </think> 감지
            if in_ceo_think and "</think>" in buffer:
                in_ceo_think = False
                idx = buffer.find("</think>")
                yield buffer[:idx] + "\n</think>\n\n"
                buffer = buffer[idx + 8 :]
                continue

            # 스트리밍 출력
            if in_ceo_think and len(buffer) > 8:
                safe_chunk = buffer[:-8]
                yield safe_chunk
                buffer = buffer[-8:]

    # 루프 종료 후, 생각 블록이 열려있다면 닫아줍니다.
    if in_ceo_think:
        if buffer:
            yield buffer
        yield "\n</think>\n\n"

    ctx.analysis = analysis
    ctx.task_type = analysis.get("task_type", "simple_chat")
    ctx.delegate_to = analysis.get("delegate_to", "SELF")
    ctx.refined_prompt = analysis.get("refined_prompt", ctx.user_message)

    # 역할 자동 보정
    if ctx.task_type == "coding" and ctx.delegate_to == "SELF":
        ctx.delegate_to = "WORKER"
    elif ctx.task_type in ("reasoning", "complex") and ctx.delegate_to == "SELF":
        ctx.delegate_to = "ENG_MANAGER"


# ─── PRE_ROUTE 핸들러 ────────────────────────────────────────────


def pre_route_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """불확실성 인식 + 사용자 모델 학습."""
    # 불확실성 인식
    try:
        ki_count = len(orch.ctx.ki_engine.load_kis()) if orch.ctx.ki_engine else 0
        uncertainty = orch.ctx.uncertainty_estimator.estimate(ctx.user_message, ctx.analysis, ki_count)
        if uncertainty.should_ask_user:
            yield f"\n❓ **[불확실성 감지]** {uncertainty.clarification}\n"
        elif uncertainty.confidence.value != "high":
            unc_context = orch.ctx.uncertainty_estimator.format_prompt_injection(uncertainty)
            if unc_context:
                ctx.custom_messages[-1] = {
                    "role": "user",
                    "content": ctx.custom_messages[-1]["content"] + unc_context,
                }
    except Exception as e:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK - uncertainty boundary
        logger.exception("Unhandled exception")
        logger.debug(f"Uncertainty estimation error: {e}")

    # 사용자 모델 학습
    try:
        orch.ctx.user_model.observe(ctx.user_message, ctx.task_type)
        preferences = orch.ctx.memory_manager.resolved_preferences(ctx.user_message)
        user_context = orch.ctx.user_model.build_context(preferences)
        if user_context:
            ctx.custom_messages[-1] = {
                "role": "user",
                "content": ctx.custom_messages[-1]["content"] + user_context,
            }
    except Exception as e:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK - user-model boundary
        logger.exception("Unhandled exception")
        logger.debug(f"User model error: {e}")


# ─── RuleEngine 기반 결정론적 라우팅 ──────────────────────────────────
def route_decision(ctx: StateContext) -> AgentState:
    """태스크 유형에 따라 다음 상태를 결정합니다. (RuleEngine 기반 결정론적)"""
    from antigravity_k.engine.rule_engine import route_decision_deterministic

    return route_decision_deterministic(ctx)


# ─── 파이프라인 합성 헬퍼 (RuleEngine 조건용 분석 데이터 보강) ──────────────────
def _synthesize_explicit_pipeline(ctx: StateContext) -> bool:
    """사용자 프롬프트에 명시적 단계가 있으면 파이프라인을 합성합니다 (RuleEngine 조건 평가 전 호출)."""
    if ctx.analysis.get("pipeline"):
        return False
    from antigravity_k.engine.cognitive_loop import _split_explicit_steps

    steps = _split_explicit_steps(ctx.user_message or "")
    if len(steps) < 2:
        return False
    ctx.analysis["pipeline"] = [
        {"step": idx, "agent": ctx.delegate_to or "WORKER", "task": desc} for idx, desc in enumerate(steps, start=1)
    ]
    return True


# ─── ROUTE 핸들러 (라우팅 UI 표시) ──────────────────────────────────


def route_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """라우팅 UI 표시 (P4: simple_chat은 메시지 생략, 이모지 중복 제거)."""
    role_emoji = {
        "WORKER": "👨‍💻",
        "ENG_MANAGER": "🏗️",
        "QA": "🔍",
        "DESIGNER": "🎨",
        "SELF": "💬",
        "ARCHITECT": "🏗️",
        "PROPOSER": "💡",
        "CRITIC": "⚖️",
        "ARBITER": "🔨",
    }
    emoji = role_emoji.get(ctx.delegate_to, "🤖")

    # P4: simple_chat (SELF 위임)은 CEO 메시지 생략 — 단순 질문에 방해가 됨
    if ctx.delegate_to == "SELF" and ctx.task_type in ("simple_chat", "reasoning"):
        return

    if ctx.task_type == "agi_core":  # noqa: E501  # noqa: IF_VARIANT_OK - open task vocabulary
        sub_type = ctx.analysis.get("sub_type", "scout")
        yield f"**[CEO]** 🧬 **AGI Core ({sub_type})** 파이프라인 시작\n\n"
    elif ctx.task_type == "hardware_report":  # noqa: E501  # noqa: IF_VARIANT_OK - open task vocabulary
        yield "**[CEO]** 🖥️ **하드웨어 컨설턴트** 호출\n\n"
    elif ctx.task_type == "complex" or ctx.analysis.get("pipeline"):
        pipeline = ctx.analysis.get("pipeline", [])
        if pipeline:
            yield f"**[CEO]** 🚀 **다단계 파이프라인({len(pipeline)}단계)** 시작\n\n"
        else:
            yield "**[CEO]** ⚡ **MAX 모드 병렬 편집** 시작\n\n"
    elif ctx.task_type == "max_execute":  # noqa: E501  # noqa: IF_VARIANT_OK - open task vocabulary
        yield "**[CEO]** ⚡ **MAX 모드** — 다중 워커 병렬 실행\n\n"
    elif ctx.task_type == "debate":
        yield "**[CEO]** ⚖️ **토론(Debate) 파이프라인** 시작\n\n"
    elif ctx.delegate_to != "SELF":
        delegate_model = orch._get_model_for_role(ctx.delegate_to)
        yield f"**[CEO]** {emoji} **{ctx.delegate_to}** 위임 (`{delegate_model}`)\n\n"
