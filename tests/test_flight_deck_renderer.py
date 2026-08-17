"""Unit tests for FlightDeckRenderer."""

from antigravity_k.engine.flight_deck_renderer import FlightDeckRenderer, FlightTelemetryState


def test_flight_deck_rendering():
    state = FlightTelemetryState(
        mission_goal="Build Spacecraft Telemetry",
        active_step="Verify Raptor Turbopump",
        completed_steps=3,
        total_steps=5,
        tdd_passed=8,
        tdd_failed=0,
        active_negative_constraints=["DO NOT use blocking I/O"],
        fast_path_latency_ms=2.45,
        model_name="qwen3.8",
    )

    panel = FlightDeckRenderer.render_panel(state)
    assert panel is not None
    assert "ANTIGRAVITY-K FLIGHT DECK" in panel.title
