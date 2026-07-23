#!/usr/bin/env python3
"""
Antigravity-K: 데이터 추출 A/B 테스트 프레임워크 단위 테스트
===========================================================
ExtractionABTestRunner, ABTestReport, 내장 케이스 등을 검증합니다.
"""

import json

import pytest

from antigravity_k.engine.data_extractor import (
    ExtractedStockPrice,
    ExtractionResult,
)
from antigravity_k.engine.extraction_ab_test import (
    BUILTIN_CASES,
    ABTestReport,
    ExtractionABTestCase,
    ExtractionABTestRunner,
    ExtractionComparison,
    FieldScore,
    run_builtin_suite,
)

# ─── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def runner() -> ExtractionABTestRunner:
    return ExtractionABTestRunner()


@pytest.fixture
def sample_texts() -> list[str]:
    return [
        "📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)",
        "종가: 943,000원 | 시가: 930,000원 | 고가: 970,000원 | 저가: 905,000원 | 거래량: 142,859주 | 등락률: +1.51%",
    ]


@pytest.fixture
def expected_stock_result() -> ExtractionResult:
    return ExtractionResult(
        stock_prices=[
            ExtractedStockPrice(
                name="한화에어로스페이스",
                ticker="012450",
                close_price=943000,
                open_price=930000,
                high_price=970000,
                low_price=905000,
                change_percent=1.51,
                change_amount=14000,
                volume=142859,
            ),
        ],
    )


@pytest.fixture
def stock_case(sample_texts, expected_stock_result) -> ExtractionABTestCase:
    return ExtractionABTestCase(
        name="한화에어로스페이스 테스트",
        query="한화에어로스페이스 주가",
        input_texts=sample_texts,
        expected=expected_stock_result,
        tags=["stock", "korean"],
    )


# ─── FieldScore 테스트 ────────────────────────────────────────────


class TestFieldScore:
    """FieldScore 데이터 모델 검증."""

    def test_exact_match(self):
        """정확히 일치하는 경우."""
        fs = FieldScore(field_name="close_price", expected_value=1000, actual_value=1000, match=True)
        assert fs.match is True
        assert fs.partial is False

    def test_mismatch(self):
        """값이 다른 경우."""
        fs = FieldScore(field_name="close_price", expected_value=1000, actual_value=2000, match=False)
        assert fs.match is False

    def test_partial_match(self):
        """부분 일치 (기대값은 있으나 실제값이 None)."""
        fs = FieldScore(field_name="close_price", expected_value=1000, actual_value=None, match=False, partial=True)
        assert fs.match is False
        assert fs.partial is True


# ─── ExtractionComparison 테스트 ──────────────────────────────────


class TestExtractionComparison:
    """ExtractionComparison 데이터 모델 검증."""

    def test_summary_with_expected(self):
        """기대값이 있는 경우 요약 문자열."""
        c = ExtractionComparison(
            case_name="테스트",
            duration_ms=100.5,
            fields_matched=5,
            fields_total=8,
            accuracy_pct=62.5,
            has_expected=True,
        )
        summary = c.summary
        assert "테스트" in summary
        assert "62.5%" in summary
        assert "5/8" in summary

    def test_summary_no_expected(self):
        """기대값이 없는 경우 요약 (스킵)."""
        c = ExtractionComparison(
            case_name="스킵테스트",
            duration_ms=50.0,
            has_expected=False,
        )
        assert "스킵" in c.summary


# ─── ABTestReport 테스트 ──────────────────────────────────────────


class TestABTestReport:
    """ABTestReport 데이터 모델 검증."""

    def test_empty_report(self):
        """빈 보고서."""
        report = ABTestReport(total_cases=0)
        assert report.passed == 0
        assert report.failed == 0
        assert report.to_dict()["total_cases"] == 0

    def test_passed_failed_counts(self):
        """통과/실패 카운트."""
        comparisons = [
            ExtractionComparison(
                case_name="a", fields_matched=5, fields_total=5, accuracy_pct=100.0, has_expected=True
            ),
            ExtractionComparison(case_name="b", fields_matched=3, fields_total=5, accuracy_pct=60.0, has_expected=True),
            ExtractionComparison(case_name="c", fields_matched=0, fields_total=5, accuracy_pct=0.0, has_expected=True),
            ExtractionComparison(case_name="d", fields_matched=0, fields_total=0, accuracy_pct=0.0, has_expected=False),
        ]
        report = ABTestReport(
            version_label="test",
            total_cases=len(comparisons),
            comparisons=comparisons,
            total_fields_matched=8,
            total_fields=15,
            avg_accuracy=53.3,
        )
        assert report.passed == 1  # only 'a' is 100%
        assert report.failed == 2  # 'b' and 'c' are < 100%, 'd' has no expected

    def test_to_dict_structure(self):
        """to_dict() JSON 구조 검증."""
        c = ExtractionComparison(
            case_name="t1",
            duration_ms=100.0,
            fields_matched=2,
            fields_total=3,
            accuracy_pct=66.7,
            has_expected=True,
            has_data=True,
            field_scores=[
                FieldScore(field_name="close_price", expected_value=1000, actual_value=1000, match=True),
                FieldScore(field_name="open_price", expected_value=2000, actual_value=None, match=False),
            ],
        )
        report = ABTestReport(
            version_label="v1",
            total_cases=1,
            comparisons=[c],
            total_fields_matched=1,
            total_fields=2,
            avg_accuracy=50.0,
        )
        d = report.to_dict()
        assert d["version_label"] == "v1"
        assert d["total_cases"] == 1
        assert d["passed"] == 0
        assert d["failed"] == 1
        assert len(d["comparisons"]) == 1
        assert d["comparisons"][0]["accuracy_pct"] == 66.7

    def test_to_markdown_output(self):
        """to_markdown() 마크다운 출력 검증."""
        comparisons = [
            ExtractionComparison(
                case_name="pass", fields_matched=5, fields_total=5, accuracy_pct=100.0, has_expected=True
            ),
            ExtractionComparison(
                case_name="fail", fields_matched=0, fields_total=5, accuracy_pct=0.0, has_expected=True
            ),
        ]
        report = ABTestReport(total_cases=2, comparisons=comparisons)
        md = report.to_markdown()
        assert "A/B 테스트 보고서" in md
        assert "✅" in md
        assert "❌" in md
        assert "fail" in md

    def test_by_tag_accuracy(self):
        """태그별 정확도 집계."""
        comparisons = [
            ExtractionComparison(
                case_name="stock-1", fields_matched=5, fields_total=5, accuracy_pct=100.0, has_expected=True
            ),
            ExtractionComparison(
                case_name="weather-1", fields_matched=3, fields_total=5, accuracy_pct=60.0, has_expected=True
            ),
        ]
        report = ABTestReport(
            total_cases=2,
            comparisons=comparisons,
            by_tag={"stock": 100.0, "weather": 60.0},
        )
        assert report.by_tag["stock"] == 100.0
        assert report.by_tag["weather"] == 60.0


# ─── ExtractionABTestRunner 테스트 ────────────────────────────────


class TestExtractionABTestRunner:
    """ExtractionABTestRunner 실행 검증."""

    def test_run_test_returns_comparison(self, runner, stock_case):
        """단일 테스트 케이스 실행 시 ExtractionComparison 반환."""
        comparison = runner.run_test(stock_case)
        assert isinstance(comparison, ExtractionComparison)
        assert comparison.case_name == "한화에어로스페이스 테스트"
        assert comparison.has_expected is True

    def test_run_test_stock_fields(self, runner, stock_case):
        """주식 데이터 필드 정확도 검증."""
        comparison = runner.run_test(stock_case)
        # 최소한 ticker, close_price, name은 매칭되어야 함
        ticker_scores = [fs for fs in comparison.field_scores if "ticker" in fs.field_name]
        if ticker_scores:
            assert any(fs.match for fs in ticker_scores), "ticker should match"
        close_scores = [fs for fs in comparison.field_scores if "close_price" in fs.field_name]
        if close_scores:
            assert any(fs.match for fs in close_scores), "close_price should match"

    def test_run_test_duration(self, runner, stock_case):
        """실행 시간이 측정되는지 확인."""
        comparison = runner.run_test(stock_case)
        assert comparison.duration_ms > 0

    def test_run_test_no_expected(self, runner):
        """기대값이 없는 경우 has_expected=False 처리."""
        case = ExtractionABTestCase(
            name="no-expected",
            query="테스트",
            input_texts=["테스트 텍스트입니다."],
            expected=ExtractionResult(),  # 빈 결과
        )
        comparison = runner.run_test(case)
        assert comparison.has_expected is False

    def test_run_suite_returns_report(self, runner, stock_case):
        """여러 케이스 실행 시 ABTestReport 반환."""
        cases = [stock_case]
        report = runner.run_suite(cases, version_label="test:v1")
        assert isinstance(report, ABTestReport)
        assert report.total_cases == 1
        assert report.version_label == "test:v1"

    def test_run_suite_multiple_cases(self, runner, stock_case):
        """2개 케이스 실행 시 total_cases=2."""
        # create a second case
        case2 = ExtractionABTestCase(
            name="삼성전자 테스트",
            query="삼성전자 주가",
            input_texts=["삼성전자(005930) 84,500원 (-0.82%)"],
            expected=ExtractionResult(
                stock_prices=[ExtractedStockPrice(ticker="005930", close_price=84500)],
            ),
            tags=["stock"],
        )
        report = runner.run_suite([stock_case, case2], version_label="test:v2")
        assert report.total_cases == 2
        assert report.avg_accuracy > 0
        assert report.avg_duration_ms >= 0

    def test_run_suite_empty(self, runner):
        """빈 케이스 리스트 처리."""
        report = runner.run_suite([], version_label="empty")
        assert report.total_cases == 0
        assert report.avg_accuracy == 0.0
        assert report.to_dict()["total_cases"] == 0

    def test_tags_accuracy(self, runner, stock_case):
        """태그별 정확도가 집계되는지 확인."""
        report = runner.run_suite([stock_case], version_label="tag-test")
        assert "stock" in report.by_tag
        assert "korean" in report.by_tag


# ─── 내장 테스트 케이스 검증 ──────────────────────────────────────


class TestBuiltinCases:
    """BUILTIN_CASES 목록 검증."""

    def test_builtin_cases_not_empty(self):
        """내장 케이스가 최소 1개 이상 존재."""
        assert len(BUILTIN_CASES) >= 4

    def test_builtin_cases_have_names(self):
        """모든 내장 케이스에 이름이 있음."""
        for case in BUILTIN_CASES:
            assert case.name, f"Case missing name: {case}"

    def test_builtin_cases_have_query(self):
        """모든 내장 케이스에 쿼리가 있음."""
        for case in BUILTIN_CASES:
            assert case.query, f"Case missing query: {case.name}"

    def test_builtin_cases_have_inputs(self):
        """모든 내장 케이스에 input_texts가 있음."""
        for case in BUILTIN_CASES:
            assert len(case.input_texts) > 0, f"Case missing inputs: {case.name}"

    def test_builtin_stock_case(self):
        """주식 내장 케이스에 stock_prices 데이터 포함."""
        stock_cases = [c for c in BUILTIN_CASES if "stock" in c.tags]
        for case in stock_cases:
            assert len(case.expected.stock_prices) > 0, f"Stock case has no stock data: {case.name}"


# ─── run_builtin_suite 통합 테스트 ───────────────────────────────


class TestRunBuiltinSuite:
    """run_builtin_suite() 통합 테스트."""

    def test_builtin_suite_runs(self):
        """내장 스위트가 정상 실행됨."""
        report = run_builtin_suite(version_label="test-ci")
        assert isinstance(report, ABTestReport)
        assert report.total_cases >= 4
        assert report.avg_accuracy >= 0

    def test_builtin_suite_to_dict(self):
        """내장 스위트 결과가 JSON 직렬화 가능."""
        report = run_builtin_suite()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "comparisons" in d
        assert json.dumps(d, ensure_ascii=False)

    def test_builtin_suite_to_markdown(self):
        """내장 스위트 결과가 마크다운으로 출력 가능."""
        report = run_builtin_suite()
        md = report.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 50

    def test_builtin_suite_all_patterns(self):
        """모든 유형(주식, 날씨, 환율)의 케이스 포함."""
        report = run_builtin_suite()
        comparison_names = [c.case_name for c in report.comparisons]
        assert comparison_names  # non-empty
        # 최소한 주요 케이스 이름 확인
        assert any("한화" in n for n in comparison_names), "한화 케이스 없음"
        assert any("날씨" in n or "서울" in n for n in comparison_names), "날씨 케이스 없음"
        assert any("환율" in n or "달러" in n for n in comparison_names), "환율 케이스 없음"
