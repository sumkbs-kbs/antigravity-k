import logging
import re
from typing import Dict, Any

logger = logging.getLogger("antigravity_k.engine.intent_router")

class IntentRouter:
    """
    IntentGate: Analyzes the user's task description and routes it to the optimal agent profile.
    Inspired by oh-my-openagent's discipline agents (Sisyphus, Hephaestus, Prometheus).
    """
    
    def __init__(self):
        self.categories = {
            "visual-engineering": ["frontend", "ui", "ux", "design", "css", "html", "react"],
            "deep": ["refactor", "architect", "research", "analyze", "deep", "complex", "backend"],
            "quick": ["typo", "quick", "fix", "minor", "lint", "format"],
            "ultrabrain": ["plan", "strategy", "interview", "design document", "architecture"]
        }

    def classify_intent(self, user_prompt: str) -> str:
        """
        Classify the intent based on keyword heuristics.
        In a production system, this could be an LLM-based classification call.
        """
        lower_prompt = user_prompt.lower()
        scores = {k: 0 for k in self.categories.keys()}
        
        for category, keywords in self.categories.items():
            for kw in keywords:
                # Use regex for word boundary matching
                if re.search(r'\b' + re.escape(kw) + r'\b', lower_prompt):
                    scores[category] += 1
                    
        # Find the category with the highest score
        best_category = max(scores, key=scores.get)
        
        # Default to 'deep' if no clear category is found
        if scores[best_category] == 0:
            return "deep"
            
        return best_category

    def get_agent_profile(self, category: str) -> Dict[str, Any]:
        """
        Returns the agent profile (model, persona) for the given category.
        """
        profiles = {
            "visual-engineering": {
                "name": "Frontend Agent",
                "model": "claude-3-opus-20240229", # Fallback to appropriate vision/frontend models
                "persona": "You are an expert Frontend and UI/UX engineer."
            },
            "deep": {
                "name": "Hephaestus (Deep Worker)",
                "model": "gpt-4-turbo", # Equivalent to gpt-5.4 conceptual model
                "persona": "You are Hephaestus, a deep worker who autonomously researches and implements complex architectural changes end-to-end without needing supervision."
            },
            "quick": {
                "name": "Quick Fixer",
                "model": "gpt-3.5-turbo", # Fast, cheap model
                "persona": "You are a fast and precise engineer focused on fixing typos and minor bugs immediately."
            },
            "ultrabrain": {
                "name": "Prometheus (Strategic Planner)",
                "model": "claude-3-opus-20240229",
                "persona": "You are Prometheus, a strategic planner. Do not write code immediately. Ask clarifying questions and output a robust implementation plan first."
            }
        }
        return profiles.get(category, profiles["deep"])

# Singleton
intent_router = IntentRouter()

def get_intent_router() -> IntentRouter:
    return intent_router
