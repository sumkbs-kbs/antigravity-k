"""Antigravity-K: 도구 가드레일 관리자 (Tool Guardrail Manager).

=============================================================
오케스트레이터 루프에서 인라인으로 수행되던 가드레일 전/후 체크 로직을
독립 모듈로 분리합니다. 오케스트레이터는 이 매니저에 도구 이름/인자를
전달하고 GuardrailDecision을 받아 처리합니다.

사용법:
    mgr = ToolGuardrailManager(guardrail, plan_guard, harness)
    decision = mgr.check_before(tool_name, tool_args)
    if not decision.allowed:
        # 차단 처리
    result = execute_tool(tool_name, tool_args)
    post = mgr.check_after(tool_name, tool_args, result, failed=False)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("antigravity_k.tool_guardrail_manager")


@dataclass
class GuardrailDecision:
    """통합 가드레일 판정 결과."""

    allowed: bool = True
    should_halt: bool = False
    message: str = ""
    code: str = ""
    source: str = ""  # "harness", "plan_guard", "tool_guardrail"


class ToolGuardrailManager:
    """도구 호출 전/후 가드레일 체크를 통합 관리합니다.

    오케스트레이터에서 직접 체크하던 HarnessEnforcer, PlanGuard,
    ToolGuardrail의 before/after 호출을 하나의 인터페이스로 통합합니다.
    """

    def __init__(
        self,
        tool_guardrail: Any = None,
        plan_guard: Any = None,
        harness: Any = None,
    ):
        """Initialize the ToolGuardrailManager.

        Args:
            tool_guardrail (Any): tool guardrail.
            plan_guard (Any): plan guard.
            harness (Any): harness.

        """
        self._guardrail = tool_guardrail
        self._plan_guard = plan_guard
        self._harness = harness

    def check_before(self, tool_name: str, tool_args: dict[str, Any]) -> GuardrailDecision:
        """도구 호출 전 통합 가드레일 체크.

        체크 순서:
        1. HarnessEnforcer (도구 경계 검증)
        2. PlanGuard (계획 기반 권한 검증)
        3. ToolGuardrail (루프 방지 등 일반 가드레일)
        """
        # 1. Harness boundary check
        if self._harness:
            try:
                h_res = self._harness.check_tool_boundary(tool_name)
                if not h_res.get("allowed", True):
                    return GuardrailDecision(
                        allowed=False,
                        message=f"HarnessEnforcer: {h_res.get('reason', 'blocked')}",
                        source="harness",
                    )
            except Exception as e:
                logger.exception("Harness check error (default-deny)")
                return GuardrailDecision(
                    allowed=False,
                    message=f"Guardrail check failed (safe default): {e}",
                    source="harness",
                )

        # 2. PlanGuard permission check
        if self._plan_guard:
            try:
                pg_res = self._plan_guard.check_tool_permission(tool_name)
                if not pg_res.get("allowed", True):
                    return GuardrailDecision(
                        allowed=False,
                        message=f"PlanGuard: {pg_res.get('reason', 'blocked')}",
                        source="plan_guard",
                    )
            except Exception as e:
                logger.exception("PlanGuard check error (default-deny)")
                return GuardrailDecision(
                    allowed=False,
                    message=f"PlanGuard check failed (safe default): {e}",
                    source="plan_guard",
                )

        # 3. General tool guardrail (loop detection etc.)
        if self._guardrail:
            try:
                pre_decision = self._guardrail.before_call(tool_name, tool_args)
                if not pre_decision.allows_execution:
                    return GuardrailDecision(
                        allowed=False,
                        should_halt=pre_decision.should_halt,
                        message=pre_decision.message,
                        code=getattr(pre_decision, "code", ""),
                        source="tool_guardrail",
                    )
            except Exception as e:
                logger.exception("Tool guardrail before_call error (default-deny)")
                return GuardrailDecision(
                    allowed=False,
                    message=f"Tool guardrail check failed (safe default): {e}",
                    source="tool_guardrail",
                )

        return GuardrailDecision(allowed=True)

    def check_after(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: Any,
        failed: bool = False,
    ) -> GuardrailDecision:
        """도구 호출 후 가드레일 체크."""
        if not self._guardrail:
            return GuardrailDecision(allowed=True)

        try:
            post_decision = self._guardrail.after_call(
                tool_name,
                tool_args,
                tool_result,
                failed=failed,
            )
            return GuardrailDecision(
                allowed=True,
                should_halt=post_decision.should_halt,
                message=getattr(post_decision, "message", ""),
                code=getattr(post_decision, "code", ""),
                source="tool_guardrail",
            )
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("Tool guardrail after_call error: %s", e)
            return GuardrailDecision(allowed=True)

    def reset_for_turn(self) -> None:
        """턴 시작 시 가드레일 상태를 초기화합니다."""
        if self._guardrail and hasattr(self._guardrail, "reset_for_turn"):
            self._guardrail.reset_for_turn()

    def on_failure_escalation(self, tool_result: str) -> str | None:
        """실패 시 HarnessEnforcer 에스컬레이션 체크.

        Returns:
            에스컬레이션 메시지 또는 None

        """
        if not self._harness:
            return None

        try:
            fb_action = self._harness.feedback_loop(str(tool_result))
            if fb_action.action_type == "escalate":
                return "⚠️ **[Harness]** 에스컬레이션: 반복 오류 감지. 롤백 또는 플랜 변경을 권장합니다."
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("Harness feedback_loop error: %s", e)

        return None
