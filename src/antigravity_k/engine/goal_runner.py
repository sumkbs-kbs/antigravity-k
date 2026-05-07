"""
Autonomous Goal Runner
======================

Deterministic planning core behind the `/goal` command.  It turns an
open-ended objective into an evidence-driven execution contract that other
agents, tools, and UI workflows can follow safely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class GoalStep:
    """One verifiable step in an autonomous goal loop."""

    index: int
    title: str
    purpose: str
    actions: list[str]
    verification: list[str]
    risk_gate: str


@dataclass(frozen=True)
class GoalAssessment:
    """Small deterministic readiness assessment for a goal."""

    domain: str
    autonomy_level: str
    risk_level: str
    confidence: float
    missing_inputs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GoalSignal:
    """One scored signal used by the autonomous judgment policy."""

    name: str
    score: float
    evidence: str


@dataclass(frozen=True)
class GoalJudgment:
    """Decision policy for whether the goal can move from planning to action."""

    decision: str
    ready_to_execute: bool
    blocked_by: list[str]
    gates: list[str]
    signals: list[GoalSignal]


@dataclass(frozen=True)
class GoalReport:
    """Structured `/goal` result."""

    objective: str
    normalized_objective: str
    assessment: GoalAssessment
    success_criteria: list[str]
    steps: list[GoalStep]
    judgment: GoalJudgment
    capability_matrix: list[tuple[str, str, str]]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "normalized_objective": self.normalized_objective,
            "assessment": {
                "domain": self.assessment.domain,
                "autonomy_level": self.assessment.autonomy_level,
                "risk_level": self.assessment.risk_level,
                "confidence": self.assessment.confidence,
                "missing_inputs": self.assessment.missing_inputs,
            },
            "success_criteria": self.success_criteria,
            "judgment": {
                "decision": self.judgment.decision,
                "ready_to_execute": self.judgment.ready_to_execute,
                "blocked_by": self.judgment.blocked_by,
                "gates": self.judgment.gates,
                "signals": [
                    {
                        "name": signal.name,
                        "score": signal.score,
                        "evidence": signal.evidence,
                    }
                    for signal in self.judgment.signals
                ],
            },
            "steps": [
                {
                    "index": step.index,
                    "title": step.title,
                    "purpose": step.purpose,
                    "actions": step.actions,
                    "verification": step.verification,
                    "risk_gate": step.risk_gate,
                }
                for step in self.steps
            ],
            "capability_matrix": self.capability_matrix,
            "next_actions": self.next_actions,
        }


class GoalRunner:
    """
    Build an autonomous, evidence-first execution plan.

    The runner is intentionally deterministic so `/goal` remains useful even
    when no local model is loaded.  Model-backed agents can consume the same
    report and execute it step by step.
    """

    _DOMAIN_KEYWORDS = {
        "coding": {
            "code",
            "test",
            "ruff",
            "pytest",
            "bug",
            "fix",
            "api",
            "ui",
            "dom",
            "build",
            "refactor",
            "implement",
            "program",
            "코드",
            "테스트",
            "구현",
            "개선",
            "프로그램",
            "버그",
        },
        "research": {
            "research",
            "compare",
            "analyze",
            "benchmark",
            "조사",
            "분석",
            "비교",
            "벤치마크",
        },
        "documentation": {
            "doc",
            "report",
            "procedure",
            "readme",
            "문서",
            "리포트",
            "절차",
            "프로시져",
        },
        "operations": {
            "deploy",
            "server",
            "database",
            "credential",
            "secret",
            "운영",
            "배포",
            "서버",
            "데이터베이스",
        },
    }

    _RISK_KEYWORDS = {
        "delete",
        "remove",
        "drop",
        "credential",
        "secret",
        "password",
        "payment",
        "production",
        "deploy",
        "rm -rf",
        "삭제",
        "비밀번호",
        "시크릿",
        "결제",
        "운영",
        "배포",
    }

    _DELIVERABLE_KEYWORDS = {
        "create",
        "build",
        "write",
        "fix",
        "update",
        "report",
        "test",
        "구현",
        "작성",
        "개선",
        "수정",
        "업데이트",
        "리포트",
        "테스트",
    }

    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max(1, max_iterations)

    def run(
        self,
        objective: str,
        context: Mapping[str, Any] | None = None,
    ) -> GoalReport:
        normalized = self._normalize(objective)
        assessment = self._assess(normalized, context or {})
        return GoalReport(
            objective=objective,
            normalized_objective=normalized,
            assessment=assessment,
            success_criteria=self._success_criteria(normalized, assessment),
            steps=self._steps(assessment),
            judgment=self._judge(normalized, assessment, context or {}),
            capability_matrix=self._capability_matrix(),
            next_actions=self._next_actions(assessment),
        )

    def render_markdown(self, report: GoalReport) -> str:
        lines = [
            "# /goal Autonomous Goal Contract",
            "",
            f"**Objective:** {report.normalized_objective}",
            "",
            "## Readiness",
            f"- Domain: `{report.assessment.domain}`",
            f"- Autonomy level: `{report.assessment.autonomy_level}`",
            f"- Risk level: `{report.assessment.risk_level}`",
            f"- Confidence: `{report.assessment.confidence:.2f}`",
        ]
        if report.assessment.missing_inputs:
            lines.append(
                "- Missing inputs: "
                + ", ".join(f"`{item}`" for item in report.assessment.missing_inputs)
            )

        lines.extend(["", "## Success Criteria"])
        lines.extend(f"- {item}" for item in report.success_criteria)

        lines.extend(["", "## Autonomous Judgment Policy"])
        lines.append(f"- Decision: `{report.judgment.decision}`")
        lines.append(
            f"- Ready to execute: `{str(report.judgment.ready_to_execute).lower()}`"
        )
        if report.judgment.blocked_by:
            lines.append(
                "- Blocked by: "
                + ", ".join(f"`{item}`" for item in report.judgment.blocked_by)
            )
        lines.append("- Required gates: " + "; ".join(report.judgment.gates))
        for signal in report.judgment.signals:
            lines.append(
                f"- Signal `{signal.name}`: {signal.score:.2f} — {signal.evidence}"
            )

        lines.extend(["", "## Autonomous Loop"])
        for step in report.steps:
            lines.append(f"### {step.index}. {step.title}")
            lines.append(f"- Purpose: {step.purpose}")
            lines.append("- Actions: " + "; ".join(step.actions))
            lines.append("- Verification: " + "; ".join(step.verification))
            lines.append(f"- Risk gate: {step.risk_gate}")

        lines.extend(["", "## Capability Transfer Matrix"])
        for capability, codex_pattern, antigravity_hook in report.capability_matrix:
            lines.append(f"- **{capability}:** {codex_pattern} → `{antigravity_hook}`")

        lines.extend(["", "## Next Actions"])
        lines.extend(f"- {item}" for item in report.next_actions)
        return "\n".join(lines)

    def _normalize(self, objective: str) -> str:
        normalized = re.sub(r"\s+", " ", objective or "").strip()
        return normalized or "No objective provided"

    def _assess(
        self,
        normalized: str,
        context: Mapping[str, Any],
    ) -> GoalAssessment:
        lowered = normalized.lower()
        domain_scores = {
            domain: sum(1 for keyword in keywords if keyword in lowered)
            for domain, keywords in self._DOMAIN_KEYWORDS.items()
        }
        domain = max(domain_scores, key=domain_scores.get)
        if domain_scores[domain] == 0:
            domain = "general"

        has_deliverable = any(
            keyword in lowered for keyword in self._DELIVERABLE_KEYWORDS
        )
        has_risk = any(keyword in lowered for keyword in self._RISK_KEYWORDS)
        token_count = len(re.findall(r"[\w가-힣]+", normalized))
        context_bonus = 0.1 if context else 0.0

        clarity = min(1.0, max(0.25, token_count / 18))
        deliverable_score = 1.0 if has_deliverable else 0.55
        safety_score = 0.55 if has_risk else 0.9
        verification_score = 0.9 if domain in {"coding", "documentation"} else 0.7
        confidence = round(
            min(
                0.98,
                (clarity + deliverable_score + safety_score + verification_score) / 4
                + context_bonus,
            ),
            2,
        )

        missing_inputs = []
        if normalized == "No objective provided":
            missing_inputs.append("objective")
        if token_count < 5:
            missing_inputs.append("acceptance criteria")
        if has_risk:
            missing_inputs.append("explicit approval for high-risk actions")

        autonomy_level = "supervised"
        if confidence >= 0.75 and not has_risk:
            autonomy_level = "autonomous-with-verification"
        elif has_risk:
            autonomy_level = "approval-gated"

        return GoalAssessment(
            domain=domain,
            autonomy_level=autonomy_level,
            risk_level="high" if has_risk else "normal",
            confidence=confidence,
            missing_inputs=missing_inputs,
        )

    def _success_criteria(
        self,
        normalized: str,
        assessment: GoalAssessment,
    ) -> list[str]:
        criteria = [
            "목표가 한 문장으로 재진술되고 성공/실패 기준이 명시된다.",
            "작업은 관찰 가능한 단계로 분해되고 각 단계마다 증거가 남는다.",
            "파일 수정, 셸 실행, 외부 전송, 배포성 작업은 권한 게이트를 통과한다.",
            f"최대 {self.max_iterations}회 관찰-수정 루프 안에서 검증 결과를 갱신한다.",
            "최종 산출물에는 변경 요약, 테스트 결과, 잔여 위험이 포함된다.",
        ]
        if assessment.domain == "coding":
            criteria.append(
                "정적 분석, 단위 테스트, 빌드, DOM/UI 검증 중 적용 가능한 게이트가 통과된다."
            )
        if assessment.domain == "documentation":
            criteria.append("절차 문서와 테스트 리포트가 실제 수행 결과와 일치한다.")
        if normalized == "No objective provided":
            criteria.append("목표 입력 전에는 실행 대신 요구사항 수집 상태로 머문다.")
        return criteria

    def _steps(self, assessment: GoalAssessment) -> list[GoalStep]:
        return [
            GoalStep(
                1,
                "Intent Contract",
                "목표, 범위, 금지 행위, 완료 조건을 고정한다.",
                ["목표 재진술", "성공 기준 추출", "누락 입력 표시"],
                ["목표와 기준이 보고서에 포함됨"],
                "목표가 비어 있으면 실행 중단",
            ),
            GoalStep(
                2,
                "System Inventory",
                "현재 코드, 테스트, 도구, UI 상태를 조사한다.",
                ["파일 검색", "관련 코드 읽기", "기준 테스트 실행"],
                ["조사한 파일과 기준 검사 결과 기록"],
                "보호 경로나 사용자 변경분을 덮어쓰지 않음",
            ),
            GoalStep(
                3,
                "Plan Decomposition",
                "작업을 작고 되돌리기 쉬운 단위로 나눈다.",
                ["구현 단위 나누기", "위험도 분류", "검증 순서 지정"],
                ["각 단계에 예상 산출물과 검증 방법 존재"],
                "고위험 작업은 approval-gated 상태 유지",
            ),
            GoalStep(
                4,
                "Execute And Observe",
                "가장 작은 실행 단위를 적용하고 즉시 관찰한다.",
                ["코드/문서 반영", "테스트 또는 DOM 관찰", "증거 수집"],
                ["실패 로그 또는 통과 로그 확보"],
                f"실패 시 같은 방식으로 최대 {self.max_iterations}회만 반복",
            ),
            GoalStep(
                5,
                "Repair Loop",
                "실패 원인을 좁혀 수정하고 회귀를 확인한다.",
                ["오류 원인 분리", "패치 적용", "관련 테스트 재실행"],
                ["수정 전 실패와 수정 후 통과가 연결됨"],
                "원인 불명 수정이나 광범위 리팩터링 금지",
            ),
            GoalStep(
                6,
                "Report And Handoff",
                "최종 상태를 사용자가 재현할 수 있게 문서화한다.",
                ["결과 요약", "테스트 절차 업데이트", "잔여 위험 기록"],
                ["리포트와 테스트 프로시져가 최신 상태"],
                "미검증 항목은 통과로 표시하지 않음",
            ),
        ]

    def _judge(
        self,
        normalized: str,
        assessment: GoalAssessment,
        context: Mapping[str, Any],
    ) -> GoalJudgment:
        token_count = len(re.findall(r"[\w가-힣]+", normalized))
        clarity_score = min(1.0, max(0.0, token_count / 18))
        safety_score = 0.35 if assessment.risk_level == "high" else 0.95
        verification_score = (
            0.95 if assessment.domain in {"coding", "documentation"} else 0.75
        )
        context_score = 0.9 if context else 0.55
        confidence_score = assessment.confidence

        signals = [
            GoalSignal(
                "clarity", round(clarity_score, 2), f"{token_count} objective tokens"
            ),
            GoalSignal(
                "safety", round(safety_score, 2), f"risk={assessment.risk_level}"
            ),
            GoalSignal(
                "verification",
                round(verification_score, 2),
                f"domain={assessment.domain}",
            ),
            GoalSignal(
                "context",
                round(context_score, 2),
                "runtime context available" if context else "no runtime context",
            ),
            GoalSignal(
                "confidence", round(confidence_score, 2), "readiness assessment"
            ),
        ]

        blocked_by = list(assessment.missing_inputs)
        if normalized == "No objective provided":
            decision = "clarify_objective"
        elif assessment.risk_level == "high":
            decision = "approval_required"
        elif assessment.confidence >= 0.75 and verification_score >= 0.9:
            decision = "execute_with_verification"
        else:
            decision = "plan_first"

        ready_to_execute = decision == "execute_with_verification"
        gates = [
            "observe: inspect current code, tests, and DOM before editing",
            "permission: route side-effect tools through PermissionGate",
            "verify: run ruff, pytest, compileall, build, and self-test where applicable",
            "report: update test_report.md and test_process.md with evidence",
        ]
        if assessment.risk_level == "high":
            gates.insert(
                0, "approval: require explicit user approval before high-risk action"
            )

        return GoalJudgment(
            decision=decision,
            ready_to_execute=ready_to_execute,
            blocked_by=blocked_by,
            gates=gates,
            signals=signals,
        )

    def _capability_matrix(self) -> list[tuple[str, str, str]]:
        return [
            (
                "Goal framing",
                "명시 목표를 성공 기준과 금지 조건으로 고정",
                "GoalRunner.Intent Contract",
            ),
            (
                "Tool orchestration",
                "파일/셸/브라우저 도구를 증거 중심으로 순차 실행",
                "PermissionGate + ToolRegistry + Browser self-test",
            ),
            (
                "Plan/Act/Observe loop",
                "계획, 실행, 관찰, 수정을 반복하는 자율 루프",
                "GoalStep + max_iterations",
            ),
            (
                "Code quality gates",
                "정적 분석, 단위 테스트, 빌드 결과를 완료 조건으로 사용",
                "ruff + pytest + dashboard build",
            ),
            (
                "Response quality gates",
                "코드-only 응답, Big-O 누락, 반복 문단, 비교 구조 누락을 자동 감점",
                "QualityGate + OmniTDD.Response Reconstructor",
            ),
            (
                "DOM-grounded QA",
                "실제 화면 DOM을 근거로 UI 동작 검증",
                "/qa + browser harness + command palette",
            ),
            (
                "Evidence reporting",
                "결과/위험/후속 항목을 문서에 남김",
                "test_report.md + test_process.md",
            ),
        ]

    def _next_actions(self, assessment: GoalAssessment) -> list[str]:
        if "objective" in assessment.missing_inputs:
            return [
                "`/goal <달성하려는 목표>` 형태로 목표를 입력한다.",
                "목표가 정해지면 실행 전 성공 기준과 검증 게이트를 먼저 확정한다.",
            ]
        actions = [
            "이 계약을 기준으로 관련 코드와 UI를 조사한다.",
            "가장 작은 변경 단위를 적용한 뒤 즉시 정적 분석/테스트/DOM 검증을 실행한다.",
            "검증 실패 시 원인과 수정 내용을 같은 리포트 체인에 누적한다.",
        ]
        if assessment.autonomy_level == "approval-gated":
            actions.insert(
                0,
                "고위험 동작은 사용자의 명시 승인 전까지 계획/검증 단계에 머문다.",
            )
        return actions
