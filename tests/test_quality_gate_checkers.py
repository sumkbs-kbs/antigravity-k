"""테스트: QualityGate 세부 체커.
==========================
안전/반복/태그유출/언어오염/정보밀도/마크다운 규약 체커의 감점 계약을 검증한다.
"""

from collections.abc import Callable
from typing import cast

import pytest

from antigravity_k.engine.quality_gate import QualityGate

ScoreIssues = tuple[float, list[str]]


def run_checker(gate: QualityGate, name: str, output: str) -> ScoreIssues:
    checker = cast(Callable[[str], ScoreIssues], getattr(gate, name))
    return checker(output)


@pytest.fixture
def gate() -> QualityGate:
    return QualityGate(max_retries=1)


class TestSafetyChecker:
    def test_dangerous_commands_penalized(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_safety", "실행: rm -rf / 그리고 mkfs.ext4")

        assert score < 1.0
        assert any("루트삭제" in i for i in issues)
        assert any("디스크포맷" in i for i in issues)

    def test_safe_output_untouched(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_safety", "정상적인 답변입니다")

        assert score == 1.0
        assert issues == []


class TestRepetitionChecker:
    def test_severe_loop_detected(self, gate: QualityGate) -> None:
        filler_lines = [f"반복 라인 {idx}: 충분히 긴 문장으로 블록 경계를 만든다" for idx in range(6)]
        block = "\n".join(filler_lines)
        output = "\n".join([block] * 8)

        score, issues = run_checker(gate, "_check_repetition", output)

        assert score <= 0.1
        assert any("심각한 반복" in i for i in issues)

    def test_short_outputs_skipped(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_repetition", "짧은 답변")

        assert score == 1.0
        assert issues == []


class TestInternalTagLeak:
    def test_think_tag_leak_penalized(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_internal_tag_leak", "답변 <think>숨은 추론</think> 끝")

        assert score < 0.5
        assert any("<think>" in i for i in issues)

    def test_clean_output_passes(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_internal_tag_leak", "깨끗한 사용자 응답입니다.")

        assert score == 1.0
        assert issues == []


class TestLanguageContamination:
    def test_japanese_contamination_detected(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_language_contamination", "설명입니다。アップグレードできます、확인してください。")

        assert score < 1.0
        assert any("일본어" in i for i in issues)

    def test_code_block_cjk_is_exempt(self, gate: QualityGate) -> None:
        output = "한국어 설명입니다.\n```python\n# 中文注释 できません\nprint('x')\n```"

        score, issues = run_checker(gate, "_check_language_contamination", output)

        assert score == 1.0
        assert issues == []

    def test_chinese_phrase_heavy_prose_detected(self, gate: QualityGate) -> None:
        output = "이것은 테스트입니다。文件을 확인하고 产能을 올리세요。先进技術です。"

        score, _ = run_checker(gate, "_check_language_contamination", output)

        assert score < 1.0


class TestInformationDensity:
    def test_short_output_skipped(self, gate: QualityGate) -> None:
        score, _ = run_checker(gate, "_check_information_density", "짧아요")

        assert score == 1.0

    def test_highly_repetitive_long_prose_penalized(self, gate: QualityGate) -> None:
        sentence = "이 프로젝트는 매우 흥미롭고 다양한 기능을 제공합니다"
        filler = " ".join([sentence] * 12) + "."

        score, issues = run_checker(gate, "_check_information_density", filler)

        assert score < 1.0
        assert issues


class TestMarkdownStandards:
    def test_old_note_block_recommended_to_alerts(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_github_alerts", "**Note**: 구형 스타일입니다\n\n본문")

        assert score < 1.0
        assert any("GitHub Alert" in i for i in issues)

    def test_proper_alert_block_passes(self, gate: QualityGate) -> None:
        output = "> [!NOTE]\n> 올바른 경고 블록"

        score, issues = run_checker(gate, "_check_github_alerts", output)

        assert score == 1.0
        assert issues == []

    def test_carousel_syntax_error_detected(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_antigravity_markdown_standards", "<!-- slide -->\n내용뿐인 잘못된 선언")

        assert score < 1.0
        assert any("Carousel" in i for i in issues)

    def test_backtick_file_link_flagged(self, gate: QualityGate) -> None:
        score, issues = run_checker(gate, "_check_antigravity_markdown_standards", "[`src/main.py`](file://src/main.py) 참고")

        assert score < 1.0
        assert any("백틱" in i for i in issues)
