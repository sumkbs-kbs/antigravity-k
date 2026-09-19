"""
Swarm Mode — Parallel Multi-Agent Analytics Orchestrator

Spawns multiple worker agents in parallel, collects results,
and optionally correlates them for actionable insights.

Usage:
    python swarm_mode/orchestrator.py --workers financial,tech --config config.json
    python swarm_mode/orchestrator.py --all
"""

import json
import logging
import time
import uuid
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import TypeAlias, cast

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("swarm.orchestrator")

try:
    from .llm_client import get_status
    from .workers.base_worker import BaseWorker, WorkerResult
except ImportError:
    import sys

    module_dir = Path(__file__).resolve().parent
    repo_root = module_dir.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from swarm_mode.llm_client import get_status
    from swarm_mode.workers.base_worker import BaseWorker, WorkerResult

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

WorkerConfigMap: TypeAlias = dict[str, object]
WorkerRecord: TypeAlias = dict[str, object]


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    raw = cast(Mapping[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _as_mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [_as_mapping(cast(Mapping[object, object], item)) for item in items if isinstance(item, Mapping)]


def _as_text(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item for item in items if isinstance(item, str)]


def _as_float(value: object, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _as_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


class WorkerStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class SwarmRun:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: WorkerStatus = WorkerStatus.PENDING
    workers: dict[str, WorkerRecord] = field(default_factory=dict)
    correlations: list[WorkerRecord] = field(default_factory=list)
    error_summary: str = field(default="")
    duration_seconds: float = 0.0
    completed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    llm_backend: str = field(default="unknown")  # "local", "openrouter", "mixed"

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


class SwarmOrchestrator:
    """Manages parallel worker execution and result correlation."""

    def __init__(self, config_path: str | None = None):
        self.config: dict[str, object] = self._load_config(config_path)
        self.swarm_config: dict[str, object] = _as_mapping(self.config.get("swarm"))
        self.output_config: dict[str, object] = _as_mapping(self.config.get("output"))
        self.lm_config: dict[str, object] = _as_mapping(self.config.get("lm"))
        self.timeout: int = _as_int(self.swarm_config.get("timeout"), 300)
        self.max_workers: int = _as_int(self.swarm_config.get("max_workers"), 4)
        self.retry_attempts: int = _as_int(self.swarm_config.get("retry_attempts"), 2)
        self._llm_status: dict[str, bool] = {}

    def _load_config(self, config_path: str | None) -> dict[str, object]:
        if config_path and Path(config_path).exists():
            return _as_mapping(cast(object, json.loads(Path(config_path).read_text())))
        config_file = BASE_DIR / "config.json"
        if config_file.exists():
            return _as_mapping(cast(object, json.loads(config_file.read_text())))
        return self._default_config()

    def _default_config(self) -> dict[str, object]:
        return {
            "swarm": {"max_workers": 4, "timeout": 300},
            "output": {"dir": "outputs"},
            "lm": {
                "strategy": "local_first_or_fallback",
                "local_base_url": "http://localhost:11434",
                "local_model": "qwen3.6-models",
                "or_model": "openrouter/free",
            },
        }

    def _check_llm_backends(self):
        """Check what LLM backends are available."""
        self._llm_status = get_status()

    def get_llm_backend(self) -> str:
        """Determine which LLM backend to use."""
        strategy = _as_text(self.lm_config.get("strategy"), "local_first_or_fallback")

        if strategy == "or_only":
            return "openrouter"

        if strategy == "local_only":
            return "local"

        # local_first_or_fallback (default)
        if self._llm_status.get("local"):
            return "local"

        # Fallback to OpenRouter
        if self._llm_status.get("openrouter"):
            return "openrouter"

        return "error"

    def get_enabled_workers(self) -> list[WorkerConfigMap]:
        """Get list of enabled worker configs."""
        workers_config = _as_mapping_list(self.config.get("workers"))
        return [worker for worker in workers_config if bool(worker.get("enabled", True))]

    def load_worker_class(self, worker_name: str) -> type[BaseWorker] | None:
        """Import a worker module and return the BaseWorker subclass."""
        try:
            mod = cast(ModuleType, __import__(f"swarm_mode.workers.{worker_name}", fromlist=[worker_name]))
            for attr in dir(mod):
                obj = getattr(mod, attr, None)
                if isinstance(obj, type) and issubclass(obj, BaseWorker) and obj != BaseWorker:
                    return obj
            return None
        except (ImportError, AttributeError):
            return None

    def execute(self, worker_names: list[str] | None = None) -> SwarmRun:
        """Run workers in parallel and collect results."""
        run = SwarmRun()
        run.status = WorkerStatus.RUNNING
        t0 = time.time()

        # Check LLM backends first
        self._check_llm_backends()
        backend = self.get_llm_backend()
        run.llm_backend = backend

        log.info("=== Swarm Mode STARTING ===")
        log.info(f"LLM Backend: {backend}")
        log.info(f"LLM Status: {self._llm_status}")
        log.info(f"Strategy: {self.lm_config.get('strategy', 'unknown')}")
        log.info("=== ========================= ===")

        # Select workers
        all_workers = self.get_enabled_workers()
        if worker_names:
            workers_to_run = [worker for worker in all_workers if _as_text(worker.get("name")) in worker_names]
        else:
            workers_to_run = all_workers

        if not workers_to_run:
            run.status = WorkerStatus.FAILED
            run.error_summary = "No workers found or all disabled."
            return run

        # Execute in parallel
        results: dict[str, WorkerResult] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map: dict[Future[WorkerResult], WorkerConfigMap] = {}
            for worker_cfg in workers_to_run:
                future = executor.submit(self._run_single_worker, worker_cfg, backend)
                future_map[future] = worker_cfg

            for future in as_completed(future_map, timeout=self.timeout):
                worker_cfg = future_map[future]
                try:
                    result = future.result(timeout=self.timeout)
                    worker_name = _as_text(worker_cfg.get("name"))
                    results[worker_name] = result
                    run.workers[worker_name] = cast(WorkerRecord, asdict(result))
                except Exception as e:
                    worker_name = _as_text(worker_cfg.get("name"))
                    run.workers[worker_name] = {"status": WorkerStatus.FAILED.value, "error": str(e)}
                    run.error_summary += f"Worker '{worker_name}' failed: {e}\n"

        # Correlation step if correlator is enabled
        if results.get("financial_analyzer") and results.get("tech_trend_analyzer"):
            run.correlations = self._correlate_results(results["financial_analyzer"], results["tech_trend_analyzer"])

        run.status = WorkerStatus.SUCCESS
        run.duration_seconds = time.time() - t0

        # Save output
        self._save_output(run)
        return run

    def _run_single_worker(self, worker_cfg: WorkerConfigMap, backend: str) -> WorkerResult:
        """Run a single worker with retry logic and LLM fallback."""
        name = _as_text(worker_cfg.get("name"))
        worker_cls = self.load_worker_class(name)
        if not worker_cls:
            return WorkerResult(
                worker=name, status=WorkerStatus.FAILED.value, duration=0.0, error=f"Worker class not found: {name}"
            )

        worker_instance = worker_cls(_as_mapping(worker_cfg.get("params")))
        last_error: Exception | None = None

        for attempt in range(1 + self.retry_attempts):
            try:
                # Pass backend info to worker
                setattr(worker_instance, "_llm_backend", backend)
                setattr(worker_instance, "_llm_config", self.lm_config)
                result = worker_instance.execute()
                return result
            except Exception as e:
                last_error = e
                log.warning(f"Worker '{name}' attempt {attempt} failed: {e}")
                if attempt < self.retry_attempts:
                    time.sleep(1 * (attempt + 1))  # 1s, 2s backoff
                    continue

        return WorkerResult(worker=name, status=WorkerStatus.FAILED.value, duration=0.0, error=str(last_error))

    def _correlate_results(self, financial_result: WorkerResult, tech_result: WorkerResult) -> list[WorkerRecord]:
        """Find correlations between financial and tech data."""
        correlations: list[WorkerRecord] = []
        fin_data = _as_mapping(cast(object, financial_result.data))
        tech_data = _as_mapping(cast(object, tech_result.data))
        market_metrics = _as_mapping(fin_data.get("market_metrics"))
        fin_assets: dict[str, WorkerRecord] = {}
        for name, asset in market_metrics.items():
            if isinstance(asset, Mapping) and "change_pct" in asset:
                fin_assets[name] = _as_mapping(cast(Mapping[object, object], asset))
        tech_trends = _as_mapping_list(tech_data.get("trends"))

        for trend in tech_trends:
            trend_assets = _as_text_list(trend.get("related_assets"))
            for asset_name in trend_assets:
                for name, asset in fin_assets.items():
                    if asset_name.lower() in name.lower():
                        correlations.append(
                            {
                                "tech_trend": trend.get("topic", "unknown"),
                                "asset": name,
                                "market_change": _as_float(asset.get("change_pct")),
                                "confidence": _as_float(trend.get("confidence"), 0.5),
                                "action": "monitor",
                            }
                        )
                        break

        # Auto-generate actions for high-confidence correlations
        for c in correlations:
            if _as_float(c.get("confidence")) > 0.7:
                c["action"] = "review_portfolio"
            elif _as_float(c.get("market_change")) > 5:
                c["action"] = "consider_profit"

        return correlations

    def _save_output(self, run: SwarmRun) -> None:
        """Save run results as JSON."""
        configured_dir = Path(str(self.output_config.get("dir", "outputs")))
        if configured_dir.is_absolute():
            output_dir = configured_dir
        elif configured_dir.parts and configured_dir.parts[0] == BASE_DIR.name:
            output_dir = BASE_DIR.parent / configured_dir
        else:
            output_dir = BASE_DIR / configured_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_file = output_dir / f"run_{ts}_{run.run_id}.json"
        _ = output_file.write_text(json.dumps(asdict(run), indent=2, ensure_ascii=False))

        if self.output_config.get("include_wiki_doc"):
            wiki_content = self._generate_wiki_doc(run)
            wiki_file = output_dir / f"run_{ts}_{run.run_id}.md"
            _ = wiki_file.write_text(wiki_content)

    def _generate_wiki_doc(self, run: SwarmRun) -> str:
        """Generate a Wiki-format markdown doc from run results."""
        lines = [
            f"# Swarm Analysis — {run.started_at[:10]}",
            "",
            f"**Run ID:** `{run.run_id}` | **Duration:** {run.duration_seconds:.1f}s | **Status:** {run.status.value} | **LLM Backend:** {run.llm_backend}",
            "",
            "## Workers",
            "",
        ]
        for name, result in run.workers.items():
            status = result.get("status", "?")
            duration = result.get("duration", 0)
            lines.append(f"- [{name}](#{name}) — **{status}** ({duration:.1f}s)")

        if run.correlations:
            lines += ["", "## Correlations", ""]
            for c in run.correlations:
                lines.append(
                    f"- **{c.get('tech_trend', '?')}** ↔ {c.get('asset', '?')} "
                    + f"(변화: {c.get('market_change', 0):+.2f}% | 신뢰도: {c.get('confidence', 0):.1f}) "
                    + f"→ {c.get('action', 'review')}"
                )

        return "\n".join(lines)

    def execute_with_backtest(self, strategy_desc: str) -> SwarmRun:
        """Run swarm mode with goal-based backtest."""
        try:
            from .goal_backtest import run_backtest
        except ImportError:
            from swarm_mode.goal_backtest import run_backtest

        run = SwarmRun()
        t0 = time.time()

        log.info(f"Goal Mode: '{strategy_desc}'")

        # Execute swarm first
        _ = self.execute()

        # Run backtest
        bt_result = run_backtest(ticker="005930.KS", strategy="ma_crossover", period=90, config=self.config)

        run.workers["backtest"] = asdict(bt_result)
        run.status = WorkerStatus.SUCCESS
        run.duration_seconds = time.time() - t0

        return run


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Swarm Mode Orchestrator")
    _ = parser.add_argument("--workers", type=str, default=None, help="Comma-separated worker names (e.g., financial,tech)")
    _ = parser.add_argument("--config", type=str, default=None, help="Path to config JSON")
    args = parser.parse_args()

    config_path = cast(str | None, args.config)
    workers_arg = cast(str | None, args.workers)
    orch = SwarmOrchestrator(config_path)
    worker_list = workers_arg.split(",") if workers_arg else None
    run = orch.execute(worker_list)

    print(json.dumps(asdict(run), indent=2, ensure_ascii=False))
