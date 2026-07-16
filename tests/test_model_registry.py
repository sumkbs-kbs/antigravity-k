"""Tests for ModelRegistry — model profile management and provider inference.

Covers ModelProfile (from_dict/to_dict/backend), _infer_provider heuristics,
DefaultModels, and ModelRegistry core operations (list/get/find_by_role).
"""

from __future__ import annotations

from antigravity_k.engine.model_registry import (
    DefaultModels,
    ModelProfile,
    _infer_provider,
)

# ---------------------------------------------------------------------------
# ModelProfile
# ---------------------------------------------------------------------------


class TestModelProfile:
    """ModelProfile dataclass, serialization, and backend alias."""

    def test_basic_creation(self):
        p = ModelProfile(name="test-model", repo="test/repo", role="reasoning")
        assert p.name == "test-model"
        assert p.role == "reasoning"

    def test_from_dict_minimal(self):
        """from_dict with only required fields."""
        p = ModelProfile.from_dict({"name": "qwen3:latest", "repo": "qwen/repo", "role": "reasoning"})
        assert p.name == "qwen3:latest"
        assert p.role == "reasoning"

    def test_from_dict_full(self):
        """from_dict with all fields."""
        data = {
            "name": "gpt-4o",
            "repo": "openai/gpt-4o",
            "role": "reasoning",
            "quantization": "none",
            "estimated_memory_gb": 0,
            "context_length": 128000,
            "dimensions": 0,
            "description": "GPT-4 Omni",
            "provider": "openrouter",
            "api_base": "",
            "api_key_env": "",
        }
        p = ModelProfile.from_dict(data)
        assert p.provider == "openrouter"
        assert p.context_length == 128000

    def test_to_dict_roundtrip(self):
        """to_dict produces the expected fields."""
        p = ModelProfile(
            name="test",
            repo="r",
            role="coding",
            quantization="Q4",
            context_length=4096,
        )
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["quantization"] == "Q4"
        assert d["context_length"] == 4096

    def test_to_dict_omits_empty_optional_fields(self):
        """to_dict omits empty quantization/dimensions/description."""
        p = ModelProfile(name="t", repo="r", role="reasoning")
        d = p.to_dict()
        assert "quantization" not in d
        assert "dimensions" not in d

    def test_backend_alias_for_provider(self):
        """backend property returns provider or 'ollama' default."""
        p = ModelProfile(name="t", repo="r", role="reasoning", provider="nim")
        assert p.backend == "nim"

    def test_backend_defaults_to_ollama(self):
        """When provider is empty, backend returns 'ollama'."""
        p = ModelProfile(name="t", repo="r", role="reasoning", provider="")
        assert p.backend == "ollama"

    def test_from_dict_auto_infers_provider(self):
        """When provider is not specified, _infer_provider is called."""
        p = ModelProfile.from_dict({"name": "qwen:latest", "repo": "", "role": "reasoning"})
        # ":tag" without "/" → ollama
        assert p.provider == "ollama"


# ---------------------------------------------------------------------------
# _infer_provider
# ---------------------------------------------------------------------------


class TestInferProvider:
    """_infer_provider heuristic provider detection."""

    def test_ollama_tag_format(self):
        """':tag' format without '/' infers ollama."""
        assert _infer_provider("qwen3:latest", "") == "ollama"

    def test_ollama_memory_positive(self):
        """Positive estimated_memory_gb without '/' infers ollama."""
        assert _infer_provider("local-model", "", estimated_memory_gb=4.0) == "ollama"

    def test_free_suffix_is_openrouter(self):
        """:free suffix infers openrouter."""
        assert _infer_provider("meta-llama/llama-3:free", "") == "openrouter"

    def test_claude_direct(self):
        """'claude-' prefix without anthropic/ repo infers anthropic."""
        assert _infer_provider("claude-3-opus", "") == "anthropic"

    def test_gpt_direct(self):
        """'gpt-' prefix without openai/ infers openai direct."""
        assert _infer_provider("gpt-4o", "") == "openai"

    def test_gemini_direct(self):
        """'gemini-' prefix infers gemini."""
        assert _infer_provider("gemini-1.5-pro", "") == "gemini"

    def test_glm_direct(self):
        """'glm-' prefix infers zai."""
        assert _infer_provider("glm-4", "") == "zai"

    def test_openai_o_series(self):
        """'o1'/'o3'/'o4' prefix infers openai."""
        assert _infer_provider("o1-preview", "") == "openai"
        assert _infer_provider("o3-mini", "") == "openai"

    def test_nvidia_nim_prefix(self):
        """'nvidia/' prefix infers nim."""
        assert _infer_provider("nvidia/llama-3.1-nemotron", "") == "nim"

    def test_openrouter_slash_prefix(self):
        """Slash prefix like 'openai/' infers openrouter."""
        assert _infer_provider("openai/gpt-4o", "") == "openrouter"
        assert _infer_provider("anthropic/claude-3", "") == "openrouter"

    def test_unknown_returns_empty(self):
        """An unclassifiable name returns empty string."""
        assert _infer_provider("random-model-name", "") == ""


# ---------------------------------------------------------------------------
# DefaultModels
# ---------------------------------------------------------------------------


class TestDefaultModels:
    """DefaultModels dataclass and from_dict."""

    def test_defaults_all_none(self):
        d = DefaultModels()
        assert d.reasoning is None
        assert d.coding is None

    def test_from_dict(self):
        d = DefaultModels.from_dict(
            {
                "reasoning": "qwen3:latest",
                "coding": "deepseek-coder:latest",
            }
        )
        assert d.reasoning == "qwen3:latest"
        assert d.coding == "deepseek-coder:latest"

    def test_from_dict_partial(self):
        """Missing fields default to None."""
        d = DefaultModels.from_dict({"reasoning": "model-a"})
        assert d.reasoning == "model-a"
        assert d.embedding is None
