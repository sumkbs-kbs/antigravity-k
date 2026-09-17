"""기록된 **실제 실행**을 새 SC-6 기준으로 다시 판정한다 — 합성 픽스처만으로는 못 닫는 구멍.

왜 필요한가(문서가 스스로 남긴 위험):
    새 기준(창 밖 증가 + 반복당 creep)의 검증은 **합성 픽스처**로만 되어 있었다(`test_sc6_criterion_contract.py`
    의 8건). 문서는 그 사실을 “남는 위험: 통과 경로는 합성 픽스처로만 증명”이라고 적어 두었고, 그것은
    “이 기준이 **진짜 8시간 실행**을 옳게 판정하는가” 를 아무도 안 물어봤다는 뜻이다.

    물어볼 자료는 이미 있다 — 이 창이 남긴 **실제 리포트** 세 개다:

    | 실행 | 실제 성격 | 옛 기준이 한 말 |
    |---|---|---|
    | `soak-28800-fail001.json` | **진짜 누수**(`journal.tail()` 전체 파싱 · 증가 1,683.5 MB) | FAIL |
    | `soak-28800.json` (4차) | 건강(증가 52.1 MB) | pass |
    | `soak-60.json` | 60초 리허설 — 8시간 임계값을 물으면 안 되는 실행 | pass(+21.2 MB 를 누수처럼 볼 뻔했다) |

    그래서 이 프로브는 **적용된 함수**(`scripts/val02_staging.py` 의 `sc6_warmup_window_s`·`sc6_rss_criterion`)를
    그대로 불러 세 실행을 다시 판정한다. 재구현하지 않는 이유는 그것이 목적이기 때문이다 —
    “새 코드가 실제 자료에서 무엇을 말하는가”.

정직하게 밝히는 한계:
    옛 리포트는 `rss_samples_mb` 만 남기고 **표본 시각을 남기지 않는다**(하네스가 `sample_times_s` 를
    파일에 쓰지 않는다). 그래서 창 경계가 되는 표본 인덱스만은 **시간 모델**로 세운다:
    반복 수는 정확히 복원된다(표본은 50 반복마다 찍히므로 `ops = 50·k`), 시각은 “창이 소비한 반복 비율”
    `share` 로 만든다. 그래서 판정은 **한 값이 아니라 구간**으로 보고한다 — `share` 를 0.04~0.06(±20%)으로
    흔들어 **판정이 뒤집히지 않는지**까지 본다. 뒤집히면 그 사실이 결론이다(그때는 리포트에 시각을 남겨야 한다).

사용:
    PYTHONPATH=src .venv/bin/python docs/qa/2026-09-16-followup/nx10/sc6fix/replay_real_runs.py
    PYTHONPATH=src …/replay_real_runs.py --json        # 기계 판독(계약 시험이 같은 함수를 쓴다)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NX10 = HERE.parent
# 표본은 하네스 루프에서 50 반복마다 찍힌다(`i % 50 == 0`) — 반복 수 복원의 근거다.
SAMPLE_EVERY_OPS = 50
# 창이 소비한 **반복 비율**의 불확실성 구간. 0.05 = 처리량 일정 모델(창 5% ↔ 반복 5%).
SHARES = (0.04, 0.045, 0.05, 0.055, 0.06)
CASES = (
    ("누수 실행", "soak-28800-fail001.json"),
    ("4차 실행(건강)", "soak-28800.json"),
    ("60초 리허설", "soak-60.json"),
)


def repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError("저장소 루트를 찾지 못했다 — pyproject.toml 이 없다")


def load_staging(repo: Path) -> Any:
    """적용된 하네스를 **모듈로** 불러온다(재구현 금지 — 적용된 함수가 판정해야 한다)."""
    path = repo / "scripts" / "val02_staging.py"
    spec = importlib.util.spec_from_file_location("nx10_val02_staging", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def soak_scenario(report: Path) -> dict[str, Any] | None:
    doc = json.loads(report.read_text(encoding="utf-8"))
    for scenario in doc.get("scenarios") or []:
        if scenario.get("scenario") == "SC-6-soak":
            return scenario
    return None


def times_for_share(sample_count: int, share: float, window_s: float) -> list[float]:
    """`share` 비율의 반복이 창(`window_s`)을 소비한다고 놓고 표본 시각을 만든다.

    이 값은 창 경계 인덱스(`rss_warmup_index`) 하나만 정한다 — 반복 수와 증가량은 리포트 값 그대로다.
    """
    boundary = max(1, int(round(share * sample_count)))
    per_sample = window_s / boundary
    return [index * per_sample for index in range(sample_count)]


def replay(report: Path, staging: Any) -> dict[str, Any]:
    """한 리포트를 새 기준으로 판정한다(순수 계산 — 파일을 쓰지 않는다)."""
    scenario = soak_scenario(report)
    if scenario is None:
        return {"report": report.name, "error": "SC-6 시나리오가 없다"}
    samples = [round(float(value), 1) for value in scenario.get("rss_samples_mb") or []]
    duration = float(scenario.get("actual_duration_s") or scenario.get("duration_s") or 0.0)
    completed_ops = int(scenario.get("completed_ops") or 0)
    if len(samples) < 3 or duration <= 0:
        return {"report": report.name, "error": f"표본 부족({len(samples)}) 또는 지속시간 없음({duration})"}
    ops = [SAMPLE_EVERY_OPS * (index + 1) for index in range(len(samples))]
    window_s = staging.sc6_warmup_window_s(duration)
    arms: dict[str, Any] = {}
    for share in SHARES:
        fields = staging.sc6_rss_criterion(samples, ops, times_for_share(len(samples), share, window_s), duration)
        arms[f"{share:.3f}"] = {
            "verdict": fields.get("rss_criterion"),
            "index": fields.get("rss_warmup_index"),
            "excluded_mb": fields.get("rss_growth_warmup_excluded_mb"),
            "creep_kb_per_op": fields.get("rss_creep_kb_per_operation"),
            "basis": fields.get("rss_criterion_basis"),
        }
    verdicts = {arm["verdict"] for arm in arms.values()}
    return {
        "report": report.name,
        "samples": len(samples),
        "duration_s": duration,
        "completed_ops": completed_ops,
        "ops_per_sample_assumed": round(completed_ops / len(samples), 2) if completed_ops else None,
        "window_s": round(window_s, 1),
        "total_growth_mb": round(samples[-1] - samples[0], 1),
        "old_criterion_limit_mb": staging.RSS_LEAK_THRESHOLD_MB,
        "old_verdict": "pass" if (samples[-1] - samples[0]) <= staging.RSS_LEAK_THRESHOLD_MB else "fail",
        "arms": arms,
        "robust_to_time_model": len(verdicts) == 1,
        "verdict": sorted(str(v) for v in verdicts)[0] if len(verdicts) == 1 else "mixed",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="기록된 실제 soak 실행을 새 SC-6 기준으로 재판정")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=str(HERE / "replay-real-runs.json"))
    args = parser.parse_args(argv)
    repo = repo_root(HERE)
    staging = load_staging(repo)
    results = []
    for label, filename in CASES:
        report = NX10 / filename
        if not report.is_file():
            results.append({"label": label, "report": filename, "error": "리포트가 없다"})
            continue
        results.append({"label": label, **replay(report, staging)})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("=== 새 SC-6 기준으로 본 실제 실행 (창 = max(5분, 지속×5%)) ===\n")
        for item in results:
            if item.get("error"):
                print(f"[{item['label']}] {item['report']}: {item['error']}")
                continue
            print(f"[{item['label']}] {item['report']}")
            print(
                f"  표본 {item['samples']:,}개 · 지속 {item['duration_s']:.0f}s · 창 {item['window_s']:.0f}s · "
                f"총 증가 {item['total_growth_mb']:.1f} MB(옛 기준 {item['old_criterion_limit_mb']:.0f} MB → {item['old_verdict']})"
            )
            for share, arm in item["arms"].items():
                print(
                    f"    share {share}: {arm['verdict']} · 창 경계 표본 {arm['index']:,} · "
                    f"창 밖 증가 {arm['excluded_mb']} MB · 반복당 {arm['creep_kb_per_op']} KB"
                )
            flag = "시각 모델에 흔들리지 않는다" if item["robust_to_time_model"] else "**시각 모델에 따라 뒤집힌다**"
            print(f"  → 판정 {item['verdict']} · {flag}\n")

    if args.out and not args.json:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"기록: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
