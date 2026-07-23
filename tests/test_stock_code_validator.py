"""Tests for antigravity_k.engine.stock_code_validator."""

from antigravity_k.engine.stock_code_validator import (
    enrich_search_query,
    extract_stock_codes,
    format_code_correction,
    has_stock_context,
    validate_query_stock_codes,
    validate_stock_code,
)

# ─── extract_stock_codes ─────────────────────────────────────────


class TestExtractStockCodes:
    def test_valid_6_digit_code(self):
        """6자리 숫자를 정확히 추출해야 함."""
        assert extract_stock_codes("012450 주가 알려줘") == ["012450"]

    def test_multiple_codes(self):
        """여러 개의 6자리 숫자를 모두 추출해야 함."""
        codes = extract_stock_codes("005930 012450 주가")
        assert codes == ["005930", "012450"]

    def test_no_code(self):
        """숫자가 없으면 빈 리스트 반환."""
        assert extract_stock_codes("삼성전자 주가") == []

    def test_5_digit_number(self):
        """5자리 숫자는 추출하지 않음."""
        assert extract_stock_codes("12345 주가") == []

    def test_7_digit_number(self):
        """7자리 숫자는 추출하지 않음."""
        assert extract_stock_codes("1234567 주가") == []

    def test_code_in_middle(self):
        """중간에 있는 코드도 추출."""
        assert extract_stock_codes("어제 012450 주가 알려줘") == ["012450"]

    def test_embedded_in_longer_number(self):
        """더 긴 숫자에 포함된 6자리는 추출하지 않음."""
        assert extract_stock_codes("123012450789 주가") == []

    def test_comma_separated(self):
        """쉼표로 구분된 코드도 추출."""
        codes = extract_stock_codes("005930,012450 주가")
        assert codes == ["005930", "012450"]


# ─── has_stock_context ───────────────────────────────────────────


class TestHasStockContext:
    def test_korean_stock_keywords(self):
        """한국어 주식 키워드 감지."""
        assert has_stock_context("주가 알려줘") is True
        assert has_stock_context("주식 시세") is True
        assert has_stock_context("코스피 지수") is True
        assert has_stock_context("종목 코드") is True

    def test_english_stock_keywords(self):
        """영어 주식 키워드 감지."""
        assert has_stock_context("stock price") is True
        assert has_stock_context("ticker symbol") is True

    def test_no_stock_context(self):
        """주식 관련 없는 쿼리는 False."""
        assert has_stock_context("오늘 날씨 알려줘") is False
        assert has_stock_context("안녕하세요") is False
        assert has_stock_context("Python 코드 작성") is False


# ─── validate_stock_code ─────────────────────────────────────────


class TestValidateStockCode:
    def test_valid_kospi_code(self):
        """유효한 KOSPI 종목코드."""
        result = validate_stock_code("005930")
        assert result.is_valid is True
        assert result.company_name == "삼성전자"

    def test_valid_kosdaq_code(self):
        """유효한 KOSDAQ 종목코드."""
        result = validate_stock_code("091990")
        assert result.is_valid is True
        assert result.company_name == "셀트리온헬스케어"

    def test_invalid_code_with_suggestion(self):
        """잘못된 코드 — 유사 코드 추천."""
        # 096732 → 012450 (한화에어로스페이스)와 유사하지 않음
        # 012450과 첫 3자리(012)는 같지 않으니 다른 매칭 확인
        # 096760 (SK가스)와 유사한지 확인
        result = validate_stock_code("096732")
        assert result.is_valid is False
        assert result.needs_correction is True
        # 첫 3자리 096 으로 시작하는 종목이 있음 (096760 SK가스, 096770 SK이노베이션)
        assert result.suggested_code
        assert result.suggested_name

    def test_invalid_format(self):
        """형식이 잘못된 코드."""
        result = validate_stock_code("12345")
        assert result.is_valid is False
        assert result.needs_correction is False
        assert "형식" in result.message

        result2 = validate_stock_code("abcdef")
        assert result2.is_valid is False

    def test_unknown_code_no_suggestion(self):
        """대조표에 없는 코드 — 추천 없음."""
        # 999999는 대조표에 없고 유사 코드도 없음
        result = validate_stock_code("999999")
        assert result.is_valid is False
        assert result.suggested_code == ""
        assert "대조표에 없는" in result.message


# ─── validate_query_stock_codes ────────────────────────────────────


class TestValidateQueryStockCodes:
    def test_valid_code_in_query(self):
        """유효한 코드가 포함된 쿼리."""
        result = validate_query_stock_codes("005930 주가 알려줘")
        assert result.needs_correction is False
        assert len(result.codes_found) == 1
        assert result.codes_found[0].is_valid is True
        assert result.codes_found[0].company_name == "삼성전자"

    def test_invalid_code_in_query(self):
        """잘못된 코드가 포함된 쿼리."""
        result = validate_query_stock_codes("096732 주가 알려줘")
        assert result.needs_correction is True
        assert result.corrected_query != result.original_query
        assert "096732" not in result.corrected_query

    def test_no_code_in_query(self):
        """코드 없는 쿼리는 교정 불필요."""
        result = validate_query_stock_codes("삼성전자 주가 알려줘")
        assert result.needs_correction is False
        assert result.codes_found == []
        assert result.corrected_query == "삼성전자 주가 알려줘"

    def test_mixed_valid_and_invalid(self):
        """유효 코드 + 잘못된 코드 혼합."""
        result = validate_query_stock_codes("005930 096732 주가")
        assert result.needs_correction is True
        assert len(result.codes_found) == 2
        # 005930은 유효
        assert result.codes_found[0].is_valid is True
        # 096732는 무효 (추천 포함)
        assert result.codes_found[1].is_valid is False


# ─── enrich_search_query ─────────────────────────────────────────


class TestEnrichSearchQuery:
    def test_corrects_query(self):
        """잘못된 코드가 교정된 쿼리로 변경."""
        validation = validate_query_stock_codes("096732 주가 알려줘")
        enriched = enrich_search_query("096732 주가 알려줘", validation)
        assert "096732" not in enriched
        assert "012450" in enriched or "096760" in enriched or "096770" in enriched

    def test_preserves_valid_query(self):
        """유효한 쿼리는 그대로 유지."""
        validation = validate_query_stock_codes("삼성전자 주가")
        enriched = enrich_search_query("삼성전자 주가", validation)
        assert enriched == "삼성전자 주가"


# ─── format_code_correction ──────────────────────────────────────


class TestFormatCodeCorrection:
    def test_generates_message_for_invalid(self):
        """잘못된 코드에 대한 메시지 생성."""
        validation = validate_query_stock_codes("096732 주가 알려줘")
        msg = format_code_correction(validation)
        assert "096732" in msg
        assert "잘못" in msg or "교정" in msg

    def test_empty_for_valid(self):
        """유효한 코드면 빈 문자열."""
        validation = validate_query_stock_codes("005930 주가")
        assert format_code_correction(validation) == ""

    def test_empty_for_no_code(self):
        """코드 없으면 빈 문자열."""
        validation = validate_query_stock_codes("날씨 알려줘")
        assert format_code_correction(validation) == ""


# ─── Edge Cases ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_string(self):
        """빈 문자열 처리."""
        assert extract_stock_codes("") == []
        result = validate_query_stock_codes("")
        assert result.needs_correction is False
        assert result.codes_found == []

    def test_special_characters(self):
        """특수문자 포함."""
        codes = extract_stock_codes("012450!@#$%^&*()")
        assert codes == ["012450"]

    def test_unicode(self):
        """유니코드 포함."""
        codes = extract_stock_codes("📈 012450 주가 📉")
        assert codes == ["012450"]

    def test_stock_context_unicode(self):
        """유니코드 이모지 포함 주식 컨텍스트."""
        assert has_stock_context("📈 주가") is True
        assert has_stock_context("코스닥 🚀") is True

    def test_whitespace_variations(self):
        """공백 변형 처리."""
        codes = extract_stock_codes(" 012450  주가")
        assert codes == ["012450"]

    def test_kospi_code_prefix_check(self):
        """005930 (삼성전자) — 가장 많이 검색되는 종목."""
        result = validate_stock_code("005930")
        assert result.is_valid is True
        assert result.company_name == "삼성전자"

    def test_preferred_stock(self):
        """우선주 처리."""
        result = validate_stock_code("005935")
        assert result.is_valid is True
        assert "삼성전자" in result.company_name
        assert "우" in result.company_name
