"""Unit tests for SemanticQAEngine."""

from antigravity_k.engine.semantic_qa_engine import QATestScenario, SemanticQAEngine


def test_parse_accessibility_tree():
    sample_html = """
    <div class="container">
      <input id="username-input" name="username" type="text" />
      <button id="login-btn" type="submit">Sign In</button>
    </div>
    """
    elements = SemanticQAEngine.parse_accessibility_tree(sample_html)
    assert len(elements) == 2
    roles = [e.role for e in elements]
    assert "button" in roles
    assert "textbox" in roles


def test_evaluate_qa_scenario_pass():
    sample_html = """<button id="submit-order">Checkout</button>"""
    elements = SemanticQAEngine.parse_accessibility_tree(sample_html)

    scenario = QATestScenario(
        scenario_name="Click Checkout",
        target_url="http://localhost:3000",
        actions=["click #submit-order"],
        expected_outcome="Order placed",
    )

    res = SemanticQAEngine.evaluate_scenario(scenario, elements)
    assert res.passed is True
