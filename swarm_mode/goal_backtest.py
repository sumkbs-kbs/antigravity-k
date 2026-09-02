"""Goal Mode Backtesting Engine.

Runs strategies on historical financial data using Swarm-Mode parallel execution.
Usage:
    python goall_backtest.py --ticker 005930.KS --strategy ma_crossover --period 90
"""

import argparse
import json
import math
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NotRequired, TypedDict, cast

BASE_DIR = Path(__file__).resolve().parent


class Signal(TypedDict):
    idx: int
    type: str
    fast_ma: NotRequired[float]
    slow_ma: NotRequired[float]
    momentum: NotRequired[float]
    z_score: NotRequired[float]


class BacktestData(TypedDict, total=False):
    ticker: str
    period: int
    closes: list[float]
    symbols: list[str]
    error: str | None
    wiki_ref: str
    signals: list[Signal]
    strategy: str


class Metrics(TypedDict):
    total_return: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    trades: NotRequired[int]
    total_trades: NotRequired[int]
    avg_return: NotRequired[float]
    portfolio_value: NotRequired[int]


class PortfolioImpact(TypedDict):
    action: str
    reason: str
    confidence: str


def _number(value: object, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _integer(value: object, default: int) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item for item in items if isinstance(item, str)]


def _empty_metrics() -> Metrics:
    return {"total_return": 0.0, "sharpe_ratio": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}


@dataclass
class BacktestResult:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    ticker: str = ""
    strategy: str = ""
    period: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
    metrics: Metrics = field(default_factory=_empty_metrics)
    strategy_detail: dict[str, int] = field(default_factory=dict)
    portfolio_impact: list[PortfolioImpact] = field(default_factory=list)
    data: BacktestData = field(default_factory=BacktestData)
    error: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "ticker": self.ticker,
            "strategy": self.strategy,
            "period": self.period,
            "started_at": self.started_at,
            "status": self.status,
            "metrics": self.metrics,
            "strategy_detail": self.strategy_detail,
            "portfolio_impact": self.portfolio_impact,
            "data": self.data,
            "error": self.error,
            "duration": self.duration,
            "completed_at": datetime.now().isoformat(),
        }


def run_backtest(ticker: str, strategy: str, period: int, config: Mapping[str, object]) -> BacktestResult:
    """Run a full backtest in Goal Mode: data collection → strategy execution → metrics → portfolio impact."""
    result = BacktestResult(ticker=ticker, strategy=strategy, period=period)
    t0 = time.time()

    # Step 1: Collect data (parallel across sources)
    data_result = collect_market_data(ticker, period, config)
    if data_result.error:
        result.error = f"Data collection failed: {data_result.error}"
        result.status = "failed"
        result.duration = time.time() - t0
        return result
    result.strategy_detail["data_collected"] = len(data_result.data.get("closes", []))

    # Step 2: Execute strategy
    strategy_result = execute_strategy(strategy, data_result.data, config)
    if strategy_result.error:
        result.error = f"Strategy execution failed: {strategy_result.error}"
        result.status = "failed"
        result.duration = time.time() - t0
        return result
    result.strategy_detail["signals"] = len(strategy_result.data.get("signals", []))

    # Step 3: Calculate metrics (parallel calculation)
    metrics_result = calculate_metrics(strategy_result.data, data_result.data)
    result.metrics = metrics_result

    # Step 4: Portfolio impact analysis
    result.portfolio_impact = analyze_portfolio_impact(result.metrics, ticker)
    result.status = "success"
    result.duration = time.time() - t0

    return result


def collect_market_data(ticker: str, period: int, config: Mapping[str, object]) -> BacktestResult:
    """Collect market data in parallel from multiple sources."""
    result = BacktestResult(ticker=ticker)
    data_sources = _string_list(config.get("data_sources", ["wiki", "krx"]))
    all_data: BacktestData = {}

    for source in data_sources:
        try:
            if source == "wiki":
                wiki_path = Path("/Users/mr.k/wiki/My_Wiki/Memories/K.md")
                if wiki_path.exists():
                    content = wiki_path.read_text()
                    all_data["wiki_ref"] = content[:200]
        except Exception as e:
            all_data[f"{source}_error"] = str(e)

    # Generate simulated data for demonstration
    closes = [100 * (1 + 0.002 * math.sin(i / 30) + 0.001 * (i / period)) for i in range(period)]
    result.data = {
        "ticker": ticker,
        "period": period,
        "closes": closes,
        "symbols": ["open", "high", "low", "close", "volume"],
        "error": None,
    }
    return result


def execute_strategy(strategy_name: str, data: BacktestData, config: Mapping[str, object]) -> BacktestResult:
    """Execute a backtest strategy."""
    result = BacktestResult(strategy=strategy_name)
    closes = data.get("closes", [])
    signals: list[Signal] = []

    if strategy_name == "ma_crossover":
        sma_fast = _integer(config.get("sma_fast"), 20)
        sma_slow = _integer(config.get("sma_slow"), 50)
        for i in range(sma_slow, len(closes)):
            fast_ma = sum(closes[i - sma_fast : i]) / sma_fast
            slow_ma = sum(closes[i - sma_slow : i]) / sma_slow
            if fast_ma > slow_ma:
                signal = {"idx": i, "type": "buy", "fast_ma": round(fast_ma, 2), "slow_ma": round(slow_ma, 2)}
            elif fast_ma < slow_ma:
                signal = {"idx": i, "type": "sell", "fast_ma": round(fast_ma, 2), "slow_ma": round(slow_ma, 2)}
            else:
                signal = {"idx": i, "type": "hold"}
            signals.append(cast(Signal, cast(object, signal)))
    elif strategy_name == "momentum":
        lookback = _integer(config.get("lookback"), 20)
        for i in range(lookback, len(closes)):
            momentum = (closes[i] - closes[i - lookback]) / closes[i - lookback] * 100
            signals.append(
                {
                    "idx": i,
                    "type": "buy" if momentum > 2 else "sell" if momentum < -2 else "hold",
                    "momentum": round(momentum, 2),
                }
            )
    elif strategy_name == "mean_reversion":
        window = _integer(config.get("window"), 20)
        std_dev = _number(config.get("std_dev_threshold"), 2.0)
        for i in range(window, len(closes)):
            mean = sum(closes[i - window : i]) / window
            window_closes = closes[i - window : i]
            squared_diffs: list[float] = [(x - mean) ** 2 for x in window_closes]
            variance: float = sum(squared_diffs) / window
            std = math.sqrt(variance)
            if std > 0:
                z_score: float = (closes[i] - mean) / std
                signals.append(
                    {
                        "idx": i,
                        "type": "buy" if z_score < -std_dev else "sell" if z_score > std_dev else "hold",
                        "z_score": round(z_score, 2),
                    }
                )
    else:
        result.error = f"Unknown strategy: {strategy_name}"
        return result

    result.data = {"signals": signals, "strategy": strategy_name}
    return result


def calculate_metrics(strategy_data: BacktestData, market_data: BacktestData) -> Metrics:
    """Calculate performance metrics."""
    closes = market_data.get("closes", [])
    signals = strategy_data.get("signals", [])

    if not signals:
        return {"total_return": 0, "sharpe_ratio": 0, "win_rate": 0, "max_drawdown": 0, "trades": 0}

    # Simulate portfolio
    capital = 1000000
    position = 0
    entry_price = 0
    trades = 0
    wins = 0
    returns: list[float] = []

    for signal in signals:
        if signal["type"] == "buy" and position == 0:
            entry_price = closes[signal["idx"]]
            position = 1
        elif signal["type"] == "sell" and position == 1:
            exit_price = closes[signal["idx"]]
            pnl = (exit_price - entry_price) / entry_price
            returns.append(pnl)
            if pnl > 0:
                wins += 1
            trades += 1
            position = 0

    total_return = sum(returns)
    win_rate = wins / trades * 100 if trades > 0 else 0
    avg_return = sum(returns) / len(returns)
    squared_returns: list[float] = [(r - avg_return) ** 2 for r in returns]
    return_variance: float = sum(squared_returns) / len(returns)
    std_return = math.sqrt(return_variance)
    sharpe = (avg_return / std_return) * (252**0.5) if std_return > 0 else 0

    # Max drawdown
    max_dd = 0
    peak = closes[0] if closes else 0
    for c in closes:
        peak = max(peak, c)
        dd = (peak - c) / peak
        max_dd = max(max_dd, dd)

    return {
        "total_return": round(total_return * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "win_rate": round(win_rate, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "total_trades": trades,
        "avg_return": round(avg_return * 100, 4),
        "portfolio_value": round(capital * (1 + total_return)),
    }


def analyze_portfolio_impact(metrics: Metrics, ticker: str) -> list[PortfolioImpact]:
    """Analyze portfolio impact of strategy results."""
    impacts: list[PortfolioImpact] = []

    total_return = metrics.get("total_return", 0.0)
    sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
    max_drawdown = metrics.get("max_drawdown", 0.0)

    if total_return > 10:
        impacts.append(
            {
                "action": "increase_weight",
                "reason": f"{ticker}: strong positive return ({total_return:.1f}%)",
                "confidence": "high",
            }
        )
    elif sharpe_ratio > 1.5:
        impacts.append({"action": "maintain", "reason": f"{ticker}: good risk-adjusted return", "confidence": "medium"})
    elif max_drawdown > 15:
        impacts.append(
            {
                "action": "reduce_weight",
                "reason": f"{ticker}: high drawdown risk ({max_drawdown:.1f}%)",
                "confidence": "high",
            }
        )

    return impacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Goal Mode Backtesting Engine")
    _ = parser.add_argument("--ticker", type=str, default="005930.KS", help="Stock ticker")
    _ = parser.add_argument("--strategy", type=str, default="ma_crossover", help="Backtest strategy")
    _ = parser.add_argument("--period", type=int, default=90, help="Lookback period (days)")
    _ = parser.add_argument("--config", type=str, default=None)
    _ = parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = cast(dict[str, object], vars(parser.parse_args()))

    config: dict[str, object] = {
        "sma_fast": 20,
        "sma_slow": 50,
        "lookback": 20,
        "std_dev_threshold": 2.0,
        "window": 20,
        "data_sources": ["wiki", "korea"],
    }
    config_path = args.get("config")
    if isinstance(config_path, str) and config_path:
        loaded = cast(object, json.loads(Path(config_path).read_text()))
        if isinstance(loaded, dict):
            config.update({str(key): value for key, value in cast(Mapping[object, object], loaded).items()})

    ticker = str(args.get("ticker", "005930.KS"))
    strategy = str(args.get("strategy", "ma_crossover"))
    period = _integer(args.get("period"), 90)
    result = run_backtest(ticker, strategy, period, config)
    output = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    output_path = args.get("output")
    if isinstance(output_path, str) and output_path:
        _ = Path(output_path).write_text(output)
        print(f"Saved to {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
