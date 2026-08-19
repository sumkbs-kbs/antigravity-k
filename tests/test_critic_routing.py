"""Critic 모델 라우팅 테스트: critic-swarm 콤보가 config에서 로드되고
CoV/집단지성 critic 역할이 해당 콤보로 라우팅되는지 검증."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.orchestrator_handlers import _cov_settings, cov_verify_handler
from antigravity_k.engine.state_graph import StateContext

COMPLEX_TASK = "복잡한 알고리즘 아키텍처 리팩토링 마이그레이션 설계 최적화 시간복잡도 분석"
LONG_AGENT_OUTPUT = (
    "아래는 요청하신 설계입니다:\n"
    "```python\n"
    "def compute(x: int) -> int:\n"
    '    """계산합니다."""\n'
    "    return x + 1\n"
    "```\n"
    "시간복잡도는 O(1)이며 구조적으로 확장 가능합니다."
)


def _registry() -> ModelRegistry:
    return ModelRegistry("config.yaml")


def test_critic_swarm_combo_loaded_from_config() -> None:
    router = ModelRouter(_registry())
    combo = router.get_combo("critic-swarm")
    assert combo is not None
    assert combo.strategy == RouteStrategy.FALLBACK
    assert combo.models[0] == "deepseek-r1:70b"
    assert "qwen3.8" in combo.models
    assert "qwen3.6:latest" in combo.models


def test_cov_settings_defaults_to_critic_swarm() -> None:
    raw = _registry()._raw
    orch = SimpleNamespace(config=raw)
    enabled, model, *_ = _cov_settings(orch)
    assert enabled is True
    assert model == "critic-swarm"


def test_generate_collective_uses_critic_swarm_critics() -> None:
    manager = ModelManager(_registry())
    # 라우팅 정책 결과와 무관하게 critic 콤보 경로를 격리 검증: 고유 콤보로 대체
    manager.router.register_combo(
        ModelCombo(
            name="critic-swarm",
            models=["deepseek-r1:70b"],
            strategy=RouteStrategy.FALLBACK,
        )
    )
    with patch("antigravity_k.engine.model_manager.CollectiveIntelligenceEngine") as engine_cls:
        engine_cls.return_value.run.return_value = "synthesized"
        result = manager.generate_collective("프로젝트 아키텍처 설계", "reasoning-swarm")
        assert result == "synthesized"
        _, kwargs = engine_cls.return_value.run.call_args
        # critic 후보는 proposer 모델이 아닌 critic-swarm 콤보 멤버에서 온다
        assert kwargs["critics"] == ["deepseek-r1:70b"]


def test_cov_handler_routes_verify_to_critic_swarm() -> None:
    orch = SimpleNamespace()
    orch.config = {
        "model": {"main_model": "qwen3.8"},
        "amplification": {"cov": {"enabled": True, "model": "critic-swarm"}},
    }
    orch.manager = MagicMock()
    orch.manager.generate.return_value = "문제 없음"
    ctx = StateContext(user_message=COMPLEX_TASK, agent_output=LONG_AGENT_OUTPUT)
    list(cov_verify_handler(ctx, orch))
    call = orch.manager.generate.call_args
    assert call is not None
    assert call.kwargs["target"] == "critic-swarm"


def test_cov_handler_routes_to_single_model_when_configured() -> None:
    orch = SimpleNamespace()
    orch.config = {
        "model": {"main_model": "qwen3.8"},
        "amplification": {"cov": {"enabled": True, "model": "mlx-community/qwen3.6-4bit"}},
    }
    orch.manager = MagicMock()
    orch.manager.generate.return_value = "문제 없음"
    ctx = StateContext(user_message=COMPLEX_TASK, agent_output=LONG_AGENT_OUTPUT)
    list(cov_verify_handler(ctx, orch))
    call = orch.manager.generate.call_args
    assert call is not None
    assert call.kwargs["target"] == "mlx-community/qwen3.6-4bit"