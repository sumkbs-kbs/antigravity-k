"""계약 시험 — SC-6 RSS 판정이 **워밍업 창 밖 증가**와 **반복당 creep** 을 실제로 재는가.

왜 계약인가 (2026-09-17, `SC6_CRITERION_REVIEW.md`): 옛 판정식은 `마지막 표본 − 첫 표본` 이었고
첫 표본이 **루프 50 반복 뒤**라, 그 50 반복이 처리량에 따라 0.08초(600회/초)~20.45초(2.4회/초)로
움직였다 — 같은 코드를 처리량에 따라 다르게 재는 기준이었고 워밍업이 예산의 15~33%를 먹었다.
게다가 창을 1분으로 두면 종료 투영이 “요즘 기울기”와 “누적 평균”에 따라 PASS/FAIL 로 갈렸다
(모델 분산 = 기준의 30~46%). 새 기준은 ① 창 밖 증가 ≤ 64 MB ② 창 밖 반복당 creep ≤ 0.25 KB/회
두 축이고, 창은 `max(5분, 지속×5%)` 다.

이 시험은 8시간 soak 을 돌리지 않는다 — 순수 함수 `sc6_rss_criterion` 에 **합성 계열**을 넣어
① 창 안의 큰 계단이 판정에서 빠지고(옛 기준이면 FAIL 인 픽스처가 PASS 가 되는지)
② 짧은 실행은 `not_applicable` 로 **판정하지 않고 이유를 남기는지**
③ 반복당 creep 이 실제로 반복 수로 나뉘는지
④ **음성 대조군**(끝으로 갈수록 가팔라지는 진짜 누수 곡선)이 두 축 모두 FAIL 인지
⑤ 리포트의 `rss_samples_mb` + `rss_warmup_index` 만으로 같은 판정이 재현되는지
⑥ 시나리오가 그 함수를 **실제로 부르는지**(판정식이 조용히 떨어져 나가지 않게)를 고정한다.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

THRESHOLD_MB = 64.0
CREEP_MAX_KB_PER_OP = 0.25
WARMUP_MIN_S = 300.0
WARMUP_FRACTION = 0.05


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


def _load_staging() -> Any:
    path = _repo_root() / "scripts" / "val02_staging.py"
    spec = importlib.util.spec_from_file_location("val02_staging_sc6_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


staging = _load_staging()


def _series(n: int, duration_s: float, rss: list[float]) -> tuple[list[float], list[int], list[float]]:
    """표본 목록을 하네스와 같은 좌표계로 만든다 — 50 반복마다 표본, 시간은 균등."""
    assert len(rss) == n
    sample_ops = [50 * (k + 1) for k in range(n)]
    sample_times = [duration_s * k / (n - 1) for k in range(n)]
    return rss, sample_ops, sample_times


def _ramp_then_flat(n: int = 1000, window_ramp_mb: float = 70.0, creep_mb: float = 1.0) -> tuple[list, list, list]:
    """시작 계단 +70 MB(창 안) 뒤 완만한 +1 MB(창 밖) — **총량은 기준을 넘지만 누수가 아니다**."""
    ramp = int(n * WARMUP_FRACTION) + 100  # 창(5%)보다 조금 뒤까지 계단이 남게 한다
    rss = [100.0]
    for k in range(1, n):
        rss.append(100.0 + (window_ramp_mb if k <= ramp else window_ramp_mb + creep_mb))
    return _series(n, 28800.0, rss)


def _leak_curve(n: int = 1000, total_mb: float = 1683.4) -> tuple[list, list, list]:
    """음성 대조군 — 오늘 실제로 FAIL 한 실행의 모양(끝으로 갈수록 가팔라진다)."""
    rss = [100.0 + (k / n) ** 2 * total_mb for k in range(n)]
    return _series(n, 28800.0, rss)


def test_warmup_window_floor_and_fraction() -> None:
    """창은 `max(5분, 지속×5%)` — 두 항이 **각각** 쓰이는 경계를 고정한다."""
    assert staging.sc6_warmup_window_s(60.0) == WARMUP_MIN_S
    assert staging.sc6_warmup_window_s(28800.0) == 28800.0 * WARMUP_FRACTION  # 1,440초
    assert staging.sc6_warmup_window_s(6000.0) == 6000.0 * WARMUP_FRACTION  # 5% = 300초 = 하한
    assert staging.sc6_warmup_window_s(5999.0) == WARMUP_MIN_S  # 하한이 이긴다
    assert staging.RSS_WARMUP_MIN_S == WARMUP_MIN_S
    assert staging.RSS_WARMUP_FRACTION == WARMUP_FRACTION
    assert staging.RSS_LEAK_THRESHOLD_MB == THRESHOLD_MB
    assert staging.RSS_CREEP_MAX_KB_PER_OP == CREEP_MAX_KB_PER_OP


def test_warmup_ramp_is_excluded_and_total_is_kept() -> None:
    """창 안의 큰 계단은 판정에서 빠지고, 옛 값(`rss_growth_mb`)은 기록으로 남는다.

    픽스처의 총량은 71 MB 로 기준 64 MB 를 **넘는다** — 옛 판정식이었다면 FAIL 이다.
    새 판정식은 창(24분) 뒤 증가만 보므로 PASS 여야 한다(이게 “워밍업 제외”의 뜻이다).
    """
    rss, ops, times = _ramp_then_flat()
    out = staging.sc6_rss_criterion(rss, ops, times, 28800.0)
    assert out["rss_growth_mb"] >= THRESHOLD_MB, "픽스처가 옛 기준을 넘지 않으면 이 시험이 무의미하다"
    assert out["rss_warmup_growth_mb"] > 60.0
    assert out["rss_growth_warmup_excluded_mb"] <= 2.0
    assert out["rss_criterion"] == "pass", out["rss_criterion_basis"]


def test_short_run_is_not_applicable_with_a_reason() -> None:
    """1분 리허설에 8시간 임계값을 물으면 +21 MB 를 누수로 보고한다 — 이제 판정하지 않는다."""
    rss, ops, times = _series(3, 60.1, [67.2, 80.0, 88.4])
    out = staging.sc6_rss_criterion(rss, ops, times, 60.1)
    assert out["rss_criterion"] == "not_applicable"
    assert out["rss_criterion"] != "pass" and out["rss_criterion"] != "fail"
    assert "판정 불가" in out["rss_criterion_basis"]
    assert str(int(staging.RSS_WARMUP_MIN_S)) in out["rss_criterion_basis"]
    # 옛 값은 그대로 남는다(회귀 비교용) — 이 실행의 총량은 +21.2 MB 다.
    assert out["rss_growth_mb"] == 21.2


def test_report_rounding_does_not_open_a_reproducibility_gap() -> None:
    """반올림 지점이 두 곳이면 리포트와 재현값이 어긋난다 — 2026-09-17 리허설이 잡은 틈.

    한때 반복당 creep 을 **반올림 전** 증가량으로 계산해 리포트(0.1 MB 단위)와 1e-4 만큼 달랐다.
    숫자가 작아 보여도 “리포트만으로 같은 판정을 재현한다”는 이 기준의 전제를 깨고 있었다.
    """
    rss, ops, times = _leak_curve()
    out = staging.sc6_rss_criterion(rss, ops, times, 28800.0)
    index = out["rss_warmup_index"]
    ops_after = max(ops[-1] - ops[index], 1)
    exact_from_unrounded = (rss[-1] - rss[index]) * 1024.0 / ops_after
    reported = out["rss_creep_kb_per_operation"]
    # 판정이 민감하지 않은 구간에서는 이 차이가 무해하다 — 그러나 값은 리포트의 반올림을 따라야 한다.
    assert abs(reported - exact_from_unrounded) < 0.01
    assert reported == round(out["rss_growth_warmup_excluded_mb"] * 1024.0 / ops_after, 4)


def test_creep_per_operation_divides_by_operation_count() -> None:
    """같은 바이트를 10배 반복으로 나누면 creep 은 1/10 — 처리량 불변 지표의 정의다."""
    n = 200
    rss = [100.0] * (n - 1) + [101.0]  # 창 밖에서 정확히 +1 MB
    _, ops1, times1 = _series(n, 28800.0, rss)
    _, ops10, times10 = _series(n, 28800.0, rss)
    ops10 = [v * 10 for v in ops10]
    a = staging.sc6_rss_criterion(rss, ops1, times1, 28800.0)
    b = staging.sc6_rss_criterion(rss, ops10, times10, 28800.0)
    assert a["rss_growth_warmup_excluded_mb"] == b["rss_growth_warmup_excluded_mb"]
    assert a["rss_creep_kb_per_operation"] > 0.0
    assert abs(a["rss_creep_kb_per_operation"] / b["rss_creep_kb_per_operation"] - 10.0) < 0.05


def test_verdict_is_reproducible_from_the_report_fields() -> None:
    """리포트만 보고 같은 판정을 재현할 수 있는가 — `rss_warmup_index` 가 그 문이다."""
    for rss, ops, times in (_ramp_then_flat(), _leak_curve()):
        out = staging.sc6_rss_criterion(rss, ops, times, 28800.0)
        index = out["rss_warmup_index"]
        assert 0 <= index < len(rss) - 1
        assert out["rss_growth_warmup_excluded_mb"] == round(rss[-1] - rss[index], 1)
        assert out["rss_warmup_growth_mb"] == round(rss[index] - rss[0], 1)
        # 창 밖 반복 수 = 표본 인덱스 × 50 반복 — 리포트의 값만으로 계산된다.
        ops_after = max(50 * (len(rss) - 1 + 1) - 50 * (index + 1), 1)
        expected = round(out["rss_growth_warmup_excluded_mb"] * 1024.0 / ops_after, 4)
        # **정확히** 같아야 한다 — 반올림을 한 번만 하므로 재현에 틈이 없다.
        assert out["rss_creep_kb_per_operation"] == expected, (
            f"리포트 값이 재현되지 않는다: {out['rss_creep_kb_per_operation']} != {expected}"
        )


def test_negative_control_leak_curve_fails_both_axes() -> None:
    """음성 대조군(오늘의 진짜 누수 모양)은 **두 축 모두** FAIL 이어야 한다.

    이 픽스처가 PASS 로 바뀌면 새 기준은 누수를 못 잡는다 — 그때 이 시험이 먼저 빨개진다.
    """
    rss, ops, times = _leak_curve()
    out = staging.sc6_rss_criterion(rss, ops, times, 28800.0)
    assert out["rss_criterion"] == "fail", out["rss_criterion_basis"]
    assert out["rss_growth_warmup_excluded_mb"] > THRESHOLD_MB
    assert out["rss_creep_kb_per_operation"] > CREEP_MAX_KB_PER_OP
    basis = out["rss_criterion_basis"]
    assert "창 밖 증가" in basis and "반복당" in basis  # 두 축을 문장으로도 말한다


def test_scenario_soak_actually_uses_the_criterion() -> None:
    """시나리오 배선 — 판정식이 조용히 떨어져 나가면(예: 옛 `growth` 로 되돌리면) 여기서 걸린다."""
    source = inspect.getsource(staging.scenario_soak)
    assert "sc6_rss_criterion(" in source, "soak 시나리오가 새 기준을 부르지 않는다"
    assert "rss_verdict" in source, "판정 결과가 리포트에 실리지 않는다"
    assert "rss_criterion" in source, "`pass` 가 새 판정을 보지 않는다"
    # 표본의 시각·반복 수를 모으지 않으면 창 밖 구간을 정의할 수 없다.
    assert "sample_times_s" in source and "sample_ops" in source


def test_report_schema_carries_the_new_fields() -> None:
    """새 필드가 리포트에 실리는가 — 다음 사람이 기준을 비교할 수 있어야 한다."""
    rss, ops, times = _ramp_then_flat()
    out = staging.sc6_rss_criterion(rss, ops, times, 28800.0)
    for key in (
        "rss_growth_mb",
        "rss_growth_warmup_excluded_mb",
        "rss_warmup_growth_mb",
        "rss_warmup_window_s",
        "rss_warmup_index",
        "rss_creep_kb_per_operation",
        "rss_creep_max_kb_per_op",
        "rss_warmup_min_s",
        "rss_warmup_fraction",
        "rss_criterion",
        "rss_criterion_basis",
    ):
        assert key in out, f"리포트 필드 누락: {key}"
