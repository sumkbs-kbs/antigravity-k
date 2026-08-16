from __future__ import annotations

import argparse
import json
from pathlib import Path

from antigravity_k.tools.claim_grounding_benchmark import (
    load_claim_grounding_cases,
    load_claim_responses,
    run_claim_grounding_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/claim_grounding_cases.json"),
    )
    _ = parser.add_argument("--responses", type=Path, default=None)
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmarks/claim-grounding.json"),
    )
    args = parser.parse_args()
    cases = load_claim_grounding_cases(args.fixture)
    responses = load_claim_responses(args.responses) if args.responses else None
    results = run_claim_grounding_benchmark(cases, responses)
    payload = {
        "case_count": len(results),
        "passed_count": sum(result.passed for result in results),
        "failed_count": sum(not result.passed for result in results),
        "response_overrides": sorted(responses) if responses else [],
        "results": [result.to_dict() for result in results],
    }
    _ = args.output.parent.mkdir(parents=True, exist_ok=True)
    _ = args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
