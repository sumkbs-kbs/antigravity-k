"""Tests for ModelRegistry — model profile management and provider inference.

Covers ModelProfile (from_dict/to_dict/backend), _infer_provider heuristics,
DefaultModels, and ModelRegistry core operations (list/get/find_by_role).
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from antigravity_k.engine.model_registry import (
    DefaultModels,
    ModelProfile,
    ModelRegistry,
    _default_config_path,
    _infer_provider,
)

# ---------------------------------------------------------------------------
# ModelProfile
# ---------------------------------------------------------------------------


def test_default_config_is_packaged_as_runtime_resource():
    # Given: the wheel is installed outside the source checkout.
    bundled = files("antigravity_k").joinpath("config.yaml")

    # Then: the default model roster remains available without the repository.
    assert bundled.is_file()


def test_default_config_path_falls_back_to_bundled_resource(tmp_path: Path):
    # Given: an installed package has no adjacent project config.yaml.
    missing_project_root = tmp_path / "missing-project"

    # When: the registry resolves its default config.
    config_path = _default_config_path(missing_project_root)

    # Then: it falls back to the packaged default rather than raising.
    assert config_path.is_file()
    assert config_path.name == "config.yaml"


def test_bundled_default_config_matches_repository_default():
    # Given: package data can drift silently when only one copy is edited.
    repository_config = Path(__file__).resolve().parents[1] / "config.yaml"

    # Then: the packaged default remains byte-identical to the source default.
    assert Path(str(files("antigravity_k").joinpath("config.yaml"))).read_text() == repository_config.read_text()


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

    def test_capability_metadata_exposes_local_20b_plus_qwen_tier(self):
        p = ModelProfile.from_dict(
            {
                "name": "qwen3.6:latest",
                "repo": "qwen3.6:latest",
                "role": "reasoning",
                "parameter_count_b": 36,
            },
        )

        assert p.effective_parameter_count_b == 36
        assert p.capability_tier == "30B"
        assert p.is_local is True
        assert p.is_20b_plus is True
        assert p.routing_metadata()["provider"] == "ollama"
        assert p.routing_metadata()["roles"] == ["reasoning"]

    def test_capability_tier_does_not_infer_embedding_size_from_memory(self):
        p = ModelProfile(
            name="nomic-embed-text:latest",
            repo="nomic-embed-text:latest",
            role="embedding",
            estimated_memory_gb=0.5,
        )

        assert p.effective_parameter_count_b == 0
        assert p.capability_tier == "unknown"
        assert p.is_20b_plus is False

    def test_registry_merges_duplicate_qwen_roles(self):
        from antigravity_k.engine.model_registry import ModelRegistry

        # default(코딩/비전) 역할 부여로 3역할 병합 (registry 기본 모델 로직)
        profile = ModelRegistry().get_model("qwen3.8")

        assert profile is not None
        assert profile.role == "reasoning"
        assert profile.supported_roles == ("reasoning", "coding", "vision")
        assert profile.routing_metadata()["roles"] == ["reasoning", "coding", "vision"]

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

    def test_mlx_community_repo_prefers_mlx_over_local_name_heuristics(self):
        assert _infer_provider("qwen-mlx-local", "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit") == "mlx"

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


def test_project_defaults_prioritize_qwen38_for_reasoning_and_coding():
    registry = ModelRegistry()

    assert registry.defaults.reasoning == "qwen3.8"
    assert registry.defaults.coding == "qwen3.8"
