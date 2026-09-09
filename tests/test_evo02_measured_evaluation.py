"""EVO-02 — 기대 개선과 실측 평가 분리.

GA-100 plan §EVO-02 수용기준:
  AC-1  mutation 적용 직후 measured metric은 비어 있고 예상값과 혼합되지 않는다.
  AC-2  frozen benchmark 재실행 결과와 환경/provenance hash가 저장된다.
  AC-3  regression이면 promotion이 거절되고 regression_rejected 상태로 전환된다.
  AC-4  UI/API가 예상·실측·평가 상태를 구분해 노출한다 (summary/보고서 필드).

EVO-01 fail-closed 스위트와 동일한 fixture 패턴을 재사용한다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from antigravity_k.engine.self_evolution_coordinator import (
    EvolutionDecision,
    MutationDomain,
    PerformanceSnapshot,
    SelfEvolutionCoordinator,
)


def _snapshot(grade: str = "F", score: float = 0.35) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        quality_grade=grade,
        quality_score=score,
        timestamp=0.0,
    )


def _decision(expected: float = 0.1) -> EvolutionDecision:
    return EvolutionDecision(
        domain=MutationDomain.SYSTEM_PROMPT,
        confidence=0.9,
        expected_improvement=expected,
        target_file="prompts/system_prompt.md",
    )


class _SandboxPass:
    """검증을 통과시키는 sandbox double — enum-style value 속성 필요."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def safe_mutation(self, name: str):  # noqa: ANN001, ANN202
        self.calls.append(name)

        class _Ctx:
            def __enter__(self) -> dict[str, Any]:
                return {"passed": True, "value": "pass"}

            def __exit__(self, *args: object) -> bool:
                return False

        return _Ctx()


def _wire_success_path(
    coord: SelfEvolutionCoordinator,
    monkeypatch: pytest.MonkeyPatch,
    expected: float = 0.1,
) -> None:
    """sandbox 통과 + mutation 적용 + validation 통과 경로로 조립."""
    coord._sandbox = _SandboxPass()  # type: ignore[assignment]
    coord._last_evolution_time = 0.0
    coord._turns_since_last_evolution = 999

    monkeypatch.setattr(
        coord,
        "_mutate_system_prompt",
        lambda decision, snapshot: {
            "applied": True,
            "message": "fixture",
            "method": "fixture",
            "new_prompt_snippet": "EVO02 fixture prompt content for validation path",
        },
    )
    monkeypatch.setattr(
        coord,
        "_analyze",
        lambda snapshot: _decision(expected),
    )
    monkeypatch.setattr(
        coord,
        "_validate",
        lambda decision, payload: {"passed": True, "value": "pass"},
    )


# ─── AC-1 · 적용 직후 measured는 비어 있고 expected와 혼합되지 않는다 ───


def test_after_apply_metric_is_pending_not_expected(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch, expected=0.1)

    result = coord.auto_evolve(_snapshot())

    assert result.success is True
    # EVO-02 핵심 계약 — 예상치를 실측으로 위장하지 않는다
    assert result.measured_after_metric is None
    assert result.improvement is None
    assert result.evaluation_state == "pending_evaluation"
    assert result.expected_improvement == pytest.approx(0.1)
    # before_metric만 기록된다
    assert result.before_metric == pytest.approx(0.35)


def test_summary_distinguishes_pending_from_measured(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch, expected=0.1)

    result = coord.auto_evolve(_snapshot())
    text = result.summary
    assert "평가 대기" in text
    assert "실측 미확정" in text
    # 실측 개선 문구가 아니어야 한다
    assert "실측 개선 확인" not in text


def test_history_record_keeps_expected_and_measured_separate(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch, expected=0.1)

    coord.auto_evolve(_snapshot())
    history_path = tmp_path / "data" / "evolution_history.json"
    assert history_path.exists()
    records = json.loads(history_path.read_text(encoding="utf-8"))
    last = records[-1]
    assert last["expected_improvement"] == pytest.approx(0.1)
    assert last["measured_after_metric"] is None
    assert last["improvement"] is None
    assert last["evaluation_state"] == "pending_evaluation"


# ─── AC-2 · frozen benchmark 재실행 결과 + provenance hash 저장 ───


def test_evaluate_pending_fills_measured_and_provenance(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch, expected=0.1)
    result = coord.auto_evolve(_snapshot())

    evaluated = coord.evaluate_pending_mutation(
        result.details.get("cycle_id", "") or _last_cycle_id(coord),
        run_frozen_benchmark=lambda suite: 0.5,  # before 0.35 → +0.15 개선
    )

    assert evaluated is not None
    assert evaluated.measured_after_metric == pytest.approx(0.5)
    assert evaluated.improvement == pytest.approx(0.15)
    assert evaluated.evaluation_state == "evaluated"
    prov = evaluated.benchmark_provenance
    assert prov["suite"] == f"evo-{result.mutation_domain.value}"
    assert len(prov["env_hash"]) == 16
    assert prov["evaluated_at"] > 0


def test_evaluate_pending_requires_runner(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch)
    result = coord.auto_evolve(_snapshot())

    before = (result.measured_after_metric, result.evaluation_state)
    out = coord.evaluate_pending_mutation(_last_cycle_id(coord), run_frozen_benchmark=None)
    # runner 없이는 실측을 만들어내지 않는다 (fail-closed)
    assert (out.measured_after_metric, out.evaluation_state) == before


# ─── AC-3 · regression이면 promotion 거절 ───


def test_regression_rejects_promotion(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch)
    coord.auto_evolve(_snapshot(score=0.6))

    events_before = len(coord._event_ledger)
    evaluated = coord.evaluate_pending_mutation(
        _last_cycle_id(coord),
        run_frozen_benchmark=lambda suite: 0.5,  # before 0.6 → -0.1 회귀
    )

    assert evaluated is not None
    assert evaluated.improvement == pytest.approx(-0.1)
    assert evaluated.evaluation_state == "regression_rejected"
    kinds = [e.get("stage") for e in coord._event_ledger[events_before:]]
    assert "promotion_rejected" in kinds
    assert "promotion_approved" not in kinds
    # 회귀 요약이 거절을 알린다
    assert "promotion 거절" in evaluated.summary


def test_improvement_promotion_approved(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch)
    coord.auto_evolve(_snapshot(score=0.4))

    evaluated = coord.evaluate_pending_mutation(
        _last_cycle_id(coord),
        run_frozen_benchmark=lambda suite: 0.55,
    )
    assert evaluated is not None
    assert evaluated.evaluation_state == "evaluated"
    kinds = [e.get("stage") for e in coord._event_ledger[-3:]]
    assert "promotion_approved" in kinds


# ─── AC-4 · UI/API 구분 노출 ───


def test_report_exposes_pending_evaluation_count(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch)
    coord.auto_evolve(_snapshot())
    # MIN_EVOLUTION_INTERVAL(30s)/턴 쿨다운(3)은 실측과 무관 — 테스트에서만 리셋
    coord._last_evolution_time = 0.0
    coord._turns_since_last_evolution = 999
    coord.auto_evolve(_snapshot())

    report = coord.get_report()
    assert report["pending_evaluations"] == 2


def test_report_pending_count_excludes_evaluated(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch)
    coord.auto_evolve(_snapshot())
    coord.evaluate_pending_mutation(
        _last_cycle_id(coord),
        run_frozen_benchmark=lambda suite: 0.8,
    )

    report = coord.get_report()
    assert report["pending_evaluations"] == 0


def test_summary_shows_measured_when_evaluated(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    _wire_success_path(coord, monkeypatch)
    coord.auto_evolve(_snapshot(score=0.35))
    evaluated = coord.evaluate_pending_mutation(
        _last_cycle_id(coord),
        run_frozen_benchmark=lambda suite: 0.6,
    )
    assert evaluated is not None
    assert "실측 개선 확인" in evaluated.summary
    assert "평가 대기" not in evaluated.summary


# ─── 경계 ───


def test_evaluate_unknown_cycle_returns_none(tmp_path) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    assert coord.evaluate_pending_mutation("no-such-cycle") is None


def test_evaluate_non_success_cycle_is_noop(tmp_path, monkeypatch) -> None:
    coord = SelfEvolutionCoordinator(project_root=str(tmp_path))
    result = coord.auto_evolve(_snapshot(grade="A"))  # should_evolve가 거절하는 등급
    assert result.skipped is True
    out = coord.evaluate_pending_mutation(_last_cycle_id(coord) or "none")
    # skipped 사이클은 pending이 아니므로 그대로 반환/무시
    assert out is None or out.evaluation_state != "evaluated"


# ─── 헬퍼 ───


def _last_cycle_id(coord: SelfEvolutionCoordinator) -> str:
    assert coord._history, "history가 비어 있으면 안 된다"
    return coord._history[-1].cycle_id
