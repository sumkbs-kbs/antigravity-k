"""테스트: ModelManager 라이프사이클·캐스케이드·프로바이더 경로.
=====================================================
load/unload/swap/prefetch 등 모델 생명주기와, 캐스케이드 에스컬레이션,
레거시 Ollama HTTP 생성 경로, 상태 조회 API를 검증한다.
"""

import json
from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.config import config
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import (
    AllModelsUnavailableError,
    ModelCombo,
    ModelRouter,
    RouteStrategy,
)
from antigravity_k.engine.usage_tracker import UsageTracker


def _profile(name: str, role: str = "reasoning") -> ModelProfile:
    return ModelProfile(name=name, repo=f"test/{name}", role=role, estimated_memory_gb=1)


def _mock_method(obj: MagicMock, name: str) -> MagicMock:
    return cast(MagicMock, getattr(obj, name))


def _private_mock(obj: ModelManager, name: str) -> MagicMock:
    return cast(MagicMock, getattr(obj, name))


def _loaded(manager: ModelManager) -> Mapping[str, object]:
    return cast(Mapping[str, object], getattr(manager, "_loaded"))


def _private_call(manager: ModelManager, name: str) -> Callable[..., object]:
    return cast(Callable[..., object], getattr(manager, name))


class _RequestLike(Protocol):
    data: bytes
    full_url: str


@pytest.fixture
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ModelRegistry)
    memory_config = MagicMock()
    memory_config.max_loaded_gb = 1000
    memory_config.auto_unload = False
    setattr(registry, "memory_config", memory_config)

    profiles = {
        "model-a": _profile("model-a"),
        "model-b": _profile("model-b"),
        "model-c": _profile("model-c", role="coding"),
    }
    def get_model(value: object) -> ModelProfile | None:
        return profiles.get(cast(str, value))

    _mock_method(registry, "get_model").side_effect = get_model
    _mock_method(registry, "list_models").return_value = list(profiles.values())
    registry._raw = {}
    return registry


@pytest.fixture
def setup_manager(mock_registry: MagicMock) -> ModelManager:
    router = ModelRouter(mock_registry)
    tracker = UsageTracker(db_path=None)
    manager = ModelManager(registry=mock_registry, router=router, tracker=tracker)
    setattr(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), MagicMock())))
    setattr(manager, "_do_generate", MagicMock(return_value="Mock response"))
    return manager


# ─── 모델 생명주기 ────────────────────────────────────────────────


class TestModelLifecycle:
    def test_load_new_model_creates_loaded_entry(self, setup_manager: ModelManager):
        loaded = setup_manager.load("model-a")

        assert loaded.profile.name == "model-a"
        assert setup_manager.is_loaded("model-a") or "model-a" in _loaded(setup_manager)

    def test_load_reuses_cached_instance_without_reload(self, setup_manager: ModelManager):
        first = setup_manager.load("model-a")
        second = setup_manager.load("model-a")

        assert first is second
        loader = _private_mock(setup_manager, "_load_mlx_model")
        assert loader.call_count == 1

    def test_load_unknown_model_raises_with_registered_names(
        self, setup_manager: ModelManager
    ):
        with pytest.raises(ValueError) as excinfo:
            _ = setup_manager.load("no-such-model")

        message = str(excinfo.value)
        assert "no-such-model" in message
        assert "model-a" in message

    def test_unload_not_loaded_returns_false(self, setup_manager: ModelManager):
        assert setup_manager.unload("model-a") is False

    def test_unload_removes_and_reports_true(self, setup_manager: ModelManager):
        _ = setup_manager.load("model-a")
        assert setup_manager.unload("model-a") is True
        assert "model-a" not in _loaded(setup_manager)

    def test_swap_replaces_same_role_models(self, setup_manager: ModelManager):
        _ = setup_manager.load("model-a")
        _ = setup_manager.load("model-b")

        swapped = setup_manager.swap("model-c", role="reasoning")

        assert swapped.profile.name == "model-c"
        assert "model-a" not in _loaded(setup_manager)
        assert "model-b" not in _loaded(setup_manager)

    def test_swap_unknown_model_raises_value_error(self, setup_manager: ModelManager):
        with pytest.raises(ValueError):
            _ = setup_manager.swap("ghost")

    def test_get_by_role_returns_matching_loaded_model(self, setup_manager: ModelManager):
        loaded = setup_manager.load("model-c")
        found = setup_manager.get_by_role("coding")

        assert found is loaded

    def test_get_by_role_loads_default_when_nothing_loaded(self, setup_manager: ModelManager, mock_registry: MagicMock):
        _mock_method(mock_registry, "get_default").return_value = _profile("model-a")

        found = setup_manager.get_by_role("reasoning")

        assert found is not None
        assert found.profile.name == "model-a"

    def test_get_by_role_returns_none_without_default(self, setup_manager: ModelManager, mock_registry: MagicMock):
        _mock_method(mock_registry, "get_default").return_value = None

        assert setup_manager.get_by_role("vision") is None


class TestTargetResolution:
    def test_get_target_for_role_uses_agent_models_mapping(self, setup_manager: ModelManager, mock_registry: MagicMock):
        mock_registry._raw = {"agent_models": {"coding": "model-c"}}

        assert setup_manager.get_target_for_role("coding") == "model-c"

    def test_get_target_for_role_accepts_case_variants(self, setup_manager: ModelManager, mock_registry: MagicMock):
        mock_registry._raw = {"agent_models": {"CODING": "model-c"}}

        assert setup_manager.get_target_for_role("coding") == "model-c"

    def test_get_target_for_role_falls_back_to_default_profile(
        self, setup_manager: ModelManager, mock_registry: MagicMock
    ):
        mock_registry._raw = {}
        _mock_method(mock_registry, "get_default").return_value = _profile("model-b")

        assert setup_manager.get_target_for_role("unknown-role") == "model-b"

    def test_get_target_for_role_final_literal(self, setup_manager: ModelManager, mock_registry: MagicMock):
        mock_registry._raw = {}
        _mock_method(mock_registry, "get_default").return_value = None

        assert setup_manager.get_target_for_role("unknown-role") == "default_model"

    def test_get_target_for_role_recovers_from_unregistered_configured_target(
        self, setup_manager: ModelManager, mock_registry: MagicMock
    ):
        mock_registry._raw = {"agent_models": {"coding": "missing-local"}}
        discovered = _profile("discovered-local:7b", role="coding")
        discovered.provider = "ollama"
        _mock_method(mock_registry, "refresh_local_models").return_value = (discovered,)

        def get_discovered_model(value: object) -> ModelProfile | None:
            return {"discovered-local:7b": discovered}.get(cast(str, value))

        _mock_method(mock_registry, "get_model").side_effect = get_discovered_model
        _mock_method(mock_registry, "get_default").return_value = None

        assert setup_manager.get_target_for_role("coding", default_role="coding") == "discovered-local:7b"


class TestPrefetch:
    def test_prefetch_already_loaded_returns_true(self, setup_manager: ModelManager):
        _ = setup_manager.load("model-a")
        assert setup_manager.prefetch("model-a") is True

    def test_prefetch_unknown_model_returns_false(self, setup_manager: ModelManager):
        assert setup_manager.prefetch("ghost") is False

    def test_prefetch_denied_when_memory_insufficient(self, setup_manager: ModelManager, mock_registry: MagicMock):
        memory_config = cast(MagicMock, getattr(mock_registry, "memory_config"))
        memory_config.max_loaded_gb = 0

        assert setup_manager.prefetch("model-a") is False

    def test_prefetch_success_loads_model(self, setup_manager: ModelManager):
        assert setup_manager.prefetch("model-a") is True
        assert "model-a" in _loaded(setup_manager)


# ─── generate 오류 경로 ───────────────────────────────────────────


class TestGenerateErrorPaths:
    def test_single_model_failure_records_and_raises(self, setup_manager: ModelManager):
        manager = setup_manager
        setattr(manager, "_do_generate", MagicMock(side_effect=RuntimeError("boom")))

        with pytest.raises(RuntimeError):
            _ = manager.generate("Hello", "model-a")

        recent = manager.tracker.get_recent(1)
        assert recent[0].success is False

    def test_all_models_unavailable_propagates(self, setup_manager: ModelManager, mock_registry: MagicMock):
        manager = setup_manager
        del mock_registry
        manager.router.route_single = MagicMock(side_effect=AllModelsUnavailableError("combo", ["model-a"]))

        with pytest.raises(AllModelsUnavailableError):
            _ = manager.generate("Hello", "model-a")


# ─── 캐스케이드 에스컬레이션 ───────────────────────────────────────


@pytest.fixture
def cascading_manager(setup_manager: ModelManager) -> ModelManager:
    combo = ModelCombo(
        name="cascade-combo",
        models=["model-a", "model-b"],
        strategy=RouteStrategy.CASCADING,
    )
    setup_manager.router.register_combo(combo)
    setup_manager.router.cascade_on_low_confidence = True
    setup_manager.router.cascade_confidence_threshold = 0.4
    setup_manager.router.cascade_max_escalations = 2
    return setup_manager


class TestCascadeEscalation:
    def test_escalates_low_confidence_to_upper_tier(self, cascading_manager: ModelManager):
        weak = "모르겠습니다"
        strong = (
            "정답은 다음과 같습니다. 이 문제의 핵심 원리는 보존 법칙이며, "
            "단계별로 유도하면 명확하게 결론에 도달합니다. 추가 검증도 통과했습니다."
        )
        setattr(cascading_manager, "_do_generate", MagicMock(side_effect=[weak, strong]))

        result = cascading_manager.generate("Hello", "cascade-combo")

        assert result == strong
        assert _private_mock(cascading_manager, "_do_generate").call_count == 2

    def test_disabled_cascade_keeps_original_response(self, cascading_manager: ModelManager):
        cascading_manager.router.cascade_on_low_confidence = False
        setattr(cascading_manager, "_do_generate", MagicMock(return_value="모르겠습니다"))

        result = cascading_manager.generate("Hello", "cascade-combo")

        assert result == "모르겠습니다"
        assert _private_mock(cascading_manager, "_do_generate").call_count == 1

    def test_stops_when_no_upper_tier_exists(self, cascading_manager: ModelManager):
        cascading_manager.router.cascade_max_escalations = 3
        setattr(cascading_manager, "_do_generate", MagicMock(return_value="모르겠습니다"))
        cascading_manager.router.escalate = MagicMock(return_value=None)

        result = cascading_manager.generate("Hello", "cascade-combo")

        assert result == "모르겠습니다"
        assert cascading_manager.router.escalate.call_count == 1

    def test_upper_tier_failure_returns_last_good_response(self, cascading_manager: ModelManager):
        weak = "모르겠습니다"
        setattr(cascading_manager, "_do_generate", MagicMock(side_effect=[weak, RuntimeError("tier-2 down")]))
        cascading_manager.router.mark_failure = MagicMock()

        result = cascading_manager.generate("Hello", "cascade-combo")

        assert result == weak
        cascading_manager.router.mark_failure.assert_called_once()
        assert "tier-2 down" in str(cascading_manager.router.mark_failure.call_args)


class TestConfidenceEstimation:
    def test_heuristic_used_when_evaluator_missing(self, cascading_manager: ModelManager):
        cascading_manager.router.confidence_evaluator_enabled = True
        cascading_manager.router.select_confidence_evaluator = MagicMock(return_value=None)

        estimate_confidence = cast(Callable[[str, str], float], getattr(cascading_manager, "_estimate_confidence"))
        score = estimate_confidence("q", "완벽한 답변입니다. " * 20)

        assert 0.0 <= score <= 1.0

    def test_evaluator_exception_falls_back_to_heuristic(self, cascading_manager: ModelManager):
        evaluator_profile = _profile("model-c")
        cascading_manager.router.confidence_evaluator_enabled = True
        cascading_manager.router.select_confidence_evaluator = MagicMock(return_value=evaluator_profile)
        setattr(cascading_manager, "_do_generate", MagicMock(side_effect=RuntimeError("evaluator down")))

        estimate_confidence = cast(Callable[[str, str], float], getattr(cascading_manager, "_estimate_confidence"))
        score = estimate_confidence("q", "answer text here")

        assert isinstance(score, float)


# ─── 집단지성 폴백 ────────────────────────────────────────────────


class TestCollectiveFallback:
    def test_below_min_participants_falls_back_to_single(self, setup_manager: ModelManager):
        combo = ModelCombo(
            name="tiny-swarm",
            models=["model-a"],
            strategy=RouteStrategy.COLLECTIVE,
        )
        setup_manager.router.register_combo(combo)
        setattr(setup_manager, "_collective_config", MagicMock(return_value={"min_participants": 2}))

        result = setup_manager.generate("Hello", "tiny-swarm")

        assert result == "Mock response"


# ─── 프로바이더 위임 & 레거시 HTTP 경로 ──────────────────────────


class TestProviderDelegation:
    def test_do_generate_falls_back_to_legacy_path_without_provider(self, setup_manager: ModelManager):
        manager = setup_manager
        setattr(manager, "_get_provider", MagicMock(return_value=None))
        setattr(manager, "_uses_anthropic_direct", MagicMock(return_value=False))
        setattr(manager, "_do_ollama_generate", MagicMock(return_value="legacy output"))

        loaded = manager.load("model-a")
        do_generate = cast(Callable[[ModelManager, object, str], str], getattr(ModelManager, "_do_generate"))
        result = do_generate(manager, loaded, "Hi")

        assert result == "legacy output"
        _private_mock(manager, "_do_ollama_generate").assert_called_once()

    def test_available_combo_or_models_prefers_existing_combo(self, setup_manager: ModelManager):
        critic = ModelCombo(
            name="critic-pair",
            models=["model-b", "model-c"],
            strategy=RouteStrategy.FALLBACK,
        )
        setup_manager.router.register_combo(critic)

        resolved = cast(list[str], _private_call(setup_manager, "_available_combo_or_models")("critic-pair", ["fallback-x"]))

        assert resolved == ["model-b", "model-c"]

    def test_available_combo_or_models_falls_back_without_combo(self, setup_manager: ModelManager):
        resolved = cast(list[str], _private_call(setup_manager, "_available_combo_or_models")("missing-combo", ["m"]))
        assert resolved == ["m"]

    def test_ollama_native_base_strips_version_suffix(self):
        ollama_native_base = cast(Callable[[str], str], getattr(ModelManager, "_ollama_native_base"))
        assert ollama_native_base("http://localhost:11434/v1/") == "http://localhost:11434"
        assert ollama_native_base("") == ""


@pytest.fixture
def http_env():
    original_model = config.model
    setattr(
        config,
        "model",
        SimpleNamespace(
            api_base="http://127.0.0.1:11434/v1",
            api_key="test-key",
            api_engine="ollama",
        ),
    )
    yield
    setattr(config, "model", original_model)


class TestLegacyOllamaGenerate:
    def test_posts_payload_and_returns_content(self, setup_manager: ModelManager, http_env: None):
        del http_env
        cm = _make_http({"choices": [{"message": {"content": "안녕하세요"}}]})
        loaded = setup_manager.load("model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=cm) as up:
            result = cast(str, _private_call(setup_manager, "_do_ollama_generate")(loaded, "인사해줘"))

        assert result == "안녕하세요"
        request = cast(_RequestLike, up.call_args.args[0])
        body = cast(dict[str, object], json.loads(request.data.decode("utf-8")))
        assert request.full_url.endswith("/chat/completions")
        assert body["model"] == "model-a"
        assert body["stream"] is False
        messages = cast(list[dict[str, object]], body["messages"])
        assert messages[-1] == {"role": "user", "content": "인사해줘"}

    def test_raw_messages_prepend_system_prompt(self, setup_manager: ModelManager, http_env: None):
        del http_env
        cm = _make_http({"choices": [{"message": {"content": "ok"}}]})
        loaded = setup_manager.load("model-a")
        raw = [{"role": "user", "content": "hi"}]

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=cm) as up:
            _ = _private_call(setup_manager, "_do_ollama_generate")(
                loaded, "", raw_messages=raw, system_prompt="시스템 지침"
            )

        request = cast(_RequestLike, up.call_args.args[0])
        body = cast(dict[str, object], json.loads(request.data.decode("utf-8")))
        messages = cast(list[dict[str, object]], body["messages"])
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "시스템 지침"
        assert messages[1] == {"role": "user", "content": "hi"}

    def test_json_schema_forces_format_field(self, setup_manager: ModelManager, http_env: None):
        del http_env
        cm = _make_http({"choices": [{"message": {"content": "{}"}}]})
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        loaded = setup_manager.load("model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=cm) as up:
            _ = _private_call(setup_manager, "_do_ollama_generate")(loaded, "?", response_format=schema)

        request = cast(_RequestLike, up.call_args.args[0])
        body = cast(dict[str, object], json.loads(request.data.decode("utf-8")))
        assert body["format"] == schema

    def test_http_failure_returns_api_error_string(self, setup_manager: ModelManager, http_env: None):
        del http_env
        failing = MagicMock()
        _mock_method(failing, "__enter__").side_effect = OSError("connection refused")
        loaded = setup_manager.load("model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=failing):
            result = cast(str, _private_call(setup_manager, "_do_ollama_generate")(loaded, "Hi"))

        assert result.startswith("[API Error for model-a]")
        assert "connection refused" in result

    def test_hidden_thinking_only_output_is_flagged_as_error(self, setup_manager: ModelManager, http_env: None):
        del http_env
        cm = _make_http({"choices": [{"message": {"content": "", "thinking": "비밀 추론"}}]})
        loaded = setup_manager.load("model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=cm):
            result = cast(str, _private_call(setup_manager, "_do_ollama_generate")(loaded, "Hi"))

        assert "[API Error for model-a]" in result

    def test_qwen3_messages_receive_direct_answer_directive(self, setup_manager: ModelManager, http_env: None):
        del http_env
        cm = _make_http({"choices": [{"message": {"content": "답변"}}]})
        profile = _profile("qwen3-test")
        registry = cast(MagicMock, getattr(setup_manager, "_registry"))

        def get_qwen_model(value: object) -> ModelProfile | None:
            return profile if value == "qwen3-test" else None

        _mock_method(registry, "get_model").side_effect = get_qwen_model
        loaded = setup_manager.load("qwen3-test")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=cm) as up:
            _ = _private_call(setup_manager, "_do_ollama_generate")(loaded, "질문")

        request = cast(_RequestLike, up.call_args.args[0])
        body = cast(dict[str, object], json.loads(request.data.decode("utf-8")))
        messages = cast(list[dict[str, object]], body["messages"])
        assert "/no_think" in cast(str, messages[0]["content"])
        assert messages[0]["role"] == "system"


def _make_http(payload: dict[str, object]) -> MagicMock:
    cm = MagicMock()
    _mock_method(cm, "read").return_value = json.dumps(payload).encode("utf-8")
    _mock_method(cm, "__enter__").return_value = cm
    return cm


# ─── 상태 조회 ────────────────────────────────────────────────────


class TestStatusSurface:
    def test_status_reports_loaded_models_and_memory(self, setup_manager: ModelManager):
        _ = setup_manager.load("model-a")

        status = setup_manager.status()

        assert status["total_loaded_gb"] == 1.0
        loaded_models = status["loaded_models"]
        assert isinstance(loaded_models, list)
        assert isinstance(loaded_models[0], dict)
        assert loaded_models[0]["name"] == "model-a"
        assert status["max_allowed_gb"] == 1000
        assert "routing" in status
        assert "provider_capabilities" in status

    def test_get_model_info_aliases_status(self, setup_manager: ModelManager):
        assert setup_manager.get_model_info() == setup_manager.status()

    def test_loaded_names_reflect_state(self, setup_manager: ModelManager):
        assert setup_manager.loaded_names() == []
        _ = setup_manager.load("model-a")
        assert setup_manager.loaded_names() == ["model-a"]

    def test_provider_capability_unknown_model_returns_none(self, setup_manager: ModelManager):
        assert setup_manager.provider_capability("ghost") is None

    def test_is_loaded_shortcircuits_for_local_runtime_profiles(
        self, setup_manager: ModelManager, mock_registry: MagicMock
    ):
        local_profile = _profile("lmstudio-model")
        local_profile.provider = "lmstudio"
        def get_local_model(value: object) -> ModelProfile | None:
            return local_profile if value == "lmstudio-model" else None

        _mock_method(mock_registry, "get_model").side_effect = get_local_model

        assert setup_manager.is_loaded("lmstudio-model") is True
