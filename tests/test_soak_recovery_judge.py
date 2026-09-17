"""계약 시험(승격본) — soak 회수 **판정기**가 통과를 남발하지 않게 고정한다.

왜 계약인가: 카드는 soak 판정에 "지표 + 시작/종료 지문 동일"을 요구하는데, 이 프로젝트는 이미
지표만 보고 승격한 사고를 겪었다(EX-05: JSON PASS 인데 종료·귀속이 미확정이었는데 상태 셀이 PASS 로 올라갔다).
회수 판정도 사람 눈이 아니라 코드가 하되, 그 코드가 **틀린 방향으로 관대해지지 않도록** 여기서 고정한다.

판정기는 `scripts/collect_soak_result.py`(승격 전에는 `docs/…/nx10/` 에 있다)이고, 이 시험은
`judge()` 를 합성 입력으로 직접 부른다 — 8시간을 기다리지 않고 판정 로직만 검증한다.

승격 상태: `tests/test_soak_recovery_judge.py` 로 옮겨진다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


REPO = _repo_root()
_CANDIDATES = (
    REPO / "scripts" / "collect_soak_result.py",
    REPO / "docs" / "qa" / "2026-09-16-followup" / "nx10" / "collect_soak_result.py",
)

_FP = "a" * 64
_BASE_BLOCK = {
    "soak_seconds": "28800",
    "start_time": "2026-09-16T13:00:00Z",
    "end_time": "2026-09-16T21:00:10Z",  # 8시간 10초
    "start_fingerprint": _FP,
    "end_fingerprint": _FP,
    "exit": "0",
}
_GOOD_REPORT: dict[str, Any] = {"all_pass": True, "missing_required": [], "scenarios": []}


def _load_module() -> Any:
    path = next((c for c in _CANDIDATES if c.is_file()), None)
    if path is None:
        pytest.fail(f"회수 판정기를 찾지 못했다: {[str(c.relative_to(REPO)) for c in _CANDIDATES]}")
    spec = importlib.util.spec_from_file_location("collect_soak_result_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `sys.modules` 에 먼저 등록해야 한다 — 판정기의 `@dataclass(frozen=True)` 가
    # `sys.modules[cls.__module__]` 을 찾기 때문이다(등록 없이는 AttributeError: 'NoneType').
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
JUDGE = MODULE.judge


@pytest.mark.parametrize(
    ("label", "block", "report", "now_fp", "expected"),
    [
        ("정상(지표+실행+귀속)", {}, _GOOD_REPORT, _FP, "PASS"),
        (
            "중단(exit 143, 20분)",
            {"exit": "143", "end_time": "2026-09-16T13:20:00Z"},
            _GOOD_REPORT,
            _FP,
            "METRICS_PASS",
        ),
        ("시작 지문 ≠ 종료 지문", {"end_fingerprint": "b" * 64}, _GOOD_REPORT, _FP, "FAIL"),
        ("지표 실패", {}, {"all_pass": False, "missing_required": ["SC-6"], "scenarios": []}, _FP, "FAIL"),
        ("측정 후 코드 변경", {}, _GOOD_REPORT, "c" * 64, "FAIL"),
        ("리포트 없음", {}, None, _FP, "FAIL"),
    ],
)
def test_verdict_matches_the_three_stage_rule(
    label: str, block: dict[str, str], report: dict[str, Any] | None, now_fp: str, expected: str
) -> None:
    """① 지표 ② 실행(exit+벽시계) ③ 귀속(기대=시작=종료=지금) 중 하나라도 어긋나면 PASS 가 아니다."""
    verdict, _ = JUDGE(block={**_BASE_BLOCK, **block}, report=report, expected_fp=_FP, now_fp=now_fp, seconds=28800)
    if expected == "METRICS_PASS":
        assert verdict.startswith("METRICS_PASS"), f"{label}: {verdict}"
        assert "DONE 아님" in verdict, f"{label}: 지표만 통과한 상태를 PASS 처럼 읽게 두면 안 된다"
    else:
        assert verdict == expected, f"{label}: {verdict}"


def test_short_wall_clock_is_not_a_pass_even_with_all_pass_report() -> None:
    """즉시 끝난 실행도 리포트는 쓴다 — 벽시계를 보지 않으면 그 실행이 통과로 새어 나간다."""
    verdict, checks = JUDGE(
        block={**_BASE_BLOCK, "end_time": "2026-09-16T13:05:00Z"},  # 5분
        report=_GOOD_REPORT,
        expected_fp=_FP,
        now_fp=_FP,
        seconds=28800,
    )
    assert verdict != "PASS"
    assert any(not c.ok and "벽시계" in c.label for c in checks), [c.label for c in checks]


def test_schedule_reader_uses_the_latest_reservation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """예약을 재장전하면 블록이 **덧붙는다** — 첫 값을 잡으면 밤새 정상으로 끝난 실행이 거짓 FAIL 이 된다.

    실측(2026-09-16): 종전 구현(`re.search` = 첫 매치)은 `157311cf…`(08:20Z 예약)를 기대값으로 잡았고,
    현재 예약은 `92fcaeb5…`(11:39Z)였으므로 그대로 두면 ③(기대 == 시작)이 거짓으로 어긋났다.
    """
    schedule = tmp_path / "soak-schedule.txt"
    schedule.write_text(
        "expected_fingerprint: " + "1" * 64 + "\n"
        "# ── 운영자 기록: 예약 취소 ──\n"
        "previous_expected_fingerprint: " + "9" * 64 + "\n"
        "expected_fingerprint: " + "2" * 64 + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "SCHEDULE", schedule)
    assert MODULE.expected_fingerprint() == "2" * 64, "마지막 예약을 기대값으로 쓰지 않았다"
    assert MODULE.reservation_count() == 2
    # 다른 키(`previous_…`)는 줄 시작 앵커 때문에 기대값으로 새지 않는다.
    assert MODULE.latest_expected_fingerprint("previous_expected_fingerprint: " + "d" * 64 + "\n") == "UNVERIFIED"
    assert MODULE.latest_expected_fingerprint("") == "UNVERIFIED"


def test_aborted_reservation_is_never_the_reference(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """중단된 예약은 “그 트리에서 아무것도 재지 않았다” — 기대값으로 쓰면 정상 실행이 거짓 FAIL 이 된다.

    실측(2026-09-17): 예약 이력의 **마지막 두 블록**이 `aborted: true`(예약 시점에 지문을 못 재
    `start_check_fingerprint: UNVERIFIED`)였다. 그 예약들은 한 틱도 돌지 않았는데, 지표 all_pass ·
    러너 exit 0 · 벽시계 28804s · 시작==종료==현재 트리(`b6a74304…`)로 끝난 8시간 실행이
    그 지문(`322b4d3b…`)과 달라 FAIL 로 판정됐다 — 승격 체인이 그 FAIL 로 멈췄다.
    """
    schedule = tmp_path / "soak-schedule.txt"
    schedule.write_text(
        "# NX-10 soak 예약 기록\n"
        f"expected_fingerprint: {'4' * 64}\n"
        "# NX-10 soak 예약 기록\n"
        f"expected_fingerprint: {'5' * 64}\n"
        "start_check_fingerprint: UNVERIFIED\n"
        "aborted: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "SCHEDULE", schedule)
    assert MODULE.latest_expected_fingerprint(schedule.read_text(encoding="utf-8")) == "4" * 64
    assert MODULE.expected_fingerprint() == "4" * 64, "중단된 예약의 지문을 기대값으로 썼다"
    # 중단뿐인 이력은 “기대값 없음” 이다 — 없는 근거를 만들어 내지 않는다.
    only_aborted = "# NX-10 soak 예약 기록\n" + f"expected_fingerprint: {'6' * 64}\naborted: true\n"
    assert MODULE.latest_expected_fingerprint(only_aborted) == "UNVERIFIED"
    assert MODULE.schedule_blocks(only_aborted) == [only_aborted]


def test_no_live_reservation_falls_back_to_the_runner_record_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """즉시 실행(`run`)은 예약 블록을 남기지 않는다 — 그때 근거는 러너의 자기 기록뿐이고, 그 사실을 밝힌다.

    조용히 통과시키면 “기대 == 시작” 검사가 사라지고, 그렇다고 FAIL 로 몰면 정상 실행이 매번 거짓 FAIL 이
    된다. 그래서 러너가 기록한 시작 지문을 쓰고 **출처를 문장으로** 남긴다.
    """
    schedule = tmp_path / "soak-schedule.txt"
    schedule.write_text(
        "# NX-10 soak 예약 기록\n" + f"expected_fingerprint: {'6' * 64}\naborted: true\n", encoding="utf-8"
    )
    monkeypatch.setattr(MODULE, "SCHEDULE", schedule)
    runner = {"start_fingerprint": "7" * 64}
    expected, source = MODULE.resolve_expected(None, runner)
    assert expected == "7" * 64
    assert "러너" in source and "예약" in source, source
    # 러너 기록조차 없으면 근거 없음 — 조용히 PASS 로 새지 않는다.
    assert MODULE.resolve_expected(None, {})[0] == "UNVERIFIED"
    # 사람이 지정하면 그것이 최우선이고, 그 사실도 출처에 남는다.
    assert MODULE.resolve_expected("8" * 64, runner)[1].startswith("사람이 지정")


def test_verdict_prints_where_the_reference_came_from() -> None:
    """판정 ③ 줄에 출처가 붙는다 — PASS 를 읽는 사람이 “이 값이 어디서 왔는가”를 되물어야 하지 않게."""
    _, checks = JUDGE(
        block={**_BASE_BLOCK},
        report=_GOOD_REPORT,
        expected_fp=_FP,
        now_fp=_FP,
        seconds=28800,
        expected_source="예약 기록 없음(즉시 실행) → 러너가 기록한 시작 지문",
    )
    detail = next(c.detail for c in checks if c.label.startswith("③ 기대 지문"))
    assert "러너" in detail, detail


def test_every_failure_reason_is_named() -> None:
    """실패했는데 미충족 항목이 비어 있으면 그 판정은 쓸모가 없다(원인 없는 FAIL)."""
    _, checks = JUDGE(
        block={**_BASE_BLOCK, "exit": "1"}, report=None, expected_fp="z" * 64, now_fp="y" * 64, seconds=28800
    )
    assert [c.label for c in checks if not c.ok], "미충족 항목이 하나도 없다"
