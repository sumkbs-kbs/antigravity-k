"""qwen3.6(로컬) vs frontier 모델 벤치마크 비교.

같은 벤치마크 케이스로 로컬 모델과 frontier 모델(gpt-4o-mini 등, OpenRouter)을
비교해 "프론티어 근접도"를 측정한다. 증폭 off(revision_off)로 순수 모델 능력을
비교한다.

사용:
    # .env 에 OPENROUTER_API_KEY 필요
    uv run python scripts/run_frontier_comparison.py
    uv run python scripts/run_frontier_comparison.py --frontier openai/gpt-4o-mini --cases sim-001 lh-001
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--local", default="qwen3.6:latest", help="로컬 모델")
    p.add_argument("--frontier", default="openai/gpt-4o-mini", help="frontier 모델")
    p.add_argument(
        "--cases",
        nargs="+",
        default=["sim-001", "lh-001"],
        help="벤치마크 케이스 ID (default: sim-001 lh-001)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmarks/frontier-comparison.json"),
        help="결과 JSON 저장 경로",
    )
    return p.parse_args()


def _score(harness, case_id: str, target: str) -> dict:
    out = harness.compare_amplification([case_id], target, modes=["revision_off"])
    r = out["by_case"][case_id]["revision_off"]
    return {
        "score": r.benchmark_score,
        "grade": r.quality_grade,
        "latency_ms": r.latency_ms,
    }


def main() -> int:
    from antigravity_k.engine.benchmark_harness import BenchmarkHarness
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry
    from antigravity_k.engine.quality_gate import QualityGate

    args = _parse_args()
    mgr = ModelManager(ModelRegistry())
    rows = []

    print(f"{'케이스':<12} {args.local:<20} {args.frontier:<20} 격차")
    print("-" * 70)
    for cid in args.cases:
        # revision_off 로 순수 모델 능력 비교 (공평한 베이스라인)
        h_local = BenchmarkHarness(mgr, quality_gate=QualityGate(max_retries=0), db_path=None)
        local = _score(h_local, cid, args.local)
        h_front = BenchmarkHarness(mgr, quality_gate=QualityGate(max_retries=0), db_path=None)
        front = _score(h_front, cid, args.frontier)
        gap = front["score"] - local["score"]
        rows.append({"case_id": cid, "local": local, "frontier": front, "gap": gap})
        print(f"{cid:<12} {local['score']:<20.2f} {front['score']:<20.2f} {gap:+.2f}")

    avg_local = sum(r["local"]["score"] for r in rows) / len(rows)
    avg_front = sum(r["frontier"]["score"] for r in rows) / len(rows)
    avg_gap = avg_front - avg_local
    print("-" * 70)
    print(f"{'평균':<12} {avg_local:<20.2f} {avg_front:<20.2f} {avg_gap:+.2f}")
    print(f"\n격차 {avg_gap:+.2f} (음수/0이면 로컬이 frontier 도달/초과, 양수가 격차)")

    payload = {
        "schema_version": 1,
        "local_model": args.local,
        "frontier_model": args.frontier,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "cases": rows,
        "avg_local": avg_local,
        "avg_frontier": avg_front,
        "avg_gap": avg_gap,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n결과 저장: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
