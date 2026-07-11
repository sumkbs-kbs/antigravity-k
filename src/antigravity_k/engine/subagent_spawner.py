"""SubAgent Spawner Engine (OpenClaw Pattern).

===========================================

독립적인 서브 세션을 생성하고 병렬로 실행하여 결과를 취합하는 엔진 모듈입니다.
OpenClaw의 'sessions_spawn' 로직을 내재화하여 메인 컨텍스트 오염을 방지하고
작업을 효율적으로 병렬 분배합니다.
"""

import asyncio
import logging
import time
from typing import Any

from antigravity_k.api.dependencies import get_vault_engine
from antigravity_k.engine.orchestrator import OrchestratorAgent

logger = logging.getLogger(__name__)


class SubagentSpawner:
    """Subagentspawner."""

    def __init__(self, model_manager, tool_registry):
        """Initialize the SubagentSpawner.

        Args:
            model_manager: model manager.
            tool_registry: tool registry.

        """
        self.model_manager = model_manager
        self.tool_registry = tool_registry
        self.vault_engine = get_vault_engine()

    async def spawn_parallel(
        self,
        tasks: list[dict[str, Any]],
        max_tokens: int = 4096,
    ) -> list[str]:
        """여러 서브 태스크를 병렬로 스폰하여 결과를 반환합니다."""
        logger.info("Spawning %s sub-agents in parallel.", len(tasks))

        async def _run_subagent(task_data: dict[str, Any], index: int) -> str:
            task_desc = task_data.get("task", "")
            tools_allowed = task_data.get("tools", ["read_file", "glob_search"])

            start_time = time.time()
            try:
                # 독립된 Orchestrator 인스턴스 생성 (부모 툴 레지스트리 공유)
                sub_orch = OrchestratorAgent(
                    model_manager=self.model_manager,
                    vault_engine=self.vault_engine,
                    tool_registry=self.tool_registry,
                )

                target_model = sub_orch._get_model_for_role("WORKER")
                system_prompt = (
                    "You are a focused sub-agent spawned for a specific sub-task. "
                    "Use your tools to solve it. Return only the essential result."
                )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Task: {task_desc}\nAllowed tools: {tools_allowed}",
                    },
                ]

                # run_stream is synchronous generator, we need to run it in a thread to not block async
                def run_sync_stream():
                    output_parts = []
                    for chunk in sub_orch.run_stream(messages, target_model=target_model):
                        output_parts.append(chunk)
                    return "".join(output_parts)

                result = await asyncio.to_thread(run_sync_stream)
                elapsed = time.time() - start_time
                return f"[Sub-Agent #{index} Result] (in {elapsed:.1f}s)\n{result}"

            except Exception as e:
                logger.error("Subagent #%s failed: %s", index, e, exc_info=True)
                return f"[Sub-Agent #{index} Error] {e}"

        coroutines = [_run_subagent(task, i) for i, task in enumerate(tasks)]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Format results
        formatted_results = []
        for res in results:
            if isinstance(res, BaseException):
                formatted_results.append(f"Exception: {res}")
            else:
                formatted_results.append(str(res))

        return formatted_results

    def spawn(self, task: str, tools: list[str], max_tokens: int = 4096) -> str:
        """단일 서브 태스크를 스폰하는 동기 진입점 (기존 AgentSpawnTool 하위호환)."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        tasks = [{"task": task, "tools": tools}]
        results = loop.run_until_complete(self.spawn_parallel(tasks, max_tokens))
        return results[0]
