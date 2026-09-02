"""테스트: TokenEstimator 추정 공식.
==============================
단일 캘리브레이션 공식(CJK ~1.2토큰/글자, 기타 ~0.25토큰/글자)과
짧은 텍스트의 최소 1토큰 하한을 검증한다.
"""

import pytest

from antigravity_k.engine.tokenizer import TokenEstimator


class TestEstimateText:
    def test_empty_text_costs_zero(self):
        assert TokenEstimator.estimate_text("") == 0

    def test_short_ascii_answer_costs_at_least_one_token(self):
        # "10"은 실제로는 1토큰 이상 소비된다 (Out: 0 버그 방지 하한)
        assert TokenEstimator.estimate_text("10") == 1
        assert TokenEstimator.estimate_text("2") == 1

    def test_long_english_estimate_is_conservative(self):
        text = "a" * 300
        # 라틴 0.25토큰/글자 (≈4글자/토큰)
        assert TokenEstimator.estimate_text(text) == 75

    def test_korean_gets_cjk_adjustment(self):
        text = "가" * 9
        # CJK 1.2토큰/글자 — 한국어를 len//4처럼 과소평가하지 않는다
        assert TokenEstimator.estimate_text(text) == 11

    def test_korean_not_overestimated_like_legacy_formula(self):
        # 구버전(bytes//3 + CJK)은 한국어를 ~2토큰/글자로 과대평가했다 —
        # 새 공식은 실측 근사(~1.2)를 따른다
        text = "한국어 텍스트 샘플입니다"
        legacy = len(text.encode("utf-8")) // 3 + 9  # 구 공식 재현
        assert TokenEstimator.estimate_text(text) < legacy

    @pytest.mark.parametrize("payload", ["hello world", "안녕하세요", "x"])
    def test_non_empty_text_never_estimates_zero(self, payload: str):
        assert TokenEstimator.estimate_text(payload) >= 1


class TestEstimateMessages:
    def test_sums_message_contents(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        total = TokenEstimator.estimate_messages(messages)

        expected = sum(TokenEstimator.estimate_text(m["content"]) for m in messages)
        assert total == expected

    def test_empty_list_is_zero(self):
        assert TokenEstimator.estimate_messages([]) == 0
