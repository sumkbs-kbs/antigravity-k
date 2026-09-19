"""Hard composite benchmark tasks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompositeTask:
    task_id: str
    task_type: str
    prompt: str
    must_contain: tuple[str, ...]
    test_code: str | None = None


TASKS: tuple[CompositeTask, ...] = (
    CompositeTask(
        task_id="exp_capability_gate",
        task_type="explore",
        prompt="In this codebase, which module decides whether a tool action is allowed before it executes, and what is the primary class name?",
        must_contain=("permission_gate", "PermissionGate"),
    ),
    CompositeTask(
        task_id="exp_eval_runner",
        task_type="explore",
        prompt="Where is the end-to-end evaluation runner that drives the real orchestration path, and what is its main class?",
        must_contain=("end_to_end_runner", "EndToEndEvaluationRunner"),
    ),
    CompositeTask(
        task_id="exp_search_contract",
        task_type="explore",
        prompt="Which module defines the typed wire contract for the external search provider, including request and response models?",
        must_contain=("ssak_search_contract",),
    ),
    CompositeTask(
        task_id="code_impl_stack_min",
        task_type="code",
        prompt="Implement a function min_stack that supports push, pop, top, and get_min all in O(1). Use a list of (value, current_min) tuples.",
        must_contain=("def min_stack", "get_min"),
        test_code=(
            "from solution import min_stack\n"
            "def test_min_stack():\n"
            "    s = min_stack()\n"
            "    s.push(5); s.push(3); s.push(7)\n"
            "    assert s.get_min() == 3\n"
            "    assert s.top() == 7\n"
            "    s.pop()\n"
            "    assert s.get_min() == 3\n"
            "    s.pop()\n"
            "    assert s.get_min() == 5\n"
        ),
    ),
    CompositeTask(
        task_id="code_impl_decoder",
        task_type="code",
        prompt="Implement decode_string(s) that decodes patterns like '3[a2[c]]' into 'accaccacc'. Numbers mean repeat counts, brackets nest. Use a stack.",
        must_contain=("def decode_string", "stack"),
        test_code=(
            "from solution import decode_string\n"
            "def test_decode():\n"
            "    assert decode_string('3[a]') == 'aaa'\n"
            "    assert decode_string('3[a2[c]]') == 'accaccacc'\n"
            "    assert decode_string('2[abc]3[cd]ef') == 'abcabccdcdcdef'\n"
            "    assert decode_string('') == ''\n"
        ),
    ),
    CompositeTask(
        task_id="code_fix_concurrent",
        task_type="code",
        prompt="The Counter class has a thread-safety bug: increment is not atomic. Fix it using a threading.Lock so concurrent increments are safe. Keep the same API.",
        must_contain=("Lock", "with"),
        test_code=(
            "from solution import Counter\n"
            "import threading\n"
            "def test_concurrent():\n"
            "    c = Counter()\n"
            "    def worker():\n"
            "        for _ in range(1000):\n"
            "            c.increment()\n"
            "    threads = [threading.Thread(target=worker) for _ in range(10)]\n"
            "    for t in threads: t.start()\n"
            "    for t in threads: t.join()\n"
            "    assert c.value == 10000\n"
        ),
    ),
    CompositeTask(
        task_id="web_langchain_version",
        task_type="web",
        prompt="What is the current latest version of the LangChain Python package, and what is its import style?",
        must_contain=("langchain",),
    ),
    CompositeTask(
        task_id="answer_recursion_depth",
        task_type="answer",
        prompt="What is Python's default recursion limit, and how do you change it?",
        must_contain=("1000", "sys.setrecursionlimit"),
    ),
)
