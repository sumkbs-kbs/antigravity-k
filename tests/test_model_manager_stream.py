"""테스트: ModelManager 스트리밍 경로.
=====================================
Ollama 네이티브 스트림, OpenAI 호환 SSE, Anthropic 직접 스트림,
동적 추론 설정 및 스트림 요청 빌더를 네트워크 없이 검증한다.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.config import config
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.usage_tracker import UsageTracker
from tests.test_model_manager_lifecycle import _profile


@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=ModelRegistry)
    registry.memory_config = MagicMock()
    registry.memory_config.max_loaded_gb = 1000
    registry.memory_config.auto_unload = False

    profiles = {
        "model-a": _profile("model-a"),
        "model-b": _profile("model-b"),
        "qwen3-test": _profile("qwen3-test"),
        "claude-x": _profile("claude-x"),
    }
    registry.get_model.side_effect = lambda x: profiles.get(x)
    registry.list_models.return_value = list(profiles.values())
    registry._raw = {}
    return registry


@pytest.fixture
def manager(mock_registry):
    tracker = UsageTracker(db_path=None)
    mgr = ModelManager(registry=mock_registry, router=ModelRouter(mock_registry), tracker=tracker)
    mgr._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    return mgr


def _loaded(manager_obj: ModelManager, name: str):
    return manager_obj.load(name)


def _stream_cm(lines: list[bytes]) -> MagicMock:
    """safe_urlopen이 반환할, 줄 단위 이터레이션이 가능한 응답 컨텍스트 매니저."""
    resp = MagicMock()
    resp.__iter__.return_value = iter(lines)
    cm = MagicMock()
    cm.__enter__.return_value = resp
    return cm


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
    config.model = original_model


# ─── 동적 추론 설정 ───────────────────────────────────────────────


class TestDynamicInferenceConfig:
    def test_plain_model_keeps_kwargs_temperature(self, manager):
        name, temperature, thinking, attribution = manager._apply_dynamic_inference_config(
            _profile("model-a"), "prompt", {"temperature": 0.3}
        )

        assert name == "model-a"
        assert temperature == 0.3
        assert thinking is None
        assert attribution.startswith("\nx-antigravity-k-agent:")

    def test_digit_suffix_becomes_thinking_budget(self, manager):
        _, temperature, thinking, _ = manager._apply_dynamic_inference_config(_profile("qwen3:4096"), "prompt", {})

        assert thinking == {"type": "enabled", "budget_tokens": 4096}
        assert temperature == 1.0

    def test_level_suffix_scales_thinking_budget(self, manager):
        _, temperature, thinking, _ = manager._apply_dynamic_inference_config(
            _profile("qwen3:high"), "prompt", {"max_tokens": 8192}
        )

        assert thinking is not None
        assert thinking["budget_tokens"] >= 1024
        assert temperature == 1.0


# ── 스트림 메시지 준비 & 요청 빌더 ────────────────────────────────


class TestStreamMessagePreparation:
    def test_raw_messages_get_system_prompt_prepended(self, manager, http_env):
        loaded = _loaded(manager, "model-a")
        msgs = manager._prepare_stream_messages(
            loaded,
            "",
            {"raw_messages": [{"role": "user", "content": "hi"}], "system_prompt": "지침"},
        )

        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"].startswith("지침")
        assert "x-antigravity-k-agent:" in msgs[0]["content"]
        assert msgs[1]["content"] == "hi"

    def test_content_parts_flattened_to_string(self, manager, http_env):
        loaded = _loaded(manager, "model-a")
        msgs = manager._prepare_stream_messages(
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

        assert msgs[0]["content"].startswith("part1 part2")

    def test_attribution_appended_to_first_message(self, manager, http_env):
        loaded = _loaded(manager, "model-a")
        msgs = manager._prepare_stream_messages(loaded, "hello", {})

        assert "x-antigravity-k-agent:" in msgs[-1]["content"]


class TestStreamRequestBuilder:
    def test_ollama_native_request_shape(self, manager, http_env):
        req, model_name = manager._build_stream_request(
            _loaded(manager, "model-a"),
            [{"role": "user", "content": "hi"}],
            {"max_tokens": 128},
            is_openrouter=False,
        )

        body = json.loads(req.data.decode("utf-8"))
        assert req.full_url == "http://127.0.0.1:11434/api/chat"
        assert model_name == "model-a"
        assert body["stream"] is True
        assert body["keep_alive"] == "30m"
        assert body["options"]["num_ctx"] == 32768
        assert body["options"]["num_predict"] == 128

    def test_openrouter_request_targets_chat_completions(self, manager, http_env):
        req, model_name = manager._build_stream_request(
            _loaded(manager, "model-a"),
            [{"role": "user", "content": "hi"}],
            {},
            is_openrouter=True,
        )

        body = json.loads(req.data.decode("utf-8"))
        assert req.full_url.endswith("/chat/completions")
        assert req.headers.get("X-title") == "Antigravity-K"
        assert model_name == "model-a"
        assert body["stream"] is True


# ── Ollama 네이티브 스트림 파싱 ───────────────────────────────────


class TestOllamaNativeStream:
    def test_yields_message_contents(self, manager, http_env):
        lines = [
            json.dumps({"message": {"content": "안녕"}}, ensure_ascii=False).encode("utf-8") + b"\n",
            b"\n",
            json.dumps({"message": {"content": "하세요"}}, ensure_ascii=False).encode("utf-8") + b"\n",
            b'{"done":true}\n',
        ]
        loaded = _loaded(manager, "model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=_stream_cm(lines)):
            chunks = list(manager._do_ollama_stream(loaded, "인사"))

        assert chunks == ["안녕", "하세요"]

    def test_invalid_json_lines_skipped(self, manager, http_env):
        lines = [b"not-json\n", b'{"message":{"content":"ok"}}\n']
        loaded = _loaded(manager, "model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=_stream_cm(lines)):
            chunks = list(manager._do_ollama_stream(loaded, "Hi"))

        assert chunks == ["ok"]

    def test_generic_failure_yields_api_error_marker(self, manager, http_env):
        failing = MagicMock()
        failing.__enter__.side_effect = RuntimeError("socket exploded")
        loaded = _loaded(manager, "model-a")

        with patch("antigravity_k.engine.model_manager.safe_urlopen", return_value=failing):
            chunks = list(manager._do_ollama_stream(loaded, "Hi"))

        assert chunks and chunks[0].startswith("[API Error for model-a]")


# ── OpenAI 호환 SSE 스트림 파싱 ───────────────────────────────────


class TestOpenRouterSseStream:
    def test_parses_delta_frames_and_stops_on_done(self, manager):
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
                chunks = list(manager._do_ollama_stream(loaded, "Hi"))

            assert chunks == ["A"]
        finally:
            setattr(config, "model", original_model)

    def test_malformed_frames_are_tolerated(self, manager):
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
                chunks = list(manager._do_ollama_stream(loaded, "Hi"))

            assert chunks == ["B"]
        finally:
            config.model = original_model


# ── 스트림 디스패치 & stream_generate ─────────────────────────────


class TestStreamDispatchAndGenerate:
    def test_dispatch_falls_back_to_legacy_stream_without_provider(self, manager):
        manager._uses_anthropic_direct = MagicMock(return_value=False)
        manager._get_provider = MagicMock(return_value=None)

        with patch.object(
            ModelManager,
            "_do_ollama_stream",
            lambda self, loaded, prompt, **kw: iter(["legacy"]),
        ):
            chunks = list(ModelManager._do_stream_generate(manager, _loaded(manager, "model-a"), "Hi"))

        assert chunks == ["legacy"]

    def test_dispatch_delegates_to_provider_when_available(self, manager):
        provider = MagicMock()
        provider.stream_generate.return_value = iter(["p1", "p2"])
        manager._get_provider = MagicMock(return_value=provider)
        manager._uses_anthropic_direct = MagicMock(return_value=False)

        chunks = list(ModelManager._do_stream_generate(manager, _loaded(manager, "model-a"), "Hi"))

        assert chunks == ["p1", "p2"]

    def test_dispatch_passes_long_context_plan_to_provider(self, manager):
        provider = MagicMock()
        provider.stream_generate.return_value = iter(["p1"])
        manager._get_provider = MagicMock(return_value=provider)
        manager._uses_anthropic_direct = MagicMock(return_value=False)
        plan = {"native_attention_enabled": True}
        manager.long_context_plan = MagicMock(return_value=plan)

        list(ModelManager._do_stream_generate(manager, _loaded(manager, "model-a"), "Hi"))

        assert provider.stream_generate.call_args.kwargs["execution_plan"] is plan

    def test_stream_generate_single_model_records_usage(self, manager):
        manager._do_stream_generate = lambda loaded, prompt, **kw: iter(["안녕", "하세요"])

        chunks = list(manager.stream_generate("프롬프트", "model-a"))

        assert chunks == ["안녕", "하세요"]
        recent = manager.tracker.get_recent(1)
        assert recent[0].success is True
        assert recent[0].model_name == "model-a"
        assert len(recent) == 1

    def test_stream_generate_combo_fallback_on_error(self, manager):
        combo = ModelCombo(
            name="fb-combo",
            models=["model-a", "model-b"],
            strategy=RouteStrategy.FALLBACK,
        )
        manager.router.register_combo(combo)

        calls: list[str] = []

        def fake_stream(loaded, prompt, **kwargs):
            calls.append(loaded.profile.name)
            if loaded.profile.name == "model-a":
                raise RuntimeError("stream down")
            yield "복구"

        manager._do_stream_generate = fake_stream

        chunks = list(manager.stream_generate("Hello", "fb-combo"))

        assert chunks == ["복구"]
        assert calls == ["model-a", "model-b"]

    def test_stream_generate_collective_chunks_full_text(self, manager):
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
        stream_cm.__enter__.side_effect = RuntimeError("anthropic overloaded")
    else:
        inner = MagicMock()
        inner.text_stream = iter(texts)
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = inner

    client = MagicMock()
    client.messages.stream.return_value = stream_cm
    module.Anthropic.return_value = client
    return module


class TestAnthropicDirectStream:
    def test_missing_api_key_yields_error_text(self, manager):
        original_raw = getattr(config, "_raw", {})
        config._raw = {"api_keys": {"anthropic": ""}}
        try:
            with patch(
                "antigravity_k.engine.model_manager.import_module",
                return_value=MagicMock(),
            ):
                chunks = list(ModelManager._do_anthropic_stream(manager, _loaded(manager, "claude-x"), "Hi"))
        finally:
            config._raw = original_raw

        assert chunks == ["[Error] Anthropic API Key not found in config.yaml"]

    def test_streams_texts_with_valid_key(self, manager):
        original_raw = getattr(config, "_raw", {})
        config._raw = {"api_keys": {"anthropic": "sk-ant-real"}}
        try:
            with patch(
                "antigravity_k.engine.model_manager.import_module",
                return_value=_fake_anthropic_module(["안녕", "!"]),
            ) as import_mod:
                chunks = list(ModelManager._do_anthropic_stream(manager, _loaded(manager, "claude-x"), "Hi"))
        finally:
            config._raw = original_raw

        assert chunks == ["안녕", "!"]
        import_mod.assert_called_once_with("anthropic")

    def test_stream_failure_yields_api_error(self, manager):
        original_raw = getattr(config, "_raw", {})
        config._raw = {"api_keys": {"anthropic": "sk-ant-real"}}
        try:
            with patch(
                "antigravity_k.engine.model_manager.import_module",
                return_value=_fake_anthropic_module([], fail=True),
            ):
                chunks = list(ModelManager._do_anthropic_stream(manager, _loaded(manager, "claude-x"), "Hi"))
        finally:
            config._raw = original_raw

        assert chunks and chunks[0].startswith("[API Error for claude-x]")


class TestAnthropicRequestParams:
    def test_filters_roles_and_builds_system_blocks(self, manager):
        raw_messages = [
            {"role": "system", "content": "should be dropped"},
            {"role": "user", "content": "질문"},
        ]
        params = manager._build_anthropic_request_params(
            raw_messages,
            "시스템 프롬프트",
            "\nx-antigravity-k-agent: id=abc;",
            "claude-x",
            1.0,
            None,
            {"max_tokens": 2048},
        )

        assert params["messages"] == [{"role": "user", "content": "질문"}]
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert params["system"][0]["text"].endswith("id=abc;")
        assert params["max_tokens"] == 2048
        assert "thinking" not in params

    def test_thinking_config_included_when_present(self, manager):
        params = manager._build_anthropic_request_params(
            [{"role": "user", "content": "?"}],
            "",
            "\nattribution",
            "claude-x",
            1.0,
            {"type": "enabled", "budget_tokens": 4096},
            {},
        )

        assert params["thinking"] == {"type": "enabled", "budget_tokens": 4096}

    def test_more_than_four_cache_blocks_trims_middle(self, manager):
        blocks = [{"cache_control": {"type": "ephemeral"}} for _ in range(5)]
        content_list = [[block] for block in blocks]
        raw_messages = [
            {"role": role, "content": content} for role, content in zip(("user", "assistant") * 3, content_list)
        ]

        params = manager._build_anthropic_request_params(raw_messages, "", "", "claude-x", 0.7, None, {})

        kept = sum(
            1
            for msg in params["messages"]
            for block in (msg["content"] if isinstance(msg["content"], list) else [])
            if isinstance(block, dict) and "cache_control" in block
        )
        assert kept == 4
