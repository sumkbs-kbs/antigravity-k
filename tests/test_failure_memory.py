"""Tests for failure_memory — FailureMemory.

Covers __init__, record, _extract_pattern, _is_similar, find_similar,
build_prompt, get_session_stats, _rotate_log_if_needed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from antigravity_k.engine.failure_memory import FailureMemory


def _new_memory(tmp_path: Path) -> FailureMemory:
    return FailureMemory(project_root=str(tmp_path))


def _log_path(memory: FailureMemory) -> str:
    return cast(str, getattr(memory, "_log_path"))


def _session_failures(memory: FailureMemory) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], getattr(memory, "_session_failures"))


def _extract_pattern(memory: FailureMemory, text: str) -> str:
    callback = cast(Callable[[str], object], getattr(memory, "_extract_pattern"))
    return cast(str, callback(text))


def _is_similar(memory: FailureMemory, entry: Mapping[str, object], keywords: set[str]) -> bool:
    callback = cast(Callable[[Mapping[str, object], set[str]], object], getattr(memory, "_is_similar"))
    return bool(callback(entry, keywords))


def _rotate_log(memory: FailureMemory, *, max_lines: int, keep_lines: int) -> None:
    callback = cast(Callable[..., object], getattr(memory, "_rotate_log_if_needed"))
    _ = callback(max_lines=max_lines, keep_lines=keep_lines)


def _json_mapping(text: str) -> Mapping[str, object]:
    return cast(Mapping[str, object], cast(object, json.loads(text)))


class TestInit:
    def test_default_log_path(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        expected = os.path.join(str(tmp_path), ".antigravity", "failure_log.jsonl")
        assert _log_path(fm) == expected
        assert os.path.exists(os.path.dirname(expected))

    def test_session_failures_empty(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        assert _session_failures(fm) == []


class TestExtractPattern:
    def test_python_error_type(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        pattern = _extract_pattern(fm, "ValueError: invalid literal for int()")
        assert "ValueError" in pattern

    def test_command_not_found(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        assert _extract_pattern(fm, "bash: command not found: foo") == "command_not_found"

    def test_permission_denied(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        assert _extract_pattern(fm, "Permission denied") == "permission_denied"

    def test_file_not_found(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        assert _extract_pattern(fm, "No such file or directory: 'test.txt'") == "file_not_found"

    def test_generic_error_first_line(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        pattern = _extract_pattern(fm, "Something went wrong\nDetails here")
        assert pattern == "Something went wrong"


class TestIsSimilar:
    def test_overlap_above_threshold(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        entry = {"tool": "web_search", "error_pattern": "timeout_error", "args_summary": "search query"}
        keywords = {"query", "search", "error"}
        assert _is_similar(fm, entry, keywords) is True

    def test_overlap_below_threshold(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        entry = {"tool": "web_search", "error_pattern": "timeout_error", "args_summary": "search query"}
        keywords = {"unrelated", "words"}
        assert _is_similar(fm, entry, keywords) is False


class TestRecord:
    def test_records_to_session(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        fm.record(tool="web_search", error_text="TimeoutError: connection timeout")
        assert len(_session_failures(fm)) == 1
        assert _session_failures(fm)[0]["tool"] == "web_search"
        assert _session_failures(fm)[0]["error_pattern"] == "TimeoutError: connection timeout"

    def test_records_to_jsonl(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        fm.record(tool="read_file", error_text="FileNotFoundError: missing.txt")
        assert os.path.exists(_log_path(fm))
        with open(_log_path(fm), encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = _json_mapping(lines[0])
        assert data["tool"] == "read_file"


class TestBuildPrompt:
    def test_no_similar_returns_empty(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        from unittest.mock import patch

        with patch("antigravity_k.engine.failure_memory.global_gbrain.search_semantic", return_value=[]):
            result = fm.build_prompt("zzz_unique_nonexistent_keyword_xyz")
            assert result == ""

    def test_with_similar_returns_prompt(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        from unittest.mock import patch

        with patch("antigravity_k.engine.failure_memory.global_gbrain.search_semantic", return_value=[]):
            _session_failures(fm).clear()
            fm.record(
                tool="web_search",
                error_text="connection timeout: server TimeoutError",
                fix_applied="retry with delay",
                success_after_fix=True,
            )
            result = fm.build_prompt("connection timeout")
            assert "<failure_memory>" in result


class TestGetSessionStats:
    def test_empty_returns_zero(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        stats = fm.get_session_stats()
        assert stats["total"] == 0
        assert stats["unique_tools"] == 0
        assert stats["fixed"] == 0

    def test_with_failures(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        fm.record(tool="web_search", error_text="timeout")
        fm.record(tool="file_tools", error_text="not found", success_after_fix=True)
        fm.record(tool="web_search", error_text="another timeout")
        stats = fm.get_session_stats()
        assert stats["total"] == 3
        assert stats["unique_tools"] == 2
        assert stats["fixed"] == 1


class TestRotateLog:
    def test_rotate_log_truncates(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        with open(_log_path(fm), "w", encoding="utf-8") as f:
            for i in range(100):
                _ = f.write(json.dumps({"i": i}, ensure_ascii=False) + "\n")
        _rotate_log(fm, max_lines=50, keep_lines=20)
        with open(_log_path(fm), encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 20

    def test_rotate_under_threshold_does_nothing(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        with open(_log_path(fm), "w", encoding="utf-8") as f:
            _ = f.write("line1\nline2\n")
        _rotate_log(fm, max_lines=50, keep_lines=20)
        with open(_log_path(fm), encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2


class TestFindSimilar:
    def test_find_similar_from_session(self, tmp_path: Path):
        fm = _new_memory(tmp_path)
        fm.record(tool="web_search", error_text="timeout_error on web search")
        results = fm.find_similar("search web error", max_results=3)
        assert len(results) >= 1
        assert results[0]["tool"] == "web_search"
