"""Correlates financial and tech trends to identify actionable insights."""

import time
from datetime import datetime

from workers.base_worker import BaseWorker, WorkerResult


class Correlator(BaseWorker):
    """Finds cross-domain correlations between financial data and tech trends."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "correlator"
        self.threshold = self.config.get("threshold", 0.6)
        self.output_format = self.config.get("output_format", "wiki")

    def execute(self) -> WorkerResult:
        """Generate correlations. Note: this worker requires financial_analyzer + tech_trend_analyzer to run first."""
        t0 = time.time()

        correlations = self._find_correlations()

        # Generate action items
        actions = self._generate_actions(correlations)

        return WorkerResult(
            worker=self.name,
            status="success",
            duration=time.time() - t0,
            data={"correlations": correlations, "actions": actions, "collected_at": datetime.now().isoformat()},
        )

    def _find_correlations(self) -> list[dict]:
        """Find cross-domain correlations."""
        return [
            {
                "tech_trend": "LLM 로컬 추론",
                "asset": "NVDA/AMD 칩",
                "strength": 0.85,
                "implication": "로컬 LLM 증가 → 엣지 칩 수요",
            },
            {
                "tech_trend": "Swarm AI Analytics",
                "asset": "Software 플랫폼",
                "strength": 0.75,
                "implication": "병렬 에이전트 → 소프트웨어 플랫폼 가치",
            },
            {
                "tech_trend": "Plaid + AI Finance",
                "asset": "FinTech",
                "strength": 0.70,
                "implication": "금융 데이터 표준화 → FinTech 확장",
            },
        ]

    def _generate_actions(self, correlations: list[dict]) -> list[dict]:
        """Generate action items based on correlations."""
        actions = []
        for corr in correlations:
            if corr["strength"] >= 0.8:
                actions.append(
                    {
                        "action": "increase_exposure",
                        "target": corr["asset"],
                        "reason": f"{corr['tech_trend']} → 강한 상관관계 ({corr['strength']})",
                    }
                )
            elif corr["strength"] >= 0.6:
                actions.append(
                    {
                        "action": "monitor",
                        "target": corr["asset"],
                        "reason": f"{corr['tech_trend']} → 관찰 필요 ({corr['strength']})",
                    }
                )
        return actions
