#!/usr/bin/env python3
"""증폭 팔 조합 A/B 실측 (qwen 30B급 로컬 모델).

동일 케이스를 여러 증폭 팔로 실행해 QualityGate 종합점수 차이를 측정한다.
--modes로 팔을 자유 조합한다:

  cascade_off : 단일 생성 baseline (재시도 0)
  bon_on      : 실행 검증 Best-of-N (재시도 0)
  avo_on      : AVO 감독 재시도 루프 (예산 2, STALL 개입 주입)
  bon_avo     : BoN + AVO 감독 조합
  revision_on : 기존 재생성 증폭 (비교용)

첫 번째 팔이 baseline이 되며, 나머지 팔의 delta가 계산된다.

사용:
    uv run python scripts/run_bon_ab_measurement.py
    uv run python scripts/run_bon_ab_measurement.py --cases lh-001 --n-samples 3 \
        --modes cascade_off bon_on avo_on bon_avo
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", nargs="+", default=["sim-001", "lh-001"])
    p.add_argument("--target", default="qwen3.8")
    p.add_argument("--n-samples", type=int, default=3)
    p.add_argument("--repeats", type=int, default=1, help="노이즈 감소용 반복 횟수")
    p.add_argument(
        "--modes",
        nargs="+",
        default=["cascade_off", "bon_on"],
        help="비교할 증폭 팔 목록 (첫 팔이 baseline)",
    )
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
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
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

    print(
        f"target={args.target} n_samples={args.n_samples} repeats={args.repeats} cases={args.cases} modes={args.modes}"
    )
    acc: dict[str, dict[str, list[float]]] = {cid: {m: [] for m in args.modes} for cid in args.cases}
    out: dict[str, Any] = {"stats": {}}

    for rep in range(1, args.repeats + 1):
        out = harness.compare_amplification(args.cases, args.target, modes=args.modes)
        for cid in args.cases:
            by = out["by_case"].get(cid, {})
            for mode in args.modes:
                r = by.get(mode)
                if r is not None and not r.error:
                    acc[cid][mode].append(r.benchmark_score)
        print(f"[rep {rep}/{args.repeats}] done")

    baseline_mode = args.modes[0]
    rows = []
    for cid in args.cases:
        row: dict[str, Any] = {"case": cid, "repeats": args.repeats, "baseline": baseline_mode}
        for mode in args.modes:
            scores = acc[cid][mode]
            if scores:
                row[mode] = {
                    "mean_score": round(sum(scores) / len(scores), 4),
                    "scores": [round(s, 4) for s in scores],
                }
        base = row.get(baseline_mode)
        deltas = {}
        if base:
            for mode in args.modes[1:]:
                arm = row.get(mode)
                if arm:
                    deltas[mode] = round(arm["mean_score"] - base["mean_score"], 4)
        if deltas:
            row["delta_vs_baseline"] = deltas
        rows.append(row)

    stats = out["stats"]
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": args.target,
        "n_samples": args.n_samples,
        "modes": args.modes,
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
