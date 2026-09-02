#!/usr/bin/env python3
"""Self-consistency 증폭 A/B 실측 (직접 Ollama + SelfConsistencyEngine).

amplification.self_consistency.enabled 전환 근거 확보.
baseline(단일 샘플, temp=GENERAL 프로파일) vs SC(n샘플 병렬 + 다수결)을
동일 검증 가능한 문제 세트로 비교한다. thinking은 고정 OFF로 격리한다.

사용:
    uv run python scripts/measure_sc_ab.py [--n-samples 3] [--repeats 2]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from antigravity_k.engine.self_consistency import SelfConsistencyEngine  # noqa: E402
from scripts.measure_thinking_ab import QUESTIONS  # noqa: E402 — 같은 문제 세트 재사용

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3.8:latest"


def call_ollama(prompt: str, temperature: float) -> str:
    import re

    payload = {
        "model": MODEL,
        "stream": False,
        "keep_alive": "30m",
        "think": False,
        "options": {"temperature": temperature, "num_predict": 2048, "num_ctx": 16384},
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = str(data.get("message", {}).get("content", "") or "")
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-samples", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    print(f"🗳️ Self-consistency A/B (n={args.n_samples}, repeats={args.repeats}, thinking=OFF 고정)")

    baseline_correct = 0
    sc_correct = 0
    baseline_lat: list[float] = []
    sc_lat: list[float] = []

    engine = SelfConsistencyEngine(
        generate_fn=lambda p, **kw: call_ollama(p, float(kw.get("temperature", 0.5))),
        n_samples=args.n_samples,
        base_temperature=0.5,
        temperature_spread=0.3,
        similarity_threshold=0.4,
        selection="majority",
    )

    for q in QUESTIONS:
        base_ok = 0
        sc_ok = 0
        for _ in range(args.repeats):
            start = time.perf_counter()
            answer = call_ollama(q.prompt, 0.5)
            baseline_lat.append(time.perf_counter() - start)
            if q.verify(answer):
                base_ok += 1

            start = time.perf_counter()
            trace = engine.run(q.prompt)
            sc_lat.append(time.perf_counter() - start)
            if trace.skipped or not trace.selected:
                continue
            if q.verify(trace.selected):
                sc_ok += 1
        b_passed = base_ok >= (args.repeats + 1) // 2
        s_passed = sc_ok >= (args.repeats + 1) // 2
        baseline_correct += b_passed
        sc_correct += s_passed
        print(f"  {q.qid:12s} baseline={'✅' if b_passed else '❌'} SC={'✅' if s_passed else '❌'}")

    print()
    print(f"baseline(1샘플): {baseline_correct}/{len(QUESTIONS)} 정답, 평균 {statistics.mean(baseline_lat):.1f}초")
    print(f"SC(n={args.n_samples})   : {sc_correct}/{len(QUESTIONS)} 정답, 평균 {statistics.mean(sc_lat):.1f}초")
    print(
        f"델타: {sc_correct - baseline_correct:+d} | 지연 배율: {statistics.mean(sc_lat) / max(statistics.mean(baseline_lat), 0.001):.2f}x"
    )

    if args.output:
        payload = {
            "model": MODEL,
            "n_samples": args.n_samples,
            "baseline": {"correct": baseline_correct, "mean_latency": statistics.mean(baseline_lat)},
            "self_consistency": {"correct": sc_correct, "mean_latency": statistics.mean(sc_lat)},
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"결과 저장: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
