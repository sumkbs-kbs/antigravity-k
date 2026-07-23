"""Tests for AgentTracer (tracing.py)."""

import json
import tempfile
from pathlib import Path

import pytest

from antigravity_k.engine.tracing import (
    AgentTracer,
    Span,
    Trace,
    get_tracer,
    traced,
)


class TestSpan:
    def test_span_creation(self):
        span = Span(name="test_span", span_type="tool_call")
        assert span.span_id
        assert span.name == "test_span"
        assert span.span_type == "tool_call"
        assert span.status == "ok"
        assert span.duration_ms == 0.0

    def test_set_output_string(self):
        span = Span(name="test")
        span.set_output("hello world")
        assert span.output_data["text"] == "hello world"

    def test_set_output_dict(self):
        span = Span(name="test")
        span.set_output({"key": "value"})
        assert span.output_data["key"] == "value"

    def test_set_output_other(self):
        span = Span(name="test")
        span.set_output(42)
        assert span.output_data["value"] == "42"

    def test_set_error(self):
        span = Span(name="test")
        span.set_error(ValueError("bad value"))
        assert span.status == "error"
        assert "ValueError" in span.error_message

    def test_finish(self):
        import time

        span = Span(name="test", start_time=time.time() - 0.5)
        span.finish()
        assert span.duration_ms > 0
        assert span.end_time > 0

    def test_to_dict(self):
        span = Span(name="test", span_type="llm", token_count=100)
        d = span.to_dict()
        assert d["name"] == "test"
        assert d["type"] == "llm"
        assert d["token_count"] == 100


class TestTrace:
    def test_trace_creation(self):
        trace = Trace(query="test query")
        assert trace.trace_id
        assert trace.query == "test query"
        assert trace.spans == []

    def test_add_span_updates_aggregates(self):
        trace = Trace()
        span = Span(name="tool1", span_type="tool_call", token_count=50)
        trace.add_span(span)
        assert len(trace.spans) == 1
        assert trace.total_tokens == 50
        assert trace.tool_calls == 1

    def test_add_span_counts_errors(self):
        trace = Trace()
        span = Span(name="err", status="error")
        trace.add_span(span)
        assert trace.errors == 1

    def test_finish_calculates_duration(self):
        import time

        trace = Trace(started_at=time.time() - 1.0)
        trace.finish()
        assert trace.total_duration_ms > 0

    def test_to_dict(self):
        trace = Trace(query="q")
        trace.add_span(Span(name="s1"))
        trace.finish()
        d = trace.to_dict()
        assert "trace_id" in d
        assert "spans" in d
        assert len(d["spans"]) == 1

    def test_summary(self):
        trace = Trace(query="test")
        trace.add_span(Span(name="tool", span_type="tool_call"))
        trace.finish()
        s = trace.summary()
        assert "Trace" in s
        assert "Spans:" in s


class TestAgentTracer:
    def test_init(self):
        tracer = AgentTracer()
        assert tracer._traces == []
        assert tracer._active_trace is None

    def test_init_with_persist_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            AgentTracer(persist_dir=tmpdir)
            assert Path(tmpdir).exists()

    def test_start_trace(self):
        tracer = AgentTracer()
        trace = tracer.start_trace("hello")
        assert trace.query == "hello"
        assert tracer._active_trace is trace

    def test_end_trace(self):
        tracer = AgentTracer()
        tracer.start_trace("hello")
        trace = tracer.end_trace()
        assert trace is not None
        assert trace.query == "hello"
        assert tracer._active_trace is None
        assert len(tracer._traces) == 1

    def test_end_trace_no_active(self):
        tracer = AgentTracer()
        assert tracer.end_trace() is None

    def test_span_context_manager(self):
        tracer = AgentTracer()
        tracer.start_trace("test")
        with tracer.span("my_span", {"key": "val"}, span_type="llm") as s:
            assert s.name == "my_span"
            s.set_output("done")
        assert len(tracer._traces) == 0  # not ended yet
        trace = tracer.end_trace()
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "my_span"

    def test_span_context_manager_error(self):
        tracer = AgentTracer()
        tracer.start_trace("test")
        with pytest.raises(ValueError):
            with tracer.span("failing"):
                raise ValueError("oops")
        trace = tracer.end_trace()
        assert trace.spans[0].status == "error"

    def test_start_end_span_manual(self):
        tracer = AgentTracer()
        tracer.start_trace("test")
        s = tracer.start_span("manual", span_type="tool_call")
        assert s.name == "manual"
        tracer.end_span(s)
        trace = tracer.end_trace()
        assert len(trace.spans) == 1

    def test_get_recent_traces(self):
        tracer = AgentTracer()
        assert tracer.get_recent_traces() == []
        tracer.start_trace("q1")
        tracer.end_trace()
        assert len(tracer.get_recent_traces(5)) == 1

    def test_get_performance_stats_empty(self):
        tracer = AgentTracer()
        stats = tracer.get_performance_stats()
        assert "message" in stats

    def test_get_performance_stats_with_data(self):
        tracer = AgentTracer()
        tracer.start_trace("q")
        tracer.end_trace()
        stats = tracer.get_performance_stats()
        assert stats["total_traces"] == 1

    def test_export_jsonl(self):
        tracer = AgentTracer()
        tracer.start_trace("q")
        tracer.end_trace()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            tracer.export_jsonl(f.name)
            content = Path(f.name).read_text()
            assert content.strip()
            json.loads(content)  # valid JSON

    def test_max_traces_enforced(self):
        tracer = AgentTracer(max_traces=2)
        for i in range(5):
            tracer.start_trace(f"q{i}")
            tracer.end_trace()
        assert len(tracer._traces) == 2


class TestTracedDecorator:
    def test_sync_wrapper(self):
        tracer = AgentTracer()
        tracer.start_trace("test")

        @traced(tracer, span_type="tool_call")
        def my_func(x: int) -> int:
            return x * 2

        result = my_func(5)
        assert result == 10
        trace = tracer.end_trace()
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "my_func"

    def test_traced_with_custom_name(self):
        tracer = AgentTracer()
        tracer.start_trace("test")

        @traced(tracer, name="custom_name")
        def foo():
            return "ok"

        assert foo() == "ok"
        trace = tracer.end_trace()
        assert trace.spans[0].name == "custom_name"


class TestGetTracer:
    def test_get_tracer_singleton(self):
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2
