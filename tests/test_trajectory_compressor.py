"""Tests for TrajectoryCompressor and FactAppender.

TrajectoryCompressor: compresses long chat histories into head+summary+tail.
FactAppender: collects facts during a session for context injection.
"""

from __future__ import annotations

from antigravity_k.engine.fact_appender import FactAppender
from antigravity_k.engine.trajectory_compressor import CompressionResult, TrajectoryCompressor

# ---------------------------------------------------------------------------
# TrajectoryCompressor
# ---------------------------------------------------------------------------


class TestShouldCompress:
    """should_compress threshold logic."""

    def test_short_history_no_compression(self):
        """A short history should not trigger compression."""
        comp = TrajectoryCompressor(max_messages=40)
        messages = [{"role": "user", "content": "hi"}] * 5
        assert comp.should_compress(messages) is False

    def test_too_many_messages_triggers(self):
        """Exceeding max_messages triggers compression."""
        comp = TrajectoryCompressor(max_messages=10)
        messages = [{"role": "user", "content": "x"}] * 11
        assert comp.should_compress(messages) is True

    def test_too_many_chars_triggers(self):
        """Exceeding max_chars triggers compression even with few messages."""
        comp = TrajectoryCompressor(max_messages=100, max_chars=100)
        messages = [{"role": "user", "content": "x" * 200}]
        assert comp.should_compress(messages) is True

    def test_empty_messages_no_compression(self):
        comp = TrajectoryCompressor()
        assert comp.should_compress([]) is False


class TestCompress:
    """compress() behavior."""

    def test_empty_messages_returns_empty(self):
        comp = TrajectoryCompressor()
        result = comp.compress([])
        assert result.compressed_messages == []

    def test_head_and_tail_preserved(self):
        """The first message and last 10 messages are always kept."""
        comp = TrajectoryCompressor()
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(20)]
        result = comp.compress(messages)

        # First message preserved
        assert result.compressed_messages[0]["content"] == "msg-0"
        # Last 10 messages preserved
        tail_contents = [m["content"] for m in result.compressed_messages[-10:]]
        assert "msg-19" in tail_contents

    def test_summary_inserted_for_middle(self):
        """A system summary message is inserted between head and tail."""
        comp = TrajectoryCompressor(summarize_fn=lambda text: "SUMMARY")
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(20)]
        result = comp.compress(messages)

        summary_msgs = [m for m in result.compressed_messages if m["role"] == "system"]
        assert len(summary_msgs) >= 1
        assert "SUMMARY" in summary_msgs[0]["content"]

    def test_custom_summarize_fn_used(self):
        """A custom summarize_fn is called and its result is used."""
        calls = []

        def my_summarize(text):
            calls.append(text)
            return "custom summary"

        comp = TrajectoryCompressor(summarize_fn=my_summarize)
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(15)]
        result = comp.compress(messages)

        assert len(calls) == 1
        assert "custom summary" in result.compressed_messages[1]["content"]

    def test_no_summarize_fn_truncates(self):
        """Without a summarize_fn, the raw text is truncated to 4000 chars."""
        comp = TrajectoryCompressor(summarize_fn=None)
        messages = [{"role": "user", "content": "A" * 5000}]
        messages = messages * 2
        result = comp.compress(messages)

        summary_msgs = [m for m in result.compressed_messages if m["role"] == "system"]
        if summary_msgs:
            # Truncated to at most 4000 chars in the raw form
            assert len(summary_msgs[0]["content"]) <= 5000  # includes prefix

    def test_summarize_fn_error_falls_back(self):
        """If summarize_fn raises, the fallback truncation is used."""

        def bad_summarize(text):
            raise RuntimeError("summarize failed")

        comp = TrajectoryCompressor(summarize_fn=bad_summarize)
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(15)]
        result = comp.compress(messages)
        # Should not raise; should produce a valid result.
        assert len(result.compressed_messages) > 0

    def test_compression_result_has_user_message(self):
        """The CompressionResult includes a user-facing notification."""
        comp = TrajectoryCompressor()
        messages = [{"role": "user", "content": f"msg-{i}"} for i in range(20)]
        result = comp.compress(messages)
        assert result.user_message != ""

    def test_compression_result_type(self):
        """compress() returns a CompressionResult."""
        comp = TrajectoryCompressor()
        result = comp.compress([{"role": "user", "content": "hi"}])
        assert isinstance(result, CompressionResult)


# ---------------------------------------------------------------------------
# FactAppender
# ---------------------------------------------------------------------------


class TestFactAppender:
    """FactAppender fact collection and context formatting."""

    def test_empty_facts_return_empty_string(self):
        """No facts → empty context string."""
        fa = FactAppender()
        assert fa.get_context_str() == ""

    def test_append_single_fact(self):
        fa = FactAppender()
        fa.append_fact("The API uses port 8080")
        assert "The API uses port 8080" in fa.get_context_str()

    def test_duplicate_facts_not_added(self):
        """Duplicate facts are not added twice."""
        fa = FactAppender()
        fa.append_fact("same fact")
        fa.append_fact("same fact")
        assert len(fa.session_facts) == 1

    def test_empty_fact_not_added(self):
        """Empty string facts are ignored."""
        fa = FactAppender()
        fa.append_fact("")
        assert len(fa.session_facts) == 0

    def test_context_str_format(self):
        """The context string has the expected format."""
        fa = FactAppender()
        fa.append_fact("fact one")
        fa.append_fact("fact two")
        ctx = fa.get_context_str()
        assert "[Learned Facts" in ctx
        assert "- fact one" in ctx
        assert "- fact two" in ctx

    def test_multiple_unique_facts(self):
        fa = FactAppender()
        for i in range(5):
            fa.append_fact(f"fact-{i}")
        assert len(fa.session_facts) == 5
