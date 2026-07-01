"""Antigravity-K: Chain-of-Verification (CoV) 자기검증 루프.

========================================================
모델이 생성한 답변을 동일 모델의 별도 호출로 검증하여
복잡한 추론에서의 환각과 논리적 오류를 자가 수정합니다.

격차 해소 대상: 추론 깊이 및 정확도
"""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger("antigravity_k.chain_of_verification")


@dataclass
class VerificationResult:
    """검증 결과."""

    issues_found: list[str] = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high
    suggested_fixes: list[str] = field(default_factory=list)
    verification_reasoning: str = ""
    passed: bool = True


@dataclass
class CoVTrace:
    """CoV 실행 추적."""

    original_response: str = ""
    verification_result: VerificationResult | None = None
    revised_response: str = ""
    total_passes: int = 1
    total_latency_ms: float = 0.0
    skipped: bool = False
    skip_reason: str = ""


# ─── 복잡도 판단 기준 ────────────────────────────────────────

COMPLEX_INDICATORS = [
    "아키텍처",
    "설계",
    "리팩토링",
    "마이그레이션",
    "최적화",
    "architecture",
    "design",
    "refactor",
    "migrate",
    "optimize",
    "알고리즘",
    "algorithm",
    "시간복잡도",
    "time complexity",
    "보안",
    "security",
    "취약점",
    "vulnerability",
    "데이터베이스",
    "database",
    "스키마",
    "schema",
    "동시성",
    "concurrency",
    "비동기",
    "async",
    "분산",
    "distributed",
    "캐시",
    "cache",
]

SIMPLE_INDICATORS = [
    "안녕",
    "hello",
    "hi",
    "도움",
    "help",
    "파일 읽",
    "파일 보",
    "목록",
    "list",
    "간단한",
    "simple",
    "basic",
]


class ChainOfVerification:
    """Generate → Verify → Revise 3-pass 자기검증 파이프라인.

    단순 질문은 1-pass로 통과시키고,
    복잡한 코드 생성/아키텍처 설계만 선택적으로 3-pass를 적용합니다.
    """

    def __init__(
        self,
        generate_fn: Callable | None = None,
        min_response_length: int = 200,
        complexity_threshold: float = 0.4,
    ):
        """Args:
        generate_fn: 모델 호출 함수 (prompt: str) -> str
        min_response_length: CoV를 적용할 최소 응답 길이
        complexity_threshold: 복잡도 점수 임계값 (0.0~1.0).

        """
        self._generate_fn = generate_fn
        self.min_response_length = min_response_length
        self.complexity_threshold = complexity_threshold

    def set_generate_fn(self, fn: Callable):
        """모델 호출 함수를 설정합니다."""
        self._generate_fn = fn

    def should_verify(self, task: str, response: str) -> bool:
        """이 응답에 CoV 검증이 필요한지 판단합니다."""
        # 너무 짧은 응답은 스킵
        if len(response) < self.min_response_length:
            return False

        # 복잡도 점수 계산
        score = self.estimate_complexity(task)
        return score >= self.complexity_threshold

    def estimate_complexity(self, task: str) -> float:
        """작업의 복잡도를 0.0~1.0으로 추정합니다."""
        task_lower = task.lower()

        # 단순 지표 체크
        simple_hits = sum(1 for ind in SIMPLE_INDICATORS if ind in task_lower)
        if simple_hits >= 2:
            return 0.1

        # 복잡 지표 체크
        complex_hits = sum(1 for ind in COMPLEX_INDICATORS if ind in task_lower)

        # 코드 블록 포함 여부
        has_code_request = any(
            kw in task_lower
            for kw in [
                "코드",
                "code",
                "함수",
                "function",
                "클래스",
                "class",
                "구현",
                "implement",
            ]
        )

        # 길이 기반 보정
        length_factor = min(len(task) / 500, 1.0) * 0.2

        score = min(
            (complex_hits * 0.15) + (0.2 if has_code_request else 0.0) + length_factor,
            1.0,
        )
        return score

    def verify(self, task: str, response: str) -> VerificationResult:
        """생성된 응답을 검증합니다 (Pass 2)."""
        result = VerificationResult()

        # 1. 규칙 기반 빠른 검증
        rule_issues = self._rule_based_check(task, response)
        result.issues_found.extend(rule_issues)

        # 2. LLM 기반 심층 검증 (generate_fn이 있는 경우)
        if self._generate_fn and len(response) >= self.min_response_length:
            llm_result = self._llm_verify(task, response)
            if llm_result:
                result.issues_found.extend(llm_result.issues_found)
                result.suggested_fixes.extend(llm_result.suggested_fixes)
                result.verification_reasoning = llm_result.verification_reasoning

        # 심각도 판정
        if len(result.issues_found) == 0:
            result.severity = "none"
            result.passed = True
        elif len(result.issues_found) <= 2:
            result.severity = "low"
            result.passed = True  # 경미한 문제는 통과
        elif len(result.issues_found) <= 4:
            result.severity = "medium"
            result.passed = False
        else:
            result.severity = "high"
            result.passed = False

        return result

    def revise(self, task: str, response: str, verification: VerificationResult) -> str:
        """검증 결과를 바탕으로 응답을 수정합니다 (Pass 3)."""
        if verification.passed or not self._generate_fn:
            return response

        issues_text = "\n".join(f"- {issue}" for issue in verification.issues_found)
        fixes_text = "\n".join(f"- {fix}" for fix in verification.suggested_fixes)

        revise_prompt = (
            "아래는 사용자의 질문에 대한 이전 답변입니다. "
            "검증 과정에서 다음 문제점이 발견되었습니다.\n\n"
            f"## 원래 질문\n{task}\n\n"
            f"## 이전 답변\n{response[:3000]}\n\n"
            f"## 발견된 문제\n{issues_text}\n\n"
        )

        if fixes_text:
            revise_prompt += f"## 제안된 수정 방향\n{fixes_text}\n\n"

        revise_prompt += (
            "위 문제를 모두 수정하여 개선된 답변을 작성해주세요. "
            "기존 답변에서 올바른 부분은 유지하고, 문제가 있는 부분만 수정하세요."
        )

        try:
            revised = self._generate_fn(revise_prompt)
            if revised and len(revised.strip()) > 50:
                return revised
        except Exception:
            logger.exception("[CoV] Revision failed")

        return response  # 수정 실패 시 원본 유지

    def run(self, task: str, response: str) -> CoVTrace:
        """전체 CoV 파이프라인을 실행합니다.

        Returns:
            CoVTrace with original, verification, and revised response

        """
        trace = CoVTrace(original_response=response)
        start = time.time()

        # 1. 검증 필요성 판단
        if not self.should_verify(task, response):
            trace.skipped = True
            trace.skip_reason = "Low complexity or short response"
            trace.revised_response = response
            trace.total_latency_ms = (time.time() - start) * 1000
            return trace

        # 2. 검증 (Pass 2)
        verification = self.verify(task, response)
        trace.verification_result = verification
        trace.total_passes = 2

        # 3. 수정 (Pass 3) — 검증 실패 시에만
        if not verification.passed:
            trace.revised_response = self.revise(task, response, verification)
            trace.total_passes = 3
        else:
            trace.revised_response = response

        trace.total_latency_ms = (time.time() - start) * 1000
        logger.info(
            "[CoV] %s-pass complete. Issues: %s, Severity: %s, Latency: %sms",
            trace.total_passes,
            len(verification.issues_found),
            verification.severity,
            trace.total_latency_ms,
        )

        return trace

    # ─── 규칙 기반 빠른 검증 ──────────────────────────────────

    def _rule_based_check(self, task: str, response: str) -> list[str]:
        """LLM 호출 없이 규칙 기반으로 빠르게 검증합니다."""
        issues = []

        # 1. Python 코드 블록의 구문 검증
        code_blocks = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
        for i, code in enumerate(code_blocks):
            import ast as _ast

            try:
                _ast.parse(code)
            except SyntaxError as e:
                issues.append(f"코드 블록 #{i + 1}에 구문 오류: {e.msg} (line {e.lineno})")

        # 2. 자기 모순 감지 (동일 답변 내 상반된 주장)
        response_lower = response.lower()
        contradiction_pairs = [
            ("동기", "비동기"),
            ("O(1)", "O(n)"),
            ("thread-safe", "not thread-safe"),
            ("가능합니다", "불가능합니다"),
        ]
        for a, b in contradiction_pairs:
            if a.lower() in response_lower and b.lower() in response_lower:
                # 같은 문단에서 모순이면 문제
                for para in response.split("\n\n"):
                    if a.lower() in para.lower() and b.lower() in para.lower():
                        issues.append(f"자기 모순 감지: '{a}'와 '{b}'가 같은 문단에 동시 존재")
                        break

        # 3. 과도한 반복 감지
        sentences = [s.strip() for s in response.split(".") if len(s.strip()) > 20]
        seen = set()
        for s in sentences:
            normalized = s.lower().strip()
            if normalized in seen:
                issues.append(f"반복 문장 감지: '{s[:50]}...'")
                break
            seen.add(normalized)

        return issues

    def _llm_verify(self, task: str, response: str) -> VerificationResult | None:
        """LLM을 호출하여 심층 검증합니다."""
        verify_prompt = (
            "당신은 엄격한 테크니컬 리뷰어입니다. 아래 답변에서 다음 사항들을 검증해주세요:\n"
            "1. 사실 오류 (부정확한 정보)\n"
            "2. 의미론적/논리적 모순 (앞뒤가 안 맞는 주장)\n"
            "3. 코드 버그 및 구문 오류\n"
            "4. 보안 취약점\n\n"
            f"## 원본 질문\n{task[:500]}\n\n"
            f"## 검증할 답변\n{response[:3000]}\n\n"
            "발견된 문제점만 명확하게 번호 목록으로 작성하세요.\n"
            "문제가 없다면 오직 '문제 없음'이라고만 출력하세요.\n"
            "문제를 지적할 때는 어떻게 수정해야 하는지도 함께 제안해주세요."
        )

        try:
            result_text = self._generate_fn(verify_prompt)
            if not result_text:
                return None

            result = VerificationResult()
            result.verification_reasoning = result_text

            # "문제 없음" 키워드 체크
            if "문제 없음" in result_text or "no issues" in result_text.lower():
                return result

            # 번호 목록 파싱
            lines = result_text.split("\n")
            for line in lines:
                stripped = line.strip()
                if re.match(r"^\d+[\.\)]\s", stripped):
                    issue = re.sub(r"^\d+[\.\)]\s*", "", stripped)
                    if len(issue) > 10:
                        result.issues_found.append(issue)

            return result

        except Exception:
            logger.exception("[CoV] LLM verification failed")
            return None
