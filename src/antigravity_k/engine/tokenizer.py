"""Antigravity-K: 토큰 추정기 (TokenEstimator).

=============================================
시스템 전체에서 단 하나의 토큰 추정 공식만 사용하도록 통일합니다.

이전 문제:
  - orchestrator.py: len(text) // 4
  - context_shaper.py: len(bytes) // 3
  → 두 추정치가 서로 다른 결과를 내어 토큰 예산 계산이 불일치.

설계 원칙 (Claude Code 패턴):
  - 한국어/영어 혼합 텍스트에 대해 보수적 추정
  - 메시지 리스트 단위 추정 지원
  - 성능을 위한 캐싱 (메시지별 _tokens 필드)
"""

import re
from typing import Any

# 한글, 한자, 일본어(히라가나/가타카나) 정규식
CJK_PATTERN = re.compile(r"[\uac00-\ud7a3\u4e00-\u9fff\u3040-\u30ff]")


class TokenEstimator:
    """토큰 수 추정 — 시스템 전체에서 이 클래스만 사용할 것.

    추정 공식: UTF-8 바이트 수 / 3

    근거:
      - 영어: ~4글자 = 1토큰 → 1바이트/글자 → 4바이트/토큰 → /3은 보수적
      - 한국어: ~1.5토큰/글자 → 3바이트/글자(UTF-8) → 2바이트/토큰 → /3은 보수적
      - 보수적 추정이 안전함 (과소 추정 → 토큰 초과 → API 에러)
    """

    BYTES_PER_TOKEN = 3  # 보수적 추정 상수

    @staticmethod
    def estimate_text(text: str) -> int:
        """단일 텍스트의 토큰 수를 추정합니다."""
        if not text:
            return 0
        base_tokens = len(text.encode("utf-8")) // TokenEstimator.BYTES_PER_TOKEN
        # 한글/CJK 문자는 모델에 따라 토큰을 더 많이 소비하므로 보정치 추가 (+1 token/char)
        cjk_count = len(CJK_PATTERN.findall(text))
        return base_tokens + cjk_count

    @staticmethod
    def estimate_messages(messages: list[dict[str, str]], use_cache: bool = True) -> int:
        """메시지 리스트의 총 토큰 수를 추정합니다.

        Args:
            messages: [{"role": "...", "content": "..."}] 리스트
            use_cache: True이면 메시지별 _tokens 필드에 캐시 (반복 호출 시 성능 향상)

        """
        total = 0
        for msg in messages:
            if use_cache and "_tokens" in msg:
                _t = msg["_tokens"]
                if isinstance(_t, (int, float)):
                    total += int(_t)
            else:
                content = msg.get("content", "")
                tokens = TokenEstimator.estimate_text(content)
                if use_cache:
                    typed_msg: dict[str, Any] = msg  # widen for _tokens
                    typed_msg["_tokens"] = tokens
                total += tokens
        return total

    @staticmethod
    def estimate_messages_by_role(messages: list[dict[str, str]]) -> dict[str, int]:
        """역할별 토큰 사용량을 분석합니다."""
        by_role: dict[str, int] = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            tokens = TokenEstimator.estimate_text(msg.get("content", ""))
            by_role[role] = by_role.get(role, 0) + tokens
        return by_role
