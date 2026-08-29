#!/usr/bin/env python3
"""스톨 감독기 시나리오 시뮬레이터 — 임계값 보정용 결정론 측정.

LLM 없이 AutonomousFlightController 미션 루프에 스크립트된 실행기를 넣어
감독 축(무진행 윈도우 / 유사 오류 클러스터 / 동일 반복 차단)의 발화 시점과
미션 회복 여부를 측정한다. 임계값을 바꿔가며 돌려 데이터로 보정한다.

사용:
    uv run python scripts/simulate_stall_supervision.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.flight_controller import AutonomousFlightController


def _controller(max_turns: int = 20) -> AutonomousFlightController:
    return AutonomousFlightController(
        project_root=tempfile.mkdtemp(prefix="agk_supervision_"),
        max_flight_turns=max_turns,
    )


def _sequential_executor(outcomes: list[bool]):
    """호출 순서대로 outcomes를 소비하는 실행기."""
    calls = {"n": 0}

    def executor(sid: str, desc: str) -> bool:
        idx = min(calls["n"], len(outcomes) - 1)
        calls["n"] += 1
        return outcomes[idx]

    return executor


def _subgoals(n: int) -> list[dict[str, object]]:
    return [{"id": f"s{i}", "desc": f"independent step {i}"} for i in range(1, n + 1)]


def scenario_healthy() -> dict[str, object]:
    report = _controller().launch_mission("healthy mission", _subgoals(3), _sequential_executor([True] * 3))
    return {
        "scenario": "healthy",
        "success": report.is_success,
        "interventions": len(report.stall_interventions),
        "expect": "success=True, interventions=0",
    }


def scenario_flaky_recovered() -> dict[str, object]:
    """각 서브골이 1회 실패 후 재시도 성공 — 시도 예산 안에서 회복된다."""
    seen: dict[str, int] = {}

    def flaky(sid: str, desc: str) -> bool:
        seen[sid] = seen.get(sid, 0) + 1
        return seen[sid] >= 2

    report = _controller(max_turns=12).launch_mission("flaky mission", _subgoals(3), flaky)
    return {
        "scenario": "flaky_recovered",
        "success": report.is_success,
        "interventions": len(report.stall_interventions),
        "failed_steps": report.failed_steps_count,
        "expect": "success=True, interventions=0 (재시도 예산이 회복 담당)",
    }


def scenario_no_progress_intervention() -> dict[str, object]:
    """연속 5회 실패 → 무진행 개입 1회 발화 후 나머지 서브골 완주."""
    # s1(영구실패) s2(영구실패) s3(1회실책→재시도성공) s4 s5
    outcomes = [False, False, False, False, False, True, True, True]
    report = _controller(max_turns=16).launch_mission("stall mission", _subgoals(5), _sequential_executor(outcomes))
    head = report.stall_interventions[0].splitlines()[0] if report.stall_interventions else ""
    return {
        "scenario": "no_progress_intervention",
        "success": report.is_success,
        "interventions": len(report.stall_interventions),
        "first_intervention_head": head,
        "permanent_failures": report.failed_steps_count,
        "expect": "interventions=1 & head에 '진척 없는 행동' (s1·s2는 희생 노드라 success=False 정상)",
    }


def main() -> int:
    results = [
        scenario_healthy(),
        scenario_flaky_recovered(),
        scenario_no_progress_intervention(),
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    from antigravity_k.engine.harness_enforcer import HarnessEnforcer

    print("\n임계값 현재 설정:")
    print(f"  STALL_REPEAT_THRESHOLD        = {HarnessEnforcer.STALL_REPEAT_THRESHOLD}")
    print(f"  STALL_ERROR_CLUSTER_THRESHOLD = {HarnessEnforcer.STALL_ERROR_CLUSTER_THRESHOLD}")
    print(f"  STALL_NO_PROGRESS_WINDOW      = {HarnessEnforcer.STALL_NO_PROGRESS_WINDOW}")
    print(f"  MAX_STEP_ATTEMPTS             = {AutonomousFlightController.MAX_STEP_ATTEMPTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
