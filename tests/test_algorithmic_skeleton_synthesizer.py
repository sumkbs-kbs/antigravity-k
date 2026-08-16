"""Unit tests for AlgorithmicSkeletonSynthesizer."""

from antigravity_k.engine.algorithmic_skeleton_synthesizer import AlgorithmicSkeletonSynthesizer


def test_synthesize_contract_prompt():
    prompt = AlgorithmicSkeletonSynthesizer.synthesize_contract_prompt(
        task_description="Implement topological sort with cycle detection",
        function_name="topological_sort",
    )
    assert "topological_sort" in prompt
    assert "Pre-Conditions" in prompt
    assert "Post-Conditions" in prompt
    assert "Complexity Bounds" in prompt


def test_parse_contract_from_text():
    sample_reasoning = "Let's ensure Time complexity O(V + E) and Space O(V)"
    contract = AlgorithmicSkeletonSynthesizer.parse_contract_from_text(sample_reasoning, "topological_sort")

    assert contract.function_name == "topological_sort"
    assert "O(V + E)" in contract.time_complexity_target
