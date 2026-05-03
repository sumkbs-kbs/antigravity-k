"""
테스트: 모델 매니저 추론 및 라우팅 연동
======================================
ModelManager.generate() 가 ModelRouter의 폴백 전략과 UsageTracker의 통계 기록을 정상적으로 처리하는지 검증.
"""
import pytest
from unittest.mock import MagicMock, patch

from antigravity_k.engine.model_registry import ModelRegistry, ModelProfile
from antigravity_k.engine.model_router import ModelRouter, ModelCombo, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker
from antigravity_k.engine.model_manager import ModelManager


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=ModelRegistry)
    # 메모리 설정 (테스트에서는 무한대)
    registry.memory_config = MagicMock()
    registry.memory_config.max_loaded_gb = 1000
    registry.memory_config.auto_unload = False
    
    profiles = {
        "model-a": ModelProfile(name="model-a", repo="test", role="test", estimated_memory_gb=1),
        "model-b": ModelProfile(name="model-b", repo="test", role="test", estimated_memory_gb=1),
        "model-c": ModelProfile(name="model-c", repo="test", role="test", estimated_memory_gb=1),
    }
    registry.get_model.side_effect = lambda x: profiles.get(x)
    registry.list_models.return_value = list(profiles.values())
    return registry


@pytest.fixture
def setup_manager(mock_registry):
    router = ModelRouter(mock_registry)
    combo = ModelCombo(name="fallback-combo", models=["model-a", "model-b", "model-c"], strategy=RouteStrategy.FALLBACK)
    router.register_combo(combo)
    
    tracker = UsageTracker(db_path=None)
    
    manager = ModelManager(registry=mock_registry, router=router, tracker=tracker)
    
    # 더미 _load_mlx_model를 모킹하여 실제 로드를 건너뜀
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    # 내부 텍스트 생성 _do_generate 모킹
    manager._do_generate = MagicMock(return_value="Mock response")
    
    return manager


def test_generate_single_model(setup_manager):
    manager = setup_manager
    res = manager.generate("Hello", "model-a")
    
    assert res == "Mock response"
    manager._do_generate.assert_called_once()
    
    # 사용량 기록 확인
    recent = manager.tracker.get_recent(1)
    assert len(recent) == 1
    assert recent[0].model_name == "model-a"
    assert recent[0].success is True
    assert recent[0].combo_name is None


def test_generate_fallback_combo_success(setup_manager):
    manager = setup_manager
    res = manager.generate("Hello", "fallback-combo")
    
    assert res == "Mock response"
    
    # 사용량 기록 확인 (첫 번째 모델인 model-a 사용됨)
    recent = manager.tracker.get_recent(1)
    assert recent[0].model_name == "model-a"
    assert recent[0].combo_name == "fallback-combo"
    assert recent[0].fallback_depth == 0


def test_generate_fallback_on_failure(setup_manager):
    manager = setup_manager
    
    # 첫 번째 호출에서 의도적으로 실패 유도
    def do_generate_side_effect(loaded, prompt, **kwargs):
        if loaded.profile.name == "model-a":
            raise RuntimeError("API Timeout")
        return "Fallback response"
        
    manager._do_generate.side_effect = do_generate_side_effect
    
    res = manager.generate("Hello", "fallback-combo")
    
    assert res == "Fallback response"
    
    # 사용량 기록 확인 (model-a는 실패, model-b는 성공이어야 함)
    records = manager.tracker.get_recent(2)
    assert len(records) == 2
    # 최근 기록이 model-b 성공
    assert records[0].model_name == "model-b"
    assert records[0].success is True
    assert records[0].fallback_depth == 1
    assert records[0].combo_name == "fallback-combo"
    
    # 그 이전 기록이 model-a 실패
    assert records[1].model_name == "model-a"
    assert records[1].success is False
    assert records[1].error == "API Timeout"
    
    # 라우터 상태 확인 (model-a는 쿨다운 중이어야 함)
    assert len(manager.router.status()["unavailable"]) > 0
    assert not manager.router._tracker.is_available("model-a")
