"""
Antigravity-K: 품질 검증 게이트 (QualityGate)
=============================================
E-5: 에이전트 출력물의 품질을 자가 평가하고,
기준 미달 시 재시도 루프를 트리거합니다.
"""

import ast
import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QualityGrade(Enum):
    A = "excellent"
    B = "good"
    C = "retry"
    F = "fail"


@dataclass
class QualityScore:
    grade: QualityGrade
    score: float
    feedback: str
    user_message: str
    should_retry: bool
    issues: list


class QualityGate:
    """에이전트 출력 품질 자동 평가. A/B는 통과, C/F는 재시도."""

    def __init__(self, max_retries: int = 1):
        self.max_retries = max_retries
        self._retry_count = 0

    def evaluate(
        self, task_type: str, user_request: str, agent_output: str
    ) -> QualityScore:
        if not agent_output or not agent_output.strip():
            return QualityScore(
                QualityGrade.F,
                0.0,
                "출력이 비어 있습니다.",
                "⚠️ 응답 없음",
                True,
                ["empty"],
            )

        issues = []
        score = 1.0

        if task_type in ("coding", "complex", "complex_step"):
            s, i = self._check_code(agent_output)
            score *= s
            issues.extend(i)

        s, i = self._check_completeness(user_request, agent_output, task_type)
        score *= s
        issues.extend(i)

        s, i = self._check_safety(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_repetition(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_internal_tag_leak(agent_output)
        score *= s
        issues.extend(i)

        grade = (
            QualityGrade.A
            if score >= 0.8
            else (
                QualityGrade.B
                if score >= 0.6
                else QualityGrade.C if score >= 0.3 else QualityGrade.F
            )
        )
        should_retry = (
            grade in (QualityGrade.C, QualityGrade.F)
            and self._retry_count < self.max_retries
        )

        feedback = ""
        if grade in (QualityGrade.C, QualityGrade.F):
            feedback = (
                "[QUALITY GATE] 품질 미달. 문제: " + "; ".join(issues) + ". 개선하세요."
            )

        user_msg = (
            "" if grade == QualityGrade.A else f"📊 *품질: {grade.value} ({score:.0%})*"
        )
        if grade == QualityGrade.C:
            user_msg = f"🔄 *품질 미달 ({score:.0%}) — 자동 개선 중...*"

        return QualityScore(
            grade, round(score, 2), feedback, user_msg, should_retry, issues
        )

    def mark_retry(self):
        self._retry_count += 1

    def reset(self):
        self._retry_count = 0

    def _check_code(self, output: str) -> tuple:
        score, issues = 1.0, []
        blocks = re.findall(r"```python\n(.*?)```", output, re.DOTALL)
        for i, block in enumerate(blocks):
            try:
                ast.parse(block)
            except SyntaxError as e:
                score *= 0.5
                issues.append(f"코드블록{i+1} 구문오류: {e.msg}")
            if "..." in block or "NotImplemented" in block:
                score *= 0.8
                issues.append(f"코드블록{i+1} 미완성")
        return score, issues

    def _check_completeness(self, request: str, output: str, task_type: str) -> tuple:
        score, issues = 1.0, []
        if task_type in ("coding", "complex", "reasoning") and len(output) < 100:
            score *= 0.5
            issues.append("응답이 너무 짧음")
        req_words = set(re.findall(r"[가-힣a-zA-Z]{2,}", request.lower()))
        out_words = set(re.findall(r"[가-힣a-zA-Z]{2,}", output.lower()))
        if req_words and len(req_words & out_words) / len(req_words) < 0.15:
            score *= 0.7
            issues.append("요청과 관련성 낮음")
        return score, issues

    def _check_safety(self, output: str) -> tuple:
        score, issues = 1.0, []
        for pattern, desc in [
            (r"rm\s+-rf\s+/", "루트삭제"),
            (r":(){ :\|:& };:", "포크폭탄"),
            (r"mkfs\.", "디스크포맷"),
        ]:
            if re.search(pattern, output):
                score *= 0.3
                issues.append(f"위험명령: {desc}")
        return score, issues

    def _check_repetition(self, output: str) -> tuple:
        """동일 문단이 3회 이상 반복되면 품질 감점."""
        score, issues = 1.0, []
        # 4줄 이상의 블록 단위로 반복 탐지
        lines = output.split("\n")
        if len(lines) > 20:
            block_size = 4
            seen_blocks = {}
            for i in range(len(lines) - block_size + 1):
                block = "\n".join(lines[i : i + block_size]).strip()
                if len(block) < 40:  # 너무 짧은 블록은 무시
                    continue
                seen_blocks[block] = seen_blocks.get(block, 0) + 1
            max_repeats = max(seen_blocks.values()) if seen_blocks else 0
            if max_repeats >= 5:
                score *= 0.1
                issues.append(f"심각한 반복 루프 탐지 ({max_repeats}회 반복)")
            elif max_repeats >= 3:
                score *= 0.3
                issues.append(f"반복 콘텐츠 탐지 ({max_repeats}회 반복)")
        return score, issues

    def _check_internal_tag_leak(self, output: str) -> tuple:
        """내부 태그(%%THINK_END%%, <algorithm> 등)가 사용자에게 유출되면 감점."""
        score, issues = 1.0, []
        leak_patterns = [
            (r"%%THINK_END%%", "%%THINK_END%% 태그 유출"),
            (r"<algorithm>.*?</algorithm>", "<algorithm> 태그 유출"),
            (r"The user wants me to", "영어 혼잣말(monologue) 유출"),
            (r"I need to:?\n", "영어 내부 계획(plan) 유출"),
        ]
        for pattern, desc in leak_patterns:
            if re.search(pattern, output, re.DOTALL | re.IGNORECASE):
                score *= 0.5
                issues.append(desc)
        return score, issues
