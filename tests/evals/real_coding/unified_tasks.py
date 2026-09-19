"""Unified benchmark tasks covering explore, web, and code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnifiedTask:
    task_id: str
    task_type: str
    prompt: str
    must_contain: tuple[str, ...]
    test_code: str | None = None


TASKS: tuple[UnifiedTask, ...] = (
    UnifiedTask(
        task_id="exp_graphify_loc",
        task_type="explore",
        prompt="In this codebase, where is the embedding-based codebase retrieval function defined? Give file and function name.",
        must_contain=("graphify_builder", "hybrid_retrieve"),
    ),
    UnifiedTask(
        task_id="exp_headroom_loc",
        task_type="explore",
        prompt="Which file defines the content-aware compression layer that runs before the LLM sees tool outputs?",
        must_contain=("headroom_compressor",),
    ),
    UnifiedTask(
        task_id="web_fastapi_async",
        task_type="web",
        prompt="Does FastAPI's BackgroundTasks run after the response is sent, and is it suitable for long-running CPU work?",
        must_contain=("after", "response"),
    ),
    UnifiedTask(
        task_id="code_fix_offbyone",
        task_type="code",
        prompt="The function range_inclusive(start, end) should sum integers from start to end inclusive. It has an off-by-one bug. Fix it.",
        must_contain=("range(start, end",),
        test_code=(
            "from solution import range_inclusive\n"
            "def test_inclusive():\n"
            "    assert range_inclusive(1, 5) == 15\n"
            "    assert range_inclusive(1, 1) == 1\n"
            "    assert range_inclusive(0, 3) == 6\n"
        ),
    ),
    UnifiedTask(
        task_id="code_fix_dict_mutation",
        task_type="code",
        prompt="The function add_key(d, k, v) mutates the input dict in place AND returns it, causing surprising side effects. Make it return a new dict without mutating the input.",
        must_contain=("def add_key",),
        test_code=(
            "from solution import add_key\n"
            "def test_no_mutation():\n"
            "    original = {'a': 1}\n"
            "    result = add_key(original, 'b', 2)\n"
            "    assert original == {'a': 1}\n"
            "    assert result == {'a': 1, 'b': 2}\n"
        ),
    ),
    UnifiedTask(
        task_id="answer_python_gil",
        task_type="answer",
        prompt="In one or two sentences, what is the Python GIL and how does it affect multithreaded CPU-bound code?",
        must_contain=("gil", "thread"),
    ),
)
