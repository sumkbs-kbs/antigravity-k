from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DependencyTask:
    task_id: str
    difficulty: str
    module_code: str
    test_code: str
    scenario: str


TASKS: tuple[DependencyTask, ...] = (
    DependencyTask(
        task_id="dep_unit_conversion",
        difficulty="hard",
        scenario=(
            "The test suite tests process_orders but the bug is in a helper. "
            "Find the root cause across the module and fix it."
        ),
        module_code=(
            "def to_cents(dollars):\n"
            "    return dollars * 0.10\n"
            "\n"
            "def process_orders(orders):\n"
            "    total_cents = 0\n"
            "    for order in orders:\n"
            "        total_cents += to_cents(order['amount'])\n"
            "    return total_cents\n"
            "\n"
            "def format_total(orders):\n"
            "    cents = process_orders(orders)\n"
            "    return f'${cents / 100:.2f}'\n"
        ),
        test_code=(
            "from solution import process_orders, format_total, to_cents\n"
            "def test_to_cents():\n"
            "    assert to_cents(10) == 1000\n"
            "def test_process():\n"
            "    orders = [{'amount': 10}, {'amount': 5}]\n"
            "    assert process_orders(orders) == 1500\n"
            "def test_format():\n"
            "    assert format_total([{'amount': 10}]) == '$10.00'\n"
        ),
    ),
    DependencyTask(
        task_id="dep_off_by_helper",
        difficulty="hard",
        scenario=(
            "Reports are wrong. The bug is in a shared helper used by multiple "
            "functions. Fix the root cause, not the symptom."
        ),
        module_code=(
            "def safe_index(items, target):\n"
            "    for i in range(len(items)):\n"
            "        if items[i] == target:\n"
            "            return i + 1\n"
            "    return -1\n"
            "\n"
            "def find_positions(values, targets):\n"
            "    return {t: safe_index(values, t) for t in targets}\n"
            "\n"
            "def first_missing(values, candidates):\n"
            "    for c in candidates:\n"
            "        if safe_index(values, c) == -1:\n"
            "            return c\n"
            "    return None\n"
        ),
        test_code=(
            "from solution import safe_index, find_positions, first_missing\n"
            "def test_index():\n"
            "    assert safe_index(['a', 'b', 'c'], 'b') == 1\n"
            "    assert safe_index(['a', 'b', 'c'], 'a') == 0\n"
            "    assert safe_index(['a', 'b', 'c'], 'z') == -1\n"
            "def test_positions():\n"
            "    assert find_positions(['x', 'y', 'z'], ['y', 'z']) == {'y': 1, 'z': 2}\n"
            "def test_missing():\n"
            "    assert first_missing([1, 2, 3], [2, 4, 5]) == 4\n"
        ),
    ),
    DependencyTask(
        task_id="dep_state_leak",
        difficulty="hard",
        scenario=("A class accumulates incorrectly across instances. The bug is subtle shared state. Find and fix it."),
        module_code=(
            "_cache = []\n"
            "\n"
            "class Counter:\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n"
            "        self.count = 0\n"
            "    def increment(self):\n"
            "        self.count += 1\n"
            "        _cache.append(self.count)\n"
            "        return self.count\n"
            "    def history(self):\n"
            "        return list(_cache)\n"
        ),
        test_code=(
            "from solution import Counter\n"
            "def test_isolated():\n"
            "    a = Counter('a')\n"
            "    b = Counter('b')\n"
            "    a.increment()\n"
            "    a.increment()\n"
            "    assert a.history() == [1, 2]\n"
            "    assert b.increment() == 1\n"
            "def test_independent():\n"
            "    c = Counter('c')\n"
            "    d = Counter('d')\n"
            "    c.increment()\n"
            "    d.increment()\n"
            "    d.increment()\n"
            "    assert c.history() == [1]\n"
            "    assert d.history() == [1, 2]\n"
        ),
    ),
)
