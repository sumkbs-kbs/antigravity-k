"""[DEPRECATED] IntentRouter — 키워드 기반 의도 라우팅 (레거시).

==========================================================
이 모듈은 현재 시스템에서 사용되지 않습니다 (데드 코드).
동일한 기능이 orchestrator.py의 _ceo_analyze() CEO 분석 파이프라인에서
LLM 기반 + 키워드 폴백 방식으로 대체되었습니다.

향후 통합 또는 제거 예정 (W-1).
"""

import logging
import re
import warnings
from typing import Any

logger = logging.getLogger("antigravity_k.engine.intent_router")

warnings.warn(
    "IntentRouter is deprecated. Use OrchestratorAgent._ceo_analyze() instead.",
    DeprecationWarning,
    stacklevel=2,
)


class IntentRouter:
    """[DEPRECATED] IntentGate: Analyzes the user's task description and routes it to the optimal agent profile.

    Inspired by oh-my-openagent's discipline agents (Sisyphus, Hephaestus, Prometheus).
    """

    def __init__(self):
        """Initialize the IntentRouter."""
        self.categories = {
            "visual-engineering": ["frontend", "ui", "ux", "design", "css", "html", "react"],
            "deep": ["refactor", "architect", "research", "analyze", "deep", "complex", "backend"],
            "quick": ["typo", "quick", "fix", "minor", "lint", "format"],
            "ultrabrain": ["plan", "strategy", "interview", "design document", "architecture"],
        }

    def classify_intent(self, user_prompt: str) -> str:
        """Classify the intent based on keyword heuristics.

        In a production system, this could be an LLM-based classification call.
        """
        lower_prompt = user_prompt.lower()
        scores = {k: 0 for k in self.categories.keys()}

        for category, keywords in self.categories.items():
            for kw in keywords:
                # Use regex for word boundary matching
                if re.search(r"\b" + re.escape(kw) + r"\b", lower_prompt):
                    scores[category] += 1

        # Find the category with the highest score
        best_category = max(scores, key=scores.get)

        # Default to 'deep' if no clear category is found
        if scores[best_category] == 0:
            return "deep"

        return best_category

    def get_agent_profile(self, category: str) -> dict[str, Any]:
        """Return the agent profile (model, persona) for the given category."""
        profiles = {
            "visual-engineering": {
                "name": "Frontend Agent",
                "model": "claude-3-opus-20240229",  # Fallback to appropriate vision/frontend models
                "persona": "You are an expert Frontend and UI/UX engineer.",
            },
            "deep": {
                "name": "Hephaestus (Deep Worker)",
                "model": "gpt-4-turbo",  # Equivalent to gpt-5.4 conceptual model
                "persona": "You are Hephaestus, a deep worker who autonomously researches and implements complex architectural"  # type: ignore  # noqa: E501
                "changes end-to-end without needing supervision.",
            },
            "quick": {
                "name": "Quick Fixer",
                "model": "gpt-3.5-turbo",  # Fast, cheap model
                "persona": "You are a fast and precise engineer focused on fixing typos and minor bugs immediately.",
            },
            "ultrabrain": {
                "name": "Prometheus (Strategic Planner)",
                "model": "claude-3-opus-20240229",
                "persona": "You are Prometheus, a strategic planner. Do not write code immediately. Ask clarifying questions"  # type: ignore  # noqa: E501
                "and output a robust implementation plan first.",
            },
        }
        return profiles.get(category, profiles["deep"])


# Singleton
intent_router = IntentRouter()


def get_intent_router() -> IntentRouter:
    """Retrieve intent router.

    Returns:
        IntentRouter: The intentrouter result.

    """
    return intent_router
