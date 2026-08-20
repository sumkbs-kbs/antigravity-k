from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Protocol, final

from antigravity_k.engine.direct_task_execution import (
    DirectTaskExecution,
    MaxEnginePort,
    MaxRunResultPort,
    TaskOutcomeRecorder,
    TaskStoreRunnerPort,
    TrackedStream,
)
from antigravity_k.engine.goal_runner import GoalReport, GoalRunner
from antigravity_k.engine.task_state_store import ExecutionEventRecord


class OrchestratorPort(Protocol):
    @property
    def max_engine(self) -> MaxEnginePort | None: ...

    def get_model_for_role(self, role: str) -> str: ...

    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Iterator[str]: ...


class TaskRunnerPort(Protocol):
    def submit_task(
        self,
        prompt: str,
        context: dict[str, object] | None = None,
        orchestrator: OrchestratorPort | None = None,
        target_model: str = "",
        use_worktree: bool = False,
        idempotency_key: str | None = None,
    ) -> str: ...

    def resume_task(
        self,
        task_id: str,
        orchestrator: OrchestratorPort | None = None,
        target_model: str = "",
    ) -> bool: ...

    def cancel_task(self, task_id: str) -> bool: ...

    def get_status(self, task_id: str) -> dict[str, object] | None: ...

    def list_tasks(self, limit: int = 20) -> list[dict[str, object]]: ...

    def get_output(self, task_id: str) -> str | None: ...

    def wait_task(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> dict[str, object] | None: ...


class GoalRunnerPort(Protocol):
    def run(self, objective: str, context: Mapping[str, object] | None = None) -> GoalReport: ...

    def render_markdown(self, report: GoalReport) -> str: ...


@final
class AgentRuntime:
    def __init__(
        self,
        orchestrator: OrchestratorPort,
        task_runner: TaskRunnerPort | None = None,
        goal_runner: GoalRunnerPort | None = None,
        task_outcome_recorder: TaskOutcomeRecorder | None = None,
    ) -> None:
        self.is_canonical_runtime = True
        self.orchestrator = orchestrator
        self.task_runner = task_runner
        self.goal_runner = goal_runner or GoalRunner()
        self._direct_tasks = DirectTaskExecution(
            orchestrator,
            task_runner if isinstance(task_runner, TaskStoreRunnerPort) else None,
            task_outcome_recorder,
        )
        if getattr(orchestrator, "agent_runtime", None) is None:
            setattr(orchestrator, "agent_runtime", self)

    def resolve_model(self, target_model: str = "") -> str:
        model = target_model.strip() if target_model else ""
        if model:
            return model
        resolved = self.orchestrator.get_model_for_role("default")
        if not resolved:
            raise RuntimeError("orchestrator did not provide a default model")
        return resolved

    def stream(
        self,
        messages: Sequence[Mapping[str, str]],
        target_model: str = "",
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Iterator[str]:
        yield from self.start_stream(
            messages,
            target_model=target_model,
            max_steps=max_steps,
            ephemeral_message=ephemeral_message,
        ).chunks

    def start_stream(
        self,
        messages: Sequence[Mapping[str, str]],
        target_model: str = "",
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> TrackedStream:
        return self._direct_tasks.start_stream(
            messages,
            target_model=self.resolve_model(target_model),
            max_steps=max_steps,
            ephemeral_message=ephemeral_message,
        )

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        target_model: str = "",
        max_steps: int = 15,
    ) -> str:
        return "".join(self.stream(messages, target_model=target_model, max_steps=max_steps))

    def goal_contract(self, objective: str, context: Mapping[str, object] | None = None) -> str:
        report = self.plan_task(objective, context=context)
        return self.goal_runner.render_markdown(report)

    def plan_task(self, objective: str, context: Mapping[str, object] | None = None) -> GoalReport:
        return self.goal_runner.run(objective, context=context)

    def run_max(self, task_spec: dict[str, object]) -> MaxRunResultPort:
        engine = self.orchestrator.max_engine
        if engine is None:
            raise RuntimeError("max engine is required for MAX execution")
        return self._direct_tasks.run_max(engine, task_spec)

    async def run_parallel_goals(
        self,
        goals: list[dict[str, object]],
        project_root: str,
        base_branch: str = "main",
    ) -> list[object]:
        from antigravity_k.engine.multiplexer import Multiplexer

        multiplexer = Multiplexer(project_root, agent_runtime=self)
        results: list[dict[str, str] | BaseException] = await multiplexer.run_parallel_goals(
            goals,
            base_branch=base_branch,
        )
        return list(results)

    def submit_task(
        self,
        prompt: str,
        context: dict[str, object] | None = None,
        target_model: str = "",
        use_worktree: bool = False,
        idempotency_key: str | None = None,
    ) -> str:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for background task submission")
        execution_context = dict(context or {})
        execution_context["task_plan"] = self.plan_task(prompt, context=execution_context).to_dict()
        return self.task_runner.submit_task(
            prompt=prompt,
            context=execution_context,
            orchestrator=self.orchestrator,
            target_model=self.resolve_model(target_model),
            use_worktree=use_worktree,
            idempotency_key=idempotency_key,
        )

    def resume_task(self, task_id: str, target_model: str = "") -> bool:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for background task resume")
        return self.task_runner.resume_task(
            task_id=task_id,
            orchestrator=self.orchestrator,
            target_model=self.resolve_model(target_model),
        )

    def get_task_status(self, task_id: str) -> dict[str, object] | None:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for task status")
        return self.task_runner.get_status(task_id)

    def list_tasks(self, limit: int = 20) -> list[dict[str, object]]:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for task listing")
        return self.task_runner.list_tasks(limit=limit)

    def get_task_output(self, task_id: str) -> str | None:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for task output")
        return self.task_runner.get_output(task_id)

    def list_task_events(
        self,
        task_id: str,
        after_sequence: int = 0,
        limit: int = 1_000,
    ) -> list[ExecutionEventRecord]:
        if not isinstance(self.task_runner, TaskStoreRunnerPort):
            raise RuntimeError("task state store is required for event replay")
        return self.task_runner.state_store.list_execution_events(
            task_id,
            after_sequence=after_sequence,
            limit=limit,
        )

    def wait_task(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> dict[str, object] | None:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for task wait")
        return self.task_runner.wait_task(task_id, timeout=timeout)

    def cancel_task(self, task_id: str) -> bool:
        if self.task_runner is None:
            raise RuntimeError("task runner is required for background task cancellation")
        return self.task_runner.cancel_task(task_id)


__all__ = ["AgentRuntime", "GoalRunnerPort", "OrchestratorPort", "TaskRunnerPort", "TrackedStream"]
