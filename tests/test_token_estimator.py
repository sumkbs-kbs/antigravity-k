"""테스트: TokenEstimator 추정 공식.
==============================
바이트 기반 보수적 추정과 짧은 텍스트의 최소 1토큰 하한을 검증한다.
"""

import pytest

from antigravity_k.engine.tokenizer import TokenEstimator


class TestEstimateText:
    def test_empty_text_costs_zero(self):
        assert TokenEstimator.estimate_text("") == 0

    def test_short_ascii_answer_costs_at_least_one_token(self):
        # "10"은 2바이트라 2//3=0이었고, 실제로는 1토큰 이상 소비된다 (Out: 0 버그)
        assert TokenEstimator.estimate_text("10") == 1
        assert TokenEstimator.estimate_text("2") == 1

    def test_long_english_estimate_is_conservative(self):
        text = "a" * 300

        assert TokenEstimator.estimate_text(text) == 100

    def test_korean_gets_cjk_adjustment(self):
        text = "가" * 9  # 27바이트 → base 9 + CJK 9

        assert TokenEstimator.estimate_text(text) == 18

    @pytest.mark.parametrize("payload", ["hello world", "안녕하세요", "x"])
    def test_non_empty_text_never_estimates_zero(self, payload):
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
