"""테스트: 스마트 모델 라우터.
========================
9Router 패턴의 폴백/라운드로빈/로드밸런싱 전략 테스트.
"""

import time
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.model_registry import ModelProfile
from antigravity_k.engine.model_router import (
    AllModelsUnavailableError,
    ComboNotFoundError,
    ModelCombo,
    ModelRouter,
    RouteStrategy,
    UnavailabilityTracker,
)

# ─── 픽스처 ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_registry():
    """모델 3개가 등록된 Mock 레지스트리."""
    registry = MagicMock()
    registry._raw = {}  # combos 섹션 없음 (수동 등록 테스트)

    profiles = {
        "qwen3-72b": ModelProfile(
            name="qwen3-72b",
            repo="test/qwen3",
            role="reasoning",
            estimated_memory_gb=40,
            context_length=32768,
        ),
        "qwen-coder-32b": ModelProfile(
            name="qwen-coder-32b",
            repo="test/coder",
            role="coding",
            estimated_memory_gb=18,
            context_length=32768,
        ),
        "llama4-scout": ModelProfile(
            name="llama4-scout",
            repo="test/llama",
            role="reasoning",
            estimated_memory_gb=10,
            context_length=131072,
        ),
    }
    registry.get_model = lambda name: profiles.get(name)
    registry.list_models.return_value = list(profiles.values())
    return registry


@pytest.fixture
def combo_fallback():
    return ModelCombo(
        name="coding-stack",
        models=["qwen3-72b", "qwen-coder-32b", "llama4-scout"],
        strategy=RouteStrategy.FALLBACK,
    )


@pytest.fixture
def combo_roundrobin():
    return ModelCombo(
        name="fast-response",
        models=["llama4-scout", "qwen-coder-32b"],
        strategy=RouteStrategy.ROUND_ROBIN,
    )


@pytest.fixture
def combo_loadbalance():
    return ModelCombo(
        name="reasoning-balanced",
        models=["qwen3-72b", "qwen-coder-32b", "llama4-scout"],
        strategy=RouteStrategy.LOAD_BALANCE,
    )


@pytest.fixture
def router(mock_registry, combo_fallback, combo_roundrobin, combo_loadbalance):
    r = ModelRouter(mock_registry)
    r.register_combo(combo_fallback)
    r.register_combo(combo_roundrobin)
    r.register_combo(combo_loadbalance)
    return r


# ─── UnavailabilityTracker 테스트 ────────────────────────────────────


class TestUnavailabilityTracker:
    """비가용 추적기 테스트."""

    def test_initially_available(self):
        tracker = UnavailabilityTracker()
        assert tracker.is_available("any-model") is True

    def test_mark_unavailable(self):
        tracker = UnavailabilityTracker(base_cooldown_sec=60)
        tracker.mark_unavailable("model-a", reason="OOM")
        assert tracker.is_available("model-a") is False

    def test_cooldown_expiry(self):
        tracker = UnavailabilityTracker(base_cooldown_sec=0.1)
        tracker.mark_unavailable("model-a")
        time.sleep(0.15)
        assert tracker.is_available("model-a") is True

    def test_exponential_backoff(self):
        tracker = UnavailabilityTracker(
            base_cooldown_sec=10,
            backoff_multiplier=2.0,
        )
        tracker.mark_unavailable("model-a")
        entry1 = tracker.get_entry("model-a")
        assert entry1 is not None
        assert entry1.cooldown_sec == 10  # 첫 번째

        tracker.mark_unavailable("model-a")  # 두 번째
        entry2 = tracker.get_entry("model-a")
        assert entry2 is not None
        assert entry2.cooldown_sec == 20  # 10 * 2^1

    def test_manual_recovery(self):
        tracker = UnavailabilityTracker()
        tracker.mark_unavailable("model-a")
        assert tracker.is_available("model-a") is False
        tracker.mark_available("model-a")
        assert tracker.is_available("model-a") is True

    def test_status(self):
        tracker = UnavailabilityTracker(base_cooldown_sec=600)
        tracker.mark_unavailable("model-a", reason="OOM")
        tracker.mark_unavailable("model-b", reason="Timeout")
        status = tracker.status()
        assert len(status) == 2
        assert status[0]["model"] in ("model-a", "model-b")

    def test_clear_all(self):
        tracker = UnavailabilityTracker()
        tracker.mark_unavailable("m1")
        tracker.mark_unavailable("m2")
        tracker.clear_all()
        assert tracker.is_available("m1") is True
        assert tracker.is_available("m2") is True


# ─── ModelCombo 테스트 ────────────────────────────────────────────────


class TestModelCombo:
    """모델 콤보 데이터 클래스 테스트."""

    def test_from_dict(self):
        combo = ModelCombo.from_dict(
            "test",
            {
                "models": ["a", "b", "c"],
                "strategy": "fallback",
                "description": "테스트 콤보",
            },
        )
        assert combo.name == "test"
        assert len(combo.models) == 3
        assert combo.strategy == RouteStrategy.FALLBACK
        assert combo.description == "테스트 콤보"

    def test_invalid_strategy_fallback(self):
        combo = ModelCombo.from_dict(
            "test",
            {
                "models": ["a"],
                "strategy": "unknown",
            },
        )
        assert combo.strategy == RouteStrategy.FALLBACK  # 기본값

    def test_round_robin_strategy(self):
        combo = ModelCombo.from_dict(
            "test",
            {
                "models": ["a", "b"],
                "strategy": "round-robin",
            },
        )
        assert combo.strategy == RouteStrategy.ROUND_ROBIN

    def test_collective_strategy(self):
        combo = ModelCombo.from_dict(
            "test",
            {
                "models": ["a", "b", "c"],
                "strategy": "collective",
            },
        )
        assert combo.strategy == RouteStrategy.COLLECTIVE


# ─── ModelRouter: 폴백 전략 테스트 ───────────────────────────────────


class TestFallbackRouting:
    """폴백 전략 테스트."""

    def test_selects_first_available(self, router):
        profile = router.route("coding-stack")
        assert profile.name == "qwen3-72b"  # 첫 번째 모델

    def test_skips_unavailable(self, router):
        router.mark_failure("qwen3-72b", "OOM")
        profile = router.route("coding-stack")
        assert profile.name == "qwen-coder-32b"  # 두 번째 모델

    def test_all_unavailable_raises(self, router):
        router.mark_failure("qwen3-72b")
        router.mark_failure("qwen-coder-32b")
        router.mark_failure("llama4-scout")
        with pytest.raises(AllModelsUnavailableError):
            router.route("coding-stack")

    def test_recovery_after_cooldown(self, router):
        router._tracker = UnavailabilityTracker(base_cooldown_sec=0.1)
        router.mark_failure("qwen3-72b")
        time.sleep(0.15)
        profile = router.route("coding-stack")
        assert profile.name == "qwen3-72b"  # 쿨다운 후 복구


# ─── ModelRouter: 라운드로빈 전략 테스트 ─────────────────────────────


class TestRoundRobinRouting:
    """라운드로빈 전략 테스트."""

    def test_cycles_through_models(self, router):
        p1 = router.route("fast-response")
        p2 = router.route("fast-response")
        p3 = router.route("fast-response")
        # 2개 모델이 순환되어야 함
        assert p1.name != p2.name
        assert p3.name == p1.name  # 다시 처음으로

    def test_skips_unavailable_in_rotation(self, router):
        router.mark_failure("llama4-scout")
        profile = router.route("fast-response")
        assert profile.name == "qwen-coder-32b"


# ─── ModelRouter: 로드밸런싱 전략 테스트 ─────────────────────────────


class TestLoadBalanceRouting:
    """로드밸런싱 전략 테스트."""

    def test_selects_lightest_model(self, router):
        profile = router.route("reasoning-balanced")
        # llama4-scout가 10GB로 가장 가벼움
        assert profile.name == "llama4-scout"

    def test_skips_unavailable_lightest(self, router):
        router.mark_failure("llama4-scout")
        profile = router.route("reasoning-balanced")
        # 다음 가벼운 모델 선택 (qwen-coder-32b: 18GB)
        assert profile.name == "qwen-coder-32b"


# ─── ModelRouter: 관리 API 테스트 ────────────────────────────────────


class TestRouterManagement:
    """라우터 관리 API 테스트."""

    def test_combo_not_found(self, router):
        with pytest.raises(ComboNotFoundError):
            router.route("nonexistent-combo")

    def test_register_unregister(self, mock_registry):
        r = ModelRouter(mock_registry)
        combo = ModelCombo(name="test", models=["qwen3-72b"])
        r.register_combo(combo)
        assert r.get_combo("test") is not None
        assert r.unregister_combo("test") is True
        assert r.get_combo("test") is None

    def test_list_combos(self, router):
        combos = router.list_combos()
        assert len(combos) == 3

    def test_status(self, router):
        status = router.status()
        assert "combos" in status
        assert "unavailable" in status
        assert len(status["combos"]) == 3

    def test_summary(self, router):
        summary = router.summary()
        assert "Model Router" in summary
        assert "coding-stack" in summary

    def test_route_single(self, router):
        profile = router.route_single("qwen3-72b")
        assert profile.name == "qwen3-72b"

    def test_mark_recovered(self, router):
        router.mark_failure("qwen3-72b")
        router.mark_recovered("qwen3-72b")
        profile = router.route("coding-stack")
        assert profile.name == "qwen3-72b"

    def test_available_model_names(self, router):
        router.mark_failure("qwen3-72b")
        available = router.available_model_names("coding-stack")
        assert "qwen3-72b" not in available
        assert available == ["qwen-coder-32b", "llama4-scout"]

    def test_collective_routes_as_fallback_for_legacy_paths(self, mock_registry):
        router = ModelRouter(mock_registry)
        router.register_combo(
            ModelCombo(
                name="collective-council",
                models=["qwen3-72b", "qwen-coder-32b"],
                strategy=RouteStrategy.COLLECTIVE,
            )
        )
        profile = router.route("collective-council")
        assert profile.name == "qwen3-72b"


# ─── config.yaml 콤보 로드 테스트 ───────────────────────────────────


class TestComboAutoLoad:
    """config.yaml에서 콤보 자동 로드 테스트."""

    def test_loads_from_raw_config(self):
        registry = MagicMock()
        registry._raw = {
            "combos": {
                "auto-combo": {
                    "models": ["model-a", "model-b"],
                    "strategy": "fallback",
                }
            }
        }
        registry.get_model = lambda name: ModelProfile(
            name=name,
            repo="test",
            role="reasoning",
        )

        router = ModelRouter(registry)
        assert router.get_combo("auto-combo") is not None
        assert len(router.get_combo("auto-combo").models) == 2
