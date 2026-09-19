from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SWETask:
    task_id: str
    difficulty: str
    scenario: str
    buggy_code: str
    test_code: str


TASKS: tuple[SWETask, ...] = (
    SWETask(
        task_id="off_by_one",
        difficulty="medium",
        scenario=(
            "The function range_sum should return the sum of integers from start "
            "to end inclusive. It has an off-by-one bug. Fix it so all tests pass."
        ),
        buggy_code=(
            "def range_sum(start, end):\n"
            "    total = 0\n"
            "    for i in range(start, end):\n"
            "        total += i\n"
            "    return total\n"
        ),
        test_code=(
            "from solution import range_sum\n"
            "def test_inclusive():\n"
            "    assert range_sum(1, 5) == 15\n"
            "    assert range_sum(1, 1) == 1\n"
            "    assert range_sum(5, 5) == 5\n"
            "    assert range_sum(0, 3) == 6\n"
        ),
    ),
    SWETask(
        task_id="mutable_default",
        difficulty="medium",
        scenario=(
            "The append_to_list function has a classic Python mutable-default-argument "
            "bug: repeated calls share state. Fix it without changing the API."
        ),
        buggy_code=("def append_to_list(value, target=[]):\n    target.append(value)\n    return target\n"),
        test_code=(
            "from solution import append_to_list\n"
            "def test_isolated():\n"
            "    assert append_to_list(1) == [1]\n"
            "    assert append_to_list(2) == [2]\n"
            "    assert append_to_list(3) == [3]\n"
            "    assert append_to_list('x', ['a']) == ['a', 'x']\n"
        ),
    ),
    SWETask(
        task_id="race_in_logic",
        difficulty="hard",
        scenario=(
            "The dedupe_keep_order function should remove duplicate values while "
            "preserving first-occurrence order. It incorrectly uses a list "
            "membership check that mutates during iteration. Fix the logic so it "
            "keeps order and removes all duplicates."
        ),
        buggy_code=(
            "def dedupe_keep_order(items):\n"
            "    seen = []\n"
            "    result = []\n"
            "    for item in items:\n"
            "        result.append(item)\n"
            "        if item in seen:\n"
            "            seen.append(item)\n"
            "        else:\n"
            "            seen.append(item)\n"
            "    return result\n"
        ),
        test_code=(
            "from solution import dedupe_keep_order\n"
            "def test_dedupe():\n"
            "    assert dedupe_keep_order([1, 2, 1, 3, 2, 4]) == [1, 2, 3, 4]\n"
            "    assert dedupe_keep_order(['a', 'b', 'a', 'c']) == ['a', 'b', 'c']\n"
            "    assert dedupe_keep_order([]) == []\n"
            "    assert dedupe_keep_order([1, 1, 1]) == [1]\n"
        ),
    ),
    SWETask(
        task_id="wrong_data_structure",
        difficulty="hard",
        scenario=(
            "The group_by_parity function should return a dict mapping True->evens "
            "and False->odds. It has a bug: it uses is_even = (n % 2 == 1) which "
            "inverts the condition. Fix it so even numbers group under True."
        ),
        buggy_code=(
            "def group_by_parity(numbers):\n"
            "    groups = {True: [], False: []}\n"
            "    for n in numbers:\n"
            "        is_even = (n % 2 == 1)\n"
            "        groups[is_even].append(n)\n"
            "    return groups\n"
        ),
        test_code=(
            "from solution import group_by_parity\n"
            "def test_parity():\n"
            "    r = group_by_parity([1, 2, 3, 4, 5, 6])\n"
            "    assert r[True] == [2, 4, 6]\n"
            "    assert r[False] == [1, 3, 5]\n"
            "    r2 = group_by_parity([0, 2, 4])\n"
            "    assert r2[True] == [0, 2, 4]\n"
            "    assert r2[False] == []\n"
        ),
    ),
    SWETask(
        task_id="missing_base_case",
        difficulty="hard",
        scenario=(
            "The flatten_nested function recursively flattens arbitrarily nested "
            "lists. It crashes on empty nested lists and non-list leaves. Fix it "
            "so it handles [], nested [], and integer leaves correctly."
        ),
        buggy_code=(
            "def flatten_nested(items):\n"
            "    result = []\n"
            "    for item in items:\n"
            "        result.append(item[0])\n"
            "        result.extend(flatten_nested(item[1:]))\n"
            "    return result\n"
        ),
        test_code=(
            "from solution import flatten_nested\n"
            "def test_flatten():\n"
            "    assert flatten_nested([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]\n"
            "    assert flatten_nested([]) == []\n"
            "    assert flatten_nested([[], [[]], [1]]) == [1]\n"
            "    assert flatten_nested([1, 2, 3]) == [1, 2, 3]\n"
        ),
    ),
    SWETask(
        task_id="wrong_algorithm",
        difficulty="hard",
        scenario=(
            "The binary_search function should return the index of target in a "
            "sorted list, or -1. It has two bugs: the mid calculation can overflow "
            "(not in Python but logically wrong range) and the loop never "
            "terminates when target is absent. Fix it to return correct index or -1."
        ),
        buggy_code=(
            "def binary_search(arr, target):\n"
            "    lo = 0\n"
            "    hi = len(arr)\n"
            "    while lo != hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            lo = mid\n"
            "        else:\n"
            "            hi = mid\n"
            "    return -1\n"
        ),
        test_code=(
            "from solution import binary_search\n"
            "def test_search():\n"
            "    assert binary_search([1, 3, 5, 7, 9], 5) == 2\n"
            "    assert binary_search([1, 3, 5, 7, 9], 1) == 0\n"
            "    assert binary_search([1, 3, 5, 7, 9], 9) == 4\n"
            "    assert binary_search([1, 3, 5, 7, 9], 4) == -1\n"
            "    assert binary_search([], 1) == -1\n"
            "    assert binary_search([2], 2) == 0\n"
        ),
    ),
)
