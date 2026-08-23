#!/usr/bin/env python3
"""실행 검증 Best-of-N 증폭의 A/B 실측 (qwen 30B급 로컬 모델).

동일 케이스를 [baseline(단일 생성), bon_on(실행 검증 N샘플)] 두 경로로 실행해
QualityGate 종합점수 차이를 측정한다. revision(retry)을 양쪽 모두 0으로 고정해
BoN 단독 효과만 분리한다.

사용:
    uv run python scripts/run_bon_ab_measurement.py
    uv run python scripts/run_bon_ab_measurement.py --cases lh-001 --n-samples 3
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", nargs="+", default=["sim-001", "lh-001"])
    p.add_argument("--target", default="qwen3.8")
    p.add_argument("--n-samples", type=int, default=3)
    p.add_argument("--repeats", type=int, default=1, help="노이즈 감소용 반복 횟수")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmarks/bon-ab-measurement.json"),
    )
    return p.parse_args()


def main() -> int:
    from antigravity_k.engine.benchmark_harness import BenchmarkHarness
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.model_registry import ModelRegistry

    args = _parse_args()
    registry = ModelRegistry()
    raw = getattr(registry, "_raw", None)
    if isinstance(raw, dict):
        amp = raw.setdefault("amplification", {})
        if not isinstance(amp, dict):
            amp = {}
            raw["amplification"] = amp
        bon_cfg = {
            "enabled": True,
            "n_samples": args.n_samples,
            "base_temperature": 0.7,
            "temperature_spread": 0.3,
            "verifier": "syntax",
            "feedback_loop": False,
            "complexity_threshold": None,
        }
        amp["best_of_n"] = bon_cfg

    mgr = ModelManager(registry)
    harness = BenchmarkHarness(mgr, db_path=None)
    harness._quality_gate.max_retries = 0  # 양팔 모두 revision off — BoN 단독 효과 분리

    print(f"target={args.target} n_samples={args.n_samples} repeats={args.repeats} cases={args.cases}")
    acc: dict[str, dict[str, list[float]]] = {cid: {"cascade_off": [], "bon_on": []} for cid in args.cases}

    for rep in range(1, args.repeats + 1):
        out = harness.compare_amplification(args.cases, args.target, modes=["cascade_off", "bon_on"])
        for cid in args.cases:
            by = out["by_case"].get(cid, {})
            for mode in ("cascade_off", "bon_on"):
                r = by.get(mode)
                if r is not None and not r.error:
                    acc[cid][mode].append(r.benchmark_score)
        print(f"[rep {rep}/{args.repeats}] done")

    rows = []
    for cid in args.cases:
        row: dict = {"case": cid, "repeats": args.repeats}
        for mode in ("cascade_off", "bon_on"):
            scores = acc[cid][mode]
            if scores:
                row[mode] = {
                    "mean_score": round(sum(scores) / len(scores), 4),
                    "scores": [round(s, 4) for s in scores],
                }
        base, bon = row.get("cascade_off"), row.get("bon_on")
        if base and bon:
            row["delta_score"] = round(bon["mean_score"] - base["mean_score"], 4)
        rows.append(row)

    stats = out["stats"]
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "n_samples": args.n_samples,
        "rows": rows,
        "improvement": stats.get("improvement", {}),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"\nimprovement: {json.dumps(stats.get('improvement', {}), ensure_ascii=False)}")
    print(f"saved → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
