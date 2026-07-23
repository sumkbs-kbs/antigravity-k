"""Tests for SkillGenerator (skill_generator.py)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from antigravity_k.engine.skill_generator import SkillGenerator


class TestSkillGenerator:
    def test_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            assert gen.project_root == str(tmpdir)
            assert gen._drafts_dir == str(Path(tmpdir) / "_drafts" / "auto_skills")
            assert gen._tools_dir == str(Path(tmpdir) / "src" / "antigravity_k" / "tools")

    def test_generate_skill_llm_fails(self):
        gen = SkillGenerator(project_root="/tmp")
        gen._generate_spec = MagicMock(return_value=None)
        result = gen.generate_skill("parse json")
        assert result["success"] is False
        assert "Failed to generate" in result["message"]

    def test_generate_skill_syntax_error(self):
        gen = SkillGenerator(project_root="/tmp")
        gen._generate_spec = MagicMock(
            return_value={
                "tool_name": "test_tool",
                "class_name": "TestTool",
                "description": "A test tool",
                "tags": ["test"],
                "properties": {},
                "required": [],
                "execute_body": "This is not valid Python",
            }
        )
        result = gen.generate_skill("test")
        assert result["success"] is False

    def test_generate_skill_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            gen._generate_spec = MagicMock(
                return_value={
                    "tool_name": "test_tool",
                    "class_name": "TestTool",
                    "description": "A test tool",
                    "tags": ["test"],
                    "properties": {},
                    "required": [],
                    "execute_body": "return 'hello'",
                }
            )
            result = gen.generate_skill("test")
            assert result["success"] is True
            assert result["class_name"] == "TestTool"
            assert result["tool_name"] == "test_tool"

    def test_approve_skill_not_found(self):
        gen = SkillGenerator(project_root="/tmp")
        result = gen.approve_skill("nonexistent")
        assert result["success"] is False
        assert "Draft not found" in result["message"]

    def test_approve_skill_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(gen._drafts_dir)
            draft_dir.mkdir(parents=True, exist_ok=True)
            draft_file = draft_dir / "auto_skill_good.py"
            draft_file.write_text("x = 1")
            # Create tools dir so shutil.move succeeds
            tools_dir = Path(gen._tools_dir)
            tools_dir.mkdir(parents=True, exist_ok=True)

            result = gen.approve_skill("good")
            assert result["success"] is True

    def test_approve_skill_syntax_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(gen._drafts_dir)
            draft_dir.mkdir(parents=True, exist_ok=True)
            draft_file = draft_dir / "auto_skill_bad.py"
            draft_file.write_text("This is not valid Python @@")

            result = gen.approve_skill("bad")
            assert result["success"] is False

    def test_list_pending_empty(self):
        gen = SkillGenerator(project_root="/tmp/nonexistent")
        assert gen.list_pending() == []

    def test_list_pending_with_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(gen._drafts_dir)
            draft_dir.mkdir(parents=True, exist_ok=True)
            meta = {"tool_name": "parser", "status": "pending_review"}
            (draft_dir / "auto_skill_parser.py.meta.json").write_text(json.dumps(meta))
            pending = gen.list_pending()
            assert len(pending) == 1
            assert pending[0]["tool_name"] == "parser"

    def test_list_pending_approved_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(gen._drafts_dir)
            draft_dir.mkdir(parents=True, exist_ok=True)
            approved = {"tool_name": "t1", "status": "approved"}
            pending = {"tool_name": "t2", "status": "pending_review"}
            (draft_dir / "auto_skill_t1.py.meta.json").write_text(json.dumps(approved))
            (draft_dir / "auto_skill_t2.py.meta.json").write_text(json.dumps(pending))
            result = gen.list_pending()
            assert len(result) == 1
            assert result[0]["tool_name"] == "t2"

    def test_render_code_normalizes_indentation(self):
        gen = SkillGenerator(project_root="/tmp")
        spec = {
            "tool_name": "t",
            "class_name": "T",
            "description": "desc",
            "tags": ["t"],
            "properties": {},
            "required": [],
            "execute_body": "result = some_function()\nreturn result",
        }
        code = gen._render_code(spec)
        assert "result = some_function()" in code
        assert "        result" in code  # 8-space indented
