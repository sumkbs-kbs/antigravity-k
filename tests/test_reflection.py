"""Tests for ReflectionAgent (reflection.py)."""

from unittest.mock import MagicMock, patch

from antigravity_k.engine.reflection import ReflectionAgent


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

    @patch("os.path.exists")
    @patch("subprocess.run")
    def test_reflect_with_diff(self, mock_run, mock_exists):
        mock_exists.return_value = True
        mock_run.return_value.stdout = "diff --git a/file.py b/file.py\n+new code"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0

        model_manager = MagicMock()
        model_manager.generate.return_value = (
            '{"learned_knowledge": {"title": "Error pattern", '
            '"summary": "Always check for None", '
            '"target_files": ["file.py"]}, '
            '"propose_auto_skill": false, '
            '"skill_description": ""}'
        )

        agent = ReflectionAgent("/tmp/test_project", model_manager)
        with patch.object(agent.ki_engine, "save_ki"):
            agent.reflect_on_task("task1", "/tmp/worktree", "test")
            # Should not raise

    @patch("os.path.exists")
    @patch("subprocess.run")
    def test_reflect_with_auto_skill(self, mock_run, mock_exists):
        mock_exists.return_value = True
        mock_run.return_value.stdout = "diff --git a/file.py b/file.py\n+new code"
        mock_run.return_value.stderr = ""
        mock_run.return_value.returncode = 0

        model_manager = MagicMock()
        model_manager.generate.return_value = (
            '{"learned_knowledge": {"title": "Test", "summary": "Test"}, '
            '"propose_auto_skill": true, '
            '"skill_description": "A tool for parsing regex"}'
        )

        agent = ReflectionAgent("/tmp/test_project", model_manager)
        with patch.object(agent.ki_engine, "save_ki"):
            with patch.object(agent, "_synthesize_skill"):
                agent.reflect_on_task("task1", "/tmp/worktree", "test")
                # Should not raise

    def test_synthesize_skill_valid(self):
        model_manager = MagicMock()
        model_manager.generate.return_value = (
            "```python\nclass RegexParserTool(BaseTool):\n"
            "    name = 'regex_parser'\n"
            "    def execute(self, **kwargs):\n"
            "        return 'parsed'\n"
            "```"
        )
        agent = ReflectionAgent("/tmp/test_project", model_manager)
        with patch("builtins.open"):
            with patch("os.path.join", return_value="/tmp/skill.py"):
                agent._synthesize_skill("A regex parser tool")

    def test_synthesize_skill_invalid(self):
        model_manager = MagicMock()
        model_manager.generate.return_value = "Not valid code"
        agent = ReflectionAgent("/tmp/test_project", model_manager)
        agent._synthesize_skill("invalid")
        # Should not crash

    def test_synthesize_skill_syntax_error(self):
        model_manager = MagicMock()
        model_manager.generate.return_value = "```python\nclass (MissingName):\n    pass\n```"
        agent = ReflectionAgent("/tmp/test_project", model_manager)
        agent._synthesize_skill("invalid syntax")
        # Should not crash
