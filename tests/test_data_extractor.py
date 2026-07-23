"""Tests for antigravity_k.engine.data_extractor.

Coverage areas:
  - ExtractionResult dataclass (has_data, format_for_llm)
  - DataExtractor.extract_stock_prices (6 data sources)
  - DataExtractor.extract_weather (3 data sources)
  - DataExtractor.extract_exchange_rate
  - DataExtractor.extract_dates (Korean + ISO)
  - DataExtractor.extract_numeric_data
  - DataExtractor.extract_all (integration)
  - extract_structured_data shortcut
"""

import pytest

from antigravity_k.engine.data_extractor import (
    DataExtractor,
    ExtractedExchangeRate,
    ExtractedNumericData,
    ExtractedStockPrice,
    ExtractedWeather,
    ExtractionResult,
    extract_structured_data,
)

# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def extractor() -> DataExtractor:
    return DataExtractor()


# ─── ExtractionResult ──────────────────────────────────────────────


class TestExtractionResult:
    def test_has_data_empty(self):
        """빈 결과는 has_data()가 False."""
        result = ExtractionResult()
        assert result.has_data() is False

    def test_has_data_with_stock(self):
        """주식 데이터가 있으면 has_data()가 True."""
        result = ExtractionResult(stock_prices=[ExtractedStockPrice(close_price=1000)])
        assert result.has_data() is True

    def test_has_data_with_weather(self):
        """날씨 데이터가 있으면 has_data()가 True."""
        result = ExtractionResult(weather=[ExtractedWeather(temperature=25.0)])
        assert result.has_data() is True

    def test_has_data_with_exchange(self):
        """환율 데이터가 있으면 has_data()가 True."""
        result = ExtractionResult(exchange_rates=[ExtractedExchangeRate(rate=1300.0)])
        assert result.has_data() is True

    def test_has_data_with_numeric(self):
        """기타 숫자 데이터가 있으면 has_data()가 True."""
        result = ExtractionResult(numeric_data=[ExtractedNumericData(label="GDP")])
        assert result.has_data() is True

    def test_has_data_with_dates(self):
        """날짜가 있으면 has_data()가 True."""
        result = ExtractionResult(dates_found=["2026년 7월 16일"])
        assert result.has_data() is True

    def test_format_for_llm_empty(self):
        """데이터가 없으면 빈 문자열 반환."""
        result = ExtractionResult()
        assert result.format_for_llm() == ""

    def test_format_for_llm_stock(self):
        """주식 데이터가 포함된 LLM 포맷 출력."""
        sp = ExtractedStockPrice(
            name="한화에어로스페이스",
            ticker="012450",
            close_price=943000,
            change_percent=1.51,
            change_amount=14000,
            volume=142859,
        )
        result = ExtractionResult(stock_prices=[sp])
        text = result.format_for_llm()
        assert "📈" in text
        assert "한화에어로스페이스" in text
        assert "943,000원" in text
        assert "종가" in text
        assert "+1.51%" in text or "1.51%" in text
        assert "종목코드: 012450" in text
        assert "142,859주" in text

    def test_format_for_llm_weather(self):
        """날씨 데이터가 포함된 LLM 포맷 출력."""
        w = ExtractedWeather(location="서울", temperature=28.5, humidity=65, condition="맑음")
        result = ExtractionResult(weather=[w])
        text = result.format_for_llm()
        assert "☀️" in text or "📍" in text
        assert "서울" in text
        assert "28.5°C" in text
        assert "65%" in text

    def test_format_for_llm_max_lines(self):
        """max_lines 제한이 올바르게 동작."""
        stocks = [ExtractedStockPrice(name=f"종목{i}", ticker=f"00000{i}", close_price=i * 1000) for i in range(20)]
        result = ExtractionResult(stock_prices=stocks)
        text = result.format_for_llm(max_lines=3)
        lines = [line for line in text.split("\n") if line.strip() and not line.startswith("...")]
        assert len(lines) <= 3 + 1  # max_lines + possible truncation message

    def test_format_for_llm_exchange(self):
        """환율 데이터가 포함된 LLM 포맷 출력."""
        er = ExtractedExchangeRate(currency_pair="원/달러", rate=1382.50, change_percent=-0.12)
        result = ExtractionResult(exchange_rates=[er])
        text = result.format_for_llm()
        assert "💱" in text
        assert "원/달러" in text
        assert "1,382.50" in text or "1382.50" in text


# ─── DataExtractor.extract_stock_prices ────────────────────────────


class TestExtractStockPrices:
    def test_self_hosted_snippet(self, extractor):
        """Self-Hosted 엔진 구조화 출력에서 추출."""
        sp = extractor.extract_stock_prices("📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)")
        assert sp is not None
        assert sp.name == "한화에어로스페이스"
        assert sp.ticker == "012450"
        assert sp.close_price == 943000
        assert sp.change_percent == 1.51

    def test_self_hosted_snippet_negative(self, extractor):
        """Self-Hosted 출력 — 하락 (-부호)."""
        sp = extractor.extract_stock_prices("📊 삼성전자 (005930) 84,500원 -0.82% (하락)")
        assert sp is not None
        assert sp.name == "삼성전자"
        assert sp.ticker == "005930"
        assert sp.close_price == 84500
        assert sp.change_percent == -0.82

    def test_label_based_format(self, extractor):
        """라벨 기반 형식 (종가: 943,000원 ...)."""
        text = (
            "종가: 943,000원 | 시가: 930,000원 | 고가: 970,000원 | 저가: 905,000원 | 거래량: 142,859주 | 등락률: +1.51%"
        )
        sp = extractor.extract_stock_prices(text)
        assert sp is not None
        assert sp.close_price == 943000
        assert sp.open_price == 930000
        assert sp.high_price == 970000
        assert sp.low_price == 905000
        assert sp.volume == 142859
        assert sp.change_percent == 1.51

    def test_change_amount_with_symbol(self, extractor):
        """▲/▼ 기호를 포함한 등락액 추출."""
        sp = extractor.extract_stock_prices("한화에어로스페이스 943,000원 ▲14,000원")
        assert sp is not None
        assert sp.change_amount == 14000

    def test_change_amount_negative(self, extractor):
        """▼ 기호로 하락한 등락액 추출."""
        sp = extractor.extract_stock_prices("삼성전자 84,500원 ▼2,000원")
        assert sp is not None
        assert sp.change_amount == -2000

    def test_change_percent_with_arrow(self, extractor):
        """▲/▼ 기호를 포함한 등락률 추출."""
        sp = extractor.extract_stock_prices("▲1.51%")
        assert sp is not None
        assert sp.change_percent == 1.51

    def test_change_percent_negative_arrow(self, extractor):
        """▼ 기호 음수 등락률."""
        sp = extractor.extract_stock_prices("▼0.82%")
        assert sp is not None
        assert sp.change_percent == -0.82

    def test_price_only(self, extractor):
        """가격만 있는 텍스트에서 기본 추출."""
        sp = extractor.extract_stock_prices("943,000원")
        assert sp is not None
        assert sp.close_price == 943000

    def test_no_stock_data(self, extractor):
        """주식 데이터가 전혀 없으면 None."""
        sp = extractor.extract_stock_prices("오늘 날씨 맑음")
        assert sp is None

    def test_empty_string(self, extractor):
        """빈 문자열 처리."""
        sp = extractor.extract_stock_prices("")
        assert sp is None

    def test_krx_ticker_format(self, extractor):
        """종목코드가 포함된 형식."""
        # 종목코드가 _stock_names에 없으면 name만 추출
        sp = extractor.extract_stock_prices("삼성전자(005930) 84,500원 (-0.82%)")
        assert sp is not None
        assert sp.close_price == 84500

    def test_change_percent_no_sign(self, extractor):
        """부호 없는 등락률 (0%)."""
        sp = extractor.extract_stock_prices("등락률: 0%")
        assert sp is not None
        assert sp.change_percent == 0.0

    def test_price_no_commas(self, extractor):
        """쉼표 없는 가격."""
        sp = extractor.extract_stock_prices("종가: 943000원")
        assert sp is not None
        assert sp.close_price == 943000

    def test_change_amount_plus_sign(self, extractor):
        """+ 기호를 포함한 등락액: +14,000원"""
        sp = extractor.extract_stock_prices("한화에어로스페이스 943,000원 +14,000원")
        assert sp is not None
        assert sp.change_amount == 14000

    def test_change_amount_minus_sign(self, extractor):
        """- 기호를 포함한 등락액: -2,000원"""
        sp = extractor.extract_stock_prices("삼성전자 84,500원 -2,000원")
        assert sp is not None
        assert sp.change_amount == -2000

    # ── 만원/억원 표기법 테스트 ──

    def test_manwon_integer(self, extractor):
        """정수 만원: '95만원' → 950,000원"""
        sp = extractor.extract_stock_prices("한화에어로스페이스 95만원")
        assert sp is not None
        assert sp.close_price == 950000

    def test_manwon_decimal(self, extractor):
        """소수점 만원: '99.6만원' → 996,000원"""
        sp = extractor.extract_stock_prices("99.6만원")
        assert sp is not None
        assert sp.close_price == 996000

    def test_manwon_without_won(self, extractor):
        """만 (원 생략): '100만' → 1,000,000원"""
        sp = extractor.extract_stock_prices("100만")
        assert sp is not None
        assert sp.close_price == 1000000

    def test_manwon_comma_separated(self, extractor):
        """쉼표 포함 만원: '1,000만원' → 10,000,000원"""
        sp = extractor.extract_stock_prices("1,000만원")
        assert sp is not None
        assert sp.close_price == 10000000

    def test_manwon_with_space(self, extractor):
        """공백 포함: '95만 원' → 950,000원"""
        sp = extractor.extract_stock_prices("장중 최고 95만 원")
        assert sp is not None
        assert sp.close_price == 950000

    def test_eokwon_integer(self, extractor):
        """정수 억원: '2억원' → 200,000,000원"""
        sp = extractor.extract_stock_prices("시가총액 2억원")
        assert sp is not None
        assert sp.close_price == 200000000

    def test_eokwon_decimal(self, extractor):
        """소수점 억원: '1.5억원' → 150,000,000원"""
        sp = extractor.extract_stock_prices("1.5억원")
        assert sp is not None
        assert sp.close_price == 150000000

    def test_manwon_in_context(self, extractor):
        """실제 answer.text 맥락에서 만원 추출.

        '100만원을 향해'는 추측성 컨텍스트 → 필터링
        '장중 최고 95만원까지'는 '장중' 키워드로 유효 → 95만원 추출
        '목표 주가 99.6만원'은 '목표' 키워드 → 필터링
        """
        sp = extractor.extract_stock_prices(
            "한화에어로스페이스의 주가는 100만원을 향해 상승하고 있으며, "
            "2025년 6월 10일 장중 최고 95만원까지 치솟았습니다. "
            "증권가에서는 목표 주가를 99.6만원으로 제시"
        )
        assert sp is not None
        # '장중 최고 95만원'이 유효한 가격으로 추출되어야 함
        assert sp.close_price == 950000, f"예상: 950000 (장중 최고 95만원), 실제: {sp.close_price}"

    def test_false_positive_target_price_filtered(self, extractor):
        """'목표 186만인데 왜 빠지나' → 목표 키워드로 필터링되어야 함."""
        sp = extractor.extract_stock_prices("목표 186만인데 왜 빠지나, 지금 기회일까")
        # 가격 데이터가 없거나, ticker만 있어야 함 (close_price는 None)
        if sp is not None:
            assert sp.close_price is None, f"'186만'이 필터링되지 않음! close_price={sp.close_price}"

    def test_false_positive_directional_filtered(self, extractor):
        """'100만원을 향해' → 추측성 컨텍스트로 필터링.

        ticker도 없고 가격도 필터링되면 extract_stock_prices는 None 반환.
        """
        sp = extractor.extract_stock_prices("한화에어로스페이스 100만원을 향해 상승")
        # ticker가 없고 가격이 필터링되면 None 또는 close_price=None
        if sp is not None:
            assert sp.close_price is None, f"'100만원을 향해'가 필터링되지 않음! close_price={sp.close_price}"

    def test_false_positive_forecast_filtered(self, extractor):
        """'전망 200만원' → 전망 키워드로 필터링."""
        sp = extractor.extract_stock_prices("증권가 전망 200만원 목표가 제시")
        if sp is not None:
            assert sp.close_price is None, f"'전망 200만원'이 필터링되지 않음! close_price={sp.close_price}"

    def test_valid_current_price_kept(self, extractor):
        """'현재 95만원에 거래 중' → 유효 컨텍스트로 유지."""
        sp = extractor.extract_stock_prices("한화에어로스페이스 현재 95만원에 거래 중")
        assert sp is not None
        assert sp.close_price == 950000, f"'현재 95만원'이 필터링됨! close_price={sp.close_price}"

    def test_valid_trading_price_kept(self, extractor):
        """'장중 95만원 기록' → 장중 키워드로 유지."""
        sp = extractor.extract_stock_prices("장중 최고 95만원 기록")
        assert sp is not None
        assert sp.close_price == 950000, f"'장중 95만원'이 필터링됨! close_price={sp.close_price}"

    def test_valid_close_price_kept(self, extractor):
        """'종가 943,000원' → 라벨 기반 추출 우선, 컨텍스트 무관."""
        sp = extractor.extract_stock_prices("종가: 943,000원")
        assert sp is not None
        assert sp.close_price == 943000

    def test_speculative_suffix_filtered(self, extractor):
        """'95만원까지' → '까지' 접미사로 필터링."""
        sp = extractor.extract_stock_prices("95만원까지 치솟았습니다")
        if sp is not None:
            assert sp.close_price is None, f"'95만원까지'가 필터링되지 않음! close_price={sp.close_price}"

    def test_manwon_preferred_over_krw(self, extractor):
        """만원과 원 표기가 모두 있을 때 만원 우선 (원 패턴 우선)."""
        # '종가: 943,000원 | ... 95만원' → 원 패턴이 먼저 매칭
        text = "종가: 943,000원 | 장중 최고 95만원"
        sp = extractor.extract_stock_prices(text)
        assert sp is not None
        # 원 패턴이 라벨 기반에서 먼저 추출됨
        assert sp.close_price == 943000

    # ── 종목명 오탐 방지 테스트 ──

    def test_ticker_false_positive_kospi(self, extractor):
        """'KOSPI (012450) 95만원' → 이름이 'KOSPI'가 아닌 '한화에어로스페이스'여야 함."""
        sp = extractor.extract_stock_prices("KOSPI (012450) 95만원")
        assert sp is not None
        assert sp.close_price == 950000
        assert sp.ticker == "012450"
        # 'KOSPI'는 알려진 종목명이 아니므로 코드 매핑에서 공식명을 가져와야 함
        assert sp.name == "한화에어로스페이스", f"예상: 한화에어로스페이스, 실제: {sp.name}"

    def test_ticker_known_name_preserved(self, extractor):
        """'한화에어로스페이스 (012450)' → 정상 케이스, 이름 유지."""
        sp = extractor.extract_stock_prices("한화에어로스페이스 (012450) 95만원")
        assert sp is not None
        assert sp.close_price == 950000
        assert sp.ticker == "012450"
        assert sp.name == "한화에어로스페이스"

    def test_ticker_known_name_samsung(self, extractor):
        """'삼성전자 (005930) 84,500원' → 정상 케이스."""
        sp = extractor.extract_stock_prices("삼성전자 (005930) 84,500원")
        assert sp is not None
        assert sp.close_price == 84500
        assert sp.ticker == "005930"
        assert sp.name == "삼성전자"

    def test_ticker_false_positive_index(self, extractor):
        """'코스피 (012450)' 같은 지수명 → 코드 매핑의 공식명 사용."""
        sp = extractor.extract_stock_prices("코스피 (012450) 100만원")
        assert sp is not None
        assert sp.close_price == 1000000
        assert sp.ticker == "012450"
        # '코스피'는 종목명이 아니므로 '한화에어로스페이스'로 교정되어야 함
        assert sp.name == "한화에어로스페이스", f"예상: 한화에어로스페이스, 실제: {sp.name}"

    def test_ticker_pipe_separator(self, extractor):
        """파이프(|) 구분자: '한화에어로스페이스 | KOSPI 012450' → 종목명+코드 추출."""
        sp = extractor.extract_stock_prices("한화에어로스페이스 | KOSPI 012450")
        assert sp is not None
        assert sp.ticker == "012450"
        # name_candidate='한화에어로스페이스 | KOSPI' → 검증에서 '한화에어로스페이스'로 교정
        assert sp.name == "한화에어로스페이스", f"예상: 한화에어로스페이스, 실제: {sp.name}"

    def test_ticker_paren_with_text(self, extractor):
        """괄호 안 추가 텍스트: '한화에어로스페이스 주가 정보 (KOSPI 012450)'."""
        sp = extractor.extract_stock_prices("한화에어로스페이스 주가 정보 (KOSPI 012450) 95만원")
        assert sp is not None
        assert sp.ticker == "012450"
        assert sp.name == "한화에어로스페이스", f"예상: 한화에어로스페이스, 실제: {sp.name}"
        assert sp.close_price == 950000

    def test_ticker_code_only_fallback(self, extractor):
        """코드만 있는 텍스트에서 폴백 로직으로 이름+코드 추출.
        '한화에어로스페이스 | KOSPI 012450' — 1차 패턴 실패 시 2차 코드 스캔."""
        sp = extractor.extract_stock_prices("이전 문장. 한화에어로스페이스 | KOSPI 012450. 이후 문장.")
        assert sp is not None
        assert sp.ticker == "012450"
        assert sp.name == "한화에어로스페이스", f"예상: 한화에어로스페이스, 실제: {sp.name}"

    def test_ticker_slash_separator(self, extractor):
        """슬래시(/) 구분자: 삼성전자/005930"""
        sp = extractor.extract_stock_prices("삼성전자/005930 84,500원")
        assert sp is not None
        assert sp.ticker == "005930"
        assert sp.name == "삼성전자"
        assert sp.close_price == 84500

    def test_ticker_hybrid_dash(self, extractor):
        """하이픈(-) 구분자: SK하이닉스-000660"""
        sp = extractor.extract_stock_prices("SK하이닉스-000660 120,000원")
        assert sp is not None
        assert sp.ticker == "000660"
        assert sp.name == "SK하이닉스"
        assert sp.close_price == 120000


# ─── DataExtractor.extract_weather ─────────────────────────────────


class TestExtractWeather:
    def test_korean_format(self, extractor):
        """한국어 날씨 형식."""
        w = extractor.extract_weather("서울 날씨: 기온 28.5°C, 습도 65%, 맑음")
        assert w is not None
        assert w.temperature == 28.5
        assert w.humidity == 65
        assert w.condition == "맑음"

    def test_temperature_only(self, extractor):
        """온도만 있는 경우."""
        w = extractor.extract_weather("현재기온: 22.3°C")
        assert w is not None
        assert w.temperature == 22.3

    def test_negative_temperature(self, extractor):
        """영하 기온."""
        w = extractor.extract_weather("기온: -5.2°C")
        assert w is not None
        assert w.temperature == -5.2

    def test_feels_like(self, extractor):
        """체감온도 추출."""
        w = extractor.extract_weather("기온 28.5°C 체감온도 30.2°C")
        assert w is not None
        assert w.temperature == 28.5
        assert w.feels_like == 30.2

    def test_humidity_only(self, extractor):
        """습도만 있는 경우."""
        w = extractor.extract_weather("습도: 55%")
        assert w is not None
        assert w.humidity == 55

    def test_wttr_in_format(self, extractor):
        """wttr.in 출력 형식."""
        w = extractor.extract_weather("Weather report: Seoul, South Korea\n기온 28.5°C")
        assert w is not None
        assert w.location == "Seoul, South Korea"
        assert w.temperature == 28.5

    def test_no_weather(self, extractor):
        """날씨 데이터 없음."""
        w = extractor.extract_weather("삼성전자 주가 84,500원")
        assert w is None

    def test_empty_string(self, extractor):
        """빈 문자열."""
        w = extractor.extract_weather("")
        assert w is None


# ─── DataExtractor.extract_exchange_rate ────────────────────────────


class TestExtractExchangeRate:
    def test_korean_format(self, extractor):
        """한국어 환율 형식.

        Note: 현재 regex는 `(-0.12%)` 같은 괄호를 처리하지 못하므로
        괄호 없이 `-0.12%` 형식만 지원합니다.
        """
        er = extractor.extract_exchange_rate("원/달러 환율 1,382.50 -0.12%")
        assert er is not None
        assert "원/" in er.currency_pair or "환율" in er.currency_pair
        assert er.rate == 1382.50
        assert er.change_percent is not None
        assert abs(er.change_percent - (-0.12)) < 0.01

    def test_rate_only(self, extractor):
        """환율만 있는 경우."""
        er = extractor.extract_exchange_rate("환율 1,300.50원")
        assert er is not None
        assert er.rate == 1300.50

    def test_no_exchange(self, extractor):
        """환율 데이터 없음."""
        er = extractor.extract_exchange_rate("삼성전자 주가 84,500원")
        assert er is None

    def test_empty_string(self, extractor):
        """빈 문자열."""
        er = extractor.extract_exchange_rate("")
        assert er is None


# ─── DataExtractor.extract_dates ────────────────────────────────────


class TestExtractDates:
    def test_korean_date(self, extractor):
        """한국어 날짜 형식."""
        dates = extractor.extract_dates("2026년 7월 16일 주가")
        assert dates == ["2026년 7월 16일"]

    def test_iso_date(self, extractor):
        """ISO 날짜 형식 (하이픈)."""
        dates = extractor.extract_dates("2026-07-16 주가")
        assert dates == ["2026년 7월 16일"]

    def test_iso_date_slash(self, extractor):
        """ISO 날짜 형식 (슬래시)."""
        dates = extractor.extract_dates("2026/07/16 주가")
        assert dates == ["2026년 7월 16일"]

    def test_multiple_dates(self, extractor):
        """여러 날짜."""
        dates = extractor.extract_dates("2026년 7월 15일부터 2026년 7월 16일까지")
        assert len(dates) == 2
        assert "2026년 7월 15일" in dates
        assert "2026년 7월 16일" in dates

    def test_no_dates(self, extractor):
        """날짜 없음."""
        dates = extractor.extract_dates("삼성전자 주가")
        assert dates == []

    def test_empty_string(self, extractor):
        """빈 문자열."""
        dates = extractor.extract_dates("")
        assert dates == []

    def test_duplicate_dedup(self, extractor):
        """중복 날짜 제거 (extract_all에서 처리)."""
        result = extractor.extract_all(
            ["2026년 7월 16일 주가", "2026년 7월 16일 날씨"],
            query="주가",
        )
        assert len(result.dates_found) == 1
        assert result.dates_found == ["2026년 7월 16일"]


# ─── DataExtractor.extract_numeric_data ─────────────────────────────


class TestExtractNumericData:
    def test_billion_unit(self, extractor):
        """억 단위 숫자."""
        nums = extractor.extract_numeric_data("순이익 500억")
        assert len(nums) >= 1

    def test_trillion_unit(self, extractor):
        """조 단위 숫자."""
        nums = extractor.extract_numeric_data("GDP 2,000조")
        assert len(nums) >= 1

    def test_percentage(self, extractor):
        """퍼센트."""
        nums = extractor.extract_numeric_data("금리 3.5%")
        assert len(nums) >= 1

    def test_interest_rate_label(self, extractor):
        """금리 라벨."""
        nums = extractor.extract_numeric_data("금리: 2.75%")
        assert len(nums) >= 1

    def test_gdp_label(self, extractor):
        """GDP 라벨."""
        nums = extractor.extract_numeric_data("GDP 3.2% 성장")
        assert len(nums) >= 1

    def test_no_numeric(self, extractor):
        """숫자 데이터 없음."""
        nums = extractor.extract_numeric_data("안녕하세요")
        assert nums == []

    def test_empty_string(self, extractor):
        """빈 문자열."""
        nums = extractor.extract_numeric_data("")
        assert nums == []


# ─── DataExtractor.extract_all (통합) ──────────────────────────────


class TestExtractAll:
    def test_comprehensive_extraction(self, extractor):
        """여러 텍스트에서 모든 데이터 통합 추출."""
        snippets = [
            "📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)",
            "서울 날씨: 기온 28.5°C, 습도 65%",
            "원/달러 환율 1,382.50원",
            "2026년 7월 16일 기준",
        ]
        result = extractor.extract_all(snippets, query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        assert result.stock_prices[0].name == "한화에어로스페이스"
        assert len(result.dates_found) >= 1
        assert "2026년 7월 16일" in result.dates_found

    def test_query_filter_stock(self, extractor):
        """주식 쿼리가 아니면 주식 데이터 제거."""
        snippets = ["📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)"]
        result = extractor.extract_all(snippets, query="오늘 날씨")
        assert len(result.stock_prices) == 0

    def test_query_filter_weather(self, extractor):
        """날씨 쿼리가 아니면 날씨 데이터 제거."""
        snippets = ["서울 날씨: 기온 28.5°C, 습도 65%"]
        result = extractor.extract_all(snippets, query="삼성전자 주가")
        assert len(result.weather) == 0

    def test_query_filter_exchange(self, extractor):
        """환율 쿼리가 아니면 환율 데이터 제거."""
        snippets = ["원/달러 환율 1,382.50원"]
        result = extractor.extract_all(snippets, query="삼성전자 주가")
        assert len(result.exchange_rates) == 0

    def test_empty_input(self, extractor):
        """빈 입력 처리."""
        result = extractor.extract_all([], query="")
        assert result.has_data() is False

    def test_short_input(self, extractor):
        """5자 미만 짧은 텍스트는 건너뜀."""
        result = extractor.extract_all(["a", "bc", ""], query="")
        assert result.has_data() is False

    def test_result_format_for_llm_integrated(self, extractor):
        """extract_all + format_for_llm 통합."""
        snippets = [
            "📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)",
            "삼성전자(005930) 84,500원 (-0.82%)",
        ]
        result = extractor.extract_all(snippets, query="한화에어로스페이스 주가")
        text = result.format_for_llm()
        assert "한화에어로스페이스" in text
        assert "삼성전자" in text or "005930" in text


# ─── extract_structured_data shortcut ──────────────────────────────


class TestExtractStructuredData:
    def test_with_stock_data(self):
        """주식 데이터가 포함된 구조화 출력."""
        texts = ["📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)"]
        result = extract_structured_data(texts, query="주가")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "한화에어로스페이스" in result
        assert "943,000원" in result

    def test_no_data(self):
        """데이터 없으면 빈 문자열."""
        result = extract_structured_data(["안녕하세요"], query="인사")
        assert result == ""

    def test_empty_input(self):
        """빈 입력."""
        result = extract_structured_data([], query="")
        assert result == ""

    def test_weather_data(self):
        """날씨 데이터 포함."""
        texts = ["서울 날씨: 기온 28.5°C, 습도 65%, 맑음"]
        result = extract_structured_data(texts, query="서울 날씨")
        assert isinstance(result, str)
        if result:
            assert "28.5°C" in result or "28.5" in result


# ─── TOP 1 JSON 추출 + 만원/억원 통합 ──────────────────────────


class TestTop1JsonExtraction:
    """TOP 1 심층 분석 JSON 블록 추출과 만원/억원 패턴의 통합 테스트."""

    _SEARCH_FORMAT = (
        "[웹 검색 결과] 쿼리: 'test' (SelfHosted, 3개)\n\n"
        "👑 **[TOP 1 심층 분석] 💡 AI Answer**\n"
        "🔗 https://example.com/search?q=test\n"
        "📄 본문 마크다운 요약 (Jina Reader):\n"
        "Title: \n\n"
        "URL Source: https://example.com\n\n"
        "Markdown Content:\n"
        "{}\n\n"
        "2. **Result 2**\n   snippet\n   🔗 https://example.com/2\n"
    )

    def _make_search_result(self, json_body: str) -> str:
        """TOP 1 JSON을 포함한 전체 검색 결과 텍스트 생성."""
        return self._SEARCH_FORMAT.format(json_body)

    def test_top1_with_manwon(self, extractor):
        """TOP 1 JSON + 만원 표기법: answer.text에 '95만원' 포함."""
        json_body = (
            '{"query":"한화에어로스페이스 주가",'
            '"answer":{"text":"한화에어로스페이스 주가는 95만원입니다 [1]"},'
            '"results":[]}'
        )
        search_text = self._make_search_result(json_body)

        # TOP 1 JSON 추출
        top1 = extractor._extract_top1_json(search_text)
        assert top1 is not None
        assert "95만원" in top1["answer"]["text"]

        # _extract_from_top1_json → 만원 패턴으로 가격 추출
        sp = extractor._extract_from_top1_json(top1)
        assert sp is not None
        assert sp.close_price == 950000  # 95만원 → 950,000원

    def test_top1_with_manwon_decimal(self, extractor):
        """TOP 1 JSON + 소수점 만원 + 목표 컨텍스트 → 필터링.

        '목표주가 99.6만원으로'는 '목표' 키워드로 추측성 판단 → close_price=None
        (ticker도 없고 가격도 필터링되면 _extract_from_top1_json이 None 반환)
        """
        json_body = '{"query":"test","answer":{"text":"목표주가 99.6만원으로 상향 [1]"},"results":[]}'
        search_text = self._make_search_result(json_body)
        top1 = extractor._extract_top1_json(search_text)
        assert top1 is not None

        sp = extractor._extract_from_top1_json(top1)
        # '목표주가'는 목표 컨텍스트 → 99.6만원 필터링되어야 함
        if sp is not None:
            assert sp.close_price is None, f"'목표주가 99.6만원'이 필터링되지 않음! close_price={sp.close_price}"

    def test_top1_with_eokwon(self, extractor):
        """TOP 1 JSON + 억원 표기법: answer.text에 '1.5억원' 포함."""
        json_body = '{"query":"시가총액","answer":{"text":"한화에어로스페이스 시가총액 1.5억원 [1]"},"results":[]}'
        search_text = self._make_search_result(json_body)
        top1 = extractor._extract_top1_json(search_text)
        assert top1 is not None

        sp = extractor._extract_from_top1_json(top1)
        assert sp is not None
        assert sp.close_price == 150000000  # 1.5억원 → 150,000,000원

    def test_top1_with_ticker_and_manwon(self, extractor):
        """TOP 1 JSON + ticker + 만원: 종목코드와 만원 가격 모두 추출."""
        json_body = (
            '{"query":"한화에어로스페이스 주가",'
            '"answer":{"text":"한화에어로스페이스 (012450) 95만원 +1.51%"},'
            '"results":[]}'
        )
        search_text = self._make_search_result(json_body)

        top1 = extractor._extract_top1_json(search_text)
        assert top1 is not None

        sp = extractor._extract_from_top1_json(top1)
        assert sp is not None
        assert sp.close_price == 950000  # 95만원
        assert sp.change_percent == 1.51  # +1.51%
        # ticker는 stock_code_validator의 _stock_names 매핑에 따라 설정됨
        # 실제 환경에서는 012450이 한화에어로스페이스로 매핑됨
        if sp.ticker:
            assert sp.ticker == "012450"

    def test_top1_with_results_content(self, extractor):
        """TOP 1 JSON + results content에서도 추출."""
        json_body = (
            '{"query":"test",'
            '"answer":{"text":"주식 시장 동향입니다."},'
            '"results":[{"title":"한화에어로스페이스",'
            '"content":"한화에어로스페이스 현재 100만원 거래 중",'
            '"score":0.9,"domain":"naver.com"}]}'
        )
        search_text = self._make_search_result(json_body)

        sp = extractor._extract_from_top1_json(extractor._extract_top1_json(search_text))
        assert sp is not None
        assert sp.close_price == 1000000  # 100만원 → 1,000,000원

    def test_top1_in_extract_all(self, extractor):
        """extract_all에서 TOP 1 JSON + 만원 통합 추출.

        '100만원을 향해' → 필터링
        '장중 최고 95만원까지' → '장중' 키워드로 유효 → 95,000원
        '목표주가 99.6만원' → 필터링
        """
        json_body = (
            '{"query":"한화에어로스페이스 주가 알려줘",'
            '"answer":{"text":"한화에어로스페이스 주가는 100만원'
            "을 향해 상승 중이며 장중 최고 95만원까지 치솟았습니다. "
            '목표주가 99.6만원 [1]"},'
            '"results":[]}'
        )
        search_text = self._make_search_result(json_body)

        result = extractor.extract_all([search_text], query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        sp = result.stock_prices[0]
        # '장중 최고 95만원까지'가 유효 가격으로 추출됨
        assert sp.close_price is not None
        assert sp.close_price == 950000, f"'장중 최고 95만원'이 추출되어야 함. 실제: {sp.close_price}"

    def test_top1_json_no_stock_data(self, extractor):
        """TOP 1 JSON에 주식 데이터 없음 → None."""
        json_body = '{"query":"오늘 날씨","answer":{"text":"서울은 맑고 기온은 22도입니다."},"results":[]}'
        search_text = self._make_search_result(json_body)
        top1 = extractor._extract_top1_json(search_text)
        assert top1 is not None
        assert "서울" in top1["answer"]["text"]

        # 주식 데이터는 없어야 함
        sp = extractor._extract_from_top1_json(top1)
        assert sp is None

    def test_top1_with_dates(self, extractor):
        """TOP 1 JSON + 만원 + 날짜 동시 추출."""
        json_body = (
            '{"query":"test","answer":{"text":"2025년 6월 10일 장중 최고 95만원 까지치솟았습니다 [1]"},"results":[]}'
        )
        search_text = self._make_search_result(json_body)

        result = extractor.extract_all([search_text], query="주가")
        # 주식 데이터 확인
        assert len(result.stock_prices) >= 1
        assert result.stock_prices[0].close_price == 950000  # 95만원
        # 날짜 확인
        assert len(result.dates_found) >= 1
        assert "2025년 6월 10일" in result.dates_found


# ─── Edge Cases & Error Handling ────────────────────────────────────


class TestEdgeCases:
    def test_large_numbers(self, extractor):
        """큰 숫자 처리 (1,000,000)."""
        sp = extractor.extract_stock_prices("1,000,000원")
        assert sp is not None
        assert sp.close_price == 1000000

    def test_special_characters_in_text(self, extractor):
        """특수문자가 있는 텍스트에서 추출."""
        sp = extractor.extract_stock_prices("📈 삼성전자 (005930) 84,500원 (-0.82%) 📉")
        assert sp is not None
        assert sp.close_price == 84500

    def test_multiple_prices_in_text(self, extractor):
        """여러 가격이 있는 텍스트 (첫 번째 사용)."""
        sp = extractor.extract_stock_prices("시가 930,000원 종가 943,000원")
        # _STOCK_OPEN_LABEL이 먼저 매칭 → 시가
        assert sp is not None
        assert sp.open_price == 930000
        assert sp.close_price == 943000

    def test_stock_snippet_without_ticker(self, extractor):
        """종목코드 없는 Self-Hosted 형식."""
        text = "📊 (012450) 943,000원 +1.51% (상승)"  # 종목명 없음
        sp = extractor.extract_stock_prices(text)
        assert sp is not None
        assert sp.ticker == "012450"
        assert sp.close_price == 943000
        assert sp.change_percent == 1.51
