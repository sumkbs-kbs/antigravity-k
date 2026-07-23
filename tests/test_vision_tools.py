"""Tests for the vision_tools module."""

import os
import tempfile
from pathlib import Path

from antigravity_k.tools.vision_tools import GenerateImageTool


class TestGenerateImageTool:
    def test_properties(self):
        tool = GenerateImageTool(project_root="/tmp")
        assert tool.name == "generate_image"
        assert "image" in tool.description.lower()
        required = tool.parameters_schema["required"]
        assert "image_name" in required
        assert "prompt" in required

    def test_execute_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = GenerateImageTool(project_root=tmpdir)
            result = tool.execute(image_name="test.png", prompt="a cat")
            assert "test.png" in result
            assert "a cat" in result
            assert os.path.exists(os.path.join(tmpdir, "artifacts"))

    def test_execute_missing_image_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = GenerateImageTool(project_root=tmpdir)
            result = tool.execute(prompt="test")
            assert "IMAGE" in result
            assert "test" in result
            assert os.path.exists(os.path.join(tmpdir, "artifacts"))

    def test_execute_missing_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = GenerateImageTool(project_root=tmpdir)
            tool.execute(image_name="img.png")
            assert os.path.exists(os.path.join(tmpdir, "artifacts"))

    def test_execute_directory_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = Path(tmpdir) / "artifacts"
            artifacts.mkdir()
            (artifacts / "existing.txt").write_text("x")

            tool = GenerateImageTool(project_root=tmpdir)
            result = tool.execute(image_name="new.png", prompt="test")
            assert "new.png" in result
            assert artifacts.exists()
