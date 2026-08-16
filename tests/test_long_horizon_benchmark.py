from antigravity_k.engine.benchmark_cases import get_suite


def test_long_horizon_suite_contains_recovery_orchestration_case():
    cases = get_suite("long_horizon")

    assert cases
    assert all(case.category == "long_horizon" for case in cases)
    assert any("checkpoint" in case.prompt.lower() for case in cases)
    assert any("recovery" in case.prompt.lower() for case in cases)


def test_long_horizon_cases_are_high_difficulty_and_have_acceptance_signals():
    cases = get_suite("long_horizon")

    assert all(case.difficulty >= 4 for case in cases)
    assert all(case.expected_keywords for case in cases)
