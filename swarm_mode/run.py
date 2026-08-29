"""Swarm Mode — entry point for parallel multi-agent analytics."""

import argparse
import json
import sys
from pathlib import Path

try:
    from .llm_client import get_status
    from .orchestrator import SwarmOrchestrator
except ImportError:
    module_dir = Path(__file__).resolve().parent
    repo_root = module_dir.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from swarm_mode.llm_client import get_status
    from swarm_mode.orchestrator import SwarmOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Antigravity-K Swarm Mode")
    parser.add_argument(
        "--workers", type=str, default=None, help='Workers to run: "financial,tech" or "financial,tech,correlator"'
    )
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    parser.add_argument(
        "--goal-mode", type=str, default=None, help="Backtest strategy description (triggers backtest mode)"
    )
    parser.add_argument("--llm-status", action="store_true", help="Show LLM backend status and exit")
    parser.add_argument(
        "--strategy",
        type=str,
        default="local_first_or_fallback",
        help="LLM strategy: local_only, local_first_or_fallback, or_only",
    )
    args = parser.parse_args()

    # Show LLM status if requested
    if args.llm_status:
        status = get_status()
        print("=" * 50)
        print("  LLM Backend Status")
        print("=" * 50)
        for backend, available in status.items():
            icon = "V" if available else "X"
            print(f"  [{icon}] {backend}")
        print("=" * 50)
        print(f"\nCurrent strategy: {args.strategy}")

        # Show which backend will be selected
        strategy = args.strategy
        if strategy == "or_only":
            print("Selected backend: openrouter")
        elif strategy == "local_only":
            print(f"Selected backend: {'local (V)' if status['local'] else 'local (X) - NEEDS FIX'}")
        else:  # local_first_or_fallback
            if status["local"]:
                print("Selected backend: local (will fallback to openrouter if unavailable)")
            elif status["openrouter"]:
                print("Selected backend: openrouter (local unavailable)")
            else:
                print("Selected backend: ERROR — no backends available!")
        print("=" * 50)
        return

    orch = SwarmOrchestrator(args.config)

    if args.goal_mode:
        # Goal Mode: run backtest
        result = orch.execute_with_backtest(args.goal_mode)
    else:
        worker_list = args.workers.split(",") if args.workers else None
        result = orch.execute(worker_list)

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
