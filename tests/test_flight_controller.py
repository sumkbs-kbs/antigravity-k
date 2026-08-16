"""Unit tests for AutonomousFlightController."""

from pathlib import Path

from antigravity_k.engine.flight_controller import AutonomousFlightController


def test_autonomous_flight_success():
    controller = AutonomousFlightController(project_root=Path.cwd(), max_flight_turns=5)

    subgoals = [
        {"id": "m1", "desc": "Ignition test"},
        {"id": "m2", "desc": "Stage separation", "depends_on": ["m1"]},
        {"id": "m3", "desc": "Orbit insertion", "depends_on": ["m2"]},
    ]

    def mock_executor(step_id: str, desc: str) -> bool:
        # All steps succeed
        return True

    report = controller.launch_mission(
        goal="Launch Starship to Orbit",
        initial_subgoals=subgoals,
        step_executor=mock_executor,
    )

    assert report.is_success is True
    assert report.total_steps_executed == 3
    assert report.failed_steps_count == 0
