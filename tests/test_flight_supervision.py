"""미션 루프의 감독기 연동 테스트 (flight_controller × HarnessEnforcer)."""

import tempfile

from antigravity_k.engine.flight_controller import AutonomousFlightController


def _controller(max_turns: int = 20) -> AutonomousFlightController:
    return AutonomousFlightController(
        project_root=tempfile.mkdtemp(prefix="agk_sup_test_"),
        max_flight_turns=max_turns,
    )


def _sequential_executor(outcomes: list[bool]):
    calls = {"n": 0}

    def executor(sid: str, desc: str) -> bool:
        idx = min(calls["n"], len(outcomes) - 1)
        calls["n"] += 1
        return outcomes[idx]

    return executor


def _subgoals(n: int) -> list[dict]:
    return [{"id": f"s{i}", "desc": f"independent step {i}"} for i in range(1, n + 1)]


class TestRetryBudget:
    def test_flaky_step_recovers_within_attempt_budget(self):
        seen: dict[str, int] = {}

        def flaky(sid: str, desc: str) -> bool:
            seen[sid] = seen.get(sid, 0) + 1
            return seen[sid] >= 2

        report = _controller(max_turns=12).launch_mission("flaky", _subgoals(3), flaky)
        assert report.is_success is True
        assert report.stall_interventions == []

    def test_double_failure_is_permanent(self):
        report = _controller(max_turns=12).launch_mission("hard", _subgoals(2), _sequential_executor([False] * 4))
        assert report.is_success is False
        assert "PERMANENTLY FAILED" in "".join(report.log_messages)


class TestSupervisorIntervention:
    def test_no_progress_window_fires_exactly_once(self):
        outcomes = [False, False, False, False, False, True, True, True]
        report = _controller(max_turns=16).launch_mission("stall", _subgoals(5), _sequential_executor(outcomes))
        assert len(report.stall_interventions) == 1
        assert "진척 없는 행동" in report.stall_interventions[0]
        assert any("Supervisor intervention" in line for line in report.log_messages)

    def test_healthy_mission_has_zero_interventions(self):
        report = _controller().launch_mission("clean", _subgoals(3), _sequential_executor([True] * 3))
        assert report.is_success is True
        assert report.stall_interventions == []


class TestMissionReportCompat:
    def test_report_defaults_backward_compatible(self):
        from antigravity_k.engine.flight_controller import MissionReport

        report = MissionReport(goal="g", is_success=True, total_steps_executed=1, failed_steps_count=0, tdd_passed=True)
        assert report.stall_interventions == []
