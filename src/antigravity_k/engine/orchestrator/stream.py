"""Orchestrator streaming execution logic.

run_stream / run_sync 의 실제 구현을 제공합니다.
"""

import logging
from collections.abc import Generator

from antigravity_k.engine.state_graph import StateContext

logger = logging.getLogger("antigravity_k.orchestrator.stream")


def _extract_learned_preferences(orch) -> dict | None:
    """UserIntentModeler 프로파일에서 학습된 선호도를 추출합니다 (작업 5).

    GlobalMemoryProvider.sync_turn()이 이 metadata를 받아
    preferences/patterns로 영속화합니다.
    """
    try:
        user_model = getattr(orch.ctx, "user_model", None)
        if user_model is None:
            return None
        profile = getattr(user_model, "_profile", {})
        if not profile or not profile.get("stats"):
            return None

        prefs: list[str] = []
        stats = profile["stats"]

        # 언어 선호
        lang_counts = stats.get("language_pref", {})
        if lang_counts:
            top_lang = max(lang_counts, key=lang_counts.get)
            if lang_counts[top_lang] >= 3:
                lang_map = {"korean": "한국어 응답 선호", "english": "영어 응답 선호", "mixed": "한영 혼용"}
                prefs.append(lang_map.get(top_lang, f"언어 선호: {top_lang}"))

        # 도메인
        domain_counts = stats.get("domain", {})
        if domain_counts:
            top_domain = max(domain_counts, key=domain_counts.get)
            if domain_counts[top_domain] >= 3:
                prefs.append(f"주요 작업 도메인: {top_domain}")

        # 스킬 수준
        skill_counts = stats.get("skill_level", {})
        if skill_counts:
            top_skill = max(skill_counts, key=skill_counts.get)
            if skill_counts[top_skill] >= 3:
                skill_map = {"beginner": "초보자 친화적 설명 선호", "advanced": "고급 기술 답변 선호"}
                prefs.append(skill_map.get(top_skill, f"기술 수준: {top_skill}"))

        if prefs:
            return {"learned_preferences": prefs}
        return None
    except Exception:
        logger.debug("선호도 추출 실패 (non-critical)", exc_info=True)
        return None


def run_stream(
    orch,
    messages: list[dict[str, str]],
    target_model: str,
    max_steps: int = 15,
    ephemeral_message: str | None = None,
) -> Generator[str, None, None]:
    """State Graph 기반 멀티 에이전트 스트리밍 실행.

    Args:
        orch: OrchestratorAgent 인스턴스
        messages: 대화 메시지 목록
        target_model: 대상 모델
        max_steps: 최대 단계 수
        ephemeral_message: 임시 메시지

    Yields:
        str: 스트리밍 응답 청크
    """
    # ─── Self-Capability Fast Path ───
    try:
        from antigravity_k.engine.self_capability import (
            is_self_capability_request,
        )

        if is_self_capability_request(orch._latest_user_text(messages)):
            response = orch._render_self_capability_response()
            orch._last_agent_output = response
            yield response
            return
    except ImportError:
        logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
    except (AttributeError, TypeError) as e:
        logger.warning("Self-capability fast path skipped: %s", e)

    # ─── State Graph Fallback ───
    if not orch._state_graph:
        from antigravity_k.engine.orchestrator_handlers import (
            build_orchestrator_graph,
        )

        orch._state_graph = build_orchestrator_graph()

    # ─── Memory Prefetch: 대화 시작 전 관련 기억 주입 ───
    try:
        user_text = orch._latest_user_text(messages)

        # --- Hermes Synergy: Preflight Validator ---
        from antigravity_k.engine.engine_profile import EngineProfile
        from antigravity_k.engine.preflight_validator import PreflightValidator

        validator = PreflightValidator(orch.manager)
        is_valid, reject_reason, profile = validator.validate(user_text)
        if not is_valid:
            yield f"✈️ [Preflight 거부]\n{reject_reason}"
            return

        # P1: 모드 메시지는 코딩/복잡한 작업에만 간략하게 표시 (simple_chat에는 생략)
        # 단순 질문(인사, 날씨, 정보 조회)에는 방해가 되므로 출력하지 않음
        user_text_lower = user_text.lower()
        _simple_patterns = ["안녕", "고마워", "누구", "뭐해", "hello", "hi ", "thanks"]
        _is_simple_chat = len(user_text) < 30 and any(p in user_text_lower for p in _simple_patterns)
        if not _is_simple_chat and profile == EngineProfile.FAST_PROTOTYPER:
            yield "🚀 **[빠른 프로토타이핑 모드]**\n\n"
        elif not _is_simple_chat:
            yield "🛡️ **[정밀 엔지니어링 모드]**\n\n"
        # -------------------------------------------

        recalled = orch.ctx.memory_manager.prefetch_all(user_text)
        if recalled:
            messages = list(messages)  # 원본 불변
            messages.insert(
                1 if len(messages) > 1 else 0,
                {"role": "system", "content": f"[Recalled Memory]\n{recalled}"},
            )
    except ImportError:
        logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
    except (AttributeError, RuntimeError, ValueError, TypeError) as e:
        logger.warning("Memory prefetch error (non-critical): %s", e, exc_info=True)

    # ─── Trajectory Compressor: 대화 궤적 압축 체크포인트 ───
    try:
        if orch.trajectory_compressor and orch.trajectory_compressor.should_compress(messages):
            result = orch.trajectory_compressor.compress(messages)
            messages = result.compressed_messages
            yield f"\n{result.user_message}\n\n"
            logger.info("[Orchestrator] %s", result.user_message)
    except (AttributeError, RuntimeError) as e:
        logger.warning("Trajectory compression error (non-critical): %s", e, exc_info=True)

    # ─── Context Compressor: 토큰 예산 기반 적응형 압축 (TrajectoryCompressor 보완) ───
    # TrajectoryCompressor(메시지 수 기반)가 동작하지 않은 상태에서 토큰이 한계를
    # 초과하면 task_type별 전략으로 더 정밀하게 압축합니다.
    try:
        ctx_compressor = getattr(orch, "context_compressor", None)
        if ctx_compressor and ctx_compressor.needs_compression(messages):
            before_tokens = ctx_compressor.usage_percent(messages)
            messages = ctx_compressor.adaptive_compress(messages, task_type="GENERAL")
            after_tokens = ctx_compressor.usage_percent(messages)
            yield f"\n📦 **[Context Compressor]** 토큰 사용량 {before_tokens:.0f}% → {after_tokens:.0f}% 압축\n\n"
            logger.info(
                "[Orchestrator] Context compressed: %.0f%% → %.0f%%",
                before_tokens,
                after_tokens,
            )
    except (AttributeError, RuntimeError, TypeError) as e:
        logger.warning("Context compression error (non-critical): %s", e, exc_info=True)

    # ─── State Context 생성 및 그래프 실행 ───
    ctx = StateContext(
        messages=messages,
        target_model=target_model,
        max_steps=max_steps,
        ephemeral_message=ephemeral_message,
    )

    logger.info("[Orchestrator] State Graph 실행 시작 (trace_id=%s)", ctx.trace_id)

    yield from orch._state_graph.execute(ctx, orchestrator=orch)

    # ─── 에이전트 출력 동기화 ───
    if ctx.agent_output:
        orch._last_agent_output = ctx.agent_output
        # Memory Sync: 턴 완료 후 모든 메모리 제공자에 동기화
        try:
            # 작업 5: 사용자 프로파일에서 학습된 선호도를 추출하여 metadata로 전달
            _sync_metadata = _extract_learned_preferences(orch)
            orch.ctx.memory_manager.sync_all(
                orch._latest_user_text(messages),
                ctx.agent_output,
                metadata=_sync_metadata,
            )
        except (RuntimeError, ConnectionError, ValueError) as e:
            logger.warning("Memory sync error (non-critical): %s", e, exc_info=True)

    logger.info(
        "[Orchestrator] State Graph 완료: %s, %s개 전이, %sms",
        ctx.current_state.value,
        len(ctx.state_history),
        ctx.get_duration_ms(),
    )


def run_sync(
    orch,
    messages: list[dict[str, str]],
    target_model: str,
    max_steps: int = 15,
) -> str:
    """동기식 실행 (커맨드 팔레트 등에서 사용).

    Args:
        orch: OrchestratorAgent 인스턴스
        messages: 대화 메시지 목록
        target_model: 대상 모델
        max_steps: 최대 단계 수

    Returns:
        str: 전체 응답 텍스트
    """
    result = []
    for chunk in run_stream(orch, messages, target_model, max_steps):
        result.append(chunk)
    return "".join(result)
