"""Tests for the hashline_tools module."""

import tempfile
from pathlib import Path

from antigravity_k.tools.hashline_tools import (
    HashlineEditTool,
    MultiReplaceFileContentTool,
    ReadHashFileTool,
    compute_line_hash,
)


class TestComputeLineHash:
    def test_returns_4_upper_chars(self):
        h = compute_line_hash("hello world")
        assert isinstance(h, str)
        assert len(h) == 4
        assert h == h.upper()

    def test_different_lines_different_hashes(self):
        h1 = compute_line_hash("line one")
        h2 = compute_line_hash("line two")
        assert h1 != h2

    def test_same_line_same_hash(self):
        assert compute_line_hash("test") == compute_line_hash("test")


class TestReadHashFileTool:
    def test_properties(self):
        tool = ReadHashFileTool()
        assert tool.name == "read_hash_file"
        assert "hash" in tool.description
        assert "file_path" in tool.parameters_schema["required"]

    def test_execute_file_not_found(self):
        tool = ReadHashFileTool()
        result = tool.execute(file_path="/nonexistent/file_xyz.txt")
        assert "Error" in result
        assert "not found" in result

    def test_execute_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("line1\nline2\nline3\n")

            tool = ReadHashFileTool()
            result = tool.execute(file_path=str(fpath))
            assert "1#" in result
            assert "2#" in result
            assert "3#" in result
            assert "line1" in result
            assert "line2" in result
            assert "line3" in result

    def test_execute_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "empty.txt"
            fpath.write_text("")

            tool = ReadHashFileTool()
            result = tool.execute(file_path=str(fpath))
            assert result == ""

    def test_execute_exception(self):
        tool = ReadHashFileTool()
        result = tool.execute(file_path="")
        assert "Error" in result


class TestHashlineEditTool:
    def test_properties(self):
        tool = HashlineEditTool()
        assert tool.name == "hashline_edit"
        assert "hash" in tool.description
        required = tool.parameters_schema["required"]
        assert "file_path" in required
        assert "line_number" in required
        assert "expected_hash" in required
        assert "replacement_text" in required

    def test_file_not_found(self):
        tool = HashlineEditTool()
        result = tool.execute(file_path="/nonexistent.txt")
        assert "Error" in result

    def test_missing_line_number(self):
        tool = HashlineEditTool()
        result = tool.execute(file_path="/tmp")
        assert "line_number" in result

    def test_line_out_of_bounds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("line1\n")

            tool = HashlineEditTool()
            result = tool.execute(file_path=str(fpath), line_number=999, expected_hash="AAAA", replacement_text="new")
            assert "out of bounds" in result

    def test_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("original line\n")

            tool = HashlineEditTool()
            result = tool.execute(
                file_path=str(fpath), line_number=1, expected_hash="ZZZZ", replacement_text="new line"
            )
            assert "Hash mismatch" in result

    def test_successful_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("original line\n")

            line_hash = compute_line_hash("original line")
            tool = HashlineEditTool()
            result = tool.execute(
                file_path=str(fpath), line_number=1, expected_hash=line_hash, replacement_text="new line"
            )
            assert "Successfully" in result
            assert fpath.read_text() == "new line\n"

    def test_successful_replace_no_newline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("original line")

            line_hash = compute_line_hash("original line")
            tool = HashlineEditTool()
            result = tool.execute(
                file_path=str(fpath), line_number=1, expected_hash=line_hash, replacement_text="new line"
            )
            assert "Successfully" in result
            assert fpath.read_text() == "new line"


class TestMultiReplaceFileContentTool:
    def test_properties(self):
        tool = MultiReplaceFileContentTool()
        assert tool.name == "multi_replace_file_content"
        assert tool.parameters_schema["required"] == ["TargetFile", "ReplacementChunks"]

    def test_file_not_found(self):
        tool = MultiReplaceFileContentTool()
        result = tool.execute(TargetFile="/nonexistent.txt")
        assert "Error" in result

    def test_successful_single_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("hello foo world\n")

            tool = MultiReplaceFileContentTool()
            result = tool.execute(
                TargetFile=str(fpath),
                ReplacementChunks=[
                    {
                        "StartLine": 1,
                        "EndLine": 1,
                        "TargetContent": "foo",
                        "ReplacementContent": "bar",
                    }
                ],
            )
            assert "Successfully" in result
            assert fpath.read_text() == "hello bar world\n"

    def test_successful_multi_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("aaa\nbbb\nccc\n")

            tool = MultiReplaceFileContentTool()
            result = tool.execute(
                TargetFile=str(fpath),
                ReplacementChunks=[
                    {"StartLine": 1, "EndLine": 1, "TargetContent": "aaa", "ReplacementContent": "xxx"},
                    {"StartLine": 3, "EndLine": 3, "TargetContent": "ccc", "ReplacementContent": "zzz"},
                ],
            )
            assert "Successfully" in result
            assert "2" in result
            content = fpath.read_text()
            assert "xxx" in content
            assert "zzz" in content
            assert "bbb" in content

    def test_target_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "test.txt"
            fpath.write_text("hello world\n")

            tool = MultiReplaceFileContentTool()
            result = tool.execute(
                TargetFile=str(fpath),
                ReplacementChunks=[
                    {
                        "StartLine": 1,
                        "EndLine": 1,
                        "TargetContent": "nonexistent_content_xyz",
                        "ReplacementContent": "bar",
                    }
                ],
            )
            assert "not found" in result
