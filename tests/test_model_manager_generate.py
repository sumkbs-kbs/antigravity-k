"""테스트: 모델 매니저 추론 및 라우팅 연동.
======================================
ModelManager.generate() 가 ModelRouter의 폴백 전략과 UsageTracker의 통계 기록을 정상적으로 처리하는지 검증.
"""

from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker


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
    combo = ModelCombo(
        name="fallback-combo",
        models=["model-a", "model-b", "model-c"],
        strategy=RouteStrategy.FALLBACK,
    )
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
    assert recent[0].combo_name == ""


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


def test_generate_collective_combo_runs_council(setup_manager):
    manager = setup_manager
    manager.router.register_combo(
        ModelCombo(
            name="collective-council",
            models=["model-a", "model-b"],
            strategy=RouteStrategy.COLLECTIVE,
        )
    )
    manager.router.register_combo(
        ModelCombo(
            name="critic-swarm",
            models=["model-c"],
            strategy=RouteStrategy.FALLBACK,
        )
    )
    manager.router.register_combo(
        ModelCombo(
            name="supreme-court",
            models=["model-b"],
            strategy=RouteStrategy.FALLBACK,
        )
    )
    manager._registry._raw = {
        "collective_intelligence": {
            "min_participants": 2,
            "max_proposers": 2,
            "max_critics": 1,
            "critic_combo": "critic-swarm",
            "arbiter_combo": "supreme-court",
            "expose_trace": True,
        }
    }

    def do_generate_side_effect(loaded, prompt, **kwargs):
        if "최종 합성" in prompt:
            return "최종 합성 답변"
        if "비판 라운드" in prompt:
            return "비판 내용"
        return f"후보 답변: {loaded.profile.name}"

    manager._do_generate.side_effect = do_generate_side_effect

    res = manager.generate("테스트 요청", "collective-council")

    assert "집단지성" in res
    assert "최종 합성 답변" in res
    called_prompts = [call.args[1] for call in manager._do_generate.call_args_list]
    assert any("제안 라운드" in prompt for prompt in called_prompts)
    assert any("비판 라운드" in prompt for prompt in called_prompts)
    assert any("최종 합성" in prompt for prompt in called_prompts)


def test_get_target_for_role_prefers_agent_model_combo(setup_manager):
    manager = setup_manager
    manager._registry._raw = {
        "agent_models": {
            "WORKER": "coding-swarm",
            "default": "collective-council",
        }
    }

    assert manager.get_target_for_role("WORKER", default_role="coding") == "coding-swarm"
    assert manager.get_target_for_role("QA") == "collective-council"


def test_qwen3_messages_force_no_think_mode(setup_manager):
    manager = setup_manager

    messages = manager._suppress_model_thinking(
        "hf.co/Qwen/Qwen3-30B-A3B-GGUF:Q5_K_M",
        [{"role": "user", "content": "안녕"}],
    )

    assert messages[0]["role"] == "system"
    assert "/no_think" in messages[0]["content"]
    assert "hidden reasoning" in messages[0]["content"]


def test_non_qwen3_messages_are_unchanged(setup_manager):
    manager = setup_manager
    original = [{"role": "user", "content": "안녕"}]

    messages = manager._suppress_model_thinking("deepseek-r1:32b", original)

    assert messages is original


def test_generate_strips_hidden_reasoning_blocks(setup_manager):
    manager = setup_manager
    manager._do_generate.return_value = "<think>private reasoning</think>\n최종 답변입니다."

    res = manager.generate("Hello", "model-a")

    assert res == "최종 답변입니다."


def test_strip_legacy_thinking_process_block(setup_manager):
    manager = setup_manager
    text = "--- Thinking Process ---\nprivate plan\n--- End of Thinking* ---\n공개 답변"

    assert manager._strip_hidden_reasoning(text) == "공개 답변"
