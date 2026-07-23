"""Tests for failure_memory — FailureMemory.

Covers __init__, record, _extract_pattern, _is_similar, find_similar,
build_prompt, get_session_stats, _rotate_log_if_needed.
"""

from __future__ import annotations

import json
import os

from antigravity_k.engine.failure_memory import FailureMemory


class TestInit:
    def test_default_log_path(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        expected = os.path.join(str(tmp_path), ".antigravity", "failure_log.jsonl")
        assert fm._log_path == expected
        assert os.path.exists(os.path.dirname(expected))

    def test_session_failures_empty(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        assert fm._session_failures == []


class TestExtractPattern:
    def test_python_error_type(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        pattern = fm._extract_pattern("ValueError: invalid literal for int()")
        assert "ValueError" in pattern

    def test_command_not_found(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        assert fm._extract_pattern("bash: command not found: foo") == "command_not_found"

    def test_permission_denied(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        assert fm._extract_pattern("Permission denied") == "permission_denied"

    def test_file_not_found(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        assert fm._extract_pattern("No such file or directory: 'test.txt'") == "file_not_found"

    def test_generic_error_first_line(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        pattern = fm._extract_pattern("Something went wrong\nDetails here")
        assert pattern == "Something went wrong"


class TestIsSimilar:
    def test_overlap_above_threshold(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        entry = {"tool": "web_search", "error_pattern": "timeout_error", "args_summary": "search query"}
        keywords = {"query", "search", "error"}
        assert fm._is_similar(entry, keywords) is True

    def test_overlap_below_threshold(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        entry = {"tool": "web_search", "error_pattern": "timeout_error", "args_summary": "search query"}
        keywords = {"unrelated", "words"}
        assert fm._is_similar(entry, keywords) is False


class TestRecord:
    def test_records_to_session(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        fm.record(tool="web_search", error_text="TimeoutError: connection timeout")
        assert len(fm._session_failures) == 1
        assert fm._session_failures[0]["tool"] == "web_search"
        assert fm._session_failures[0]["error_pattern"] == "TimeoutError: connection timeout"

    def test_records_to_jsonl(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        fm.record(tool="read_file", error_text="FileNotFoundError: missing.txt")
        assert os.path.exists(fm._log_path)
        with open(fm._log_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["tool"] == "read_file"


class TestBuildPrompt:
    def test_no_similar_returns_empty(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        from unittest.mock import patch

        with patch("antigravity_k.engine.failure_memory.global_gbrain.search_semantic", return_value=[]):
            result = fm.build_prompt("zzz_unique_nonexistent_keyword_xyz")
            assert result == ""

    def test_with_similar_returns_prompt(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        from unittest.mock import patch

        with patch("antigravity_k.engine.failure_memory.global_gbrain.search_semantic", return_value=[]):
            fm._session_failures.clear()
            fm.record(
                tool="web_search",
                error_text="connection timeout: server TimeoutError",
                fix_applied="retry with delay",
                success_after_fix=True,
            )
            result = fm.build_prompt("connection timeout")
            assert "<failure_memory>" in result


class TestGetSessionStats:
    def test_empty_returns_zero(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        stats = fm.get_session_stats()
        assert stats["total"] == 0
        assert stats["unique_tools"] == 0
        assert stats["fixed"] == 0

    def test_with_failures(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        fm.record(tool="web_search", error_text="timeout")
        fm.record(tool="file_tools", error_text="not found", success_after_fix=True)
        fm.record(tool="web_search", error_text="another timeout")
        stats = fm.get_session_stats()
        assert stats["total"] == 3
        assert stats["unique_tools"] == 2
        assert stats["fixed"] == 1


class TestRotateLog:
    def test_rotate_log_truncates(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        with open(fm._log_path, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(json.dumps({"i": i}, ensure_ascii=False) + "\n")
        fm._rotate_log_if_needed(max_lines=50, keep_lines=20)
        with open(fm._log_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 20

    def test_rotate_under_threshold_does_nothing(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        with open(fm._log_path, "w", encoding="utf-8") as f:
            f.write("line1\nline2\n")
        fm._rotate_log_if_needed(max_lines=50, keep_lines=20)
        with open(fm._log_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2


class TestFindSimilar:
    def test_find_similar_from_session(self, tmp_path):
        fm = FailureMemory(project_root=str(tmp_path))
        fm.record(tool="web_search", error_text="timeout_error on web search")
        results = fm.find_similar("search web error", max_results=3)
        assert len(results) >= 1
        assert results[0]["tool"] == "web_search"
