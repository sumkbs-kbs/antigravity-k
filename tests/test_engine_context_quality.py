"""Tests for EngineContext quality gate configuration wiring."""

from antigravity_k.engine.engine_context import quality_gate_from_config


def test_quality_gate_retry_budget_comes_from_raw_config() -> None:
    # Given: config.yaml declares the measured revision retry budget.
    raw_config = {"quality_gate": {"max_retries": 2}}

    # When: the context builds its quality gate.
    gate = quality_gate_from_config(raw_config)

    # Then: the production gate can revise twice before failing.
    assert gate.max_retries == 2


def test_quality_gate_keeps_safe_default_without_config() -> None:
    # Given: an older config omits the quality gate section.
    gate = quality_gate_from_config({})

    # Then: one revision remains available without requiring migration.
    assert gate.max_retries == 1
