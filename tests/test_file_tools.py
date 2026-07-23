"""Tests for FileTools — WriteFileTool, CreateDirectoryTool, EditFileTool, GlobSearchTool, GrepSearchTool."""

import os
import tempfile
from unittest import mock

import pytest

from antigravity_k.tools.file_tools import (
    CreateDirectoryTool,
    EditFileTool,
    GlobSearchTool,
    GrepSearchTool,
    MultiReplaceFileContentTool,
    WriteFileTool,
)

# ─── WriteFileTool ───────────────────────────────────────────────


class TestWriteFileTool:
    def test_name(self):
        assert WriteFileTool().name == "write_file"

    def test_write_new_file(self):
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            result = tool.execute(file_path=path, content="hello world")
            assert "wrote" in result.lower()
            assert os.path.exists(path)
            with open(path) as f:
                assert f.read() == "hello world"

    def test_write_creates_dirs(self):
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub/deep/test.txt")
            result = tool.execute(file_path=path, content="nested")
            assert "wrote" in result.lower()
            assert os.path.exists(path)

    def test_write_overwrites(self):
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            with open(path, "w") as f:
                f.write("old")
            result = tool.execute(file_path=path, content="new")
            assert "wrote" in result.lower()
            with open(path) as f:
                assert f.read() == "new"

    def test_write_error(self):
        tool = WriteFileTool()
        result = tool.execute(file_path="/nonexistent-dir-xyz-123/test.txt", content="test")
        assert "error" in result.lower()


# ─── CreateDirectoryTool ─────────────────────────────────────────


class TestCreateDirectoryTool:
    def test_name(self):
        assert CreateDirectoryTool().name == "create_directory"

    def test_create_new_dir(self):
        tool = CreateDirectoryTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "newdir")
            result = tool.execute(dir_path=path)
            assert "created" in result.lower()
            assert os.path.isdir(path)

    def test_create_existing_dir(self):
        tool = CreateDirectoryTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = tool.execute(dir_path=tmpdir)
            assert "created" in result.lower()

    def test_create_nested(self):
        tool = CreateDirectoryTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a/b/c")
            result = tool.execute(dir_path=path)
            assert "created" in result.lower()
            assert os.path.isdir(path)

    def test_create_error(self):
        tool = CreateDirectoryTool()
        result = tool.execute(dir_path="/root/forbidden-dir-test")
        assert "error" in result.lower()


# ─── EditFileTool ─────────────────────────────────────────────────


class TestEditFileTool:
    @pytest.fixture
    def sample_file(self):
        content = "line1\nline2\nline3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_name(self):
        assert EditFileTool().name == "edit_file"

    def test_file_not_found(self):
        tool = EditFileTool()
        result = tool.execute(file_path="/nonexistent.txt", old_str="hello", new_str="world")
        assert "not found" in result.lower()

    def test_exact_match(self, sample_file):
        tool = EditFileTool()
        tool.execute(file_path=sample_file, old_str="line2", new_str="line2_edited")
        with open(sample_file) as f:
            content = f.read()
        assert "line2_edited" in content

    def test_exact_match_multi_line(self, sample_file):
        tool = EditFileTool()
        tool.execute(
            file_path=sample_file,
            old_str="line1\nline2",
            new_str="line1\nline2_edited",
        )
        with open(sample_file) as f:
            content = f.read()
        assert "line2_edited" in content

    def test_ambiguous_match(self, sample_file):
        tool = EditFileTool()
        with open(sample_file, "w") as f:
            f.write("dup\nmiddle\ndup\n")
        result = tool.execute(file_path=sample_file, old_str="dup", new_str="changed")
        assert "found" in result.lower() and "times" in result.lower()

    def test_no_match_hint(self, sample_file):
        """When old_str has zero similarity to any line, returns base message."""
        tool = EditFileTool()
        result = tool.execute(file_path=sample_file, old_str="nonexistent_text_xyz", new_str="replacement")
        assert "not found" in result.lower()
        assert "verify" in result.lower()

    def test_error_handling(self):
        tool = EditFileTool()
        with mock.patch("builtins.open", side_effect=PermissionError("mocked error")):
            with mock.patch("os.path.exists", return_value=True):
                result = tool.execute(file_path="/fake.txt", old_str="a", new_str="b")
                assert "error" in result.lower()

    def test_fuzzy_whitespace_match(self, sample_file):
        """Fuzzy match handles whitespace differences."""
        tool = EditFileTool()
        tool.execute(
            file_path=sample_file,
            old_str="  line2",  # extra spaces
            new_str="line2_fuzzy",
        )
        with open(sample_file) as f:
            content = f.read()
        assert "line2_fuzzy" in content

    def test_fuzzy_single_line_similarity(self):
        """Fuzzy match with single-line similarity."""
        tool = EditFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("the quick brown fox\njumps over the lazy dog\n")
            path = f.name
        try:
            tool.execute(
                file_path=path,
                old_str="quick brown fox",
                new_str="slow brown fox",
            )
            with open(path) as f2:
                content = f2.read()
            assert "slow brown fox" in content
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ─── MultiReplaceFileContentTool ─────────────────────────────────


class TestMultiReplaceFileContentTool:
    def test_name(self):
        assert MultiReplaceFileContentTool().name == "multi_replace_file_content"

    def test_multi_replace(self):
        tool = MultiReplaceFileContentTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("aaa\nbbb\nccc\n")
            path = f.name
        try:
            result = tool.execute(
                file_path=path,
                ReplacementChunks=[
                    {"TargetContent": "aaa", "ReplacementContent": "AAA"},
                    {"TargetContent": "ccc", "ReplacementContent": "CCC"},
                ],
            )
            assert "applied" in result.lower()
            with open(path) as f:
                content = f.read()
            assert "AAA" in content
            assert "CCC" in content
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        tool = MultiReplaceFileContentTool()
        result = tool.execute(file_path="/nonexistent.txt", ReplacementChunks=[])
        assert "not found" in result.lower()

    def test_chunk_target_not_found(self):
        tool = MultiReplaceFileContentTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("hello\n")
            path = f.name
        try:
            result = tool.execute(
                file_path=path,
                ReplacementChunks=[
                    {"TargetContent": "nonexistent", "ReplacementContent": "world"},
                ],
            )
            assert "not found" in result.lower()
        finally:
            os.unlink(path)


# ─── GlobSearchTool ───────────────────────────────────────────────


class TestGlobSearchTool:
    def test_name(self):
        assert GlobSearchTool().name == "glob_search"

    def test_find_py_files(self):
        tool = GlobSearchTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "test.py"), "w").close()
            open(os.path.join(tmpdir, "test.txt"), "w").close()
            result = tool.execute(pattern="*.py", root=tmpdir)
            assert "test.py" in result
            assert "found" in result.lower()

    def test_no_results(self):
        tool = GlobSearchTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = tool.execute(pattern="*.xyzabc", root=tmpdir)
            assert "no files" in result.lower()

    def test_human_size(self):
        assert GlobSearchTool._human_size(500) == "500B"
        assert GlobSearchTool._human_size(2048) == "2KB"

    def test_error(self):
        tool = GlobSearchTool()
        result = tool.execute(pattern="**/*", root="/nonexistent-path-xyz")
        assert "error" in result.lower() or "no files" in result.lower()


# ─── GrepSearchTool ───────────────────────────────────────────────


class TestGrepSearchTool:
    def test_name(self):
        assert GrepSearchTool().name == "grep_search"

    def test_text_search(self):
        tool = GrepSearchTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            with open(path, "w") as f:
                f.write("def foo(): pass\n# bar\n")
            result = tool.execute(query="foo", path=tmpdir, include="*.py")
            assert "foo" in result
            assert "found" in result.lower()

    def test_regex_search(self):
        tool = GrepSearchTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("error_123\nwarning_456\n")
            path = f.name
        try:
            result = tool.execute(query=r"error_\d+", path=path, is_regex=True)
            assert "error_123" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_no_match(self):
        tool = GrepSearchTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.py")
            with open(path, "w") as f:
                f.write("hello world\n")
            result = tool.execute(query="nonexistent", path=tmpdir, include="*.py")
            assert "no matches" in result.lower()

    def test_single_file(self):
        tool = GrepSearchTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("target_text\n")
            path = f.name
        try:
            result = tool.execute(query="target_text", path=path)
            assert "target_text" in result
            assert "found" in result.lower()
        finally:
            os.unlink(path)

    def test_empty_query(self):
        tool = GrepSearchTool()
        result = tool.execute(query="")
        assert "error" in result.lower()

    def test_invalid_regex(self):
        tool = GrepSearchTool()
        result = tool.execute(query=r"[invalid", is_regex=True)
        assert "error" in result.lower() or "invalid" in result.lower()
