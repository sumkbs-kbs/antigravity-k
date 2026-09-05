"""Tests for SkillGenerator (skill_generator.py)."""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

from antigravity_k.engine.skill_generator import SkillGenerator, SkillResult
from antigravity_k.tools.self_evolution_tool import SelfEvolutionTool


def _result_map(result: SkillResult) -> dict[str, object]:
    return cast(dict[str, object], cast(object, result))


def _private_value(instance: object, name: str) -> object:
    return cast(object, getattr(instance, name))


def _none_spec(_requirement: str) -> None:
    return None


def _syntax_spec(_requirement: str) -> dict[str, object]:
    return {
        "tool_name": "test_tool",
        "class_name": "TestTool",
        "description": "A test tool",
        "tags": ["test"],
        "properties": {},
        "required": [],
        "execute_body": "This is not valid Python",
    }


def _success_spec(_requirement: str) -> dict[str, object]:
    return {
        "tool_name": "test_tool",
        "class_name": "TestTool",
        "description": "A test tool",
        "tags": ["test"],
        "properties": {},
        "required": [],
        "execute_body": "return 'hello'",
    }


class _RecordingManager:
    def __init__(self, response: str, target: str) -> None:
        self.response: str = response
        self.target: str = target
        self.role_calls: list[tuple[str, str]] = []
        self.generate_calls: list[tuple[str, str, int, float]] = []

    def get_target_for_role(self, role: str, *, default_role: str) -> str | None:
        self.role_calls.append((role, default_role))
        return self.target

    def generate(
        self,
        prompt: str,
        target: str,
        **kwargs: object,
    ) -> str:
        self.generate_calls.append(
            (
                prompt,
                target,
                cast(int, kwargs.get("max_tokens")),
                cast(float, kwargs.get("temperature")),
            )
        )
        return self.response


class TestSkillGenerator:
    def test_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            assert gen.project_root == str(tmpdir)
            assert cast(str, _private_value(gen, "_drafts_dir")) == str(Path(tmpdir) / "_drafts" / "auto_skills")
            assert cast(str, _private_value(gen, "_tools_dir")) == str(Path(tmpdir) / "src" / "antigravity_k" / "tools")

    def test_generate_skill_llm_fails(self):
        gen = SkillGenerator(project_root="/tmp")
        setattr(gen, "_generate_spec", _none_spec)
        result = _result_map(gen.generate_skill("parse json"))
        assert result["success"] is False
        assert "Failed to generate" in cast(str, result["message"])

    def test_generate_skill_syntax_error(self):
        gen = SkillGenerator(project_root="/tmp")
        setattr(gen, "_generate_spec", _syntax_spec)
        result = _result_map(gen.generate_skill("test"))
        assert result["success"] is False

    def test_generate_skill_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            setattr(gen, "_generate_spec", _success_spec)
            result = _result_map(gen.generate_skill("test"))
            assert result["success"] is True
            assert result["class_name"] == "TestTool"
            assert result["tool_name"] == "test_tool"

    def test_approve_skill_not_found(self):
        gen = SkillGenerator(project_root="/tmp")
        result = _result_map(gen.approve_skill("nonexistent"))
        assert result["success"] is False
        assert "Draft not found" in cast(str, result["message"])

    def test_approve_skill_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(cast(str, _private_value(gen, "_drafts_dir")))
            draft_dir.mkdir(parents=True, exist_ok=True)
            draft_file = draft_dir / "auto_skill_good.py"
            _ = draft_file.write_text("x = 1")
            # Create tools dir so shutil.move succeeds
            tools_dir = Path(cast(str, _private_value(gen, "_tools_dir")))
            tools_dir.mkdir(parents=True, exist_ok=True)

            result = _result_map(gen.approve_skill("good"))
            assert result["success"] is True

    def test_approve_skill_syntax_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(cast(str, _private_value(gen, "_drafts_dir")))
            draft_dir.mkdir(parents=True, exist_ok=True)
            draft_file = draft_dir / "auto_skill_bad.py"
            _ = draft_file.write_text("This is not valid Python @@")

            result = _result_map(gen.approve_skill("bad"))
            assert result["success"] is False

    def test_list_pending_empty(self):
        gen = SkillGenerator(project_root="/tmp/nonexistent")
        assert gen.list_pending() == []

    def test_list_pending_with_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(cast(str, _private_value(gen, "_drafts_dir")))
            draft_dir.mkdir(parents=True, exist_ok=True)
            meta = {"tool_name": "parser", "status": "pending_review"}
            _ = (draft_dir / "auto_skill_parser.py.meta.json").write_text(json.dumps(meta))
            pending = gen.list_pending()
            assert len(pending) == 1
            assert pending[0]["tool_name"] == "parser"

    def test_list_pending_approved_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = SkillGenerator(project_root=tmpdir)
            draft_dir = Path(cast(str, _private_value(gen, "_drafts_dir")))
            draft_dir.mkdir(parents=True, exist_ok=True)
            approved = {"tool_name": "t1", "status": "approved"}
            pending = {"tool_name": "t2", "status": "pending_review"}
            _ = (draft_dir / "auto_skill_t1.py.meta.json").write_text(json.dumps(approved))
            _ = (draft_dir / "auto_skill_t2.py.meta.json").write_text(json.dumps(pending))
            result = gen.list_pending()
            assert len(result) == 1
            assert result[0]["tool_name"] == "t2"

    def test_render_code_normalizes_indentation(self):
        gen = SkillGenerator(project_root="/tmp")
        spec: dict[str, object] = {
            "tool_name": "t",
            "class_name": "T",
            "description": "desc",
            "tags": ["t"],
            "properties": {},
            "required": [],
            "execute_body": "result = some_function()\nreturn result",
        }
        render_code = cast(Callable[[dict[str, object]], str], _private_value(gen, "_render_code"))
        code = render_code(spec)
        assert "result = some_function()" in code
        assert "        result" in code  # 8-space indented

    def test_generate_spec_uses_managed_model_target(self):
        manager = _RecordingManager(
            '{"tool_name":"managed_tool","class_name":"ManagedTool"}',
            "local-code-combo",
        )
        gen = SkillGenerator(project_root="/tmp", model_manager=manager)

        result = _result_map(gen.generate_skill("managed generation"))

        assert result["success"] is True
        assert manager.role_calls == [("skill_generator", "code")]
        assert len(manager.generate_calls) == 1
        assert manager.generate_calls[0][1:] == ("local-code-combo", 1024, 0.4)

    def test_self_evolution_uses_managed_model_target_for_patches(self):
        manager = _RecordingManager('{"engine.py":"print(1)"}', "local-code-model")
        tool = SelfEvolutionTool(model_manager=manager)

        generate_patches = cast(
            Callable[[str, dict[str, str], str], dict[str, str]],
            _private_value(tool, "_generate_patches"),
        )
        result = generate_patches("improve", {"engine.py": "print(0)"}, "")

        assert result == {"engine.py": "print(1)"}
        assert manager.role_calls == [("self_evolution", "code")]
        assert len(manager.generate_calls) == 1
        assert manager.generate_calls[0][1:] == ("local-code-model", 4096, 0.3)
