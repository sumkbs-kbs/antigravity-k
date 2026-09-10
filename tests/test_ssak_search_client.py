"""Tests for Ssak-Search client and agent tool."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

from antigravity_k.tools.ssak_search_client import (
    SsakHit,
    _refine_query,
    grounded_answer,
    grounded_context,
    search,
)
from antigravity_k.tools.ssak_search_tool import SsakSearchTool


def test_refine_query_strips_fillers() -> None:
    assert _refine_query("what is python asyncio?") == "python asyncio"
    assert _refine_query("how to implement quicksort in rust") == "quicksort in rust"
    assert _refine_query("plain query") == "plain query"


def test_search_parses_results_successfully() -> None:
    mock_payload = {
        "results": [
            {
                "title": "FastAPI Guide",
                "url": "https://fastapi.tiangolo.com",
                "content": "FastAPI framework, high performance, easy to learn.",
                "score": 0.95,
                "domain": "fastapi.tiangolo.com",
            },
            {
                "title": "Python Docs",
                "url": "https://docs.python.org",
                "content": "Python 3.13 documentation.",
                "score": 0.88,
                "domain": "docs.python.org",
            },
        ]
    }
    raw_bytes = json.dumps(mock_payload).encode("utf-8")
    mock_resp = io.BytesIO(raw_bytes)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        hits = search("fastapi tutorial", max_results=2)

    assert len(hits) == 2
    assert hits[0].title == "FastAPI Guide"
    assert hits[0].score == 0.95
    assert hits[1].domain == "docs.python.org"


def test_search_handles_network_error_gracefully() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("Network down")):
        hits = search("any query")
    assert hits == []


def test_grounded_context_formats_hits() -> None:
    fake_hits = [
        SsakHit(title="Doc 1", url="https://example.com/1", content="Content 1", score=0.9, domain="example.com"),
        SsakHit(title="Doc 2", url="https://example.com/2", content="Content 2", score=0.8, domain="example.com"),
    ]
    with patch("antigravity_k.tools.ssak_search_client.search", return_value=fake_hits):
        ctx = grounded_context("test query")

    assert "Web search results for: test query" in ctx
    assert "[1] Doc 1" in ctx
    assert "https://example.com/1" in ctx
    assert "[2] Doc 2" in ctx


def test_grounded_answer_invokes_generate() -> None:
    fake_hits = [
        SsakHit(
            title="Release Notes",
            url="https://pkg.org/notes",
            content="Version 2.0 released",
            score=0.9,
            domain="pkg.org",
        ),
    ]
    mock_gen = MagicMock(return_value="The latest version is 2.0 based on [1].")

    with patch("antigravity_k.tools.ssak_search_client.search", return_value=fake_hits):
        answer, hits = grounded_answer("what is the latest version", mock_gen, "qwen3.6:latest")

    assert "2.0" in answer
    assert len(hits) == 1
    mock_gen.assert_called_once()
    assert "Reference:" in mock_gen.call_args.kwargs["prompt"]


def test_ssak_search_tool_execution() -> None:
    tool = SsakSearchTool()
    assert tool.name == "ssak_search"

    # Empty query check
    res_empty = json.loads(tool.execute(query=""))
    assert "error" in res_empty

    # Normal search
    fake_hits = [
        SsakHit(title="Result", url="https://test.com", content="Test content", score=0.85, domain="test.com"),
    ]
    with patch("antigravity_k.tools.ssak_search_tool.search", return_value=fake_hits):
        res_raw = tool.execute(query="test keyword", max_results=3)
        res = json.loads(res_raw)

    assert res["count"] == 1
    assert res["results"][0]["title"] == "Result"
