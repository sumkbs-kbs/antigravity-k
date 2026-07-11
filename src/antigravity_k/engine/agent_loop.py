"""Antigravity-K: 에이전트 실행 루프 (AgentLoop).

=============================================
ReAct(Reason+Act) 패턴의 상태머신 기반 에이전트 실행 엔진.

이전 구조 (orchestrator._run_single_agent, ~380줄):
    중첩 for/while/if 스파게티 → 디버깅 불가, 테스트 불가

현재 구조 (상태머신):
    GENERATING → TOOL_CALL → OBSERVING → (반복)
                              ↓
                          NUDGING (계획만 서술 시)
                              ↓
                           DONE / ERROR

핵심 설계 원칙 (Codex + Claude Code):
    1. StepContext 데이터클래스로 모든 step 상태를 캡슐화
    2. 각 상태 핸들러가 독립 메서드 → 단위 테스트 가능
    3. parse_error_count, nudge_count 등이 명시적 필드
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReActState(Enum):
    """에이전트 실행 루프의 상태.

    Note: state_graph.py의 AgentState(오케스트레이터 레벨)와 구분하기 위해
    ReActState로 명명합니다.
    """

    PLANNING = "planning"  # 초기 계획 수립 단계
    GENERATING = "generating"  # LLM이 텍스트 생성 중
    TOOL_CALL = "tool_call"  # 도구 호출 감지 → 실행
    OBSERVING = "observing"  # 도구 결과를 LLM에 피드백
    ADAPTING = "adapting"  # 연속 실패로 인한 전략 수정 단계
    NUDGING = "nudging"  # 도구 없이 계획만 서술 → 재촉
    DONE = "done"  # 최종 답변 생성 완료
    ERROR = "error"  # 복구 불가능한 에러


@dataclass
class StepContext:
    """한 step의 모든 상태를 캡슐화합니다.

    이전에는 이 정보가 지역 변수, getattr, 클래스 속성에 흩어져 있었습니다.
    """

    step_number: int
    max_steps: int
    full_response: str = ""  # 현재 step의 raw LLM 출력
    tool_executed: bool = False  # 이 step에서 도구가 실행되었는지
    tool_responses: list[str] = field(default_factory=list)  # 도구 응답 목록
    state: ReActState = ReActState.GENERATING
    adaptation_applied: bool = False  # 전략 수정(Adapt) 반영 여부

    @property
    def visible_text(self) -> str:
        """Thought 블록을 제외한 사용자 보이는 텍스트."""
        return re.sub(r"<thought>.*?</thought>", "", self.full_response, flags=re.DOTALL)

    @property
    def steps_remaining(self) -> int:
        """Steps Remaining.

        Returns:
            int: The int result.

        """
        return self.max_steps - self.step_number


# ── 미완료 계획 감지 패턴 ──
_INCOMPLETE_PLAN_PATTERNS = [
    "하겠습니다",
    "확인합니다",
    "점검하겠",
    "실행하겠",
    "분석하겠",
    "진행하겠",
    "수행하겠",
    "시작하겠",
    "알아보겠",
    "다음 단계",
    "I will",
    "Let me",
    "I'll check",
    "I'll analyze",
    "I need to",
    "Let's do",
    "Plan:",
]


class NudgeDetector:
    """에이전트가 계획만 서술하고 도구를 사용하지 않은 경우를 감지합니다.

    조건:
      1. 현재 step의 visible_text(thought 제외)에 계획 패턴이 포함
      2. visible_text가 200자 미만 (짧은 계획 서술만 대상)
      3. 재촉 횟수가 2회 미만
    """

    MAX_NUDGES = 2

    def __init__(self):
        """Initialize the NudgeDetector."""
        self._count = 0

    def should_nudge(self, ctx: StepContext, has_tool_prompt: bool) -> bool:
        """재촉이 필요한지 판단합니다."""
        if not has_tool_prompt or ctx.tool_executed:
            return False
        if self._count >= self.MAX_NUDGES:
            return False

        visible = ctx.visible_text
        has_plan = any(p in visible for p in _INCOMPLETE_PLAN_PATTERNS) and len(visible.strip()) < 200
        return has_plan

    def nudge(self) -> str:
        """재촉 메시지를 생성하고 카운터를 증가시킵니다."""
        self._count += 1
        return (
            "[SYSTEM WARNING] 당신은 방금 계획을 설명만 했고, 정작 도구를 호출하지 않았습니다!\n"
            "절대 사과하거나, 변명하거나, 도구를 호출하겠다고 부연 설명하지 마세요.\n"
            "지금 즉시 순수한 `<action_call>` 블록을 생성하여 도구를 호출하세요. "
            "평문으로 `Query: ...` 라고 쓰지 마세요."
        )

    @property
    def count(self) -> int:
        """Count.

        Returns:
            int: The int result.

        """
        return self._count

    def reset(self):
        """Reset the agent loop to its initial state, clearing history."""
        self._count = 0


class ParseErrorGuard:
    """연속 파싱 에러를 감지하여 무한 재시도를 방지합니다.

    2회 이상 연속 파싱 에러 시 tool_executed=False로 설정하여
    에이전트가 자연어로 직접 답변하도록 유도합니다.
    """

    MAX_CONSECUTIVE = 2

    def __init__(self):
        """Initialize the ParseErrorGuard."""
        self._count = 0

    def record_error(self) -> bool:
        """에러를 기록하고, 중단해야 하는지 반환합니다."""
        self._count += 1
        if self._count >= self.MAX_CONSECUTIVE:
            logger.warning(
                "[ParseErrorGuard] %s consecutive parse errors — stopping retries",
                self._count,
            )
            return True  # 중단
        return False  # 계속 재시도

    def reset_on_success(self):
        """성공적인 도구 호출 시 카운터를 리셋합니다."""
        self._count = 0

    @property
    def count(self) -> int:
        """Count.

        Returns:
            int: The int result.

        """
        return self._count
