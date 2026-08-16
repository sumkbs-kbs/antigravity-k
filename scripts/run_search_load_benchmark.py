from __future__ import annotations

import argparse
import json
from pathlib import Path

import anyio

from antigravity_k.tools.search_benchmark import _load_cases, run_search_load_benchmark
from antigravity_k.tools.web_search_engine import WebSearchEngine


async def _run(fixture: Path, repeats: int, concurrency: int) -> dict[str, object]:
    cases = _load_cases(fixture)
    engine = WebSearchEngine(max_results=3)
    try:
        report = await run_search_load_benchmark(
            engine,
            [case.query for case in cases],
            repeats=repeats,
            concurrency=concurrency,
        )
        return report.to_dict()
    finally:
        await engine.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/search_quality_cases.json"))
    parser.add_argument("--output", type=Path, default=Path("data/benchmarks/live-search-load.json"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    report = anyio.run(_run, args.fixture, args.repeats, args.concurrency)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    error_count = report.get("error_count")
    return 0 if isinstance(error_count, int) and error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
