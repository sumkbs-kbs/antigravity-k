import logging
from typing import Callable, Dict, Any
from .team_manager import TeamManager

logger = logging.getLogger(__name__)

class CommandHandler:
    """
    사용자(CTO)가 입력하는 슬래시 명령어(Slash Command)를 처리합니다.
    Claude Code의 명령어 시스템(/review, /tasks 등)을 차용했습니다.
    """
    def __init__(self, team_manager: TeamManager):
        self.team_manager = team_manager
        self.commands: Dict[str, Callable] = {
            "/help": self.handle_help,
            "/tasks": self.handle_tasks,
            "/review": self.handle_review,
            "/delegate": self.handle_delegate,
            "/status": self.handle_status,
            "/clear": self.handle_clear
        }

    def execute(self, command_str: str) -> str:
        parts = command_str.strip().split()
        if not parts:
            return "명령어가 입력되지 않았습니다. /help를 입력해 도움말을 확인하세요."
            
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd in self.commands:
            try:
                return self.commands[cmd](args)
            except Exception as e:
                logger.error(f"Error executing command {cmd}: {e}")
                return f"명령어 실행 중 오류 발생: {e}"
        else:
            return f"알 수 없는 명령어입니다: {cmd}. '/help'를 입력하여 사용 가능한 명령어를 확인하세요."

    def handle_help(self, args: list) -> str:
        """사용 가능한 슬래시 명령어 목록을 출력합니다."""
        help_text = [
            "=== Antigravity-K 명령어 가이드 ===",
            "/help         : 이 도움말을 표시합니다.",
            "/tasks        : 현재 Kanban 보드의 상태를 출력합니다.",
            "/status       : 에이전트 팀과 메모리 상태를 요약합니다.",
            "/review [대상]: QA 에이전트에게 코드나 상태 리뷰를 요청합니다.",
            "/delegate [ID] [에이전트]: 특정 작업을 다른 에이전트에게 할당합니다.",
            "/clear        : 현재 컨텍스트나 화면 상태를 초기화합니다 (UI 연동용)."
        ]
        return "\n".join(help_text)

    def handle_status(self, args: list) -> str:
        """팀 상태 및 시스템 헬스체크를 수행합니다."""
        return "시스템 헬스: 정상\n가동 중인 에이전트 수: 측정 중...\n(추후 팀 상태 연동 예정)"

    def handle_clear(self, args: list) -> str:
        """상태 초기화 명령"""
        return "CLEAR_COMMAND_RECEIVED"

    def handle_tasks(self, args: list) -> str:
        """현재 Kanban 보드의 상태를 출력합니다."""
        state = self.team_manager.kanban_board.get_board_state()
        output = ["=== Kanban Board ==="]
        for column, tasks in state.items():
            output.append(f"\n[{column}]")
            if not tasks:
                output.append("  (비어 있음)")
            for task in tasks:
                assignee = task.get('assignee') or 'Unassigned'
                output.append(f"  - {task['id']}: {task['description']} (담당: {assignee})")
        return "\n".join(output)

    def handle_review(self, args: list) -> str:
        """QA 에이전트에게 특정 코드나 상태의 리뷰를 지시합니다."""
        if not args:
            return "사용법: /review [리뷰할 내용 또는 대상]"
        
        target = " ".join(args)
        task_id = self.team_manager.add_task(f"Review required for: {target}")
        self.team_manager.delegate_task(task_id, "QA")
        return f"리뷰 작업이 QA 에이전트에게 할당되었습니다. (Task ID: {task_id})"

    def handle_delegate(self, args: list) -> str:
        """작업을 특정 에이전트에게 수동으로 할당합니다."""
        if len(args) < 2:
            return "사용법: /delegate [Task_ID] [Agent_Name]"
            
        task_id = args[0]
        agent_name = args[1].upper()
        
        try:
            self.team_manager.delegate_task(task_id, agent_name)
            return f"작업 {task_id}이(가) {agent_name} 에이전트에게 위임되었습니다."
        except Exception as e:
            return str(e)
