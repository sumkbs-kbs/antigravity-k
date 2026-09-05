"""테스트: ModelManager 스트리밍 경로.
=====================================
Ollama 네이티브 스트림, OpenAI 호환 SSE, Anthropic 직접 스트림,
동적 추론 설정 및 스트림 요청 빌더를 네트워크 없이 검증한다.
"""

import json
from collections.abc import Callable, Iterator, Mapping
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import MagicMock, patch

import pytest

import tests.test_model_manager_lifecycle as lifecycle_tests
from antigravity_k.config import config
from antigravity_k.engine.model_manager import LoadedModel, ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker


class _RequestLike(Protocol):
    data: bytes
    full_url: str
    headers: Mapping[str, str]


def _profile(name: str, role: str = "reasoning") -> ModelProfile:
    profile = cast(Callable[..., ModelProfile], getattr(lifecycle_tests, "_profile"))
    return profile(name, role)


def _apply_dynamic(manager: ModelManager, *args: object) -> tuple[str, float, dict[str, str | int] | None, str]:
    method = cast(
        Callable[..., tuple[str, float, dict[str, str | int] | None, str]],
        getattr(manager, "_apply_dynamic_inference_config"),
    )
    return method(*args)


def _prepare_messages(manager: ModelManager, *args: object) -> list[dict[str, object]]:
    method = cast(Callable[..., list[dict[str, object]]], getattr(manager, "_prepare_stream_messages"))
    return method(*args)


def _build_stream_request(manager: ModelManager, *args: object, **kwargs: object) -> tuple[_RequestLike, str]:
    method = cast(Callable[..., tuple[_RequestLike, str]], getattr(manager, "_build_stream_request"))
    return method(*args, **kwargs)


def _ollama_stream(manager: ModelManager, *args: object, **kwargs: object) -> Iterator[str]:
    method = cast(Callable[..., Iterator[str]], getattr(manager, "_do_ollama_stream"))
    return method(*args, **kwargs)


def _anthropic_request_params(manager: ModelManager, *args: object) -> dict[str, object]:
    method = cast(Callable[..., dict[str, object]], getattr(manager, "_build_anthropic_request_params"))
    return method(*args)


def _cache_block_count(messages: list[object]) -> int:
    count = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = cast(Mapping[str, object], message).get("content")
        if not isinstance(content, list):
            continue
        count += sum(1 for block in cast(list[object], content) if isinstance(block, dict) and "cache_control" in block)
    return count


def _class_stream_call(name: str) -> Callable[..., Iterator[str]]:
    return cast(Callable[..., Iterator[str]], getattr(ModelManager, name))


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
        "qwen3-test": _profile("qwen3-test"),
        "claude-x": _profile("claude-x"),
    }
    get_model = cast(MagicMock, getattr(registry, "get_model"))

    def get_model_impl(value: object) -> ModelProfile | None:
        return profiles.get(cast(str, value))

    get_model.side_effect = get_model_impl
    list_models = cast(MagicMock, getattr(registry, "list_models"))
    list_models.return_value = list(profiles.values())
    setattr(registry, "_raw", {})
    return registry


@pytest.fixture
def manager(mock_registry: MagicMock) -> ModelManager:
    tracker = UsageTracker(db_path=None)
    mgr = ModelManager(registry=mock_registry, router=ModelRouter(mock_registry), tracker=tracker)
    setattr(mgr, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
    return mgr


def _loaded(manager_obj: ModelManager, name: str) -> LoadedModel:
    return manager_obj.load(name)


def _stream_cm(lines: list[bytes]) -> MagicMock:
    """safe_urlopen이 반환할, 줄 단위 이터레이션이 가능한 응답 컨텍스트 매니저."""
    resp = MagicMock()
    response_iter = cast(MagicMock, getattr(resp, "__iter__"))
    response_iter.return_value = iter(lines)
    cm = MagicMock()
    context_enter = cast(MagicMock, getattr(cm, "__enter__"))
    context_enter.return_value = resp
    return cm


@pytest.fixture
def http_env() -> Iterator[None]:
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
    config.model = original_model


# ─── 동적 추론 설정 ───────────────────────────────────────────────


class TestDynamicInferenceConfig:
    def test_plain_model_keeps_kwargs_temperature(self, manager: ModelManager):
        name, temperature, thinking, attribution = _apply_dynamic(
            manager, _profile("model-a"), "prompt", {"temperature": 0.3}
        )

        assert name == "model-a"
        assert temperature == 0.3
        assert thinking is None
        assert attribution.startswith("\nx-antigravity-k-agent:")

    def test_digit_suffix_becomes_thinking_budget(self, manager: ModelManager):
        _, temperature, thinking, _ = _apply_dynamic(manager, _profile("qwen3:4096"), "prompt", {})

        assert thinking == {"type": "enabled", "budget_tokens": 4096}
        assert temperature == 1.0

    def test_level_suffix_scales_thinking_budget(self, manager: ModelManager):
        _, temperature, thinking, _ = _apply_dynamic(manager, _profile("qwen3:high"), "prompt", {"max_tokens": 8192})

        assert thinking is not None
        assert isinstance(thinking["budget_tokens"], int)
        assert thinking["budget_tokens"] >= 1024
        assert temperature == 1.0


# ── 스트림 메시지 준비 & 요청 빌더 ────────────────────────────────


class TestStreamMessagePreparation:
    def test_raw_messages_get_system_prompt_prepended(self, manager: ModelManager, http_env: None):
        _ = http_env
        loaded = _loaded(manager, "model-a")
        msgs = _prepare_messages(
            manager,
            loaded,
            "",
            {"raw_messages": [{"role": "user", "content": "hi"}], "system_prompt": "지침"},
        )

        assert msgs[0]["role"] == "system"
        content = str(msgs[0]["content"])
        assert content.startswith("지침")
        # attribution 지문은 프롬프트에 주입되지 않는다 (오염 제거)
        assert "x-antigravity-k-agent:" not in content
        assert msgs[1]["content"] == "hi"

    def test_content_parts_flattened_to_string(self, manager: ModelManager, http_env: None):
        _ = http_env
        loaded = _loaded(manager, "model-a")
        msgs = _prepare_messages(
            manager,
            loaded,
            "",
            {
                "raw_messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "part1"},
                            "part2",
                            {"type": "image", "url": "skip"},
                        ],
                    }
                ]
            },
        )

        assert str(msgs[0]["content"]).startswith("part1 part2")

    def test_attribution_not_injected_into_prompt(self, manager: ModelManager, http_env: None):
        """attribution 지문은 다시 파싱되지 않는 프롬프트 오염이다 — 주입 금지."""
        _ = http_env
        loaded = _loaded(manager, "model-a")
        msgs = _prepare_messages(manager, loaded, "hello", {})

        assert "x-antigravity-k-agent:" not in str(msgs[-1]["content"])
        assert str(msgs[-1]["content"]).strip() == "hello"


class TestStreamRequestBuilder:
    def test_ollama_native_request_shape(self, manager: ModelManager, http_env: None):
        _ = http_env
        req, model_name = _build_stream_request(
            manager,
            _loaded(manager, "model-a"),
            [{"role": "user", "content": "hi"}],
            {"max_tokens": 128},
            is_openrouter=False,
        )

        assert isinstance(req.data, bytes)
        body = cast(dict[str, object], json.loads(req.data.decode("utf-8")))
        assert req.full_url == "http://127.0.0.1:11434/api/chat"
        assert model_name == "model-a"
        assert body["stream"] is True
        assert body["keep_alive"] == "30m"
        options = cast(Mapping[str, object], body["options"])
        assert options["num_ctx"] == 32768
        assert options["num_predict"] == 128

    def test_openrouter_request_targets_chat_completions(self, manager: ModelManager, http_env: None):
        _ = http_env
        req, model_name = _build_stream_request(
            manager,
            _loaded(manager, "model-a"),
            [{"role": "user", "content": "hi"}],
            {},
            is_openrouter=True,
        )

        assert isinstance(req.data, bytes)
        body = cast(dict[str, object], json.loads(req.data.decode("utf-8")))
        assert req.full_url.endswith("/chat/completions")
        assert req.headers.get("X-title") == "Ssak-Ai"
        assert model_name == "model-a"
        assert body["stream"] is True


# ── Ollama 네이티브 스트림 파싱 ───────────────────────────────────


class TestOllamaNativeStream:
    def test_yields_message_contents(self, manager: ModelManager, http_env: None):
        _ = http_env
        lines = [
            json.dumps({"message": {"content": "안녕"}}, ensure_ascii=False).encode("utf-8") + b"\n",
            b"\n",
            json.dumps({"message": {"content": "하세요"}}, ensure_ascii=False).encode("utf-8") + b"\n",
            b'{"done":true}\n',
        ]
        loaded = _loaded(manager, "model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=_stream_cm(lines)):
            chunks = list(_ollama_stream(manager, loaded, "인사"))

        assert chunks == ["안녕", "하세요"]

    def test_invalid_json_lines_skipped(self, manager: ModelManager, http_env: None):
        _ = http_env
        lines = [b"not-json\n", b'{"message":{"content":"ok"}}\n']
        loaded = _loaded(manager, "model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=_stream_cm(lines)):
            chunks = list(_ollama_stream(manager, loaded, "Hi"))

        assert chunks == ["ok"]

    def test_generic_failure_yields_api_error_marker(self, manager: ModelManager, http_env: None):
        _ = http_env
        failing = MagicMock()
        failing_enter = cast(MagicMock, getattr(failing, "__enter__"))
        failing_enter.side_effect = RuntimeError("socket exploded")
        loaded = _loaded(manager, "model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=failing):
            chunks = list(_ollama_stream(manager, loaded, "Hi"))

        assert chunks and chunks[0].startswith("[API Error for model-a]")


# ── OpenAI 호환 SSE 스트림 파싱 ───────────────────────────────────


class TestOpenRouterSseStream:
    def test_parses_delta_frames_and_stops_on_done(self, manager: ModelManager):
        original_model = config.model
        setattr(
            config,
            "model",
            SimpleNamespace(
                api_base="https://openrouter.ai/api/v1",
                api_key="key",
                api_engine="openrouter",
            ),
        )
        try:
            frames = b'data: {"choices":[{"delta":{"content":"A"}}]}\n\ndata: [DONE]\n\n'
            loaded = _loaded(manager, "model-a")

            with patch(
                "antigravity_k.engine.model_manager.safe_urlopen",
                return_value=_stream_cm([frames]),
            ):
                chunks = list(_ollama_stream(manager, loaded, "Hi"))

            assert chunks == ["A"]
        finally:
            setattr(config, "model", original_model)

    def test_malformed_frames_are_tolerated(self, manager: ModelManager):
        original_model = config.model
        setattr(
            config,
            "model",
            SimpleNamespace(
                api_base="https://openrouter.ai/api/v1",
                api_key="key",
                api_engine="openrouter",
            ),
        )
        try:
            frames = b'data: {broken json}\n\ndata: {"choices":[{"delta":{"content":"B"}}]}\n\n'
            loaded = _loaded(manager, "model-a")

            with patch(
                "antigravity_k.engine.model_manager.safe_urlopen",
                return_value=_stream_cm([frames]),
            ):
                chunks = list(_ollama_stream(manager, loaded, "Hi"))

            assert chunks == ["B"]
        finally:
            config.model = original_model


# ── 스트림 디스패치 & stream_generate ─────────────────────────────


class TestStreamDispatchAndGenerate:
    def test_dispatch_falls_back_to_legacy_stream_without_provider(self, manager: ModelManager):
        setattr(manager, "_uses_anthropic_direct", MagicMock(return_value=False))
        setattr(manager, "_get_provider", MagicMock(return_value=None))

        def legacy_stream(_self: ModelManager, _loaded: LoadedModel, _prompt: str, **_kwargs: object) -> Iterator[str]:
            return iter(["legacy"])

        with patch.object(
            ModelManager,
            "_do_ollama_stream",
            legacy_stream,
        ):
            chunks = list(_class_stream_call("_do_stream_generate")(manager, _loaded(manager, "model-a"), "Hi"))

        assert chunks == ["legacy"]

    def test_dispatch_delegates_to_provider_when_available(self, manager: ModelManager):
        provider = MagicMock()
        provider_stream = cast(MagicMock, getattr(provider, "stream_generate"))
        provider_stream.return_value = iter(["p1", "p2"])
        setattr(manager, "_get_provider", MagicMock(return_value=provider))
        setattr(manager, "_uses_anthropic_direct", MagicMock(return_value=False))

        chunks = list(_class_stream_call("_do_stream_generate")(manager, _loaded(manager, "model-a"), "Hi"))

        assert chunks == ["p1", "p2"]

    def test_dispatch_passes_long_context_plan_to_provider(self, manager: ModelManager):
        provider = MagicMock()
        provider_stream = cast(MagicMock, getattr(provider, "stream_generate"))
        provider_stream.return_value = iter(["p1"])
        setattr(manager, "_get_provider", MagicMock(return_value=provider))
        setattr(manager, "_uses_anthropic_direct", MagicMock(return_value=False))
        plan = {"native_attention_enabled": True}
        manager.long_context_plan = MagicMock(return_value=plan)

        _ = list(_class_stream_call("_do_stream_generate")(manager, _loaded(manager, "model-a"), "Hi"))

        call_args = cast(MagicMock, getattr(provider_stream, "call_args"))
        call_kwargs = cast(Mapping[str, object], call_args.kwargs)
        assert call_kwargs["execution_plan"] is plan

    def test_stream_generate_single_model_records_usage(self, manager: ModelManager):
        def single_stream(_loaded: LoadedModel, _prompt: str, **_kwargs: object) -> Iterator[str]:
            return iter(["안녕", "하세요"])

        setattr(
            manager,
            "_do_stream_generate",
            single_stream,
        )

        chunks = list(manager.stream_generate("프롬프트", "model-a"))

        assert chunks == ["안녕", "하세요"]
        recent = manager.tracker.get_recent(1)
        assert recent[0].success is True
        assert recent[0].model_name == "model-a"
        assert len(recent) == 1

    def test_stream_generate_combo_fallback_on_error(self, manager: ModelManager):
        combo = ModelCombo(
            name="fb-combo",
            models=["model-a", "model-b"],
            strategy=RouteStrategy.FALLBACK,
        )
        manager.router.register_combo(combo)

        calls: list[str] = []

        def fake_stream(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> Iterator[str]:
            calls.append(loaded.profile.name)
            if loaded.profile.name == "model-a":
                raise RuntimeError("stream down")
            yield "복구"

        setattr(manager, "_do_stream_generate", fake_stream)

        chunks = list(manager.stream_generate("Hello", "fb-combo"))

        assert chunks == ["복구"]
        assert calls == ["model-a", "model-b"]

    def test_stream_generate_midstream_fallback_discards_partial(self, manager: ModelManager):
        """C7: mid-stream failure must not concatenate partial + fallback."""
        combo = ModelCombo(
            name="fb-combo",
            models=["model-a", "model-b"],
            strategy=RouteStrategy.FALLBACK,
        )
        manager.router.register_combo(combo)

        calls: list[str] = []

        def fake_stream(loaded: LoadedModel, _prompt: str, **_kwargs: object) -> Iterator[str]:
            calls.append(loaded.profile.name)
            if loaded.profile.name == "model-a":
                yield "부분출력"
                raise RuntimeError("mid-stream boom")
            yield "완전한"
            yield "폴백답변"

        setattr(manager, "_do_stream_generate", fake_stream)

        chunks = list(manager.stream_generate("Hello", "fb-combo"))
        joined = "".join(chunks)

        assert "부분출력" not in joined
        assert "스트림 중단" not in joined
        assert joined == "완전한폴백답변"
        assert chunks == ["완전한", "폴백답변"]
        assert calls == ["model-a", "model-b"]

    def test_stream_generate_collective_chunks_full_text(self, manager: ModelManager):
        combo = ModelCombo(
            name="swarm",
            models=["model-a", "model-b"],
            strategy=RouteStrategy.COLLECTIVE,
        )
        manager.router.register_combo(combo)
        long_text = "가" * 600
        manager.generate_collective = MagicMock(return_value=long_text)

        chunks = list(manager.stream_generate("Hello", "swarm"))

        assert "".join(chunks) == long_text
        assert all(len(c) <= 256 for c in chunks)


# ── Anthropic 직접 스트림 ─────────────────────────────────────────


def _fake_anthropic_module(texts: list[str], fail: bool = False) -> MagicMock:
    module = MagicMock()

    if fail:
        stream_cm = MagicMock()
        stream_enter = cast(MagicMock, getattr(stream_cm, "__enter__"))
        stream_enter.side_effect = RuntimeError("anthropic overloaded")
    else:
        inner = MagicMock()
        setattr(inner, "text_stream", iter(texts))
        stream_cm = MagicMock()
        stream_enter = cast(MagicMock, getattr(stream_cm, "__enter__"))
        stream_enter.return_value = inner

    client = MagicMock()
    messages = cast(MagicMock, getattr(client, "messages"))
    stream = cast(MagicMock, getattr(messages, "stream"))
    stream.return_value = stream_cm
    anthropic = cast(MagicMock, getattr(module, "Anthropic"))
    anthropic.return_value = client
    return module


class TestAnthropicDirectStream:
    def test_missing_api_key_yields_error_text(self, manager: ModelManager):
        original_raw = getattr(config, "_raw", {})
        setattr(config, "_raw", {"api_keys": {"anthropic": ""}})
        try:
            with patch(
                "antigravity_k.engine.model_manager.import_module",
                return_value=MagicMock(),
            ):
                chunks = list(_class_stream_call("_do_anthropic_stream")(manager, _loaded(manager, "claude-x"), "Hi"))
        finally:
            setattr(config, "_raw", original_raw)

        assert chunks == ["[Error] Anthropic API Key not found in config.yaml"]

    def test_streams_texts_with_valid_key(self, manager: ModelManager):
        original_raw = getattr(config, "_raw", {})
        setattr(config, "_raw", {"api_keys": {"anthropic": "sk-ant-real"}})
        try:
            with patch(
                "antigravity_k.engine.model_manager.import_module",
                return_value=_fake_anthropic_module(["안녕", "!"]),
            ) as import_mod:
                chunks = list(_class_stream_call("_do_anthropic_stream")(manager, _loaded(manager, "claude-x"), "Hi"))
        finally:
            setattr(config, "_raw", original_raw)

        assert chunks == ["안녕", "!"]
        import_mod.assert_called_once_with("anthropic")

    def test_stream_failure_yields_api_error(self, manager: ModelManager):
        original_raw = getattr(config, "_raw", {})
        setattr(config, "_raw", {"api_keys": {"anthropic": "sk-ant-real"}})
        try:
            with patch(
                "antigravity_k.engine.model_manager.import_module",
                return_value=_fake_anthropic_module([], fail=True),
            ):
                chunks = list(_class_stream_call("_do_anthropic_stream")(manager, _loaded(manager, "claude-x"), "Hi"))
        finally:
            setattr(config, "_raw", original_raw)

        assert chunks and chunks[0].startswith("[API Error for claude-x]")


class TestAnthropicRequestParams:
    def test_filters_roles_and_builds_system_blocks(self, manager: ModelManager):
        raw_messages = [
            {"role": "system", "content": "should be dropped"},
            {"role": "user", "content": "질문"},
        ]
        params = _anthropic_request_params(
            manager,
            raw_messages,
            "시스템 프롬프트",
            "\nx-antigravity-k-agent: id=abc;",
            "claude-x",
            1.0,
            None,
            {"max_tokens": 2048},
        )

        assert params["messages"] == [{"role": "user", "content": "질문"}]
        system = params["system"]
        assert isinstance(system, list)
        assert isinstance(system[0], dict)
        system_block = cast(Mapping[str, object], system[0])
        assert system_block["cache_control"] == {"type": "ephemeral"}
        assert str(system_block["text"]).endswith("id=abc;")
        assert params["max_tokens"] == 2048
        assert "thinking" not in params

    def test_thinking_config_included_when_present(self, manager: ModelManager):
        params = _anthropic_request_params(
            manager,
            [{"role": "user", "content": "?"}],
            "",
            "\nattribution",
            "claude-x",
            1.0,
            {"type": "enabled", "budget_tokens": 4096},
            {},
        )

        assert params["thinking"] == {"type": "enabled", "budget_tokens": 4096}

    def test_more_than_four_cache_blocks_trims_middle(self, manager: ModelManager):
        blocks = [{"cache_control": {"type": "ephemeral"}} for _ in range(5)]
        content_list = [[block] for block in blocks]
        raw_messages = [
            {"role": role, "content": content} for role, content in zip(("user", "assistant") * 3, content_list)
        ]

        params = _anthropic_request_params(manager, raw_messages, "", "", "claude-x", 0.7, None, {})

        messages = params["messages"]
        assert isinstance(messages, list)
        kept = _cache_block_count(cast(list[object], messages))
        assert kept == 4
