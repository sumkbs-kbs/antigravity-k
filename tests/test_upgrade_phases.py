"""Tests for RAG Indexer, Chain-of-Verification, Context Compressor upgrade,
and External Brain auto-delegation.
"""

from collections.abc import Callable
from typing import cast, final

import pytest

from antigravity_k.engine.chain_of_verification import ChainOfVerification
from antigravity_k.engine.rag_indexer import CodeChunk, RAGIndexer


def _chunk_python(indexer: RAGIndexer, rel_path: str, content: str) -> list[CodeChunk]:
    chunker = cast(Callable[[str, str], list[CodeChunk]], getattr(indexer, "_chunk_python"))
    return chunker(rel_path, content)


def _chunk_markdown(indexer: RAGIndexer, rel_path: str, content: str) -> list[CodeChunk]:
    chunker = cast(Callable[[str, str], list[CodeChunk]], getattr(indexer, "_chunk_markdown"))
    return chunker(rel_path, content)


def _make_id(file_path: str, suffix: str) -> str:
    maker = cast(Callable[[str, str], str], getattr(RAGIndexer, "_make_id"))
    return maker(file_path, suffix)


def _rule_based_check(cov: ChainOfVerification, task: str, response: str) -> list[str]:
    checker = cast(Callable[[str, str], list[str]], getattr(cov, "_rule_based_check"))
    return checker(task, response)

# ─── Phase A: RAG Indexer Tests ──────────────────────────────────


class TestRAGIndexer:
    def test_chunk_python_splits_by_function(self):
        indexer = RAGIndexer(project_root="/tmp")
        code = '''"""Module doc."""
import os

def hello():
    """Say hello."""
    return "hi"

class Foo:
    """Foo class."""
    def bar(self):
        return 1

    def baz(self):
        return 2
'''
        chunks = _chunk_python(indexer, "test.py", code)
        names = [c.node_name for c in chunks]
        # header, hello function, Foo class, Foo.bar, Foo.baz
        assert any("hello" in n for n in names), f"Expected hello in {names}"
        assert any("Foo" in n for n in names), f"Expected Foo in {names}"
        assert any("bar" in n for n in names), f"Expected bar in {names}"

    def test_chunk_markdown_splits_by_heading(self):
        indexer = RAGIndexer(project_root="/tmp")
        md = "# Title\nParagraph\n## Section\nMore text\n## Another\nEnd"
        chunks = _chunk_markdown(indexer, "doc.md", md)
        assert len(chunks) >= 2, f"Expected >= 2 sections, got {len(chunks)}"
        assert chunks[0].node_type == "text_section"

    def test_format_context_returns_xml_block(self):
        """format_context should produce <relevant_code> XML when results exist."""
        @final
        class _VectorStoreDouble:
            persist_directory: str = "/tmp"

            def search(self, query: str, n_results: int = 5) -> list[dict[str, object]]:
                _ = (query, n_results)
                return [
                    {
                        "text": "def foo(): pass",
                        "metadata": {
                            "source": "a.py",
                            "node_name": "foo",
                            "start_line": 1,
                            "end_line": 2,
                        },
                    },
                ]

        mock_store = _VectorStoreDouble()
        indexer = RAGIndexer(project_root="/tmp", vector_store=mock_store)
        ctx = indexer.format_context("foo function")
        assert "<relevant_code>" in ctx
        assert "a.py" in ctx

    def test_make_id_is_deterministic(self):
        id1 = _make_id("file.py", "fn_hello")
        id2 = _make_id("file.py", "fn_hello")
        assert id1 == id2


# ─── Phase B: Chain-of-Verification Tests ────────────────────────


class TestChainOfVerification:
    def test_simple_query_skips_verification(self):
        cov = ChainOfVerification()
        score = cov.estimate_complexity("안녕하세요 도움이 필요합니다")
        assert score < 0.4, f"Simple query should be low complexity: {score}"

    def test_complex_query_triggers_verification(self):
        cov = ChainOfVerification()
        score = cov.estimate_complexity(
            "마이크로서비스 아키텍처로 데이터베이스 스키마를 마이그레이션하는 "
            + "알고리즘을 설계하고 시간복잡도를 분석해주세요",
        )
        assert score >= 0.4, f"Complex query should be high complexity: {score}"

    def test_rule_based_check_catches_syntax_error(self):
        cov = ChainOfVerification()
        response = "```python\ndef broken(\n    return\n```"
        issues = _rule_based_check(cov, "코드 작성", response)
        assert len(issues) > 0, "Should detect syntax error in code block"
        assert "구문 오류" in issues[0]

    def test_cov_run_skips_short_response(self):
        cov = ChainOfVerification()
        trace = cov.run("hello", "짧은 답변")
        assert trace.skipped is True
        assert trace.total_passes == 1

    def test_cov_run_with_valid_code_passes(self):
        cov = ChainOfVerification(min_response_length=10, complexity_threshold=0.0)
        response = (
            '```python\ndef hello():\n    return "world"\n```\n이 함수는 "world"를 반환합니다. 시간복잡도는 O(1)입니다.'
        )
        trace = cov.run("함수 작성", response)
        # No generate_fn so no LLM verification, only rule-based
        assert trace.verification_result is not None
        assert trace.revised_response == response  # no revisions needed


# ─── Phase A+E: Context Compressor Tests ─────────────────────────


class TestContextCompressorUpgrade:
    def test_compress_uses_llm_summary_when_available(self):
        from antigravity_k.engine.context_compressor import ContextCompressor

        summarize_called: list[str] = []

        def mock_summarize(prompt: str) -> str:
            summarize_called.append(prompt)
            return "사용자가 아키텍처 변경을 결정하고 새로운 모듈 구조를 적용했습니다"

        cc = ContextCompressor(token_limit=100, keep_last_n=2, summarize_fn=mock_summarize)
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "A" * 200},
            {"role": "assistant", "content": "B" * 200},
            {"role": "user", "content": "C" * 200},
            {"role": "assistant", "content": "D" * 200},
            {"role": "user", "content": "recent1"},
            {"role": "assistant", "content": "recent2"},
        ]
        result = cc.compress(messages)
        assert len(summarize_called) > 0, "Should have called summarize_fn"
        # Check that the summary is in the result
        assert any("아키텍처" in m.get("content", "") for m in result)

    def test_enrich_with_rag_injects_context(self):
        from antigravity_k.engine.context_compressor import ContextCompressor

        def mock_rag(query: str, n: int) -> str:
            _ = (query, n)
            return "<relevant_code>\ndef foo(): pass\n</relevant_code>"

        cc = ContextCompressor(token_limit=5000, rag_search_fn=mock_rag)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "foo 함수 찾아줘"},
        ]
        result = cc.enrich_with_rag(messages, "foo 함수")
        # Should have an extra system message with RAG content
        assert len(result) > len(messages)
        rag_msgs = [m for m in result if "코드베이스 컨텍스트" in m.get("content", "")]
        assert len(rag_msgs) == 1

    def test_pruned_summaries_are_preserved(self):
        from antigravity_k.engine.context_compressor import ContextCompressor

        cc = ContextCompressor(token_limit=50, keep_last_n=1, summarize_fn=lambda p: "요약 결과")
        messages = [
            {"role": "user", "content": "X" * 200},
            {"role": "assistant", "content": "Y" * 200},
            {"role": "user", "content": "Z"},
        ]
        _ = cc.compress(messages)
        summaries = cc.get_pruned_summaries()
        assert len(summaries) > 0, "Should preserve pruned summary"


# ─── Phase D: External Brain Auto-Delegation Tests ───────────────


class TestExternalBrainAutoDelegation:
    @pytest.mark.asyncio
    async def test_adapt_strategy_triggers_delegation_after_3_failures(self):
        from unittest.mock import MagicMock

        from antigravity_k.engine.cognitive_loop import CognitiveLoop

        mock_router = MagicMock()
        loop = CognitiveLoop(
            project_root="/tmp",
            external_brain_router=mock_router,
        )

        # Simulate 3 consecutive failures
        setattr(loop, "_step_history", [
            {
                "tool": "write_file",
                "grade": "F",
                "passed": False,
                "issues": ["구문 오류"],
                "timestamp": "t1",
            },
            {
                "tool": "write_file",
                "grade": "F",
                "passed": False,
                "issues": ["파일 없음"],
                "timestamp": "t2",
            },
            {
                "tool": "edit_file",
                "grade": "F",
                "passed": False,
                "issues": ["권한 거부"],
                "timestamp": "t3",
            },
        ])

        result = await loop.adapt_strategy("파일 수정 작업", None)
        # Should at least attempt adaptation (2+ failures)
        assert result is not None
        assert "전략 변경" in result or "External Brain" in result

    @pytest.mark.asyncio
    async def test_no_delegation_without_router(self):
        from antigravity_k.engine.cognitive_loop import CognitiveLoop

        loop = CognitiveLoop(project_root="/tmp")
        setattr(loop, "_step_history", [
            {
                "tool": "a",
                "grade": "F",
                "passed": False,
                "issues": ["err"],
                "timestamp": "t",
            },
        ] * 3)

        result = await loop.adapt_strategy("task", None)
        # Without external_brain_router, should fall through to normal adaptation
        assert result is not None
        assert "전략 변경" in result
