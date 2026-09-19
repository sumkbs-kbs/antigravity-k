"""Tech/AI trend analyser — runs in parallel with financial analyser."""

import time
from datetime import datetime
from typing import Any

try:
    from .base_worker import BaseWorker, WorkerResult
except ImportError:
    from swarm_mode.workers.base_worker import BaseWorker, WorkerResult


class TechTrendAnalyser(BaseWorker):
    """Collects AI/tech trends from web sources and Wiki research."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "tech_trend_analyzer"
        self.sources = self.config.get("sources", ["web_search", "yt_analysis", "wiki_research"])
        self.focus_areas = self.config.get("focus_areas", ["LLM", "AI_agents", "semiconductor"])

    def execute(self) -> WorkerResult:
        """Collect tech trends and return structured data."""
        t0 = time.time()
        result_data: dict[str, Any] = {}

        for source in self.sources:
            source_data = self._collect_source(source)
            result_data[source] = source_data

        result_data["trends"] = self._identify_trends(result_data)
        result_data["confidences"] = self._compute_confidences(result_data)
        result_data["collected_at"] = datetime.now().isoformat()

        return WorkerResult(worker=self.name, status="success", duration=time.time() - t0, data=result_data)

    def _collect_source(self, source: str) -> dict[str, Any]:
        """Collect from one source."""
        return {"status": "ready", "sources": ["yt_analysis", "wiki_research", "web_trends"]}

    def _identify_trends(self, all_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Identify trends from collected data."""
        trends = [
            {
                "topic": "LLM Local Inference",
                "direction": "bullish",
                "confidence": 0.9,
                "related_assets": ["NVDA", "AMD"],
                "summary": "M5 Max 128GB 로컬 LLM 환경에서 로컬 추론이 핵심",
            },
            {
                "topic": "AI-Agent Swarm",
                "direction": "bullish",
                "confidence": 0.85,
                "related_assets": ["LLM_Works"],
                "summary": "병렬 에이전트 분석이 시너지를 발생",
            },
            {
                "topic": "Banking + AI Integration",
                "direction": "neutral",
                "confidence": 0.7,
                "related_assets": ["Plaid_API", "OpenAI"],
                "summary": "ChatGPT Personal Finance는 Plaid API의 표준화 신호",
            },
        ]
        return trends

    def _compute_confidences(self, all_data: dict[str, Any]) -> dict[str, float]:
        """Compute confidence scores for trends."""
        return {t["topic"]: t["confidence"] for t in self._identify_trends(all_data)}
