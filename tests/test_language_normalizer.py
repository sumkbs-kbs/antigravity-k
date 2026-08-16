"""Tests for deterministic local-model language cleanup."""

from antigravity_k.engine.language_normalizer import (
    normalize_foreign_technical_terms,
    normalize_streaming_chunks,
)


def test_recurring_complexity_false_friend_becomes_korean() -> None:
    # Given: qwen3.6 repeatedly emits the Chinese spelling of "complexity".
    contaminated = "시간复杂도와 공간复杂도를 설명합니다."

    # When: the output is normalized before quality evaluation.
    normalized = normalize_foreign_technical_terms(contaminated)

    # Then: both occurrences use the Korean technical term without changing prose.
    assert normalized == "시간복잡도와 공간복잡도를 설명합니다."


def test_unknown_cjk_terms_are_preserved_for_explicit_revision() -> None:
    # Given: no deterministic Korean mapping is known for the emitted term.
    contaminated = "설명합니다写法"

    # When: normalization runs.
    normalized = normalize_foreign_technical_terms(contaminated)

    # Then: the unknown term remains visible to the quality gate and revision loop.
    assert normalized == contaminated


def test_simplified_and_traditional_complexity_variants_normalize_identically() -> None:
    # Given: one run emits simplified Chinese and another emits traditional Chinese.
    simplified = "시간复杂도"
    traditional = "공간複雜度"

    # When: both outputs are normalized.
    normalized_simplified = normalize_foreign_technical_terms(simplified)
    normalized_traditional = normalize_foreign_technical_terms(traditional)

    # Then: both variants resolve to the same Korean technical term.
    assert normalized_simplified == "시간복잡도"
    assert normalized_traditional == "공간복잡도"


def test_streaming_normalizer_handles_terms_split_across_chunks() -> None:
    # Given: a model stream splits the false friend between two chunks.
    chunks = iter(["시간复", "杂도와 공간", "複雜度"])

    # When: chunks are normalized without waiting for the full response.
    normalized_chunks = list(normalize_streaming_chunks(chunks))

    # Then: reassembled output is Korean and no partial source term leaks early.
    assert "".join(normalized_chunks) == "시간복잡도와 공간복잡도"
