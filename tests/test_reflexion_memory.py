"""Unit tests for ReflexionMemory."""

from antigravity_k.engine.reflexion_memory import ReflexionMemory


def test_reflexion_record_and_render():
    memory = ReflexionMemory(max_episodes=3)

    memory.record_failure(
        context="Calculating average",
        attempted_action="dividing by len(items)",
        failure_reason="ZeroDivisionError when items is empty",
        suggested_alternative="check if items is empty first",
    )

    prompt = memory.render_negative_constraints_prompt()
    assert "NEGATIVE_CONSTRAINTS" in prompt
    assert "DO NOT attempt 'dividing by len(items)'" in prompt
    assert "check if items is empty first" in prompt


def test_reflexion_max_capacity():
    memory = ReflexionMemory(max_episodes=2)
    memory.record_failure("c1", "a1", "r1")
    memory.record_failure("c2", "a2", "r2")
    memory.record_failure("c3", "a3", "r3")

    assert len(memory.episodes) == 2
    assert memory.episodes[-1].attempted_action == "a3"
