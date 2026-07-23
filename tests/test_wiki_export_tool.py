"""Tests for wiki_export_tool.py — WikiExportTool.

Covers pure-logic methods and file I/O with temp directories.
Files are written to <project_root>/wiki_exports/ by default.
"""

import os
import tempfile
from unittest.mock import patch

from antigravity_k.tools.wiki_export_tool import WikiExportTool

WIKI_EXPORTS_SUBDIR = "wiki_exports"


def _wiki_dir(tmpdir):
    return os.path.join(tmpdir, WIKI_EXPORTS_SUBDIR)


class TestWikiExportToolInit:
    def test_name(self):
        tool = WikiExportTool()
        assert tool.name == "export_to_wiki"

    def test_description(self):
        tool = WikiExportTool()
        assert "wiki" in tool.description.lower()
        assert "export" in tool.description.lower()

    def test_parameters_schema_has_required_fields(self):
        tool = WikiExportTool()
        schema = tool.parameters_schema
        assert "title" in schema["properties"]
        assert "content" in schema["properties"]
        assert "tags" in schema["properties"]
        assert "filename" in schema["properties"]
        assert schema["required"] == ["title", "content"]


class TestWikiExportToolExecute:
    def test_basic_export(self):
        """Happy path: title + content → file created with frontmatter."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="Test Page", content="Hello world")
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                assert os.path.isdir(wiki_dir)
                md_files = [f for f in os.listdir(wiki_dir) if f.endswith(".md")]
                assert len(md_files) > 0

    def test_export_with_tags(self):
        """Tags should appear in YAML frontmatter."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="Architecture", content="Details", tags=["architecture", "design"])
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                for fname in os.listdir(wiki_dir):
                    if fname.endswith(".md"):
                        with open(os.path.join(wiki_dir, fname)) as f:
                            content = f.read()
                        assert "tags: [architecture, design]" in content
                        assert "title: Architecture" in content
                        break

    def test_export_with_custom_filename(self):
        """Custom filename should be used instead of title-based."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="My Title", content="Stuff", filename="custom_name")
                assert "Successfully exported" in result
                assert "custom_name.md" in result

    def test_export_without_title(self):
        """Empty title should not crash."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="", content="Some content")
                assert "Successfully" in result or "exported" in result

    def test_safe_filename_creation(self):
        """Special chars in title should be sanitized."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="User Guide / FAQ", content="Guide content")
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                for fname in os.listdir(wiki_dir):
                    if fname.endswith(".md"):
                        assert "/" not in fname
                        assert "FAQ" in fname or "User" in fname
                        break

    def test_content_preserved(self):
        """Content should be preserved in the file after frontmatter."""
        tool = WikiExportTool()
        test_content = "# Test\n\nThis is test content with **markdown**."
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="Preserved", content=test_content)
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                for fname in os.listdir(wiki_dir):
                    if fname.endswith(".md"):
                        with open(os.path.join(wiki_dir, fname)) as f:
                            file_content = f.read()
                        assert test_content in file_content
                        break

    def test_date_in_frontmatter(self):
        """Frontmatter should contain a date field."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="Dated", content="Test")
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                for fname in os.listdir(wiki_dir):
                    if fname.endswith(".md"):
                        with open(os.path.join(wiki_dir, fname)) as f:
                            content = f.read()
                        assert "date: " in content
                        assert "---" in content
                        break

    def test_export_to_default_wiki_exports_dir(self):
        """Default wiki_exports directory is created if it doesn't exist."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="Wiki Test", content="Content")
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                assert os.path.isdir(wiki_dir)

    def test_fallback_on_permission_error(self):
        """When writing to wiki_dir fails, should fallback to project_root."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                original_open = open

                class MockWriteCounter:
                    def __init__(self):
                        self.call_count = 0

                    def __call__(self, file, mode="r", **kwargs):
                        self.call_count += 1
                        if self.call_count == 1 and "wiki_exports" in file:
                            raise OSError("Permission denied")
                        return original_open(file, mode, **kwargs)

                mock_writer = MockWriteCounter()
                with patch("builtins.open", mock_writer):
                    result = tool.execute(title="Fallback", content="Test")
                    assert "fallback" in result.lower() or "saved to" in result.lower()

    def test_frontmatter_format(self):
        """Verify correct YAML frontmatter structure."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                tool.execute(title="TestDoc", content="Body", tags=["tag1", "tag2"])
                wiki_dir = _wiki_dir(tmpdir)
                for fname in os.listdir(wiki_dir):
                    if fname.endswith(".md"):
                        with open(os.path.join(wiki_dir, fname)) as f:
                            content = f.read()
                        assert content.startswith("---")
                        assert "title: TestDoc" in content
                        assert "tags: [tag1, tag2]" in content
                        assert "---" in content
                        assert "Body" in content
                        break

    def test_filename_has_date_prefix(self):
        """Filename should start with YYYY-MM-DD_ prefix."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="DatePrefix", content="Test")
                import re

                match = re.search(r"(\d{4}-\d{2}-\d{2}_.*\.md)", result)
                assert match, f"Expected date-prefixed filename in: {result}"

    def test_config_wiki_dir_used(self):
        """When config.yaml has wiki_dir, it should be used."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = os.path.join(tmpdir, "config_wiki")
            os.makedirs(wiki_dir)
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                with open(os.path.join(tmpdir, "config.yaml"), "w") as f:
                    f.write(f"wiki_dir: {wiki_dir}\n")
                result = tool.execute(title="Config Test", content="Data")
                assert wiki_dir in result

    def test_empty_tags(self):
        """Empty tags list should not produce tags in frontmatter."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                tool.execute(title="NoTags", content="Content", tags=[])
                wiki_dir = _wiki_dir(tmpdir)
                for fname in os.listdir(wiki_dir):
                    if fname.endswith(".md"):
                        with open(os.path.join(wiki_dir, fname)) as f:
                            content = f.read()
                        assert "tags:" not in content
                        break

    def test_none_content(self):
        """None content should be handled gracefully (converted to empty string)."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(title="Empty", content=None)
                assert "Successfully exported" in result

    def test_full_pipeline_with_frontmatter_and_content(self):
        """End-to-end: frontmatter + content written correctly."""
        tool = WikiExportTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("antigravity_k.tools.wiki_export_tool.os.getcwd", return_value=tmpdir):
                result = tool.execute(
                    title="Full Pipeline",
                    content="# Section 1\n\nSome text here.\n\n## Section 2\n\nMore text.",
                    tags=["test", "pipeline"],
                    filename="full_test",
                )
                assert "Successfully exported" in result
                wiki_dir = _wiki_dir(tmpdir)
                md_files = [f for f in os.listdir(wiki_dir) if f.endswith(".md")]
                assert len(md_files) > 0
                filepath = os.path.join(wiki_dir, md_files[0])
                with open(filepath) as f:
                    content = f.read()
                assert content.startswith("---")
                assert "title: Full Pipeline" in content
                assert "tags: [test, pipeline]" in content
                assert "# Section 1" in content
                assert "## Section 2" in content
