"""ModelRoutingPolicy 비용 상한 테스트.

config.yaml router.model_policy의 max_cost_per_1k_tokens_usd가
모델 비용(cost_per_1k_tokens_usd) 상한을 넘는 후보를 라우팅에서
제외하는지 검증한다. 비용 미설정(0.0) 모델은 오탐 방지를 위해 통과한다.
"""

from typing import cast

from antigravity_k.engine.model_policy import ModelRoutingPolicy
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelRouter


def _profile(name: str, cost: float) -> ModelProfile:
    return ModelProfile(
        name=name,
        repo=name,
        role="reasoning",
        cost_per_1k_tokens_usd=cost,
    )


def _policy(**overrides: object) -> ModelRoutingPolicy:
    raw: dict[str, object] = {
        "enabled": True,
        "prefer_local": False,
        "max_cost_per_1k_tokens_usd": 0.005,
    }
    raw.update(overrides)
    return ModelRoutingPolicy.from_mapping(raw)


def _router_policy(router: ModelRouter) -> ModelRoutingPolicy:
    return cast(ModelRoutingPolicy, cast(object, getattr(router, "_model_policy")))


def test_cost_below_cap_is_allowed() -> None:
    decision = _policy().decide(_profile("openai/gpt-4o-mini", 0.000375))
    assert decision.allowed is True
    assert decision.reason == "eligible"


def test_cost_above_cap_is_rejected() -> None:
    decision = _policy().decide(_profile("openai/gpt-4o", 0.00625))
    assert decision.allowed is False
    assert decision.reason == "cost_cap_exceeded"


def test_unknown_cost_passes_even_with_cap() -> None:
    # 비용 미설정(0.0) 모델은 상한과 무관하게 통과 — 오탐 차단 없음
    decision = _policy().decide(_profile("vendor/unknown-model", 0.0))
    assert decision.allowed is True


def test_no_cap_allows_expensive_model() -> None:
    decision = _policy(max_cost_per_1k_tokens_usd=0.0).decide(_profile("openai/gpt-4o", 0.00625))
    assert decision.allowed is True


def test_disabled_policy_skips_cost_check() -> None:
    decision = _policy(enabled=False).decide(_profile("openai/gpt-4o", 0.00625))
    assert decision.allowed is True
    assert decision.reason == "policy_disabled"


def test_from_mapping_to_dict_roundtrip_includes_cost_cap() -> None:
    policy = _policy(max_cost_per_1k_tokens_usd=0.005)
    assert policy.to_dict()["max_cost_per_1k_tokens_usd"] == 0.005
    assert ModelRoutingPolicy.from_mapping(policy.to_dict()) == policy


def test_router_excludes_over_budget_models_from_config() -> None:
    registry = ModelRegistry("config.yaml")
    router = ModelRouter(registry)
    policy = _router_policy(router)
    # config의 비용 상한(0.005) 기준: gpt-4o(0.00625)/claude-opus-4(0.045) 제외,
    # gpt-4o-mini(0.000375)/qwen3-next(0.00045) 통과
    assert policy.max_cost_per_1k_tokens_usd == 0.005
    gpt4o = registry.get_model("openai/gpt-4o")
    assert gpt4o is not None
    decision = policy.decide(gpt4o)
    assert decision.allowed is False
    assert decision.reason == "cost_cap_exceeded"
    gpt4o_mini = registry.get_model("openai/gpt-4o-mini")
    assert gpt4o_mini is not None
    assert policy.decide(gpt4o_mini).allowed is True
    qwen = registry.get_model("qwen3.8")
    assert qwen is not None
    assert policy.decide(qwen).allowed is True


def test_large_local_models_are_not_rejected_by_parameter_cap() -> None:
    policy = ModelRoutingPolicy(
        enabled=True,
        max_parameter_count_b=70.0,
        min_local_parameter_count_b=20.0,
    )
    large_local = ModelProfile(
        name="Qwen3.8-Flash-Next-GGUF-UD-IQ4_XS",
        repo="unsloth/Qwen3.8-Flash-Next-GGUF",
        role="reasoning",
        provider="unsloth",
        estimated_memory_gb=87.25,
        parameter_count_b=87.25,
    )
    assert large_local.is_local is True
    decision = policy.decide(large_local)
    assert decision.allowed is True
    assert decision.reason == "eligible"

