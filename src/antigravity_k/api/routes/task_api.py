from __future__ import annotations

import re
from collections.abc import AsyncIterator

import anyio
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from antigravity_k.api.dependencies import get_agent_runtime
from antigravity_k.api.task_models import (
    TaskActionResponse,
    TaskBenchmarkRequest,
    TaskEvent,
    TaskEventsResponse,
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

router = APIRouter()

_TERMINAL_TASK_STATUSES = frozenset({"done", "failed", "cancelled"})
_SSE_EVENT_NAME = re.compile(r"[A-Za-z0-9_.:-]+")


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


async def _event_stream(
    runtime: AgentRuntime,
    task_id: str,
    request: Request,
    after_sequence: int,
) -> AsyncIterator[str]:
    sequence = after_sequence
    idle_cycles = 0
    while True:
        records = await anyio.to_thread.run_sync(runtime.list_task_events, task_id, sequence, 200)
        for record in records:
            event = TaskEvent.from_record(record)
            sequence = event.sequence
            yield _event_frame(event)
        task = await anyio.to_thread.run_sync(runtime.get_task_status, task_id)
        task_status = str(task.get("status", "unknown")) if task is not None else "unknown"
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


def _event_frame(event: TaskEvent) -> str:
    event_name = event.event_type if _SSE_EVENT_NAME.fullmatch(event.event_type) else "task.event"
    return f"id: {event.sequence}\nevent: {event_name}\ndata: {event.model_dump_json()}\n\n"


__all__ = ["router"]
