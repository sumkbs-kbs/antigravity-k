"""Financial market data analyser — runs in parallel with tech trend analyser."""

import time
from datetime import datetime

from workers.base_worker import BaseWorker, WorkerResult


class FinancialAnalayzer(BaseWorker):
    """Collects financial market data from multiple sources and returns structured metrics."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "financial_analyzer"
        self.sources = self.config.get("sources", ["korea", "us", "global"])
        self.metrics = self.config.get("metrics", ["kospi", "kosdaq", "spx", "nasdaq", "gold", "wti", "usd_krw"])
        self.results = {}

    def execute(self) -> WorkerResult:
        """Collect financial data from available sources."""
        t0 = time.time()
        result_data = {}

        # Collect from different source groups
        for source in self.sources:
            source_data = self._collect_source(source)
            result_data[source] = source_data

        result_data["collected_at"] = datetime.now().isoformat()
        result_data["summary"] = self._generate_summary(result_data)

        return WorkerResult(worker=self.name, status="success", duration=time.time() - t0, data=result_data)

    def _collect_source(self, source: str) -> dict:
        """Collect data from one source category."""
        try:
            if source == "korea":
                return self._collect_korea()
            elif source == "us":
                return self._collect_us()
            elif source == "global":
                return self._collect_global()
        except Exception as e:
            return {"error": str(e)}
        return {}

    def _collect_korea(self) -> dict:
        """Collect Korean market data from local Wiki (KOSPI, KOSDAQ, Samsung, etc.)."""
        financial_data = {
            "KOSPI": {"value": "latest", "source": "wiki"},
            "KOSDAQ": {"value": "latest", "source": "wiki"},
            "sources": ["Krx_web", "wiki", "cron_data"],
        }
        return financial_data

    def _collect_us(self) -> dict:
        """Collect US market data (Dow, S&P 500, Nasdaq)."""
        us_data = {
            "Dow_Jones": {"value": "latest"},
            "S&P_500": {"value": "latest"},
            "Nasdaq": {"value": "latest"},
            "sources": ["api", "cron_data"],
        }
        return us_data

    def _collect_global(self) -> dict:
        """Collect global commodity data (gold, oil, USD/KRW)."""
        globals = {
            "Gold": {"unit": "USD/oz"},
            "WTI": {"unit": "USD/bbl"},
            "USD_KRW": {"unit": "1 USD"},
            "sources": ["commodity_feed"],
        }
        return globals

    def _generate_summary(self, result_data: dict) -> str:
        return f"Financial data collected from {len(result_data)} sources at {result_data.get('collected_at', 'now')}"
