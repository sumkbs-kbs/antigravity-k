from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, final

from mcp.types import CallToolResult, ListToolsResult, Tool
from pydantic import JsonValue

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
@final
class AwaitRecord:
    kwargs: dict[str, JsonValue]


@final
class AsyncCallRecorder(Generic[T]):
    def __init__(self, result: T) -> None:
        self._result: T = result
        self._await_count: int = 0
        self._await_args: AwaitRecord | None = None
        self.side_effect: BaseException | None = None

    async def __call__(self, *args: str, **kwargs: JsonValue) -> T:
        del args
        self._await_count += 1
        self._await_args = AwaitRecord(kwargs=dict(kwargs))
        if self.side_effect is not None:
            raise self.side_effect
        return self._result

    @property
    def await_args(self) -> AwaitRecord | None:
        return self._await_args

    def assert_awaited_once(self) -> None:
        assert self._await_count == 1

    def assert_not_awaited(self) -> None:
        assert self._await_count == 0

    def reset_mock(self) -> None:
        self._await_count = 0
        self._await_args = None


@dataclass(frozen=True, slots=True)
@final
class SessionDouble:
    call_tool: AsyncCallRecorder[CallToolResult]
    list_tools: AsyncCallRecorder[ListToolsResult]

    @classmethod
    def with_result(cls, call_result: CallToolResult) -> SessionDouble:
        return cls(
            call_tool=AsyncCallRecorder(call_result),
            list_tools=AsyncCallRecorder(
                ListToolsResult(
                    tools=[Tool(name="start_training", description="start", inputSchema={"type": "object"})],
                ),
            ),
        )
