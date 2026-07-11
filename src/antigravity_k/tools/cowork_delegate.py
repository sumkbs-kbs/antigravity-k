"""Cowork Delegate module."""

import logging
from typing import Any

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

# 주의: task_runner와 orchestrator는 순환 참조 방지를 위해 execute() 내부에서 지연 import

logger = logging.getLogger(__name__)


class CoworkDelegateTool(BaseTool):
    """Claude Cowork 철학을 반영하여, 메인 에이전트가 복잡한 백그라운드 태스크(정보 수집, 파일 수정, 분석 등)를.

    격리된 워크트리 환경에서 수행할 '서브 에이전트(Sub-Agent)'를 스폰합니다.
    """

    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🤝"
    tags = ["cowork", "delegate", "subagent", "background", "worktree"]

    def __init__(self, project_root: str | None = None, model_manager=None):
        """Initialize the CoworkDelegateTool.

        Args:
            project_root (str): str project root.
            model_manager: model manager.

        """
        super().__init__()
        self._name = "cowork_delegate"
        self._description = "Delegate a complex, multi-step task (like research, mass file reading, or refactoring) to an autonomous Sub-Agent. The"  # type: ignore  # noqa: E501
        "Sub-Agent will run in the background in an isolated Git Worktree so it won't block the main chat or conflict with current files. Returns a background Task ID."  # noqa: E501
        self._schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Highly detailed instructions for the Sub-Agent. What it needs to do, read, or write.",  # noqa: E501
                },
                "use_worktree": {
                    "type": "boolean",
                    "description": "Set to true to isolate the Sub-Agent in a separate git worktree (prevents git conflicts). Default true.",  # noqa: E501
                    "default": True,
                },
            },
            "required": ["prompt"],
        }
        self.project_root = project_root
        self.model_manager = model_manager

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        prompt = kwargs.get("prompt", "")
        use_worktree = kwargs.get("use_worktree", True)

        if not prompt:
            return "Error: Prompt is required."

        try:
            if not self.model_manager:
                return "Error: model_manager is not initialized in CoworkDelegateTool."

            # 지연 import (순환 참조 방지)
            from antigravity_k.engine.orchestrator import OrchestratorAgent
            from antigravity_k.engine.task_runner import get_task_runner

            runner = get_task_runner()
            # Create a dedicated Orchestrator for the sub-agent
            sub_orchestrator = OrchestratorAgent(model_manager=self.model_manager)

            # Context can carry over some current path info
            context = {"cowork_mode": True, "project_root": self.project_root}

            task_id = runner.submit_task(
                prompt=f"[Coworker Sub-Agent] You are a delegated background agent. Goal:\n{prompt}\n\nPlease complete this task autonomously"  # type: ignore  # noqa: E501
                "using your tools. When done, create an artifact with your final report so the main user can see it.",
                context=context,
                orchestrator=sub_orchestrator,
                use_worktree=use_worktree,
            )

            return (
                f"[COWORK DELEGATED]\n"
                f"Successfully spawned a Sub-Agent to handle the task in the background.\n"
                f"Task ID: {task_id}\n"
                f"Worktree Isolated: {use_worktree}\n"
                f"You can continue chatting with the user while the coworker finishes the task."
            )
        except Exception as e:
            logger.exception("Cowork delegation failed")
            return f"Error spawning sub-agent: {e}"
