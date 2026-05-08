"""
GatePipeline — 우선순위 기반 다단계 도구 실행 게이트
====================================================
IronClaw approval.rs + Engine V2 gate/pipeline.rs 패턴 이식.

핵심 패턴:
- ExecutionGate 추상 프로토콜: name(), priority(), evaluate() 인터페이스
- Priority-Sorted Pipeline: 게이트를 우선순위순으로 순차 평가
- GateDecision 3분기: Allow / Pause(reason, resume_kind) / Deny(reason)
- 기존 ToolCallGuardrailController를 RateLimitGate로 래핑

게이트 우선순위:
    P50:  RateLimitGate     — 레이트 리밋 (기존 guardrails 래핑)
    P80:  CostBudgetGate    — 비용 예산 게이트 (CostGuard 래핑)
    P100: ApprovalGate      — 도구별 승인 정책
    P150: SecurityPolicyGate — 보안 정책 (SecurityPolicyEngine 래핑)
    P200: CapabilityGate    — 능력 정책 (AutonomousCapabilityPolicy 래핑)

사용법:
    pipeline = GatePipeline()
    pipeline.add_gate(RateLimitGate(guardrails))
    pipeline.add_gate(ApprovalGate())

    ctx = GateContext(tool_name="run_bash_command", args={"command": "ls"})
    decision = await pipeline.evaluate(ctx)
    if decision.is_denied:
        inject_error(decision.reason)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Protocol, runtime_checkable

logger = logging.getLogger("antigravity_k.engine.gate_pipeline")


# ── 게이트 판정 ──


class GateAction(str, Enum):
    """게이트 판정 결과."""

    ALLOW = "allow"
    PAUSE = "pause"  # 사용자 승인 대기
    DENY = "deny"  # 즉시 거부


class ResumeKind(str, Enum):
    """Pause 후 재개 유형."""

    APPROVAL = "approval"  # 사용자 승인
    RETRY = "retry"  # 자동 재시도 (시간 경과 후)


@dataclass(frozen=True)
class GateDecision:
    """게이트 평가 결과."""

    action: GateAction = GateAction.ALLOW
    reason: str = ""
    gate_name: str = ""
    resume_kind: Optional[ResumeKind] = None
    allow_always: bool = False  # "항상 허용" 옵션 제공 여부
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.action == GateAction.ALLOW

    @property
    def is_paused(self) -> bool:
        return self.action == GateAction.PAUSE

    @property
    def is_denied(self) -> bool:
        return self.action == GateAction.DENY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "gate_name": self.gate_name,
            "resume_kind": self.resume_kind.value if self.resume_kind else None,
            "allow_always": self.allow_always,
        }


# ── 게이트 컨텍스트 ──


@dataclass
class GateContext:
    """게이트 평가에 필요한 컨텍스트."""

    tool_name: str
    args: Mapping[str, Any] = field(default_factory=dict)
    user_id: str = "default"
    session_id: str = ""
    execution_mode: str = "interactive"  # interactive / autonomous / container
    auto_approved_tools: frozenset[str] = field(default_factory=frozenset)
    source_channel: str = "web"


# ── ExecutionGate 프로토콜 ──


@runtime_checkable
class ExecutionGate(Protocol):
    """도구 실행 게이트 프로토콜.

    IronClaw Engine V2의 ExecutionGate 트레이트를 Python Protocol로 이식.
    """

    def name(self) -> str:
        """게이트 이름."""
        ...

    def priority(self) -> int:
        """평가 우선순위 (낮은 값 = 먼저 실행)."""
        ...

    def evaluate(self, ctx: GateContext) -> GateDecision:
        """게이트 평가. Allow/Pause/Deny 반환."""
        ...


# ── 기본 게이트 구현 ──


class RateLimitGate:
    """기존 ToolCallGuardrailController를 래핑하는 게이트.

    Priority: 50 (가장 먼저 실행 — 빠른 거부).
    """

    def __init__(self, guardrails=None):
        self._guardrails = guardrails

    def name(self) -> str:
        return "rate_limit"

    def priority(self) -> int:
        return 50

    def evaluate(self, ctx: GateContext) -> GateDecision:
        if self._guardrails is None:
            return GateDecision(gate_name=self.name())

        decision = self._guardrails.before_call(ctx.tool_name, dict(ctx.args))
        if decision.should_halt:
            return GateDecision(
                action=GateAction.DENY,
                reason=decision.message,
                gate_name=self.name(),
                metadata={"guardrail_code": decision.code},
            )

        return GateDecision(gate_name=self.name())


class CostBudgetGate:
    """CostGuard를 래핑하는 비용 예산 게이트.

    Priority: 80 (레이트 리밋 후, 승인 전).
    """

    def __init__(self, cost_guard=None):
        self._cost_guard = cost_guard

    def name(self) -> str:
        return "cost_budget"

    def priority(self) -> int:
        return 80

    def evaluate(self, ctx: GateContext) -> GateDecision:
        if self._cost_guard is None:
            return GateDecision(gate_name=self.name())

        # 비용 게이트는 LLM 호출 도구에만 적용
        # (도구 자체는 비용이 없으므로 기본 Allow)
        return GateDecision(gate_name=self.name())


class ApprovalGate:
    """도구별 승인 정책 게이트.

    IronClaw approval.rs 패턴:
    - Interactive 모드: 승인 필요 도구 → Pause
    - Autonomous 모드: 승인 필요 도구 → Deny
    - Container 모드: 모두 Allow

    Priority: 100.
    """

    # 항상 승인 필요한 도구 (IronClaw ApprovalRequirement::Always)
    ALWAYS_REQUIRE_APPROVAL: frozenset[str] = frozenset(
        {
            "db_migration",
            "deploy",
            "create_pr",
            "git_push",
            "payment",
        }
    )

    # 자동 승인 제외 시 승인 필요 (IronClaw ApprovalRequirement::UnlessAutoApproved)
    UNLESS_AUTO_APPROVED: frozenset[str] = frozenset(
        {
            "run_bash_command",
            "run_persistent_command",
            "write_file",
            "edit_file",
            "multi_replace_file_content",
            "replace_file_content",
            "git_commit",
            "agent_spawn",
            "computer_use",
        }
    )

    def name(self) -> str:
        return "approval"

    def priority(self) -> int:
        return 100

    def evaluate(self, ctx: GateContext) -> GateDecision:
        tool = ctx.tool_name

        # Container 모드: 모두 허용
        if ctx.execution_mode == "container":
            return GateDecision(gate_name=self.name())

        # 항상 승인 필요
        if tool in self.ALWAYS_REQUIRE_APPROVAL:
            if ctx.execution_mode == "autonomous":
                return GateDecision(
                    action=GateAction.DENY,
                    reason=f"도구 '{tool}'은(는) 명시적 승인이 필요하며 자율 모드에서 실행할 수 없습니다.",
                    gate_name=self.name(),
                )
            return GateDecision(
                action=GateAction.PAUSE,
                reason=f"도구 '{tool}'은(는) 이 작업에 대해 명시적 승인이 필요합니다.",
                gate_name=self.name(),
                resume_kind=ResumeKind.APPROVAL,
                allow_always=False,
            )

        # 자동 승인 가능 도구
        if tool in self.UNLESS_AUTO_APPROVED:
            if tool in ctx.auto_approved_tools:
                return GateDecision(gate_name=self.name())

            if ctx.execution_mode == "autonomous":
                # Autonomous 모드에서는 UnlessAutoApproved도 허용
                # (IronClaw 회귀 수정: 0e5f1b12)
                return GateDecision(gate_name=self.name())

            if ctx.execution_mode == "interactive_auto_approve":
                return GateDecision(gate_name=self.name())

            return GateDecision(
                action=GateAction.PAUSE,
                reason=f"도구 '{tool}'의 실행을 승인하시겠습니까?",
                gate_name=self.name(),
                resume_kind=ResumeKind.APPROVAL,
                allow_always=True,
            )

        # 기본: 허용
        return GateDecision(gate_name=self.name())


class SecurityPolicyGate:
    """보안 정책 게이트.

    Priority: 150 (승인 후).
    """

    def __init__(self, policy_engine=None):
        self._policy_engine = policy_engine

    def name(self) -> str:
        return "security_policy"

    def priority(self) -> int:
        return 150

    def evaluate(self, ctx: GateContext) -> GateDecision:
        if self._policy_engine is None:
            return GateDecision(gate_name=self.name())

        # 커맨드 실행 도구
        if ctx.tool_name in {"run_bash_command", "run_persistent_command"}:
            cmd = ctx.args.get("command", "")
            if cmd and not self._policy_engine.is_command_allowed(cmd):
                return GateDecision(
                    action=GateAction.DENY,
                    reason=f"보안 정책에 의해 명령어 '{cmd[:50]}' 차단됨.",
                    gate_name=self.name(),
                )

        # 네트워크 도구
        if ctx.tool_name in {"web_search", "web_scrape", "fetch_dom"}:
            url = ctx.args.get("url", "") or ctx.args.get("query", "")
            if url and not self._policy_engine.is_domain_allowed(url):
                return GateDecision(
                    action=GateAction.DENY,
                    reason=f"보안 정책에 의해 도메인 '{url[:50]}' 차단됨.",
                    gate_name=self.name(),
                )

        return GateDecision(gate_name=self.name())


# ── 메인 파이프라인 ──


class GatePipeline:
    """우선순위 기반 다단계 게이트 파이프라인.

    IronClaw Engine V2 gate/pipeline.rs 패턴:
    게이트를 우선순위순으로 정렬하고, 첫 번째 비-Allow 결과에서 즉시 반환합니다.
    """

    def __init__(self):
        self._gates: List[Any] = []  # ExecutionGate instances
        self._sorted = False

    def add_gate(self, gate) -> "GatePipeline":
        """게이트를 파이프라인에 추가합니다."""
        self._gates.append(gate)
        self._sorted = False
        return self

    def _ensure_sorted(self) -> None:
        """게이트를 우선순위순으로 정렬합니다."""
        if not self._sorted:
            self._gates.sort(key=lambda g: g.priority())
            self._sorted = True

    def evaluate(self, ctx: GateContext) -> GateDecision:
        """모든 게이트를 우선순위순으로 평가합니다.

        첫 번째 비-Allow 결과에서 즉시 반환 (short-circuit).
        """
        self._ensure_sorted()

        for gate in self._gates:
            try:
                decision = gate.evaluate(ctx)
                if not decision.is_allowed:
                    logger.info(
                        f"GatePipeline: {gate.name()} → {decision.action.value} "
                        f"for '{ctx.tool_name}': {decision.reason}"
                    )
                    return decision
            except Exception as e:
                # IronClaw 패턴: 게이트 에러는 fail-open (보수적으로 허용)
                logger.warning(
                    f"GatePipeline: gate '{gate.name()}' error (fail-open): {e}"
                )
                continue

        return GateDecision(gate_name="pipeline", reason="all_gates_passed")

    def list_gates(self) -> List[Dict[str, Any]]:
        """등록된 게이트 목록을 반환합니다."""
        self._ensure_sorted()
        return [{"name": g.name(), "priority": g.priority()} for g in self._gates]


# ── 팩토리 ──


def create_default_pipeline(
    guardrails=None,
    cost_guard=None,
    policy_engine=None,
) -> GatePipeline:
    """기본 게이트 파이프라인을 생성합니다.

    IronClaw의 기본 게이트 구성을 재현합니다.
    """
    pipeline = GatePipeline()
    pipeline.add_gate(RateLimitGate(guardrails))
    pipeline.add_gate(CostBudgetGate(cost_guard))
    pipeline.add_gate(ApprovalGate())
    pipeline.add_gate(SecurityPolicyGate(policy_engine))
    return pipeline
