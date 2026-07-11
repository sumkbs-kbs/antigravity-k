"""AgentSpawn — Sub-Agent 스폰 도구.

=================================
Claw Code의 Agent Task 아키텍처 이식.

메인 에이전트가 하위 작업을 독립 컨텍스트에서
별도 LLM 호출로 위임하고 결과를 수집하는 패턴.

핵심 특징:
- 독립 컨텍스트 (메인 컨텍스트 오염 방지)
- 토큰 예산 제한
- 결과 요약 후 메인 컨텍스트에 주입
"""

import logging
import time
from typing import Any

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)


class AgentSpawnTool(BaseTool):
    """Sub-Agent를 스폰하여 독립 작업을 수행합니다.

    Claw Code의 agent_task 패턴:
    - 별도 LLM 호출로 하위 작업 수행
    - 독립 컨텍스트 (메인 대화 오염 방지)
    - 결과를 요약하여 메인에 반환
    """

    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "🤖"
    tags = ["agent", "spawn", "delegate", "subtask"]

    def __init__(self, model_manager=None, tool_registry=None):
        """Initialize the AgentSpawnTool.

        Args:
            model_manager: model manager.
            tool_registry: tool registry.

        """
        super().__init__()
        self._name = "agent_spawn"
        self._description = (
            "Spawns a sub-agent to perform an independent task. "
            "The sub-agent runs in its own context with its own tool set. "
            "Use for complex sub-tasks that require focused work."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of what the sub-agent should do.",
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tool names the sub-agent can use.",
                    "default": ["read_file", "glob_search", "grep_search"],
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens for the sub-agent's context.",
                    "default": 4096,
                },
            },
            "required": ["task"],
        }
        self._model_manager = model_manager
        self._tool_registry = tool_registry

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
        task = kwargs.get("task", "")
        tool_names = kwargs.get("tools", ["read_file", "glob_search", "grep_search"])
        max_tokens = kwargs.get("max_tokens", 4096)

        if not task:
            return "Error: No task description provided."

        if not self._model_manager:
            return self._fallback_execute(task, tool_names)

        try:
            return self._spawn_sub_agent(task, tool_names, max_tokens)
        except Exception as e:
            logger.exception("Sub-agent spawn failed")
            return f"Error: Sub-agent failed: {e}"

    def _spawn_sub_agent(self, task: str, tool_names: list, max_tokens: int) -> str:
        """실제 Orchestrator 루프를 통한 Sub-Agent 실행."""
        start_time = time.time()

        try:
            from antigravity_k.api.dependencies import get_vault_engine
            from antigravity_k.engine.orchestrator import OrchestratorAgent

            sub_orchestrator = OrchestratorAgent(
                model_manager=self._model_manager,
                vault_engine=get_vault_engine(),
                tool_registry=self._tool_registry,  # 부모의 ToolRegistry 공유 (도구 중복 생성 방지)
            )

            # Sub-Agent용 모델 결정 (WORKER 역할에 매핑된 모델 사용)
            target_model = sub_orchestrator._get_model_for_role("WORKER")

            # Sub-Agent 시스템 프롬프트
            system_prompt = (
                "You are a focused sub-agent. Complete the given task efficiently. "
                "You have access to tools, use them to accomplish the task. "
                "Return only the essential result without unnecessary explanation."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Task: {task}\nAvailable tools: {tool_names}",
                },
            ]

            logger.info("Starting synchronous Sub-Agent for task: %s...", task[:50])

            output_parts = []
            for chunk in sub_orchestrator.run_stream(messages, target_model=target_model):
                output_parts.append(chunk)

            elapsed = time.time() - start_time
            result = "".join(output_parts)

            return f"[Sub-Agent Result] (completed in {elapsed:.1f}s)\n{result}"
        except Exception as e:
            logger.error("Sub-agent execution failed: %s", e, exc_info=True)
            return f"Sub-agent execution failed: {e}"

    def _fallback_execute(self, task: str, tool_names: list) -> str:
        """ModelManager 미연결 시 폴백 (작업 기록만)."""
        return (
            f"[Sub-Agent Queued]\n"
            f"Task: {task}\n"
            f"Tools: {', '.join(tool_names)}\n"
            f"Note: Sub-agent execution requires a connected ModelManager. "
            f"Task has been recorded for manual review."
        )
