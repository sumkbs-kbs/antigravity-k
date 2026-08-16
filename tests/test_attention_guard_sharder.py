"""Unit tests for AttentionGuardSharder."""

from antigravity_k.engine.attention_guard_sharder import AttentionGuardSharder


def test_sandwich_pinning_structure():
    sys_rules = "You are an autonomous senior engineer."
    body = "Here is 500 lines of source code..."
    constraints = ["DO NOT use eval()", "DO NOT delete database"]
    objective = "Refactor payment service"

    sharded = AttentionGuardSharder.create_sandwich_prompt(sys_rules, body, constraints, objective)

    assert "PRIMACY_ATTENTION_BLOCK" in sharded.primacy_block
    assert "RECENCY_ATTENTION_ANCHOR" in sharded.recency_anchor
    assert "DO NOT use eval()" in sharded.recency_anchor
    assert "Objective: Refactor payment service" in sharded.recency_anchor
    # Verify sandwich order
    assert sharded.full_prompt.startswith("<!-- PRIMACY_ATTENTION_BLOCK")
    assert sharded.full_prompt.endswith("<!-- END_RECENCY_ANCHOR -->")
