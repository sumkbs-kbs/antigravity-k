"""테스트: OmniTDDEngine — 적응형 레이싱 스킵·코드 추출.
====================================
단순 요청 레이싱 스킵 판정과 Python 코드 블록 추출 계약을 검증한다.
"""

from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.tdd_engine import OmniTDDEngine


@pytest.fixture
def engine():
    return OmniTDDEngine(model_manager=MagicMock(), coding_model="test-model")


class TestShouldSkipRacing:
    def test_short_simple_prompt_skips_racing(self, engine):
        assert engine._should_skip_racing("간단한 함수를 작성해줘") is True

    def test_long_prompt_does_not_skip(self, engine):
        # 30토큰 이상 → 단순 지시어가 있어도 레이싱 실행
        prompt = " ".join(["토큰"] * 35) + " 코드 작성"
        assert engine._should_skip_racing(prompt) is False

    def test_short_but_complex_keyword_does_not_skip(self, engine):
        # 30토큰 미만이지만 "최적화" 등 복잡 지시어 없음 + 단순 지시어 있음 → skip
        assert engine._should_skip_racing("코드 작성") is True

    def test_no_simple_indicator_does_not_skip(self, engine):
        # 단순 지시어 없음 → 30토큰 미만이라도 레이싱 스킵 안함
        prompt = " ".join(["아키텍처"] * 40) + " 최적화 병목 프로파일링 보고서"
        assert engine._should_skip_racing(prompt) is False

    def test_english_simple_prompt_skips(self, engine):
        assert engine._should_skip_racing("write a hello world function") is True


class TestExtractPythonCode:
    def test_code_block_extraction(self, engine):
        text = "설명입니다\n```python\nprint('hello')\n```\n끝"
        assert engine._extract_python_code(text) == "print('hello')"

    def test_no_code_block_returns_original(self, engine):
        text = "그냥 코드만 있는 경우"
        assert engine._extract_python_code(text) == text
