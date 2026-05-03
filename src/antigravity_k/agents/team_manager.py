import logging
import time
import subprocess
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .base_agent import BaseAgent
from .personas import get_persona
from .kanban import KanbanBoard
from .message_bus import MessageBus
from ..config import config
from ..knowledge.artifact_service import ArtifactService
from .coordinator import CoordinatorManager
from ..tools.tool_registry import ToolRegistry
from ..tools.base_tool import RiskLevel
from ..i18n import get_i18n, I18n

logger = logging.getLogger(__name__)

class TeamManager:
    """
    Claude Agent Teams 아키텍처를 구현하는 오케스트레이터(CTO 역할).
    하위 에이전트들을 관리하고, 상태(Kanban)를 추적하며 메시지를 라우팅합니다.
    """
    def __init__(self, model_manager=None):
        self.agents: Dict[str, BaseAgent] = {}
        self.kanban_board = KanbanBoard()
        self.message_bus = MessageBus()
        self.model_manager = model_manager
        self.artifact_service = ArtifactService()
        self.coordinator = CoordinatorManager(self)

        # ── ToolRegistry 초기화 (tiptap-vuetify Plugin.install 패턴) ──
        self.tool_registry = ToolRegistry()
        self._initialize_tool_registry()

        # ── I18n 초기화 (tiptap-vuetify i18n 패턴) ──
        locale_code = config.i18n.locale if config.i18n.locale != "auto" else None
        self.i18n: I18n = get_i18n() if locale_code is None else I18n(locale_code=locale_code)

        # 초기 기본 팀 구성
        self._initialize_default_team()

    def _auto_commit(self, phase_name: str):
        """Autopilot: 중요 지점 자동 Git 커밋 수행"""
        if not config.workflow.auto_commit:
            return
            
        try:
            status_output = subprocess.run(["git", "status", "--porcelain"], check=True, capture_output=True, text=True).stdout
            if not status_output.strip():
                logger.info(f"Autopilot: No changes to commit for phase {phase_name}")
                return

            logger.info(f"Autopilot: Auto-committing for phase {phase_name}")
            subprocess.run(["git", "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"[Auto-Agent] Phase: {phase_name}"], check=True, capture_output=True)
            logger.info(f"Auto-commit successful: {phase_name}")
        except subprocess.CalledProcessError as e:
            err_msg = e.output.decode('utf-8', errors='ignore') if isinstance(e.output, bytes) else str(e)
            logger.debug(f"Auto-commit skipped or failed: {err_msg}")
        except Exception as e:
            logger.error(f"Auto-commit failed: {e}")

    def _initialize_tool_registry(self):
        """
        시스템 도구들을 ToolRegistry에 자동 등록합니다.
        tiptap-vuetify의 Plugin.install() 패턴 적용.
        """
        from ..tools.system_tools import ReadFileTool, ReplaceFileContentTool, RunBashCommandTool
        from ..tools.test_runner_tool import TestRunnerTool
        self.tool_registry.install_many(
            ReadFileTool, ReplaceFileContentTool, RunBashCommandTool, TestRunnerTool
        )
        # ComputerUseTool은 설정에 따라 조건부 등록
        if config.computer_use.enabled:
            from ..tools.computer_use import ComputerUseTool
            self.tool_registry.install(
                ComputerUseTool, force_stub=config.computer_use.force_stub
            )
        logger.info(self.tool_registry.summary())

    def get_tools_for_role(self, role_name: str) -> List:
        """
        역할(role)에 맞는 도구 목록을 ToolRegistry에서 필터링하여 반환합니다.
        위험도가 config.security.max_tool_risk를 초과하는 도구는 자동 제외됩니다.
        """
        max_risk_str = config.security.max_tool_risk
        try:
            max_risk = RiskLevel(max_risk_str)
        except ValueError:
            max_risk = RiskLevel.HIGH

        allowed_tools = self.tool_registry.filter_by_risk(max_risk)
        return allowed_tools

    def _initialize_default_team(self):
        """기본 페르소나들로 팀을 구성합니다."""
        for role_name in ["CEO", "ENG_MANAGER", "WORKER", "QA"]:
            self.create_agent(role_name)

    def create_agent(self, role_name: str, custom_name: Optional[str] = None):
        """새로운 에이전트를 생성하여 팀에 합류시킵니다."""
        persona = get_persona(role_name)
        agent_name = custom_name or role_name
        
        # 실제 환경에서는 ModelManager를 통해 각 역할에 맞는 최적의 모델(예: Hermes 3, Qwen 등)을 
        # 할당해야 하지만, 여기서는 더미 model_id를 지정합니다.
        model_id = "default_model"
        if self.model_manager:
            model_role = "reasoning"
            if persona["role"] == "WORKER":
                model_role = "coding"
            
            loaded_model = self.model_manager.get_by_role(model_role)
            if loaded_model:
                model_id = loaded_model.profile.name
        
        agent = BaseAgent(
            name=agent_name,
            role=persona["role"],
            system_prompt=persona["system_prompt"],
            model_id=model_id
        )
        self.message_bus.subscribe("general", agent)
        self.agents[agent_name] = agent
        logger.info(f"Agent '{agent_name}' ({persona['role']}, Model: {model_id}) joined the team.")

    def add_task(self, task_description: str):
        """새로운 작업을 Kanban TODO 리스트에 추가합니다."""
        return self.kanban_board.create_task(task_description)

    def move_task(self, task_id: str, new_status: str):
        """작업의 상태를 변경합니다 (예: TODO -> IN_PROGRESS)."""
        self.kanban_board.move_task(task_id, new_status)

    def delegate_task(self, task_id: str, agent_name: str):
        """특정 에이전트에게 작업을 할당합니다."""
        if agent_name not in self.agents:
            logger.error(f"Agent {agent_name} does not exist.")
            return

        self.kanban_board.assign_task(task_id, agent_name)
        agent = self.agents[agent_name]
        
        logger.info(f"Task {task_id} delegated to {agent_name}")

    def spawn_subagent(self, task_description: str, context: Optional[Dict] = None) -> str:
        """
        독립적인 서브에이전트(Worker)를 스레드로 스폰하여 병렬 작업을 수행합니다.
        (Subagent-Driven Development 아키텍처)
        """
        task_id = self.add_task(task_description)
        subagent_name = f"SUBAGENT_{task_id}"
        
        # 임시 워커 생성 (이름은 task_id를 포함하여 유일하게 구성)
        self.create_agent("WORKER", custom_name=subagent_name)
        self.delegate_task(task_id, subagent_name)
        
        import threading
        
        def _run_subagent():
            logger.info(f"Subagent {subagent_name} started for {task_id}")
            agent = self.agents[subagent_name]
            
            # 컨텍스트가 있다면 프롬프트에 추가
            prompt = f"Task: {task_description}"
            if context:
                prompt += f"\nContext: {context}"
                
            # Autopilot: 자동 문서화 (시작)
            if config.workflow.auto_artifacts:
                console = Console()
                with console.status(f"[cyan]Subagent {subagent_name} is generating dynamic plan..."):
                    plan_prompt = f"Analyze the following task and provide a detailed implementation plan. Task: {task_description}"
                    if context:
                        plan_prompt += f"\nContext: {context}"
                    plan_content = agent.run(plan_prompt, model_manager=self.model_manager)
                    
                    checklist_prompt = f"Based on this implementation plan, generate a concise checklist of steps to execute. Provide only the items, one per line, with no introductory text or bullet points.\nPlan:\n{plan_content}"
                    checklist_content = agent.run(checklist_prompt, model_manager=self.model_manager)
                    
                    checklist_items = [line.strip('- *[]').strip() for line in checklist_content.split('\n') if line.strip()]
                    
                self.artifact_service.generate_plan(task_id, task_description, plan_content)
                self.artifact_service.generate_checklist(task_id, checklist_items)

            # Autopilot: 커밋 (시작)
            self._auto_commit(f"Start Subagent Task {task_id}")

            try:
                # 서브에이전트 구동
                result = agent.run(prompt, model_manager=self.model_manager)
                logger.info(f"Subagent {subagent_name} finished {task_id}. Result length: {len(result)}")
                
                # 작업 완료 시 REVIEW 상태로 이동 (Verification Gate 통과를 위함)
                self.move_task(task_id, "REVIEW")
                
                # Autopilot: 자동 문서화 (종료)
                if config.workflow.auto_artifacts:
                    self.artifact_service.generate_review(task_id, f"Subagent completed task successfully.\nResult length: {len(result)}")
                    self.artifact_service.generate_result(task_id, result, status="REVIEW")
                    
                # Autopilot: 커밋 (종료)
                self._auto_commit(f"Finish Subagent Task {task_id}")
                
            except Exception as e:
                logger.error(f"Subagent {subagent_name} failed on {task_id}: {str(e)}")
                # 실패 시 BACKLOG로 상태 원복
                self.move_task(task_id, "BACKLOG")
                if config.workflow.auto_artifacts:
                    if hasattr(self.artifact_service, 'generate_error_report'):
                        self.artifact_service.generate_error_report(task_id, str(e))
                self._auto_commit(f"Fail Subagent Task {task_id}")
            finally:
                # 임시 에이전트 자원 정리
                if subagent_name in self.agents:
                    del self.agents[subagent_name]
        
        thread = threading.Thread(target=_run_subagent, name=subagent_name)
        thread.daemon = True
        thread.start()
        
        return task_id

    def run_debate(self, topic: str, rounds: int = 2, num_critics: int = 2, context: Optional[Dict] = None) -> str:
        """
        주어진 주제(topic)에 대해 PROPOSER와 다수의 CRITIC 에이전트가 상호 토론(Debate)하여 최적의 결과를 도출합니다.
        (N:N / MoE / Peer Review 방식)
        """
        console = Console()
        console.print(Panel(f"[bold green]Starting Debate[/bold green]\nTopic: {topic}\nRounds: {rounds}, Critics: {num_critics}"))
        logger.info(f"Starting debate on topic: {topic} for {rounds} rounds with {num_critics} critics via MessageBus.")
        
        # 모델 프리패칭 (가능한 경우)
        if self.model_manager:
            default_reasoning = self.model_manager._registry.get_default("reasoning")
            if default_reasoning:
                self.model_manager.prefetch(default_reasoning.name)
        
        # 임시 토론용 에이전트 생성
        proposer_name = f"TEMP_PROPOSER_{id(self)}"
        self.create_agent("PROPOSER", custom_name=proposer_name)
        proposer = self.agents[proposer_name]
        
        critic_names = []
        for i in range(num_critics):
            critic_name = f"TEMP_CRITIC_{id(self)}_{i+1}"
            self.create_agent("CRITIC", custom_name=critic_name)
            critic_names.append(critic_name)
        
        # 토론 전용 채널 개설 및 구독
        channel_name = f"debate_{id(self)}"
        self.message_bus.create_channel(channel_name)
        self.message_bus.subscribe(channel_name, proposer)
        for c_name in critic_names:
            self.message_bus.subscribe(channel_name, self.agents[c_name])
            
        debate_log = [f"# Debate Log: {topic}\n"]
        current_proposal = ""
        
        for i in range(1, rounds + 1):
            debate_log.append(f"## Round {i}\n")
            console.print(f"\n[bold magenta]--- Debate Round {i} ---[/bold magenta]")
            logger.info(f"--- Debate Round {i} ---")
            
            # 1. Proposer의 제안/수정
            if i == 1:
                prompt = f"Please provide your initial optimal solution for the following topic.\nTopic: {topic}"
                if context:
                    prompt += f"\nContext: {context}"
            else:
                prompt = "Please revise your previous proposal based on the CRITICS' feedback provided in the channel. Consolidate their feedback and improve your proposal."
                
            with console.status(f"[cyan]PROPOSER is thinking (Round {i})..."):
                current_proposal = proposer.run(prompt, model_manager=self.model_manager)
            
            self.message_bus.publish(channel_name, proposer_name, current_proposal)
            debate_log.append(f"### PROPOSER\n{current_proposal}\n")
            logger.info(f"Proposer completed round {i}.")
            console.print(Panel(Markdown(current_proposal), title="[blue]PROPOSER[/blue]", border_style="blue"))
            
            # 2. 다수 Critic의 비판
            critique_prompt = f"Please analyze the latest proposal from PROPOSER critically and provide constructive feedback."
            for idx, c_name in enumerate(critic_names):
                critic = self.agents[c_name]
                with console.status(f"[yellow]CRITIC {idx+1} is analyzing..."):
                    critic_feedback = critic.run(critique_prompt, model_manager=self.model_manager)
                
                self.message_bus.publish(channel_name, c_name, critic_feedback)
                debate_log.append(f"### CRITIC {idx+1}\n{critic_feedback}\n")
                logger.info(f"Critic {idx+1} ({c_name}) completed round {i}.")
                console.print(Panel(Markdown(critic_feedback), title=f"[yellow]CRITIC {idx+1}[/yellow]", border_style="yellow"))

        # 최종 산출물 정리 (ARBITER 중재)
        arbiter_name = f"TEMP_ARBITER_{id(self)}"
        self.create_agent("ARBITER", custom_name=arbiter_name)
        arbiter = self.agents[arbiter_name]
        
        with console.status("[green]ARBITER is finalizing the consensus..."):
            final_summary_prompt = "Based on the debate above, objectively weigh the arguments, resolve any conflicts, and provide the final, fully refined and optimal consensus solution. Do not include the debate history, only the final result."
            
            # 토론 기록을 Context로 전달
            full_debate_context = "\n".join(debate_log)
            final_result = arbiter.run(f"Debate History:\n{full_debate_context}\n\nTask: {final_summary_prompt}", model_manager=self.model_manager)
            
        debate_log.append(f"## Final Optimal Solution (by ARBITER)\n{final_result}\n")
        console.print(Panel(Markdown(final_result), title="[bold green]Final Optimal Solution (by ARBITER)[/bold green]", border_style="green"))

        
        # ArtifactService를 이용해 토론 기록 저장
        try:
            from ..knowledge.artifact_service import ArtifactService
            artifact_service = ArtifactService()
            log_content = "\n".join(debate_log)
            artifact_path = artifact_service.create_artifact(
                name=f"debate_log_{int(time.time())}", 
                content=log_content, 
                extension="md"
            )
            logger.info(f"Debate log saved to {artifact_path}")
            console.print(f"[dim]Debate log saved to artifacts.[/dim]")
        except Exception as e:
            logger.error(f"Failed to save debate log: {e}")
        
        # 임시 에이전트 자원 정리
        del self.agents[proposer_name]
        for c_name in critic_names:
            del self.agents[c_name]
        if arbiter_name in self.agents:
            del self.agents[arbiter_name]
            
        # Autopilot: 커밋 (Debate 완료)
        self._auto_commit(f"Complete Debate - {topic[:20]}")
            
        return final_result

    def run_team_cycle(self):
        """
        팀 전체의 협업 사이클을 한 번 돕니다.
        자율 작업 풀링(Pull) 및 메시지 버스 연동을 처리합니다.
        """
        logger.info("Running team collaboration cycle...")
        
        # 1. 할당되지 않은 작업들을 에이전트들이 자율적으로 Pull하도록 시도
        for agent_name, agent in self.agents.items():
            if hasattr(self.kanban_board, "pull_task"):
                pulled_task_id = self.kanban_board.pull_task(agent_name)
                if pulled_task_id:
                    logger.info(f"Agent '{agent_name}' autonomously pulled task '{pulled_task_id}'")
                    # 향후: 여기서 agent.run() 을 호출하여 작업 시작 가능
                    
        # 2. 메시지 버스의 알림을 처리 (추후 구현)
        logger.info("Team cycle completed.")

    def run_coordinator_task(self, user_prompt: str, context: Optional[Dict] = None) -> str:
        """
        CoordinatorManager를 이용해 태스크를 동적으로 분석하고 다중 에이전트 병렬 실행을 수행합니다.
        (Antigravity-K 2단계 고도화 아키텍처)
        """
        logger.info(f"Delegating task to Coordinator: {user_prompt[:50]}...")
        return self.coordinator.analyze_and_delegate(user_prompt, context)
