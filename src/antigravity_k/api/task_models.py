from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from antigravity_k.engine.task_state_store import ExecutionEventRecord

_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_TASK_DATA_ADAPTER: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
_TASK_LIST_ADAPTER: TypeAdapter[list[dict[str, JsonValue]]] = TypeAdapter(list[dict[str, JsonValue]])


class TaskSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    context: dict[str, JsonValue] = Field(default_factory=dict)
    model: str = ""
    use_worktree: bool = False
    idempotency_key: str | None = None

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        prompt = value.strip()
        if not prompt:
            raise ValueError("prompt must not be blank")
        return prompt


class TaskSubmitResponse(BaseModel):
    status: Literal["submitted"] = "submitted"
    task_id: str


class BlankTaskForkPromptError(ValueError):
    pass


class TaskForkRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    prompt: str | None = None
    model: str = ""
    use_worktree: bool = False
    idempotency_key: str | None = None

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
    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="qwen3.6:latest", min_length=1)
    idempotency_key: str | None = None


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
]
