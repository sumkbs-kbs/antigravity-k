"""Antigravity-K: 통합 위임 엔진 (P1-2).

====================================
기존 5개 위임 메커니즘(MAX, Pipeline, Debate, SubagentSpawner, single)을
단일 전략 패턴으로 통합합니다.

라우팅 결정이 분산되어 예측 불가능하던 문제를 해결:
  - CEO LLM이 매번 다른 메커니즘을 판단하던 중복 제거
  - 단일 DelegationEngine.delegate(strategy=...) 진입점
  - 기존 메커니즘은 어댑터로 래핑 (점진적 마이그레이션)

전략:
  - "single": 단일 에이전트 (ToolLoopEngine)
  - "parallel": MAX 모드 (N개 워커 + Selector)
  - "pipeline": 순차 다단계
  - "debate": 제안/비판 토론
  - "subagent": SubagentSpawner

사용법:
    engine = DelegationEngine(orchestrator)
    result = engine.delegate(
        strategy="parallel",
        messages=messages,
        delegate_to="WORKER",
        task_type="coding",
    )
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity_k.delegation_engine")


class DelegationStrategy(str, Enum):
    """위임 전략."""

    SINGLE = "single"  # 단일 에이전트 (ToolLoopEngine)
    PARALLEL = "parallel"  # MAX 모드 (N 워커 + Selector)
    PIPELINE = "pipeline"  # 순차 다단계
    DEBATE = "debate"  # 제안/비판 토론
    SUBAGENT = "subagent"  # SubagentSpawner


@dataclass
class DelegationResult:
    """위임 실행 결과."""

    strategy: DelegationStrategy
    success: bool
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DelegationEngine:
    """통합 위임 엔진 — 5개 메커니즘을 단일 인터페이스로.

    기존 메커니즘을 직접 수정하지 않고 어댑터로 래핑하여 점진적 마이그레이션.
    향후 단일화 시 기존 메커니즘은 제거하고 이 엔진이 단일 진입점이 됨.
    """

    def __init__(self, orchestrator):
        """Initialize the DelegationEngine.

        Args:
            orchestrator: OrchestratorAgent 인스턴스

        """
        self.orch = orchestrator

    def delegate(
        self,
        strategy: str | DelegationStrategy,
        messages: list[dict[str, str]],
        delegate_to: str = "WORKER",
        task_type: str = "coding",
        max_steps: int = 15,
        target_model: str | None = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """지정된 전략으로 위임 실행 (스트리밍).

        Args:
            strategy: 위임 전략 (single/parallel/pipeline/debate/subagent)
            messages: 대화 메시지
            delegate_to: 위임 대상 역할
            task_type: 태스크 유형
            max_steps: 최대 도구 호출 단계
            target_model: 대상 모델
            **kwargs: 전략별 추가 파라미터

        Yields:
            str: 스트리밍 응답 청크
        """
        if isinstance(strategy, str):
            try:
                strategy = DelegationStrategy(strategy)
            except ValueError:
                logger.warning("알 수 없는 위임 전략 '%s', single로 폴백", strategy)
                strategy = DelegationStrategy.SINGLE

        logger.info(
            "[DelegationEngine] 전략=%s, 역할=%s, 태스크=%s",
            strategy.value,
            delegate_to,
            task_type,
        )

        try:
            if strategy == DelegationStrategy.SINGLE:
                yield from self._delegate_single(messages, delegate_to, task_type, max_steps, target_model)
            elif strategy == DelegationStrategy.PARALLEL:
                yield from self._delegate_parallel(messages, delegate_to, task_type, max_steps, target_model, **kwargs)
            elif strategy == DelegationStrategy.PIPELINE:
                yield from self._delegate_pipeline(messages, delegate_to, task_type, max_steps, target_model, **kwargs)
            elif strategy == DelegationStrategy.DEBATE:
                yield from self._delegate_debate(messages, delegate_to, task_type, max_steps, target_model, **kwargs)
            elif strategy == DelegationStrategy.SUBAGENT:
                yield from self._delegate_subagent(messages, delegate_to, task_type, max_steps, target_model, **kwargs)
        except Exception as e:
            logger.warning(
                "[DelegationEngine] %s 전략 실패, single로 폴백: %s",
                strategy.value,
                e,
                exc_info=True,
            )
            yield f"\n⚠️ **[{strategy.value} 위임 실패]** {e}. 단일 에이전트로 폴백합니다.\n\n"
            yield from self._delegate_single(messages, delegate_to, task_type, max_steps, target_model)

    def recommend_strategy(
        self,
        task_type: str,
        user_message: str,
        analysis: dict | None = None,
    ) -> DelegationStrategy:
        """태스크 특성에 따라 최적의 위임 전략을 추천합니다.

        CEO LLM의 매번 판단 대신, 결정적 규칙으로 전략을 선택하여
        예측 가능성을 높입니다. analysis(CEO 분석 결과)가 있으면 그것을 존중.
        """
        analysis = analysis or {}

        # CEO가 명시적으로 파이프라인을 지정한 경우 존중
        if analysis.get("pipeline"):
            return DelegationStrategy.PIPELINE

        # MAX 모드 키워드
        msg_lower = user_message.lower()
        max_keywords = ["refactor", "architecture", "리팩토링", "아키텍처", "전면 수정"]
        if any(kw in msg_lower for kw in max_keywords):
            return DelegationStrategy.PARALLEL

        # debate 키워드 (설계 결정, 트레이드오프)
        debate_keywords = ["trade-off", "트레이드오프", "비교", "장단점", "설계 결정"]
        if any(kw in msg_lower for kw in debate_keywords):
            return DelegationStrategy.DEBATE

        # 복잡한 태스크
        if task_type == "complex":
            return DelegationStrategy.PARALLEL

        # 기본값: 단일 에이전트
        return DelegationStrategy.SINGLE

    # ─── 전략별 어댑터 (기존 메커니즘 래핑) ──────────────────────────

    def _delegate_single(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int,
        target_model: str | None,
    ) -> Generator[str, None, None]:
        """단일 에이전트 위임 — ToolLoopEngine 래핑."""
        from antigravity_k.engine.tool_loop import ToolLoopEngine

        tool_loop = ToolLoopEngine(self.orch)
        yield from tool_loop.run_loop(
            messages,
            delegate_to,
            task_type,
            max_steps,
            target_model,
        )
        self.orch._last_agent_output = getattr(self.orch, "_last_agent_output", "")

    def _delegate_parallel(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int,
        target_model: str | None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """병렬 위임 — MaxModeEngine 래핑."""
        max_engine = getattr(self.orch, "max_engine", None)
        if max_engine is None:
            yield "ℹ️ MAX Engine 미가용, 단일 에이전트로 폴백.\n"
            yield from self._delegate_single(messages, delegate_to, task_type, max_steps, target_model)
            return

        user_msg = messages[-1].get("content", "") if messages else ""
        task_spec = {
            "prompt": user_msg,
            "messages": messages,
            "task_type": task_type,
            "delegate_to": delegate_to,
            "max_steps": max_steps,
            "target_model": target_model or "",
        }

        yield "⚡ **[병렬 위임]** 다중 워커 실행 중...\n"
        result = max_engine.run(task_spec, orchestrator=self.orch)

        if result.final_output:
            if result.selected_idx >= 0 and result.results:
                selected = result.results[result.selected_idx]
                yield f"\n\n🏆 **Selector 선정:** Worker {result.selected_idx + 1} ({selected.model})\n"
            yield result.final_output
            self.orch._last_agent_output = result.final_output
        else:
            yield f"\n\n❌ **병렬 위임 실패:** {result.error or '모든 워커 실패'}\n"

    def _delegate_pipeline(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int,
        target_model: str | None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """파이프라인 위임 — 순차 다단계 실행 래핑.

        kwargs["steps"]가 있으면 각 단계를 순차 실행.
        없으면 단일 에이전트로 폴백.
        """
        steps = kwargs.get("steps")
        if not steps:
            yield from self._delegate_single(messages, delegate_to, task_type, max_steps, target_model)
            return

        yield f"🚀 **[파이프라인 위임]** {len(steps)}단계 순차 실행\n\n"
        accumulated_context = list(messages)

        for i, step in enumerate(steps):
            step_role = step.get("delegate_to", delegate_to)
            step_prompt = step.get("prompt", "")
            yield f"\n**[단계 {i + 1}/{len(steps)}]** {step_prompt[:60]}...\n"

            step_messages = list(accumulated_context)
            step_messages.append({"role": "user", "content": step_prompt})

            step_output = ""
            for chunk in self._delegate_single(step_messages, step_role, task_type, max_steps, target_model):
                step_output += chunk
                yield chunk

            # 다음 단계의 컨텍스트로 누적
            accumulated_context.append({"role": "assistant", "content": step_output})

    def _delegate_debate(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int,
        target_model: str | None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """토론 위임 — 제안/비판/합성 3단계 래핑."""
        yield "⚖️ **[토론 위임]** 제안 → 비판 → 합성\n\n"

        # 1단계: 제안 (WORKER)
        yield "**[제안 단계]**\n"
        proposal = ""
        for chunk in self._delegate_single(list(messages), "WORKER", task_type, max_steps, target_model):
            proposal += chunk
            yield chunk

        # 2단계: 비판 (QA)
        yield "\n\n**[비판 단계]**\n"
        critique_messages = messages + [
            {"role": "assistant", "content": proposal},
            {"role": "user", "content": "위 제안의 문제점과 개선점을 지적하세요."},
        ]
        critique = ""
        for chunk in self._delegate_single(critique_messages, "QA", "reasoning", max_steps, target_model):
            critique += chunk
            yield chunk

        # 3단계: 합성
        yield "\n\n**[합성 단계]**\n"
        synth_messages = messages + [
            {"role": "assistant", "content": f"제안:\n{proposal}"},
            {"role": "user", "content": f"비판:\n{critique}\n\n비판을 수용하여 최종 답변을 작성하세요."},
        ]
        yield from self._delegate_single(synth_messages, "ENG_MANAGER", task_type, max_steps, target_model)

    def _delegate_subagent(
        self,
        messages: list[dict[str, str]],
        delegate_to: str,
        task_type: str,
        max_steps: int,
        target_model: str | None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """서브에이전트 위임 — SubagentSpawner 래핑."""
        try:
            from antigravity_k.engine.subagent_spawner import SubagentSpawner

            spawner = SubagentSpawner(self.orch, getattr(self.orch, "tool_registry", None))
            user_msg = messages[-1].get("content", "") if messages else ""
            result = spawner.spawn(task=user_msg, tools=kwargs.get("tools", []))
            yield result
            self.orch._last_agent_output = result
        except Exception as e:
            logger.warning("SubagentSpawner 실패, single로 폴백: %s", e)
            yield from self._delegate_single(messages, delegate_to, task_type, max_steps, target_model)
