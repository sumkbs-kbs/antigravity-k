from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, final, runtime_checkable

from antigravity_k.engine.benchmark_harness import TaskOutcome
from antigravity_k.engine.language_normalizer import normalize_streaming_chunks
from antigravity_k.engine.task_context_snapshot import save_task_context_snapshot
from antigravity_k.engine.task_execution_context import TaskStateStoreProtocol
from antigravity_k.engine.task_state_store import (
    TaskExecutionContext,
    TaskStateStore,
    current_task_execution_context,
)

TaskOutcomeRecorder = Callable[[TaskOutcome], TaskOutcome | None]


@dataclass(frozen=True, slots=True)
class TrackedStream:
    task_id: str | None
    chunks: Iterator[str]


class StreamOrchestratorPort(Protocol):
    def run_stream(
        self,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int = 15,
        ephemeral_message: str | None = None,
    ) -> Iterator[str]: ...


class MaxRunResultPort(Protocol):
    final_output: str
    error: str | None


class MaxEnginePort(Protocol):
    def set_max_workers(self, n: int) -> None: ...

    def run(
        self,
        task_spec: dict[str, object],
        orchestrator: object | None = None,
    ) -> MaxRunResultPort: ...


@runtime_checkable
class ToolRegistryPort(Protocol):
    def get_names(self) -> list[str]: ...


@runtime_checkable
class TaskExecutionBindingPort(Protocol):
    def bind_task_execution(
        self,
        task_id: str,
        state_store: TaskStateStoreProtocol,
    ) -> AbstractContextManager[None]: ...


@runtime_checkable
class TaskStoreRunnerPort(Protocol):
    state_store: TaskStateStore


@final
class DirectTaskExecution:
    def __init__(
        self,
        orchestrator: StreamOrchestratorPort,
        task_runner: TaskStoreRunnerPort | None,
        task_outcome_recorder: TaskOutcomeRecorder | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._task_runner = task_runner
        self._task_outcome_recorder = task_outcome_recorder

    def start_stream(
        self,
        messages: Sequence[Mapping[str, str]],
        target_model: str,
        max_steps: int,
        ephemeral_message: str | None,
        execution_type: str = "interactive",
    ) -> TrackedStream:
        normalized_messages = [dict(message) for message in messages]
        execution_context = self._create_execution(
            self._latest_user_text(normalized_messages),
            execution_type,
        )
        if execution_context is None:
            return TrackedStream(
                task_id=None,
                chunks=self._orchestrator.run_stream(
                    normalized_messages,
                    target_model=target_model,
                    max_steps=max_steps,
                    ephemeral_message=ephemeral_message,
                ),
            )
        if normalized_messages:
            _ = save_task_context_snapshot(
                execution_context.state_store,
                execution_context.task_id,
                normalized_messages,
                target_model,
            )
        return TrackedStream(
            task_id=execution_context.task_id,
            chunks=self._stream_execution(
                execution_context,
                normalized_messages,
                target_model,
                max_steps,
                ephemeral_message,
                execution_type,
            ),
        )

    def run_max(self, engine: MaxEnginePort, task_spec: dict[str, object]) -> MaxRunResultPort:
        execution_context = self._create_execution(
            str(task_spec.get("prompt", "MAX execution")),
            "max_execution",
        )
        if execution_context is None:
            return engine.run(task_spec, orchestrator=self._orchestrator)

        state_store = execution_context.state_store
        _ = state_store.transition(execution_context.task_id, "running")
        _ = state_store.append_execution_event(
            execution_context.task_id,
            "max_execution_started",
            json.dumps({"mode": "max"}, sort_keys=True),
        )
        try:
            with self._execution_binding(execution_context):
                result = engine.run(task_spec, orchestrator=self._orchestrator)
        except Exception as exc:  # noqa: BLE001
            _ = state_store.transition(execution_context.task_id, "failed", error=str(exc))
            _ = state_store.append_execution_event(
                execution_context.task_id,
                "max_execution_failed",
                json.dumps({"error": str(exc)}, sort_keys=True),
            )
            raise

        output = str(getattr(result, "final_output", ""))
        error = getattr(result, "error", None)
        if output:
            _ = state_store.transition(execution_context.task_id, "done", output=output)
            _ = state_store.append_execution_event(
                execution_context.task_id,
                "max_execution_completed",
                json.dumps({"output_length": len(output)}, sort_keys=True),
            )
        else:
            message = str(error or "MAX produced no output")
            _ = state_store.transition(execution_context.task_id, "failed", error=message)
            _ = state_store.append_execution_event(
                execution_context.task_id,
                "max_execution_failed",
                json.dumps({"error": message}, sort_keys=True),
            )
        return result

    @staticmethod
    def _latest_user_text(messages: Sequence[Mapping[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "")
        return messages[-1].get("content", "") if messages else ""

    def _create_execution(self, prompt: str, mode: str) -> TaskExecutionContext | None:
        task_runner = self._task_runner
        if task_runner is None or self._is_bound():
            return None

        state_store = task_runner.state_store
        task_id = f"direct_{uuid.uuid4().hex[:12]}"
        _ = state_store.create_task(task_id, prompt, "pending", datetime.now(UTC).isoformat())
        expected_tools = self._explicit_tool_contract(prompt)
        checkpoint_context = {"expected_tools": expected_tools} if expected_tools else {}
        if mode != "max_execution":
            state_store.save_checkpoint(
                task_id,
                0,
                json.dumps(checkpoint_context),
                "",
            )
        _ = state_store.append_execution_event(
            task_id,
            f"{mode}_registered",
            json.dumps({"mode": mode}, sort_keys=True),
        )
        return TaskExecutionContext(task_id, state_store)

    def _explicit_tool_contract(self, prompt: str) -> list[str]:
        tool_registry = getattr(self._orchestrator, "tool_registry", None)
        if not isinstance(tool_registry, ToolRegistryPort):
            return []
        tool_names = tool_registry.get_names()
        lowered_prompt = prompt.casefold()
        contracted: list[str] = []
        for tool_name in tool_names:
            escaped = re.escape(tool_name.casefold())
            # "X tool" / "X 도구" form, and Korean instrumental/object particles
            # (X로/으로/을/를) that unambiguously name the tool as the means/object.
            pattern = rf"(?<!\w){escaped}(?!\w)\s*(?:tool|도구)|(?<!\w){escaped}(?:로|으로|을|를)"
            if re.search(pattern, lowered_prompt):
                contracted.append(tool_name)
        return contracted

    def _is_bound(self) -> bool:
        return current_task_execution_context() is not None or isinstance(
            getattr(self._orchestrator, "task_execution_context", None),
            TaskExecutionContext,
        )

    def _execution_binding(self, execution_context: TaskExecutionContext) -> AbstractContextManager[None]:
        if isinstance(self._orchestrator, TaskExecutionBindingPort):
            return self._orchestrator.bind_task_execution(
                execution_context.task_id,
                execution_context.state_store,
            )
        return nullcontext()

    def _stream_execution(
        self,
        execution_context: TaskExecutionContext,
        messages: list[dict[str, str]],
        target_model: str,
        max_steps: int,
        ephemeral_message: str | None,
        execution_type: str,
    ) -> Iterator[str]:
        state_store = execution_context.state_store
        started_at = time.monotonic()
        _ = state_store.transition(execution_context.task_id, "running")
        _ = state_store.append_execution_event(
            execution_context.task_id,
            f"{execution_type}_started",
            json.dumps({"model": target_model}, sort_keys=True),
        )
        output_parts: list[str] = []
        initial_agent_output = str(getattr(self._orchestrator, "_last_agent_output", "") or "")
        try:
            with self._execution_binding(execution_context):
                for chunk in normalize_streaming_chunks(
                    self._orchestrator.run_stream(
                        messages,
                        target_model=target_model,
                        max_steps=max_steps,
                        ephemeral_message=ephemeral_message,
                    )
                ):
                    output_parts.append(chunk)
                    yield chunk
        except Exception as exc:  # noqa: BLE001
            output = "".join(output_parts)
            self._save_resume_checkpoint(execution_context, output)
            _ = state_store.transition(
                execution_context.task_id,
                "failed",
                output=output,
                error=str(exc),
            )
            _ = state_store.append_execution_event(
                execution_context.task_id,
                f"{execution_type}_failed",
                json.dumps({"error": str(exc)}, sort_keys=True),
            )
            self._record_task_outcome(
                execution_context.task_id,
                target_model,
                self._latest_user_text(messages),
                output,
                started_at,
                success=False,
                completion_reason="failed",
                error=str(exc),
            )
            raise
        else:
            output = "".join(output_parts)
            record = state_store.get_task(execution_context.task_id)
            if record is not None and record["status"] != "running":
                if record["status"] in {"failed", "paused"}:
                    output = str(record["output"] or output)
                    self._save_resume_checkpoint(execution_context, output)
                _ = state_store.append_execution_event(
                    execution_context.task_id,
                    f"{execution_type}_{record['status']}",
                    json.dumps({"output_length": len(output), "error": record["error"]}, sort_keys=True),
                )
            else:
                final_agent_output = str(getattr(self._orchestrator, "_last_agent_output", "") or "")
                if final_agent_output and final_agent_output != initial_agent_output:
                    output = final_agent_output
                _ = state_store.transition(execution_context.task_id, "done", output=output)
                _ = state_store.append_execution_event(
                    execution_context.task_id,
                    f"{execution_type}_completed",
                    json.dumps({"output_length": len(output)}, sort_keys=True),
                )
                self._record_task_outcome(
                    execution_context.task_id,
                    target_model,
                    self._latest_user_text(messages),
                    output,
                    started_at,
                    success=True,
                    completion_reason="done",
                )
        finally:
            record = state_store.get_task(execution_context.task_id)
            if record is not None and record["status"] == "running":
                output = "".join(output_parts)
                _ = state_store.transition(execution_context.task_id, "cancelled", output=output)
                _ = state_store.append_execution_event(
                    execution_context.task_id,
                    f"{execution_type}_cancelled",
                    json.dumps({"output_length": len(output)}, sort_keys=True),
                )
                self._record_task_outcome(
                    execution_context.task_id,
                    target_model,
                    self._latest_user_text(messages),
                    output,
                    started_at,
                    success=False,
                    completion_reason="cancelled",
                )

    @staticmethod
    def _save_resume_checkpoint(execution_context: TaskExecutionContext, output: str) -> None:
        checkpoint = execution_context.state_store.get_last_checkpoint(execution_context.task_id)
        step = checkpoint["step"] + 1 if checkpoint is not None else 0
        context_json = checkpoint["context_json"] if checkpoint is not None else "{}"
        execution_context.state_store.save_checkpoint(
            execution_context.task_id,
            step,
            context_json,
            output,
        )

    def _record_task_outcome(
        self,
        task_id: str,
        target_model: str,
        prompt: str,
        output: str,
        started_at: float,
        *,
        success: bool,
        completion_reason: str,
        error: str = "",
    ) -> None:
        if self._task_outcome_recorder is None:
            return
        _ = self._task_outcome_recorder(
            TaskOutcome(
                case_id=task_id,
                target=target_model,
                success=success,
                completion_reason=completion_reason,
                latency_ms=(time.monotonic() - started_at) * 1000,
                tokens_in=len(prompt) // 4,
                tokens_out=len(output) // 4,
                error=error,
            ),
        )


__all__ = ["DirectTaskExecution", "TaskOutcomeRecorder", "TaskStoreRunnerPort", "TrackedStream"]
