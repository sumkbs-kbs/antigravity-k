"""FactAppender Engine (Memory/Context Extension).

==============================================

작업 중 새롭게 알게 된 사실(Fact)을 추출하고 메인 에이전트의 컨텍스트에
영구적으로 또는 세션 동안 추가하는 역할을 수행합니다.
"""

import logging

logger = logging.getLogger(__name__)


class FactAppender:
    """LLM 응답 및 도구 실행 결과에서 유의미한 사실을 추출/추가합니다."""

    def __init__(self, vault_engine=None):
        """Initialize the FactAppender.

        Args:
            vault_engine: vault engine.

        """
        self.vault_engine = vault_engine
        self.session_facts = []

    def append_fact(self, fact_text: str):
        """세션 컨텍스트에 새로운 사실을 추가합니다."""
        if fact_text and fact_text not in self.session_facts:
            self.session_facts.append(fact_text)
            logger.info("Fact appended: %s...", fact_text[:50])

    def get_context_str(self) -> str:
        """현재 세션까지 수집된 모든 사실을 프롬프트용 문자열로 반환합니다."""
        if not self.session_facts:
            return ""

        facts = "\n".join(f"- {fact}" for fact in self.session_facts)
        return f"\n[Learned Facts in Current Session]\n{facts}\n"
