"""테스트: Cascading-on-low-confidence 에스컬레이션.

낮은 신뢰도 응답이 상위 티어 모델로 자동 재생성되는지, 그리고 비활성 시/최고
티어 도달 시 안전하게 정지하는지 검증한다. 이것은 "작은 모델로 프론티어 근접"
목표의 핵심 메커니즘이 실제로 연결되어 동작함을 증명한다.
"""

from unittest.mock import MagicMock

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker


def _make_registry():
    registry = MagicMock(spec=ModelRegistry)
    registry.memory_config = MagicMock()
    registry.memory_config.max_loaded_gb = 1000
    registry.memory_config.auto_unload = False
    profiles = {
        "light-4b": ModelProfile(name="light-4b", repo="t", role="test", estimated_memory_gb=1),
        "mid-24b": ModelProfile(name="mid-24b", repo="t", role="test", estimated_memory_gb=1),
        "heavy-72b": ModelProfile(name="heavy-72b", repo="t", role="test", estimated_memory_gb=1),
    }
    registry.get_model.side_effect = lambda x: profiles.get(x)
    registry.list_models.return_value = list(profiles.values())
    registry._raw = {}
    return registry


def _make_manager(responses, cascade_on, threshold=0.4, max_esc=2):
    registry = _make_registry()
    router = ModelRouter(registry)
    combo = ModelCombo(
        name="cascade-stack",
        models=["light-4b", "mid-24b", "heavy-72b"],
        strategy=RouteStrategy.CASCADING,
    )
    router.register_combo(combo)
    router.cascade_on_low_confidence = cascade_on
    router.cascade_confidence_threshold = threshold
    router.cascade_max_escalations = max_esc

    manager = ModelManager(registry=registry, router=router, tracker=UsageTracker(db_path=None))
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    calls = []

    def fake_generate(loaded, prompt, **kwargs):
        name = loaded.profile.name
        calls.append(name)
        return responses.get(name, "fallback")

    manager._do_generate = MagicMock(side_effect=fake_generate)
    manager.calls = calls
    return manager


def test_cascade_disabled_keeps_low_confidence_response():
    # 짧은 응답 = 신뢰도 낮음 (estimate_confidence < 0.2 for len < 20)
    manager = _make_manager({"light-4b": "짧음"}, cascade_on=False)
    result = manager.generate("질문", "cascade-stack")
    assert result == "짧음"
    assert manager.calls == ["light-4b"]


def test_cascade_enabled_escalates_on_low_confidence():
    manager = _make_manager(
        {"light-4b": "짧음", "mid-24b": "충분히 길고 구체적이며 상세한 정답입니다." * 3}, cascade_on=True
    )
    result = manager.generate("질문", "cascade-stack")
    assert "mid-24b" in manager.calls
    assert result != "짧음"


def test_cascade_keeps_high_confidence_response():
    long_good = "이것은 매우 상세하고 구체적이며 정보가 풍부한 정답입니다. " * 6
    manager = _make_manager({"light-4b": long_good}, cascade_on=True)
    result = manager.generate("질문", "cascade-stack")
    assert result.strip() == long_good.strip()
    assert manager.calls == ["light-4b"]


def test_cascade_stops_at_top_tier():
    # 모든 티어가 낮은 신뢰도 → 최고 티어에서 정지 (escalate None)
    manager = _make_manager(
        {"light-4b": "짧", "mid-24b": "짧", "heavy-72b": "짧"},
        cascade_on=True,
        max_esc=5,
    )
    manager.generate("질문", "cascade-stack")
    # 최고 티어까지 에스컬레이션 후 정지
    assert manager.calls[-1] == "heavy-72b"


def test_cascade_respects_max_escalations():
    manager = _make_manager(
        {"light-4b": "짧", "mid-24b": "짧", "heavy-72b": "충분히 길고 구체적입니다. " * 4},
        cascade_on=True,
        max_esc=1,
    )
    manager.generate("질문", "cascade-stack")
    # max_esc=1 이면 light→mid 한 번만 에스컬레이션 가능
    assert "heavy-72b" not in manager.calls


def test_non_cascading_combo_not_escalated():
    registry = _make_registry()
    router = ModelRouter(registry)
    combo = ModelCombo(
        name="fallback-stack",
        models=["light-4b", "mid-24b"],
        strategy=RouteStrategy.FALLBACK,
    )
    router.register_combo(combo)
    router.cascade_on_low_confidence = True

    manager = ModelManager(registry=registry, router=router, tracker=UsageTracker(db_path=None))
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    manager._do_generate = MagicMock(return_value="짧")
    result = manager.generate("질문", "fallback-stack")
    assert result == "짧"
