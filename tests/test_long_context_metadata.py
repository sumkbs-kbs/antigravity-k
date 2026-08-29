from collections.abc import Mapping
from typing import cast

from pydantic import JsonValue

from antigravity_k.engine.long_context_metadata import infer_long_context_capabilities


def test_explicit_model_metadata_promotes_long_context_capabilities() -> None:
    metadata = {
        "sparse_attention": True,
        "attention": {"attention_type": "gated_linear"},
        "kv_cache_compression": True,
    }

    capabilities = infer_long_context_capabilities(cast(Mapping[str, JsonValue], cast(object, metadata)))

    assert capabilities == ("kv_cache_compression", "linear_attention", "sparse_attention")


def test_implementation_accelerators_do_not_claim_structural_long_context_support() -> None:
    metadata = {
        "attn_implementation": "flash_attention_2",
        "cache_implementation": "paged",
        "capabilities": ["paged_attention"],
    }

    assert infer_long_context_capabilities(cast(Mapping[str, JsonValue], cast(object, metadata))) == ()


def test_false_or_unknown_metadata_is_not_promoted() -> None:
    metadata = {
        "use_sparse_attention": False,
        "attention_type": "full",
        "kv_cache_compression": "auto",
    }

    assert infer_long_context_capabilities(metadata) == ()
