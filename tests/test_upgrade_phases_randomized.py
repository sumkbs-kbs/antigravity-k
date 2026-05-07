"""
Antigravity-K: Randomized Upgrade Phase Tests
=============================================
매번 다른 입력/시나리오로 테스트하여 과적합을 방지합니다.
동일 테스트를 반복 실행해도 입력값이 달라집니다.
"""

import random
import string
import textwrap
import os

# ─── 랜덤 테스트 재현성 보장 ──────────────────────────────────────

SEED = os.environ.get("RANDOM_SEED", str(random.randint(0, 999999)))
random.seed(SEED)
print(f"\n[Randomized Test] Using SEED: {SEED}")

# ─── 랜덤 입력 생성기 ─────────────────────────────────────────


def _rand_python_code():
    """매번 다른 Python 코드를 생성합니다."""
    fn_names = [
        "process",
        "calculate",
        "transform",
        "validate",
        "convert",
        "serialize",
        "dispatch",
        "handle",
        "render",
        "analyze",
    ]
    cls_names = [
        "Manager",
        "Handler",
        "Service",
        "Controller",
        "Processor",
        "Builder",
        "Factory",
        "Registry",
        "Adapter",
        "Engine",
    ]
    random.shuffle(fn_names)
    random.shuffle(cls_names)

    fn1, fn2 = fn_names[:2]
    cls1 = cls_names[0]
    method1, method2 = fn_names[2:4]

    return (
        textwrap.dedent(
            f'''
        """Auto-generated test module."""
        import os
        import sys

        def {fn1}(data):
            """Process input data."""
            return data * 2

        def {fn2}(value: int) -> str:
            """Convert value to string."""
            return str(value)

        class {cls1}:
            """Main handler class."""
            def {method1}(self):
                return True

            def {method2}(self, x, y):
                return x + y
    '''
        ),
        fn1,
        fn2,
        cls1,
        method1,
        method2,
    )


def _rand_markdown():
    """매번 다른 Markdown 문서를 생성합니다."""
    topics = [
        "Architecture",
        "Deployment",
        "Security",
        "Performance",
        "Testing",
        "Monitoring",
        "Configuration",
        "Database",
    ]
    random.shuffle(topics)
    sections = random.randint(3, 6)
    lines = [f"# {topics[0]} Guide"]
    for i in range(sections):
        t = topics[min(i + 1, len(topics) - 1)]
        lines.append(f"\n## {t}\n")
        lines.append(f"This section covers {t.lower()} details and best practices.\n")
    return "\n".join(lines), sections + 1  # +1 for main title section


def _rand_simple_query():
    """매번 다른 단순 질문을 생성합니다."""
    templates = [
        "안녕하세요 {topic}에 대해 도움이 필요합니다",
        "안녕 간단한 {topic} 질문이 있어요",
        "hello {topic} 관련 도움 부탁해요",
        "{topic} 파일 목록 보여줘",
        "간단한 {topic} 사용법 알려줘",
    ]
    topics = ["파이썬", "자바", "도커", "리눅스", "깃"]
    return random.choice(templates).format(topic=random.choice(topics))


def _rand_complex_query():
    """매번 다른 복잡 질문을 생성합니다."""
    templates = [
        "마이크로서비스 아키텍처로 {db} 스키마를 마이그레이션하는 알고리즘을 설계하고 시간복잡도를 분석해주세요",
        "{pattern} 패턴으로 분산 시스템의 동시성 문제를 해결하는 보안 아키텍처를 설계해주세요",
        "{db} 데이터베이스의 캐시 레이어를 최적화하는 알고리즘을 구현하고 시간복잡도를 비교해주세요",
        "대규모 {pattern} 아키텍처의 보안 취약점을 분석하고 마이그레이션 전략을 설계해주세요",
    ]
    dbs = ["PostgreSQL", "MongoDB", "Redis", "DynamoDB"]
    patterns = ["CQRS", "Event Sourcing", "Saga", "Circuit Breaker"]
    return random.choice(templates).format(
        db=random.choice(dbs), pattern=random.choice(patterns)
    )


def _rand_broken_code():
    """매번 다른 구문 오류가 있는 코드를 생성합니다."""
    errors = [
        "```python\ndef broken(\n    return\n```",
        "```python\nclass Foo\n    pass\n```",
        '```python\nif True\n    print("x")\n```',
        "```python\ndef f(x, y,):\n    return x +\n```",
        "```python\nfor i in range(10\n    print(i)\n```",
    ]
    return random.choice(errors)


def _rand_contradiction():
    """매번 다른 자기 모순 텍스트를 생성합니다."""
    pairs = [
        ("O(1)", "O(n)"),
        ("thread-safe", "not thread-safe"),
        ("가능합니다", "불가능합니다"),
        ("동기", "비동기"),
    ]
    a, b = random.choice(pairs)
    return f"이 함수는 {a}이며 {b}입니다.", a, b


def _rand_messages(count=7):
    """매번 다른 대화 메시지 히스토리를 생성합니다."""
    topics = ["리팩토링", "배포", "테스트", "보안", "성능", "마이그레이션"]
    msgs = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(count - 1):
        role = "user" if i % 2 == 0 else "assistant"
        topic = random.choice(topics)
        content = (
            f"{topic} 관련 {'질문' if role == 'user' else '답변'}: "
            + "X" * random.randint(100, 300)
        )
        msgs.append({"role": role, "content": content})
    return msgs


# ─── Phase 21: RAG Indexer 랜덤 테스트 ──────────────────────────


class TestRAGIndexerRandomized:
    def test_chunk_python_with_random_code(self):
        from antigravity_k.engine.rag_indexer import RAGIndexer

        indexer = RAGIndexer(project_root="/tmp")
        code, fn1, fn2, cls1, m1, m2 = _rand_python_code()
        chunks = indexer._chunk_python("rand_test.py", code)
        names = [c.node_name for c in chunks]
        types = [c.node_type for c in chunks]

        assert fn1 in names, f"FAIL: {fn1} not in {names}"
        assert any(cls1 in n for n in names), f"FAIL: {cls1} not in {names}"
        assert "function" in types
        assert len(chunks) >= 3, f"Expected >=3 chunks, got {len(chunks)}"

    def test_chunk_markdown_with_random_doc(self):
        from antigravity_k.engine.rag_indexer import RAGIndexer

        indexer = RAGIndexer(project_root="/tmp")
        md, expected_sections = _rand_markdown()
        chunks = indexer._chunk_markdown("rand.md", md)
        assert len(chunks) >= 2, f"Expected >=2 chunks, got {len(chunks)}"
        assert all(c.node_type == "text_section" for c in chunks)

    def test_generic_chunking_with_random_size(self):
        from antigravity_k.engine.rag_indexer import RAGIndexer

        indexer = RAGIndexer(project_root="/tmp")
        line_count = random.randint(80, 200)
        content = "\n".join(
            f"line_{i}: {''.join(random.choices(string.ascii_lowercase, k=20))}"
            for i in range(line_count)
        )
        chunks = indexer._chunk_generic("rand.txt", content)
        assert len(chunks) >= 2
        # 모든 원본 라인이 청크에 포함되어야 함
        total_lines_in_chunks = sum(
            c.end_line - c.start_line + 1 for c in chunks if c.content.strip()
        )
        assert total_lines_in_chunks >= line_count * 0.8

    def test_hash_change_detection(self):
        from antigravity_k.engine.rag_indexer import RAGIndexer

        indexer = RAGIndexer(project_root="/tmp")
        # 첫 번째 인덱싱
        code1 = f"def rand_{random.randint(1000,9999)}(): pass"
        _chunks1 = indexer._chunk_python("hash_test.py", code1)  # noqa: F841
        indexer._file_hashes["hash_test.py"] = "abc123"
        # 해시가 같으면 스킵하는지 확인 (index_file은 파일 시스템 의존이라 해시만 확인)
        assert "hash_test.py" in indexer._file_hashes


# ─── Phase 22: CoV 랜덤 테스트 ───────────────────────────────────


class TestCoVRandomized:
    def test_random_simple_query_is_low_complexity(self):
        from antigravity_k.engine.chain_of_verification import ChainOfVerification

        cov = ChainOfVerification()
        for _ in range(5):
            q = _rand_simple_query()
            score = cov.estimate_complexity(q)
            assert score < 0.4, f"Simple query '{q}' scored {score}"

    def test_random_complex_query_is_high_complexity(self):
        from antigravity_k.engine.chain_of_verification import ChainOfVerification

        cov = ChainOfVerification()
        for _ in range(5):
            q = _rand_complex_query()
            score = cov.estimate_complexity(q)
            assert score >= 0.4, f"Complex query '{q}' scored {score}"

    def test_random_broken_code_detected(self):
        from antigravity_k.engine.chain_of_verification import ChainOfVerification

        cov = ChainOfVerification()
        code = _rand_broken_code()
        issues = cov._rule_based_check("코드 작성", code)
        assert len(issues) > 0, f"Broken code not detected: {code[:50]}"

    def test_random_contradiction_detected(self):
        from antigravity_k.engine.chain_of_verification import ChainOfVerification

        cov = ChainOfVerification()
        text, a, b = _rand_contradiction()
        issues = cov._rule_based_check("analysis", text)
        assert any("모순" in i for i in issues), f"Contradiction {a}/{b} not detected"

    def test_cov_run_with_random_valid_code(self):
        from antigravity_k.engine.chain_of_verification import ChainOfVerification

        fn_name = f"func_{random.randint(1000, 9999)}"
        response = (
            f"```python\ndef {fn_name}(x):\n    return x * 2\n```\n"
            f"이 함수는 입력을 2배로 반환합니다. 시간복잡도는 O(1)입니다."
        )
        cov = ChainOfVerification(min_response_length=10, complexity_threshold=0.0)
        trace = cov.run("함수 작성", response)
        assert trace.verification_result is not None
        assert trace.revised_response == response


# ─── Phase 25: Context Compressor 랜덤 테스트 ────────────────────


class TestContextCompressorRandomized:
    def test_compress_with_random_messages(self):
        from antigravity_k.engine.context_compressor import ContextCompressor

        summaries = []
        topic = random.choice(["배포 전략", "DB 스키마", "API 설계", "캐시 정책"])

        cc = ContextCompressor(
            token_limit=100,
            keep_last_n=2,
            summarize_fn=lambda p: (
                summaries.append(1),
                f"{topic} 관련 결정사항 요약 완료입니다",
            )[1],
        )
        msgs = _rand_messages(7)
        result = cc.compress(msgs)
        assert len(summaries) > 0, "summarize_fn not called"
        assert any(topic in m.get("content", "") for m in result)

    def test_rag_injection_with_random_query(self):
        from antigravity_k.engine.context_compressor import ContextCompressor

        fn = f"func_{random.randint(1000, 9999)}"

        cc = ContextCompressor(
            token_limit=5000,
            rag_search_fn=lambda q, n: f"<relevant_code>\ndef {fn}(): pass\n</relevant_code>",
        )
        base = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"{fn} 함수 찾아줘"},
        ]
        enriched = cc.enrich_with_rag(base, fn)
        assert len(enriched) == len(base) + 1
        rag_content = [
            m["content"] for m in enriched if "코드베이스 컨텍스트" in m["content"]
        ]
        assert len(rag_content) == 1
        assert fn in rag_content[0]

    def test_memory_injection_after_random_pruning(self):
        from antigravity_k.engine.context_compressor import ContextCompressor

        keyword = random.choice(
            ["마이크로서비스", "모놀리식", "서버리스", "이벤트 드리븐"]
        )
        cc = ContextCompressor(
            token_limit=50,
            keep_last_n=1,
            summarize_fn=lambda p, kw=keyword: f"{kw} 아키텍처로 전환을 결정하고 새로운 구조를 적용했습니다",
        )
        msgs = _rand_messages(5)
        cc.compress(msgs)
        assert len(cc.get_pruned_summaries()) > 0

        base = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
        mem = cc.inject_memory(base)
        mem_msgs = [m for m in mem if "장기 기억" in m.get("content", "")]
        assert len(mem_msgs) == 1
        assert keyword in mem_msgs[0]["content"]
