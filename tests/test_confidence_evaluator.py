from unittest.mock import MagicMock

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker


def _make_registry() -> MagicMock:
    registry = MagicMock(spec=ModelRegistry)
    registry.memory_config = MagicMock()
    registry.memory_config.max_loaded_gb = 1000
    registry.memory_config.auto_unload = False
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
    registry.get_model.side_effect = lambda name: profiles.get(name)
    registry.list_models.return_value = list(profiles.values())
    registry._raw = {}
    return registry


def test_router_selects_only_20b_or_larger_evaluator():
    registry = _make_registry()
    router = ModelRouter(registry)

    selected = router.select_confidence_evaluator()
    assert selected is not None
    assert selected.name == "qwen3.6:latest"
    assert router.select_confidence_evaluator("worker-4b") is None


def test_router_prefers_configured_large_evaluator():
    registry = _make_registry()
    registry._raw = {
        "router": {
            "confidence_evaluator_model": "heavy-72b",
            "confidence_evaluator_min_params_b": 20,
        }
    }
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
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    calls = []

    def fake_generate(loaded, prompt, **kwargs):
        calls.append(loaded.profile.name)
        if loaded.profile.name == "judge-24b":
            return '{"score": 0.9}'
        return "짧은 응답"

    manager._do_generate = MagicMock(side_effect=fake_generate)

    result = manager.generate("질문", "cascade-stack")

    assert result == "짧은 응답"
    assert calls == ["worker-4b", "judge-24b"]


def test_qwen_evaluator_uses_native_ollama_stream():
    registry = _make_registry()
    registry.get_model("qwen3.6:latest").provider = "ollama"
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
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    manager._do_generate = MagicMock(return_value="짧은 응답")
    manager._do_stream_generate = MagicMock(return_value=iter(["0.9"]))

    result = manager.generate("질문", "cascade-stack")

    assert result == "짧은 응답"
    manager._do_stream_generate.assert_called_once()
    manager._do_generate.assert_called_once()


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
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    calls = []

    def fake_generate(loaded, prompt, **kwargs):
        calls.append(loaded.profile.name)
        if loaded.profile.name == "judge-24b":
            return "invalid"
        if loaded.profile.name == "heavy-72b":
            return "충분히 구체적인 최종 응답입니다. " * 5
        return "짧은 응답"

    manager._do_generate = MagicMock(side_effect=fake_generate)

    result = manager.generate("질문", "cascade-stack")

    assert "구체적인 최종 응답" in result
    assert calls == ["worker-4b", "judge-24b", "heavy-72b"]
