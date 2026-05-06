"""
Antigravity-K: 토큰 추정기 (TokenEstimator)
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

from typing import Dict, List


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
        return len(text.encode("utf-8")) // TokenEstimator.BYTES_PER_TOKEN

    @staticmethod
    def estimate_messages(
        messages: List[Dict[str, str]], use_cache: bool = True
    ) -> int:
        """메시지 리스트의 총 토큰 수를 추정합니다.

        Args:
            messages: [{"role": "...", "content": "..."}] 리스트
            use_cache: True이면 메시지별 _tokens 필드에 캐시 (반복 호출 시 성능 향상)
        """
        total = 0
        for msg in messages:
            if use_cache and "_tokens" in msg:
                total += msg["_tokens"]
            else:
                content = msg.get("content", "")
                tokens = len(content.encode("utf-8")) // TokenEstimator.BYTES_PER_TOKEN
                if use_cache:
                    msg["_tokens"] = tokens
                total += tokens
        return total

    @staticmethod
    def estimate_messages_by_role(messages: List[Dict[str, str]]) -> Dict[str, int]:
        """역할별 토큰 사용량을 분석합니다."""
        by_role: Dict[str, int] = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            tokens = (
                len(msg.get("content", "").encode("utf-8"))
                // TokenEstimator.BYTES_PER_TOKEN
            )
            by_role[role] = by_role.get(role, 0) + tokens
        return by_role
