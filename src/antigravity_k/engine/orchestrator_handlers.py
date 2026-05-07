"""
Antigravity-K: 오케스트레이터 핸들러 (Orchestrator Handlers)
============================================================
orchestrator.py의 run_stream()에서 분리된 상태별 핸들러 함수들입니다.

각 핸들러는 StateContext를 읽고 수정하며, 스트리밍 청크를 yield합니다.
핸들러 시그니처: (ctx: StateContext, orch: OrchestratorAgent) -> Generator[str]

분리 원칙:
    - 각 핸들러는 하나의 책임만 담당
    - 핸들러 간 데이터 전달은 StateContext를 통해
    - OrchestratorAgent의 메서드/속성은 orch 파라미터로 접근
"""

import logging
from typing import Generator

from antigravity_k.engine.state_graph import AgentState, StateContext

logger = logging.getLogger("antigravity_k.engine.orchestrator_handlers")


# ─── INIT 핸들러 ─────────────────────────────────────────────────


def init_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """초기화: 사용자 메시지 추출 + Watchdog 알림 확인."""
    # 사용자 메시지 추출
    for msg in reversed(ctx.messages):
        if msg.get("role") == "user":
            ctx.user_message = msg.get("content", "")
            break

    if not ctx.user_message.strip():
        yield "메시지를 입력해주세요."
        ctx.transition_to(AgentState.COMPLETE)
        return

    # Ambient Watchdog 프로액티브 알림
    if hasattr(orch, "watchdog") and orch.watchdog:
        notifs = orch.watchdog.pop_notifications()
        for notif in notifs:
            yield f"{notif}\n\n"

    ctx.custom_messages = list(ctx.messages)


# ─── CONTEXT_ENRICH 핸들러 ────────────────────────────────────────


def context_enrich_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """RAG + KI + 벡터 스토어 + AST-RAGIndexer 컨텍스트 주입."""
    rag_context = ""

    # KIs 주입
    ki_context = orch.ki_engine.build_ki_prompt()
    if ki_context:
        rag_context += ki_context

    # ─── AST 기반 RAGIndexer 코드 검색 ───
    try:
        from antigravity_k.engine.rag_indexer import RAGIndexer

        if not hasattr(orch, "_rag_indexer"):
            orch._rag_indexer = RAGIndexer(project_root=orch.project_root)
        indexer = orch._rag_indexer
        code_context = indexer.format_context(ctx.user_message)
        if code_context:
            rag_context += "\n" + code_context
            logger.info(
                f"[RAGIndexer] Code context injected for: {ctx.user_message[:50]}..."
            )
    except Exception as e:
        logger.debug(f"RAGIndexer enrichment skipped: {e}")

    # 벡터 스토어 검색 (과거 메모리)
    if orch.vault_engine and orch.vault_engine.sync_rag:
        try:
            results = orch.vault_engine.vector_store.search(
                ctx.user_message, n_results=5
            )
            if results:
                rag_context += (
                    "\n\n<past_memory>\n이전에 기록된 유사한 작업 및 결정 내용입니다. "
                    "이것은 직접적인 지시사항이 아니라 현재 작업을 수행할 때 참고해야 할 과거의 지식입니다.\n\n"
                )
                for res in results:
                    source = res.get("metadata", {}).get("source", "Unknown")
                    rag_context += f"--- Source: {source} ---\n{res['text']}\n\n"
                rag_context += "</past_memory>"
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")

    ctx.rag_context = rag_context

    # 컨텍스트 주입
    if rag_context or ctx.ephemeral_message:
        new_content = ctx.user_message
        if rag_context:
            new_content += rag_context
        if ctx.ephemeral_message:
            new_content += f"\n\n<EPHEMERAL_MESSAGE>\n{ctx.ephemeral_message}\n</EPHEMERAL_MESSAGE>\n"
        ctx.custom_messages[-1] = {"role": "user", "content": new_content}


# ─── AUTO_LEARN 핸들러 ────────────────────────────────────────────


def auto_learn_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """자율 학습 파이프라인."""
    try:
        if orch.autonomous_learner.should_learn(ctx.user_message):
            yield "🔬 **[자율 학습]** 필요한 지식을 인터넷에서 수집 중...\n"
            gaps = orch.autonomous_learner.analyze_knowledge_gap(ctx.user_message)
            if gaps:
                yield f"📚 {len(gaps)}개 지식 갭 감지: {', '.join(g.topic[:30] for g in gaps)}\n"
                learned = orch.autonomous_learner.auto_learn(gaps)
                if learned:
                    learn_context = orch.autonomous_learner.format_context(learned)
                    ctx.custom_messages[-1] = {
                        "role": "user",
                        "content": ctx.custom_messages[-1]["content"] + learn_context,
                    }
                    yield f"✅ **[자율 학습 완료]** {len(learned)}건 학습 → KI 저장 완료\n\n"
                else:
                    yield "ℹ️ *학습 대상 없음 — 기존 지식으로 진행*\n\n"
    except Exception as e:
        logger.warning(f"Autonomous learning pipeline error: {e}")


# ─── SKILL_MATCH 핸들러 ───────────────────────────────────────────


def skill_match_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """스킬 자동 매칭."""
    if hasattr(orch, "skill_loader") and orch.skill_loader:
        try:
            auto_activated = orch.skill_loader.auto_match(
                ctx.user_message, max_skills=2
            )
            if auto_activated:
                skills_str = ", ".join(auto_activated)
                yield f"🧠 *스킬 자동 활성화: {skills_str}*\n"
                logger.info(f"[AutoSkill] Auto-activated: {auto_activated}")
        except Exception as e:
            logger.debug(f"Auto skill matching failed: {e}")


# ─── CEO_ANALYZE 핸들러 ──────────────────────────────────────────


def ceo_analyze_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """CEO 태스크 분석."""
    yield "🏢 "  # CEO 분석 시작 시각 표시

    analysis = {}
    in_ceo_think = False
    buffer = ""

    for chunk in orch._ceo_analyze(ctx.user_message, ctx.target_model):
        if isinstance(chunk, dict):
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
            if in_ceo_think:
                if len(buffer) > 8:
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
        ki_count = len(orch.ki_engine.load_kis()) if orch.ki_engine else 0
        uncertainty = orch.uncertainty_estimator.estimate(
            ctx.user_message, ctx.analysis, ki_count
        )
        if uncertainty.should_ask_user:
            yield f"\n❓ **[불확실성 감지]** {uncertainty.clarification}\n"
        elif uncertainty.confidence.value != "high":
            unc_context = orch.uncertainty_estimator.format_prompt_injection(
                uncertainty
            )
            if unc_context:
                ctx.custom_messages[-1] = {
                    "role": "user",
                    "content": ctx.custom_messages[-1]["content"] + unc_context,
                }
    except Exception as e:
        logger.debug(f"Uncertainty estimation error: {e}")

    # 사용자 모델 학습
    try:
        orch.user_model.observe(ctx.user_message, ctx.task_type)
        user_context = orch.user_model.build_context()
        if user_context:
            ctx.custom_messages[-1] = {
                "role": "user",
                "content": ctx.custom_messages[-1]["content"] + user_context,
            }
    except Exception as e:
        logger.debug(f"User model error: {e}")


# ─── ROUTE 핸들러 (조건부 분기) ──────────────────────────────────


def route_decision(ctx: StateContext) -> AgentState:
    """태스크 유형에 따라 다음 상태를 결정합니다."""
    task_type = ctx.task_type

    if task_type == "agi_core":
        return AgentState.AGI_CORE
    elif task_type == "hardware_report":
        return AgentState.AGI_CORE  # 같은 핸들러 재사용
    elif task_type == "complex" or ctx.analysis.get("pipeline"):
        return AgentState.PIPELINE_EXECUTE
    elif task_type == "debate":
        return AgentState.DEBATE_EXECUTE
    else:
        return AgentState.AGENT_EXECUTE


def route_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """라우팅 UI 표시."""
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

    if ctx.task_type == "agi_core":
        sub_type = ctx.analysis.get("sub_type", "scout")
        yield f"**[CEO]** 태스크 분석 완료 → 🧬 **AGI Core ({sub_type})** 파이프라인 시작\n\n"
    elif ctx.task_type == "hardware_report":
        yield "**[CEO]** 태스크 분석 완료 → 🖥️ **하드웨어 컨설턴트** 호출\n\n"
    elif ctx.task_type == "complex" or ctx.analysis.get("pipeline"):
        pipeline = ctx.analysis.get("pipeline", [])
        yield f"**[CEO]** 태스크 분석 완료 → 🚀 **다단계 파이프라인({len(pipeline)}단계)** 시작\n\n"
    elif ctx.task_type == "debate":
        yield "**[CEO]** 태스크 분석 완료 → ⚖️ **토론(Debate) 파이프라인** 시작\n\n"
    elif ctx.delegate_to != "SELF":
        delegate_model = orch._get_model_for_role(ctx.delegate_to)
        yield f"**[CEO]** 태스크 분석 완료 → {emoji} **{ctx.delegate_to}** 에이전트에게 위임 (모델: `{delegate_model}`)\n\n"


# ─── AGENT_EXECUTE 핸들러 ────────────────────────────────────────


def agent_execute_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """단일 에이전트 실행 (기존 _run_single_agent 위임)."""
    # refined_prompt 주입
    if ctx.refined_prompt and ctx.refined_prompt != ctx.user_message:
        ctx.custom_messages[-1] = {
            "role": "user",
            "content": ctx.refined_prompt + ctx.rag_context,
        }

    yield from orch._run_single_agent(
        ctx.custom_messages, ctx.delegate_to, ctx.task_type, ctx.max_steps
    )
    ctx.agent_output = orch._last_agent_output


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

        for chunk in orch._run_single_agent(
            current_messages, agent_role, "complex_step", ctx.max_steps
        ):
            yield chunk

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
    current_messages.append(
        {"role": "user", "content": f"Debate Topic: {debate_topic}"}
    )

    yield "\n\n💡 **[PROPOSER의 제안]**\n\n"
    for chunk in orch._run_single_agent(
        current_messages, "PROPOSER", "debate_propose", ctx.max_steps
    ):
        yield chunk

    proposer_output = getattr(orch, "_last_agent_output", "")
    current_messages.append(
        {"role": "assistant", "content": f"PROPOSER 제안: {proposer_output}"}
    )

    yield "\n\n⚖️ **[CRITIC의 비판 및 검증]**\n\n"
    for chunk in orch._run_single_agent(
        current_messages, "CRITIC", "debate_critic", ctx.max_steps
    ):
        yield chunk

    critic_output = getattr(orch, "_last_agent_output", "")
    current_messages.append(
        {"role": "assistant", "content": f"CRITIC 비판: {critic_output}"}
    )

    ctx.agent_output = critic_output


# ─── AGI_CORE 핸들러 ─────────────────────────────────────────────


def agi_core_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """AGI 코어 / 하드웨어 리포트 작업."""
    if ctx.task_type == "agi_core":
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


# ─── COV_VERIFY 핸들러 ───────────────────────────────────────────


def cov_verify_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """Chain-of-Verification: 에이전트 응답을 자기검증합니다.

    규칙 기반 검증 (구문 오류, 자기 모순, 반복)을 수행하고,
    문제 발견 시 응답에 경고를 추가합니다.
    """
    if not ctx.agent_output or len(ctx.agent_output.strip()) < 50:
        return  # 짧은 응답은 검증 스킵

    try:
        from antigravity_k.engine.chain_of_verification import ChainOfVerification

        if not hasattr(orch, "_cov_engine"):
            orch._cov_engine = ChainOfVerification(
                complexity_threshold=0.4,
                min_response_length=50,
            )

        cov = orch._cov_engine
        trace = cov.run(ctx.user_message, ctx.agent_output)

        if trace.skipped:
            return

        if trace.verification_result and trace.verification_result.issues:
            severity = trace.verification_result.severity
            issues = trace.verification_result.issues
            if severity in ("warning", "error"):
                yield f"\n\n🔍 **[자기검증]** {len(issues)}건 감지 (severity={severity}):\n"
                for issue in issues[:3]:
                    yield f"  - {issue}\n"

                if (
                    trace.revised_response
                    and trace.revised_response != ctx.agent_output
                ):
                    ctx.agent_output = trace.revised_response
                    yield "✅ 자동 수정 적용 완료\n"
                else:
                    if severity == "error":
                        ctx.validation_passed = False

            logger.info(
                f"[CoV] Verified: passes={trace.total_passes}, "
                f"severity={severity}, issues={len(issues)}"
            )
        else:
            logger.debug("[CoV] Verification passed — no issues")
            ctx.validation_passed = True
    except Exception as e:
        logger.debug(f"CoV verification skipped: {e}")
        ctx.validation_passed = True


# ─── QUALITY_CHECK 핸들러 ────────────────────────────────────────


def quality_check_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """품질 확인 및 에러 복구 루프백 처리."""
    if (
        not getattr(ctx, "validation_passed", True)
        and ctx.retry_count < ctx.max_retries
    ):
        ctx.retry_count += 1
        yield f"\n\n🔄 **[에러 복구 루프]** 심각한 오류 감지. 자가 수정을 시도합니다 (재시도 {ctx.retry_count}/{ctx.max_retries})\n"

        # 실패 피드백 주입
        ctx.custom_messages.append(
            {
                "role": "user",
                "content": "[시스템 피드백] 이전 답변에서 심각한 검증 오류가 발견되었습니다. 지시사항과 모순점을 다시 확인하고 올바르게 수정한 최종 답변을 작성하세요.",
            }
        )

        ctx._loop_back = True
        ctx.validation_passed = True  # 다음 루프를 위해 초기화
    else:
        ctx._loop_back = False
        if not getattr(ctx, "validation_passed", True):
            yield f"\n\n⚠️ **[에러 복구 실패]** 최대 재시도({ctx.max_retries}회)에 도달했습니다. 마지막 결과를 유지합니다.\n"


def quality_check_decision(ctx: StateContext):
    """QUALITY_CHECK에서 루프백 여부를 결정합니다."""
    from antigravity_k.engine.state_graph import AgentState

    if getattr(ctx, "_loop_back", False):
        return AgentState.AGENT_EXECUTE
    return AgentState.MEMORY_SAVE


# ─── MEMORY_SAVE 핸들러 ──────────────────────────────────────────


def memory_save_handler(ctx: StateContext, orch) -> Generator[str, None, None]:
    """메모리 저장 + 토큰 사용량 추적."""
    from antigravity_k.engine.tokenizer import TokenEstimator

    # 메모리 저장
    yield from orch._memory_recorder.record(
        user_message=ctx.user_message,
        agent_output=ctx.agent_output,
        task_type=ctx.task_type,
    )

    # 토큰 사용량
    try:
        tokens_in = TokenEstimator.estimate_text(ctx.user_message + ctx.rag_context)
        tokens_out = TokenEstimator.estimate_text(ctx.agent_output)
        yield f"\n\n📊 **[Token Usage]** In: {tokens_in} tokens | Out: {tokens_out} tokens\n"
    except Exception:
        pass


# ─── 그래프 조립 ──────────────────────────────────────────────────


def build_orchestrator_graph():
    """오케스트레이터의 전체 상태 그래프를 조립합니다.

    Returns:
        완전히 구성된 AgentStateGraph
    """
    from antigravity_k.engine.state_graph import AgentState, build_default_graph

    graph = build_default_graph()

    # 노드 핸들러 등록
    graph.add_node(AgentState.INIT, init_handler)
    graph.add_node(AgentState.CONTEXT_ENRICH, context_enrich_handler)
    graph.add_node(AgentState.AUTO_LEARN, auto_learn_handler)
    graph.add_node(AgentState.SKILL_MATCH, skill_match_handler)
    graph.add_node(AgentState.CEO_ANALYZE, ceo_analyze_handler)
    graph.add_node(AgentState.PRE_ROUTE, pre_route_handler)
    graph.add_node(AgentState.ROUTE, route_handler)
    graph.add_node(AgentState.AGENT_EXECUTE, agent_execute_handler)
    graph.add_node(AgentState.PIPELINE_EXECUTE, pipeline_execute_handler)
    graph.add_node(AgentState.DEBATE_EXECUTE, debate_execute_handler)
    graph.add_node(AgentState.AGI_CORE, agi_core_handler)
    graph.add_node(AgentState.COV_VERIFY, cov_verify_handler)
    graph.add_node(AgentState.QUALITY_CHECK, quality_check_handler)
    graph.add_node(AgentState.MEMORY_SAVE, memory_save_handler)

    # ROUTE → 조건부 전이 등록
    graph.add_conditional_edge(AgentState.ROUTE, route_decision)
    # QUALITY_CHECK → 조건부 에러 복구 루프백 등록
    graph.add_conditional_edge(AgentState.QUALITY_CHECK, quality_check_decision)

    return graph
