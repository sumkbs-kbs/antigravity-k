from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import ClassVar, Final

import anyio
from anyio.to_thread import run_sync
from fastapi import APIRouter, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from antigravity_k.api.dependencies import get_agent_runtime
from antigravity_k.api.routes.session_state import close_unauthorized_ws
from antigravity_k.api.task_models import (
    TaskActionResponse,
    TaskBenchmarkRequest,
    TaskEvent,
    TaskEventsResponse,
    TaskForkRequest,
    TaskForkResponse,
    TaskListResponse,
    TaskOutputResponse,
    TaskStatusResponse,
    TaskStreamEnd,
    TaskSubmitRequest,
    TaskSubmitResponse,
)
from antigravity_k.engine.agent_runtime import AgentRuntime
from antigravity_k.engine.benchmark_cases import get_suite
from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.task_events import ExecutionEventRecord

router = APIRouter()

_TERMINAL_TASK_STATUSES = frozenset({"done", "failed", "cancelled"})
_SSE_EVENT_NAME = re.compile(r"[A-Za-z0-9_.:-]+")
_FORK_OUTPUT_CONTEXT_LIMIT: Final = 12_000


class _TaskForkSource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    task_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    status: str = Field(min_length=1)
    output: str = ""


class _TaskForkMetadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    source_task_id: str
    source_status: str
    source_output: str
    source_last_sequence: int


class _TaskForkContext(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    fork: _TaskForkMetadata


def _runtime() -> AgentRuntime:
    return get_agent_runtime()


def _require_task(runtime: AgentRuntime, task_id: str) -> dict[str, object]:
    task = runtime.get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post(
    "/api/tasks/submit",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_background_task(request: TaskSubmitRequest) -> TaskSubmitResponse:
    context: dict[str, object] = dict(request.context)
    task_id = _runtime().submit_task(
        prompt=request.prompt,
        context=context,
        target_model=request.model,
        use_worktree=request.use_worktree,
        idempotency_key=request.idempotency_key,
    )
    return TaskSubmitResponse(task_id=task_id)


@router.post(
    "/api/tasks/{task_id}/fork",
    response_model=TaskForkResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def fork_task(task_id: str, request: TaskForkRequest) -> TaskForkResponse:
    runtime = _runtime()
    try:
        source = _TaskForkSource.model_validate(_require_task(runtime, task_id))
    except ValidationError as error:
        raise HTTPException(status_code=409, detail="Task history is not forkable") from error

    events = runtime.list_task_events(task_id, after_sequence=0, limit=1_000)
    last_sequence = events[-1]["sequence"] if events else 0
    fork_context = _TaskForkContext(
        fork=_TaskForkMetadata(
            source_task_id=source.task_id,
            source_status=source.status,
            source_output=source.output[-_FORK_OUTPUT_CONTEXT_LIMIT:],
            source_last_sequence=last_sequence,
        ),
    ).model_dump()
    forked_task_id = runtime.submit_task(
        prompt=request.prompt or source.prompt,
        context=fork_context,
        target_model=request.model,
        use_worktree=request.use_worktree,
        idempotency_key=request.idempotency_key,
    )
    return TaskForkResponse(task_id=forked_task_id, source_task_id=source.task_id)


@router.get("/api/tasks/{task_id}/status", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    return TaskStatusResponse.from_runtime(_require_task(_runtime(), task_id))


@router.get("/api/tasks", response_model=TaskListResponse)
def list_tasks(limit: int = Query(default=20, ge=1, le=200)) -> TaskListResponse:
    return TaskListResponse.from_runtime(_runtime().list_tasks(limit=limit))


@router.get("/api/tasks/{task_id}/output", response_model=TaskOutputResponse)
def get_task_output(task_id: str) -> TaskOutputResponse:
    output = _runtime().get_task_output(task_id)
    if output is None:
        raise HTTPException(status_code=404, detail="Task output not found")
    return TaskOutputResponse(task_id=task_id, output=output)


@router.post("/api/tasks/{task_id}/cancel", response_model=TaskActionResponse)
def cancel_background_task(task_id: str) -> TaskActionResponse:
    if not _runtime().cancel_task(task_id):
        raise HTTPException(status_code=404, detail="Task is not active")
    return TaskActionResponse(status="cancelled", task_id=task_id)


@router.post("/api/tasks/{task_id}/resume", response_model=TaskActionResponse)
def resume_task(task_id: str) -> TaskActionResponse:
    if not _runtime().resume_task(task_id=task_id):
        raise HTTPException(status_code=404, detail="Task is not resumable or has no checkpoint")
    return TaskActionResponse(status="resumed", task_id=task_id)


@router.post("/api/tasks/benchmark/{case_id}", response_model=None)
def submit_task_benchmark(case_id: str, request: TaskBenchmarkRequest) -> dict[str, object]:
    cases = get_suite(case_id)
    if len(cases) != 1 or cases[0].id != case_id:
        raise HTTPException(status_code=404, detail="Benchmark case not found")
    case = cases[0]
    task_id = _runtime().submit_task(
        prompt=case.prompt,
        context=BenchmarkHarness.task_context_for_case(case),
        target_model=request.model,
        idempotency_key=request.idempotency_key,
    )
    return {
        "status": "submitted",
        "task_id": task_id,
        "benchmark_case": {
            "id": case.id,
            "category": case.category,
            "difficulty": case.difficulty,
            "expected_tools": list(case.expected_tools),
        },
    }


@router.get("/api/tasks/{task_id}/events", response_model=TaskEventsResponse)
def list_task_events(
    task_id: str,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> TaskEventsResponse:
    runtime = _runtime()
    _require_task(runtime, task_id)
    events = [
        TaskEvent.from_record(record)
        for record in runtime.list_task_events(task_id, after_sequence=after_sequence, limit=limit)
    ]
    last_sequence = events[-1].sequence if events else after_sequence
    return TaskEventsResponse(task_id=task_id, events=events, last_sequence=last_sequence)


@router.get("/api/tasks/{task_id}/events/stream")
async def stream_task_events(
    task_id: str,
    request: Request,
    after_sequence: int = Query(default=0, ge=0),
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID", ge=0),
) -> StreamingResponse:
    runtime = _runtime()
    _require_task(runtime, task_id)
    resume_sequence = max(after_sequence, last_event_id or 0)
    return StreamingResponse(
        _event_stream(runtime, task_id, request, resume_sequence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.websocket("/api/tasks/{task_id}/events/ws")
async def stream_task_events_websocket(
    websocket: WebSocket,
    task_id: str,
    after_sequence: int = Query(default=0, ge=0),
) -> None:
    runtime = _runtime()
    if runtime.get_task_status(task_id) is None:
        await websocket.close(code=1008, reason="Task not found")
        return
    if await close_unauthorized_ws(websocket):
        return
    sequence = after_sequence
    try:
        while True:
            records = await _next_task_events(runtime, task_id, sequence)
            for record in records:
                event = TaskEvent.from_record(record)
                sequence = event.sequence
                await websocket.send_json(event.model_dump(mode="json"))
            task_status = await _task_status(runtime, task_id)
            if task_status in _TERMINAL_TASK_STATUSES:
                end = TaskStreamEnd(task_id=task_id, last_sequence=sequence, status=task_status)
                await websocket.send_json(
                    {
                        "type": "stream.end",
                        "task_id": end.task_id,
                        "last_sequence": end.last_sequence,
                        "status": end.status,
                    },
                )
                await websocket.close()
                return
            await anyio.sleep(0.5)
    except WebSocketDisconnect:
        return


async def _event_stream(
    runtime: AgentRuntime,
    task_id: str,
    request: Request,
    after_sequence: int,
) -> AsyncIterator[str]:
    sequence = after_sequence
    idle_cycles = 0
    while True:
        records = await _next_task_events(runtime, task_id, sequence)
        for record in records:
            event = TaskEvent.from_record(record)
            sequence = event.sequence
            yield _event_frame(event)
        task_status = await _task_status(runtime, task_id)
        if task_status in _TERMINAL_TASK_STATUSES:
            end = TaskStreamEnd(task_id=task_id, last_sequence=sequence, status=task_status)
            yield f"event: stream.end\ndata: {end.model_dump_json()}\n\n"
            return
        if await request.is_disconnected():
            return
        idle_cycles += 1
        if idle_cycles % 30 == 0:
            yield ": keep-alive\n\n"
        await anyio.sleep(0.5)


async def _next_task_events(
    runtime: AgentRuntime,
    task_id: str,
    after_sequence: int,
) -> list[ExecutionEventRecord]:
    def load() -> list[ExecutionEventRecord]:
        return runtime.list_task_events(task_id, after_sequence=after_sequence, limit=200)

    return await run_sync(load)


async def _task_status(runtime: AgentRuntime, task_id: str) -> str:
    def load() -> dict[str, object] | None:
        return runtime.get_task_status(task_id)

    task = await run_sync(load)
    return str(task.get("status", "unknown")) if task is not None else "unknown"


def _event_frame(event: TaskEvent) -> str:
    event_name = event.event_type if _SSE_EVENT_NAME.fullmatch(event.event_type) else "task.event"
    return f"id: {event.sequence}\nevent: {event_name}\ndata: {event.model_dump_json()}\n\n"


__all__ = ["router"]
