"""Orchestrator streaming execution logic.

run_stream / run_sync 의 실제 구현을 제공합니다.
"""

import logging
from collections.abc import Generator

from antigravity_k.engine.state_graph import StateContext

logger = logging.getLogger("antigravity_k.orchestrator.stream")


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
        logger.debug("self_capability module not available — skipping fast path")
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

        if profile == EngineProfile.FAST_PROTOTYPER:
            yield "🚀 [FAST_PROTOTYPER 모드] 엄격한 검증을 생략하고 빠른 구축을 시작합니다...\n\n"
        else:
            yield "🛡️ [STRICT_ENGINEER 모드] 정밀한 엔지니어링 및 44단계 검증 프로세스를 시작합니다...\n\n"
        # -------------------------------------------

        recalled = orch.ctx.memory_manager.prefetch_all(user_text)
        if recalled:
            messages = list(messages)  # 원본 불변
            messages.insert(
                1 if len(messages) > 1 else 0,
                {"role": "system", "content": f"[Recalled Memory]\n{recalled}"},
            )
    except ImportError:
        logger.debug("PreflightValidator or EngineProfile not installed — skipping")
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
            orch.ctx.memory_manager.sync_all(
                orch._latest_user_text(messages),
                ctx.agent_output,
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
