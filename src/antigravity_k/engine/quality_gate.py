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

        s, i = self._check_output_contract(user_request, agent_output, task_type)
        score *= s
        issues.extend(i)

        s, i = self._check_safety(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_planning_mode(user_request, agent_output, task_type)
        score *= s
        issues.extend(i)

        s, i = self._check_repetition(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_internal_tag_leak(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_language_contamination(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_korean_readability(agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_current_info_grounding(user_request, agent_output)
        score *= s
        issues.extend(i)

        s, i = self._check_comparison_table(user_request, agent_output)
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
        if should_retry:
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

    def _check_output_contract(
        self, request: str, output: str, task_type: str
    ) -> tuple:
        """Codex/Claude 수준 응답 형식 계약을 휴리스틱으로 검증합니다."""
        score, issues = 1.0, []
        request_lower = request.lower()

        asks_for_code = task_type in ("coding", "complex", "complex_step") or bool(
            re.search(
                r"(코드|구현|작성|함수|알고리즘|python|javascript|typescript|"
                r"function|implement|write|code)",
                request_lower,
            )
        )
        if not asks_for_code:
            return score, issues

        code_blocks = re.findall(r"```(?:\w+)?\s*.*?```", output, re.DOTALL)
        prose = re.sub(r"```(?:\w+)?\s*.*?```", "", output, flags=re.DOTALL).strip()
        has_korean_prose = bool(re.search(r"[가-힣]{2,}", prose))

        if not code_blocks:
            score *= 0.3
            issues.append("요청된 코드 블록 누락")
        elif len(prose) < 80 or not has_korean_prose:
            score *= 0.45
            issues.append("코드-only 응답")
        elif len(output) < 200:
            score *= 0.75
            issues.append("코딩 응답 설명 부족")

        complexity_requested = bool(
            re.search(
                r"(복잡도|big-?o|성능|시간\s*복잡도|공간\s*복잡도|"
                r"time complexity|space complexity)",
                request_lower,
            )
        )
        if complexity_requested and not re.search(r"\bO\s*\([^)]+\)", output):
            score *= 0.55
            issues.append("Big-O 복잡도 누락")

        comparison_requested = bool(
            re.search(
                r"(비교|차이|장단점|compare|comparison|trade-?off)", request_lower
            )
        )
        output_lower = output.lower()
        markdown_table = bool(re.search(r"^\s*\|.+\|\s*$", output, re.MULTILINE))
        structured_comparison = markdown_table or bool(
            re.search(
                r"(장점|단점|기준|차이점|trade-?off|pros|cons|" r"1\.\s+.+\n\s*2\.\s+)",
                output_lower,
                re.DOTALL,
            )
        )
        if comparison_requested and not structured_comparison:
            score *= 0.55
            issues.append("비교 구조 부족")

        return score, issues

    def _check_planning_mode(self, request: str, output: str, task_type: str) -> tuple:
        """대규모/복잡한 아키텍처 변경 요청 시 Planning Mode (Artifacts) 작동 여부 검증"""
        score, issues = 1.0, []
        request_lower = request.lower()

        # 복잡한 변경을 요구하는 단어들
        is_complex_request = task_type == "complex" or bool(
            re.search(
                r"(아키텍처|구조|전면|대규모|마이그레이션|프레임워크|리팩토링|architecture|refactor|migrate|framework)",
                request_lower,
            )
        )

        if is_complex_request:
            has_plan_artifact = bool(
                re.search(r"implementation_plan\.md", output, re.IGNORECASE)
            )
            has_approval = bool(re.search(r"\[APPROVAL REQUIRED\]", output))

            if not has_plan_artifact and not has_approval:
                score *= 0.4
                issues.append(
                    "복잡한 태스크에서 Planning Mode(계획안 및 승인 요청) 누락 (재시도 필요)"
                )

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
        """내부 태그/추론 흔적이 사용자에게 유출되면 강하게 감점."""
        score, issues = 1.0, []
        leak_patterns = [
            (r"%%THINK_START%%", "%%THINK_START%% 태그 유출"),
            (r"%%THINK_END%%", "%%THINK_END%% 태그 유출"),
            (r"</?think>", "<think> 태그 유출"),
            (r"</?thought>", "<thought> 태그 유출"),
            (r"<algorithm>.*?</algorithm>", "<algorithm> 태그 유출"),
            (r"---\s*\*?Thinking Process\*?\s*---", "Thinking Process 섹션 유출"),
            (r"---\s*\*?End of Thinking\*?\s*---", "End of Thinking 섹션 유출"),
            (r"The user wants me to", "영어 혼잣말(monologue) 유출"),
            (r"\bOkay,\s*I need to\b", "영어 내부 추론 유출"),
            (r"\bI need to:?\n", "영어 내부 계획(plan) 유출"),
            (r"\bI should\b", "영어 내부 계획(plan) 유출"),
            (r"\bThe first step is\b", "영어 내부 절차 서술 유출"),
            (r"\bSo the plan is\b", "영어 내부 계획(plan) 유출"),
            (r"\bLooking at the persistent context\b", "내부 컨텍스트 언급 유출"),
        ]
        for pattern, desc in leak_patterns:
            if re.search(pattern, output, re.DOTALL | re.IGNORECASE):
                score *= 0.35
                issues.append(desc)
        return score, issues

    def _check_language_contamination(self, output: str) -> tuple:
        """한국어 응답에 중국어/일본어 문자가 혼입되면 감점.
        코드 블록 내부는 제외합니다."""
        score, issues = 1.0, []
        # 코드 블록 제거 후 산문(prose)만 검사
        prose = re.sub(r"```(?:\w+)?\s*.*?```", "", output, flags=re.DOTALL).strip()
        # 중국어 간체/번체 (한국어 한자 범위 밖)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", prose)
        # 한국어 한자(한문) 사용은 허용하되, 중국어 문장 패턴 감지
        chinese_phrases = re.findall(r"[\u4e00-\u9fff]{3,}", prose)
        # 일본어 히라가나/카타카나 혼입
        japanese_chars = re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", prose)
        suspicious_cjk_terms = re.findall(
            r"(文件|できません|アップ|アップグレード|グレード|できます)",
            prose,
            flags=re.IGNORECASE,
        )
        if suspicious_cjk_terms:
            score *= 0.35
            issues.append(
                "한국어 응답 내 외국어 오염 감지 "
                f"({', '.join(sorted(set(suspicious_cjk_terms))[:3])})"
            )
        if len(chinese_phrases) >= 2:
            score *= 0.4
            issues.append(
                f"중국어 문자열 혼입 감지 ({len(chinese_phrases)}개 구절: "
                f"{'、'.join(chinese_phrases[:3])})"
            )
        elif len(chinese_chars) > 5:
            score *= 0.6
            issues.append(f"중국어 문자 다수 혼입 ({len(chinese_chars)}자)")
        if japanese_chars:
            score *= 0.35 if len(japanese_chars) > 3 else 0.55
            issues.append(f"일본어 문자 혼입 ({len(japanese_chars)}자)")
        return score, issues

    def _check_korean_readability(self, output: str) -> tuple:
        """한국어 산문의 띄어쓰기/문장 경계 붕괴를 탐지합니다."""
        score, issues = 1.0, []
        prose = re.sub(r"```(?:\w+)?\s*.*?```", "", output, flags=re.DOTALL).strip()
        if not re.search(r"[가-힣]{2,}", prose):
            return score, issues

        bad_spacing_terms = re.findall(
            r"(할수|될수|사용할수|작성할수|확인할수|알려줄래|"
            r"당신의프로젝트|확인하고어떻게|로컬LLM모델의을|"
            r"모델의을|내가업|응답でき|업グ레?드)",
            prose,
        )
        long_glued_hangul = re.findall(r"[가-힣]{13,}", prose)
        missing_sentence_spaces = re.findall(r"[.!?。][가-힣A-Za-z]", prose)
        korean_foreign_glue = re.findall(
            r"(?:[가-힣][A-Za-z]{3,}[가-힣]|[가-힣]{2,}[A-Za-z]{3,}|[A-Za-z]{3,}[가-힣]{2,})",
            prose,
        )

        defect_count = (
            len(bad_spacing_terms)
            + len(long_glued_hangul)
            + len(missing_sentence_spaces)
            + max(0, len(korean_foreign_glue) - 2)
        )
        if defect_count >= 6:
            score *= 0.35
            issues.append("한국어 띄어쓰기/가독성 붕괴")
        elif defect_count >= 3:
            score *= 0.6
            issues.append("한국어 띄어쓰기/문장 경계 품질 저하")
        return score, issues

    def _check_current_info_grounding(self, request: str, output: str) -> tuple:
        """최신/현재 정보 요청에서 cutoff 핑계나 미검증 답변을 감점합니다."""
        score, issues = 1.0, []
        request_lower = request.lower()
        asks_current_info = bool(
            re.search(
                r"(최신|최근|동향|실시간|현재|오늘|이번\s*주|latest|recent|"
                r"current|trend|news|today)",
                request_lower,
            )
        )
        if not asks_current_info:
            return score, issues

        output_lower = output.lower()
        stale_or_ungrounded = bool(
            re.search(
                r"(knowledge cutoff|as of my knowledge cutoff|october\s+2023|"
                r"2023년\s*10월|실시간\s*데이터.*없|인터넷.*접속.*없|"
                r"real[- ]?time data.*not|available up until)",
                output_lower,
            )
        )
        has_date_or_source = bool(
            re.search(
                r"(20\d{2}[년./-]\s*\d{1,2}|출처|source|검색|확인|"
                r"https?://|github|hugging\s*face)",
                output_lower,
            )
        )
        if stale_or_ungrounded:
            score *= 0.35
            issues.append("최신 정보 요청에서 지식 cutoff/비검증 답변")
        elif not has_date_or_source:
            score *= 0.7
            issues.append("최신 정보 요청에 날짜/출처/검증 근거 부족")
        return score, issues

    def _check_comparison_table(self, request: str, output: str) -> tuple:
        """비교 요청 시 Markdown 테이블이 포함되지 않으면 감점.
        Codex/Claude Code 수준의 구조화된 비교를 강제합니다."""
        score, issues = 1.0, []
        request_lower = request.lower()
        comparison_requested = bool(
            re.search(
                r"(비교|차이|장단점|compare|comparison|versus|vs\b|trade-?off)",
                request_lower,
            )
        )
        if not comparison_requested:
            return score, issues

        has_table = bool(re.search(r"^\s*\|.+\|.+\|\s*$", output, re.MULTILINE))
        if not has_table:
            score *= 0.65
            issues.append("비교 요청에 Markdown 비교표(table) 누락")
        return score, issues
