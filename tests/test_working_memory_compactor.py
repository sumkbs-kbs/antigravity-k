"""Unit tests for WorkingMemoryCompactor."""

from antigravity_k.engine.working_memory_compactor import WorkingMemoryCompactor


def test_working_memory_compaction():
    # Simulate a long 15-message trajectory
    messages = [
        {"role": "user", "content": "Let's update src/auth/jwt.py and tests/test_jwt.py"},
        {"role": "assistant", "content": "I will read src/auth/jwt.py and configure RSA keys"},
        {"role": "user", "content": "Also check config.yaml and policy.yaml"},
    ]

    adrs = [
        "ADR-001: Use RS256 for all JWT tokens",
        "ADR-002: Disallow plain text tokens in logs",
    ]

    pending = ["Implement token refresh endpoint"]

    state = WorkingMemoryCompactor.compact(messages, adrs=adrs, pending_subgoals=pending)
    pinned_block = state.format_pinned_working_memory()

    assert "PINNED_WORKING_MEMORY_STATE" in pinned_block
    assert "ADR-001: Use RS256" in pinned_block
    assert "src/auth/jwt.py" in pinned_block
    assert "Implement token refresh endpoint" in pinned_block
