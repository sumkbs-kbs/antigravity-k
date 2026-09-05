"""테스트: 모델 매니저 추론 및 라우팅 연동.
======================================
ModelManager.generate() 가 ModelRouter의 폴백 전략과 UsageTracker의 통계 기록을 정상적으로 처리하는지 검증.
"""

import platform
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.model_manager import LoadedModel, ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.tracing import AgentTracer
from antigravity_k.engine.usage_tracker import UsageTracker


def _mock_attr(value: object, name: str) -> MagicMock:
    return cast(MagicMock, getattr(value, name))


def _set_registry_raw(manager: ModelManager, value: object) -> None:
    registry = cast(object, getattr(manager, "_registry"))
    setattr(registry, "_raw", value)


def _tracker_is_available(manager: ModelManager, model_name: str) -> bool:
    router = cast(object, getattr(manager, "router"))
    tracker = cast(object, getattr(router, "_tracker"))
    checker = cast(Callable[[str], bool], getattr(tracker, "is_available"))
    return checker(model_name)


def _load_mlx_model(manager: ModelManager, profile: ModelProfile) -> tuple[object, object]:
    loader = cast(Callable[[ModelManager, ModelProfile], tuple[object, object]], getattr(ModelManager, "_load_mlx_model"))
    return loader(manager, profile)


def _suppress_model_thinking(manager: ModelManager, model_name: str, messages: list[dict[str, str]]) -> list[dict[str, str]]:
    suppress = cast(Callable[[str, list[dict[str, str]]], list[dict[str, str]]], getattr(manager, "_suppress_model_thinking"))
    return suppress(model_name, messages)


def _strip_hidden_reasoning(manager: ModelManager, text: str) -> str:
    stripper = cast(Callable[[str], str], getattr(manager, "_strip_hidden_reasoning"))
    return stripper(text)


@pytest.fixture
def mock_registry() -> MagicMock:
    registry = MagicMock(spec=ModelRegistry)
    # 메모리 설정 (테스트에서는 무한대)
    memory_config = MagicMock()
    setattr(registry, "memory_config", memory_config)
    setattr(memory_config, "max_loaded_gb", 1000)
    setattr(memory_config, "auto_unload", False)

    profiles = {
        "model-a": ModelProfile(name="model-a", repo="test", role="test", estimated_memory_gb=1),
        "model-b": ModelProfile(name="model-b", repo="test", role="test", estimated_memory_gb=1),
        "model-c": ModelProfile(name="model-c", repo="test", role="test", estimated_memory_gb=1),
    }
    get_model = _mock_attr(registry, "get_model")

    def get_model_impl(name: object) -> ModelProfile | None:
        return profiles.get(cast(str, name))

    get_model.side_effect = get_model_impl
    list_models = _mock_attr(registry, "list_models")
    list_models.return_value = list(profiles.values())
    return registry


@pytest.fixture
def setup_manager(mock_registry: MagicMock) -> ModelManager:
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
    setattr(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
    # 내부 텍스트 생성 _do_generate 모킹
    setattr(manager, "_do_generate", MagicMock(return_value="Mock response"))

    return manager


def test_generate_single_model(setup_manager: ModelManager) -> None:
    manager = setup_manager
    res = manager.generate("Hello", "model-a")

    assert res == "Mock response"
    do_generate = _mock_attr(manager, "_do_generate")
    assert isinstance(do_generate, MagicMock)
    do_generate.assert_called_once()

    # 사용량 기록 확인
    recent = manager.tracker.get_recent(1)
    assert len(recent) == 1
    assert recent[0].model_name == "model-a"
    assert recent[0].success is True
    assert recent[0].combo_name == ""


def test_generate_fallback_combo_success(setup_manager: ModelManager) -> None:
    manager = setup_manager
    res = manager.generate("Hello", "fallback-combo")

    assert res == "Mock response"

    # 사용량 기록 확인 (첫 번째 모델인 model-a 사용됨)
    recent = manager.tracker.get_recent(1)
    assert recent[0].model_name == "model-a"
    assert recent[0].combo_name == "fallback-combo"
    assert recent[0].fallback_depth == 0


def test_stream_generate_records_local_qwen_capability_trace(
    setup_manager: ModelManager, mock_registry: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = setup_manager
    qwen = ModelProfile(
        name="qwen3.6:latest",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="ollama",
        parameter_count_b=36.0,
        estimated_memory_gb=24.0,
    )
    get_model = _mock_attr(mock_registry, "get_model")
    def get_qwen(name: object) -> ModelProfile | None:
        return qwen if cast(str, name) == qwen.name else None

    get_model.side_effect = get_qwen
    capability_probe = cast(object, getattr(manager, "_capability_probe"))
    setattr(capability_probe, "observe", MagicMock(
        return_value={
            "model": qwen.name,
            "provider": "ollama",
            "is_local": True,
            "native_tool_calling": "supported",
            "runtime_status": "available",
            "source": "ollama:/api/show",
            "detail": "test",
            "reported_capabilities": ["tools"],
            "reported_model_count": 0,
        },
    ))
    tracer = AgentTracer()
    monkeypatch.setattr("antigravity_k.engine.tracing.get_tracer", lambda: tracer)
    setattr(manager, "_do_stream_generate", MagicMock(return_value=iter(["streamed ", "answer"])))

    _ = tracer.start_trace("stream qwen")
    response = "".join(manager.stream_generate("local prompt", qwen.name))
    trace = tracer.end_trace()

    assert response == "streamed answer"
    assert trace is not None
    span = next(span for span in trace.spans if span.name == f"llm:{qwen.name}")
    assert span.status == "ok"
    assert span.attributes["provider"] == "ollama"
    assert span.attributes["is_local"] is True
    assert span.attributes["parameter_count_b"] == 36.0
    assert span.attributes["fallback_depth"] == 0
    assert span.attributes["native_tool_calling"] == "supported"
    assert span.attributes["provider_runtime_status"] == "available"


def test_stream_generate_records_local_qwen_failure_trace(
    setup_manager: ModelManager, mock_registry: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = setup_manager
    qwen = ModelProfile(
        name="qwen3.6:latest",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="ollama",
        parameter_count_b=36.0,
        estimated_memory_gb=24.0,
    )
    get_model = _mock_attr(mock_registry, "get_model")
    def get_qwen(name: object) -> ModelProfile | None:
        return qwen if cast(str, name) == qwen.name else None

    get_model.side_effect = get_qwen
    tracer = AgentTracer()
    monkeypatch.setattr("antigravity_k.engine.tracing.get_tracer", lambda: tracer)
    setattr(manager, "_do_stream_generate", MagicMock(side_effect=RuntimeError("stream outage")))

    _ = tracer.start_trace("failed stream qwen")
    with pytest.raises(RuntimeError, match="stream outage"):
        _ = list(manager.stream_generate("local prompt", qwen.name))
    trace = tracer.end_trace()

    assert trace is not None
    span = next(span for span in trace.spans if span.name == f"llm:{qwen.name}")
    assert span.status == "error"
    assert span.error_message == "stream outage"
    assert span.attributes["provider"] == "ollama"
    assert span.attributes["is_local"] is True
    assert span.attributes["parameter_count_b"] == 36.0
    assert span.attributes["fallback_depth"] == 0


def test_generate_fallback_on_failure(setup_manager: ModelManager) -> None:
    manager = setup_manager

    # 첫 번째 호출에서 의도적으로 실패 유도
    def do_generate_side_effect(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> str:
        if loaded.profile.name == "model-a":
            raise RuntimeError("API Timeout")
        return "Fallback response"

    do_generate = _mock_attr(manager, "_do_generate")
    assert isinstance(do_generate, MagicMock)
    do_generate.side_effect = do_generate_side_effect

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
    assert not _tracker_is_available(manager, "model-a")


def test_generate_fallback_on_swallowed_api_error_string(setup_manager: ModelManager) -> None:
    manager = setup_manager

    # _do_generate가 실제 프로덕션처럼 실패를 문자열로 삼켜 반환 (모델 404 등)
    def do_generate_side_effect(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> str:
        if loaded.profile.name == "model-a":
            return "[API Error for model-a] HTTP Error 404: Not Found"
        return "Fallback response"

    do_generate = _mock_attr(manager, "_do_generate")
    assert isinstance(do_generate, MagicMock)
    do_generate.side_effect = do_generate_side_effect

    res = manager.generate("Hello", "fallback-combo")

    assert res == "Fallback response"

    records = manager.tracker.get_recent(2)
    assert len(records) == 2
    assert records[0].model_name == "model-b"
    assert records[0].success is True
    assert records[0].fallback_depth == 1
    assert records[0].combo_name == "fallback-combo"

    assert records[1].model_name == "model-a"
    assert records[1].success is False
    assert "404" in records[1].error

    assert not _tracker_is_available(manager, "model-a")


def test_stream_generate_fallback_on_swallowed_api_error_string(setup_manager: ModelManager) -> None:
    manager = setup_manager

    # 스트림 경로에서도 오류 문자열이 첫 청크로 삼켜져 오면 폴백이 발동해야 함
    def do_stream_side_effect(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> Iterator[str]:
        if loaded.profile.name == "model-a":
            return iter(["[API Error for model-a] HTTP Error 404: Not Found"])
        return iter(["streamed ", "answer"])

    setattr(manager, "_do_stream_generate", MagicMock(side_effect=do_stream_side_effect))

    response = "".join(manager.stream_generate("Hello", "fallback-combo"))

    assert response == "streamed answer"

    records = manager.tracker.get_recent(2)
    assert len(records) == 2
    assert records[0].model_name == "model-b"
    assert records[0].success is True
    assert records[0].fallback_depth == 1

    assert records[1].model_name == "model-a"
    assert records[1].success is False

    assert not _tracker_is_available(manager, "model-a")


def test_generate_collective_combo_runs_council(setup_manager: ModelManager) -> None:
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
    _set_registry_raw(manager, {
        "collective_intelligence": {
            "min_participants": 2,
            "max_proposers": 2,
            "max_critics": 1,
            "critic_combo": "critic-swarm",
            "arbiter_combo": "supreme-court",
            "expose_trace": True,
        }
    })

    def do_generate_side_effect(loaded: LoadedModel, prompt: str, **_kwargs: object) -> str:
        if "최종 합성" in prompt:
            return "최종 합성 답변"
        if "비판 라운드" in prompt:
            return "비판 내용"
        return f"후보 답변: {loaded.profile.name}"

    do_generate = _mock_attr(manager, "_do_generate")
    assert isinstance(do_generate, MagicMock)
    do_generate.side_effect = do_generate_side_effect

    res = manager.generate("테스트 요청", "collective-council")

    assert "집단지성" in res
    assert "최종 합성 답변" in res
    do_generate = _mock_attr(manager, "_do_generate")
    assert isinstance(do_generate, MagicMock)
    called_prompts = [cast(str, cast(tuple[object, ...], call.args)[1]) for call in do_generate.call_args_list]
    assert any("제안 라운드" in prompt for prompt in called_prompts)
    assert any("비판 라운드" in prompt for prompt in called_prompts)
    assert any("최종 합성" in prompt for prompt in called_prompts)


def test_get_target_for_role_prefers_agent_model_combo(setup_manager: ModelManager) -> None:
    manager = setup_manager
    _set_registry_raw(manager, {
        "agent_models": {
            "WORKER": "coding-swarm",
            "default": "collective-council",
        }
    })

    assert manager.get_target_for_role("WORKER", default_role="coding") == "coding-swarm"
    assert manager.get_target_for_role("QA") == "collective-council"


def test_qwen3_messages_force_no_think_mode(setup_manager: ModelManager) -> None:
    manager = setup_manager

    messages = _suppress_model_thinking(
        manager,
        "hf.co/Qwen/Qwen3-30B-A3B-GGUF:Q5_K_M",
        [{"role": "user", "content": "안녕"}],
    )

    assert messages[0]["role"] == "system"
    content = str(messages[0]["content"])
    assert "/no_think" in content
    assert "hidden reasoning" in content


def test_non_qwen3_messages_are_unchanged(setup_manager: ModelManager) -> None:
    manager = setup_manager
    original = [{"role": "user", "content": "안녕"}]

    messages = _suppress_model_thinking(manager, "deepseek-r1:32b", original)

    assert messages is original


def test_generate_strips_hidden_reasoning_blocks(setup_manager: ModelManager) -> None:
    manager = setup_manager
    do_generate = _mock_attr(manager, "_do_generate")
    assert isinstance(do_generate, MagicMock)
    do_generate.return_value = "<think>private reasoning</think>\n최종 답변입니다."

    res = manager.generate("Hello", "model-a")

    assert res == "최종 답변입니다."


def test_strip_legacy_thinking_process_block(setup_manager: ModelManager) -> None:
    manager = setup_manager
    text = "--- Thinking Process ---\nprivate plan\n--- End of Thinking* ---\n공개 답변"

    assert _strip_hidden_reasoning(manager, text) == "공개 답변"


def test_explicit_mlx_profile_bypasses_global_api_mode(
    setup_manager: ModelManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = setup_manager
    profile = ModelProfile(
        name="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        repo="mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
        role="coding",
        provider="mlx",
    )
    model = object()
    tokenizer = object()
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    def fake_import_module(_name: str) -> SimpleNamespace:
        def fake_load(_repo: str) -> tuple[object, object]:
            return model, tokenizer

        return SimpleNamespace(load=fake_load)

    monkeypatch.setattr("antigravity_k.engine.model_manager.import_module", fake_import_module)

    loaded_model, loaded_tokenizer = _load_mlx_model(manager, profile)

    assert loaded_model is model
    assert loaded_tokenizer is tokenizer


def test_lmstudio_profile_never_loads_direct_mlx_weights(
    setup_manager: ModelManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    from antigravity_k.config import config
    from antigravity_k.engine.provider_adapters import dev_shims

    manager = setup_manager
    profile = ModelProfile(
        name="lmstudio/qwen3.6",
        repo="qwen3.6:latest",
        role="reasoning",
        provider="lmstudio",
    )
    mlx_loader = MagicMock()
    monkeypatch.setattr(config.model, "force_api", False)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr("antigravity_k.engine.model_manager.import_module", mlx_loader)

    model, tokenizer = _load_mlx_model(manager, profile)

    ollama_model = cast(type[object], getattr(dev_shims, "_OllamaModel"))
    ollama_tokenizer = cast(type[object], getattr(dev_shims, "_OllamaTokenizer"))
    assert isinstance(model, ollama_model)
    assert isinstance(tokenizer, ollama_tokenizer)
    mlx_loader.assert_not_called()
