from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

from antigravity_k.engine.model_manager import LoadedModel, ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker


def _assert_called_once(manager: ModelManager, method_name: str) -> None:
    method = cast(MagicMock, getattr(manager, method_name))
    callback = cast(Callable[[], object], getattr(method, "assert_called_once"))
    _ = callback()


def _make_registry() -> ModelRegistry:
    registry = MagicMock(spec=ModelRegistry)
    setattr(
        registry,
        "memory_config",
        SimpleNamespace(max_loaded_gb=1000, auto_unload=False, unload_cooldown_sec=30),
    )
    profiles = {
        "qwen3.6:latest": ModelProfile(
            name="qwen3.6:latest",
            repo="qwen3.6:latest",
            role="reasoning",
            parameter_count_b=35,
        ),
        "worker-4b": ModelProfile(
            name="worker-4b",
            repo="test/worker",
            role="reasoning",
            parameter_count_b=4,
        ),
        "judge-24b": ModelProfile(
            name="judge-24b",
            repo="test/judge",
            role="reasoning",
            parameter_count_b=24,
        ),
        "heavy-72b": ModelProfile(
            name="heavy-72b",
            repo="test/heavy",
            role="reasoning",
            parameter_count_b=72,
        ),
        "remote-26b": ModelProfile(
            name="remote-26b",
            repo="remote/model",
            role="reasoning",
            provider="openrouter",
        ),
    }
    def get_profile(name: str) -> ModelProfile | None:
        return profiles.get(name)

    setattr(registry, "get_model", get_profile)
    setattr(registry, "list_models", lambda: list(profiles.values()))
    setattr(registry, "_raw", {})
    return cast(ModelRegistry, registry)


def test_router_selects_only_20b_or_larger_evaluator():
    registry = _make_registry()
    router = ModelRouter(registry)

    selected = router.select_confidence_evaluator()
    assert selected is not None
    assert selected.name == "qwen3.6:latest"
    assert router.select_confidence_evaluator("worker-4b") is None


def test_router_prefers_configured_large_evaluator():
    registry = _make_registry()
    setattr(registry, "_raw", {
        "router": {
            "confidence_evaluator_model": "heavy-72b",
            "confidence_evaluator_min_params_b": 20,
        }
    })
    router = ModelRouter(registry)

    selected = router.select_confidence_evaluator()

    assert selected is not None
    assert selected.name == "heavy-72b"


def test_router_infers_remote_model_size_from_name():
    registry = _make_registry()
    router = ModelRouter(registry)

    selected = router.select_confidence_evaluator("remote-26b")

    assert selected is not None
    assert selected.name == "remote-26b"


def test_parse_confidence_score_accepts_machine_readable_score():
    assert ModelRouter.parse_confidence_score('{"score": 0.82}') == 0.82
    assert ModelRouter.parse_confidence_score('{"confidence": 0.31}') == 0.31
    assert ModelRouter.parse_confidence_score("Score should be 1.0.") == 1.0
    assert ModelRouter.parse_confidence_score("0.73") == 0.73
    assert ModelRouter.parse_confidence_score("The instruction says score=0.0.") is None
    assert ModelRouter.parse_confidence_score("not-json") is None


def test_cascade_uses_large_evaluator_before_escalation():
    registry = _make_registry()
    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="cascade-stack",
            models=["worker-4b", "heavy-72b"],
            strategy=RouteStrategy.CASCADING,
        )
    )
    router.cascade_on_low_confidence = True
    router.cascade_confidence_threshold = 0.5
    router.cascade_max_escalations = 1
    router.confidence_evaluator_enabled = True
    router.confidence_evaluator_model = "judge-24b"

    manager = ModelManager(
        registry=registry,
        router=router,
        tracker=UsageTracker(db_path=None),
    )
    setattr(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
    calls: list[str] = []

    def fake_generate(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> str:
        calls.append(loaded.profile.name)
        if loaded.profile.name == "judge-24b":
            return '{"score": 0.9}'
        return "짧은 응답"

    setattr(manager, "_do_generate", MagicMock(side_effect=fake_generate))

    result = manager.generate("질문", "cascade-stack")

    assert result == "짧은 응답"
    assert calls == ["worker-4b", "judge-24b"]


def test_qwen_evaluator_uses_native_ollama_stream():
    registry = _make_registry()
    qwen = registry.get_model("qwen3.6:latest")
    assert qwen is not None
    qwen.provider = "ollama"
    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="cascade-stack",
            models=["worker-4b", "heavy-72b"],
            strategy=RouteStrategy.CASCADING,
        )
    )
    router.cascade_on_low_confidence = True
    router.cascade_confidence_threshold = 0.5
    router.cascade_max_escalations = 1
    router.confidence_evaluator_enabled = True
    router.confidence_evaluator_model = "qwen3.6:latest"

    manager = ModelManager(
        registry=registry,
        router=router,
        tracker=UsageTracker(db_path=None),
    )
    setattr(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
    setattr(manager, "_do_generate", MagicMock(return_value="짧은 응답"))
    setattr(manager, "_do_stream_generate", MagicMock(return_value=iter(["0.9"])))

    result = manager.generate("질문", "cascade-stack")

    assert result == "짧은 응답"
    _assert_called_once(manager, "_do_stream_generate")
    _assert_called_once(manager, "_do_generate")


def test_cascade_falls_back_to_heuristic_when_large_evaluator_is_invalid():
    registry = _make_registry()
    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="cascade-stack",
            models=["worker-4b", "heavy-72b"],
            strategy=RouteStrategy.CASCADING,
        )
    )
    router.cascade_on_low_confidence = True
    router.cascade_confidence_threshold = 0.5
    router.cascade_max_escalations = 1
    router.confidence_evaluator_enabled = True
    router.confidence_evaluator_model = "judge-24b"

    manager = ModelManager(
        registry=registry,
        router=router,
        tracker=UsageTracker(db_path=None),
    )
    setattr(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
    calls: list[str] = []

    def fake_generate(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> str:
        calls.append(loaded.profile.name)
        if loaded.profile.name == "judge-24b":
            return "invalid"
        if loaded.profile.name == "heavy-72b":
            return "충분히 구체적인 최종 응답입니다. " * 5
        return "짧은 응답"

    setattr(manager, "_do_generate", MagicMock(side_effect=fake_generate))

    result = manager.generate("질문", "cascade-stack")

    assert "구체적인 최종 응답" in result
    assert calls == ["worker-4b", "judge-24b", "heavy-72b"]
