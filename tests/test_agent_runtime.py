from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from antigravity_k.engine.agent_runtime import AgentRuntime, TrackedStream
from antigravity_k.engine.task_runner import BackgroundTaskRunner
from antigravity_k.engine.task_state_store import TaskExecutionContext, TaskStateStore


class FakeOrchestrator:
    def __init__(self) -> None:
        self.stream_calls: list[dict[str, object]] = []

    def _get_model_for_role(self, role: str) -> str:
        assert role == "default"
        return "qwen3.6:latest"

    def get_model_for_role(self, role: str) -> str:
        return self._get_model_for_role(role)

    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Iterator[str]:
        self.stream_calls.append(
            {
                "messages": messages,
                "target_model": target_model,
                "max_steps": max_steps,
                "ephemeral_message": ephemeral_message,
            },
        )
        yield "first"
        yield "second"


class FakeTaskRunner:
    def __init__(self) -> None:
        self.submit_calls: list[dict[str, object]] = []
        self.cancel_calls: list[str] = []

    def submit_task(self, **kwargs: object) -> str:
        self.submit_calls.append(kwargs)
        return "task_runtime_001"

    def resume_task(self, **kwargs: object) -> bool:
        self.submit_calls.append(kwargs)
        return True

    def cancel_task(self, task_id: str) -> bool:
        self.cancel_calls.append(task_id)
        return True

    def get_status(self, task_id: str) -> dict[str, object] | None:
        return {"task_id": task_id, "status": "done"}

    def list_tasks(self, limit: int = 20) -> list[dict[str, object]]:
        return [{"task_id": "task_runtime_001", "status": "done"}][:limit]

    def get_output(self, task_id: str) -> str | None:
        return "runtime-output" if task_id == "task_runtime_001" else None

    def wait_task(self, task_id: str, timeout: float | None = None) -> dict[str, object] | None:
        return {"task_id": task_id, "status": "done", "timeout": timeout}


class BoundOrchestrator(FakeOrchestrator):
    def __init__(self) -> None:
        super().__init__()
        self._execution_context: ContextVar[TaskExecutionContext | None] = ContextVar(
            "runtime_test_execution_context",
            default=None,
        )

    @property
    def task_execution_context(self) -> TaskExecutionContext | None:
        return self._execution_context.get()

    @contextmanager
    def bind_task_execution(self, task_id: str, state_store: TaskStateStore):
        token = self._execution_context.set(TaskExecutionContext(task_id, state_store))
        try:
            yield
        finally:
            self._execution_context.reset(token)

    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Iterator[str]:
        assert self.task_execution_context is not None
        yield from super().run_stream(messages, target_model, max_steps, ephemeral_message)


def test_runtime_stream_resolves_default_model_and_preserves_execution_options():
    orchestrator = FakeOrchestrator()
    runtime = AgentRuntime(orchestrator)
    messages = [{"role": "user", "content": "hello"}]

    chunks = list(runtime.stream(messages, max_steps=7, ephemeral_message="context"))

    assert chunks == ["first", "second"]
    assert orchestrator.stream_calls == [
        {
            "messages": messages,
            "target_model": "qwen3.6:latest",
            "max_steps": 7,
            "ephemeral_message": "context",
        },
    ]


def test_runtime_complete_uses_explicit_model():
    orchestrator = FakeOrchestrator()
    runtime = AgentRuntime(orchestrator)

    result = runtime.complete([{"role": "user", "content": "hello"}], target_model="local-test")

    assert result == "firstsecond"
    assert orchestrator.stream_calls[0]["target_model"] == "local-test"


def test_runtime_cancels_background_task_through_runner():
    runner = FakeTaskRunner()
    runtime = AgentRuntime(FakeOrchestrator(), task_runner=runner)

    assert runtime.cancel_task("task_runtime_001") is True
    assert runner.cancel_calls == ["task_runtime_001"]


def test_runtime_exposes_durable_task_queries_and_wait_through_runner():
    # Given: the canonical runtime owns a durable task runner.
    runtime = AgentRuntime(FakeOrchestrator(), task_runner=FakeTaskRunner())

    # When: a CLI or API consumer queries one task and waits for it.
    status = runtime.get_task_status("task_runtime_001")
    tasks = runtime.list_tasks(limit=1)
    output = runtime.get_task_output("task_runtime_001")
    waited = runtime.wait_task("task_runtime_001", timeout=3)

    # Then: every view comes from the same runner-owned task record.
    assert status == {"task_id": "task_runtime_001", "status": "done"}
    assert tasks == [{"task_id": "task_runtime_001", "status": "done"}]
    assert output == "runtime-output"
    assert waited == {"task_id": "task_runtime_001", "status": "done", "timeout": 3}


def test_runtime_start_stream_persists_direct_execution_and_exposes_task_id(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    runtime = AgentRuntime(BoundOrchestrator(), task_runner=SimpleNamespace(state_store=store))

    tracked = runtime.start_stream([{"role": "user", "content": "hello"}])

    assert tracked.task_id is not None
    assert list(tracked.chunks) == ["first", "second"]
    record = store.get_task(tracked.task_id)
    assert record is not None
    assert record["status"] == "done"
    assert record["output"] == "firstsecond"
    assert [event["event_type"] for event in store.list_execution_events(tracked.task_id)] == [
        "interactive_registered",
        "context_snapshot",
        "interactive_started",
        "interactive_completed",
    ]


def test_runtime_direct_stream_persists_normalized_language_output(tmp_path):
    # Given: a direct qwen stream splits a known Chinese false friend across chunks.
    class ContaminatedOrchestrator(BoundOrchestrator):
        def run_stream(
            self,
            messages: list[dict[str, str]],
            target_model: str,
            max_steps: int = 15,
            ephemeral_message: str | None = None,
        ) -> Iterator[str]:
            assert self.task_execution_context is not None
            yield "시간复"
            yield "杂도와 공간複雜度"

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    runtime = AgentRuntime(ContaminatedOrchestrator(), task_runner=SimpleNamespace(state_store=store))

    # When: the durable direct stream completes.
    tracked = runtime.start_stream([{"role": "user", "content": "복잡도를 설명해줘"}])
    chunks = list(tracked.chunks)

    # Then: both the user stream and durable output contain Korean terms only.
    normalized = "시간복잡도와 공간복잡도"
    assert "".join(chunks) == normalized
    record = store.get_task(tracked.task_id)
    assert record is not None
    assert record["output"] == normalized


def test_runtime_direct_task_stores_canonical_final_output(tmp_path):
    # Given: the user stream shows a rejected draft and then a quality revision.
    class RevisingOrchestrator(BoundOrchestrator):
        _last_agent_output = ""

        def run_stream(
            self,
            messages: list[dict[str, str]],
            target_model: str,
            max_steps: int = 15,
            ephemeral_message: str | None = None,
        ) -> Iterator[str]:
            assert self.task_execution_context is not None
            yield "draft with syntax error\n"
            yield "revision notice\n"
            yield "corrected final answer"
            self._last_agent_output = "corrected final answer"

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    orchestrator = RevisingOrchestrator()
    runtime = AgentRuntime(orchestrator, task_runner=SimpleNamespace(state_store=store))

    # When: the durable direct stream completes.
    tracked = runtime.start_stream([{"role": "user", "content": "코드를 작성해줘"}])
    chunks = list(tracked.chunks)

    # Then: the user saw the full stream, but the task record stores only the final answer.
    assert "".join(chunks) == "draft with syntax error\nrevision notice\ncorrected final answer"
    record = store.get_task(tracked.task_id)
    assert record is not None
    assert record["status"] == "done"
    assert record["output"] == "corrected final answer"


def test_runtime_records_an_explicitly_named_tool_as_a_durable_contract(tmp_path):
    # Given: the user explicitly requires one registered tool in a direct task.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    orchestrator = BoundOrchestrator()
    orchestrator.tool_registry = SimpleNamespace(get_names=lambda: ["read_file", "web_search"])
    runtime = AgentRuntime(orchestrator, task_runner=SimpleNamespace(state_store=store))

    # When: the direct runtime creates its tracked execution.
    tracked = runtime.start_stream([{"role": "user", "content": "read_file 도구로 README를 읽어줘"}])

    # Then: the checkpoint exposes the exact tool requirement to the tool loop.
    assert tracked.task_id is not None
    checkpoint = store.get_last_checkpoint(tracked.task_id)
    assert checkpoint is not None
    assert checkpoint["context_json"] == '{"expected_tools": ["read_file"]}'


def test_runtime_records_execution_intent_tool_named_with_korean_particle(tmp_path):
    # Given: a coding prompt that asks the model to write code AND execute it via run_bash_command.
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    orchestrator = BoundOrchestrator()
    orchestrator.tool_registry = SimpleNamespace(
        get_names=lambda: ["read_file", "web_search", "run_bash_command", "write_file"]
    )
    runtime = AgentRuntime(orchestrator, task_runner=SimpleNamespace(state_store=store))

    # When: the user names the tool with a Korean dative particle and an execution verb
    # (the realistic phrasing a Korean speaker uses, not the stilted "run_bash_command 도구" form).
    tracked = runtime.start_stream(
        [
            {
                "role": "user",
                "content": "sum_to(n) 함수를 작성하고 run_bash_command로 실행해서 결과가 5050인지 검증해줘.",
            }
        ]
    )

    # Then: the checkpoint exposes run_bash_command as a required tool so the loop forces
    # real execution instead of letting the model narrate the result.
    assert tracked.task_id is not None
    checkpoint = store.get_last_checkpoint(tracked.task_id)
    assert checkpoint is not None
    import json

    payload = json.loads(checkpoint["context_json"])
    assert payload["expected_tools"] == ["run_bash_command"]


def test_runtime_preserves_inner_quality_failure_without_terminal_transition_conflict(tmp_path):
    class QualityRejectedOrchestrator(BoundOrchestrator):
        def run_stream(
            self,
            messages: list[dict[str, str]],
            target_model: str,
            max_steps: int = 15,
            ephemeral_message: str | None = None,
        ) -> Iterator[str]:
            # Given: the bound tool loop has already rejected its own durable task outcome.
            execution_context = self.task_execution_context
            assert execution_context is not None
            execution_context.state_store.transition(
                execution_context.task_id,
                "failed",
                output="quality rejected",
                error="quality_gate_failed: unsupported answer",
            )

            # When: the direct runtime consumes the completed stream.
            yield "quality rejected"

    store = TaskStateStore(str(tmp_path / "tasks.db"))
    runtime = AgentRuntime(QualityRejectedOrchestrator(), task_runner=SimpleNamespace(state_store=store))
    tracked = runtime.start_stream([{"role": "user", "content": "verify this"}])

    # Then: it keeps the inner failure rather than incorrectly forcing the task to done.
    assert tracked.task_id is not None
    assert list(tracked.chunks) == ["quality rejected"]
    record = store.get_task(tracked.task_id)
    assert record is not None
    assert record["status"] == "failed"
    assert record["error"] == "quality_gate_failed: unsupported answer"
    checkpoint = store.get_last_checkpoint(tracked.task_id)
    assert checkpoint is not None
    assert checkpoint["output_so_far"] == "quality rejected"
    assert [event["event_type"] for event in store.list_execution_events(tracked.task_id)] == [
        "interactive_registered",
        "context_snapshot",
        "interactive_started",
        "interactive_failed",
    ]


def test_runtime_resumes_failed_direct_task_with_messages_and_partial_output(tmp_path) -> None:
    class RecoveringDirectOrchestrator(BoundOrchestrator):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0
            self.resumed_messages: list[dict[str, str]] = []

        def run_stream(
            self,
            messages: list[dict[str, str]],
            target_model: str,
            max_steps: int = 15,
            ephemeral_message: str | None = None,
        ) -> Iterator[str]:
            self.calls += 1
            if self.calls == 1:
                yield "partial-output\n"
                raise RuntimeError("temporary provider outage")
            self.resumed_messages = messages
            yield "DIRECT_RESUME_OK"

    # Given: a canonical direct task fails after emitting partial output.
    runner = BackgroundTaskRunner(db_path=str(tmp_path / "tasks.db"))
    orchestrator = RecoveringDirectOrchestrator()
    runtime = AgentRuntime(orchestrator, task_runner=runner)
    messages = [
        {"role": "system", "content": "PROJECT_CONTEXT_ALPHA"},
        {"role": "user", "content": "Finish this interactive task"},
    ]
    tracked = runtime.start_stream(messages, target_model="qwen3.6:latest")
    assert tracked.task_id is not None
    with pytest.raises(RuntimeError, match="temporary provider outage"):
        list(tracked.chunks)

    # When: the caller resumes the returned direct task ID.
    assert runtime.resume_task(tracked.task_id, target_model="qwen3.6:latest") is True
    resumed = runner._tasks[tracked.task_id]
    assert resumed._thread is not None
    resumed._thread.join(timeout=2)

    # Then: original context and partial output reach the resumed completion.
    restored = "\n".join(message["content"] for message in orchestrator.resumed_messages)
    record = runner.state_store.get_task(tracked.task_id)
    assert "PROJECT_CONTEXT_ALPHA" in restored
    assert "partial-output" in restored
    assert resumed.output == "partial-output\nDIRECT_RESUME_OK"
    assert record is not None
    assert record["status"] == "done"


def test_runtime_binds_itself_to_orchestrator():
    orchestrator = FakeOrchestrator()

    runtime = AgentRuntime(orchestrator)

    assert orchestrator.agent_runtime is runtime


def test_runtime_run_max_uses_orchestrator_engine():
    orchestrator = FakeOrchestrator()
    engine = MagicMock()
    engine.run.return_value = "max-result"
    orchestrator.max_engine = engine
    runtime = AgentRuntime(orchestrator)

    task_spec = {"prompt": "inspect"}

    assert runtime.run_max(task_spec) == "max-result"
    engine.run.assert_called_once_with(task_spec, orchestrator=orchestrator)


def test_runtime_run_max_persists_a_direct_execution_without_nesting_bound_tasks(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    orchestrator = BoundOrchestrator()
    result = SimpleNamespace(final_output="max-result", error=None)
    engine = MagicMock()
    engine.run.return_value = result
    orchestrator.max_engine = engine
    runtime = AgentRuntime(orchestrator, task_runner=SimpleNamespace(state_store=store))

    assert runtime.run_max({"prompt": "inspect"}) is result

    tasks = store.list_tasks(10)
    assert len(tasks) == 1
    assert tasks[0]["status"] == "done"
    assert tasks[0]["output"] == "max-result"
    assert [event["event_type"] for event in store.list_execution_events(tasks[0]["task_id"])] == [
        "max_execution_registered",
        "max_execution_started",
        "max_execution_completed",
    ]
    engine.run.assert_called_once_with({"prompt": "inspect"}, orchestrator=orchestrator)


def test_runtime_run_max_reuses_an_existing_state_graph_task_binding(tmp_path):
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    store.create_task("task-bound", "inspect", "pending", "2026-01-01T00:00:00")
    store.transition("task-bound", "running")
    orchestrator = BoundOrchestrator()
    result = SimpleNamespace(final_output="max-result", error=None)
    engine = MagicMock()
    engine.run.return_value = result
    orchestrator.max_engine = engine
    runtime = AgentRuntime(orchestrator, task_runner=SimpleNamespace(state_store=store))

    with orchestrator.bind_task_execution("task-bound", store):
        assert runtime.run_max({"prompt": "inspect"}) is result

    tasks = store.list_tasks(10)
    assert [task["task_id"] for task in tasks] == ["task-bound"]
    assert store.list_execution_events("task-bound") == []
    engine.run.assert_called_once_with({"prompt": "inspect"}, orchestrator=orchestrator)


@pytest.mark.asyncio
async def test_runtime_run_parallel_goals_constructs_bound_multiplexer(monkeypatch, tmp_path):
    import antigravity_k.engine.multiplexer as multiplexer_module

    orchestrator = FakeOrchestrator()
    runtime = AgentRuntime(orchestrator)
    fake_multiplexer = MagicMock()
    fake_multiplexer.run_parallel_goals = AsyncMock(return_value=[{"status": "success"}])
    multiplexer_class = MagicMock(return_value=fake_multiplexer)
    monkeypatch.setattr(multiplexer_module, "Multiplexer", multiplexer_class)

    result = await runtime.run_parallel_goals(
        [{"task_id": "task-1", "instruction": "inspect"}],
        project_root=str(tmp_path),
    )

    assert result == [{"status": "success"}]
    multiplexer_class.assert_called_once_with(str(tmp_path), agent_runtime=runtime)
    fake_multiplexer.run_parallel_goals.assert_awaited_once_with(
        [{"task_id": "task-1", "instruction": "inspect"}],
        base_branch="main",
    )


def test_runtime_goal_contract_uses_injected_goal_runner():
    class GoalRunner:
        def run(self, objective, context=None):
            return {"objective": objective, "context": context}

        def render_markdown(self, report):
            return f"contract:{report['objective']}"

    runtime = AgentRuntime(FakeOrchestrator(), goal_runner=GoalRunner())

    assert runtime.goal_contract("ship the feature", context={"tool_count": 4}) == "contract:ship the feature"


def test_slash_goal_uses_bound_agent_runtime():
    from antigravity_k.engine.slash_commands import SlashCommandRegistry

    class Runtime:
        def goal_contract(self, objective, context=None):
            return f"runtime-goal:{objective}:{context['tool_count']}"

    registry = SlashCommandRegistry(tool_registry=["tool"], agent_runtime=Runtime())

    assert registry.execute("/goal ship the feature") == "runtime-goal:ship the feature:1"


def test_slash_natural_language_uses_bound_agent_runtime():
    from antigravity_k.engine.slash_commands import SlashCommandRegistry

    calls = []

    class ModelManager:
        def get_model_info(self):
            return {"active_model": "qwen3.6:latest"}

    class Runtime:
        def complete(self, messages, target_model):
            calls.append({"messages": messages, "target_model": target_model})
            return "runtime-complete"

    registry = SlashCommandRegistry(model_manager=ModelManager(), agent_runtime=Runtime())

    assert registry.execute("summarize the project") == "runtime-complete"
    assert calls == [
        {
            "messages": [{"role": "user", "content": "summarize the project"}],
            "target_model": "qwen3.6:latest",
        },
    ]


def test_legacy_slash_registry_receives_bound_agent_runtime(monkeypatch):
    from antigravity_k.api.routes import legacy

    runtime = object()
    monkeypatch.setattr(legacy, "_slash_registry", None)
    monkeypatch.setattr(legacy, "get_agent_runtime", lambda: runtime)
    monkeypatch.setattr(legacy, "__get_tool_registry", lambda: [])
    monkeypatch.setattr(legacy, "_get_session_manager", lambda: None)
    monkeypatch.setattr(legacy, "_get_context_shaper", lambda: None)
    monkeypatch.setattr(legacy, "get_model_manager", lambda: None)
    monkeypatch.setattr(legacy, "__get_skill_loader", lambda: None)

    registry = legacy._get_slash_registry()

    assert registry._agent_runtime is runtime


def test_runtime_submits_background_work_through_same_orchestrator_and_model():
    orchestrator = FakeOrchestrator()
    runner = FakeTaskRunner()
    runtime = AgentRuntime(orchestrator, task_runner=runner)

    task_id = runtime.submit_task(
        "inspect the project",
        context={"expected_tools": ["read_file"]},
        idempotency_key="request-001",
    )

    assert task_id == "task_runtime_001"
    assert len(runner.submit_calls) == 1
    submitted = runner.submit_calls[0]
    assert submitted["prompt"] == "inspect the project"
    assert submitted["orchestrator"] is orchestrator
    assert submitted["target_model"] == "qwen3.6:latest"
    assert submitted["use_worktree"] is False
    assert submitted["idempotency_key"] == "request-001"
    context = submitted["context"]
    assert isinstance(context, dict)
    assert context["expected_tools"] == ["read_file"]
    plan = context["task_plan"]
    assert isinstance(plan, dict)
    assert plan["objective"] == "inspect the project"
    assert plan["steps"]
    assert plan["judgment"]["decision"] in {"plan_first", "execute_with_verification"}


def test_runtime_requires_task_runner_for_background_work():
    runtime = AgentRuntime(FakeOrchestrator())

    with pytest.raises(RuntimeError, match="task runner"):
        runtime.submit_task("run later")


def test_runtime_resumes_background_work_through_same_orchestrator():
    orchestrator = FakeOrchestrator()
    runner = FakeTaskRunner()
    runtime = AgentRuntime(orchestrator, task_runner=runner)

    assert runtime.resume_task("task_runtime_001") is True
    assert runner.submit_calls == [
        {
            "task_id": "task_runtime_001",
            "orchestrator": orchestrator,
            "target_model": "qwen3.6:latest",
        },
    ]


@pytest.mark.asyncio
async def test_background_task_route_uses_canonical_runtime(monkeypatch):
    from antigravity_k.api.routes import legacy

    calls: list[dict[str, object]] = []

    class Runtime:
        def submit_task(self, **kwargs: object) -> str:
            calls.append(kwargs)
            return "task_route_001"

    class Request:
        async def json(self) -> dict[str, object]:
            return {
                "prompt": "inspect the project",
                "context": {"expected_tools": ["read_file"]},
                "model": "",
                "idempotency_key": "route-001",
            }

    monkeypatch.setattr(legacy, "get_agent_runtime", lambda: Runtime())

    result = await legacy.submit_background_task(Request(), MagicMock(), None)

    assert result == {"status": "submitted", "task_id": "task_route_001"}
    assert calls == [
        {
            "prompt": "inspect the project",
            "context": {"expected_tools": ["read_file"]},
            "target_model": "",
            "idempotency_key": "route-001",
        },
    ]


@pytest.mark.asyncio
async def test_agent_api_resume_route_uses_canonical_runtime(monkeypatch):
    from antigravity_k.api.routes import agent_api

    resumed_task_ids: list[str] = []

    class Runtime:
        def resume_task(self, task_id: str) -> bool:
            resumed_task_ids.append(task_id)
            return True

    monkeypatch.setattr(agent_api, "get_agent_runtime", lambda: Runtime())

    result = await agent_api.resume_task("task_runtime_001")

    assert result == {"status": "resumed", "task_id": "task_runtime_001"}
    assert resumed_task_ids == ["task_runtime_001"]


@pytest.mark.asyncio
async def test_agent_api_task_views_use_canonical_runtime(monkeypatch):
    from antigravity_k.api.routes import agent_api

    class Runtime:
        def get_task_status(self, task_id: str) -> dict[str, object] | None:
            return {"task_id": task_id, "status": "failed"}

        def list_tasks(self, limit: int) -> list[dict[str, object]]:
            return [{"task_id": "direct_001", "status": "failed"}][:limit]

        def get_task_output(self, task_id: str) -> str | None:
            return "partial-output" if task_id == "direct_001" else None

    monkeypatch.setattr(agent_api, "get_agent_runtime", lambda: Runtime())

    status = await agent_api.get_task_status("direct_001")
    tasks = await agent_api.list_tasks.__wrapped__(limit=1)
    output = await agent_api.get_task_output("direct_001")

    assert status["data"] == {"task_id": "direct_001", "status": "failed"}
    assert tasks["data"] == [{"task_id": "direct_001", "status": "failed"}]
    assert output == {"status": "ok", "task_id": "direct_001", "output": "partial-output"}


@pytest.mark.asyncio
async def test_agent_stream_route_emits_direct_task_id_before_chunks(monkeypatch):
    from antigravity_k.api.routes import agent_api

    class Runtime:
        orchestrator = None

        def start_stream(self, messages: list[dict[str, str]]) -> TrackedStream:
            assert messages == [{"role": "user", "content": "track this"}]
            return TrackedStream(task_id="direct_001", chunks=iter(["runtime-response"]))

    monkeypatch.setattr(agent_api, "get_agent_runtime", lambda: Runtime())

    response = await agent_api.stream_agent(q="track this")
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    assert '"task_id": "direct_001"' in body
    assert "runtime-response" in body


@pytest.mark.asyncio
async def test_chat_stream_route_uses_canonical_runtime(monkeypatch):
    from antigravity_k.api.routes import chat
    from antigravity_k.engine.protocol_translator import ProtocolTranslator

    calls: list[dict[str, object]] = []

    class Runtime:
        def stream(self, messages: list[dict[str, str]], target_model: str) -> Iterator[str]:
            calls.append({"messages": messages, "target_model": target_model})
            yield "runtime-response"

    class Request:
        async def json(self) -> dict[str, object]:
            return {
                "model": "test-combo",
                "messages": [{"role": "user", "content": "Explain the runtime"}],
                "stream": True,
                "agent_mode": True,
            }

    manager = MagicMock()
    manager.generate.return_value = "GENERAL"
    monkeypatch.setattr(chat, "get_agent_runtime", lambda: Runtime())

    response = await chat.chat_completions(Request(), manager, ProtocolTranslator())
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    assert "runtime-response" in body
    assert len(calls) == 1
    assert calls[0]["messages"][-1] == {"role": "user", "content": "Explain the runtime"}
    assert calls[0]["target_model"] == "test-combo"
