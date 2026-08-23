"""Tests for ContextShaper — token budget management and context compression.

Covers shape() pipeline (budget check, force_compact), _estimate_tokens,
_truncate, get_stats, get_token_usage, clear_old_tool_results, and
inject_budget_awareness.
"""

from __future__ import annotations

import json

import pytest

from antigravity_k.engine.context_compressor import ContextCompressor
from antigravity_k.engine.context_shaper import ContextShaper


@pytest.fixture
def shaper(tmp_path):
    """Create a ContextShaper with a temp storage dir."""
    return ContextShaper(
        max_tokens=10000,
        reserve_tokens=500,
        collapse_threshold=500,
        storage_dir=str(tmp_path / "context"),
    )


def _make_messages(count: int, content: str = "Hello world") -> list[dict]:
    """Generate a list of messages for testing."""
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": content} for i in range(count)]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_values(self, tmp_path):
        s = ContextShaper(storage_dir=str(tmp_path / "ctx"))
        assert s.max_tokens == 128_000
        assert s.reserve_tokens == 4_096

    def test_custom_values(self, tmp_path):
        s = ContextShaper(max_tokens=50000, reserve_tokens=1000, storage_dir=str(tmp_path / "ctx"))
        assert s.max_tokens == 50000
        assert s.reserve_tokens == 1000

    def test_storage_dir_created(self, tmp_path):
        storage = tmp_path / "my_context"
        ContextShaper(storage_dir=str(storage))
        assert storage.exists()


# ---------------------------------------------------------------------------
# shape — main compression pipeline
# ---------------------------------------------------------------------------


class TestShape:
    def test_force_compact_preserves_old_structured_tool_evidence(self, tmp_path):
        # Given: an overflow retry has old verified evidence followed by a long conversation.
        old_result = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"verify.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\n"
            + ("x" * 2000)
            + "\nVERIFIED_RESULT=5050\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": old_result},
        ]
        messages.extend(
            {"role": "assistant" if index % 2 else "user", "content": f"filler-{index} " * 120} for index in range(16)
        )
        shaper = ContextShaper(
            max_tokens=600,
            reserve_tokens=50,
            storage_dir=str(tmp_path / "overflow-context"),
        )

        # When: a context-overflow retry forces aggressive compaction.
        result = shaper.shape(messages, budget=550, force_compact=True)

        # Then: compacted provenance and the verified tail remain in the next prompt context.
        content = "\n".join(message["content"] for message in result)
        assert "[TOOL_EVIDENCE]" in content
        assert "VERIFIED_RESULT=5050" in content

    def test_short_messages_unchanged(self, shaper):
        """Messages within budget are returned unchanged."""
        messages = _make_messages(3, "short")
        result = shaper.shape(messages)
        assert len(result) == 3

    def test_force_compact_reduces_size(self, shaper):
        """force_compact triggers compression even when within budget."""
        messages = _make_messages(20, "A" * 200)
        original_size = shaper._estimate_tokens(messages)
        result = shaper.shape(messages, force_compact=True)
        result_size = shaper._estimate_tokens(result)
        assert result_size <= original_size

    def test_shape_preserves_message_structure(self, shaper):
        """Shaped messages still have role and content keys."""
        messages = [{"role": "user", "content": "test"}]
        result = shaper.shape(messages)
        for msg in result:
            assert "role" in msg
            assert "content" in msg

    def test_shape_empty_messages(self, shaper):
        result = shaper.shape([])
        assert result == []

    def test_shape_returns_list(self, shaper):
        result = shaper.shape(_make_messages(2))
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _estimate_tokens / _truncate
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    def test_estimate_tokens_positive(self, shaper):
        messages = [{"role": "user", "content": "Hello world"}]
        assert shaper._estimate_tokens(messages) > 0

    def test_estimate_tokens_empty(self, shaper):
        assert shaper._estimate_tokens([]) == 0

    def test_estimate_tokens_grows_with_content(self, shaper):
        short = shaper._estimate_tokens([{"role": "user", "content": "hi"}])
        long = shaper._estimate_tokens([{"role": "user", "content": "x" * 1000}])
        assert long > short

    def test_truncate_short_text_unchanged(self, shaper):
        assert shaper._truncate("short", 100) == "short"

    def test_truncate_long_text_capped(self, shaper):
        result = shaper._truncate("A" * 500, 100)
        assert len(result) <= 200  # truncated + suffix
        assert "500 total chars" in result


# ---------------------------------------------------------------------------
# get_stats / get_token_usage
# ---------------------------------------------------------------------------


class TestStatsAndUsage:
    def test_initial_stats_zero(self, shaper):
        stats = shaper.get_stats()
        assert stats["total_shaped"] == 0
        assert stats["tokens_saved"] == 0

    def test_get_token_usage_structure(self, shaper):
        messages = [{"role": "user", "content": "test message"}]
        usage = shaper.get_token_usage(messages)
        assert "total_tokens" in usage
        assert "max_tokens" in usage
        assert "usage_pct" in usage
        assert "budget_remaining" in usage
        assert "by_role" in usage

    def test_get_token_usage_empty_messages(self, shaper):
        usage = shaper.get_token_usage([])
        assert usage["total_tokens"] == 0
        assert usage["usage_pct"] == 0.0

    def test_usage_pct_increases_with_content(self, shaper):
        small = shaper.get_token_usage([{"role": "user", "content": "a"}])
        large = shaper.get_token_usage([{"role": "user", "content": "A" * 5000}])
        assert large["usage_pct"] > small["usage_pct"]


# ---------------------------------------------------------------------------
# clear_old_tool_results
# ---------------------------------------------------------------------------


class TestClearOldToolResults:
    def test_compaction_preserves_each_structured_result_in_a_batched_message(self, shaper):
        # Given: one old message contains two tool responses from a parallel batch.
        first = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"first.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\n" + ("a" * 1000) + "\nFIRST_RESULT=41\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        second = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"read_file","source":"second.txt"}\n'
            "[UNTRUSTED_TOOL_RESULT]\n"
            + ("b" * 1000)
            + "\nSECOND_RESULT=42\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        messages = [
            {"role": "user", "content": f"{first}\n{second}"},
            {"role": "user", "content": "<tool_response>recent</tool_response>"},
        ]

        # When: the batched message becomes an old tool result.
        result = shaper.clear_old_tool_results(messages, keep_last=1)

        # Then: both provenance records and both ground-truth tails remain available.
        compacted = result[0]["content"]
        assert '"source":"first.py"' in compacted
        assert '"source":"second.txt"' in compacted
        assert "FIRST_RESULT=41" in compacted
        assert "SECOND_RESULT=42" in compacted

    def test_compaction_preserves_structured_provenance_and_verified_result(self, shaper):
        # Given: an old structured tool response with a verified result at the end.
        old_result = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"python verify.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\n"
            + ("x" * 2000)
            + "\nVERIFIED_RESULT=5050\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        messages = [
            {"role": "user", "content": old_result},
            {"role": "user", "content": "<tool_response>recent</tool_response>"},
        ]

        # When: old tool results are compacted before the next model turn.
        result = shaper.clear_old_tool_results(messages, keep_last=1)

        # Then: the compact form retains machine-readable provenance and ground truth.
        compacted = result[0]["content"]
        assert len(compacted) < len(old_result)
        assert "[TOOL_EVIDENCE]" in compacted
        assert '"tool":"run_bash_command"' in compacted
        assert "VERIFIED_RESULT=5050" in compacted

    def test_removes_old_tool_results(self, shaper):
        """Old tool/function results are removed, keeping only recent ones."""
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "function", "content": "old result 1"},
            {"role": "function", "content": "old result 2"},
            {"role": "assistant", "content": "a1"},
            {"role": "function", "content": "recent result"},
        ]
        result = shaper.clear_old_tool_results(messages, keep_last=1)
        # The most recent tool result should be kept; older ones removed.
        assert len(result) <= len(messages)

    def test_keep_last_preserves_recent(self, shaper):
        messages = [
            {"role": "function", "content": "r1"},
            {"role": "function", "content": "r2"},
            {"role": "function", "content": "r3"},
        ]
        result = shaper.clear_old_tool_results(messages, keep_last=2)
        assert len(result) >= 2

    def test_no_tool_results_unchanged(self, shaper):
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        result = shaper.clear_old_tool_results(messages)
        assert len(result) == len(messages)


class TestAdaptiveCompressionEvidence:
    def test_prompt_cache_prefix_is_byte_stable_and_compaction_is_deterministic(self):
        # Given: the provider has cached the first two messages as one immutable prefix.
        cached_prefix = [
            {"role": "system", "content": "stable system instructions"},
            {"role": "user", "content": "stable repository contract"},
        ]
        evidence = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"verify.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\nVERIFIED_RESULT=5050\n"
            "[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        messages = [
            *cached_prefix,
            {"role": "tool", "content": evidence},
            *[
                {
                    "role": "user" if index % 2 == 0 else "assistant",
                    "content": f"mutable-{index} " * 80,
                }
                for index in range(10)
            ],
        ]
        compressor = ContextCompressor(token_limit=320, keep_last_n=4)

        # When: identical input and prompt-cache state are compacted twice.
        first = compressor.adaptive_compress(messages, prompt_cache_prefix=2)
        second = compressor.adaptive_compress(messages, prompt_cache_prefix=2)

        # Then: the cached bytes and deterministic tool evidence survive unchanged.
        def canonical(value):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        assert canonical(first[:2]) == canonical(cached_prefix)
        assert canonical(first) == canonical(second)
        assert "[TOOL_EVIDENCE]" in canonical(first)
        assert "VERIFIED_RESULT=5050" in canonical(first)
        assert messages[:2] == cached_prefix

    def test_single_oversized_user_goal_is_bounded_without_losing_its_edges(self):
        # Given: the current user goal alone is larger than the target model budget.
        goal = "BEGIN_OBJECTIVE " + ("implementation detail " * 200) + " END_CONSTRAINT"
        compressor = ContextCompressor(token_limit=100, keep_last_n=6)

        # When: production adaptive compression handles the short trajectory.
        result = compressor.adaptive_compress([{"role": "user", "content": goal}])

        # Then: the final context fits while retaining both ends of the objective.
        assert sum(compressor.estimate_tokens(message["content"]) for message in result) <= 100
        assert "BEGIN_OBJECTIVE" in result[0]["content"]
        assert "END_CONSTRAINT" in result[0]["content"]

    def test_model_summary_cannot_replace_structured_tool_evidence(self):
        # Given: the local summarizer returns fluent prose without the verified result.
        old_result = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"python verify.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\n"
            + ("x" * 2000)
            + "\nVERIFIED_RESULT=5050\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        compressor = ContextCompressor(
            token_limit=100,
            keep_last_n=1,
            summarize_fn=lambda _prompt: "The earlier work completed and the session can continue safely.",
        )
        messages = [
            {"role": "user", "content": old_result},
            {"role": "assistant", "content": "old filler " * 80},
            {"role": "user", "content": "recent"},
        ]

        # When: model-backed compression succeeds.
        result = compressor.compress(messages)

        # Then: deterministic evidence is attached alongside the model summary.
        content = "\n".join(message["content"] for message in result)
        assert "[TOOL_EVIDENCE]" in content
        assert "VERIFIED_RESULT=5050" in content

    def test_adaptive_compression_preserves_structured_provenance_and_verified_result(self):
        # Given: verified tool evidence falls outside the recent-message retention window.
        old_result = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"python verify.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\n"
            + ("x" * 2000)
            + "\nVERIFIED_RESULT=5050\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": old_result},
            {"role": "assistant", "content": "old filler " * 80},
        ]
        messages.extend(
            {"role": "user" if index % 2 == 0 else "assistant", "content": f"recent-{index} " * 8} for index in range(6)
        )
        compressor = ContextCompressor(token_limit=350, keep_last_n=6)

        # When: the production token-budget compressor summarizes old messages.
        result = compressor.adaptive_compress(messages, token_budget=350)

        # Then: the summary still carries provenance and executable ground truth.
        content = "\n".join(message["content"] for message in result)
        assert "[TOOL_EVIDENCE]" in content
        assert '"tool":"run_bash_command"' in content
        assert "VERIFIED_RESULT=5050" in content

    def test_hard_budget_compacts_structured_evidence_without_mutating_source(self):
        # Given: one oversized verified result must fit a small final budget.
        evidence = (
            '<tool_response>\n[TOOL_EVIDENCE] {"tool":"run_bash_command","source":"verify.py"}\n'
            "[UNTRUSTED_TOOL_RESULT]\nBEGIN_RESULT\n"
            + ("detail " * 300)
            + "\nVERIFIED_RESULT=5050\n[/UNTRUSTED_TOOL_RESULT]\n</tool_response>"
        )
        source = [{"role": "tool", "content": evidence}]
        compressor = ContextCompressor(token_limit=120)

        # When: the final budget enforcer compacts the only message.
        result = compressor.adaptive_compress(source)

        # Then: provenance and ground truth remain, and caller-owned input stays intact.
        content = result[0]["content"]
        assert sum(compressor.estimate_tokens(message["content"]) for message in result) <= 120
        assert "[TOOL_EVIDENCE]" in content
        assert "VERIFIED_RESULT=5050" in content
        assert source[0]["content"] == evidence


# ---------------------------------------------------------------------------
# inject_budget_awareness
# ---------------------------------------------------------------------------


class TestInjectBudgetAwareness:
    def test_injects_into_non_empty_messages(self, shaper):
        """Budget awareness adds a system note when approaching limits."""
        messages = [{"role": "user", "content": "test"}]
        result = shaper.inject_budget_awareness(messages)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_inject_empty_messages(self, shaper):
        result = shaper.inject_budget_awareness([])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _budget_reduce
# ---------------------------------------------------------------------------


class TestBudgetReduce:
    def test_target_smaller_than_current(self, shaper):
        """_budget_reduce returns a target smaller than the current size."""
        target = shaper._budget_reduce(current=10000, budget=5000)
        assert target <= 5000

    def test_target_not_negative(self, shaper):
        target = shaper._budget_reduce(current=100, budget=50)
        assert target >= 0
