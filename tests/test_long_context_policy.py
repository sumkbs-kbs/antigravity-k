from antigravity_k.engine.context_budget import ContextBudget
from antigravity_k.engine.long_context_capabilities import LongContextCapability
from antigravity_k.engine.long_context_policy import build_long_context_plan


def test_fallback_plan_reserves_budget_for_retrieved_context() -> None:
    capability: LongContextCapability = {
        "strategy": "retrieval_fallback",
        "native_sparse_attention": "unknown",
        "native_linear_attention": "unknown",
        "kv_cache_compression": "unknown",
    }
    budget = ContextBudget(
        token_limit=10_000,
        trajectory_max_messages=40,
        trajectory_max_chars=80_000,
    )

    plan = build_long_context_plan(capability, budget)

    assert plan["strategy"] == "retrieval_fallback"
    assert plan["retrieval_mode"] == "long_context"
    assert plan["native_attention_enabled"] is False
    assert plan["context_token_limit"] == 8_000
    assert plan["candidate_pool"] == 78


def test_native_plan_keeps_backend_context_budget() -> None:
    capability: LongContextCapability = {
        "strategy": "native",
        "native_sparse_attention": "supported",
        "native_linear_attention": "unsupported",
        "kv_cache_compression": "supported",
    }
    budget = ContextBudget(
        token_limit=16_000,
        trajectory_max_messages=62,
        trajectory_max_chars=80_000,
        kv_cache_byte_limit=4_000_000,
    )

    plan = build_long_context_plan(capability, budget)

    assert plan["strategy"] == "native"
    assert plan["retrieval_mode"] == "native"
    assert plan["native_attention_enabled"] is True
    assert plan["kv_cache_mode"] == "backend_managed"
    assert plan["kv_cache_compression_enabled"] is True
    assert plan["context_token_limit"] == 16_000
    assert plan["candidate_pool"] == 0


def test_unavailable_plan_does_not_claim_executable_long_context() -> None:
    capability: LongContextCapability = {
        "strategy": "unavailable",
        "native_sparse_attention": "unsupported",
        "native_linear_attention": "unsupported",
        "kv_cache_compression": "unsupported",
    }
    budget = ContextBudget(
        token_limit=8_000,
        trajectory_max_messages=40,
        trajectory_max_chars=80_000,
    )

    plan = build_long_context_plan(capability, budget)

    assert plan["strategy"] == "unavailable"
    assert plan["native_attention_enabled"] is False
    assert plan["kv_cache_compression_enabled"] is False
    assert plan["candidate_pool"] == 0
