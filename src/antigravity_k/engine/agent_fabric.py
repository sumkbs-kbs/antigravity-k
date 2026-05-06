"""
Antigravity-K: Agent Fabric (Hybrid Multi-Agent Framework)
==========================================================
CrewAI의 팀 관리 + AutoGen의 통신 + LangGraph의 상태 그래프를 융합한
통합 멀티에이전트 실행 계층입니다.

기능:
    - AgentRegistry: 역할 기반 에이전트 Lazy 생성/캐싱 (CrewAI 패턴)
    - execute_single(): 단일 에이전트 실행 + ToolLoop 통합
    - execute_crew(): sequential/hierarchical 파이프라인 (CrewAI Crew 패턴)
    - execute_debate(): N:N GroupChat 토론 (AutoGen GroupChat 패턴)
    - KanbanBoard + MessageBus + AgentTracer 통합

사용법:
    fabric = AgentFabric(model_manager, tool_registry)
    for chunk in fabric.execute_single("WORKER", messages):
        yield chunk
"""

import logging
import time
import uuid
from typing import Dict, Generator, List

from antigravity_k.agents.base_agent import BaseAgent
from antigravity_k.agents.personas import get_persona
from antigravity_k.agents.kanban import KanbanBoard
from antigravity_k.agents.message_bus import MessageBus

logger = logging.getLogger("antigravity_k.engine.agent_fabric")


class AgentFabric:
    """
    Hybrid Multi-Agent Fabric.

    CrewAI + AutoGen + LangGraph 패턴을 융합한 에이전트 라이프사이클 관리자.
    orchestrator.py의 에이전트 관리 로직과 agents/team_manager.py를 통합합니다.

    핵심 원칙:
    - Single Source of Truth: personas.py에서 역할 정의
    - Lazy Creation: 에이전트는 필요할 때만 생성
    - Kanban Tracking: 모든 실행을 태스크로 추적
    - MessageBus: 에이전트 간 결과 전달
    """

    def __init__(self, model_manager=None, tool_registry=None):
        self.model_manager = model_manager
        self.tool_registry = tool_registry

        # CrewAI: 역할 기반 에이전트 레지스트리
        self._agent_registry: Dict[str, BaseAgent] = {}

        # 태스크 추적 (KanbanBoard + MessageBus)
        self.kanban = KanbanBoard()
        self.message_bus = MessageBus()

        # 관찰성
        try:
            from antigravity_k.engine.tracing import AgentTracer

            self.tracer = AgentTracer()
        except ImportError:
            self.tracer = None

        logger.info("[AgentFabric] Hybrid Fabric 초기화 완료")

    # ─── 에이전트 레지스트리 (CrewAI 패턴) ────────────────────────

    def get_or_create(self, role: str) -> BaseAgent:
        """역할별 에이전트를 Lazy 생성하거나 캐싱된 인스턴스를 반환합니다.

        CrewAI의 Agent(role, goal, backstory) 패턴을 적용합니다.
        """
        role_upper = role.upper()

        if role_upper in self._agent_registry:
            return self._agent_registry[role_upper]

        persona = get_persona(role_upper)

        # 모델 결정 (역할에 따른 최적 모델 매핑)
        model_id = "default_model"
        if self.model_manager:
            model_role = self._role_to_model_role(role_upper)
            loaded_model = self.model_manager.get_by_role(model_role)
            if loaded_model:
                model_id = loaded_model.profile.name

        agent = BaseAgent(
            name=role_upper,
            role=persona["role"],
            system_prompt=persona["system_prompt"],
            model_id=model_id,
        )

        # MessageBus 기본 채널 구독
        self.message_bus.subscribe("general", agent)

        self._agent_registry[role_upper] = agent
        logger.info(
            f"[AgentFabric] Agent '{role_upper}' 생성 "
            f"(goal: {persona.get('goal', 'N/A')[:40]}..., model: {model_id})"
        )
        return agent

    def create_temp_agent(self, role: str, suffix: str = "") -> BaseAgent:
        """임시 에이전트 생성 (토론 등에서 사용, 캐싱하지 않음)."""
        persona = get_persona(role)
        temp_name = f"TEMP_{role.upper()}_{suffix or uuid.uuid4().hex[:6]}"

        model_id = "default_model"
        if self.model_manager:
            model_role = self._role_to_model_role(role.upper())
            loaded_model = self.model_manager.get_by_role(model_role)
            if loaded_model:
                model_id = loaded_model.profile.name

        agent = BaseAgent(
            name=temp_name,
            role=persona["role"],
            system_prompt=persona["system_prompt"],
            model_id=model_id,
        )
        return agent

    def _role_to_model_role(self, role: str) -> str:
        """에이전트 역할 → ModelManager 모델 역할 매핑."""
        mapping = {
            "WORKER": "coding",
            "DESIGNER": "coding",
            "ENG_MANAGER": "reasoning",
            "ARCHITECT": "reasoning",
            "CEO": "reasoning",
            "QA": "reasoning",
            "PROPOSER": "reasoning",
            "CRITIC": "reasoning",
            "ARBITER": "reasoning",
        }
        return mapping.get(role, "reasoning")

    # ─── 단일 에이전트 실행 ───────────────────────────────────────

    def execute_single(
        self,
        role: str,
        messages: List[Dict[str, str]],
        orchestrator=None,
        task_type: str = "simple_chat",
        max_steps: int = 15,
    ) -> Generator[str, None, None]:
        """
        단일 에이전트 스트리밍 실행.

        orchestrator가 제공되면 기존 _run_single_agent() 도구 루프를 사용하고,
        없으면 BaseAgent.run()으로 폴백합니다.

        Args:
            role: 에이전트 역할 (WORKER, ENG_MANAGER, etc.)
            messages: 대화 메시지
            orchestrator: OrchestratorAgent 인스턴스 (도구 루프 사용)
            task_type: 태스크 유형
            max_steps: 최대 도구 호출 스텝
        """
        agent = self.get_or_create(role)
        task_id = self.kanban.create_task(
            f"[{role}] {task_type}: {messages[-1].get('content', '')[:50]}...",
            assignee=role,
        )
        self.kanban.move_task(task_id, "IN_PROGRESS")

        start_time = time.time()

        # Tracing
        if self.tracer:
            self.tracer.start_trace(f"fabric_execute_{role}")
            span = self.tracer.start_span(
                f"execute_single_{role}",
                attributes={"role": role, "task_type": task_type, "task_id": task_id},
            )

        try:
            if orchestrator and hasattr(orchestrator, "_run_single_agent"):
                # 기존 orchestrator의 도구 루프 사용 (Phase 1: 래핑)
                yield from orchestrator._run_single_agent(
                    messages, role, task_type, max_steps
                )
            else:
                # BaseAgent 직접 실행 (폴백)
                user_msg = messages[-1].get("content", "") if messages else ""
                result = agent.run(user_msg, model_manager=self.model_manager)
                yield result

            # 성공 → Kanban 업데이트
            elapsed = time.time() - start_time
            self.kanban.move_task(
                task_id, "REVIEW", verification_note=f"Completed in {elapsed:.1f}s"
            )

            # 결과를 MessageBus에 발행 (다른 에이전트가 참조 가능)
            self.message_bus.publish(
                "general",
                role,
                f"[Task {task_id}] Completed ({task_type})",
                meta={"elapsed": elapsed, "task_id": task_id},
            )

        except Exception as e:
            logger.error(f"[AgentFabric] execute_single({role}) failed: {e}")
            self.kanban.move_task(task_id, "BACKLOG")
            yield f"\n❌ **[Agent Error]** {role} 실행 실패: {e}\n"

        finally:
            if self.tracer and span:
                self.tracer.end_span(span)

    # ─── CrewAI식 파이프라인 실행 ─────────────────────────────────

    def execute_crew(
        self,
        steps: List[Dict],
        messages: List[Dict[str, str]],
        orchestrator=None,
        max_steps: int = 15,
        process: str = "sequential",
    ) -> Generator[str, None, None]:
        """
        CrewAI의 Crew 패턴: 멀티 에이전트 순차/계층 파이프라인.

        sequential: step1의 output → step2의 input → step3의 input
        hierarchical: CEO가 각 단계를 모니터링하며 동적 재할당

        Args:
            steps: [{"step": 1, "agent": "ARCHITECT", "task": "..."}, ...]
            messages: 원본 메시지
            orchestrator: OrchestratorAgent
            max_steps: 도구 호출 스텝 제한
            process: "sequential" 또는 "hierarchical"
        """
        # 파이프라인 전용 채널 생성
        channel = f"crew_{uuid.uuid4().hex[:8]}"
        self.message_bus.create_channel(channel)

        yield f"🚀 **[Crew Pipeline]** {len(steps)}단계 {process} 파이프라인 시작\n\n"

        accumulated_context = ""

        for i, step_info in enumerate(steps, 1):
            agent_role = step_info.get("agent", "WORKER")
            step_task = step_info.get("task", "")
            agent = self.get_or_create(agent_role)

            # MessageBus 채널 구독
            self.message_bus.subscribe(channel, agent)

            yield f"### 📋 Step {i}/{len(steps)}: **{agent_role}**\n"
            yield f"> {step_task}\n\n"

            # 이전 단계 결과를 컨텍스트에 주입 (CrewAI의 자동 전달 패턴)
            step_messages = list(messages)
            if accumulated_context:
                step_messages[-1] = {
                    "role": "user",
                    "content": (
                        f"{step_messages[-1].get('content', '')}\n\n"
                        f"### 이전 단계 결과:\n{accumulated_context}\n\n"
                        f"### 현재 단계 지시:\n{step_task}"
                    ),
                }

            # Kanban 태스크 생성
            task_id = self.kanban.create_task(
                f"[Pipeline Step {i}] {agent_role}: {step_task[:50]}...",
                assignee=agent_role,
            )
            self.kanban.move_task(task_id, "IN_PROGRESS")

            # 실행
            step_output_parts = []
            try:
                if orchestrator and hasattr(orchestrator, "_run_single_agent"):
                    for chunk in orchestrator._run_single_agent(
                        step_messages, agent_role, "pipeline_step", max_steps
                    ):
                        step_output_parts.append(chunk)
                        yield chunk
                else:
                    result = agent.run(
                        step_messages[-1].get("content", ""),
                        model_manager=self.model_manager,
                    )
                    step_output_parts.append(result)
                    yield result

                step_output = "".join(step_output_parts)
                accumulated_context += f"\n## {agent_role} (Step {i}):\n{step_output}\n"

                # MessageBus에 결과 발행
                self.message_bus.publish(
                    channel,
                    agent_role,
                    step_output,
                    meta={"step": i, "task_id": task_id},
                )

                self.kanban.move_task(
                    task_id,
                    "REVIEW",
                    verification_note=f"Step {i} completed",
                )

            except Exception as e:
                logger.error(
                    f"[AgentFabric] Pipeline step {i} ({agent_role}) failed: {e}"
                )
                self.kanban.move_task(task_id, "BACKLOG")
                yield f"\n❌ **Step {i} ({agent_role})** 실행 실패: {e}\n"
                break

            yield "\n---\n\n"

        yield f"\n✅ **[Crew Pipeline 완료]** {len(steps)}단계 모두 실행됨\n"

    # ─── AutoGen식 N:N 토론 실행 ──────────────────────────────────

    def execute_debate(
        self,
        topic: str,
        messages: List[Dict[str, str]],
        orchestrator=None,
        rounds: int = 2,
        num_critics: int = 2,
        max_steps: int = 10,
    ) -> Generator[str, None, None]:
        """
        AutoGen의 GroupChat 패턴: N:N 토론.

        PROPOSER → N명 CRITIC → PROPOSER(수정) → ... → ARBITER(최종)
        MessageBus 채널 기반으로 피드백을 교환합니다.

        Args:
            topic: 토론 주제
            messages: 원본 메시지
            orchestrator: OrchestratorAgent
            rounds: 토론 라운드 수
            num_critics: 비평가 수
        """
        # 토론 전용 채널
        channel = f"debate_{uuid.uuid4().hex[:8]}"
        self.message_bus.create_channel(channel)

        yield f"⚖️ **[Debate]** 토론 시작: {topic[:60]}...\n"
        yield f"📌 라운드: {rounds}, 비평가: {num_critics}명\n\n"

        # 임시 에이전트 생성
        proposer = self.create_temp_agent("PROPOSER", "debate")
        self.message_bus.subscribe(channel, proposer)

        critics = []
        for i in range(num_critics):
            critic = self.create_temp_agent("CRITIC", f"debate_{i}")
            self.message_bus.subscribe(channel, critic)
            critics.append(critic)

        current_proposal = ""
        debate_log = []

        for round_num in range(1, rounds + 1):
            yield f"## 🔄 Round {round_num}\n\n"

            # 1. Proposer 제안
            if round_num == 1:
                prompt = (
                    f"다음 주제에 대해 최적의 해결책을 제안하세요.\n\n주제: {topic}"
                )
            else:
                prompt = (
                    f"CRITIC들의 피드백을 반영하여 제안을 개선하세요.\n\n"
                    f"이전 제안: {current_proposal[:500]}..."
                )

            yield "### 💡 PROPOSER\n"
            proposal_parts = []
            if orchestrator and hasattr(orchestrator, "_generate_for_role"):
                # orchestrator의 모델 생성 사용
                for chunk in orchestrator._generate_for_role(
                    "PROPOSER", prompt, messages
                ):
                    proposal_parts.append(chunk)
                    yield chunk
            else:
                result = proposer.run(prompt, model_manager=self.model_manager)
                proposal_parts.append(result)
                yield result

            current_proposal = "".join(proposal_parts)
            debate_log.append(f"## Round {round_num} - PROPOSER\n{current_proposal}")

            # MessageBus에 발행
            self.message_bus.publish(channel, "PROPOSER", current_proposal)
            yield "\n\n"

            # 2. Critics 비평
            for idx, critic in enumerate(critics, 1):
                yield f"### 🔍 CRITIC {idx}\n"

                critique_prompt = (
                    f"다음 제안을 비판적으로 분석하세요. "
                    f"엣지 케이스, 보안 취약점, 성능 문제를 찾아주세요.\n\n"
                    f"제안: {current_proposal[:500]}..."
                )

                critique_parts = []
                if orchestrator and hasattr(orchestrator, "_generate_for_role"):
                    for chunk in orchestrator._generate_for_role(
                        "CRITIC", critique_prompt, messages
                    ):
                        critique_parts.append(chunk)
                        yield chunk
                else:
                    result = critic.run(
                        critique_prompt, model_manager=self.model_manager
                    )
                    critique_parts.append(result)
                    yield result

                critique = "".join(critique_parts)
                debate_log.append(f"## Round {round_num} - CRITIC {idx}\n{critique}")
                self.message_bus.publish(channel, f"CRITIC_{idx}", critique)
                yield "\n\n"

        # 3. Arbiter 최종 중재
        yield "## ⚖️ ARBITER — 최종 합의안\n\n"

        arbiter = self.create_temp_agent("ARBITER", "debate")
        full_log = "\n\n".join(debate_log)
        arbiter_prompt = (
            f"토론 기록을 분석하여 최종 합의안을 도출하세요.\n\n"
            f"토론 기록:\n{full_log}\n\n"
            f"객관적으로 장단점을 분석하고, 최종 해결책만 출력하세요."
        )

        if orchestrator and hasattr(orchestrator, "_generate_for_role"):
            for chunk in orchestrator._generate_for_role(
                "ARBITER", arbiter_prompt, messages
            ):
                yield chunk
        else:
            result = arbiter.run(arbiter_prompt, model_manager=self.model_manager)
            yield result

        yield "\n\n✅ **[Debate 완료]**\n"

    # ─── 유틸리티 ─────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Fabric 상태 요약."""
        return {
            "active_agents": list(self._agent_registry.keys()),
            "agent_count": len(self._agent_registry),
            "kanban": self.kanban.get_board_state(),
            "message_channels": list(self.message_bus.channels.keys()),
        }

    def cleanup_temp_agents(self):
        """임시 에이전트 정리."""
        temp_keys = [k for k in self._agent_registry if k.startswith("TEMP_")]
        for key in temp_keys:
            del self._agent_registry[key]
        if temp_keys:
            logger.info(f"[AgentFabric] Cleaned up {len(temp_keys)} temp agents")
