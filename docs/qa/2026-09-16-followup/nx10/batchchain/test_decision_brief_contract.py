"""decision_brief.py 계약 — 결정 브리프는 **회수가 가리킨 자료**만 읽고, 없으면 없다고 말한다.

왜 계약이 필요한가(2026-09-18 오너 지시): *“모든 테스트가 완료되고 해당 결과를 보고 결정하자.”*
결정 자리에서 숫자가 틀리면 결정이 틀린다 — 그래서 이 도구가 고정하는 것은 “무엇을 말하는가”가
아니라 **“어느 파일을 근거로 삼는가”** 다. 특히: 이름이 비슷한 최신 파일을 집는 대신 **러너 블록이
가리킨 리포트**를 읽는 것, 처리량 축이 아직 없으면 **없다고 말하는 것**(배치 `PERF` 전에는 실제로 없다).

실행:
  .venv/bin/python -m pytest docs/qa/2026-09-16-followup/nx10/batchchain/test_decision_brief_contract.py -q
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

MARKER = "# NX-10 SC-1~6 soak 러너 기록"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("nx10_decision_brief", HERE / "decision_brief.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIEF = _load()


def _soak_report(*, scenario_extra: dict[str, Any] | None = None, all_pass: bool = True) -> dict[str, Any]:
    scenario: dict[str, Any] = {
        "scenario": "SC-6-soak",
        "completed_ops": 10_000_000,
        "rss_growth_mb": 52.1,
        "errors": 0,
        "conversation_journal_lines": 10_000_001,
        "conversation_journal_bytes": 3_700_000_000,
        "conversation_compaction_generations": 180_000,
        "duration_s": 28800.0,
        "pass": True,
    }
    scenario.update(scenario_extra or {})
    return {
        "generated_at": "2026-09-18T08:30:00Z",
        "all_pass": all_pass,
        "missing_required": [],
        "scenarios": [{"scenario": "SC-1"}, scenario],
    }


def _fixture(
    root: Path,
    *,
    report: dict[str, Any] | None,
    report_name: str = "soak-28800.json",
    block_points_at: str | None = None,
    checks_ok: int = 6,
    checks_total: int = 6,
    gates: dict[str, dict[str, Any]] | None = None,
) -> Path:
    """가짜 nx10 트리 — 러너 블록이 **가리키는** 리포트와, 이름만 비슷한 다른 리포트를 함께 둔다."""
    if report is not None:
        (root / report_name).write_text(json.dumps(report), encoding="utf-8")
    if block_points_at is not None:
        # 일부러 **없는 파일**을 가리킬 수도 있어야 한다(그때 도구가 지어내지 않는지 보려고).
        pointed: str | None = block_points_at
    elif report is not None:
        pointed = (root / report_name).as_posix()
    else:
        pointed = None
    block = (
        MARKER
        + "\n"
        + "".join(
            f"{key}: {value}\n"
            for key, value in (
                ("start_time", "2026-09-18T00:30:00Z"),
                ("end_time", "2026-09-18T08:30:00Z"),
                ("exit", "0"),
                ("soak_seconds", "28800"),
                ("report", pointed or ""),
                ("start_fingerprint", "aa"),
                ("end_fingerprint", "aa"),
            )
        )
    )
    (root / "soak-exit.txt").write_text(block, encoding="utf-8")
    checks = [
        {"label": f"검사 {index}", "ok": index <= checks_ok, "detail": ""} for index in range(1, checks_total + 1)
    ]
    (root / "soak-recovery-latest.json").write_text(
        json.dumps(
            {
                "verdict": "PASS" if checks_ok == checks_total else "FAIL",
                "collected_at": "2026-09-18T08:31:00Z",
                "checks": checks,
                "runner": {"exit": "0"},
            }
        ),
        encoding="utf-8",
    )
    for label, doc in (gates or {}).items():
        (root / f"gate-report-{label}.json").write_text(json.dumps(doc), encoding="utf-8")
    return root


def test_it_reads_the_report_the_runner_block_points_at(tmp_path: Path) -> None:
    """B-1 — 이름이 비슷한 최신 파일이 아니라 **러너가 가리킨 리포트**를 읽는다.

    실제로 이 창에는 `soak-28800.json`·`soak-28800-fail001.json`·`soak-60.json` 이 같이 있다 —
    이름만 보고 고르면 *일부러 실패시킨* 리포트의 숫자를 결정 자리에 들고 간다.
    """
    pointed = _soak_report()
    (tmp_path / "soak-28800-fail001.json").write_text(
        json.dumps(_soak_report(scenario_extra={"rss_growth_mb": 1660.0, "pass": False}, all_pass=False)),
        encoding="utf-8",
    )
    _fixture(tmp_path, report=pointed, report_name="soak-28800.json")
    state = BRIEF.brief(tmp_path)
    assert state["soak"]["report"]["sc6"]["rss_growth_mb"] == 52.1  # 가리킨 쪽
    assert state["soak"]["report"]["all_pass"] is True


def test_a_missing_report_is_reported_as_unread_not_invented(tmp_path: Path) -> None:
    """B-2 — 리포트가 없으면 “못 읽었다”다(빈칸을 숫자로 채우지 않는다)."""
    _fixture(tmp_path, report=None, block_points_at=str(tmp_path / "없는파일.json"))
    state = BRIEF.brief(tmp_path)
    assert state["soak"]["report"] is None
    text = BRIEF.render(state)
    assert "못 읽었다" in text
    assert "자료 없음" in text


def test_the_throughput_axis_is_absent_before_perf_and_present_after(tmp_path: Path) -> None:
    """B-3 — 처리량 축은 **없으면 없다고**, 있으면 값까지 말한다(배치 `PERF` 의 적용 여부가 갈린다)."""
    _fixture(tmp_path, report=_soak_report())
    before = BRIEF.render(BRIEF.brief(tmp_path))
    assert "리포트에 처리량 키가 없다" in before

    after_dir = tmp_path / "after"
    after_dir.mkdir()
    _fixture(
        after_dir,
        report=_soak_report(
            scenario_extra={"throughput_ops_per_second": 612.4, "throughput_baseline_ops_per_second": 833.0}
        ),
    )
    state = BRIEF.brief(after_dir)
    assert state["soak"]["throughput_axis"]["present"] is True
    text = BRIEF.render(state)
    assert "612.4" in text and "833.0" in text


def test_red_gates_are_named_from_the_report(tmp_path: Path) -> None:
    """B-4 — 결정 D1·D2 의 증거는 “어느 게이트가 빨간가”다 — 요약 숫자만으로는 부족하다."""
    gates = {
        "batch-sc6": {
            "summary": {"passed": 22, "failed": 1, "total": 23},
            "git": {"tree_fingerprint": "b6a74304" + "0" * 56},
            "gates": [
                {"id": "python-ruff", "status": "passed"},
                {"id": "python-tests", "status": "failed"},
                {"id": "python-mypy", "status": "skipped"},
            ],
        }
    }
    _fixture(tmp_path, report=_soak_report(), gates=gates)
    state = BRIEF.brief(tmp_path)
    sc6 = next(batch for batch in state["batches"] if batch["batch"] == "SC6")
    assert sc6["red"] == ["python-tests"], "빨간 게이트 이름을 세지 않았다(건너뛴 것은 빨강이 아니다)"
    assert "python-tests" in BRIEF.render(state)
    # 리포트가 없는 배치는 “없음”이라고 말한다.
    assert next(batch for batch in state["batches"] if batch["batch"] == "PERF")["present"] is False


def test_the_brief_writes_nothing(tmp_path: Path) -> None:
    """B-5 — 읽기 전용. 결정 브리프가 도는 체인의 측정에 끼어들지 않는다(상태판과 같은 규칙)."""
    _fixture(tmp_path, report=_soak_report())
    before = sorted(path.name for path in tmp_path.rglob("*"))
    BRIEF.brief(tmp_path)
    BRIEF.render(BRIEF.brief(tmp_path))
    after = sorted(path.name for path in tmp_path.rglob("*"))
    assert before == after, "결정 브리프가 파일을 만들었다"


def test_every_decision_says_what_number_it_needs(tmp_path: Path) -> None:
    """B-6 — 결정마다 “무엇을 보고 정하는가”가 적혀 있다 — 숫자가 없는 항목은 그렇게 밝힌다."""
    _fixture(tmp_path, report=_soak_report())
    ids = [ident for ident, _, _ in BRIEF.DECISIONS]
    assert ids[:4] == ["D1", "D2", "D3", "D4"]
    assert {"D5", "D6", "D7", "D8", "D-P1", "D-P2", "D-P3", "D-F3-1", "D-F3-2", "D-F3-3", "D-F3-4"} <= set(ids)
    text = BRIEF.render(BRIEF.brief(tmp_path))
    for ident in ids:
        assert ident in text, f"{ident} 가 브리프에 없다"
    assert text.count("자료 없음") >= 1
