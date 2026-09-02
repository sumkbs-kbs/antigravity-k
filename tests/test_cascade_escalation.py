"""테스트: Cascading-on-low-confidence 에스컬레이션.

낮은 신뢰도 응답이 상위 티어 모델로 자동 재생성되는지, 그리고 비활성 시/최고
티어 도달 시 안전하게 정지하는지 검증한다. 이것은 "작은 모델로 프론티어 근접"
목표의 핵심 메커니즘이 실제로 연결되어 동작함을 증명한다.
"""

from typing import cast

from antigravity_k.engine.model_manager import LoadedModel, ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker


class _MemoryConfigDouble:
    max_loaded_gb: int = 1000
    auto_unload: bool = False
    unload_cooldown_sec: float = 300.0


class _RegistryDouble:
    memory_config: _MemoryConfigDouble
    _raw: dict[str, object]
    _profiles: dict[str, ModelProfile]

    def __init__(self) -> None:
        self.memory_config = _MemoryConfigDouble()
        self._raw = {}
        self._profiles = {
            "light-4b": ModelProfile(name="light-4b", repo="t", role="test", estimated_memory_gb=1),
            "mid-24b": ModelProfile(name="mid-24b", repo="t", role="test", estimated_memory_gb=1),
            "heavy-72b": ModelProfile(name="heavy-72b", repo="t", role="test", estimated_memory_gb=1),
        }

    def get_model(self, name: str) -> ModelProfile | None:
        return self._profiles.get(name)

    def list_models(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def model_exists(self, name: str) -> bool:
        return name in self._profiles


def _make_registry() -> ModelRegistry:
    registry = _RegistryDouble()
    return cast(ModelRegistry, cast(object, registry))


def _make_manager(
    responses: dict[str, str],
    cascade_on: bool,
    threshold: float = 0.4,
    max_esc: int = 2,
) -> ModelManager:
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
    return _attach_generator(manager, responses)


def _attach_generator(manager: ModelManager, responses: dict[str, str]) -> ModelManager:
    calls: list[str] = []

    def fake_load(_profile: ModelProfile) -> tuple[object, object]:
        return object(), object()

    def fake_generate(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        del prompt, kwargs
        name = loaded.profile.name
        calls.append(name)
        return responses.get(name, "fallback")

    setattr(manager, "_load_mlx_model", fake_load)
    setattr(manager, "_do_generate", fake_generate)
    setattr(manager, "calls", calls)
    return manager


def _calls(manager: ModelManager) -> list[str]:
    return cast(list[str], getattr(manager, "calls"))


def test_cascade_disabled_keeps_low_confidence_response():
    # 짧은 응답 = 신뢰도 낮음 (estimate_confidence < 0.2 for len < 20)
    manager = _make_manager({"light-4b": "짧음"}, cascade_on=False)
    result = manager.generate("질문", "cascade-stack")
    assert result == "짧음"
    assert _calls(manager) == ["light-4b"]


def test_cascade_enabled_escalates_on_low_confidence():
    manager = _make_manager(
        {"light-4b": "짧음", "mid-24b": "충분히 길고 구체적이며 상세한 정답입니다." * 3}, cascade_on=True
    )
    result = manager.generate("질문", "cascade-stack")
    assert "mid-24b" in _calls(manager)
    assert result != "짧음"


def test_cascade_keeps_high_confidence_response():
    long_good = "이것은 매우 상세하고 구체적이며 정보가 풍부한 정답입니다. " * 6
    manager = _make_manager({"light-4b": long_good}, cascade_on=True)
    result = manager.generate("질문", "cascade-stack")
    assert result.strip() == long_good.strip()
    assert _calls(manager) == ["light-4b"]


def test_cascade_stops_at_top_tier():
    # 모든 티어가 낮은 신뢰도 → 최고 티어에서 정지 (escalate None)
    manager = _make_manager(
        {"light-4b": "짧", "mid-24b": "짧", "heavy-72b": "짧"},
        cascade_on=True,
        max_esc=5,
    )
    _ = manager.generate("질문", "cascade-stack")
    # 최고 티어까지 에스컬레이션 후 정지
    assert _calls(manager)[-1] == "heavy-72b"


def test_cascade_respects_max_escalations():
    manager = _make_manager(
        {"light-4b": "짧", "mid-24b": "짧", "heavy-72b": "충분히 길고 구체적입니다. " * 4},
        cascade_on=True,
        max_esc=1,
    )
    _ = manager.generate("질문", "cascade-stack")
    # max_esc=1 이면 light→mid 한 번만 에스컬레이션 가능
    assert "heavy-72b" not in _calls(manager)


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

    manager = _attach_generator(
        ModelManager(registry=registry, router=router, tracker=UsageTracker(db_path=None)),
        {"light-4b": "짧"},
    )
    result = manager.generate("질문", "fallback-stack")
    assert result == "짧"
