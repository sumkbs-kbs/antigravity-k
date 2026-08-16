import json
from unittest.mock import MagicMock, patch

from antigravity_k.engine.context_compressor import ContextCompressor
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.engine_profile import EngineProfile
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.orchestrator.stream import run_stream
from antigravity_k.engine.task_state_store import TaskExecutionContext, TaskStateStore


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


def test_read_only_benchmark_without_tools_uses_direct_target_model(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("benchmark-direct", "benchmark prompt", "pending", "2026-01-01T00:00:00")
    store.save_checkpoint(
        "benchmark-direct",
        0,
        '{"benchmark_read_only": true, "expected_tools": []}',
        "",
    )
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("benchmark-direct", store)
    orchestrator._latest_user_text.side_effect = lambda messages: messages[0]["content"]
    orchestrator.manager.stream_generate.return_value = iter(["def fibonacci(n: int) -> int: return n"])

    output = "".join(
        run_stream(
            orchestrator,
            [{"role": "user", "content": "Write fibonacci"}],
            target_model="qwen3.6:latest",
        ),
    )

    assert output == "def fibonacci(n: int) -> int: return n"
    assert orchestrator.manager.stream_generate.call_args.kwargs["target"] == "qwen3.6:latest"
    assert "no tools" in orchestrator.manager.stream_generate.call_args.kwargs["prompt"].lower()


def test_direct_response_context_uses_tool_loop_without_state_graph(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("direct-response", "answer prompt", "pending", "2026-01-01T00:00:00")
    store.save_checkpoint("direct-response", 0, '{"direct_response": true}', "")
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("direct-response", store)
    orchestrator._latest_user_text.side_effect = lambda messages: messages[0]["content"]

    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        engine_type.return_value.run_loop.return_value = iter(["direct output"])
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "answer prompt"}],
                target_model="qwen3.6:latest",
            ),
        )

    assert output == "direct output"
    assert engine_type.return_value.run_loop.call_args.kwargs["direct_response"] is True
    assert engine_type.return_value.run_loop.call_args.kwargs["target_model"] == "qwen3.6:latest"
    assert engine_type.return_value.run_loop.call_args.kwargs["max_steps"] == 2


def test_expected_tools_context_bypasses_ceo_and_invokes_tool_loop(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("tool-contract", "read README", "pending", "2026-01-01T00:00:00")
    store.save_checkpoint(
        "tool-contract",
        0,
        '{"expected_tools": ["read_file"]}',
        "",
    )
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("tool-contract", store)
    orchestrator._latest_user_text.side_effect = lambda messages: messages[0]["content"]

    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        engine_type.return_value.run_loop.return_value = iter(["grounded summary"])
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "read README"}],
                target_model="qwen3.6:latest",
            ),
        )

    assert output == "grounded summary"
    assert engine_type.return_value.run_loop.call_args.args[1] == "SELF"
    assert engine_type.return_value.run_loop.call_args.kwargs["target_model"] == "qwen3.6:latest"
    assert engine_type.return_value.run_loop.call_args.kwargs["direct_response"] is False


def test_authoritative_memory_question_uses_tool_free_direct_response() -> None:
    # Given: memory resolves a read-only project question to an authoritative fact.
    orchestrator = MagicMock()
    orchestrator.task_execution_context = None
    orchestrator._latest_user_text.side_effect = lambda messages: messages[0]["content"]
    fact = MagicMock(
        key="project:decision:database",
        value="sqlite",
        source="project",
        scope="project",
    )
    orchestrator.ctx.memory_manager.authoritative_project_fact_for_query.return_value = fact

    # When: the ordinary runtime handles the memory-only question.
    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        engine_type.return_value.run_loop.return_value = iter(["SQLite"])
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "현재 프로젝트 데이터베이스 결정이 뭐야?"}],
                target_model="qwen3.6:latest",
            ),
        )

    # Then: the model receives recalled context without agent tools or state-graph execution.
    assert output == "SQLite"
    call = engine_type.return_value.run_loop.call_args
    assert call.kwargs["direct_response"] is True
    assert call.kwargs["target_model"] == "qwen3.6:latest"
    assert call.kwargs["max_steps"] == 2
    assert call.args[1:3] == ("SELF", "chat")
    assert call.args[0][0]["role"] == "system"
    assert "[resolved:project:decision:database source=project scope=project] sqlite" in call.args[0][0]["content"]
    orchestrator._state_graph.execute.assert_not_called()


def test_web_search_contract_uses_search_task_type_for_python_research(tmp_path):
    # Given: a web-search contract whose research topic contains a code keyword.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("web-research", "research Python 3.13 JIT", "pending", "2026-01-01T00:00:00")
    store.save_checkpoint(
        "web-research",
        0,
        '{"expected_tools": ["web_search"]}',
        "",
    )
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("web-research", store)
    orchestrator._latest_user_text.side_effect = lambda messages: messages[0]["content"]

    # When: the expected-tool fast path invokes the ToolLoop.
    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        engine_type.return_value.run_loop.return_value = iter(["grounded research"])
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "Python 3.13 JIT를 웹 검색으로 조사해"}],
                target_model="qwen3.6:latest",
            ),
        )

    # Then: search quality checks apply instead of code-block requirements.
    assert output == "grounded research"
    assert engine_type.return_value.run_loop.call_args.args[2] == "search"


def test_canonical_stream_bounds_single_oversized_user_goal_before_state_graph() -> None:
    # Given: the ordinary state-graph path receives one goal beyond the model budget.
    goal = "BEGIN_OBJECTIVE " + ("implementation detail " * 200) + " END_CONSTRAINT"
    orchestrator = MagicMock()
    orchestrator.task_execution_context = None
    orchestrator._latest_user_text.side_effect = lambda messages: messages[-1]["content"]
    orchestrator.ctx.memory_manager.authoritative_project_fact_for_query.return_value = None
    orchestrator.ctx.memory_manager.prefetch_all.return_value = ""
    orchestrator.trajectory_compressor_for.return_value = None
    compressor = ContextCompressor(token_limit=100)
    orchestrator.context_compressor_for.return_value = compressor
    orchestrator._state_graph = MagicMock()
    orchestrator._state_graph.execute.return_value = iter(())

    # When: canonical streaming prepares context for the model graph.
    with patch(
        "antigravity_k.engine.preflight_validator.PreflightValidator.validate",
        return_value=(True, "", EngineProfile.STRICT_ENGINEER),
    ):
        list(run_stream(orchestrator, [{"role": "user", "content": goal}], "qwen3.6:latest"))

    # Then: the graph receives a bounded objective that still exposes both constraints.
    state_context = orchestrator._state_graph.execute.call_args.args[0]
    assert sum(compressor.estimate_tokens(message["content"]) for message in state_context.messages) <= 100
    assert "BEGIN_OBJECTIVE" in state_context.messages[0]["content"]
    assert "END_CONSTRAINT" in state_context.messages[0]["content"]


def test_canonical_stream_persists_bounded_context_for_bound_task(tmp_path) -> None:
    # Given: a bound task whose oversized objective requires canonical compression.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("context-task", "goal", "running", "2026-01-01T00:00:00")
    goal = "BEGIN_OBJECTIVE " + ("implementation detail " * 200) + " END_CONSTRAINT"
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("context-task", store)
    orchestrator._latest_user_text.side_effect = lambda messages: messages[-1]["content"]
    orchestrator.ctx.memory_manager.authoritative_project_fact_for_query.return_value = None
    orchestrator.ctx.memory_manager.prefetch_all.return_value = ""
    orchestrator.trajectory_compressor_for.return_value = None
    orchestrator.context_compressor_for.return_value = ContextCompressor(token_limit=100)
    orchestrator._state_graph = MagicMock()
    orchestrator._state_graph.execute.return_value = iter(())

    # When: the canonical stream prepares the bounded model context.
    with patch(
        "antigravity_k.engine.preflight_validator.PreflightValidator.validate",
        return_value=(True, "", EngineProfile.STRICT_ENGINEER),
    ):
        list(run_stream(orchestrator, [{"role": "user", "content": goal}], "qwen3.6:latest"))

    # Then: a versioned task-local context snapshot is durable in the execution ledger.
    snapshots = [
        event for event in store.list_execution_events("context-task") if event["event_type"] == "context_snapshot"
    ]
    assert len(snapshots) == 1
    payload = json.loads(snapshots[0]["payload_json"])
    assert payload["version"] == 1
    assert payload["target_model"] == "qwen3.6:latest"
    assert "BEGIN_OBJECTIVE" in payload["messages"][0]["content"]
    assert "END_CONSTRAINT" in payload["messages"][0]["content"]
