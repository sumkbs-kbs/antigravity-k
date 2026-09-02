"""Critic 모델 라우팅 테스트: critic-swarm 콤보가 config에서 로드되고
CoV/집단지성 critic 역할이 해당 콤보로 라우팅되는지 검증."""

from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import antigravity_k.engine.orchestrator_handler_config as handler_config
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.orchestrator_verification_handlers import cov_verify_handler
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


def _cov_settings_for(orch: object) -> tuple[bool, str, int, float, int]:
    settings = cast(
        Callable[[object], tuple[bool, str, int, float, int]],
        getattr(handler_config, "_cov_settings"),
    )
    return settings(orch)


def _call_kwargs(mock: MagicMock) -> Mapping[str, object]:
    call = cast(object, getattr(mock, "call_args"))
    if isinstance(call, tuple):
        call_tuple = cast(tuple[object, ...], call)
        if len(call_tuple) > 1:
            return cast(Mapping[str, object], call_tuple[1])
    return {}


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
    raw = cast(dict[str, object], getattr(_registry(), "_raw"))
    orch = SimpleNamespace(config=raw)
    enabled, model, *_ = _cov_settings_for(orch)
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
        engine_instance = cast(MagicMock, getattr(engine_cls, "return_value"))
        run_mock = cast(MagicMock, getattr(engine_instance, "run"))
        setattr(run_mock, "return_value", "synthesized")
        result = manager.generate_collective("프로젝트 아키텍처 설계", "reasoning-swarm")
        assert result == "synthesized"
        kwargs = _call_kwargs(run_mock)
        # critic 후보는 proposer 모델이 아닌 critic-swarm 콤보 멤버에서 온다
        assert kwargs["critics"] == ["deepseek-r1:70b"]


def test_cov_handler_routes_verify_to_critic_swarm() -> None:
    orch = SimpleNamespace()
    orch.config = {
        "model": {"main_model": "qwen3.8"},
        "amplification": {"cov": {"enabled": True, "model": "critic-swarm"}},
    }
    manager = MagicMock()
    orch.manager = manager
    generate_mock = cast(MagicMock, getattr(manager, "generate"))
    setattr(generate_mock, "return_value", "문제 없음")
    ctx = StateContext(user_message=COMPLEX_TASK, agent_output=LONG_AGENT_OUTPUT)
    _ = list(cov_verify_handler(ctx, orch))
    kwargs = _call_kwargs(generate_mock)
    assert kwargs["target"] == "critic-swarm"


def test_cov_handler_routes_to_single_model_when_configured() -> None:
    orch = SimpleNamespace()
    orch.config = {
        "model": {"main_model": "qwen3.8"},
        "amplification": {"cov": {"enabled": True, "model": "mlx-community/qwen3.6-4bit"}},
    }
    manager = MagicMock()
    orch.manager = manager
    generate_mock = cast(MagicMock, getattr(manager, "generate"))
    setattr(generate_mock, "return_value", "문제 없음")
    ctx = StateContext(user_message=COMPLEX_TASK, agent_output=LONG_AGENT_OUTPUT)
    _ = list(cov_verify_handler(ctx, orch))
    kwargs = _call_kwargs(generate_mock)
    assert kwargs["target"] == "mlx-community/qwen3.6-4bit"
