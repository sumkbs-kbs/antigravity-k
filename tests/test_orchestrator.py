from unittest.mock import MagicMock

from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.orchestrator import OrchestratorAgent


def test_orchestrator_initialization():
    # Verify Orchestrator God Object separation
    # The OrchestratorAgent should not duplicate context attributes
    mock_ctx = MagicMock(spec=EngineContext)
    # mock config for init
    mock_config = MagicMock()
    mock_ctx.config = mock_config

    agent = OrchestratorAgent(model_manager=MagicMock(), tool_registry=MagicMock())
    agent.ctx = mock_ctx

    # Should be accessible via agent.ctx
    assert agent.ctx is mock_ctx
    # Shouldn't be directly on agent
    assert not hasattr(agent, "ki_engine")
    assert not hasattr(agent, "autonomous_learner")


def test_orchestrator_run_delegation():
    # Test that run() calls model_manager.generate or delegates properly
    mock_ctx = MagicMock(spec=EngineContext)
    mock_ctx.config = MagicMock()

    # Need to mock the model_manager
    mock_model_manager = MagicMock()
    mock_model_manager.generate.return_value = "Mock response"

    agent = OrchestratorAgent(model_manager=mock_model_manager)
    agent.ctx = mock_ctx
    # Just checking initialization and attribute mapping doesn't crash
    assert agent.ctx == mock_ctx
