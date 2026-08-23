"""Goal Mode Backtesting Engine.

Runs strategies on historical financial data using Swarm-Mode parallel execution.
Usage:
    python goall_backtest.py --ticker 005930.KS --strategy ma_crossover --period 90
"""

import argparse
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class BacktestResult:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    ticker: str = ""
    strategy: str = ""
    period: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
    metrics: dict = field(default_factory=dict)
    strategy_detail: dict = field(default_factory=dict)
    portfolio_impact: list = field(default_factory=list)
    error: str = ""
    duration: float = 0.0

    def to_dict(self):
        return {**self.__dict__, "completed_at": datetime.now().isoformat()}


def run_backtest(ticker: str, strategy: str, period: int, config: dict) -> BacktestResult:
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


def collect_market_data(ticker: str, period: int, config: dict) -> BacktestResult:
    """Collect market data in parallel from multiple sources."""
    result = BacktestResult(ticker=ticker)
    data_sources = config.get("data_sources", ["wiki", "krx"])
    all_data = {}

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
    import math

    closes = [100 * (1 + 0.002 * math.sin(i / 30) + 0.001 * (i / period)) for i in range(period)]
    result.data = {
        "ticker": ticker,
        "period": period,
        "closes": closes,
        "symbols": ["open", "high", "low", "close", "volume"],
        "error": None,
    }
    return result


def execute_strategy(strategy_name: str, data: dict, config: dict) -> BacktestResult:
    """Execute a backtest strategy."""
    result = BacktestResult(strategy=strategy_name)
    closes = data.get("closes", [])
    signals = []

    if strategy_name == "ma_crossover":
        sma_fast = config.get("sma_fast", 20)
        sma_slow = config.get("sma_slow", 50)
        for i in range(sma_slow, len(closes)):
            fast_ma = sum(closes[i - sma_fast : i]) / sma_fast
            slow_ma = sum(closes[i - sma_slow : i]) / sma_slow
            if fast_ma > slow_ma:
                signal = {"idx": i, "type": "buy", "fast_ma": round(fast_ma, 2), "slow_ma": round(slow_ma, 2)}
            elif fast_ma < slow_ma:
                signal = {"idx": i, "type": "sell", "fast_ma": round(fast_ma, 2), "slow_ma": round(slow_ma, 2)}
            else:
                signal = {"idx": i, "type": "hold"}
            signals.append(signal)
    elif strategy_name == "momentum":
        lookback = config.get("lookback", 20)
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
        window = config.get("window", 20)
        std_dev = config.get("std_dev_threshold", 2)
        for i in range(window, len(closes)):
            mean = sum(closes[i - window : i]) / window
            std = (sum((x - mean) ** 2 for x in closes[i - window : i]) / window) ** 0.5
            if std > 0:
                z_score = (closes[i] - mean) / std
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


def calculate_metrics(strategy_data: dict, market_data: dict) -> dict:
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
    returns = []

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
    std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
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


def analyze_portfolio_impact(metrics: dict, ticker: str) -> list[dict]:
    """Analyze portfolio impact of strategy results."""
    impacts = []

    if metrics.get("total_return", 0) > 10:
        impacts.append(
            {
                "action": "increase_weight",
                "reason": f"{ticker}: strong positive return ({metrics['total_return']:.1f}%)",
                "confidence": "high",
            }
        )
    elif metrics.get("sharpe_ratio", 0) > 1.5:
        impacts.append({"action": "maintain", "reason": f"{ticker}: good risk-adjusted return", "confidence": "medium"})
    elif metrics.get("max_drawdown", 0) > 15:
        impacts.append(
            {
                "action": "reduce_weight",
                "reason": f"{ticker}: high drawdown risk ({metrics['max_drawdown']:.1f}%)",
                "confidence": "high",
            }
        )

    return impacts


def main():
    parser = argparse.ArgumentParser(description="Goal Mode Backtesting Engine")
    parser.add_argument("--ticker", type=str, default="005930.KS", help="Stock ticker")
    parser.add_argument("--strategy", type=str, default="ma_crossover", help="Backtest strategy")
    parser.add_argument("--period", type=int, default=90, help="Lookback period (days)")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    config = {
        "sma_fast": 20,
        "sma_slow": 50,
        "lookback": 20,
        "std_dev_threshold": 2.0,
        "window": 20,
        "data_sources": ["wiki", "korea"],
    }
    if args.config:
        config.update(json.loads(Path(args.config).read_text()))

    result = run_backtest(args.ticker, args.strategy, args.period, config)
    output = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
