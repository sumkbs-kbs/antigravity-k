import json
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from antigravity_k.engine.context_compressor import ContextCompressor
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.engine_profile import EngineProfile
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.orchestrator.stream import run_stream
from antigravity_k.engine.task_state_store import TaskExecutionContext, TaskStateStore


def _first_message_content(messages: list[dict[str, str]]) -> str:
    return messages[0]["content"]


def _last_message_content(messages: list[dict[str, str]]) -> str:
    return messages[-1]["content"]


def _mock_path(root: MagicMock, path: tuple[str, ...]) -> MagicMock:
    current: object = root
    for name in path:
        current = cast(MagicMock, cast(object, getattr(current, name)))
    return current


def _set_mock_return(root: MagicMock, path: tuple[str, ...], value: object) -> None:
    setattr(_mock_path(root, path), "return_value", value)


def _set_mock_attr(root: MagicMock, path: tuple[str, ...], value: object) -> None:
    names = list(path)
    if not names:
        raise ValueError("mock attribute path must not be empty")
    parent = _mock_path(root, path[:-1]) if len(path) > 1 else root
    setattr(parent, names[-1], value)


def _set_mock_side_effect(root: MagicMock, path: tuple[str, ...], value: object) -> None:
    setattr(_mock_path(root, path), "side_effect", value)


def _mock_call_args(root: MagicMock, path: tuple[str, ...]) -> tuple[tuple[object, ...], dict[str, object]]:
    call_args = cast(object, getattr(_mock_path(root, path), "call_args"))
    args = cast(tuple[object, ...], cast(object, getattr(call_args, "args")))
    kwargs = cast(dict[str, object], cast(object, getattr(call_args, "kwargs")))
    return args, kwargs


def _assert_mock_not_called(root: MagicMock, path: tuple[str, ...]) -> None:
    method = cast(Callable[[], object], cast(object, getattr(_mock_path(root, path), "assert_not_called")))
    _ = method()


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
    _set_mock_return(mock_model_manager, ("generate",), "Mock response")

    agent = OrchestratorAgent(model_manager=mock_model_manager)
    agent.ctx = mock_ctx
    # Just checking initialization and attribute mapping doesn't crash
    assert agent.ctx == mock_ctx


def test_read_only_benchmark_without_tools_uses_direct_target_model(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("benchmark-direct", "benchmark prompt", "pending", "2026-01-01T00:00:00")
    _ = store.save_checkpoint(
        "benchmark-direct",
        0,
        '{"benchmark_read_only": true, "expected_tools": []}',
        "",
    )
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("benchmark-direct", store)
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _first_message_content)
    _set_mock_return(orchestrator, ("manager", "stream_generate"), iter(["def fibonacci(n: int) -> int: return n"]))

    output = "".join(
        run_stream(
            orchestrator,
            [{"role": "user", "content": "Write fibonacci"}],
            target_model="qwen3.6:latest",
        ),
    )

    assert output == "def fibonacci(n: int) -> int: return n"
    _, stream_kwargs = _mock_call_args(orchestrator, ("manager", "stream_generate"))
    assert stream_kwargs["target"] == "qwen3.6:latest"
    assert "no tools" in cast(str, stream_kwargs["prompt"]).lower()


def test_direct_response_context_uses_tool_loop_without_state_graph(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("direct-response", "answer prompt", "pending", "2026-01-01T00:00:00")
    _ = store.save_checkpoint("direct-response", 0, '{"direct_response": true}', "")
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("direct-response", store)
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _first_message_content)

    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        _set_mock_return(engine_type, ("return_value", "run_loop"), iter(["direct output"]))
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "answer prompt"}],
                target_model="qwen3.6:latest",
            ),
        )

    assert output == "direct output"
    _, run_kwargs = _mock_call_args(engine_type, ("return_value", "run_loop"))
    assert run_kwargs["direct_response"] is True
    assert run_kwargs["target_model"] == "qwen3.6:latest"
    assert run_kwargs["max_steps"] == 2


def test_expected_tools_context_bypasses_ceo_and_invokes_tool_loop(tmp_path: Path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("tool-contract", "read README", "pending", "2026-01-01T00:00:00")
    _ = store.save_checkpoint(
        "tool-contract",
        0,
        '{"expected_tools": ["read_file"]}',
        "",
    )
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("tool-contract", store)
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _first_message_content)

    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        _set_mock_return(engine_type, ("return_value", "run_loop"), iter(["grounded summary"]))
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "read README"}],
                target_model="qwen3.6:latest",
            ),
        )

    assert output == "grounded summary"
    run_args, run_kwargs = _mock_call_args(engine_type, ("return_value", "run_loop"))
    assert run_args[1] == "SELF"
    assert run_kwargs["target_model"] == "qwen3.6:latest"
    assert run_kwargs["direct_response"] is False


def test_authoritative_memory_question_uses_tool_free_direct_response() -> None:
    # Given: memory resolves a read-only project question to an authoritative fact.
    orchestrator = MagicMock()
    orchestrator.task_execution_context = None
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _first_message_content)
    fact = MagicMock(
        key="project:decision:database",
        value="sqlite",
        source="project",
        scope="project",
    )
    _set_mock_return(orchestrator, ("ctx", "memory_manager", "authoritative_project_fact_for_query"), fact)

    # When: the ordinary runtime handles the memory-only question.
    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        _set_mock_return(engine_type, ("return_value", "run_loop"), iter(["SQLite"]))
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "현재 프로젝트 데이터베이스 결정이 뭐야?"}],
                target_model="qwen3.6:latest",
            ),
        )

    # Then: the model receives recalled context without agent tools or state-graph execution.
    assert output == "SQLite"
    call_args, call_kwargs = _mock_call_args(engine_type, ("return_value", "run_loop"))
    assert call_kwargs["direct_response"] is True
    assert call_kwargs["target_model"] == "qwen3.6:latest"
    assert call_kwargs["max_steps"] == 2
    assert call_args[1:3] == ("SELF", "chat")
    call_messages = cast(list[dict[str, str]], call_args[0])
    assert call_messages[0]["role"] == "system"
    assert "[resolved:project:decision:database source=project scope=project] sqlite" in call_messages[0]["content"]
    _assert_mock_not_called(orchestrator, ("_state_graph", "execute"))


def test_web_search_contract_uses_search_task_type_for_python_research(tmp_path: Path):
    # Given: a web-search contract whose research topic contains a code keyword.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("web-research", "research Python 3.13 JIT", "pending", "2026-01-01T00:00:00")
    _ = store.save_checkpoint(
        "web-research",
        0,
        '{"expected_tools": ["web_search"]}',
        "",
    )
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("web-research", store)
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _first_message_content)

    # When: the expected-tool fast path invokes the ToolLoop.
    with patch("antigravity_k.engine.tool_loop.ToolLoopEngine") as engine_type:
        _set_mock_return(engine_type, ("return_value", "run_loop"), iter(["grounded research"]))
        output = "".join(
            run_stream(
                orchestrator,
                [{"role": "user", "content": "Python 3.13 JIT를 웹 검색으로 조사해"}],
                target_model="qwen3.6:latest",
            ),
        )

    # Then: search quality checks apply instead of code-block requirements.
    assert output == "grounded research"
    run_args, _ = _mock_call_args(engine_type, ("return_value", "run_loop"))
    assert run_args[2] == "search"


def test_canonical_stream_bounds_single_oversized_user_goal_before_state_graph() -> None:
    # Given: the ordinary state-graph path receives one goal beyond the model budget.
    goal = "BEGIN_OBJECTIVE " + ("implementation detail " * 200) + " END_CONSTRAINT"
    orchestrator = MagicMock()
    orchestrator.task_execution_context = None
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _last_message_content)
    _set_mock_return(orchestrator, ("ctx", "memory_manager", "authoritative_project_fact_for_query"), None)
    _set_mock_return(orchestrator, ("ctx", "memory_manager", "prefetch_all"), "")
    _set_mock_return(orchestrator, ("trajectory_compressor_for",), None)
    compressor = ContextCompressor(token_limit=100)
    _set_mock_return(orchestrator, ("context_compressor_for",), compressor)
    _set_mock_attr(orchestrator, ("_state_graph",), MagicMock())
    _set_mock_return(orchestrator, ("_state_graph", "execute"), iter(()))

    # When: canonical streaming prepares context for the model graph.
    with patch(
        "antigravity_k.engine.preflight_validator.PreflightValidator.validate",
        return_value=(True, "", EngineProfile.STRICT_ENGINEER),
    ):
        _ = list(run_stream(orchestrator, [{"role": "user", "content": goal}], "qwen3.6:latest"))

    # Then: the graph receives a bounded objective that still exposes both constraints.
    state_args, _ = _mock_call_args(orchestrator, ("_state_graph", "execute"))
    state_context = state_args[0]
    messages = cast(list[dict[str, str]], getattr(state_context, "messages"))
    assert sum(compressor.estimate_tokens(message["content"]) for message in messages) <= 100
    assert "BEGIN_OBJECTIVE" in messages[0]["content"]
    assert "END_CONSTRAINT" in messages[0]["content"]


def test_canonical_stream_persists_bounded_context_for_bound_task(tmp_path: Path) -> None:
    # Given: a bound task whose oversized objective requires canonical compression.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    _ = store.create_task("context-task", "goal", "running", "2026-01-01T00:00:00")
    goal = "BEGIN_OBJECTIVE " + ("implementation detail " * 200) + " END_CONSTRAINT"
    orchestrator = MagicMock()
    orchestrator.task_execution_context = TaskExecutionContext("context-task", store)
    _set_mock_side_effect(orchestrator, ("_latest_user_text",), _last_message_content)
    _set_mock_return(orchestrator, ("ctx", "memory_manager", "authoritative_project_fact_for_query"), None)
    _set_mock_return(orchestrator, ("ctx", "memory_manager", "prefetch_all"), "")
    _set_mock_return(orchestrator, ("trajectory_compressor_for",), None)
    _set_mock_return(orchestrator, ("context_compressor_for",), ContextCompressor(token_limit=100))
    _set_mock_attr(orchestrator, ("_state_graph",), MagicMock())
    _set_mock_return(orchestrator, ("_state_graph", "execute"), iter(()))

    # When: the canonical stream prepares the bounded model context.
    with patch(
        "antigravity_k.engine.preflight_validator.PreflightValidator.validate",
        return_value=(True, "", EngineProfile.STRICT_ENGINEER),
    ):
        _ = list(run_stream(orchestrator, [{"role": "user", "content": goal}], "qwen3.6:latest"))

    # Then: a versioned task-local context snapshot is durable in the execution ledger.
    snapshots = [
        event for event in store.list_execution_events("context-task") if event["event_type"] == "context_snapshot"
    ]
    assert len(snapshots) == 1
    payload = cast(dict[str, object], json.loads(snapshots[0]["payload_json"]))
    assert payload["version"] == 1
    assert payload["target_model"] == "qwen3.6:latest"
    payload_messages = cast(list[dict[str, str]], payload["messages"])
    assert "BEGIN_OBJECTIVE" in payload_messages[0]["content"]
    assert "END_CONSTRAINT" in payload_messages[0]["content"]
