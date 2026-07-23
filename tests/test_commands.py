"""Tests for the agent commands module."""

from unittest import mock

from antigravity_k.agents.commands import CommandHandler


class TestCommandHandler:
    def setup_method(self):
        self.team_manager = mock.MagicMock()
        self.handler = CommandHandler(self.team_manager)

    def test_execute_empty(self):
        result = self.handler.execute("")
        assert "명령어가 입력되지 않았습니다" in result

    def test_execute_help(self):
        result = self.handler.execute("/help")
        assert "Antigravity-K 명령어 가이드" in result
        assert "/tasks" in result
        assert "/status" in result

    def test_execute_status(self):
        result = self.handler.execute("/status")
        assert "시스템 헬스" in result
        assert "정상" in result

    def test_execute_clear(self):
        result = self.handler.execute("/clear")
        assert result == "CLEAR_COMMAND_RECEIVED"

    def test_execute_tasks_empty_board(self):
        self.team_manager.kanban_board.get_board_state.return_value = {
            "Backlog": [],
            "In Progress": [],
            "Done": [],
        }
        result = self.handler.execute("/tasks")
        assert "Kanban Board" in result
        assert "Backlog" in result
        assert "비어 있음" in result

    def test_execute_tasks_with_items(self):
        self.team_manager.kanban_board.get_board_state.return_value = {
            "In Progress": [
                {"id": "T-1", "description": "Fix bug", "assignee": "QA"},
            ],
        }
        result = self.handler.execute("/tasks")
        assert "T-1" in result
        assert "Fix bug" in result
        assert "QA" in result

    def test_execute_review_no_args(self):
        result = self.handler.execute("/review")
        assert "사용법" in result

    def test_execute_review_with_args(self):
        self.team_manager.add_task.return_value = "T-42"
        result = self.handler.execute("/review my_code.py")
        assert "리뷰 작업" in result
        assert "T-42" in result
        self.team_manager.add_task.assert_called_once()
        self.team_manager.delegate_task.assert_called_once_with("T-42", "QA")

    def test_execute_delegate_no_args(self):
        result = self.handler.execute("/delegate")
        assert "사용법" in result

    def test_execute_delegate_one_arg(self):
        result = self.handler.execute("/delegate T-1")
        assert "사용법" in result

    def test_execute_delegate_success(self):
        result = self.handler.execute("/delegate T-1 Coder")
        assert "위임" in result
        assert "T-1" in result
        assert "CODER" in result or "Coder" in result
        self.team_manager.delegate_task.assert_called_once_with("T-1", "CODER")

    def test_execute_unknown_command(self):
        result = self.handler.execute("/nonexistent")
        assert "알 수 없는 명령어" in result

    def test_execute_exception_handling(self):
        self.handler.commands["/help"] = lambda args: (_ for _ in ()).throw(ValueError("oops"))
        result = self.handler.execute("/help")
        assert "오류 발생" in result
        assert "oops" in result
