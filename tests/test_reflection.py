"""Tests for ReflectionAgent (reflection.py)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, final
from unittest.mock import MagicMock, patch

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.reflection import ReflectionAgent


@dataclass(frozen=True)
class _ProcessResult:
    stdout: str
    stderr: str
    returncode: int


@final
class _ModelManagerDouble:
    response: str

    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str, *, target: str, model_id: str) -> str:
        _ = (prompt, target, model_id)
        return self.response


def _agent_with_response(response: str) -> ReflectionAgent:
    manager = cast(ModelManager, cast(object, _ModelManagerDouble(response)))
    return ReflectionAgent("/tmp/test_project", manager)


def _synthesize_skill(agent: ReflectionAgent, description: str) -> None:
    synthesizer = cast(Callable[[str], object], getattr(agent, "_synthesize_skill"))
    _ = synthesizer(description)


def _git_run(*_args: object, **_kwargs: object) -> _ProcessResult:
    return _ProcessResult(
        stdout="diff --git a/file.py b/file.py\n+new code",
        stderr="",
        returncode=0,
    )


class TestReflectionAgent:
    def test_init(self):
        model_manager = MagicMock()
        agent = ReflectionAgent("/tmp/test_project", model_manager)
        assert agent.project_root == "/tmp/test_project"
        assert agent.model_manager == model_manager

    def test_reflect_no_diff(self):
        model_manager = MagicMock()
        agent = ReflectionAgent("/tmp/test_project", model_manager)
        # No diff should skip reflection
        with patch("os.path.exists", return_value=False):
            result = agent.reflect_on_task("task1", "/tmp/worktree", "test task")
            assert result is None

    def test_reflect_with_diff(self):
        response = (
            '{"learned_knowledge": {"title": "Error pattern", '
            '"summary": "Always check for None", '
            '"target_files": ["file.py"]}, '
            '"propose_auto_skill": false, '
            '"skill_description": ""}'
        )

        agent = _agent_with_response(response)
        with patch("os.path.exists", return_value=True), patch("subprocess.run", side_effect=_git_run):
            with patch.object(agent.ki_engine, "save_ki"):
                agent.reflect_on_task("task1", "/tmp/worktree", "test")
                # Should not raise

    def test_reflect_with_auto_skill(self):
        response = (
            '{"learned_knowledge": {"title": "Test", "summary": "Test"}, '
            '"propose_auto_skill": true, '
            '"skill_description": "A tool for parsing regex"}'
        )

        agent = _agent_with_response(response)
        with patch("os.path.exists", return_value=True), patch("subprocess.run", side_effect=_git_run):
            with patch.object(agent.ki_engine, "save_ki"):
                with patch.object(agent, "_synthesize_skill"):
                    agent.reflect_on_task("task1", "/tmp/worktree", "test")
                    # Should not raise

    def test_synthesize_skill_valid(self):
        agent = _agent_with_response(
            "```python\nclass RegexParserTool(BaseTool):\n"
            + "    name = 'regex_parser'\n"
            + "    def execute(self, **kwargs):\n"
            + "        return 'parsed'\n"
            + "```",
        )
        with patch("builtins.open"):
            with patch("os.path.join", return_value="/tmp/skill.py"):
                _synthesize_skill(agent, "A regex parser tool")

    def test_synthesize_skill_invalid(self):
        agent = _agent_with_response("Not valid code")
        _synthesize_skill(agent, "invalid")
        # Should not crash

    def test_synthesize_skill_syntax_error(self):
        agent = _agent_with_response("```python\nclass (MissingName):\n    pass\n```")
        _synthesize_skill(agent, "invalid syntax")
        # Should not crash
