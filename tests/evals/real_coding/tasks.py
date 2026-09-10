from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CodingTask:
    task_id: str
    difficulty: str
    problem: str
    test_code: str
    expected_solution: str


TASKS: tuple[CodingTask, ...] = (
    CodingTask(
        task_id="fizzbuzz",
        difficulty="easy",
        problem=(
            "Write a function `fizzbuzz(n)` that returns a list of strings for "
            "numbers 1 through n (inclusive). For multiples of 3 use 'Fizz', for "
            "multiples of 5 use 'Buzz', for multiples of both use 'FizzBuzz', "
            "otherwise the number as a string."
        ),
        test_code=(
            "from solution import fizzbuzz\n"
            "def test_fizzbuzz_basic():\n"
            "    assert fizzbuzz(1) == ['1']\n"
            "    assert fizzbuzz(3) == ['1', '2', 'Fizz']\n"
            "    assert fizzbuzz(5) == ['1', '2', 'Fizz', '4', 'Buzz']\n"
            "    assert fizzbuzz(15)[-1] == 'FizzBuzz'\n"
            "def test_fizzbuzz_single():\n"
            "    assert fizzbuzz(3)[2] == 'Fizz'\n"
        ),
        expected_solution=(
            "def fizzbuzz(n):\n"
            "    result = []\n"
            "    for i in range(1, n + 1):\n"
            "        if i % 15 == 0:\n"
            "            result.append('FizzBuzz')\n"
            "        elif i % 3 == 0:\n"
            "            result.append('Fizz')\n"
            "        elif i % 5 == 0:\n"
            "            result.append('Buzz')\n"
            "        else:\n"
            "            result.append(str(i))\n"
            "    return result\n"
        ),
    ),
    CodingTask(
        task_id="two_sum",
        difficulty="easy",
        problem=(
            "Write a function `two_sum(nums, target)` that returns the indices of "
            "the two numbers in `nums` that add up to `target`. You may assume "
            "exactly one solution exists. Return the indices as a tuple (i, j) "
            "with i < j."
        ),
        test_code=(
            "from solution import two_sum\n"
            "def test_two_sum_basic():\n"
            "    assert two_sum([2, 7, 11, 15], 9) == (0, 1)\n"
            "    assert two_sum([3, 2, 4], 6) == (1, 2)\n"
            "    assert two_sum([3, 3], 6) == (0, 1)\n"
            "def test_two_sum_order():\n"
            "    assert two_sum([1, 5, 3, 7], 10) == (2, 3)\n"
        ),
        expected_solution=(
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        complement = target - num\n"
            "        if complement in seen:\n"
            "            return (seen[complement], i)\n"
            "        seen[num] = i\n"
            "    return ()\n"
        ),
    ),
    CodingTask(
        task_id="balanced_parens",
        difficulty="medium",
        problem=(
            "Write a function `is_balanced(s)` that returns True if the string `s` "
            "contains correctly matched and nested parentheses (), brackets [], "
            "and braces {}. Non-bracket characters should be ignored. Return "
            "False if any bracket is unmatched or mis-nested."
        ),
        test_code=(
            "from solution import is_balanced\n"
            "def test_balanced_valid():\n"
            "    assert is_balanced('()') is True\n"
            "    assert is_balanced('([])') is True\n"
            "    assert is_balanced('{[()]}') is True\n"
            "    assert is_balanced('a(b)c') is True\n"
            "def test_balanced_invalid():\n"
            "    assert is_balanced('(') is False\n"
            "    assert is_balanced('([)]') is False\n"
            "    assert is_balanced(')') is False\n"
            "    assert is_balanced('((') is False\n"
        ),
        expected_solution=(
            "def is_balanced(s):\n"
            "    pairs = {')': '(', ']': '[', '}': '{'}\n"
            "    stack = []\n"
            "    for ch in s:\n"
            "        if ch in '([{':\n"
            "            stack.append(ch)\n"
            "        elif ch in pairs:\n"
            "            if not stack or stack.pop() != pairs[ch]:\n"
            "                return False\n"
            "    return len(stack) == 0\n"
        ),
    ),
    CodingTask(
        task_id="merge_sorted",
        difficulty="medium",
        problem=(
            "Write a function `merge_sorted(a, b)` that merges two already-sorted "
            "lists of integers into a single sorted list and returns it. Do not "
            "use the built-in sort or sorted; merge them in linear time."
        ),
        test_code=(
            "from solution import merge_sorted\n"
            "def test_merge_basic():\n"
            "    assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]\n"
            "    assert merge_sorted([], [1, 2]) == [1, 2]\n"
            "    assert merge_sorted([1, 2], []) == [1, 2]\n"
            "    assert merge_sorted([], []) == []\n"
            "def test_merge_duplicates():\n"
            "    assert merge_sorted([1, 1, 3], [1, 2]) == [1, 1, 1, 2, 3]\n"
        ),
        expected_solution=(
            "def merge_sorted(a, b):\n"
            "    result = []\n"
            "    i = j = 0\n"
            "    while i < len(a) and j < len(b):\n"
            "        if a[i] <= b[j]:\n"
            "            result.append(a[i]); i += 1\n"
            "        else:\n"
            "            result.append(b[j]); j += 1\n"
            "    result.extend(a[i:])\n"
            "    result.extend(b[j:])\n"
            "    return result\n"
        ),
    ),
    CodingTask(
        task_id="word_frequency",
        difficulty="medium",
        problem=(
            "Write a function `top_n_words(text, n)` that takes a string of "
            "lowercase words separated by spaces, counts word frequencies, and "
            "returns the `n` most frequent words as a list of (word, count) "
            "tuples. Ties are broken alphabetically (ascending). If n exceeds "
            "the number of unique words, return all of them."
        ),
        test_code=(
            "from solution import top_n_words\n"
            "def test_top_n_basic():\n"
            "    assert top_n_words('a b a c a b', 2) == [('a', 3), ('b', 2)]\n"
            "    assert top_n_words('x y z', 5) == [('x', 1), ('y', 1), ('z', 1)]\n"
            "def test_top_n_tie():\n"
            "    result = top_n_words('banana apple cherry', 2)\n"
            "    assert result == [('apple', 1), ('banana', 1)]\n"
        ),
        expected_solution=(
            "def top_n_words(text, n):\n"
            "    from collections import Counter\n"
            "    counts = Counter(text.split())\n"
            "    items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))\n"
            "    return items[:n]\n"
        ),
    ),
    CodingTask(
        task_id="lru_cache",
        difficulty="hard",
        problem=(
            "Implement a class `LRUCache(capacity)` that stores integer "
            "key-value pairs with a fixed capacity. The `get(key)` method "
            "returns the value or -1 if the key is absent, and marks the key "
            "as most recently used. The `put(key, value)` method inserts or "
            "updates a key-value pair; if the cache is at capacity it evicts "
            "the least recently used key first. Both methods must run in "
            "amortized O(1) time."
        ),
        test_code=(
            "from solution import LRUCache\n"
            "def test_basic():\n"
            "    c = LRUCache(2)\n"
            "    c.put(1, 1); c.put(2, 2)\n"
            "    assert c.get(1) == 1\n"
            "    c.put(3, 3)\n"
            "    assert c.get(2) == -1\n"
            "    c.put(4, 4)\n"
            "    assert c.get(1) == -1\n"
            "    assert c.get(3) == 3\n"
            "    assert c.get(4) == 4\n"
            "def test_update():\n"
            "    c = LRUCache(2)\n"
            "    c.put(1, 1); c.put(2, 2)\n"
            "    c.put(1, 10)\n"
            "    c.put(3, 3)\n"
            "    assert c.get(2) == -1\n"
            "    assert c.get(1) == 10\n"
        ),
        expected_solution=(
            "from collections import OrderedDict\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity):\n"
            "        self.capacity = capacity\n"
            "        self.cache = OrderedDict()\n"
            "    def get(self, key):\n"
            "        if key not in self.cache:\n"
            "            return -1\n"
            "        self.cache.move_to_end(key)\n"
            "        return self.cache[key]\n"
            "    def put(self, key, value):\n"
            "        if key in self.cache:\n"
            "            self.cache.move_to_end(key)\n"
            "        self.cache[key] = value\n"
            "        if len(self.cache) > self.capacity:\n"
            "            self.cache.popitem(last=False)\n"
        ),
    ),
    CodingTask(
        task_id="binary_tree_inorder",
        difficulty="hard",
        problem=(
            "Write a function `inorder_traversal(root)` that returns a list of "
            "values from an iterative (non-recursive) in-order traversal of a "
            "binary tree. A tree node is an object with attributes `val`, "
            "`left`, and `right` (either child may be None). Do not use "
            "recursion; use an explicit stack."
        ),
        test_code=(
            "from solution import inorder_traversal, TreeNode\n"
            "def make(vals):\n"
            "    if not vals:\n"
            "        return None\n"
            "    nodes = [TreeNode(v) for v in vals]\n"
            "    for i in range(len(nodes)):\n"
            "        li, ri = 2*i+1, 2*i+2\n"
            "        if li < len(nodes) and vals[li] is not None: nodes[i].left = nodes[li]\n"
            "        if ri < len(nodes) and vals[ri] is not None: nodes[i].right = nodes[ri]\n"
            "    return nodes[0]\n"
            "def test_inorder():\n"
            "    assert inorder_traversal(make([1, None, 2, None, None, 3])) == [1, 3, 2]\n"
            "    assert inorder_traversal(make([2, 3, 4, 5])) == [5, 3, 2, 4]\n"
            "    assert inorder_traversal(None) == []\n"
            "    assert inorder_traversal(make([1])) == [1]\n"
        ),
        expected_solution=(
            "class TreeNode:\n"
            "    def __init__(self, val=0, left=None, right=None):\n"
            "        self.val = val; self.left = left; self.right = right\n"
            "def inorder_traversal(root):\n"
            "    result, stack, current = [], [], root\n"
            "    while current is not None or stack:\n"
            "        while current is not None:\n"
            "            stack.append(current)\n"
            "            current = current.left\n"
            "        current = stack.pop()\n"
            "        result.append(current.val)\n"
            "        current = current.right\n"
            "    return result\n"
        ),
    ),
    CodingTask(
        task_id="regex_validate_ipv4",
        difficulty="hard",
        problem=(
            "Write a function `is_valid_ipv4(s)` that returns True if and only "
            "if `s` is a valid IPv4 address in dotted-decimal notation: exactly "
            "four decimal octets (0-255) separated by single dots, with no "
            "leading zeros (except the octet '0' itself) and no extra "
            "characters. Do not use the ipaddress module."
        ),
        test_code=(
            "from solution import is_valid_ipv4\n"
            "def test_valid():\n"
            "    assert is_valid_ipv4('192.168.1.1') is True\n"
            "    assert is_valid_ipv4('0.0.0.0') is True\n"
            "    assert is_valid_ipv4('255.255.255.255') is True\n"
            "    assert is_valid_ipv4('10.0.0.1') is True\n"
            "def test_invalid():\n"
            "    assert is_valid_ipv4('256.1.1.1') is False\n"
            "    assert is_valid_ipv4('01.1.1.1') is False\n"
            "    assert is_valid_ipv4('1.2.3') is False\n"
            "    assert is_valid_ipv4('1.2.3.4.5') is False\n"
            "    assert is_valid_ipv4('') is False\n"
            "    assert is_valid_ipv4('a.b.c.d') is False\n"
            "    assert is_valid_ipv4('1.2.3.4 ') is False\n"
        ),
        expected_solution=(
            "def is_valid_ipv4(s):\n"
            "    parts = s.split('.')\n"
            "    if len(parts) != 4:\n"
            "        return False\n"
            "    for p in parts:\n"
            "        if not p.isdigit():\n"
            "            return False\n"
            "        if len(p) > 1 and p[0] == '0':\n"
            "            return False\n"
            "        if int(p) > 255:\n"
            "            return False\n"
            "    return True\n"
        ),
    ),
    CodingTask(
        task_id="longest_common_subsequence",
        difficulty="hard",
        problem=(
            "Write a function `lcs(s1, s2)` that returns the length of the "
            "longest common subsequence of two strings (not necessarily "
            "contiguous). Use dynamic programming. An empty string paired "
            "with anything has LCS length 0."
        ),
        test_code=(
            "from solution import lcs\n"
            "def test_lcs_basic():\n"
            "    assert lcs('abcde', 'ace') == 3\n"
            "    assert lcs('abc', 'abc') == 3\n"
            "    assert lcs('abc', 'def') == 0\n"
            "    assert lcs('', 'abc') == 0\n"
            "def test_lcs_edge():\n"
            "    assert lcs('bsbininm', 'jmjkbkjkv') == 1\n"
            "    assert lcs('abcdef', 'acf') == 3\n"
        ),
        expected_solution=(
            "def lcs(s1, s2):\n"
            "    m, n = len(s1), len(s2)\n"
            "    dp = [[0]*(n+1) for _ in range(m+1)]\n"
            "    for i in range(1, m+1):\n"
            "        for j in range(1, n+1):\n"
            "            if s1[i-1] == s2[j-1]:\n"
            "                dp[i][j] = dp[i-1][j-1] + 1\n"
            "            else:\n"
            "                dp[i][j] = max(dp[i-1][j], dp[i][j-1])\n"
            "    return dp[m][n]\n"
        ),
    ),
    CodingTask(
        task_id="min_window_substring",
        difficulty="hard",
        problem=(
            "Write a function `min_window(s, t)` that returns the minimum "
            "window substring of `s` that contains all characters of `t` "
            "(including duplicates). If no such window exists, return the "
            "empty string. The answer is unique. Use the sliding window "
            "technique in O(n) time."
        ),
        test_code=(
            "from solution import min_window\n"
            "def test_min_window_basic():\n"
            "    assert min_window('ADOBECODEBANC', 'ABC') == 'BANC'\n"
            "    assert min_window('a', 'a') == 'a'\n"
            "    assert min_window('a', 'aa') == ''\n"
            "    assert min_window('aa', 'aa') == 'aa'\n"
            "def test_min_window_edge():\n"
            "    assert min_window('ab', 'b') == 'b'\n"
            "    assert min_window('cabwefgewcwaefgcf', 'cae') == 'cwae'\n"
        ),
        expected_solution=(
            "def min_window(s, t):\n"
            "    from collections import Counter\n"
            "    need = Counter(t)\n"
            "    missing = len(t)\n"
            "    start, end = 0, 0\n"
            "    i = 0\n"
            "    for j, ch in enumerate(s, 1):\n"
            "        if need[ch] > 0:\n"
            "            missing -= 1\n"
            "        need[ch] -= 1\n"
            "        while missing == 0:\n"
            "            if end == 0 or j - i < end - start:\n"
            "                start, end = i, j\n"
            "            need[s[i]] += 1\n"
            "            if need[s[i]] > 0:\n"
            "                missing += 1\n"
            "            i += 1\n"
            "    return s[start:end]\n"
        ),
    ),
    CodingTask(
        task_id="trapping_rain_water",
        difficulty="hard",
        problem=(
            "Write a function `trap(height)` where `height` is a list of "
            "non-negative integers representing an elevation map. Return the "
            "total units of water trapped after raining. Solve in O(n) time "
            "with two pointers."
        ),
        test_code=(
            "from solution import trap\n"
            "def test_trap_basic():\n"
            "    assert trap([0,1,0,2,1,0,1,3,2,1,2,1]) == 6\n"
            "    assert trap([4,2,0,3,2,5]) == 9\n"
            "    assert trap([]) == 0\n"
            "    assert trap([1,2,3]) == 0\n"
            "def test_trap_edge():\n"
            "    assert trap([3,0,3]) == 3\n"
            "    assert trap([5,4,3,2,1]) == 0\n"
        ),
        expected_solution=(
            "def trap(height):\n"
            "    if not height:\n"
            "        return 0\n"
            "    left, right = 0, len(height) - 1\n"
            "    left_max = right_max = 0\n"
            "    water = 0\n"
            "    while left < right:\n"
            "        if height[left] < height[right]:\n"
            "            if height[left] >= left_max:\n"
            "                left_max = height[left]\n"
            "            else:\n"
            "                water += left_max - height[left]\n"
            "            left += 1\n"
            "        else:\n"
            "            if height[right] >= right_max:\n"
            "                right_max = height[right]\n"
            "            else:\n"
            "                water += right_max - height[right]\n"
            "            right -= 1\n"
            "    return water\n"
        ),
    ),
    CodingTask(
        task_id="serialize_tree",
        difficulty="hard",
        problem=(
            "Implement a class `Codec` with methods `serialize(root)` and "
            "`deserialize(data)` for a binary tree. serialize returns a string "
            "representation; deserialize reconstructs the tree from that "
            "string. A node has attributes val, left, right (None for no "
            "child). Represent null children as 'N'. You must define TreeNode. "
            "Round-trip must be exact: deserialize(serialize(root)) reproduces "
            "the original tree structure."
        ),
        test_code=(
            "from solution import Codec, TreeNode\n"
            "def build(vals):\n"
            "    nodes = [TreeNode(v) if v is not None else None for v in vals]\n"
            "    for i in range(len(nodes)):\n"
            "        if nodes[i] is None: continue\n"
            "        li, ri = 2*i+1, 2*i+2\n"
            "        nodes[i].left = nodes[li] if li < len(nodes) else None\n"
            "        nodes[i].right = nodes[ri] if ri < len(nodes) else None\n"
            "    return nodes[0] if nodes else None\n"
            "def inorder(root):\n"
            "    out = []\n"
            "    def walk(n):\n"
            "        if n is None: return\n"
            "        walk(n.left); out.append(n.val); walk(n.right)\n"
            "    walk(root)\n"
            "    return out\n"
            "def test_roundtrip():\n"
            "    c = Codec()\n"
            "    for vals in [[1,2,3,None,None,4,5], [1,None,2], [5,4,3,2,1], [1], []]:\n"
            "        tree = build(vals)\n"
            "        rt = c.deserialize(c.serialize(tree))\n"
            "        assert inorder(tree) == inorder(rt)\n"
        ),
        expected_solution=(
            "class TreeNode:\n"
            "    def __init__(self, val=0, left=None, right=None):\n"
            "        self.val = val; self.left = left; self.right = right\n"
            "class Codec:\n"
            "    def serialize(self, root):\n"
            "        out = []\n"
            "        def enc(node):\n"
            "            if node is None:\n"
            "                out.append('N'); return\n"
            "            out.append(str(node.val))\n"
            "            enc(node.left); enc(node.right)\n"
            "        enc(root)\n"
            "        return ','.join(out)\n"
            "    def deserialize(self, data):\n"
            "        vals = iter(data.split(','))\n"
            "        def dec():\n"
            "            v = next(vals)\n"
            "            if v == 'N': return None\n"
            "            node = TreeNode(int(v))\n"
            "            node.left = dec(); node.right = dec()\n"
            "            return node\n"
            "        return dec()\n"
        ),
    ),
    CodingTask(
        task_id="meeting_rooms_ii",
        difficulty="hard",
        problem=(
            "Write a function `min_meeting_rooms(intervals)` that takes a list "
            "of meeting intervals [start, end) and returns the minimum number "
            "of conference rooms required. Solve in O(n log n) time."
        ),
        test_code=(
            "from solution import min_meeting_rooms\n"
            "def test_basic():\n"
            "    assert min_meeting_rooms([[0,30],[5,10],[15,20]]) == 2\n"
            "    assert min_meeting_rooms([[7,10],[2,4]]) == 1\n"
            "    assert min_meeting_rooms([]) == 0\n"
            "def test_overlap():\n"
            "    assert min_meeting_rooms([[1,5],[2,6],[3,7],[4,8]]) == 4\n"
            "    assert min_meeting_rooms([[1,10],[2,3],[4,5],[6,7]]) == 2\n"
        ),
        expected_solution=(
            "import heapq\n"
            "def min_meeting_rooms(intervals):\n"
            "    if not intervals:\n"
            "        return 0\n"
            "    intervals.sort(key=lambda x: x[0])\n"
            "    heap = [intervals[0][1]]\n"
            "    for s, e in intervals[1:]:\n"
            "        if s >= heap[0]:\n"
            "            heapq.heappop(heap)\n"
            "        heapq.heappush(heap, e)\n"
            "    return len(heap)\n"
        ),
    ),
    CodingTask(
        task_id="regex_validate_email",
        difficulty="hard",
        problem=(
            "Write a function `is_valid_email(s)` that returns True if and "
            "only if `s` is a valid email: a local part, an '@', and a domain. "
            "Rules: local part is 1-64 chars of [a-zA-Z0-9._-], domain is a "
            "dot-separated list of 1+ labels where each label is 1-63 chars "
            "of [a-zA-Z0-9-] (no leading/trailing hyphen). The domain must "
            "have exactly 2-4 labels. No consecutive dots in the domain. Do "
            "not use the email stdlib module."
        ),
        test_code=(
            "from solution import is_valid_email\n"
            "def test_valid():\n"
            "    assert is_valid_email('user@example.com') is True\n"
            "    assert is_valid_email('a.b-c_d@sub.example.co') is True\n"
            "    assert is_valid_email('x@y.io') is True\n"
            "def test_invalid():\n"
            "    assert is_valid_email('user@example') is False\n"
            "    assert is_valid_email('userexample.com') is False\n"
            "    assert is_valid_email('@example.com') is False\n"
            "    assert is_valid_email('user@.com') is False\n"
            "    assert is_valid_email('user@-example.com') is False\n"
            "    assert is_valid_email('user@exa..mple.com') is False\n"
            "    assert is_valid_email('a.b.c.d.e@x.y.z.w') is True\n"
        ),
        expected_solution=(
            "import re\n"
            "def is_valid_email(s):\n"
            "    if '@' not in s:\n"
            "        return False\n"
            "    local, _, domain = s.rpartition('@')\n"
            "    if not (1 <= len(local) <= 64):\n"
            "        return False\n"
            "    if not re.fullmatch(r'[a-zA-Z0-9._-]+', local):\n"
            "        return False\n"
            "    if '..' in domain:\n"
            "        return False\n"
            "    labels = domain.split('.')\n"
            "    if not (2 <= len(labels) <= 4):\n"
            "        return False\n"
            "    for lab in labels:\n"
            "        if not (1 <= len(lab) <= 63):\n"
            "            return False\n"
            "        if lab.startswith('-') or lab.endswith('-'):\n"
            "            return False\n"
            "        if not re.fullmatch(r'[a-zA-Z0-9-]+', lab):\n"
            "            return False\n"
            "    return True\n"
        ),
    ),
)
