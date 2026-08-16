"""Unit tests for MCTSCodeExplorer."""

from antigravity_k.engine.mcts_code_explorer import MCTSCodeExplorer, MCTSNode


def test_mcts_tree_search():
    explorer = MCTSCodeExplorer(root_state="x = 0", max_iterations=5)

    def expand_fn(node: MCTSNode) -> list[tuple[str, str, str]]:
        if node.node_id == "root":
            return [
                ("cand1", "Add increment", "x = x + 1"),
                ("cand2", "Add assignment", "x = 42"),
            ]
        return []

    def eval_fn(code: str) -> float:
        return 1.0 if "42" in code else 0.5

    best = explorer.search_best_trajectory(expand_fn, eval_fn)
    assert best is not None
    assert "42" in best.code_state or "x = x + 1" in best.code_state
