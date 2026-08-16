"""Unit tests for ZeroWasteCompressor."""

from antigravity_k.engine.zero_waste_compressor import ZeroWasteCompressor


def test_zero_waste_compression():
    bloated_prompt = """
Hello! I would be happy to help with your request.
As an AI language model, here is the code:

<!-- internal comment -->
def calculate_trajectory():
    return 42

Let me know if you need anything else!
"""
    compressed = ZeroWasteCompressor.compress(bloated_prompt)
    assert compressed.saved_chars > 0
    assert "Hello!" not in compressed.text
    assert "As an AI language model" not in compressed.text
    assert "<!-- internal comment -->" not in compressed.text
    assert "def calculate_trajectory():" in compressed.text
