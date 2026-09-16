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


def _load_judge() -> Any:
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
    return module.judge


JUDGE = _load_judge()


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


def test_every_failure_reason_is_named() -> None:
    """실패했는데 미충족 항목이 비어 있으면 그 판정은 쓸모가 없다(원인 없는 FAIL)."""
    _, checks = JUDGE(
        block={**_BASE_BLOCK, "exit": "1"}, report=None, expected_fp="z" * 64, now_fp="y" * 64, seconds=28800
    )
    assert [c.label for c in checks if not c.ok], "미충족 항목이 하나도 없다"
