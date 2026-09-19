from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GroundedQATask:
    task_id: str
    question: str
    must_contain: tuple[str, ...]
    needs_web: bool


TASKS: tuple[GroundedQATask, ...] = (
    GroundedQATask(
        task_id="py_asyncio_gather",
        question="What does Python's asyncio.gather do, and what keyword argument controls error propagation?",
        must_contain=("return_exceptions",),
        needs_web=False,
    ),
    GroundedQATask(
        task_id="py_dataclass_slots",
        question="How do you enable __slots__ on a Python @dataclass, and what is the memory benefit?",
        must_contain=("slots=True",),
        needs_web=False,
    ),
    GroundedQATask(
        task_id="py_walrus_operator",
        question="What is the walrus operator in Python, its syntax, and which version introduced it?",
        must_contain=("3.8", ":="),
        needs_web=False,
    ),
    GroundedQATask(
        task_id="ssak_search_tavily",
        question="The ssak-search project on GitHub is described as what kind of search engine API, and what is its key selling point about API keys?",
        must_contain=("tavily", "no api key"),
        needs_web=True,
    ),
    GroundedQATask(
        task_id="current_fastapi_version",
        question="What is the current latest version of FastAPI, and what Python versions does it support?",
        must_contain=("0.1",),
        needs_web=True,
    ),
    GroundedQATask(
        task_id="py_pattern_matching",
        question="When was structural pattern matching (match/case) added to Python, and what is its basic syntax?",
        must_contain=("3.10", "match", "case"),
        needs_web=False,
    ),
)
