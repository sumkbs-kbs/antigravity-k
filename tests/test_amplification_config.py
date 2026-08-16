"""테스트: amplification config 섹션이 CoV/self-evolution을 올바르게 제어하는지 검증.

orch.config는 raw dict(로드된 config.yaml)이므로, 증폭 서브시스템은 dict 접근으로
설정을 읽어야 한다. 과거 cov_verify_handler가 attribute 접근(getattr(cfg,'model'))
을 써서 항상 기본값으로 폴백하던 버그의 회귀 테스트를 포함한다.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from antigravity_k.engine.cognitive_loop import CognitiveLoop
from antigravity_k.engine.engine_context import cognitive_config_from_raw
from antigravity_k.engine.orchestrator_handlers import (
    _amplification_section,
    _cov_settings,
    cov_verify_handler,
)
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


def _orch_with_config(config: dict) -> SimpleNamespace:
    """raw dict config를 가진 최소 orch stub."""
    orch = SimpleNamespace()
    orch.config = config
    orch.manager = MagicMock()
    return orch


class TestCovSettingsReader:
    """_cov_settings가 dict config에서 모델/파라미터를 올바르게 읽는지 검증."""

    def test_reads_main_model_via_dict_access(self):
        # 회귀: config.model.main_model을 dict 접근으로 읽어야 한다 (attribute 접근 금지).
        orch = _orch_with_config({"model": {"main_model": "lmstudio/qwen3.6"}})
        enabled, model, *_ = _cov_settings(orch)
        assert enabled is True
        assert model == "lmstudio/qwen3.6"

    def test_amplification_cov_model_overrides_main_model(self):
        orch = _orch_with_config(
            {
                "model": {"main_model": "qwen3.6:latest"},
                "amplification": {"cov": {"model": "mlx-community/qwen3.6-4bit"}},
            }
        )
        _, model, *_ = _cov_settings(orch)
        assert model == "mlx-community/qwen3.6-4bit"

    def test_falls_back_to_qwen36_when_no_config(self):
        orch = _orch_with_config({})
        _, model, *_ = _cov_settings(orch)
        assert model == "qwen3.6:latest"

    def test_handles_none_config(self):
        orch = SimpleNamespace(config=None)
        enabled, model, *_ = _cov_settings(orch)
        assert enabled is True
        assert model == "qwen3.6:latest"

    def test_reads_custom_params(self):
        orch = _orch_with_config(
            {
                "amplification": {
                    "cov": {
                        "enabled": True,
                        "min_response_length": 120,
                        "complexity_threshold": 0.7,
                        "max_revise_iterations": 3,
                    }
                },
            }
        )
        enabled, model, min_len, threshold, max_iter = _cov_settings(orch)
        assert enabled is True
        assert min_len == 120
        assert threshold == 0.7
        assert max_iter == 3

    def test_disabled_flag(self):
        orch = _orch_with_config({"amplification": {"cov": {"enabled": False}}})
        enabled, *_ = _cov_settings(orch)
        assert enabled is False


class TestCovHandlerToggle:
    """cov_verify_handler가 enabled 토글과 config 파라미터를 반영하는지 검증."""

    def test_handler_skips_when_disabled(self):
        orch = _orch_with_config({"amplification": {"cov": {"enabled": False}}})
        ctx = StateContext(user_message=COMPLEX_TASK, agent_output=LONG_AGENT_OUTPUT)
        result = list(cov_verify_handler(ctx, orch))
        assert result == []
        assert not hasattr(orch, "_cov_engine")

    def test_handler_creates_engine_with_config_params(self):
        orch = _orch_with_config(
            {
                "amplification": {
                    "cov": {
                        "enabled": True,
                        "min_response_length": 60,
                        "complexity_threshold": 0.5,
                        "max_revise_iterations": 3,
                    }
                },
            }
        )
        ctx = StateContext(user_message=COMPLEX_TASK, agent_output=LONG_AGENT_OUTPUT)
        list(cov_verify_handler(ctx, orch))
        assert hasattr(orch, "_cov_engine")
        assert orch._cov_engine.complexity_threshold == 0.5
        assert orch._cov_engine.min_response_length == 60
        assert orch._cov_engine.max_revise_iterations == 3


class TestSelfEvolutionPrecedence:
    """amplification.self_evolution.enabled가 기존 self_evolution.auto_modify보다 우선하는지 검증."""

    def test_amplification_enabled_overrides_legacy_false(self):
        orch = _orch_with_config(
            {
                "self_evolution": {"auto_modify": False},
                "amplification": {"self_evolution": {"enabled": True}},
            }
        )
        assert _amplification_section(orch, "self_evolution").get("enabled") is True

    def test_legacy_used_when_amplification_null(self):
        # amplification.self_evolution.enabled가 null이면 기존 self_evolution.auto_modify 사용.
        orch = _orch_with_config({"self_evolution": {"auto_modify": True}})
        assert _amplification_section(orch, "self_evolution").get("enabled") is None
        assert orch.config["self_evolution"]["auto_modify"] is True


class TestCognitiveLoopConfig:
    """CognitiveLoop가 amplification.cognitive에서 max_retries/dialectic_enabled를 읽는지 검증."""

    def test_defaults_when_no_params(self):
        # max_retries/dialectic_enabled 미지정 → 기본값(2, True)으로 폴백.
        loop = CognitiveLoop(project_root="/tmp")
        assert loop._max_retries == 2
        assert loop._dialectic_enabled is True

    def test_max_retries_override(self):
        # qwen3.6 튜닝: 작은 모델은 retry를 늘려 추론 깊이 보완.
        loop = CognitiveLoop(project_root="/tmp", max_retries=5)
        assert loop._max_retries == 5

    def test_dialectic_disabled(self):
        loop = CognitiveLoop(project_root="/tmp", dialectic_enabled=False)
        assert loop._dialectic_enabled is False

    def test_none_preserves_default(self):
        # None 명시 시 기본값 유지 (config 누락 경로).
        loop = CognitiveLoop(project_root="/tmp", max_retries=None, dialectic_enabled=None)
        assert loop._max_retries == 2
        assert loop._dialectic_enabled is True


class TestCognitiveConfigMapping:
    """cognitive_config_from_raw가 config dict를 CognitiveLoop kwargs로 매핑하는지 검증."""

    def test_full_config(self):
        e, kw = cognitive_config_from_raw(
            {
                "amplification": {
                    "cognitive": {
                        "enabled": True,
                        "max_retries": 3,
                        "dialectic_enabled": False,
                        "enable_caveman": True,
                    }
                },
            }
        )
        assert e is True
        assert kw == {"enable_caveman": True, "max_retries": 3, "dialectic_enabled": False}

    def test_disabled_returns_empty_kwargs(self):
        e, kw = cognitive_config_from_raw({"amplification": {"cognitive": {"enabled": False}}})
        assert e is False
        assert kw == {}

    def test_missing_keys_fallback_to_none(self):
        # max_retries/dialectic_enabled 누락 → None → CognitiveLoop 기본값.
        e, kw = cognitive_config_from_raw({"amplification": {"cognitive": {"enabled": True}}})
        assert e is True
        assert kw["max_retries"] is None
        assert kw["dialectic_enabled"] is None

    def test_missing_section_defaults_to_enabled(self):
        e, kw = cognitive_config_from_raw({})
        assert e is True

    def test_non_dict_config_safe(self):
        e, kw = cognitive_config_from_raw(None)
        assert e is True
        assert kw["max_retries"] is None

    def test_kwargs_build_valid_cognitive_loop(self):
        # 매핑 결과가 실제 CognitiveLoop 생성자에 그대로 전달 가능한지 검증.
        _, kw = cognitive_config_from_raw(
            {
                "amplification": {"cognitive": {"enabled": True, "max_retries": 4}},
            }
        )
        loop = CognitiveLoop(project_root="/tmp", **kw)
        assert loop._max_retries == 4
        assert loop._dialectic_enabled is True  # None → 기본값
