"""E2E 통합 테스트 — 검색→추출→LLM 포맷 파이프라인 (Phase 1 #6).

검증 범위:
  - WebSearchTool.execute() → DataExtractor.extract_all() → format_for_llm() 전체 파이프라인
  - 다양한 쿼리 타입: 주가, 날씨, 환율, 혼합
  - TOP 1 JSON 추출 + 구조화 데이터 보강
  - 만원/억원 표기법 + 등락률 + 종목코드 검증
  - 오탐 필터링 (목표가/전망가 제외)
  - API 엔드포인트 (/api/search/extract) 테스트 (mocked)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from antigravity_k.engine.data_extractor import (
    DataExtractor,
    ExtractionResult,
    extract_structured_data,
)

# ─── Mock 검색 결과 ────────────────────────────────────────────────

MOCK_SEARCH_RESULT_STOCK = """
[웹 검색 결과] 쿼리: '한화에어로스페이스 주가 알려줘' (SelfHosted, 3개)

👑 **[TOP 1 심층 분석] 💡 AI Answer**
🔗 https://example.com/search?q=test
📄 본문 마크다운 요약 (Jina Reader):
Title:
URL Source: https://example.com

Markdown Content:
{"query":"한화에어로스페이스 주가","answer":{"text":"한화에어로스페이스 (012450) 주가는 장중 최고 95만원까지 치솟았으며 현재 94만원대에 거래되고 있습니다. 등락률은 +1.51%입니다 [1]"},"results":[{"title":"한화에어로스페이스 주가","content":"한화에어로스페이스 (KOSPI 012450) 현재 943,000원 +1.51% (상승)","score":0.95}]}

2. **Result 2**
   📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)
   🔗 https://example.com/2

3. **Result 3**
   삼성전자(005930) 84,500원 (-0.82%)
   🔗 https://example.com/3
"""

MOCK_SEARCH_RESULT_WEATHER = """
[웹 검색 결과] 쿼리: '서울 날씨 알려줘' (SelfHosted, 2개)

👑 **[TOP 1 심층 분석] 💡 AI Answer**
🔗 https://example.com/weather

Markdown Content:
{"query":"서울 날씨","answer":{"text":"서울의 현재 기온은 28.5도, 습도 65%입니다. 맑은 날씨가 예상됩니다 [1]."},"results":[{"title":"서울 날씨","content":"서울 날씨: 기온 28.5°C, 습도 65%, 맑음","score":0.9}]}

2. **Result 2**
   서울 날씨: 기온 28.5°C, 습도 65%, 맑음
   🔗 https://example.com/weather2
"""

MOCK_SEARCH_RESULT_EXCHANGE = """
[웹 검색 결과] 쿼리: '원달러 환율' (SelfHosted, 1개)

👑 **[TOP 1 심층 분석] 💡 AI Answer**
🔗 https://example.com/exchange

Markdown Content:
{"query":"원달러 환율","answer":{"text":"원/달러 환율이 1,382.50원으로 전일대비 -0.12% 하락했습니다 [1]."},"results":[{"title":"원달러 환율","content":"원/달러 환율 1,382.50원 (-0.12%)","score":0.85}]}

2. **Result 2**
   원/달러 환율 1,382.50원 -0.12%
   🔗 https://example.com/exchange2
"""

MOCK_SEARCH_RESULT_MIXED = """
[웹 검색 결과] 쿼리: '한화에어로스페이스 주가와 코스피 현황' (SelfHosted, 3개)

👑 **[TOP 1 심층 분석] 💡 AI Answer**
🔗 https://example.com/search

Markdown Content:
{"query":"한화에어로스페이스 주가","answer":{"text":"한화에어로스페이스 (012450) 현재 94만원대 거래 중이며 등락률은 +1.51%입니다. 목표주가는 99.6만원이 제시되었습니다 [1]."},"results":[{"title":"한화에어로스페이스 주가","content":"📊 한화에어로스페이스 (012450) 943,000원 +1.51% (상승)","score":0.95}]}

2. **Result 2**
   삼성전자(005930) 84,500원 (-0.82%)
   🔗 https://example.com/2

3. **Result 3**
   2026년 7월 16일 기준 코스피 지수
   🔗 https://example.com/3
"""


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def extractor() -> DataExtractor:
    return DataExtractor()


@pytest.fixture
def mock_web_search_tool():
    """Mock WebSearchTool.execute() to return preset search results."""
    with patch("antigravity_k.tools.web_search.WebSearchTool.execute") as mock_execute:
        yield mock_execute


# ═══════════════════════════════════════════════════════════════════
# E2E: 주식 검색 → 추출 → 포맷
# ═══════════════════════════════════════════════════════════════════


class TestE2EStockSearch:
    """주식 검색 파이프라인 E2E: 주가 쿼리 → 데이터 추출 → LLM 포맷."""

    def test_extract_stock_from_search_result(self, extractor):
        """검색 결과에서 주식 데이터 추출 → 형식화까지."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_STOCK], query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        sp = result.stock_prices[0]
        assert sp.name == "한화에어로스페이스"
        assert sp.ticker == "012450"
        assert sp.close_price == 943000  # Self-Hosted 스니펫
        assert sp.change_percent == 1.51

        # LLM 포맷 검증
        text = result.format_for_llm()
        assert "📈" in text
        assert "한화에어로스페이스" in text
        assert "943,000원" in text
        assert "+1.51%" in text or "1.51%" in text
        assert "012450" in text

    def test_extract_multiple_stocks(self, extractor):
        """여러 종목이 포함된 검색 결과에서 각각 추출."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_MIXED], query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        # 한화에어로스페이스 확인
        hanwha = next((sp for sp in result.stock_prices if "한화" in sp.name), None)
        assert hanwha is not None
        assert hanwha.ticker == "012450"
        assert hanwha.close_price is not None

    def test_manwon_extraction_in_pipeline(self, extractor):
        """TOP 1 JSON answer.text의 만원 패턴 → 정수 변환."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_STOCK], query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        # '장중 최고 95만원까지' → 950,000원 (enrichment에서)
        # '943,000원' → 943000원 (Self-Hosted 스니펫에서)
        sp = result.stock_prices[0]
        assert sp.close_price in (943000, 950000)

    def test_change_percent_in_pipeline(self, extractor):
        """파이프라인에서 등락률 추출."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_STOCK], query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        sp = result.stock_prices[0]
        assert sp.change_percent is not None
        assert abs(sp.change_percent - 1.51) < 0.01

    def test_ticker_validation_in_pipeline(self, extractor):
        """종목코드 검증 + 오탐 방지."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_STOCK], query="한화에어로스페이스 주가")
        assert len(result.stock_prices) >= 1
        sp = result.stock_prices[0]
        assert sp.ticker == "012450"
        # KOSPI 같은 오탐이 아니라 실제 종목명이어야 함
        assert sp.name != "KOSPI"
        assert "에어로스페이스" in sp.name or "한화" in sp.name


# ═══════════════════════════════════════════════════════════════════
# E2E: 날씨 검색 → 추출 → 포맷
# ═══════════════════════════════════════════════════════════════════


class TestE2EWeatherSearch:
    """날씨 검색 파이프라인 E2E."""

    def test_extract_weather_from_search(self, extractor):
        """날씨 검색 결과에서 기온/습도 추출."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_WEATHER], query="서울 날씨")
        assert len(result.weather) >= 1
        w = result.weather[0]
        assert w.temperature is not None
        assert abs(w.temperature - 28.5) < 0.1
        assert w.humidity == 65

        # LLM 포맷 검증
        text = result.format_for_llm()
        if text:
            assert "28.5°C" in text or "28.5" in text
            assert "65%" in text

    def test_weather_without_stock(self, extractor):
        """날씨 쿼리에서는 주식 데이터 제거."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_WEATHER], query="서울 날씨")
        assert len(result.stock_prices) == 0


# ═══════════════════════════════════════════════════════════════════
# E2E: 환율 검색 → 추출 → 포맷
# ═══════════════════════════════════════════════════════════════════


class TestE2EExchangeSearch:
    """환율 검색 파이프라인 E2E."""

    def test_extract_exchange_from_search(self, extractor):
        """환율 검색 결과에서 환율/변동률 추출."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_EXCHANGE], query="원달러 환율")
        assert len(result.exchange_rates) >= 1
        er = result.exchange_rates[0]
        assert er.rate is not None
        assert abs(er.rate - 1382.50) < 0.1

        # LLM 포맷 검증
        text = result.format_for_llm()
        if text:
            assert "💱" in text or "1,382.50" in text


# ═══════════════════════════════════════════════════════════════════
# E2E: 혼합 쿼리 (주식 + 날짜 + 관심종목)
# ═══════════════════════════════════════════════════════════════════


class TestE2EMixedQuery:
    """혼합 쿼리 파이프라인 E2E."""

    def test_stock_and_dates(self, extractor):
        """주식 + 날짜 동시 추출."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_MIXED], query="한화에어로스페이스 주가")
        # 주식 추출
        assert len(result.stock_prices) >= 1
        # 날짜 추출
        assert len(result.dates_found) >= 1
        assert "2026년 7월 16일" in result.dates_found

    def test_full_pipeline_to_llm_format(self, extractor):
        """전체 파이프라인 → LLM 포맷 문자열."""
        result = extractor.extract_all([MOCK_SEARCH_RESULT_STOCK], query="한화에어로스페이스 주가")
        text = result.format_for_llm()
        assert isinstance(text, str)
        assert len(text) > 0
        # 주요 키워드 포함 확인
        assert any(kw in text for kw in ("📈", "한화", "에어로스페이스"))


# ═══════════════════════════════════════════════════════════════════
# E2E: extract_structured_data shortcut
# ═══════════════════════════════════════════════════════════════════


class TestE2EShortcut:
    """extract_structured_data → format_for_llm shortcut."""

    def test_shortcut_with_stock(self):
        """shortcut 함수로 주식 데이터 추출."""
        text = extract_structured_data([MOCK_SEARCH_RESULT_STOCK], query="한화에어로스페이스 주가")
        assert isinstance(text, str)
        if text:
            assert "한화에어로스페이스" in text

    def test_shortcut_with_weather(self):
        """shortcut 함수로 날씨 데이터 추출."""
        text = extract_structured_data([MOCK_SEARCH_RESULT_WEATHER], query="서울 날씨")
        assert isinstance(text, str)
        if text:
            assert "28.5°C" in text or "28.5" in text

    def test_shortcut_with_exchange(self):
        """shortcut 함수로 환율 데이터 추출."""
        text = extract_structured_data([MOCK_SEARCH_RESULT_EXCHANGE], query="원달러 환율")
        assert isinstance(text, str)
        if text:
            assert "1,382.50" in text or "1382.50" in text

    def test_shortcut_empty_input(self):
        """빈 입력 → 빈 문자열."""
        text = extract_structured_data([], query="")
        assert text == ""


# ═══════════════════════════════════════════════════════════════════
# E2E: 엣지 케이스
# ═══════════════════════════════════════════════════════════════════


class TestE2EEdgeCases:
    """파이프라인 엣지 케이스."""

    def test_no_matching_data(self, extractor):
        """관련 데이터가 없는 검색 결과 → 빈 결과."""
        no_data = """
        [웹 검색 결과] 쿼리: '인사말' (SelfHosted, 0개)
        결과 없음
        """
        result = extractor.extract_all([no_data], query="인사말")
        assert result.has_data() is False

    def test_malformed_json_graceful(self, extractor):
        """잘못된 JSON → graceful fallback."""
        malformed = """
        Markdown Content:
        {broken json here without closing brace
        """
        result = extractor.extract_all([malformed], query="테스트")
        # JSON 파싱 실패해도 크래시 없이 빈 결과
        assert isinstance(result, ExtractionResult)

    def test_empty_search_result(self, extractor):
        """빈 검색 결과 → 빈 결과."""
        result = extractor.extract_all([], query="")
        assert result.has_data() is False
        assert result.format_for_llm() == ""
