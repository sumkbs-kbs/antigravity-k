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
from importlib import import_module
from typing import Any

from pydantic import ValidationError

from antigravity_k.engine.agent_definition import (
    AgentContractViolation,
    AgentSpawnContract,
    AgentSpawnRequest,
    AgentToolRegistry,
    ResolvedAgentSpawn,
    default_agent_spawn_contract,
)
from antigravity_k.engine.subagent_execution import start_subagent_stream
from antigravity_k.engine.task_runner import get_task_runner

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory
from .tool_registry import ToolRegistry

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

    def __init__(
        self,
        model_manager=None,
        tool_registry: ToolRegistry | None = None,
        contract: AgentSpawnContract | None = None,
    ):
        """Initialize the AgentSpawnTool.

        Args:
            model_manager: model manager.
            tool_registry: tool registry.

        """
        super().__init__()
        self.tags = ["agent", "spawn", "delegate", "subtask"]
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
                "agent": {
                    "type": "string",
                    "description": "Declared child agent name.",
                    "default": "WORKER",
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
        self._contract = contract or default_agent_spawn_contract()

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
        try:
            request = AgentSpawnRequest.model_validate(kwargs)
            resolved = self._contract.resolve(request.agent, request.tools)
        except ValidationError as error:
            return f"Error: Invalid agent spawn request: {error.errors(include_url=False)}"
        except AgentContractViolation as error:
            return f"[DENIED] {error}"

        if not self._model_manager:
            return self._fallback_execute(request.task, list(resolved.allowed_tools))

        try:
            return self._spawn_sub_agent(request, resolved)
        except Exception as e:
            logger.exception("Sub-agent spawn failed")
            return f"Error: Sub-agent failed: {e}"

    def _spawn_sub_agent(
        self,
        request: AgentSpawnRequest,
        resolved: ResolvedAgentSpawn,
    ) -> str:
        """실제 Orchestrator 루프를 통한 Sub-Agent 실행."""
        start_time = time.time()
        tool_registry = self._tool_registry
        if tool_registry is None:
            return "Sub-agent execution failed: ToolRegistry is unavailable."

        try:
            dependencies = import_module("antigravity_k.api.dependencies")
            orchestrator_module = import_module("antigravity_k.engine.orchestrator")
            get_vault_engine = dependencies.__dict__["get_vault_engine"]
            OrchestratorAgent = orchestrator_module.__dict__["OrchestratorAgent"]

            sub_orchestrator = OrchestratorAgent(
                model_manager=self._model_manager,
                vault_engine=get_vault_engine(),
                tool_registry=AgentToolRegistry(
                    tool_registry,
                    resolved.definition,
                    resolved.allowed_tools,
                ),
            )

            # Sub-Agent용 모델 결정 (WORKER 역할에 매핑된 모델 사용)
            target_model = sub_orchestrator._get_model_for_role(resolved.definition.role)

            # Sub-Agent 시스템 프롬프트
            system_prompt = resolved.definition.system_prompt

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Task: {request.task}\nAvailable tools: {list(resolved.allowed_tools)}",
                },
            ]

            logger.info("Starting synchronous Sub-Agent for task: %s...", request.task[:50])

            tracked_stream = start_subagent_stream(
                sub_orchestrator,
                task_runner=get_task_runner(),
                messages=messages,
                target_model=target_model,
                subagent_kind="agent_spawn",
            )
            output_parts = list(tracked_stream.chunks)

            elapsed = time.time() - start_time
            result = "".join(output_parts)

            return f"[Sub-Agent Result] (completed in {elapsed:.1f}s)\n{result}"
        except Exception as e:
            logger.exception("Sub-agent execution failed")
            return f"Sub-agent execution failed: {e}"

    def _fallback_execute(self, task: str, tool_names: list[str]) -> str:
        """ModelManager 미연결 시 폴백 (작업 기록만)."""
        return (
            f"[Sub-Agent Queued]\n"
            f"Task: {task}\n"
            f"Tools: {', '.join(tool_names)}\n"
            f"Note: Sub-agent execution requires a connected ModelManager. "
            f"Task has been recorded for manual review."
        )
