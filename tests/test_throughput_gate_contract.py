"""처리량 회귀 게이트의 계약을 고정한다(배치 `PERF`, 오너 지시 2026-09-17).

계약(이 시험이 지키는 문장):
  1. 8시간 동안 **27% 느려진 실행**을 잡는다 — 그리고 그것이 RSS 누수와 **별개 축**으로 잡힌다.
     (네 조합을 모두 고정한다: 느림+누수 · 느림만 · 누수만 · 둘 다 없음)
  2. 벽시계 감소를 **효율(ops/CPU초) × 이용률**로 분해해 **귀속**한다 — “느려졌다”와 “덜 돌았다”는 다른 사건이다.
     실측 근거: 2026-09-17 4차 실행은 벽시계 -26.5% 인데 효율 -5.0% 였다(기계 경합). 벽시계만 보는 게이트는
     그 건강한 실행을 정확히 요구된 임계(27%)에서 빨갛게 만들었을 것이다.
  3. 부하를 못 읽으면 **어느 쪽으로도 단정하지 않는다**(`not_applicable` + 재실행 요구) — 그리고
     `not_applicable` 은 통과가 아니다(SC-6 기존 규칙과 같다).
  4. 실행이 너무 짧으면(60초 리허설) 판정하지 않는다 — 시작 비용이 지배하는 구간을 회귀로 읽지 않는다.
  5. 보고서만으로 판정을 재현할 수 있다(블록 삼중항이 리포트에 실린다).

실행: .venv/bin/python -m pytest docs/qa/2026-09-16-followup/nx10/perf/test_throughput_gate_contract.py -q
"""

from __future__ import annotations

import cProfile
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    """저장소 루트를 **위로 걸어 올라가며** 찾는다 — 승격(`docs/…/perf` → `tests/`)으로 깊이가 바뀌어도 산다.

    오늘 승격 리허설이 `parents[N]` 하드코딩을 실제로 밟았다(깊이가 바뀌면 다른 곳을 본다).
    """
    for candidate in (HERE, *HERE.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return HERE


REPO = _repo_root()


def _tool_path() -> Path:
    """판정 도구를 찾는다: **동거본(스테이징)** → 승격 위치(`scripts/`) → `docs/` 원본(마지막 수단).

    승격되면 도구는 `scripts/` 에 있고 시험은 `tests/` 에 있다 — 어느 쪽에서도 도구를 찾아야
    “옮긴 뒤에도 같은 계약을 검사한다”가 성립한다(못 찾으면 조용히 건너뛰지 않고 실패한다).
    동거본을 먼저 보는 이유는 실측에 있다: 승격 **전** 저장소에는 `scripts/val02_staging.py`(아직 이
    배치가 닿지 않은 기준 구현)와 스테이징본이 **동시에** 있으므로, 승격 위치를 먼저 보면 시험이
    **옛 바이트를 검사하면서 초록**이 될 수 있다(처음에 그렇게 13개가 빨개졌다 — 순서가 시험의 뜻을 바꿈).
    """
    for candidate in (
        HERE / "val02_staging.py",
        REPO / "scripts" / "val02_staging.py",
        REPO / "docs" / "qa" / "2026-09-16-followup" / "nx10" / "perf" / "val02_staging.py",
    ):
        if candidate.is_file():
            return candidate
    raise AssertionError("판정 도구 val02_staging.py 를 찾지 못했다(승격 위치·스테이징·원본 모두 없음)")


def _fixture_path() -> Path:
    """실측 픽스처를 찾는다 — 없으면 **크게 실패한다**(조용한 스킵은 이 저장소의 금지 규칙이다).

    중요도: 이 픽스처는 “오늘의 그 실행(-26.5%)을 제품 회귀라 하지 않는가” 를 겨누는 시험의 입력이다.
    없으면 그 시험이 사라지므로, 경로 후보를 문장으로 밝히고 실패한다.
    """
    tried = [
        HERE / "live-4th-series.json",
        REPO / "tests" / "live-4th-series.json",
        REPO / "docs" / "qa" / "2026-09-16-followup" / "nx10" / "perf" / "live-4th-series.json",
    ]
    for candidate in tried:
        if candidate.is_file():
            return candidate
    raise AssertionError("실측 픽스처를 찾지 못했다 — 시도한 경로: " + ", ".join(str(p) for p in tried))


CPU_COUNT = 8


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("val02_staging_perf_under_test", _tool_path())
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _series(
    *,
    duration: float,
    efficiency: tuple[float, float],
    utilization: tuple[float, float] | float,
    load1: float = 0.4,
    step: float = 60.0,
) -> dict[str, list[float]]:
    """(효율, 이용률) 을 선형으로 움직이며 표본을 만든다 — `벽시계 = 효율 × 이용률` 이 정확히 성립한다.

    이용률을 상수로 주면 효율 감소가 곧 벽시계 감소다(제품 회귀 모형). 이용률만 떨어뜨리면
    벽시계는 줄고 효율은 그대로다(경합·대기 모형) — 두 경우가 이 게이트의 핵심 구분이다.
    """
    if isinstance(utilization, tuple):
        util_a, util_b = utilization
    else:
        util_a = util_b = float(utilization)
    ops = cpu = 0.0
    samples: dict[str, list[float]] = {"ops": [0.0], "times": [0.0], "cpu": [0.0], "load": [load1]}
    count = max(4, int(duration // step))
    for k in range(count):
        at = (k + 1) * step
        fraction = (k + 0.5) / count
        eff = efficiency[0] + (efficiency[1] - efficiency[0]) * fraction
        util = util_a + (util_b - util_a) * fraction
        ops += eff * util * step
        cpu += util * step
        samples["ops"].append(int(ops))
        samples["times"].append(round(at, 3))
        samples["cpu"].append(round(cpu, 3))
        samples["load"].append(load1)
    return samples


def _verdict(module: ModuleType, samples: dict[str, list[float]], *, cpu_count: int = CPU_COUNT) -> dict[str, Any]:
    return module.throughput_criterion(
        samples["ops"],
        samples["times"],
        samples["cpu"],
        samples["load"],
        cpu_count,
        samples["times"][-1],
    )


# ── ① 잡아야 하는 것: 8시간에 27% 느려진 실행 ─────────────────────────────────────


def test_27_percent_efficiency_decay_over_eight_hours_is_caught():
    module = _load()
    samples = _series(duration=28800.0, efficiency=(780.0, 570.0), utilization=0.72)
    verdict = _verdict(module, samples)
    assert verdict["throughput_criterion"] == "fail", verdict["throughput_criterion_basis"]
    assert verdict["throughput_efficiency_ratio"] < 0.85, verdict
    assert "제품 회귀" in verdict["throughput_criterion_basis"], verdict["throughput_criterion_basis"]
    # 근거가 두 숫자(실측·허용)를 함께 든다 — 다음 사람이 판단을 검증할 수 있어야 한다.
    assert "ops/CPU초" in verdict["throughput_criterion_basis"]
    assert "허용 15%" in verdict["throughput_criterion_basis"]


def test_healthy_five_percent_drift_does_not_fire():
    """실측 건강 실행(4차)의 효율 감소는 5.0% 였다 — 이 게이트는 그것을 건드리면 안 된다."""
    module = _load()
    samples = _series(duration=28800.0, efficiency=(780.0, 741.0), utilization=0.72)
    verdict = _verdict(module, samples)
    assert verdict["throughput_criterion"] == "pass", verdict["throughput_criterion_basis"]


# ── ② 분해와 귀속: “느려짐” vs “덜 돌아감” ──────────────────────────────────────


def test_wall_clock_drop_from_contention_is_not_a_product_regression():
    """이용률만 떨어져 벽시계가 27% 줄고 부하가 높으면 → 제품 회귀가 아니라 **재실행 요구**다."""
    module = _load()
    samples = _series(duration=28800.0, efficiency=(780.0, 780.0), utilization=(0.90, 0.65), load1=6.0)
    verdict = _verdict(module, samples)
    assert verdict["throughput_wall_ratio"] < 0.85, verdict
    assert verdict["throughput_efficiency_ratio"] > 0.95, verdict
    assert verdict["throughput_criterion"] == "not_applicable", verdict["throughput_criterion_basis"]
    assert "제품 회귀 아님" in verdict["throughput_criterion_basis"]
    assert "다시 재야" in verdict["throughput_criterion_basis"]


def test_wait_bound_slowdown_on_a_quiet_host_is_a_regression():
    """같은 벽시계 감소라도 호스트가 조용하면 “대기가 늘었다” = 제품 문제다(경합 도피 금지)."""
    module = _load()
    samples = _series(duration=28800.0, efficiency=(780.0, 780.0), utilization=(0.90, 0.65), load1=0.5)
    verdict = _verdict(module, samples)
    assert verdict["throughput_criterion"] == "fail", verdict["throughput_criterion_basis"]
    assert "서비스 회귀" in verdict["throughput_criterion_basis"]


def test_missing_host_load_never_decides_either_way():
    """부하를 못 읽었으면 단정하지 않는다 — 없는 결함도, 덮어 주는 경합도 만들지 않는다."""
    module = _load()
    samples = _series(duration=28800.0, efficiency=(780.0, 770.0), utilization=(0.90, 0.66), load1=-1.0)
    verdict = _verdict(module, samples)
    assert verdict["throughput_criterion"] == "not_applicable", verdict["throughput_criterion_basis"]
    assert "부하 계기를 못 읽었다" in verdict["throughput_criterion_basis"]


def test_decomposition_identity_holds():
    """`벽시계 비율 = 효율 비율 × 이용률 비율` — 리포트가 세 값을 다 싣고, 그 곱이 맞아야 한다."""
    module = _load()
    for efficiency, utilization in (((780.0, 570.0), 0.72), ((780.0, 780.0), (0.90, 0.65))):
        verdict = _verdict(module, _series(duration=28800.0, efficiency=efficiency, utilization=utilization))
        assert verdict["throughput_identity_gap"] <= 0.002, verdict


# ── ③ RSS 축과의 독립성(네 조합) ──────────────────────────────────────────────


def test_slow_and_leaking_are_judged_separately():
    """네 조합이 각각 다르게 판정돼야 한다 — 한 축이 다른 축을 대신하지 못한다."""
    module = _load()
    flat = _series(duration=28800.0, efficiency=(780.0, 780.0), utilization=0.72)
    decayed = _series(duration=28800.0, efficiency=(780.0, 570.0), utilization=0.72)
    # RSS 시리즈는 **같은 모양**(표본 수·시각·반복 수)에 증가분만 다르게 준다:
    #   40 MB(기준 64 MB 안) vs 1,683 MB(실측 누수 실행). 반복 수는 8시간 규모(≈860만)로 맞춘다.
    count = 288
    times = [i * 100.0 for i in range(count)]
    ops = [i * 30000 for i in range(count)]
    rss_clean = [100.0 + 40.0 * i / (count - 1) for i in range(count)]
    rss_leaking = [100.0 + 1683.5 * i / (count - 1) for i in range(count)]

    def rss(series: list[float]) -> str:
        return module.sc6_rss_criterion([round(v, 1) for v in series], ops, times, 28800.0)["rss_criterion"]

    fast, slow = _verdict(module, flat)["throughput_criterion"], _verdict(module, decayed)["throughput_criterion"]
    clean, leaky = rss(rss_clean), rss(rss_leaking)
    assert (fast, clean) == ("pass", "pass"), (fast, clean)
    assert (slow, leaky) == ("fail", "fail"), (slow, leaky)
    matrix = {(fast, leaky), (slow, clean)}
    assert matrix == {("pass", "fail"), ("fail", "pass")}, matrix


# ── ④ 판정 불가 경계 ────────────────────────────────────────────────────────


def test_short_rehearsal_is_not_applicable_not_a_pass():
    module = _load()
    samples = _series(duration=60.0, efficiency=(50.0, 40.0), utilization=0.9, step=1.0)
    verdict = _verdict(module, samples)
    assert verdict["throughput_criterion"] == "not_applicable", verdict["throughput_criterion_basis"]
    assert "최소 7200s" in verdict["throughput_criterion_basis"]


def test_missing_cpu_series_does_not_crash_or_pass():
    """옛 리포트 모양(CPU 표본 없음)이 들어와도 예외 없이 판정 불가로 끝난다."""
    module = _load()
    verdict = module.throughput_criterion([0, 10, 20, 30], [0.0, 60.0, 120.0, 180.0], [], [], CPU_COUNT, 28800.0)
    assert verdict["throughput_criterion"] == "not_applicable"
    assert verdict["throughput_blocks"] == 0


# ── ⑤ 실측 픽스처: 오늘의 그 실행을 빨갛게 만들지 않는가 ─────────────────────────


def test_real_fourth_run_is_not_called_a_product_regression():
    """4차 실행(실측 표본 288개)의 벽시계는 -26.5% 였다 — 이 게이트가 ‘제품 회귀’로 단정하면 실패다.

    실측 그대로(부하 미기록)는 **판정 불가**로 끝나야 하고(재실행 요구), 실제로 경합이었음을
    부하로 표시하면 **경합으로 귀속**돼야 한다. 두 경우 모두 ‘제품 회귀’는 아니다.
    """
    module = _load()
    data = json.loads(_fixture_path().read_text(encoding="utf-8"))
    rows = data["samples"]
    ops = [row[1] for row in rows]
    times = [row[0] for row in rows]
    cpu = [row[2] for row in rows]
    duration = times[-1]

    unknown = module.throughput_criterion(ops, times, cpu, [-1.0] * len(rows), CPU_COUNT, duration)
    assert unknown["throughput_criterion"] == "not_applicable", unknown["throughput_criterion_basis"]
    assert unknown["throughput_wall_ratio"] < 0.85, unknown  # 벽시계 감소는 실재한다(실측 -26.5%)
    assert unknown["throughput_efficiency_ratio"] > 0.90, unknown  # 그러나 효율은 5% 안쪽

    contended = module.throughput_criterion(ops, times, cpu, [6.0] * len(rows), CPU_COUNT, duration)
    assert contended["throughput_criterion"] == "not_applicable", contended["throughput_criterion_basis"]
    assert "제품 회귀 아님" in contended["throughput_criterion_basis"]


def test_report_carries_everything_needed_to_reproduce_the_verdict():
    """블록 삼중항·창·부하가 리포트에 실려, 다음 사람이 리포트만으로 같은 판정을 다시 낸다."""
    module = _load()
    verdict = _verdict(module, _series(duration=28800.0, efficiency=(780.0, 570.0), utilization=0.72))
    blocks = len(verdict["throughput_blocks_wall"])
    assert blocks == len(verdict["throughput_blocks_efficiency"]) == len(verdict["throughput_blocks_utilization"])
    assert blocks >= 12, verdict
    assert verdict["throughput_block_s"] >= module.THROUGHPUT_BLOCK_MIN_S
    assert verdict["throughput_max_decline"] == module.THROUGHPUT_MAX_DECLINE


def test_unjudgeable_is_not_a_pass_on_a_full_length_run():
    """8시간 실행이 `not_applicable` 로 끝나면 **통과가 아니다** — 종전 `!= "fail"` 규칙의 구멍이다.

    실측(2026-09-17 스모그): 60초 실행이 두 축 다 `not_applicable` 인데 시나리오 `pass` 가 True 였다.
    리허설은 그래야 하지만(안 그러면 아무도 빨간불을 안 본다) 8시간 실행이 그러면 게이트가 비워진다.
    """
    module = _load()
    unjudgeable = {"rss_criterion": "not_applicable", "rss_warmup_window_s": 1440.0}
    throughput_unjudgeable = {"throughput_criterion": "not_applicable", "throughput_criterion_basis": "경합"}
    ok, why = module.criteria_gate(unjudgeable, throughput_unjudgeable, 28800.0)
    assert ok is False and "판정 불가를 통과로 취급하지 않는다" in why, why

    rehearsal_ok, rehearsal_why = module.criteria_gate(unjudgeable, throughput_unjudgeable, 60.0)
    assert rehearsal_ok is True, rehearsal_why

    failed = {"rss_criterion": "pass", "rss_warmup_window_s": 1440.0}
    tp_failed = {"throughput_criterion": "fail", "throughput_criterion_basis": "제품 회귀"}
    ok_fail, why_fail = module.criteria_gate(failed, tp_failed, 28800.0)
    assert ok_fail is False and "처리량 축 실패" in why_fail, why_fail


def test_scenario_pass_rule_requires_both_axes():
    """시나리오 통과 조건은 두 축을 **모두** 요구한다 — 한 축의 not_applicable 도 통과가 아니다."""
    source = _tool_path().read_text(encoding="utf-8")
    assert "and criteria_ok" in source, "시나리오 통과가 두 축의 게이트를 거치지 않는다"
    assert '"criteria_gate": criteria_why,' in source, "왜 통과/실패인지가 리포트에 없다"
    assert "**throughput_verdict," in source, "처리량 판정이 리포트에 실리지 않는다"


# ── ⑭~ 귀속 사다리: 게이트가 빨간 실행에서 “어느 호출이 느려졌나”를 좁힌다 ─────────────────────
#
# 픽스처 규약: 국면 단가(µs/반복)를 첫 분기→끝 분기 선형으로 움직인다. 이 추정량은 **분기 중앙값**을
# 쓰므로 선형 궤적에서 측정값은 궤적의 12.5% / 87.5% 지점에 앉는다 — 즉 **측정 증가분 = 주입 증가분의 75%** 다.
# 그래서 단언은 주입값의 75% 를 기대값으로 삼는다(추정량의 성질을 시험이 밝힌다 — 숨기지 않는다).

LADDER_PHASES = ("task.create", "task.transition", "conversation.append")


def _ladder_series(
    phase_units_us: dict[str, tuple[float, float]],
    *,
    total_units_us: tuple[float, float],
    duration: float = 28800.0,
    ops_per_s: float = 100.0,
    every: int = 500,
    sample_every: int = 50,
) -> tuple[list[list[float]], list[int], list[float], list[int], list[float], list[float]]:
    """국면별 누적 CPU 계열과 전체 누적 CPU 계열을 만든다(단위: 초 · 단가는 µs/반복).

    `total_units_us` 를 국면 합과 **다르게** 두면 “국면 밖” 잔차를 만들 수 있다 — 그게 사다리의
    세 번째 칸(`outside_phases`)을 겨누는 방법이다.
    """
    names = list(phase_units_us)
    total_ops = int(ops_per_s * duration)

    def _advance(fraction_from: float, fraction_to: float, count: int, pair: tuple[float, float]) -> float:
        first, last = pair
        start = first + (last - first) * fraction_from
        end = first + (last - first) * fraction_to
        return (start + end) / 2 * count * 1e-6

    phase_acc = [0.0] * len(names)
    total_acc = 0.0
    attribution_rows: list[list[float]] = [[] for _ in names]
    attribution_ops: list[int] = []
    attribution_times: list[float] = []
    sample_ops: list[int] = []
    sample_times: list[float] = []
    sample_cpu: list[float] = []
    n = 0
    while n < total_ops:
        count = min(sample_every, total_ops - n)
        frac0, frac1 = n / total_ops, (n + count) / total_ops
        total_acc += _advance(frac0, frac1, count, total_units_us)
        for index, name in enumerate(names):
            phase_acc[index] += _advance(frac0, frac1, count, phase_units_us[name])
        n += count
        if n % every == 0 or n == total_ops:
            attribution_ops.append(n)
            attribution_times.append(n / ops_per_s)
            for index in range(len(names)):
                attribution_rows[index].append(round(phase_acc[index], 3))
        sample_ops.append(n)
        sample_times.append(round(n / ops_per_s, 3))
        sample_cpu.append(round(total_acc, 3))
    return attribution_rows, attribution_ops, attribution_times, sample_ops, sample_times, sample_cpu


def _ladder(
    module: ModuleType, *, gate: str = "fail", duration: float = 28800.0, **series_kwargs: Any
) -> dict[str, Any]:
    """사다리를 돌린다 — 게이트 판정은 **인자로 주어진 것**을 쓴다(사다리는 판정을 만들지 않는다)."""
    rows, ops, times, s_ops, s_times, s_cpu = _ladder_series(**series_kwargs, duration=duration)
    verdict = {
        "throughput_criterion": gate,
        "throughput_criterion_basis": "합성 판정(시험용)",
        "throughput_efficiency_ratio": 0.73,
    }
    return module.throughput_attribution(LADDER_PHASES, rows, ops, times, s_ops, s_times, s_cpu, verdict, duration)


def test_ladder_names_the_phase_that_slowed_down():
    """한 국면만 느려지면 **그 이름을 지목**한다 — 그리고 그 몫이 증가분의 대부분임을 밝힌다."""
    verdict = _ladder(
        _load(),
        phase_units_us={
            "task.create": (400.0, 400.0),
            "task.transition": (400.0, 400.0),
            "conversation.append": (600.0, 1800.0),
        },
        total_units_us=(1400.0, 2600.0),
    )
    assert verdict["attribution_criterion"] == "phase", verdict["attribution_criterion_basis"]
    assert verdict["attribution_phase"] == "conversation.append"
    assert verdict["attribution_top_share"] >= 0.9, verdict
    measured = verdict["attribution_contributions_us_per_op"]["conversation.append"]
    # 분기 중앙값은 선형 궤적의 12.5%/87.5% 에 앉아 **주입 증가분의 75%** 를 본다. 워밍업 창이 앞을
    # 잘라내므로 실제로는 **약 72%** 다(실측 870/1200) — 그래서 70~80% 를 기대값으로 삼는다.
    assert 0.70 * 1200.0 <= measured <= 0.80 * 1200.0, f"주입 +1200 µs/반복의 70~80% 안이어야 한다(측정 {measured})"
    assert "conversation.append" in verdict["attribution_next_step"]


def test_ladder_refuses_to_invent_a_culprit_when_the_growth_is_noise():
    """게이트는 효율 임계로 빨개졌는데 이 실행의 단가 증가가 잡음 수준이면 **아무도 지목하지 않는다**."""
    verdict = _ladder(
        _load(),
        phase_units_us={
            "task.create": (400.0, 401.0),
            "task.transition": (400.0, 400.5),
            "conversation.append": (600.0, 601.0),
        },
        total_units_us=(1400.0, 1402.5),
    )
    assert verdict["attribution_criterion"] == "insufficient", verdict["attribution_criterion_basis"]
    assert verdict["attribution_phase"] is None
    assert "없는 범인을 지목하지 않는다" in verdict["attribution_criterion_basis"]


def test_ladder_says_outside_phases_when_phases_do_not_explain_the_growth():
    """국면은 그대로인데 전체 CPU 가 늘면 **“계측 밖”**이라 말한다(할당자·GC·루프 자체).

    이 칸이 이 설계의 요점이다: 국면 합을 총량으로 쓰면 잔차가 정의상 0 이 되어 이 판정이 영영 안 난다.
    """
    verdict = _ladder(
        _load(),
        phase_units_us={
            "task.create": (400.0, 400.0),
            "task.transition": (400.0, 400.0),
            "conversation.append": (600.0, 600.0),
        },
        total_units_us=(1400.0, 2200.0),
    )
    assert verdict["attribution_criterion"] == "outside_phases", verdict["attribution_criterion_basis"]
    assert verdict["attribution_gap_ratio"] > 0.5, verdict
    assert "프로세스 전체" in verdict["attribution_next_step"]


def test_ladder_says_spread_when_no_phase_dominates():
    """증가가 여러 국면에 퍼졌으면 하나를 범인으로 만들지 않는다(공통 경로를 보라고 말한다)."""
    verdict = _ladder(
        _load(),
        phase_units_us={
            "task.create": (400.0, 800.0),
            "task.transition": (500.0, 900.0),
            "conversation.append": (500.0, 900.0),
        },
        total_units_us=(1400.0, 2600.0),
    )
    assert verdict["attribution_criterion"] == "spread", verdict["attribution_criterion_basis"]
    assert verdict["attribution_top_share"] < 0.5, verdict
    assert "고르게 늘었다" in verdict["attribution_criterion_basis"]


def test_ladder_reports_a_phase_that_got_faster_without_blaming_it():
    """빨라진 국면은 **음수 기여**로 남고 범인으로 지목되지 않는다(빠른 것과 느린 것을 가른다)."""
    verdict = _ladder(
        _load(),
        phase_units_us={
            "task.create": (400.0, 400.0),
            "task.transition": (900.0, 600.0),
            "conversation.append": (600.0, 1800.0),
        },
        total_units_us=(1900.0, 2800.0),
    )
    assert verdict["attribution_criterion"] == "phase"
    assert verdict["attribution_phase"] == "conversation.append"
    assert verdict["attribution_speedups_us_per_op"]["task.transition"] < -150.0, verdict
    assert "task.transition" not in verdict["attribution_phase"]


def test_ladder_does_not_run_on_a_green_gate():
    """초록 실행에는 사다리가 돌지 않는다 — 귀속은 빨간 판정의 **설명**이지 별도 판정이 아니다."""
    verdict = _ladder(
        _load(),
        gate="pass",
        phase_units_us={
            "task.create": (400.0, 800.0),
            "task.transition": (400.0, 800.0),
            "conversation.append": (600.0, 1200.0),
        },
        total_units_us=(1400.0, 2800.0),
    )
    assert verdict["attribution_criterion"] == "not_applicable", verdict
    assert "빨간색이 아니다" in verdict["attribution_criterion_basis"]
    assert verdict["attribution_units_us_per_op"] == {}


def test_ladder_does_not_run_on_a_short_run():
    """60초 리허설에서는 국면 단가의 분기를 말할 수 없다 — 판정 불가를 이유와 함께 낸다."""
    verdict = _ladder(
        _load(),
        duration=60.0,
        phase_units_us={
            "task.create": (400.0, 400.0),
            "task.transition": (400.0, 400.0),
            "conversation.append": (600.0, 1800.0),
        },
        total_units_us=(1400.0, 2600.0),
    )
    assert verdict["attribution_criterion"] == "not_applicable"
    assert "최소 7200s" in verdict["attribution_criterion_basis"]


def test_ladder_decomposition_is_an_identity_and_reproducible_from_the_report():
    """쪼갠 합 = 국면 합 · 잔차 = 총합 − 쪼갠 합 — 그리고 **리포트만으로** 다시 계산된다."""
    verdict = _ladder(
        _load(),
        phase_units_us={
            "task.create": (400.0, 600.0),
            "task.transition": (400.0, 700.0),
            "conversation.append": (600.0, 1500.0),
        },
        total_units_us=(1400.0, 2900.0),
    )
    contributions = verdict["attribution_contributions_us_per_op"]
    units = verdict["attribution_units_us_per_op"]
    for name in LADDER_PHASES:
        first, last = units[name]
        assert abs((last - first) - contributions[name]) < 0.05, (name, units[name], contributions[name])
    attributed = round(sum(contributions.values()), 3)
    total_first, total_last = verdict["attribution_total_us_per_op"]
    assert abs(attributed - verdict["attribution_attributed_delta_us_per_op"]) < 1e-6
    assert abs((total_last - total_first) - verdict["attribution_total_delta_us_per_op"]) < 0.05
    assert (
        abs(verdict["attribution_gap_us_per_op"] - (verdict["attribution_total_delta_us_per_op"] - attributed)) < 0.05
    )
    assert verdict["attribution_blocks"] >= 12, verdict


def test_ladder_refuses_to_judge_when_the_two_series_do_not_align():
    """국면 계열과 전체 계열의 블록이 겹치지 않으면 **판정하지 않고 이유를 밝힌다**(빈손으로 지목하지 않는다)."""
    module = _load()
    rows, ops, times, s_ops, s_times, s_cpu = _ladder_series(
        {name: (400.0, 800.0) for name in LADDER_PHASES},
        total_units_us=(1200.0, 2400.0),
        every=700_000,  # 스냅샷 네 번 → 블록이 2개뿐이라 분기를 만들 수 없다
    )
    verdict = module.throughput_attribution(
        LADDER_PHASES,
        rows,
        ops,
        times,
        s_ops,
        s_times,
        s_cpu,
        {"throughput_criterion": "fail", "throughput_criterion_basis": "합성", "throughput_efficiency_ratio": 0.73},
        28800.0,
    )
    assert verdict["attribution_criterion"] == "insufficient", verdict["attribution_criterion_basis"]
    assert "NX10_ATTRIBUTION_SAMPLE_EVERY" in verdict["attribution_next_step"]

    ragged = module.throughput_attribution(
        LADDER_PHASES,
        [rows[0], rows[1], rows[2][:-3]],  # 국면 하나만 짧다
        ops,
        times,
        s_ops,
        s_times,
        s_cpu,
        {"throughput_criterion": "fail", "throughput_criterion_basis": "합성", "throughput_efficiency_ratio": 0.73},
        28800.0,
    )
    assert ragged["attribution_criterion"] == "insufficient"
    assert "표본 수가 맞지 않는다" in ragged["attribution_criterion_basis"]


def test_ladder_is_wired_into_the_soak_scenario():
    """배선 이빨: 하네스가 국면 경계를 실제로 적립하고, 판정을 리포트에 싣고, 임계를 남긴다."""
    source = _tool_path().read_text(encoding="utf-8")
    assert 'SOAK_PHASES: tuple[str, ...] = ("task.create", "task.transition", "conversation.append")' in source
    for index in range(3):
        assert f"_lap({index})" in source, f"국면 {index} 의 경계 적립이 없다"
    assert "**attribution_verdict," in source, "귀속 판정이 리포트에 실리지 않는다"
    assert '"attribution_sample_every": ATTRIBUTION_SAMPLE_EVERY,' in source, "임계가 리포트에 없다"
    assert "if i % ATTRIBUTION_SAMPLE_EVERY == 0:" in source, "국면 스냅샷이 표본 주기 안에 없다"


# ── ㉔~ 사다리의 다음 칸: **지목된 국면 안**의 하위 단계(저널 append · view 재작성 · tail) ─────────
#
# 픽스처 규약: 프로파일러가 실어 주는 구조를 그대로 만든다(국면별 total/ops/windows/functions).
# 함수 표는 `self_us_per_op`(= self_s/ops) 순으로 읽는다. 계측기(하네스 파일) 프레임은 순위에서 빠진다.

HARNESS_FILE = "val02_staging.py"


def _profile(
    phase: str,
    *,
    windows: int = 8,
    ops: int = 100,
    total_s: float,
    functions: dict[str, tuple[float, float, int]],
    enabled: bool = True,
    extra_files: dict[str, str] | None = None,
    callers: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    """프로파일 dict 를 만든다 — `functions[key] = (self_s, cum_s, calls)` · `callers[key] = {호출자: 호출 수}`."""
    files = extra_files or {}
    return {
        "enabled": enabled,
        "profiled_calls": windows * 25,
        "windows": windows,
        "sample_every": 200,
        "window_calls": 25,
        "max_windows": 40,
        "max_ops": 1000,
        "phases": {
            phase: {
                "total_s": total_s,
                "ops": ops,
                "windows": windows,
                # 호출자 표(`cProfile`→`pstats` 가 만들어 주는 것) — 네 번째 칸의 입력이다.
                "callers": callers or {},
                "functions": {
                    key: {
                        "self_s": value[0],
                        "cum_s": value[1],
                        "calls": value[2],
                        "file": files.get(key, f"/repo/src/antigravity_k/engine/{key.split(':')[0]}"),
                        "line": 10,
                    }
                    for key, value in functions.items()
                },
            }
        },
    }


def _ladder_phase_dict(phase: str, *, unit_last: float) -> dict[str, Any]:
    return {
        "attribution_criterion": "phase",
        "attribution_phase": phase,
        "attribution_units_us_per_op": {phase: [unit_last - 200.0, unit_last]},
    }


def test_deep_rung_names_the_function_that_dominates_inside_the_phase():
    """국면 안에서 한 함수가 지배하면 **그 이름까지** 좁힌다 — 이것이 “다음 칸”의 목적이다."""
    module = _load()
    verdict = module.phase_function_attribution(
        "conversation.append",
        _profile(
            "conversation.append",
            total_s=800e-6 * 100,
            functions={
                "conversation_store.py:_persist": (560e-6 * 100, 700e-6 * 100, 100),
                "conversation_store.py:_journal_append": (80e-6 * 100, 90e-6 * 100, 100),
                "<built-in method posix.replace>": (60e-6 * 100, 60e-6 * 100, 100),
            },
        ),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        28800.0,
    )
    assert verdict["deep_criterion"] == "function", verdict["deep_criterion_basis"]
    assert verdict["deep_function"] == "conversation_store.py:_persist"
    assert verdict["deep_function_share"] >= 0.5, verdict
    assert "_persist" in verdict["deep_next_step"]


def test_deep_rung_says_spread_inside_the_phase_when_nothing_dominates():
    """국면 안에 고르게 퍼졌으면 함수 하나를 범인으로 만들지 않는다(그 안에서 더 쪼갤 근거가 없다)."""
    module = _load()
    verdict = module.phase_function_attribution(
        "conversation.append",
        _profile(
            "conversation.append",
            total_s=800e-6 * 100,
            functions={
                "conversation_store.py:_persist": (200e-6 * 100, 300e-6 * 100, 100),
                "conversation_store.py:tail": (200e-6 * 100, 210e-6 * 100, 100),
                "conversation_store.py:_journal_append": (200e-6 * 100, 205e-6 * 100, 100),
            },
        ),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        28800.0,
    )
    assert verdict["deep_criterion"] == "spread_within_phase", verdict["deep_criterion_basis"]
    assert verdict["deep_function_share"] < 0.5, verdict
    assert "범인으로 만들 근거가 없다" in verdict["deep_next_step"]


def test_deep_rung_says_outside_functions_when_python_cannot_see_the_cost():
    """파이썬 프로파일러가 못 보는 몫(C 확장·커널)이 크면 **“파이썬 밖”**이라 말한다(지어내지 않는다)."""
    module = _load()
    verdict = module.phase_function_attribution(
        "conversation.append",
        _profile(
            "conversation.append",
            total_s=200e-6 * 100,  # 국면 단가 800 µs 중 파이썬이 본 것은 200 µs
            functions={"conversation_store.py:_persist": (150e-6 * 100, 190e-6 * 100, 100)},
        ),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        28800.0,
    )
    assert verdict["deep_criterion"] == "outside_functions", verdict["deep_criterion_basis"]
    assert verdict["deep_residual_ratio"] > 0.5, verdict
    assert "fsync" in verdict["deep_next_step"] or "syscall" in verdict["deep_next_step"]


def test_deep_rung_excludes_the_instrument_from_the_ranking_and_reports_it():
    """계측기 자신(하네스 파일)의 프레임은 순위에서 빼고, 뺀 몫은 **밝힌다**.

    실측 근거: 프로브 첫 회차가 첫 칸을 `val02_staging.py:<lambda>` 로 지목했다 — 사다리가 자기 자신을
    가리키는 부류다. 빼되 숨기지 않는다(`deep_instrument_us_per_op`).
    """
    module = _load()
    verdict = module.phase_function_attribution(
        "task.create",
        _profile(
            "task.create",
            total_s=600e-6 * 100,
            functions={
                f"{HARNESS_FILE}:<lambda>": (400e-6 * 100, 600e-6 * 100, 100),
                "task_state_store.py:create_task": (150e-6 * 100, 590e-6 * 100, 100),
            },
            extra_files={f"{HARNESS_FILE}:<lambda>": f"/repo/docs/qa/2026-09-16-followup/nx10/perf/{HARNESS_FILE}"},
        ),
        _ladder_phase_dict("task.create", unit_last=600.0),
        28800.0,
    )
    assert verdict["deep_function"] == "task_state_store.py:create_task", verdict
    assert verdict["deep_excluded_functions"] == 1, verdict
    assert verdict["deep_instrument_us_per_op"] > 0, verdict
    assert verdict["deep_product_us_per_op"] == round(
        verdict["deep_total_us_per_op"] - verdict["deep_instrument_us_per_op"], 3
    )
    assert HARNESS_FILE not in verdict["deep_function"]


def test_deep_rung_explains_a_negative_residual_as_instrument_overhead():
    """오버헤드가 국면 시간을 부풀려 잔차가 음수면 **그렇게 말한다**(“파이썬 밖이 마이너스”라고 하지 않는다)."""
    module = _load()
    verdict = module.phase_function_attribution(
        "conversation.append",
        _profile(
            "conversation.append",
            total_s=1200e-6 * 100,  # 계측 때문에 오히려 커졌다(실측 오버헤드 비율 1.50)
            functions={"conversation_store.py:_persist": (900e-6 * 100, 1100e-6 * 100, 100)},
        ),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        28800.0,
    )
    assert verdict["deep_residual_us_per_op"] < 0, verdict
    assert verdict["deep_overhead_ratio"] > 1.0, verdict
    assert "deep_residual_note" in verdict and "오버헤드" in verdict["deep_residual_note"]
    assert verdict["deep_criterion"] != "outside_functions"


def test_deep_rung_does_not_run_when_the_first_rung_named_no_phase():
    """앞칸이 국면을 지목하지 않았으면 **함수 순위를 말하지 않는다**(빈손으로 지목하지 않는다)."""
    module = _load()
    for state in ("insufficient", "not_applicable", "spread", "outside_phases"):
        verdict = module.phase_function_attribution(
            None if state != "spread" else "conversation.append",
            _profile(
                "conversation.append", total_s=800e-6 * 100, functions={"a.py:f": (800e-6 * 100, 800e-6 * 100, 1)}
            ),
            {"attribution_criterion": state, "attribution_units_us_per_op": {"conversation.append": [600.0, 800.0]}},
            28800.0,
        )
        assert verdict["deep_criterion"] == "not_applicable", (state, verdict["deep_criterion_basis"])
        assert verdict["deep_functions_top"] == []


def test_deep_rung_does_not_run_on_a_short_run():
    module = _load()
    verdict = module.phase_function_attribution(
        "conversation.append",
        _profile("conversation.append", total_s=800e-6 * 100, functions={"a.py:f": (800e-6 * 100, 800e-6 * 100, 1)}),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        60.0,
    )
    assert verdict["deep_criterion"] == "not_applicable"
    assert "최소 7200s" in verdict["deep_criterion_basis"]


def test_deep_rung_refuses_to_rank_when_windows_are_too_few():
    module = _load()
    verdict = module.phase_function_attribution(
        "conversation.append",
        _profile(
            "conversation.append",
            windows=1,
            total_s=800e-6 * 100,
            functions={"a.py:f": (800e-6 * 100, 800e-6 * 100, 100)},
        ),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        28800.0,
    )
    assert verdict["deep_criterion"] == "insufficient", verdict["deep_criterion_basis"]
    assert "NX10_DEEP_SAMPLE_EVERY" in verdict["deep_next_step"]

    disabled = module.phase_function_attribution(
        "conversation.append",
        _profile("conversation.append", total_s=800e-6 * 100, functions={}, enabled=False),
        _ladder_phase_dict("conversation.append", unit_last=800.0),
        28800.0,
    )
    assert disabled["deep_criterion"] == "not_applicable"
    assert "판정은 그대로 유효하다" in disabled["deep_next_step"]


def test_deep_rung_is_reproducible_from_the_report():
    """리포트 값만으로 같은 순위·같은 몫·같은 잔차를 다시 낸다(반올림 뒤 값으로도)."""
    module = _load()
    verdict = module.phase_function_attribution(
        "task.transition",
        _profile(
            "task.transition",
            total_s=1000e-6 * 100,
            functions={
                "task_state_store.py:transition": (300e-6 * 100, 900e-6 * 100, 200),
                "<method 'commit' of 'sqlite3.Connection' objects>": (250e-6 * 100, 250e-6 * 100, 100),
            },
        ),
        _ladder_phase_dict("task.transition", unit_last=1000.0),
        28800.0,
    )
    top = verdict["deep_functions_top"][0]
    assert top["function"] == "task_state_store.py:transition"
    share = round(top["self_us_per_op"] / verdict["deep_total_us_per_op"], 4)
    assert abs(share - verdict["deep_function_share"]) < 1e-3, (share, verdict["deep_function_share"])
    assert (
        abs(
            (verdict["deep_phase_unit_us_per_op"] - verdict["deep_product_us_per_op"])
            - verdict["deep_residual_us_per_op"]
        )
        < 0.05
    )
    assert verdict["deep_sample_every"] == module.DEEP_SAMPLE_EVERY
    assert verdict["deep_function_dominance"] == module.DEEP_FUNCTION_DOMINANCE


def _drive_profiler(module: ModuleType, profiler: Any, iterations: int = 4000) -> dict[str, Any]:
    """실제 반복 모양(create 1 · transition 2 · append 1)으로 계측기를 돌린다."""
    per_iteration = ((0, 1), (1, 1), (1, 2), (2, 0))  # (국면 인덱스, 반복 내 순번) — 전이는 두 번 부른다
    for index in range(1, iterations):
        profiler.take(index)
        for phase_index, _order in per_iteration:
            phase = module.SOAK_PHASES[phase_index]
            if profiler.active_for(phase):
                profiler.enable()
                profiler.disable()
    return profiler.report()


def test_phase_profiler_windows_are_integrating_and_reach_every_phase():
    """계측기 자체의 계약: 창이 **정확히** 국면을 돌려 가며 닫히고, 유령 창이 없다.

    이 시험이 실제 결함을 겨눈다: 전이는 반복당 2회 호출되므로 창이 그 반복의 첫 호출에서 닫힌 뒤 둘째
    호출까지 계측하면 창이 **두 번 닫혀** 유령 창이 생기고(창 수가 부풀고 국면 회전이 어긋나) 세 번째
    국면이 영영 안 돌아간다 — 프로브가 실측으로 그렸고(14/26/0), 지금은 `active_for` 가 막는다.
    """
    module = _load()
    report = _drive_profiler(module, module._PhaseProfiler(module.SOAK_PHASES))
    closed = sum(bucket["windows"] for bucket in report["phases"].values())
    assert closed == report["windows"], (closed, report["windows"])
    assert report["windows"] <= module.DEEP_MAX_WINDOWS, report
    assert report["profiled_calls"] <= module.DEEP_MAX_OPS, report
    for name, bucket in report["phases"].items():
        assert bucket["windows"] >= 3, (name, bucket["windows"])  # 세 국면이 모두 돌아간다
        assert bucket["total_s"] > 0, (name, bucket)
    # 유령 창이 없으면 **창 수 × 창 크기 = 계측 호출 수**(마지막 창이 안 닫힌 만큼만 차이가 난다).
    # 유령 창은 계측 호출 없이 창을 닫으므로 이 항등식이 깨진다(음성 대조군이 그걸 겨눈다).
    gap = report["profiled_calls"] - report["windows"] * module.DEEP_WINDOW_CALLS
    assert 0 <= gap < module.DEEP_WINDOW_CALLS, (gap, report["profiled_calls"], report["windows"])


def test_phase_profiler_ghost_windows_negative_control():
    """음성 대조군: 옛 규칙(닫힌 뒤의 꼬리 호출도 계측)을 재현하면 위 불변식이 **깨진다**.

    두 가드를 **모두** 무력화해야 결함이 재현된다(한쪽만 풀면 다른 쪽이 막는다) — 그래도 막히면
    시험이 무엇을 지키는지 알 수 없다. 실측 대조: 창 수가 **40 → 3,776** 으로 부풀고(계측 호출은 3,800),
    세 번째 국면이 사라진다 — 옛 코드에서 실제로 관찰된 14/26/0 과 같은 모양이다.
    """
    module = _load()

    class Lenient(module._PhaseProfiler):  # type: ignore[misc]
        def active_for(self, phase: str) -> bool:  # 닫힌 뒤에도 계측한다
            return self._phase == phase

        def disable(self) -> None:  # 창이 닫혀도 다시 닫는다(유령 창)
            self._profiler.disable()
            self._cpu_s += time.process_time() - self._call_t0
            self.profiled_calls += 1
            self._calls_left -= 1
            if self._calls_left > 0:
                return
            bucket = self.per_phase[self._phase or ""]
            bucket["total_s"] += self._cpu_s
            bucket["ops"] += self._window_ops
            bucket["windows"] += 1
            self.windows.append({"phase": self._phase, "ops": self._window_ops, "cpu_s": self._cpu_s})
            self._profiler = cProfile.Profile()

    lenient = _drive_profiler(module, Lenient(module.SOAK_PHASES))
    honest = _drive_profiler(module, module._PhaseProfiler(module.SOAK_PHASES))
    assert lenient["windows"] > honest["windows"] * 10, (lenient["windows"], honest["windows"])
    # 유령 창의 지문: 창 수 × 창 크기가 계측 호출 수를 **훨씬 넘는다**(호출 없이 열린 창).
    ghost_gap = lenient["windows"] * module.DEEP_WINDOW_CALLS - lenient["profiled_calls"]
    assert ghost_gap > lenient["profiled_calls"], (ghost_gap, lenient["profiled_calls"], lenient["windows"])
    honest_gap = honest["windows"] * module.DEEP_WINDOW_CALLS - honest["profiled_calls"]
    assert honest_gap <= 0, (honest_gap, honest["profiled_calls"], honest["windows"])


def test_deep_rung_is_wired_and_the_profiled_iterations_are_excluded_from_the_ladder_series():
    """배선 이빨: 창 계측이 실제로 걸리고, **계측한 반복은 판정 계열에서 빠진다**(오염 금지)."""
    source = _tool_path().read_text(encoding="utf-8")
    assert "profiler = _PhaseProfiler(SOAK_PHASES)" in source, "하네스가 계측기를 만들지 않는다"
    assert "_deep_phase[0] = profiler.take(i)" in source, "반복마다 계측 국면을 정하지 않는다"
    assert "if not profiler.active_for(phase):" in source, "창 밖 호출을 거르지 않는다(유령 창 위험)"
    assert "attribution_measured_ops += 1" in source, "계측된 반복 수를 세지 않는다"
    assert "if _deep_phase[0] == SOAK_PHASES[index]:" in source, "계측 국면을 판정 계열에서 빼지 않는다"
    assert "deep_verdict = phase_function_attribution(" in source, "다음 칸이 하네스에 연결되지 않았다"
    assert "path_verdict = function_call_path(deep_verdict, deep_profile, actual_duration)" in source, (
        "네 번째 칸이 하네스에 연결되지 않았다"
    )
    assert "deep_profile = profiler.report()" in source, "프로파일 원자료를 만들지 않는다"
    assert '"deep_profile": deep_profile,' in source, "프로파일 원자료가 리포트에 없다"
    assert "**path_verdict," in source, "네 번째 칸의 판정이 리포트에 실리지 않는다"
    assert '"deep_sample_every": DEEP_SAMPLE_EVERY,' in source, "임계가 리포트에 없다"


# ── ㊅~ 사다리의 **네 번째 칸**: 지목된 함수를 **누가·얼마나 자주** 부르는가 ─────────────────────────────
#
# 이 칸이 가르는 것: 같은 함수·같은 시간이라도 **반복당 1회**면 그 호출 자체를 싸게 만들어야 하고,
# **반복당 여러 번**이면 호출을 합쳐야 한다(코얼리싱). 같은 숫자가 다른 수술을 요구한다.


def _deep_function_dict(phase: str, function: str, *, share: float = 0.7) -> dict[str, Any]:
    """앞칸(국면 내부)이 **함수를 지목한** 판정을 만든다 — 네 번째 칸의 입력이다."""
    return {
        "deep_criterion": "function",
        "deep_phase": phase,
        "deep_function": function,
        "deep_function_share": share,
    }


def test_call_path_names_the_dominant_caller():
    """지목된 함수를 **누가** 부르는지까지 좁힌다 — 이것이 네 번째 칸의 목적이다."""
    module = _load()
    verdict = module.function_call_path(
        _deep_function_dict("conversation.append", "<built-in method posix.fsync>"),
        _profile(
            "conversation.append",
            total_s=900e-6 * 100,
            functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 100)},
            callers={"<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 100}},
        ),
        28800.0,
    )
    assert verdict["path_criterion"] == "path", verdict["path_criterion_basis"]
    assert verdict["path_caller"] == "conversation_store.py:_atomic_write"
    assert verdict["path_caller_share"] >= 0.5, verdict
    assert verdict["path_caller_is_instrument"] is False
    assert "_atomic_write" in verdict["path_next_step"]


def test_call_path_says_multi_path_when_several_callers_share_it():
    """여러 곳이 비슷하게 부르면 한 곳을 범인으로 만들지 않는다 — 공통 함수 자체를 싸게 만드는 방향."""
    module = _load()
    verdict = module.function_call_path(
        _deep_function_dict("conversation.append", "conversation_store.py:_persist"),
        _profile(
            "conversation.append",
            total_s=900e-6 * 100,
            functions={"conversation_store.py:_persist": (500e-6 * 100, 900e-6 * 100, 100)},
            callers={
                "conversation_store.py:_persist": {
                    "conversation_store.py:append": 40,
                    "conversation_store.py:_seal": 35,
                    "conversation_store.py:reconcile": 25,
                }
            },
        ),
        28800.0,
    )
    assert verdict["path_criterion"] == "multi_path", verdict["path_criterion_basis"]
    assert verdict["path_caller_share"] < 0.5, verdict
    assert len(verdict["path_callers_top"]) == 3, verdict["path_callers_top"]
    assert "그 함수 자체" in verdict["path_next_step"]


def test_call_path_refuses_to_name_a_caller_when_the_table_is_incomplete():
    """기록된 호출자가 하나뿐인데 몫이 절반 미만이면 지목하지 않는다(트리밍된 나머지를 숨기지 않는다)."""
    module = _load()
    verdict = module.function_call_path(
        _deep_function_dict("task.transition", "task_state_store.py:transition"),
        _profile(
            "task.transition",
            total_s=900e-6 * 100,
            functions={"task_state_store.py:transition": (500e-6 * 100, 900e-6 * 100, 100)},
            callers={"task_state_store.py:transition": {"task_state_store.py:_cas": 20}},
        ),
        28800.0,
    )
    assert verdict["path_criterion"] == "insufficient", verdict["path_criterion_basis"]
    assert verdict["path_caller_share"] < 0.5, verdict
    assert "불완전" in verdict["path_criterion_basis"]


def test_call_path_refuses_to_rank_when_no_caller_is_recorded():
    """호출자 표가 비면(C 쪽에서만 불리거나 창이 모자라다) “없다”고 말한다 — 지어내지 않는다."""
    module = _load()
    verdict = module.function_call_path(
        _deep_function_dict("task.create", "task_state_store.py:create_task"),
        _profile(
            "task.create",
            total_s=600e-6 * 100,
            functions={"task_state_store.py:create_task": (600e-6 * 100, 600e-6 * 100, 100)},
        ),
        28800.0,
    )
    assert verdict["path_criterion"] == "insufficient", verdict["path_criterion_basis"]
    assert verdict["path_callers_top"] == [], verdict
    assert "호출자를 말할 표본이 없다" in verdict["path_criterion_basis"]


def test_call_path_does_not_run_when_the_previous_rung_named_no_function():
    """앞칸이 함수를 지목하지 않았으면(퍼졌다·파이썬 밖) 돌리지 않는다 — 경로는 지목된 함수에만 묻는다."""
    module = _load()
    for prior in ("spread_within_phase", "outside_functions", "insufficient"):
        verdict = module.function_call_path(
            {"deep_criterion": prior, "deep_phase": "conversation.append", "deep_function": None},
            _profile(
                "conversation.append",
                total_s=900e-6 * 100,
                functions={"conversation_store.py:_persist": (500e-6 * 100, 900e-6 * 100, 100)},
                callers={"conversation_store.py:_persist": {"conversation_store.py:append": 100}},
            ),
            28800.0,
        )
        assert verdict["path_criterion"] == "not_applicable", (prior, verdict)
        assert prior in verdict["path_criterion_basis"], verdict["path_criterion_basis"]
        assert "함수 미지목" in verdict["path_next_step"]


def test_call_path_splits_the_prescription_by_calls_per_iteration():
    """**얼마나 자주** 부르는가가 처방을 가른다: 반복당 1회 vs 3회는 다른 수술이다.

    실측 근거: `posix.fsync` 를 지목한 뒤 가장 먼저 물어야 하는 것이 이것이다 — 한 번이면 그 호출 자체를
    싸게(정책·배치), 여러 번이면 **호출을 합치는** 것이 맞다(코얼리싱).
    """
    module = _load()

    def once() -> dict[str, Any]:
        return module.function_call_path(
            _deep_function_dict("conversation.append", "<built-in method posix.fsync>"),
            _profile(
                "conversation.append",
                total_s=900e-6 * 100,
                ops=100,
                functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 100)},
                callers={"<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 100}},
            ),
            28800.0,
        )

    def thrice() -> dict[str, Any]:
        return module.function_call_path(
            _deep_function_dict("conversation.append", "<built-in method posix.fsync>"),
            _profile(
                "conversation.append",
                total_s=900e-6 * 100,
                ops=100,
                functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 300)},
                callers={"<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 300}},
            ),
            28800.0,
        )

    v1, v3 = once(), thrice()
    assert v1["path_calls_per_iteration"] == 1.0, v1
    assert v3["path_calls_per_iteration"] == 3.0, v3
    assert v1["path_frequency_class"] == "at_most_once_per_iteration", v1
    assert v3["path_frequency_class"] == "repeated_per_iteration", v3
    assert v1["path_frequency_note"] != v3["path_frequency_note"], "빈도가 달라졌는데 처방이 같다"
    assert "합치는" in v3["path_frequency_note"], v3["path_frequency_note"]
    assert "그 호출 자체의 비용" in v1["path_frequency_note"], v1["path_frequency_note"]
    # 경로 판정 자체는 같은 곳을 가리킨다(빈도는 별도 축이다 — 판정을 흔들지 않는다).
    assert v1["path_caller"] == v3["path_caller"] == "conversation_store.py:_atomic_write"
    assert v1["path_criterion"] == v3["path_criterion"] == "path"


def test_call_path_walks_upwards_through_the_product_chain():
    """호출 경로를 위로 걷는다 — 한 함수를 지목하고 끝나지 않는다(그 함수를 부른 곳까지)."""
    module = _load()
    verdict = module.function_call_path(
        _deep_function_dict("conversation.append", "<built-in method posix.fsync>"),
        _profile(
            "conversation.append",
            total_s=900e-6 * 100,
            functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 100)},
            callers={
                "<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 100},
                "conversation_store.py:_atomic_write": {"conversation_store.py:_persist": 100},
                "conversation_store.py:_persist": {
                    "conversation_store.py:append": 80,
                    "conversation_store.py:_seal": 20,
                },
            },
        ),
        28800.0,
    )
    assert verdict["path_chain"] == [
        "conversation_store.py:_atomic_write",
        "conversation_store.py:_persist",
        "conversation_store.py:append",
    ], verdict["path_chain"]
    assert verdict["path_max_depth"] == module.PATH_MAX_DEPTH


def test_call_path_marks_the_harness_as_the_entry_point():
    """**하네스가 직접 부르는 함수**는 “국면 진입점”이라 밝힌다 — 계측기를 범인으로 만들지 않는다.

    지목된 함수의 호출자가 하네스 루프면 제품 쪽에 고칠 곳이 없다는 뜻이다(대신 그 함수 자체를 싸게).
    상위 사슬을 걷을 때 계측기 프레임은 건너뛰고, 건너뛴 수를 밝힌다.
    """
    module = _load()
    verdict = module.function_call_path(
        _deep_function_dict("task.create", "task_state_store.py:create_task"),
        _profile(
            "task.create",
            total_s=600e-6 * 100,
            functions={"task_state_store.py:create_task": (600e-6 * 100, 600e-6 * 100, 100)},
            callers={
                "task_state_store.py:create_task": {
                    "val02_staging.py:<lambda>": 60,
                    "task_state_store.py:_seed": 40,
                },
                "task_state_store.py:_seed": {"task_state_store.py:initialize": 40},
            },
        ),
        28800.0,
    )
    assert verdict["path_criterion"] == "path", verdict["path_criterion_basis"]
    assert verdict["path_caller_is_instrument"] is True, verdict
    assert "국면 진입점" in verdict["path_criterion_basis"], verdict["path_criterion_basis"]
    assert "그 함수 자체" in verdict["path_next_step"], verdict["path_next_step"]
    # 사슬은 계측기를 **건너뛰고** 제품 프레임으로 이어진다(건너뛴 수를 밝힌다).
    assert verdict["path_chain"][0] == "task_state_store.py:_seed", verdict["path_chain"]
    assert verdict["path_instrument_frames_skipped"] == 1, verdict["path_instrument_frames_skipped"]


def test_call_path_is_reproducible_from_the_report():
    """리포트 값만으로 같은 경로·같은 몫·같은 빈도를 다시 낸다(반올림 뒤 값으로도)."""
    module = _load()
    profile = _profile(
        "conversation.append",
        total_s=900e-6 * 100,
        ops=100,
        functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 150)},
        callers={"<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 150}},
    )
    verdict = module.function_call_path(
        _deep_function_dict("conversation.append", "<built-in method posix.fsync>"), profile, 28800.0
    )
    replayed_profile = json.loads(json.dumps(profile))
    replayed = module.function_call_path(
        _deep_function_dict("conversation.append", "<built-in method posix.fsync>"), replayed_profile, 28800.0
    )
    assert replayed == verdict
    assert verdict["path_calls_per_iteration"] == 1.5, verdict
    assert verdict["path_callers_top"][0]["share"] == 1.0, verdict["path_callers_top"]


def test_call_path_does_not_run_on_a_short_run_or_with_instrumentation_off():
    """짧은 실행·계측 꺼짐에서는 경로를 말하지 않는다(사유를 남긴다) — 앞칸과 같은 규칙이다."""
    module = _load()
    profile = _profile(
        "conversation.append",
        total_s=900e-6 * 100,
        functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 100)},
        callers={"<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 100}},
    )
    short = module.function_call_path(
        _deep_function_dict("conversation.append", "<built-in method posix.fsync>"), profile, 60.0
    )
    assert short["path_criterion"] == "not_applicable", short
    assert "60s" in short["path_criterion_basis"]
    off = module.function_call_path(
        _deep_function_dict("conversation.append", "<built-in method posix.fsync>"),
        _profile(
            "conversation.append",
            total_s=900e-6 * 100,
            enabled=False,
            functions={"<built-in method posix.fsync>": (850e-6 * 100, 850e-6 * 100, 100)},
            callers={"<built-in method posix.fsync>": {"conversation_store.py:_atomic_write": 100}},
        ),
        28800.0,
    )
    assert off["path_criterion"] == "not_applicable", off
    assert "NX10_DEEP_PROFILE=0" in off["path_criterion_basis"]


# ── 네 번째 칸의 **자료원** 계약: cProfile 이 호출자 표를 만들려면 실제 호출이 있어야 한다 ──────────────
#
# 이 두 시험이 계측기를 직접 돌리는 이유: 배선을 합성 fixture 로만 고정하면 “상자 안에서는 참인데
# 바깥에서는 거짓”인 문장이 남는다. 실제로 여기서 하나를 밟았다 — `Profile.getstats()` 의 6번째 칸은
# **callees** 이고 호출자가 아니다(내장 함수는 `None`). 그걸 호출자로 읽으면 네 번째 칸은 영영 빈다.


def _probe_leaf() -> None:
    _probe_mid()


def _probe_mid() -> None:
    _probe_top()


def _probe_top() -> None:
    sum(range(20))


def _drive_profiler_with_work(module: ModuleType, profiler: Any, iterations: int = 20000) -> dict[str, Any]:
    """실제로 함수를 부르며 계측기를 돌린다 — 호출자 표를 만들려면 **진짜 호출**이 있어야 한다.

    반복 수가 큰 이유(실측으로 밟은 계약): 창은 `index % DEEP_SAMPLE_EVERY == 0` 인 반복에서만 **열린다**.
    그래서 창 상한 40개를 다 채우려면 반복 인덱스가 `40 × 200` 이상으로 흘러야 한다 — 1200 반복으로는
    열림 기회가 5번뿐이라 국면당 창이 2개로 끝나고 네 번째 칸이 `insufficient` 로 죽는다
    (실제 8시간 실행은 반복이 수천만이라 무관하고, 60초 프로브도 기회가 180번이라 무관하다).
    """
    per_iteration = ((0, 1), (1, 1), (1, 2), (2, 0))
    for index in range(1, iterations):
        profiler.take(index)
        for phase_index, _order in per_iteration:
            phase = module.SOAK_PHASES[phase_index]
            if profiler.active_for(phase):
                profiler.enable()
                _probe_leaf()
                profiler.disable()
    return profiler.report()


def _key_ending(bucket: dict[str, Any], suffix: str) -> str:
    for key in bucket.get("functions") or {}:
        if key.endswith(suffix):
            return key
    raise AssertionError(f"{suffix} 프레임이 프로파일에 없다 — 실제 호출이 없었다")


def test_call_path_profiler_records_the_caller_table_for_every_phase():
    """계측기 계약: 창을 닫을 때 **호출자 표**가 실제로 상자에 담기고, 상한으로 트리밍된다."""
    module = _load()
    report = _drive_profiler_with_work(module, module._PhaseProfiler(module.SOAK_PHASES))
    assert report["windows"] >= 3, report["windows"]
    for name in module.SOAK_PHASES:
        bucket = report["phases"][name]
        callers = bucket.get("callers") or {}
        assert callers, f"{name}: 호출자 표가 비었다 — pstats 를 거치지 않았다(6번째 칸은 callees 다)"
        for value in callers.values():
            assert 0 < len(value) <= module.PATH_TOP_CALLERS, (name, value)
            assert all(isinstance(count, int) and count > 0 for count in value.values()), value
    # 실제 사슬이 잡혔는가: `_probe_top` 의 호출자는 `_probe_mid` 다(진짜 호출 관계).
    bucket = report["phases"][module.SOAK_PHASES[0]]
    top_key = _key_ending(bucket, ":_probe_top")
    caller_keys = (bucket["callers"] or {}).get(top_key) or {}
    assert any(key.endswith(":_probe_mid") for key in caller_keys), (top_key, caller_keys)
    # 그리고 그 호출자 표로 네 번째 칸이 실제로 **경로를 낸다**(합성이 아니라 실측 자료로).
    verdict = module.function_call_path(_deep_function_dict(module.SOAK_PHASES[0], top_key), report, 28800.0)
    assert verdict["path_criterion"] in {"path", "multi_path"}, verdict["path_criterion_basis"]
    assert verdict["path_chain"][:1] and verdict["path_chain"][0].endswith(":_probe_mid"), verdict["path_chain"]


def test_call_path_profiler_without_callers_negative_control():
    """음성 대조군: 호출자 표를 기록하지 않으면(옛 규칙) 네 번째 칸은 **아무 경로도 내지 못한다**.

    실측으로 반증된 첫 구현이 바로 이것이다 — `Profile.getstats()` 의 6번째 칸을 호출자로 믿고 읽었는데
    그건 **callees** 였다(`None`). 그러면 이 칸이 영영 `insufficient` 로 죽는다(조용한 퇴화).
    """
    module = _load()

    class NoCallers(module._PhaseProfiler):  # type: ignore[misc]
        def report(self) -> dict[str, Any]:
            payload = super().report()
            for bucket in payload["phases"].values():
                bucket["callers"] = {}
            return payload

    silent = _drive_profiler_with_work(module, NoCallers(module.SOAK_PHASES))
    bucket = silent["phases"][module.SOAK_PHASES[0]]
    top_key = _key_ending(bucket, ":_probe_top")
    verdict = module.function_call_path(_deep_function_dict(module.SOAK_PHASES[0], top_key), silent, 28800.0)
    assert verdict["path_criterion"] == "insufficient", verdict
    assert verdict["path_caller"] is None, verdict
    assert "호출자를 말할 표본이 없다" in verdict["path_criterion_basis"], verdict["path_criterion_basis"]
