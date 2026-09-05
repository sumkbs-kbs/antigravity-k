from __future__ import annotations

from typing import ClassVar, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from antigravity_k.engine.task_events import ExecutionEventRecord

_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_TASK_DATA_ADAPTER: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
_TASK_LIST_ADAPTER: TypeAdapter[list[dict[str, JsonValue]]] = TypeAdapter(list[dict[str, JsonValue]])
_MAX_TASK_CONTEXT_BYTES: Final[int] = 64 * 1024


class BlankTaskPromptError(ValueError):
    pass


class TaskContextTooLargeError(ValueError):
    pass


class TaskSubmitRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    prompt: str = Field(max_length=32_000)
    context: dict[str, JsonValue] = Field(default_factory=dict)
    model: str = Field(default="", max_length=128)
    use_worktree: bool = False
    idempotency_key: str | None = Field(default=None, max_length=256)

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        prompt = value.strip()
        if not prompt:
            raise BlankTaskPromptError("prompt must not be blank")
        return prompt

    @field_validator("context")
    @classmethod
    def limit_context_size(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if len(_TASK_DATA_ADAPTER.dump_json(value)) > _MAX_TASK_CONTEXT_BYTES:
            raise TaskContextTooLargeError("context exceeds the maximum size")
        return value


class TaskSubmitResponse(BaseModel):
    status: Literal["submitted"] = "submitted"
    task_id: str


class BlankTaskForkPromptError(ValueError):
    pass


class TaskForkRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    prompt: str | None = Field(default=None, max_length=32_000)
    model: str = Field(default="", max_length=128)
    use_worktree: bool = False
    idempotency_key: str | None = Field(default=None, max_length=256)

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        prompt = value.strip()
        if not prompt:
            raise BlankTaskForkPromptError("prompt must not be blank")
        return prompt


class TaskForkResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["forked"] = "forked"
    task_id: str
    source_task_id: str


class TaskBenchmarkRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    model: str = Field(default="qwen3.6:latest", min_length=1, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=256)


class TaskEvent(BaseModel):
    sequence: int
    schema_version: int
    task_id: str
    step_id: str | None
    agent_id: str | None
    parent_id: str | None
    tool_call_id: str | None
    approval_id: str | None
    resource_job_id: str | None
    correlation_id: str | None
    event_type: str
    payload: JsonValue
    created_at: str

    @classmethod
    def from_record(cls, record: ExecutionEventRecord) -> Self:
        return cls(
            sequence=record["sequence"],
            schema_version=record["schema_version"],
            task_id=record["task_id"],
            step_id=record["step_id"],
            agent_id=record["agent_id"],
            parent_id=record["parent_id"],
            tool_call_id=record["tool_call_id"],
            approval_id=record["approval_id"],
            resource_job_id=record["resource_job_id"],
            correlation_id=record["correlation_id"],
            event_type=record["event_type"],
            payload=_JSON_VALUE_ADAPTER.validate_json(record["payload_json"]),
            created_at=record["created_at"],
        )


class TaskEventsResponse(BaseModel):
    task_id: str
    events: list[TaskEvent]
    last_sequence: int
    has_more: bool


class TaskStreamEnd(BaseModel):
    task_id: str
    last_sequence: int
    status: str


class TaskStatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: dict[str, JsonValue]

    @classmethod
    def from_runtime(cls, data: object) -> Self:
        return cls(data=_TASK_DATA_ADAPTER.validate_python(data))


class TaskListResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data: list[dict[str, JsonValue]]

    @classmethod
    def from_runtime(cls, data: object) -> Self:
        return cls(data=_TASK_LIST_ADAPTER.validate_python(data))


class TaskOutputResponse(BaseModel):
    status: Literal["ok"] = "ok"
    task_id: str
    output: str


class TaskActionResponse(BaseModel):
    status: Literal["cancelled", "resumed"]
    task_id: str


class BlankTaskSteeringInstructionError(ValueError):
    pass


class TaskSteeringInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    instruction: str = Field(min_length=1, max_length=8_000)

    @field_validator("instruction")
    @classmethod
    def normalize_instruction(cls, value: str) -> str:
        instruction = value.strip()
        if not instruction:
            raise BlankTaskSteeringInstructionError("instruction must not be blank")
        return instruction


class TaskSteeringResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["accepted"] = "accepted"
    task_id: str
    steering_id: str
    mode: Literal["queued_replay"] = "queued_replay"


__all__ = [
    "TaskActionResponse",
    "TaskBenchmarkRequest",
    "TaskEvent",
    "TaskEventsResponse",
    "TaskForkRequest",
    "TaskForkResponse",
    "TaskListResponse",
    "TaskOutputResponse",
    "TaskStatusResponse",
    "TaskStreamEnd",
    "TaskSubmitRequest",
    "TaskSubmitResponse",
    "BlankTaskSteeringInstructionError",
    "TaskSteeringInput",
    "TaskSteeringResponse",
]
