"""Coordinator module."""

import json
import logging
import time

from rich.console import Console
from rich.panel import Panel

from ..tasks.local_agent_task import LocalAgentTask

logger = logging.getLogger(__name__)


class CoordinatorManager:
    """다중 에이전트 협업 및 병렬 태스크 실행을 오케스트레이션하는 Coordinator.

    Claude Code의 Coordinator 아키텍처에서 착안하여, 주어진 문제를 분석하고
    하위 태스크로 나누어 여러 에이전트가 동시에 처리하도록 합니다.
    """

    def __init__(self, team_manager):
        """Initialize the CoordinatorManager.

        Args:
            team_manager: team manager.

        """
        self.team_manager = team_manager
        self.active_tasks: list[LocalAgentTask] = []
        self.console = Console()

    def analyze_and_delegate(self, user_prompt: str, context: dict | None = None) -> str:
        """문제를 분석하여 병렬로 실행할 수 있는 하위 태스크로 분할하고, 다중 에이전트 토론/협력을 유도합니다."""
        self.console.print(
            Panel(f"[bold cyan]Coordinator is analyzing the task...[/bold cyan]\n{user_prompt}"),
        )
        logger.info("Coordinator started analyzing the task.")

        # 1. 문제 분석 및 역할 결정 (임시 Coordinator 에이전트 활용)
        coordinator_agent_name = f"COORDINATOR_{int(time.time())}"
        self.team_manager.create_agent("CEO", custom_name=coordinator_agent_name)
        coordinator = self.team_manager.agents[coordinator_agent_name]

        analysis_prompt = (
            f"Task: {user_prompt}\n"
            f"Analyze this task and break it down into exactly two distinct sub-perspectives for a robust solution.\n"
            f"1) 'Proposer': Focuses on functional implementation and solving the core problem.\n"
            f"2) 'Critic': Focuses on security, performance, edge cases, and code quality.\n"
            f"Return a JSON object with 'proposer_task' and"
            f"'critic_task' string fields explaining what each should do."
            f"Do not return markdown formatting, just raw JSON."
        )

        try:
            analysis_result = coordinator.run(
                analysis_prompt,
                model_manager=self.team_manager.model_manager,
            )
            import re

            cleaned_result = analysis_result.strip()
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned_result, re.DOTALL)
            if json_match:
                cleaned_result = json_match.group(1)
            else:
                start = cleaned_result.find("{")
                end = cleaned_result.rfind("}")
                if start != -1 and end != -1:
                    cleaned_result = cleaned_result[start : end + 1]
            task_breakdown = json.loads(cleaned_result.strip())
        except Exception:
            logger.exception("Failed to parse JSON from Coordinator. Fallback to default split.")
            task_breakdown = {
                "proposer_task": f"Provide the optimal functional implementation for: {user_prompt}",
                "critic_task": f"Analyze the requirements for edge cases and security regarding: {user_prompt}",
            }

        proposer_instruction = task_breakdown.get("proposer_task", "Implement the feature.")
        critic_instruction = task_breakdown.get(
            "critic_task",
            "Review for security and performance.",
        )

        # 2. 동적 팀 생성
        proposer_name = f"DYN_PROPOSER_{int(time.time())}"
        critic_name = f"DYN_CRITIC_{int(time.time())}"

        self.team_manager.create_agent("PROPOSER", custom_name=proposer_name)
        self.team_manager.create_agent("CRITIC", custom_name=critic_name)

        proposer_agent = self.team_manager.agents[proposer_name]
        critic_agent = self.team_manager.agents[critic_name]

        # 채널 생성 (메시지 버스 연동)
        channel_name = f"coord_debate_{int(time.time())}"
        self.team_manager.message_bus.create_channel(channel_name)
        self.team_manager.message_bus.subscribe(channel_name, proposer_agent)
        self.team_manager.message_bus.subscribe(channel_name, critic_agent)

        self.console.print("[dim]Dynamically generated tasks for Proposer and Critic...[/dim]")

        # 3. 병렬 태스크(LocalAgentTask) 실행
        def run_agent(agent, instruction):
            return agent.run(instruction, model_manager=self.team_manager.model_manager)

        task_p = LocalAgentTask(
            name="ProposerTask",
            target=run_agent,
            args=(proposer_agent, proposer_instruction),
        )
        task_c = LocalAgentTask(
            name="CriticTask",
            target=run_agent,
            args=(critic_agent, critic_instruction),
        )

        self.active_tasks.extend([task_p, task_c])

        with self.console.status("[bold yellow]Parallel agents are working...[/bold yellow]"):
            task_p.start()
            task_c.start()

            task_p.join()
            task_c.join()

        # 4. 결과 취합
        p_result = task_p.result if task_p.status == "COMPLETED" else f"Proposer Failed: {task_p.error}"
        c_result = task_c.result if task_c.status == "COMPLETED" else f"Critic Failed: {task_c.error}"

        self.console.print(
            Panel(p_result, title="[blue]PROPOSER RESULT[/blue]", border_style="blue"),
        )
        self.console.print(
            Panel(c_result, title="[yellow]CRITIC RESULT[/yellow]", border_style="yellow"),
        )

        # 5. 최종 종합 (Reviewer/Coordinator 병합)
        merge_prompt = (
            f"Here are two perspectives on the original task.\n"
            f"Original Task: {user_prompt}\n\n"
            f"=== Proposer ===\n{p_result}\n\n"
            f"=== Critic ===\n{c_result}\n\n"
            f"As the Coordinator, merge these into a final, highly optimized, and secure implementation/solution. "
            f"Do not include the raw debate history, just output the final comprehensive response."
        )

        with self.console.status(
            "[bold green]Coordinator is finalizing the result...[/bold green]",
        ):
            final_result = coordinator.run(
                merge_prompt,
                model_manager=self.team_manager.model_manager,
            )

        self.console.print(
            Panel(
                final_result,
                title="[bold green]FINAL COORDINATOR RESULT[/bold green]",
                border_style="green",
            ),
        )

        # 정리
        del self.team_manager.agents[coordinator_agent_name]
        del self.team_manager.agents[proposer_name]
        del self.team_manager.agents[critic_name]
        self.active_tasks.clear()

        # ArtifactService를 통한 자동 문서화(Debate Log 저장)
        if self.team_manager.artifact_service:
            log_content = (
                f"# Coordinator Debate Log\n\n## Original Task\n{user_prompt}\n\n"
                f"## Proposer\n{p_result}\n\n## Critic\n{c_result}\n\n"
                f"## Final Result\n{final_result}\n"
            )
            self.team_manager.artifact_service.create_artifact(
                name=f"coordinator_debate_{int(time.time())}",
                content=log_content,
                extension="md",
            )

        # Autopilot 자동 커밋
        self.team_manager._auto_commit("Coordinator Parallel Execution Complete")

        return final_result
